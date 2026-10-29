import math,unittest
from src.parallel_curve_relations import parallel_curve_relation


def arc(radius):return [(radius*math.cos(i*math.pi/200),radius*math.sin(i*math.pi/200)) for i in range(101)]


class ParallelCurveRelationTests(unittest.TestCase):
    def test_concentric_curves_have_local_parallel_membership(self):
        r=parallel_curve_relation(arc(1),arc(1.1),min_shared_run_mm=.1)
        self.assertIsNotNone(r);self.assertGreater(r['shared_sampled_run_mm'],1.)

    def test_opposite_parameterization_is_equivalent(self):
        a=parallel_curve_relation(arc(1),arc(1.1))
        b=parallel_curve_relation(list(reversed(arc(1))),arc(1.1))
        self.assertIsNotNone(b);self.assertAlmostEqual(a['shared_sampled_run_mm'],b['shared_sampled_run_mm'])

    def test_short_parallel_links_are_not_excluded_by_old_quarter_mm_threshold(self):
        r=parallel_curve_relation([(0,0),(.12,0)],[(0,.1),(.12,.1)],min_shared_run_mm=.05)
        self.assertIsNotNone(r)

    def test_crossing_curves_not_bundle(self):
        self.assertIsNone(parallel_curve_relation([(0,0),(1,1)],[(0,1),(1,0)]))

    def test_endpoint_only_proximity_does_not_establish_shared_run(self):
        self.assertIsNone(parallel_curve_relation([(0,0),(.1,0)],[(.2,.1),(.3,.1)],min_shared_run_mm=.05))

    def test_diverging_directions_rejected(self):
        self.assertIsNone(parallel_curve_relation([(0,0),(1,0)],[(0,.1),(1,.2)]))

    def test_remote_original_junction_does_not_hide_local_parallel_run(self):
        a=[(0,0),(2,0),(3,1)]
        b=[(0,.1),(2,.1),(3,1)]
        self.assertIsNone(parallel_curve_relation(a,b))
        self.assertIsNotNone(parallel_curve_relation(a,b,allow_remote_intersections=True,samples=201))


if __name__=='__main__':unittest.main()
