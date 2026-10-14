from pathlib import Path
import json, unittest
from src.validator import ROOT, evaluate, layers, equivalent
from src.falsification import falsify
from tools.preflight import verify_manifest

class NativeValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        verify_manifest()
        pointer=ROOT/'out/current_native.txt'
        if not pointer.exists(): raise AssertionError('Run tools/validate_native.py --run EXPORT_DIRECTORY first; native evidence is required')
        cls.export_run=Path(pointer.read_text().strip())
        cls.before=cls.export_run/'before/gerbers'; cls.candidate=cls.export_run/'candidate/gerbers'

    def test_native_positive_and_measured_exposure(self):
        r=evaluate(self.before,self.candidate)
        self.assertEqual(r['overall'],'PASS',r)
        exposure=next(c['actual'] for c in r['checks'] if c['id']=='exposure')
        self.assertAlmostEqual(exposure['before_exposed_mm2'],1.19,places=6)
        self.assertAlmostEqual(exposure['candidate_exposed_mm2'],1.4,places=6)
        parsed=layers(self.candidate)
        self.assertAlmostEqual(parsed['F_Cu']['pads']['P1'][0],20.05)

    def test_native_negative_controls(self):
        cases=falsify(self.before,self.candidate,ROOT/'out/test_negatives')
        self.assertGreaterEqual(len(cases),6)
        for row in cases:
            with self.subTest(case=row['name']): self.assertEqual(row['status'],'PASS',row)

    def test_observed_before_geometry(self):
        fresh=layers(self.before); observed=layers(ROOT/'assets/observed_before')
        for key in fresh:
            with self.subTest(layer=key): self.assertTrue(equivalent(fresh[key]['geometry'],observed[key]['geometry']))

    def test_report_schema(self):
        from jsonschema import validate
        validate(json.loads((ROOT/'out/v1_validation.json').read_text()),json.loads((ROOT/'contracts/report.schema.json').read_text()))
