import unittest

from shapely.geometry import Point, Polygon

from tools.qualify_collinear_arc_coupon import (independent_centerline,
    polygon_topology, stroke, within_accuracy_policy)
from tools.build_collinear_arc_coupon import stable_uuid


class CollinearArcCouponTests(unittest.TestCase):
    def test_circular_centerline_passes_through_start_mid_and_end(self):
        arc = {'start': [1.0, 0.0], 'mid': [0.0, 1.0], 'end': [-1.0, 0.0], 'width': 0.2}
        line = independent_centerline(arc)
        self.assertLess(line.distance(Point(*arc['mid'])), 1e-12)
        self.assertAlmostEqual(line.length, 3.141592653589793, places=4)
        self.assertGreater(line.bounds[3], 0.99)

    def test_collinear_points_do_not_define_a_unique_circle(self):
        arc = {'start': [0.0, 0.0], 'mid': [1.0, 0.0], 'end': [2.0, 0.0], 'width': 0.2}
        with self.assertRaises(ValueError):
            independent_centerline(arc)
        shape = stroke(arc)
        self.assertGreater(shape.area, 0)
        self.assertAlmostEqual(shape.bounds[0], -0.1, places=6)
        self.assertAlmostEqual(shape.bounds[2], 2.1, places=6)

    def test_topology_counts_components_and_holes(self):
        polygon = Polygon([(0, 0), (4, 0), (4, 4), (0, 4)],
                          holes=[[(1, 1), (3, 1), (3, 3), (1, 3)]])
        self.assertEqual(polygon_topology(polygon),
                         {'components': 1, 'holes': 1, 'empty': False})

    def test_coupon_object_uuids_are_stable_and_distinct(self):
        first = stable_uuid('test-object')
        self.assertEqual(first, stable_uuid('test-object'))
        self.assertNotEqual(first, stable_uuid('another-object'))

    def test_relative_area_guard_rejects_small_shapes_that_only_pass_absolute_limit(self):
        acceptance={'maximum_symmetric_difference_area_mm2': 0.0001,
                    'maximum_boundary_hausdorff_distance_mm': 0.00002,
                    'maximum_relative_symmetric_difference_fraction': 0.01}
        measurement={'symmetric_difference_area_mm2': 0.00002,
                     'boundary_hausdorff_distance_mm': 0.00001,
                     'symmetric_difference_fraction_of_expected': 0.02}
        self.assertFalse(within_accuracy_policy(measurement, acceptance))
        measurement['symmetric_difference_fraction_of_expected']=0.005
        self.assertTrue(within_accuracy_policy(measurement, acceptance))


if __name__ == '__main__':
    unittest.main()
