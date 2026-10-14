"""Tests only source custody, baseline coordinates and known before export syntax."""
import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import preflight

class BootstrapCase(unittest.TestCase):
    def test_integrity(self):
        self.assertGreater(preflight.verify_manifest(),15)
    def test_generated_candidate_coordinates(self):
        ps=preflight.positions()
        self.assertEqual(ps['candidate']['pad_x_mm'],20.05)
        self.assertEqual(ps['before']['pad_x_mm'],20.35)
    def test_observed_before_export_syntax(self):
        d=preflight.observed_baseline_smoke()
        self.assertEqual(d['mask_regions'],4)
    def test_v1_not_claimed(self):
        r=preflight.preflight()
        self.assertEqual(r['status'],'PASS_BOOTSTRAP_ONLY')
        self.assertEqual(r['native_candidate_export'],'NOT_RUN')
        self.assertEqual(r['v1_independent_gerber_validation'],'NOT_RUN')

if __name__=='__main__':unittest.main()
