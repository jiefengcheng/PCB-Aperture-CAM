from pathlib import Path
import json
import os
import unittest
from tests.local_scratch import temporary_directory
from src.native_graph_adapter import NativeGraphAdapter
from src.pipeline_scene import add_native_comparisons
from src.revision_catalog import canonical,digest
from src.visual_scene import UnverifiedEvidence

BINARY=Path(os.environ.get('PCB_CAM_NATIVE_SHADOW_BINARY','out/consolidation/native/pcb_graph_shadow'))
@unittest.skipUnless(BINARY.is_file(),'Native process unavailable; no native PASS')
class NativeComparisonSceneTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'source.json';source.write_text('{"declared":"unit relation snapshot"}')
        folder=root/'native';folder.mkdir();adapter=NativeGraphAdapter(BINARY)
        relations=[{'occurrence':'proof','source':'a','target':'b','type':'physical_contact','witness':{'layer':'F.Cu'}}]
        build=adapter.materialize(folder/'materialization','revision','physical_contact',relations,layer='F.Cu')
        samples={d:adapter.query(folder/'materialization','revision',['a','b'],direction=d,expected_layer='F.Cu') for d in ['out','in']}
        self.assertEqual({(r['source'],r['target']) for r in samples['out']['records']},{('a','b')})
        report={'status':'PARITY_PASS','source_snapshot':'revision','source_pipeline_sha256':digest(source.read_bytes()),'layer_scope':'F.Cu','native_build':build,'binary_sha256':adapter.binary_hash,'actual_query_samples':samples,'identity_count':2,'samples':[],'limitations':['Unit relation fixture, not PCB acceptance.']}
        path=folder/'result.json';path.write_bytes(canonical(report));manifest=root/'comparisons.json';manifest.write_bytes(canonical({'comparisons':[{'dataset':'unit','layer':'F.Cu','path':str(path),'sha256':digest(path.read_bytes())}]}))
        scene={'provenance':[],'pipeline':{'datasets':[{'label':'unit','catalog_revision':'revision','evidence':{'sha256':digest(source.read_bytes())},'objects':[{'id':'a'},{'id':'b'}]}]}}
        out=root/'visual';(out/'evidence').mkdir(parents=True)
        return scene,manifest,out,path
    def test_real_native_queries_bound_into_scene(self):
        with temporary_directory() as d:
            scene,manifest,out,path=self.fixture(Path(d));add_native_comparisons(scene,manifest,out)
            comparison=scene['pipeline']['datasets'][0]['native_comparisons'][0]
            self.assertEqual(comparison['materialized_ids'],['a','b']);self.assertEqual(comparison['backend_decision'],'SHADOW_ONLY')
            self.assertEqual(comparison['query_samples']['out']['query']['seeds'],['a','b'])
            self.assertEqual((out/comparison['evidence']['snapshot']).read_bytes(),path.read_bytes())
    def test_stale_revision_rejected(self):
        with temporary_directory() as d:
            scene,manifest,out,path=self.fixture(Path(d));scene['pipeline']['datasets'][0]['catalog_revision']='different'
            with self.assertRaisesRegex(UnverifiedEvidence,'stale native'):add_native_comparisons(scene,manifest,out)
    def test_changed_materialization_rejected(self):
        with temporary_directory() as d:
            scene,manifest,out,path=self.fixture(Path(d));(path.parent/'materialization/identities.json').write_text('{}')
            with self.assertRaises(UnverifiedEvidence):add_native_comparisons(scene,manifest,out)
