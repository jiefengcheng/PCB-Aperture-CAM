import unittest
from shapely import to_wkb
from src.source_offset_width import construct_source_offset_width
from tests.test_uniform_trace_width import fixture


class SourceOffsetTests(unittest.TestCase):
    def test_broad_arc_offset_remains_nested_past_its_curvature_radius(self):
        args=fixture(['(arc (start 0.25 0) (mid 0.176776695 0.176776695) (end 0 0.25) (width 1) (layer F.Cu) (net 0))'])
        previous=None
        for factor in [1.,1.000001,1.01,1.25,1.5]:
            r,_,_,core,nominal,envelope=construct_source_offset_width(*args,factor)
            self.assertTrue(nominal.covers(core));self.assertTrue(envelope.covers(nominal))
            if previous is not None:self.assertTrue(envelope.covers(previous))
            previous=envelope
            self.assertEqual(r['uniform_nominal_width_mm'],factor)

    def test_nominal_cap_is_separate_from_checking_margin(self):
        args=fixture(['(segment (start 0 0) (end 2 0) (width 0.1) (layer F.Cu) (net 0))'])
        _,_,_,_,nominal,envelope=construct_source_offset_width(*args,1.5)
        self.assertAlmostEqual(nominal.bounds[3],.075,places=12)
        self.assertGreater(envelope.bounds[3],nominal.bounds[3])
        _,parts,_,_,_,_=construct_source_offset_width(*args,1.)
        self.assertTrue(all(to_wkb(g)==args[3][sid] for sid,g in parts.items()))

    def test_invalid_scale_cannot_enter_offset_construction(self):
        args=fixture(['(segment (start 0 0) (end 2 0) (width 0.1) (layer F.Cu) (net 0))'])
        for factor in [float('nan'),float('inf'),True,0.9,1.50001]:
            with self.assertRaises(ValueError):construct_source_offset_width(*args,factor)


if __name__=='__main__':unittest.main()
