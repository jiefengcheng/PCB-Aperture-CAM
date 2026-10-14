from tests.local_scratch import temporary_directory
import json
from pathlib import Path
import tempfile
import unittest
from src.revision_catalog import RevisionCatalog,canonical,digest,CatalogError
from src.source_locators import locate
from tools.catalog_v2_run import admit

class CatalogAdmissionTests(unittest.TestCase):
    def fixture(self,root,duplicate=False):
        source=b'(board (pad a) (pad b) (pad c) (pad d) (pad e) (pad f))';spans=locate(source);pads=spans[1:]
        objects=[{'id':s.identity,'native_id':('a' if duplicate and i==1 else chr(97+i)),'source_span':[s.start,s.end]} for i,s in enumerate(pads)]
        relations=[{'occurrence':str(i),'source':pads[i].identity,'target':pads[i+1].identity,'type':'physical_contact'} for i in range(5)]
        with RevisionCatalog(root/'catalog') as catalog:
            revision=catalog.import_revision(source,objects,relations,{},publish_as='synthetic_before')
            writable=[s.identity for s in pads[:4]];selection=catalog.select(revision,object_ids=writable,context_ids=[s.identity for s in pads],writable_ids=writable)
            selection['component']={'members':[s.identity for s in pads]}
        record={'catalog_revision':revision,'selection':selection}
        (root/'before.json').write_bytes(canonical(record));(root/'receipt.json').write_bytes(canonical({'datasets':[{'label':'synthetic_before','file':'before.json'}],'outputs':{'before.json':digest((root/'before.json').read_bytes())}}))
        return {'source_sha256':digest(source),'target':'a','dependents':['b','c','d']},source
    def test_reopened_source_and_protected_context_admitted(self):
        with temporary_directory() as d:
            p=Path(d);contract,source=self.fixture(p);actual,receipt=admit(p,contract)
            self.assertEqual(actual,source);self.assertEqual(receipt['admission'],'PASS');self.assertEqual(len(receipt['selection']['context_ids']),2)
    def test_duplicate_native_identity_rejected(self):
        with temporary_directory() as d:
            p=Path(d);contract,_=self.fixture(p,duplicate=True)
            with self.assertRaisesRegex(CatalogError,'AMBIGUOUS_OPERATION_REFERENCE'):admit(p,contract)
    def test_pipeline_tampering_and_wrong_source_rejected(self):
        with temporary_directory() as d:
            p=Path(d);contract,_=self.fixture(p)
            with self.assertRaisesRegex(CatalogError,'EXECUTOR_SOURCE_REVISION_MISMATCH'):admit(p,{**contract,'source_sha256':'wrong'})
            (p/'before.json').write_text('{}')
            with self.assertRaisesRegex(CatalogError,'PIPELINE_RECORD_HASH_MISMATCH'):admit(p,contract)
