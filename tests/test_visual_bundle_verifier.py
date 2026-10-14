from tests.local_scratch import temporary_directory
"""Snapshot verifier rejects changed, missing and mismatched retained records."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from tools.verify_visual_bundle import verify

class BundleVerifierTests(unittest.TestCase):
    def fixture(self,root):
        scene=json.dumps({'provenance':[{'snapshot':'evidence.json','sha256':hashlib.sha256(b'{}').hexdigest()}]})
        (root/'scene.json').write_text(scene)
        (root/'evidence.json').write_text('{}')
        (root/'index.html').write_text('<script id="scene-data" type="application/json">'+scene+'</script>')
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
        (root/'build_receipt.json').write_text(json.dumps({'status':'PASS','outputs':hashes,'scene_sha256':hashes['scene.json'],'html_sha256':hashes['index.html']}))
    def test_complete_snapshot(self):
        with temporary_directory() as d:
            p=Path(d);self.fixture(p);self.assertEqual(verify(p)['status'],'PASS')
    def test_missing_and_changed_evidence(self):
        with temporary_directory() as d:
            p=Path(d);self.fixture(p);(p/'evidence.json').write_text('{"changed":true}')
            self.assertIn('HASH_MISMATCH',{e['error'] for e in verify(p)['errors']})
            (p/'evidence.json').unlink()
            self.assertIn('MISSING',{e['error'] for e in verify(p)['errors']})
    def test_rehashed_html_still_requires_same_embedded_scene(self):
        with temporary_directory() as d:
            p=Path(d);self.fixture(p);(p/'index.html').write_text('<script id="scene-data">{}</script>')
            r=json.loads((p/'build_receipt.json').read_text());digest=hashlib.sha256((p/'index.html').read_bytes()).hexdigest()
            r['html_sha256']=digest;r['outputs']['index.html']=digest;(p/'build_receipt.json').write_text(json.dumps(r))
            self.assertIn('EMBEDDED_SCENE_MISMATCH',{e['error'] for e in verify(p)['errors']})
    def test_manifest_cannot_escape_bundle(self):
        with temporary_directory() as d:
            p=Path(d);self.fixture(p);r=json.loads((p/'build_receipt.json').read_text());r['outputs']['../outside']='0'*64
            (p/'build_receipt.json').write_text(json.dumps(r))
            self.assertIn('OUTSIDE_BUNDLE',{e['error'] for e in verify(p)['errors']})

    def test_gzip_transport_preserves_raw_scene_binding(self):
        import gzip,base64
        with temporary_directory() as d:
            p=Path(d);self.fixture(p);raw=(p/'scene.json').read_bytes()
            encoded=base64.b64encode(gzip.compress(raw,mtime=0)).decode()
            (p/'index.html').write_text('<script id="scene-data" data-encoding="gzip-base64">'+encoded+'</script>')
            r=json.loads((p/'build_receipt.json').read_text());r['embedded_transport']='gzip-base64'
            r['html_sha256']=hashlib.sha256((p/'index.html').read_bytes()).hexdigest();r['outputs']['index.html']=r['html_sha256'];(p/'build_receipt.json').write_text(json.dumps(r))
            self.assertEqual(verify(p)['status'],'PASS')
