from pathlib import Path
import hashlib,json,re,tempfile,unittest
from src.visual_scene import bound,UnverifiedEvidence,svg_path,ROOT
from tools.visual_report import embed_scene
from shapely.geometry import box

class VisualScene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=Path((ROOT/'out/visual/current.txt').read_text().strip());cls.scene=json.loads((cls.bundle/'scene.json').read_text())
        cls.cases={c['id']:c for c in cls.scene['cases']}
    def test_actual_synthetic_values_and_state(self):
        c=self.cases['synthetic'];s=next(x for x in c['states'] if x['id']=='computed')
        self.assertEqual(s['metrics']['P1_center_mm'],[20.05,20.0]);self.assertEqual(s['candidate_verdict'],'PASS')
        self.assertAlmostEqual(s['metrics']['candidate_exposed_mm2'],1.4)
        self.assertEqual(next(o for o in s['objects'] if o['id']=='P1')['center'],[20.05,20.0])
    def test_hal_open_has_complete_expected_list_and_preserved_pad(self):
        c=self.cases['halpi2'];s=next(x for x in c['states'] if x['id']=='open');id=c['focus_object']
        self.assertEqual(len(s['objects']),64);self.assertEqual(len(s['pairs']),240)
        self.assertEqual(len([p for p in s['pairs'] if id in (p['a'],p['b']) and p['status']=='FAIL']),15)
        self.assertEqual(s['candidate_verdict'],'FAIL');self.assertEqual(s['control_test']['status'],'PASS')
    def test_glow_unknowns_are_separate(self):
        c=self.cases['glowstitch'];s=c['states'][0]
        self.assertEqual(c['electrical'],'NOT_ESTABLISHED');self.assertEqual(c['aggregate'],'NOT_ESTABLISHED');self.assertEqual(c['source_aware'],'PASS')
        self.assertEqual(s['candidate_verdict'],'PASS');self.assertTrue(all(o['net'] is None for o in s['objects']))
        self.assertEqual(len({o['id'] for o in s['objects']}),80);self.assertFalse(s['pairs'])
    def test_all_source_and_snapshot_bindings(self):
        for p in self.scene['provenance']:
            self.assertEqual(hashlib.sha256((ROOT/p['path']).read_bytes()).hexdigest(),p['sha256'])
            self.assertEqual(hashlib.sha256((self.bundle/p['snapshot']).read_bytes()).hexdigest(),p['sha256'])
    def test_finding_localization_missing_segment_and_fixed_aperture(self):
        c=self.cases['synthetic'];s=next(x for x in c['states'] if x['id']=='disconnected_n1');f=next(x for x in s['checks'] if x['id']=='connectivity')
        self.assertEqual(f['status'],'FAIL');self.assertTrue(f['focus']);self.assertEqual(len(f['objects']),3)
        expected=next(o for o in s['objects'] if o['id']==f['objects'][-1]);self.assertIn('expected segment annotation',expected['basis'])
        self.assertTrue(self.scene['geometry'][s['delta']['F.Cu']['removed']]['path'])
        f=next(x for x in next(s for s in c['states'] if s['id']=='shifted_aperture')['checks'] if x['id']=='fixed_reference')
        self.assertEqual(f['objects'],['A1']);self.assertEqual(f['status'],'FAIL')
    def test_mismatched_or_missing_input_never_verified(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'out/visual') as tmp:
            p=Path(tmp)/'artifact';p.write_text('changed')
            with self.assertRaises(UnverifiedEvidence):bound(p,'0'*64)
            with self.assertRaises(UnverifiedEvidence):bound(Path(tmp)/'missing','0'*64)
    def test_safe_script_embedding_and_constrained_svg(self):
        value={'label':'</script><script>alert(1)</script>&'};raw=embed_scene(value)
        self.assertNotIn('</script>',raw);self.assertEqual(json.loads(raw),value)
        p=svg_path(box(0,0,1,1));self.assertRegex(p,r'^M[-\d. LZ]+$');self.assertNotIn('<',p)
    def test_scene_checksum_and_replay_events(self):
        page=(self.bundle/'index.html').read_text();raw=(self.bundle/'scene.json').read_bytes()
        checksum=re.search('name="scene-sha256" content="([a-f0-9]+)"',page)[1]
        self.assertEqual(checksum,hashlib.sha256(raw).hexdigest())
        events=next(s for s in self.cases['synthetic']['states'] if s['id']=='computed')['replay']
        self.assertEqual(events,['PLANNED','STAGED','EXPORTED','VALIDATED','COMMITTED (recorded outcome)'])
