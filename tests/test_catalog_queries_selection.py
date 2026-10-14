from pathlib import Path
import json
import sqlite3
import unittest
from tests.local_scratch import temporary_directory
from src.revision_catalog import RevisionCatalog,CatalogError
from src.native_inventory import inventory

HEADER='(kicad_pcb (layers (0 "F.Cu" signal) (2 "B.Cu" signal)) '
class CatalogQuerySelectionTests(unittest.TestCase):
    def setUp(self):self.tmp=temporary_directory();self.root=Path(self.tmp.name);self.catalog=RevisionCatalog(self.root)
    def tearDown(self):self.catalog.close();self.tmp.cleanup()
    def put(self,extra=''):
        raw=(HEADER+'(footprint "f" (at 0 0) (layer "F.Cu") (uuid fp) (pad "1" smd rect (at 0 0) (size 2 2) (layers "F.Cu") (uuid a))) (segment (start 1 0) (end 3 0) (width .2) (layer "F.Cu") (uuid b)) (group "named" (id g) (members a b)) '+extra+')').encode()
        inv=inventory(raw)
        for payload in inv['payloads'].values():self.catalog.put_payload(payload)
        revision=self.catalog.import_revision(raw,inv['objects'],[],{'extractor':inv['version']})
        return revision,inv['objects']
    def test_ordered_paging_properties_layers_and_bounded_results(self):
        revision,objects=self.put()
        all_rows=self.catalog.query(revision)['records'];first=self.catalog.query(revision,limit=2)
        second=self.catalog.query(revision,after_id=first['next_after_id'],limit=10)
        self.assertEqual(first['status'],'TRUNCATED');self.assertEqual(first['records']+second['records'],all_rows)
        pads=self.catalog.query(revision,properties={'kind':'pad'},layer='F.Cu')
        self.assertEqual(len(pads['records']),1);self.assertEqual(pads['records'][0]['native_id'],'a')
        self.assertEqual(self.catalog.query(revision,work_limit=1)['status'],'WORK_BUDGET_EXCEEDED')
        self.assertEqual(self.catalog.query(revision,result_byte_limit=1)['status'],'TRUNCATED_BYTE_BUDGET')
        with self.assertRaisesRegex(CatalogError,'UNSUPPORTED_PROPERTY_QUERY'):self.catalog.query(revision,properties={'permission':'write'})
    def test_named_group_dedup_parent_dependency_and_no_implicit_write(self):
        revision,objects=self.put();pad=next(r for r in objects if r['native_id']=='a');fp=next(r for r in objects if r['native_id']=='fp')
        selection=self.catalog.select(revision,native_ids=['a','a'],named_groups=['named'],writable_ids=[pad['id']])
        self.assertEqual(len(selection['selected_ids']),3);self.assertEqual(selection['dependency_ids'],[fp['id']]);self.assertEqual(selection['writable_ids'],[pad['id']])
        self.assertTrue(all(not x['grant_write'] for x in selection['expansion']))
        self.assertTrue(selection['diagnostic_only'])
    def test_missing_ambiguous_nested_and_cyclic_groups_reject(self):
        revision,_=self.put('(group "named" (id other) (members a))')
        with self.assertRaisesRegex(CatalogError,'AMBIGUOUS_GROUP_REFERENCE'):self.catalog.select(revision,named_groups=['named'])
        with self.assertRaisesRegex(CatalogError,'MISSING_GROUP_REFERENCE'):self.catalog.select(revision,named_groups=['absent'])
        cycle,_=self.put('(group "cycle" (id c) (members c))')
        with self.assertRaisesRegex(CatalogError,'GROUP_REFERENCE_CYCLE'):self.catalog.select(cycle,named_groups=['cycle'])
    def test_region_exact_shape_and_explicit_unknown_coverage(self):
        revision,objects=self.put('(gr_text "unknown copper text" (at 0 0) (layer "F.Cu"))')
        result=self.catalog.region_query(revision,[-.5,-.5,.5,.5],'F.Cu')
        self.assertTrue(result['complete']);self.assertFalse(result['engineering_complete']);self.assertEqual([r['native_id'] for r in result['records']],['a'])
        self.assertEqual(sum(result['unsupported_counts'].values()),1)
        selected=self.catalog.select(revision,regions=[{'bounds_mm':[-.5,-.5,.5,.5],'layer':'F.Cu'}])
        self.assertFalse(selected['engineering_complete']);self.assertEqual(selected['writable_ids'],[])
        with self.assertRaisesRegex(CatalogError,'INCOMPLETE_REGION_SELECTION'):self.catalog.select(revision,regions=[{'bounds_mm':[0,0,3,3],'layer':'F.Cu','work_limit':0}])
    def test_validation_cache_is_private_and_invalidated_by_external_updates(self):
        revision,objects=self.put();snapshot=self.catalog.snapshot(revision);snapshot['objects'][0]['native_id']='caller mutation'
        self.assertNotEqual(self.catalog.query(revision)['records'][0]['native_id'],'caller mutation')
        self.assertTrue(self.catalog.query(revision)['verification']['cache_hit'])
        with sqlite3.connect(self.root/'catalog.sqlite') as external:external.execute('UPDATE objects SET native_id=? WHERE revision=? AND object_id=?',('wrong-index',revision,objects[0]['id']))
        with self.assertRaisesRegex(CatalogError,'CATALOG_INDEX_COLUMN_MISMATCH'):self.catalog.query(revision)
    def test_explicit_all_uses_bounded_batches(self):
        revision,objects=self.put();self.assertEqual(self.catalog.select(revision)['records'],[])
        selection=self.catalog.select(revision,all_objects=True)
        self.assertEqual(len(selection['records']),len(objects));self.assertTrue(selection['complete'])
        with self.assertRaisesRegex(CatalogError,'INCOMPLETE_SELECTION'):self.catalog.select(revision,all_objects=True,limit=1)

    def test_source_mutation_during_verification_rejects(self):
        revision,_=self.put();original=self.catalog.read_payload
        def changed_after_read(key):
            data=original(key);(self.catalog.payloads/key).write_bytes(data+b' ');return data
        self.catalog.read_payload=changed_after_read
        with self.assertRaisesRegex(CatalogError,'SOURCE_CHANGED_DURING_VERIFICATION'):self.catalog.snapshot(revision)

    def test_region_results_do_not_expose_private_cache(self):
        revision,_=self.put();result=self.catalog.region_query(revision,[-1,-1,1,1],'F.Cu')
        result['records'][0]['native_id']='caller change'
        self.assertEqual(self.catalog.query(revision,native_id='a')['records'][0]['native_id'],'a')
        self.assertEqual(self.catalog.region_query(revision,[-1,-1,1,1],'F.Cu')['records'][0]['native_id'],'a')

class ComponentDiagnosticTests(unittest.TestCase):
    def test_component_filter_uses_envelope_area_and_oriented_aspect(self):
        from tools.consolidation_pipeline import component_filter
        objects=[{'id':'a','bounds_mm':[0,0,2,1]},{'id':'b','bounds_mm':[8,0,10,1]},{'id':'degenerate','bounds_mm':[0,3,2,3]}]
        result=component_filter('revision',objects,[{'id':'wide','layer':'F.Cu','members':['a','b']},{'id':'flat','layer':'F.Cu','members':['degenerate']}])
        self.assertEqual(result['status'],'COMPLETE');self.assertEqual(len(result['records']),1)
        self.assertEqual(result['records'][0]['bbox_area_mm2'],10);self.assertEqual(result['records'][0]['aspect_width_over_height'],10)
        self.assertEqual(result['selected_ids'],['a','b']);self.assertIn('not filled copper area',result['scope'])
