import unittest
from shapely.geometry import box,Point
from src.joint_rectangle_growth import fit_joint_rectangle

class JointRectangleGrowthControls(unittest.TestCase):
    def test_neighbor_limit_applies_to_entire_rectangle(self):
        core=box(0,0,1,1)
        candidate,(sx,sy)=fit_joint_rectangle(core,lambda g:g.bounds[2]<=1.05)
        self.assertAlmostEqual(sx,1.1,places=9)
        self.assertEqual(sy,1.25)
        self.assertTrue(candidate.covers(core))
        self.assertEqual(len(candidate.exterior.coords),5)

    def test_joint_circle_constraint_can_limit_otherwise_clear_rectangle(self):
        core=box(0,0,1,1);circle=Point(1.2,1.2).buffer(.12)
        g,f=fit_joint_rectangle(core,lambda g:g.distance(circle)>=.1)
        self.assertGreater(g.area,core.area)
        self.assertGreaterEqual(g.distance(circle),.1)
        self.assertLess(g.area,1.25**2)

    def test_no_growth_keeps_exact_source_wkb(self):
        core=box(0,0,1,1)
        g,f=fit_joint_rectangle(core,lambda g:g.equals(core))
        self.assertEqual(g.wkb,core.wkb);self.assertEqual(f,(1.,1.))

    def test_invalid_baseline_or_unbounded_request_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'INVALID_KEEP_PREDECESSOR'):fit_joint_rectangle(box(0,0,1,1),lambda g:False)
        with self.assertRaisesRegex(ValueError,'BOUNDED_AXIS'):fit_joint_rectangle(box(0,0,1,1),lambda g:True,max_factor=1.5)
        with self.assertRaisesRegex(ValueError,'BOUNDED_AXIS'):fit_joint_rectangle(Point(0,0).buffer(1),lambda g:True)
