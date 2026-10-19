import copy
import json
from pathlib import Path
import tempfile
import unittest
from src.catalogue_scene import project,verify_projection
from src.ingestion_files import sha,write_json
from tests.test_common_catalogue import fixture


class CatalogueThemeProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='out');self.root=Path(self.tmp.name)
        self.store=self.root/'common_context/selection';self.store.mkdir(parents=True)
        revision,_=fixture(self.store)
        from src.common_catalogue import retrieve
        result=retrieve(self.store,revision)
        self.acceptance={'schema':'pcb-common-context/1','status':'PASS','dataset_revision':revision,
                         'result_sha256':result['result_sha256'],'writer_pid':1,'reader_pid':2,'export_reader_pid':3,
                         'scope':'unit fixture; not real client execution','run':'test fixture'}
        write_json(self.root/'common_context/acceptance.json',self.acceptance)
        self.config={'common_context':{'sha256':sha(self.root/'common_context/acceptance.json')},
                     'common_context_presentation':'storage-themes-v1','datasets':[{'id':'client:vme-wren:20261016:v1'}]}
    def tearDown(self):self.tmp.cleanup()
    def test_actual_tables_payloads_and_rebuilt_spatial_state(self):
        view=project(self.store,self.acceptance,themes=True);facts=view['themes']
        self.assertEqual(facts['sqlite']['counts'],{'revisions':8,'objects':8,'relations':0})
        self.assertEqual(facts['sqlite']['sha256'],sha(self.store/'store/catalog.sqlite'))
        self.assertEqual(facts['payloads']['count'],len(list((self.store/'store/payloads').iterdir())))
        self.assertEqual(facts['payloads']['bytes'],sum(p.stat().st_size for p in (self.store/'store/payloads').iterdir()))
        self.assertEqual(facts['spatial']['persistence'],'REBUILT_IN_MEMORY_ON_REOPEN')
        self.assertEqual(facts['spatial']['indexed_native_shapes'],3)
        self.assertTrue(any(i['name']=='native_lookup' for i in facts['sqlite']['indexes']))
        self.assertEqual(len(facts['artifacts']),8)
    def test_altered_or_missing_theme_facts_reject(self):
        view=project(self.store,self.acceptance,themes=True)
        write_json(self.root/'common_context/result.json',view['result'])
        verify_projection(self.root,self.config,{'common_context':view})
        for mutate in [lambda v:v['themes']['sqlite']['counts'].update(objects=999),
                       lambda v:v['themes']['spatial'].update(persistence='PERSISTED_RTREE'),
                       lambda v:v.pop('themes')]:
            changed=copy.deepcopy(view);mutate(changed)
            with self.assertRaisesRegex(ValueError,'PROJECTION_MISMATCH'):verify_projection(self.root,self.config,{'common_context':changed})
    def test_existing_publication_projection_still_verifies(self):
        view=project(self.store,self.acceptance)
        self.assertNotIn('themes',view);self.config.pop('common_context_presentation')
        write_json(self.root/'common_context/result.json',view['result'])
        verify_projection(self.root,self.config,{'common_context':view})


if __name__=='__main__':unittest.main()
