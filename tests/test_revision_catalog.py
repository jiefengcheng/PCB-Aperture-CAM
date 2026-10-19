from tests.local_scratch import temporary_directory
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from src.revision_catalog import RevisionCatalog,CatalogError
from src.source_locators import locate

class RevisionCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=temporary_directory();self.root=Path(self.tmp.name)
        self.store=RevisionCatalog(self.root)
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def fixture(self,raw=b'(board (pad same) (pad same))'):
        spans=locate(raw);objects=[{'id':s.identity,'native_id':'same' if s.head=='pad' else 'board','parent_id':next((p.identity for p in spans if p.start==s.parent_start),None),'source_span':[s.start,s.end],'coverage':'UNSUPPORTED: test semantics'} for s in spans]
        pads=[r for r in objects if r['native_id']=='same']
        relations=[{'occurrence':str(i),'source':pads[0]['id'],'target':pads[-1]['id'],'type':'physical_contact','witness':i} for i in range(2)]
        return raw,objects,relations
    def put(self,raw=b'(board (pad same) (pad same))',**kw):
        raw,objects,relations=self.fixture(raw)
        return self.store.import_revision(raw,objects,relations,{'units':'mm','predicate':'test-only'},**kw),objects
    def test_exact_source_reopen_idempotent_and_stable_results(self):
        revision,objects=self.put(publish_as='case')
        first=self.store.query(revision)
        self.assertEqual(self.put(publish_as='case')[0],revision)
        self.store.close();self.store=RevisionCatalog(self.root)
        second=self.store.query(revision)
        self.assertEqual(first['result_sha256'],second['result_sha256'])
        self.assertEqual(self.store.published('case'),revision)
        record,payload=self.store.source_record(revision,objects[1]['id'])
        self.assertEqual(payload,b'(pad same)')
    def test_same_uuid_other_revision_and_repeated_native_reference(self):
        one,objects=self.put();two,other=self.put(b'(board (pad same) (pad same) (text changed))')
        self.assertNotEqual(one,two)
        self.assertEqual(self.store.query(two,ids=[objects[1]['id']])['records'],[])
        with self.assertRaisesRegex(CatalogError,'AMBIGUOUS_NATIVE_REFERENCE'):self.store.select(one,native_ids=['same'])
        self.assertNotEqual(objects[1]['id'],objects[2]['id'])
    def test_failed_import_retains_previous_publication(self):
        previous,_=self.put(publish_as='case')
        with self.assertRaisesRegex(CatalogError,'INJECTED_PARTIAL_IMPORT_FAILURE'):
            self.put(b'(board (pad same) (pad same) (text changed))',publish_as='case',fail_after=1)
        self.assertEqual(self.store.published('case'),previous)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0],1)
    def test_foreign_keys_every_reopen_and_invalid_relation_rollback(self):
        raw,objects,relations=self.fixture();relations[0]['target']='absent'
        with self.assertRaisesRegex(CatalogError,'CATALOG_WRITE_ERROR'):self.store.import_revision(raw,objects,relations,{},publish_as='case')
        self.assertEqual(self.store.db.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0],0)
    def test_duplicate_evidence_occurrences_survive(self):
        revision,_=self.put();r=self.store.query(revision,relation_type='physical_contact')
        self.assertEqual(len(r['records']),2);self.assertTrue(r['complete'])
    def test_empty_explicit_all_dedup_and_protected_context(self):
        revision,objects=self.put();a=objects[1]['id'];b=objects[2]['id']
        self.assertEqual(self.store.select(revision)['records'],[])
        self.assertEqual(len(self.store.select(revision,all_objects=True)['records']),3)
        selected=self.store.select(revision,object_ids=[a,a],context_ids=[a,b],writable_ids=[a])
        self.assertEqual(len(selected['records']),3);self.assertEqual(selected['dependency_ids'],[objects[0]['id']]);self.assertEqual(selected['context_ids'],[b]);self.assertEqual(selected['writable_ids'],[a])
        with self.assertRaisesRegex(CatalogError,'POLICY_WRITE_OUTSIDE_SELECTION'):self.store.select(revision,object_ids=[a],context_ids=[b],writable_ids=[b])
        with self.assertRaisesRegex(CatalogError,'MISSING_OBJECT_REFERENCE'):self.store.select(revision,object_ids=['missing'])
        with self.assertRaisesRegex(CatalogError,'MISSING_NATIVE_REFERENCE'):self.store.select(revision,native_ids=['missing'])
    def test_budget_cancel_stale_missing_and_query_error_distinct(self):
        revision,_=self.put()
        self.assertEqual(self.store.query(revision,limit=1)['status'],'TRUNCATED')
        self.assertEqual(self.store.query(revision,cancel=lambda:True)['status'],'CANCELLED')
        self.assertEqual(self.store.query(revision,ids=[])['status'],'COMPLETE')
        with self.assertRaisesRegex(CatalogError,'STALE_MIXED_SNAPSHOT'):self.store.query(revision,expected_snapshot='wrong')
        with self.assertRaisesRegex(CatalogError,'REVISION_UNAVAILABLE'):self.store.query('missing')
        with self.assertRaisesRegex(CatalogError,'INVALID_QUERY_LIMIT'):self.store.query(revision,limit=-1)
    def test_payload_and_catalog_corruption_rejected(self):
        revision,objects=self.put();source=self.store.snapshot(revision)['source_sha256']
        path=self.store.payloads/source;original=path.read_bytes();path.write_bytes(b'changed')
        with self.assertRaisesRegex(CatalogError,'PAYLOAD_HASH_MISMATCH'):self.store.query(revision)
        path.write_bytes(original)
        with self.store.db:self.store.db.execute('UPDATE objects SET record_json=? WHERE revision=? AND object_id=?',('{}',revision,objects[1]['id']))
        with self.assertRaisesRegex(CatalogError,'CATALOG_MANIFEST_MISMATCH'):self.store.query(revision)

    def test_payload_size_boundary_on_write_and_read(self):
        from unittest.mock import patch
        self.assertEqual(RevisionCatalog.MAX_PAYLOAD_BYTES,128*1024*1024)
        with patch.object(self.store,'MAX_PAYLOAD_BYTES',8):
            key=self.store.put_payload(b'12345678')
            self.assertEqual(self.store.read_payload(key),b'12345678')
            with self.assertRaisesRegex(CatalogError,'PAYLOAD_BUDGET_EXCEEDED'):
                self.store.put_payload(b'123456789')
            oversized=self.store.payloads/('0'*64);oversized.write_bytes(b'123456789')
            with self.assertRaisesRegex(CatalogError,'PAYLOAD_BUDGET_EXCEEDED'):
                self.store.read_payload('0'*64)

    def test_storage_read_failure_is_typed_error(self):
        revision,_=self.put()
        self.store.db.execute('DROP TABLE relations')
        with self.assertRaisesRegex(CatalogError,'CATALOG_READ_ERROR'):self.store.query(revision)
