from tests.local_scratch import temporary_directory
"""Display projection retains persisted identities and bound source excerpts."""
import json
from pathlib import Path
import tempfile
import unittest
from src.native_inventory import inventory
from src.pipeline_scene import add_pipeline
from src.revision_catalog import canonical,digest
from src.visual_scene import UnverifiedEvidence

class PipelineSceneTests(unittest.TestCase):
    def fixture(self,root):
        p=root/'pipeline';(p/'catalog/payloads').mkdir(parents=True)
        raw=b'(kicad_pcb\r\n (layers (0 "F.Cu" signal)) (segment (start 0 0) (end 1 0) (width .2) (layer "F.Cu") (uuid repeated)))'
        inv=inventory(raw);payloads={**inv.pop('payloads'),digest(raw):raw}
        for key,data in payloads.items():(p/'catalog/payloads'/key).write_bytes(data)
        records=inv['objects'];data={'inventory':inv,'source_sha256':digest(raw),'catalog_revision':'revision-fixture','topology':{'components':[],'queries':[]},'stages':[{'stage':'inventory','state':'COMPLETE','counts':{'source_objects':1}}],'selection':None}
        (p/'source.json').write_bytes(canonical(data))
        outputs={str(f.relative_to(p)):digest(f.read_bytes()) for f in p.rglob('*') if f.is_file()}
        (p/'receipt.json').write_bytes(canonical({'datasets':[{'label':'fixture','file':'source.json'}],'outputs':outputs}))
        out=root/'bundle';(out/'evidence').mkdir(parents=True)
        return p,out,raw,records
    def test_exact_source_occurrence_and_geometry_binding(self):
        with temporary_directory() as d:
            p,out,raw,records=self.fixture(Path(d));scene={'provenance':[]};add_pipeline(scene,p,out)
            ds=scene['pipeline']['datasets'][0]
            self.assertEqual(ds['objects'],records);self.assertEqual(ds['source_utf8'].encode(),raw)
            self.assertEqual(ds['catalog_revision'],'revision-fixture')
            self.assertIn(records[0]['geometry_sha256'],ds['geometry_paths'])
            self.assertEqual((out/ds['source_evidence']['snapshot']).read_bytes(),raw)
    def test_tampered_payload_rejected_instead_of_rendering(self):
        with temporary_directory() as d:
            p,out,raw,records=self.fixture(Path(d));key=records[0]['geometry_sha256'];(p/'catalog/payloads'/key).write_bytes(b'changed')
            with self.assertRaises(UnverifiedEvidence):add_pipeline({'provenance':[]},p,out)
