import unittest
from shapely import to_wkb,reverse
from shapely.affinity import translate
from shapely.geometry import box,Polygon
from tools.capture_c02_native_binding_mismatch import compare


class NativeMismatchCaptureTests(unittest.TestCase):
    def test_exact_operand_identity(self):
        b=to_wkb(box(0,0,1,1));r=compare(b,b)
        self.assertTrue(r['byte_identical'])
        self.assertEqual(r['coordinate_differences'],[])
        self.assertEqual(r['hausdorff_distance_mm'],0.)

    def test_ring_order_is_reported_without_normalizing_source(self):
        p=box(0,0,1,1);r=compare(to_wkb(p),to_wkb(reverse(p)))
        self.assertFalse(r['byte_identical'])
        self.assertTrue(r['topological_equals'])
        self.assertEqual(r['symmetric_difference_area_mm2'],0.)
        self.assertTrue(r['coordinate_differences'])

    def test_tiny_coordinate_change_is_not_tolerated_away(self):
        p=box(0,0,1,1);r=compare(to_wkb(p),to_wkb(translate(p,1e-13,0)))
        self.assertFalse(r['byte_identical'])
        self.assertGreater(r['hausdorff_distance_mm'],0.)
        self.assertTrue(r['coordinate_differences'])
        self.assertIn('NONE',r['numerical_tolerance_applied'])

    def test_coordinate_count_mismatch_cannot_be_truncated(self):
        r=compare(to_wkb(box(0,0,1,1)),to_wkb(Polygon([(0,0),(1,0),(0,1)])))
        self.assertFalse(r['byte_identical'])
        self.assertNotEqual(r['cached_coordinate_count'],r['reconstructed_coordinate_count'])
        self.assertIsNone(r['coordinate_differences'])
        self.assertEqual(len(r['cached_coordinates_mm']),r['cached_coordinate_count'])
        self.assertEqual(len(r['reconstructed_coordinates_mm']),r['reconstructed_coordinate_count'])


if __name__=='__main__':unittest.main()
