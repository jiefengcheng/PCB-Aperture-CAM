import unittest

from shapely.geometry import Point, box

from tools.audit_crop_t02_composition import assert_t01_round_classes


class T02CompositionAuditTests(unittest.TestCase):
    def test_unchanged_companion_must_remain_exact_source_round_core(self):
        core = Point(0, 0).buffer(1, quad_segs=128)
        site = {"source_id": "circle-a", "core": core, "center": (0, 0)}
        decision = {"source_id": "circle-a", "decision": "KEEP_CONSTRAINED"}
        result = assert_t01_round_classes([site], [decision], {"circle-a": core})
        self.assertEqual(result["nonround_growth_sites"], 0)

    def test_companion_nonround_protrusion_fails_even_when_core_is_preserved(self):
        core = Point(0, 0).buffer(1, quad_segs=128)
        candidate = core.union(box(0.8, -0.1, 1.2, 0.1))
        site = {"source_id": "circle-a", "core": core, "center": (0, 0)}
        decision = {"source_id": "circle-a", "decision": "KEEP_CONSTRAINED"}
        with self.assertRaisesRegex(ValueError, "T01_UNAUTHORIZED_SHAPE_CHANGE"):
            assert_t01_round_classes([site], [decision], {"circle-a": candidate})

    def test_priority_growth_must_equal_round_circle_envelope(self):
        core = Point(0, 0).buffer(1, quad_segs=128)
        candidate = Point(0, 0).buffer(1.25, quad_segs=128)
        site = {"source_id": "circle-a", "core": core, "center": (0, 0)}
        decision = {"source_id": "circle-a", "decision": "ROUND_GROW_PRIORITY",
                    "proposed_radius_mm": 1.25}
        result = assert_t01_round_classes([site], [decision], {"circle-a": candidate})
        self.assertEqual(result["round_priority_growth_sites"], ["circle-a"])


if __name__ == "__main__":
    unittest.main()
