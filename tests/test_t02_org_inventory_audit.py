import unittest

from tools.audit_crop_t02_org_inventory import native_filled_rectangle


class NativeRectangleAuditTests(unittest.TestCase):
    def test_exact_native_rectangle_is_eligible(self):
        raw = b"""(gr_poly (pts (xy 0 0) (xy 2 0) (xy 2 1) (xy 0 1))
          (fill yes) (layer F.Cu))"""
        self.assertEqual(native_filled_rectangle(raw, [0, len(raw)])['size_mm'], [2.0, 1.0])

    def test_perturbed_vertex_is_rejected(self):
        raw = b"""(gr_poly (pts (xy 0 0) (xy 2 0) (xy 2 1) (xy 0 1.01))
          (fill yes) (layer F.Cu))"""
        self.assertIsNone(native_filled_rectangle(raw, [0, len(raw)]))

    def test_unfilled_or_wrong_layer_polygon_is_rejected(self):
        unfilled = b"(gr_poly (pts (xy 0 0) (xy 2 0) (xy 2 1) (xy 0 1)) (fill no) (layer F.Cu))"
        wrong_layer = b"(gr_poly (pts (xy 0 0) (xy 2 0) (xy 2 1) (xy 0 1)) (fill yes) (layer B.Cu))"
        self.assertIsNone(native_filled_rectangle(unfilled, [0, len(unfilled)]))
        self.assertIsNone(native_filled_rectangle(wrong_layer, [0, len(wrong_layer)]))


if __name__ == "__main__":
    unittest.main()
