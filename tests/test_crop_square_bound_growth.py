import math
import unittest
from shapely.geometry import Point,LineString
from src.crop_square_bound_growth import square_bound_radius,outward_halfplane
from src.crop_square_neighbor_experiment import Settings,construct,verify_addition


class EarlierSquareBoundTests(unittest.TestCase):
    def test_earlier_square_bounds_later_envelope_and_updates_with_round_radius(self):
        for ra in [.2,.25]:
            value=square_bound_radius((0,0),ra,(.4,.4),.020)
            self.assertAlmostEqual(value['radius_mm'],math.sqrt(.32)-ra/math.sqrt(2)-.020-.00002)
            self.assertEqual(value['square_owner'],'earlier round A')
            self.assertGreater(Point(.4,.4).buffer(value['radius_mm'],quad_segs=128).distance(LineString(value['side']['vertices'])),.020)
            self.assertGreater(ra+value['radius_mm'],math.sqrt(.32))

    def test_stopping_final_copper_at_inner_square_is_unsafe(self):
        a=Point(0,0).buffer(.25,quad_segs=128)
        v=square_bound_radius((0,0),.25,(.4,.4),.020)
        envelope=Point(.4,.4).buffer(v['radius_mm'],quad_segs=128)
        bad=envelope.intersection(outward_halfplane(v['side'],.020))
        self.assertGreater(bad.intersection(a).area,1e-6)

    def test_actual_copper_recession_allows_overlapping_envelopes_without_collision(self):
        a=Point(0,0).buffer(.25,quad_segs=128)
        b=Point(.4,.4).buffer(.1,quad_segs=128)
        v=square_bound_radius((0,0),.25,(.4,.4),.02002)
        obs=[{'source_id':'A','geometry':a}]
        st=Settings(construction_gap_mm=.02002,hard_gap_mm=.020,orientation_degrees=-45)
        result=construct(b,(.4,.4),v['radius_mm'],obs,square_enabled=False,settings=st)
        self.assertGreater(result['envelope'].intersection(a).area,0)
        self.assertEqual(result['candidate'].intersection(a).area,0)
        self.assertGreaterEqual(result['candidate'].distance(a),.020)
        self.assertTrue(verify_addition(b,result['candidate'],result['envelope'],obs,settings=st)['passed'])

    def test_invalid_bounds_fail_closed(self):
        for radius,gap in [(float('nan'),.020),(-1,.020),(.2,-.020)]:
            with self.assertRaises(ValueError): square_bound_radius((0,0),radius,(.4,.4),gap)


if __name__=='__main__': unittest.main()
