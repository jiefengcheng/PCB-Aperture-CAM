import unittest

from shapely.geometry import box
from shapely.ops import unary_union

from tools.run_g22_slice_c import (fidelity_gate, geometric_measure, gerber_roi_for_native,
                                   scalar_file_attribute, topology_change, append_gerber_rectangle_fault)


class G22SliceCTests(unittest.TestCase):
    def test_original_coordinates_map_gerber_y_back_to_native_without_fitting(self):
        native = box(2.0, -12.0, 3.0, -11.0)
        self.assertEqual(scalar_file_attribute(("Original",)), "Original")
        self.assertEqual(gerber_roi_for_native(native, "Original").bounds, (2.0, 11.0, 3.0, 12.0))
        self.assertEqual(gerber_roi_for_native(native, "None").bounds, native.bounds)

    def test_fidelity_gate_fails_closed_on_incomplete_source_and_enforces_error_bound(self):
        roi = box(0, 0, 1, 1)
        same = geometric_measure(roi, roi)
        self.assertEqual(fidelity_gate({"coverage": "COMPLETE_FOR_WINDOW"}, same, 0.00002)["status"], "PASS")
        shifted = geometric_measure(roi, box(0.001, 0, 1.001, 1))
        self.assertEqual(fidelity_gate({"coverage": "COMPLETE_FOR_WINDOW"}, shifted, 0.00002)["status"], "FAIL")
        self.assertEqual(fidelity_gate({"coverage": "INCOMPLETE"}, same, 0.00002)["status"], "NOT_ESTABLISHED")

    def test_neighbor_interaction_detects_bridge_and_possible_fragmentation(self):
        roi = box(0, 0, 5, 5)
        org = unary_union([box(1, 1, 2, 2), box(3, 1, 4, 2)])
        bridged = unary_union([org, box(1.9, 1.4, 3.1, 1.6)])
        self.assertEqual(topology_change(org, bridged, roi)["status"], "FAIL_NEW_GEOMETRIC_CONTACT")
        intact = box(1, 1, 4, 2)
        split = unary_union([box(1, 1, 2.4, 2), box(2.6, 1, 4, 2)])
        self.assertEqual(topology_change(intact, split, roi)["status"], "FAIL_POSSIBLE_LOCAL_FRAGMENTATION")

    def test_out_of_scope_fault_control_is_additive_and_preserves_eof(self):
        original = b"%FSLAX46Y46*%\n%MOMM*%\nM02*\n"
        faulted = append_gerber_rectangle_fault(original)
        self.assertEqual(original.count(b"M02*"), 1)
        self.assertEqual(faulted.count(b"M02*"), 1)
        self.assertNotEqual(faulted, original)
        self.assertIn(b"X1000000000Y1000000000D02*", faulted)


if __name__ == "__main__":
    unittest.main()
