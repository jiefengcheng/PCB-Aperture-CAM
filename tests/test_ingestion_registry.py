import copy
import json
import tempfile
import unittest
from pathlib import Path
from src.ingestion_registry import local, sha, verify

class IngestionIntegrityTests(unittest.TestCase):
    def test_intake_projection_is_sealed_and_client_specific(self):
        from src.ingestion_contracts import intake_projection
        config=json.loads(Path('contracts/ingestion_registry_v1.json').read_text())
        projection=intake_projection(config,lambda path:Path(path).read_bytes())
        self.assertEqual(projection['dataset_id'],'client:vme-wren:20261016:v1')
        self.assertEqual(len(projection['raw_files']),44)
        self.assertEqual(set(projection['artifacts']),{'entry','manifest','checksums'})
        def changed(path):
            raw=Path(path).read_bytes()
            return raw+b' ' if path.endswith('metadata/manifest.json') else raw
        with self.assertRaisesRegex(ValueError,'does not match seal'):
            intake_projection(config,changed)

    def test_missing_stale_and_escape(self):
        with tempfile.TemporaryDirectory(dir='out') as d:
            root=Path(d).resolve();p=root/'input';p.write_text('frozen')
            row={'path':'input','sha256':sha(p)}
            verify(root,[row])
            p.write_text('changed')
            with self.assertRaisesRegex(ValueError,'STALE'):verify(root,[row])
            p.unlink()
            with self.assertRaisesRegex(ValueError,'MISSING'):verify(root,[row])
            with self.assertRaisesRegex(ValueError,'escapes'):local(root,'../outside')

    def test_five_registration_groups_and_distinct_limits(self):
        config=json.loads(Path('contracts/ingestion_registry_v1.json').read_text())
        self.assertEqual(len(config['datasets']),5)
        self.assertEqual(len({d['id'] for d in config['datasets']}),5)
        self.assertTrue(all(d['sources'] and d['evidence'] for d in config['datasets']))
        glow=next(d for d in config['datasets'] if d['label']=='GlowStitch')
        self.assertIn('NOT_ESTABLISHED',glow['qualification'])
        self.assertIn('unknown',glow['intent'])

