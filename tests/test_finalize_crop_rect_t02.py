import unittest

from tools.finalize_crop_rect_t02 import target_details_html


class T02ReviewHtmlTests(unittest.TestCase):
    def test_target_table_shows_input_provenance_and_limiting_object(self):
        document = {"decisions": [{
            "source_id": "rect<&>", "source_span": [10, 20],
            "source_geometry_sha256": "a" * 64,
            "source_size_mm": [0.1, 0.2],
            "accepted_size_mm_in_source_axes": [0.12, 0.22],
            "maximum_size_mm": [0.15, 0.3], "orientation_radians": 0.0,
            "limiting_constraints": {
                "policy_cap": {"active_axes": [0]},
                "crop_boundary": {"cap_to_crop_boundary_mm": 0.012345},
                "tightest_recorded_constraint": {
                    "source_id": "T01_SCENE:decision-1", "source_kind": "accepted_T01_scene_addition",
                    "source_span": [], "constraint_type": "original_protected_source_construction_gap",
                    "measured_gap_mm": 0.02003, "required_gap_mm": 0.02002,
                    "passes_tolerance": True,
                },
                "nearest_prior_t02_addition": None,
            },
            "input_scene_revision": 2, "output_scene_revision": 3,
            "decision": "GROW", "verification": {"core": True, "cap": True},
        }]}

        rendered = target_details_html(document)

        self.assertIn("10–20", rendered)
        self.assertIn("&lt;&amp;&gt;", rendered)
        self.assertIn("T01_SCENE:decision-1", rendered)
        self.assertIn("0.02003000 / 0.02002000 mm required", rendered)
        self.assertIn("2 → 3", rendered)
        self.assertIn("X axis", rendered)
        self.assertIn("0.012345 mm", rendered)
        self.assertIn("PASS", rendered)


if __name__ == "__main__":
    unittest.main()
