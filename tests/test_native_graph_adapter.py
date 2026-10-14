from tests.local_scratch import temporary_directory
from pathlib import Path
import tempfile
import os
import unittest
from src.native_graph_adapter import NativeGraphAdapter
from src.revision_catalog import CatalogError

BINARY=Path(os.environ.get('PCB_CAM_NATIVE_SHADOW_BINARY','out/consolidation/native/pcb_graph_shadow'))
@unittest.skipUnless(BINARY.is_file(),'Pinned native build unavailable; not a native PASS')
class NativeGraphAdapterTests(unittest.TestCase):
    def setUp(self):self.tmp=temporary_directory();self.root=Path(self.tmp.name);self.adapter=NativeGraphAdapter(BINARY)
    def tearDown(self):self.tmp.cleanup()
    def relations(self):
        long='source-revision:'+('x'*350)
        return long,[{'occurrence':str(i),'source':long,'target':target,'type':'physical_contact'} for i,target in enumerate(['b','c','b'])]
    def test_long_identity_duplicates_reopen_direction_and_local_vids(self):
        long,relations=self.relations();folder=self.root/'one'
        manifest=self.adapter.materialize(folder,'snapshot-one','physical_contact',relations,local_tag=11)
        self.assertEqual(manifest['proof_occurrences'],3);self.assertEqual(manifest['deduplicated_edges'],2)
        q=NativeGraphAdapter(BINARY).query(folder,'snapshot-one',[long])
        self.assertTrue(q['complete']);self.assertEqual({r['target'] for r in q['records']},{'b','c'})
        self.assertTrue(all(r['source']==long for r in q['records']))
        incoming=self.adapter.query(folder,'snapshot-one',['b'],direction='in')
        self.assertEqual(incoming['records'][0]['source'],long)
        other=self.root/'two'
        self.adapter.materialize(other,'snapshot-two','context',[{'occurrence':'p','source':'a','target':long,'type':'context'}],local_tag=3)
        self.assertEqual(self.adapter.query(other,'snapshot-two',['a'])['records'][0]['type'],'context')
        self.assertEqual(self.adapter.query(folder,'snapshot-one',[long])['records'],q['records'])
    def test_scope_stale_corrupt_and_bounded_completion(self):
        long,relations=self.relations();folder=self.root/'one';self.adapter.materialize(folder,'s','physical_contact',relations)
        self.assertEqual(self.adapter.query(folder,'s',[long],limit_per_seed=1)['status'],'TRUNCATED')
        self.assertEqual(self.adapter.query(folder,'s',['b'])['records'],[])
        with self.assertRaisesRegex(CatalogError,'OBJECT_OUTSIDE_MATERIALIZATION'):self.adapter.query(folder,'s',['absent'])
        with self.assertRaisesRegex(CatalogError,'STALE_NATIVE_SNAPSHOT'):self.adapter.query(folder,'wrong',[long])
        (folder/'identities.json').write_text('{}')
        with self.assertRaisesRegex(CatalogError,'NATIVE_MATERIALIZATION_HASH_MISMATCH'):self.adapter.query(folder,'s',[long])
    def test_wrong_relation_scope_rejected(self):
        _,relations=self.relations()
        with self.assertRaisesRegex(CatalogError,'RELATION_SCOPE_MISMATCH'):self.adapter.materialize(self.root/'bad','s','different',relations)

    def test_executed_layer_scope_and_cross_layer_proofs(self):
        relations=[{'occurrence':'front','source':'a','target':'b','type':'physical_contact','witness':{'layer':'F.Cu'}},{'occurrence':'back','source':'a','target':'c','type':'physical_contact','witness':{'layer':'B.Cu'}}]
        folder=self.root/'front';manifest=self.adapter.materialize(folder,'s','physical_contact',relations,layer='F.Cu')
        self.assertEqual(manifest['input_occurrences'],2);self.assertEqual(manifest['proof_occurrences'],1)
        q=self.adapter.query(folder,'s',['a'],expected_layer='F.Cu')
        self.assertEqual([r['target'] for r in q['records']],['b'])
        with self.assertRaisesRegex(CatalogError,'NATIVE_LAYER_SCOPE_MISMATCH'):self.adapter.query(folder,'s',['a'],expected_layer='B.Cu')
        with self.assertRaisesRegex(CatalogError,'OBJECT_OUTSIDE_MATERIALIZATION'):self.adapter.query(folder,'s',['c'],expected_layer='F.Cu')

    def test_failed_new_index_does_not_replace_prior_materialization(self):
        long,relations=self.relations();old=self.root/'accepted';self.adapter.materialize(old,'old','physical_contact',relations)
        def fail(phase,folder):
            if phase=='INDEX_BUILT':raise OSError('injected before native manifest publication')
        pending=self.root/'pending'
        with self.assertRaisesRegex(OSError,'injected'):self.adapter.materialize(pending,'new','physical_contact',relations,hook=fail)
        self.assertFalse((pending/'manifest.json').exists())
        self.assertTrue(self.adapter.query(old,'old',[long])['complete'])
        with self.assertRaisesRegex(CatalogError,'NATIVE_MATERIALIZATION_UNAVAILABLE'):self.adapter.query(pending,'new',[long])

    def test_local_tag_numeric_boundaries(self):
        _,relations=self.relations()
        for tag in [0,254]:
            folder=self.root/('tag'+str(tag));self.adapter.materialize(folder,'s','physical_contact',relations,local_tag=tag)
            self.assertTrue(self.adapter.query(folder,'s',[relations[0]['source']])['complete'])
        with self.assertRaisesRegex(CatalogError,'INVALID_LOCAL_TAG'):self.adapter.materialize(self.root/'invalid','s','physical_contact',relations,local_tag=255)