class PublicationPathTests(unittest.TestCase):
    """Exercise the actual publisher and CLI, including coherently rehashed corruption."""
    @classmethod
    def setUpClass(cls):
        import shutil
        from src.ingestion_registry import publish
        cls.workspace = tempfile.TemporaryDirectory(dir='out')
        cls.root = Path(cls.workspace.name).resolve()
        project = Path('.').resolve()
        from src.ingestion_registry import IMPLEMENTATION_SOURCES
        for name in IMPLEMENTATION_SOURCES:
            target=cls.root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(project/name,target)
        (cls.root/'replay').mkdir()
        (cls.root/'replay/scene.json').write_text(json.dumps({'integrity':'VERIFIED_AT_GENERATION','cases':[{'id':'test'}]}))
        (cls.root/'seal').write_text('test seal')
        (cls.root/'source').write_text('test source')
        (cls.root/'evidence.json').write_text('{"test":"retained"}')
        binding=lambda p:{'path':p,'sha256':sha(cls.root/p)}
        cls.config={'schema':'pcb-ingestion-registration-v1','dataset_seal':binding('seal'),
                    'replay_bundle':'replay','replay_bindings':[binding('replay/scene.json')],
                    'datasets':[{'id':'test','label':'Test dataset','sources':[binding('source')],
                                 'evidence':[binding('evidence.json')]}]}
        cls.destination=cls.root/'out/workbench'
        cls.bundle=publish(cls.root,cls.config,cls.destination)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def cli(self,bundle):
        import subprocess,sys
        return subprocess.run([sys.executable,'tools/ingestion.py','--verify',str(bundle)],text=True,capture_output=True)

    def rehash(self,bundle):
        p=bundle/'receipt.json';receipt=json.loads(p.read_text())
        receipt['outputs']={str(q.relative_to(bundle)):sha(q) for q in bundle.rglob('*') if q.is_file() and q!=p}
        p.write_text(json.dumps(receipt))

    def test_actual_cli_accepts_staged_verified_publication(self):
        result=self.cli(self.bundle)
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertEqual(json.loads(result.stdout)['datasets_verified'],1)

    def test_intake_metadata_and_display_projection_reject_coherent_rehash(self):
        from src.ingestion_registry import publish
        from tools.visual_report import embed_scene
        import hashlib,shutil
        package=self.root/'intake_source'
        (package/'metadata').mkdir(parents=True,exist_ok=True)
        (package/'raw').mkdir(exist_ok=True)
        (package/'raw/source').write_text('test source')
        (package/'index.md').write_text('Frozen intake index')
        manifest={'dataset_id':'test','input_sets':{'sample':{'file_count':1}},
                  'files':[{'path':'raw/source','sha256':sha(package/'raw/source'),'bytes':11}]}
        (package/'metadata/manifest.json').write_text(json.dumps(manifest))
        (package/'SHA256SUMS').write_text(''.join(sha(package/name)+'  '+name+'\n'
            for name in ['index.md','metadata/manifest.json','raw/source']))
        config=copy.deepcopy(self.config)
        config['dataset_seal']={'path':'intake_source/SHA256SUMS','sha256':sha(package/'SHA256SUMS')}
        config['datasets'][0]['sources']=[{'path':'intake_source/raw/source','sha256':sha(package/'raw/source')}]
        published=publish(self.root,config,self.destination)
        self.assertEqual(self.cli(published).returncode,0)
        for fault in ['metadata','display']:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(dir='out') as directory:
                bundle=Path(directory)/'bundle';shutil.copytree(published,bundle)
                if fault=='metadata':
                    (bundle/'intake/index.md').write_text('Changed metadata')
                else:
                    old=(bundle/'scene.json').read_text();scene=json.loads(old)
                    scene['ingestion']['intake']['raw_files'][0]['bytes']=999
                    new=embed_scene(scene);(bundle/'scene.json').write_text(new)
                    html=(bundle/'index.html').read_text().replace(old,new).replace(
                        hashlib.sha256(old.encode()).hexdigest(),hashlib.sha256(new.encode()).hexdigest())
                    (bundle/'index.html').write_text(html)
                self.rehash(bundle)
                result=self.cli(bundle)
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertIn('Intake metadata' if fault=='metadata' else 'Displayed intake',result.stdout)

    def test_actual_cli_rejects_failed_unknown_and_empty_receipts(self):
        for receipt in [{'status':'FAIL','outputs':{}},{'outputs':{}},
                        {'schema':'pcb-ingestion-publication-v2','status':'FAIL','outputs':{}},
                        {'schema':'pcb-ingestion-publication-v2','status':'PASS','outputs':{}}]:
            with self.subTest(receipt=receipt),tempfile.TemporaryDirectory(dir='out') as directory:
                p=Path(directory);(p/'receipt.json').write_text(json.dumps(receipt))
                self.assertNotEqual(self.cli(p).returncode,0)

    def test_actual_cli_rejects_rehashed_missing_files_scene_registry_and_evidence(self):
        import shutil
        for fault in ['missing_index','missing_evidence','scene_mismatch','registry_mismatch','invented_measurements']:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(dir='out') as directory:
                p=Path(directory)/'bundle';shutil.copytree(self.bundle,p)
                if fault=='missing_index':(p/'index.html').unlink()
                elif fault=='missing_evidence':
                    scene=json.loads((p/'scene.json').read_text())
                    (p/scene['ingestion']['datasets'][0]['evidence'][0]['snapshot']).unlink()
                elif fault=='registry_mismatch':
                    c=json.loads((p/'registry.json').read_text());c['datasets'][0]['label']='changed';(p/'registry.json').write_text(json.dumps(c))
                else:
                    from tools.visual_report import embed_scene
                    import hashlib
                    old=(p/'scene.json').read_text();scene=json.loads(old)
                    scene['ingestion']['datasets'][0]['qualification_data']['records']=[{'invented':'metric'}]
                    new=embed_scene(scene);(p/'scene.json').write_text(new)
                    if fault=='invented_measurements':
                        html=(p/'index.html').read_text().replace(old,new).replace(hashlib.sha256(old.encode()).hexdigest(),hashlib.sha256(new.encode()).hexdigest());(p/'index.html').write_text(html)
                self.rehash(p)
                result=self.cli(p);self.assertNotEqual(result.returncode,0,result.stdout)

    def test_failed_or_stale_publication_preserves_previous_entry(self):
        from src.ingestion_registry import publish
        entry=self.destination/'index.html';before=entry.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'Injected failure'):
            publish(self.root,copy.deepcopy(self.config),self.destination,True)
        self.assertEqual(before,entry.read_bytes())
        config=copy.deepcopy(self.config);config['datasets'][0]['sources'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'STALE'):publish(self.root,config,self.destination)
        self.assertEqual(before,entry.read_bytes())
        self.assertFalse(list(self.destination.glob('.staging-*')))

    def test_publisher_keeps_registry_unchanged(self):
        from src.ingestion_registry import publish
        config=copy.deepcopy(self.config);before=copy.deepcopy(config)
        publish(self.root,config,self.destination)
        self.assertEqual(config,before)

    def test_identity_review_images_are_hash_bound_and_staged_for_findings(self):
        from src.ingestion_registry import publish
        review=self.root/'review_artifacts';(review/'images').mkdir(parents=True,exist_ok=True)
        (review/'groups').mkdir(parents=True,exist_ok=True)
        manifest={'schema':'pcb-native-object-manual-review-v1','entries':[{'image_file':'sample.svg'}]}
        (review/'manifest.json').write_text(json.dumps(manifest))
        (review/'images/sample.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        groups={'schema':'pcb-copper-neighborhood-review-v1','groups':[{'image_file':'group.svg'}]}
        (review/'groups.json').write_text(json.dumps(groups))
        (review/'groups/group.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>group</text></svg>')
        (review/'screenshot').mkdir()
        (review/'screenshot/pairs.csv').write_text('ORG,EDIT\na,b\n')
        (review/'DOMAIN_QUESTIONS.md').write_text('# PCB domain questions\n')
        config=copy.deepcopy(self.config)
        config['identity_reviews']={'test':{
            'manifest':{'path':'review_artifacts/manifest.json','sha256':sha(review/'manifest.json')},
            'images':[{'path':'review_artifacts/images/sample.svg','sha256':sha(review/'images/sample.svg')}],
            'summary':{'image_count':1},
            'groups_manifest':{'path':'review_artifacts/groups.json','sha256':sha(review/'groups.json')},
            'group_images':[{'path':'review_artifacts/groups/group.svg','sha256':sha(review/'groups/group.svg')}],
            'group_summary':{'group_count':1},
            'screenshot_evidence':[{'id':'pairs','label':'Joint crop pairs','kind':'csv',
                                    'path':'review_artifacts/screenshot/pairs.csv',
                                    'sha256':sha(review/'screenshot/pairs.csv')}],
            'context':{'path':'review_artifacts/DOMAIN_QUESTIONS.md','sha256':sha(review/'DOMAIN_QUESTIONS.md')}}}
        run=publish(self.root,config,self.destination)
        scene=json.loads((run/'scene.json').read_text())
        linked=scene['ingestion']['identity_reviews']['test']
        self.assertEqual(linked['image_count'],1)
        self.assertEqual(linked['group_image_count'],1)
        image=run/linked['images_root']/'sample.svg'
        self.assertTrue(image.exists())
        self.assertEqual(image.read_text(),
                         '<svg xmlns="http://www.w3.org/2000/svg"/>')
        group_image=run/linked['group_images_root']/'group.svg'
        self.assertTrue(group_image.exists())
        self.assertEqual(group_image.read_text(), '<svg xmlns="http://www.w3.org/2000/svg"><text>group</text></svg>')
        self.assertEqual((run/linked['context']['snapshot']).read_text(), '# PCB domain questions\n')
        pair_evidence=linked['screenshot_evidence'][0]
        self.assertEqual(pair_evidence['id'],'pairs')
        self.assertEqual((run/pair_evidence['snapshot']).read_text(),'ORG,EDIT\na,b\n')
        self.assertEqual(self.cli(run).returncode,0)
        stale=copy.deepcopy(config)
        stale['identity_reviews']['test']['screenshot_evidence'][0]['sha256']='0'*64
        previous=(self.destination/'index.html').read_bytes()
        with self.assertRaisesRegex(ValueError,'STALE'):
            publish(self.root,stale,self.destination)
        self.assertEqual((self.destination/'index.html').read_bytes(),previous)

    def test_zero_registered_rows_is_a_real_verified_workbench_not_an_empty_receipt(self):
        from src.ingestion_registry import publish
        config=copy.deepcopy(self.config);config['datasets']=[]
        run=publish(self.root,config,self.destination)
        result=self.cli(run)
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertEqual(json.loads(result.stdout)['datasets_verified'],0)
        self.assertTrue((run/'index.html').is_file())

    def test_default_rebuild_retains_removed_rows_instead_of_reloading_canonical_recipe(self):
        from unittest.mock import patch
        from src.ingestion_registry import publish
        from tools import ingestion
        config=copy.deepcopy(self.config);config['datasets']=[]
        destination=self.root/'out/removed_registry'
        publish(self.root,config,destination)
        with patch.object(ingestion,'ROOT',self.root), patch.object(ingestion,'publish',return_value=destination/'recorded') as producer:
            ingestion.main(['--output',str(destination)])
        self.assertEqual(producer.call_args.args[1]['datasets'],[])

    def test_generation_review_is_explicit_and_does_not_claim_channel_availability(self):
        scene=json.loads((self.bundle/'scene.json').read_text())
        receipt=json.loads((self.bundle/'receipt.json').read_text())
        review=receipt['cursor_review']
        self.assertEqual(review,scene['ingestion']['cursor_review'])
        self.assertEqual(review['status'],'NOT_RUN')
        self.assertEqual(review['scope'],'AT_GENERATION')
        self.assertNotIn('CHANNEL_UNAVAILABLE',json.dumps(review))

    def test_actual_cli_rejects_invented_generation_review(self):
        import shutil
        with tempfile.TemporaryDirectory(dir='out') as directory:
            bundle=Path(directory)/'bundle';shutil.copytree(self.bundle,bundle)
            path=bundle/'receipt.json';receipt=json.loads(path.read_text())
            receipt['cursor_review']['status']='PASS'
            path.write_text(json.dumps(receipt))
            result=self.cli(bundle)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('review status',result.stdout)

    def test_immutable_run_cannot_be_used_as_publication_entry(self):
        from src.ingestion_registry import publish
        before=(self.bundle/'index.html').read_bytes()
        with self.assertRaisesRegex(ValueError,'immutable bundle'):
            publish(self.root,copy.deepcopy(self.config),self.bundle)
        self.assertEqual(before,(self.bundle/'index.html').read_bytes())

    def test_implementation_drift_rejects_before_entry_replacement(self):
        from unittest.mock import patch
        from src import ingestion_registry
        source=self.root/'web/ingestion_views.js';original=source.read_bytes()
        entry=self.destination/'index.html';before=entry.read_bytes()
        writer=ingestion_registry._write_workbench
        def drift(*args):
            writer(*args)
            source.write_bytes(original+b'\n// drift during generation\n')
        try:
            with patch('src.ingestion_registry._write_workbench',side_effect=drift):
                with self.assertRaisesRegex(ValueError,'STALE'):
                    ingestion_registry.publish(self.root,copy.deepcopy(self.config),self.destination)
            self.assertEqual(before,entry.read_bytes())
        finally:
            source.write_bytes(original)

    def test_entry_replace_failure_preserves_entry_and_removes_temporary_redirect(self):
        from unittest.mock import patch
        from src.ingestion_registry import publish
        entry=self.destination/'index.html';before=entry.read_bytes()
        with patch('src.ingestion_registry.os.replace',side_effect=OSError('simulated entry failure')):
            with self.assertRaisesRegex(OSError,'simulated entry failure'):
                publish(self.root,copy.deepcopy(self.config),self.destination)
        self.assertEqual(before,entry.read_bytes())
        self.assertFalse(list(self.destination.glob('.entry-*')))
        self.assertFalse(list(self.destination.glob('.staging-*')))



class ComparisonBindingTests(unittest.TestCase):
    def setUp(self):
        import shutil
        self.workspace=tempfile.TemporaryDirectory(dir='out')
        self.addCleanup(self.workspace.cleanup)
        self.root=Path(self.workspace.name).resolve()
        self.dataset=copy.deepcopy(json.loads(Path('contracts/ingestion_registry_v1.json').read_text())['datasets'][-1])
        # Copy only the recorded receipts and actual six display inputs.
        from src.ingestion_visuals import receipt_records,comparison_specs
        records=receipt_records(self.dataset,lambda ref:json.loads(Path(ref['path']).read_text()))
        specs=comparison_specs(self.dataset,records)
        self.bindings=[r['evidence'] for r in records]+[b for spec in specs for b in spec['inputs'].values()]
        for b in self.bindings:
            p=self.root/b['path'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(b['path'],p)
        self.source=next(s['inputs']['source'] for s in specs if s['receipt_role']=='discrepancy')

    def test_removed_flash_in_actual_render_copy_rejects_before_composition(self):
        from unittest.mock import patch
        from src.ingestion_visuals import comparison_views
        p=self.root/self.source['path'];raw=p.read_bytes();flash=b'X184191125Y-292397175D03*'
        self.assertEqual(raw.count(flash),1);p.write_bytes(raw.replace(flash,b'',1))
        with patch('src.ingestion_visuals.read_region') as compose:
            with self.assertRaisesRegex(ValueError,'STALE'):comparison_views(self.root,self.dataset)
            compose.assert_not_called()

    def test_missing_actual_render_input_rejects(self):
        from src.ingestion_visuals import comparison_views
        (self.root/self.source['path']).unlink()
        with self.assertRaisesRegex(ValueError,'MISSING'):comparison_views(self.root,self.dataset)

    def test_input_drift_during_composition_rejects(self):
        from unittest.mock import patch
        from shapely.geometry import box
        from src.ingestion_visuals import comparison_views
        def compose(*args):
            (self.root/self.source['path']).write_bytes(b'changed during read')
            return {'geometry':box(0,0,1,1)}
        with patch('src.ingestion_visuals.read_region',side_effect=compose):
            with self.assertRaisesRegex(ValueError,'STALE'):comparison_views(self.root,self.dataset)

    def test_receipt_values_are_projected_and_dataset_specific(self):
        from unittest.mock import patch
        from shapely.geometry import box
        from src.ingestion_visuals import comparison_views
        ref=self.dataset['presentation']['receipts']['discrepancy'];p=self.root/ref['path']
        report=json.loads(p.read_text());report['source_only_flash_count']=7;report['symmetric_difference_area_mm2']=2.5;p.write_text(json.dumps(report))
        new_hash=sha(p);ref['sha256']=new_hash
        next(e for e in self.dataset['evidence'] if e['path']==ref['path'])['sha256']=new_hash
        drill_ref=self.dataset['presentation']['receipts']['drills'];p=self.root/drill_ref['path'];report=json.loads(p.read_text());report['PTH']['drills']['matched']=123;p.write_text(json.dumps(report))
        new_hash=sha(p);drill_ref['sha256']=new_hash;next(e for e in self.dataset['evidence'] if e['path']==drill_ref['path'])['sha256']=new_hash
        with patch('src.ingestion_visuals.read_region',return_value={'geometry':box(0,0,1,1)}):
            result=comparison_views(self.root,self.dataset)
        metrics={r['role']:r['metrics'] for r in result['records']}
        self.assertEqual(metrics['discrepancy']['source_only_flash_count'],7)
        self.assertEqual(metrics['discrepancy']['symmetric_difference_area_mm2'],2.5)
        self.assertEqual(metrics['drills']['PTH']['drills']['matched'],123)
        self.assertTrue(all(v['inputs']['source']['path'].startswith('dataset/') for v in result['comparisons']))
        other={'id':'client:another','sources':[],'evidence':[]}
        self.assertEqual(comparison_views(self.root,other),{'records':[],'comparisons':[]})
