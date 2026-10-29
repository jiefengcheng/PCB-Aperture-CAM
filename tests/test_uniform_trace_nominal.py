import unittest
from shapely import to_wkb
from src.uniform_trace_nominal import construct_nominal_width
from tests.test_uniform_trace_width import fixture


class NominalWidthTests(unittest.TestCase):
    def line(self):return fixture(['(segment (start 0 0) (end 2 0) (width 0.1) (layer F.Cu) (net 0))'])

    def test_nominal_ceiling_has_no_added_verification_margin(self):
        r,_,_,_,nominal,envelope=construct_nominal_width(*self.line(),1.5)
        self.assertAlmostEqual(nominal.bounds[3],.075,places=12)
        self.assertGreater(envelope.bounds[3],nominal.bounds[3])
        self.assertEqual(r['uniform_nominal_width_mm'],.1*1.5)

    def test_original_factor_preserves_exact_bytes(self):
        args=self.line();_,parts,_,_,_,_=construct_nominal_width(*args,1.)
        for sid,g in parts.items():self.assertEqual(to_wkb(g),args[3][sid])

    def test_small_positive_arc_growth_retains_core_and_is_contained(self):
        args=fixture(['(arc (start 1 0) (mid 0.707106781 0.707106781) (end 0 1) (width 0.1) (layer F.Cu) (net 0))'])
        for factor in [1.000001,1.01,1.5]:
            _,_,_,core,nominal,envelope=construct_nominal_width(*args,factor)
            self.assertTrue(nominal.covers(core));self.assertTrue(envelope.covers(nominal))

    def test_all_native_members_have_the_same_width_factor(self):
        args=fixture(['(segment (start 0 0) (end 1 0) (width 0.1) (layer F.Cu) (net 0))','(segment (start 1 0) (end 1 1) (width 0.1) (layer F.Cu) (net 0))'])
        r,_,_,_,_,_=construct_nominal_width(*args,1.25)
        self.assertTrue(all(p['nominal_candidate_width_mm']==.125 for p in r['primitives']))

    def test_exceeding_hard_ceiling_rejected(self):
        with self.assertRaises(ValueError):construct_nominal_width(*self.line(),1.500001)


if __name__=='__main__':unittest.main()
