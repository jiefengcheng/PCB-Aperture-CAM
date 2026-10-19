import copy
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from src.directory_intake import package_inventory, remove_dataset, restore_directory
from src.ingestion_files import sha
from tools.ingestion_server import make_handler


class DirectoryIntakeTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(dir='out')
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name).resolve()
        self.package = self.root / 'dataset/sample'
        (self.package / 'metadata').mkdir(parents=True)
        (self.package / 'raw').mkdir()
        (self.root / 'contracts').mkdir()
        (self.package / 'raw/board.gbr').write_text('original source')
        (self.package / 'index.md').write_text('preserved inputs')
        rows = [{'path': name, 'sha256': sha(self.package / name), 'bytes': (self.package / name).stat().st_size,
                 'role': 'source' if name.startswith('raw/') else 'metadata'} for name in ['index.md', 'raw/board.gbr']]
        (self.package / 'metadata/manifest.json').write_text(json.dumps({'schema': 'pcb-cam-dataset-manifest-v1', 'dataset_id': 'sample', 'files': rows}))
        (self.package / 'SHA256SUMS').write_text(''.join(sha(self.package / name) + '  ' + name + '\n'
            for name in ['index.md', 'raw/board.gbr', 'metadata/manifest.json']))
        binding = lambda name: {'path': name, 'sha256': sha(self.root / name)}
        dataset = {'id': 'sample', 'label': 'Sample', 'sources': [binding('dataset/sample/raw/board.gbr')],
                   'evidence': [binding('dataset/sample/metadata/manifest.json')]}
        self.profile = {'schema': 'pcb-ingestion-package-profiles-v1', 'packages': [{
            'package_root': 'dataset/sample', 'seal': binding('dataset/sample/SHA256SUMS'), 'dataset': dataset}]}
        self.profile_file = self.root / 'contracts/ingestion_packages_v1.json'
        self.profile_file.write_text(json.dumps(self.profile))
        self.config = {'schema': 'pcb-ingestion-registration-v1', 'datasets': [dict(dataset, id='other')]}
        _, self.inventory = package_inventory(self.root, self.package, self.profile['packages'][0]['seal']['sha256'])

    def restore(self, inventory=None):
        return restore_directory(self.root, self.config, 'dataset/sample', inventory)

    def test_remove_selected_row_preserves_files_history_recipe_and_can_reconstruct(self):
        registered = self.restore(self.inventory)
        original = copy.deepcopy(registered)
        removed = remove_dataset(registered, 'sample')
        self.assertEqual(registered, original)
        self.assertEqual(removed['datasets'], self.config['datasets'])
        self.assertNotIn('directory_intake', removed)
        _, after = package_inventory(self.root, self.package, self.profile['packages'][0]['seal']['sha256'])
        self.assertEqual(after, self.inventory)
        self.assertTrue(self.profile_file.is_file())
        restored = restore_directory(self.root, removed, 'dataset/sample', self.inventory)
        self.assertEqual(restored['datasets'], original['datasets'])

    def test_remove_last_row_allows_empty_registration_and_unknown_ids_reject(self):
        removed = remove_dataset(self.config, 'other')
        self.assertEqual(removed['datasets'], [])
        for identity in ['missing', '', None]:
            with self.assertRaises(ValueError): remove_dataset(self.config, identity)

    def test_missing_row_is_restored_idempotently_without_changing_inputs_or_registry(self):
        before = copy.deepcopy(self.config)
        result = self.restore(self.inventory)
        self.assertEqual(self.config, before)
        self.assertEqual(len(result['datasets']), 2)
        self.assertTrue(result['directory_intake']['selected_bytes_checked'])
        again = restore_directory(self.root, result, 'dataset/sample', self.inventory)
        self.assertEqual(again, result)
        self.assertEqual(sha(self.package / 'raw/board.gbr'), self.inventory[-1]['sha256'])

    def test_changed_selected_bytes_and_duplicate_or_missing_selected_files_reject(self):
        for fault in ['changed', 'missing', 'duplicate']:
            with self.subTest(fault=fault):
                selected = copy.deepcopy(self.inventory)
                if fault == 'changed': selected[-1]['sha256'] = '0' * 64
                if fault == 'missing': selected.pop()
                if fault == 'duplicate': selected.append(selected[0])
                with self.assertRaises(ValueError): self.restore(selected)

    def test_changed_missing_and_unlisted_disk_files_reject(self):
        p = self.package / 'raw/board.gbr'; original = p.read_bytes()
        for fault in ['changed', 'missing', 'unlisted']:
            with self.subTest(fault=fault):
                p.write_bytes(original)
                if fault == 'changed': p.write_bytes(original + b'x')
                if fault == 'missing': p.unlink()
                if fault == 'unlisted': (self.package / 'extra').write_text('unlisted')
                with self.assertRaises(ValueError): self.restore()

    def test_unknown_escape_symlink_and_conflicting_registration_reject(self):
        for directory in ['../escape', 'dataset/unknown']:
            with self.assertRaises(ValueError): restore_directory(self.root, self.config, directory)
        self.config['datasets'].append(dict(self.profile['packages'][0]['dataset'], label='conflicting'))
        with self.assertRaisesRegex(ValueError, 'conflicts'): self.restore()
        self.config['datasets'].pop()
        (self.package / 'link').symlink_to(self.package / 'index.md')
        with self.assertRaisesRegex(ValueError, 'symlink'): self.restore()

    def test_missing_bound_evidence_does_not_fabricate_a_review(self):
        self.profile['packages'][0]['dataset']['evidence'][0]['path'] = 'missing.json'
        self.profile_file.write_text(json.dumps(self.profile))
        with self.assertRaisesRegex(ValueError, 'MISSING'): self.restore()

    def test_http_origin_inventory_and_failure_preserve_previous_entry(self):
        destination = self.root / 'out/workbench'; destination.mkdir(parents=True)
        entry = destination / 'index.html'; entry.write_text('previous immutable publication')
        server = ThreadingHTTPServer(('127.0.0.1', 0), SimpleHTTPRequestHandler)
        server.RequestHandlerClass = make_handler(self.root, destination, self.config, server.server_port)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        def post(payload, origin, endpoint='/api/ingestion/directories'):
            conn = HTTPConnection('127.0.0.1', server.server_port)
            conn.request('POST', endpoint, json.dumps(payload), {'Content-Type': 'application/json', 'Origin': origin})
            response = conn.getresponse(); body = json.loads(response.read()); conn.close()
            return response.status, body
        origin = 'http://127.0.0.1:' + str(server.server_port)
        self.assertEqual(post({}, 'http://untrusted.example')[0], 403)
        self.assertEqual(post({'package_name': 'sample'}, origin)[0], 400)
        with patch('tools.ingestion_server.published_config', return_value=self.config), patch('tools.ingestion_server.publish', side_effect=RuntimeError('publication failed')):
            status, body = post({'package_name': 'sample', 'files': self.inventory}, origin)
            self.assertEqual(status, 400); self.assertIn('publication failed', body['error'])
            status, body = post({'dataset_id': 'other'}, origin, '/api/ingestion/remove')
            self.assertEqual(status, 400); self.assertIn('publication failed', body['error'])
        self.assertEqual(entry.read_text(), 'previous immutable publication')
