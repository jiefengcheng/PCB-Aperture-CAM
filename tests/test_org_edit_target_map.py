"""Focused checks for the frozen ORG→EDIT target-map evidence contract."""
import hashlib
from pathlib import Path
import unittest

from src.org_edit_target_map import (
    EDIT_REL, EXPECTED_MEMBERS, ORG_REL, PROFILE_REL, WINDOW_HALF_MM,
    build_target_map, fixed_window,
)


ROOT = Path(__file__).resolve().parents[1]


class OrgEditTargetMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = build_target_map(ROOT)
        cls.members = {member["ordinal"]: member for member in cls.result["members"]}

    def test_exact_family_and_source_bytes_are_bound_without_rerunning_recognition(self):
        self.assertFalse(self.result["recognition_rerun"])
        self.assertFalse(self.result["family_membership_changed"])
        self.assertEqual(tuple(self.result["member_keys"]), EXPECTED_MEMBERS)
        for side, rel in (("ORG", ORG_REL), ("EDIT", EDIT_REL)):
            digest = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
            self.assertEqual(self.result["sources"][side]["sha256"], digest)
        self.assertEqual(self.result["package_integrity"]["status"], "MISMATCH")
        self.assertIn("raw/.DS_Store", self.result["package_integrity"]["failed_paths"])

    def test_circle_and_trace_ambiguity_are_retained(self):
        self.assertEqual(self.members[1]["seed"]["edit_status"], "SUPPORTED")
        self.assertEqual(self.members[2]["seed"]["edit_status"], "AMBIGUOUS")
        self.assertEqual(len(self.members[2]["seed"]["edit_candidates"]), 2)
        self.assertEqual(self.members[3]["seed"]["edit_status"], "SUPPORTED")
        for ordinal in (1, 3):
            member = self.members[ordinal]
            mapped = [edge for edges in member["trace_correspondence"]["by_org_trace"].values()
                      for edge in edges]
            self.assertEqual(len(mapped), 1)
            self.assertAlmostEqual(mapped[0]["before_width_mm"], 0.05004, places=6)
            self.assertAlmostEqual(mapped[0]["after_width_mm"], 0.1, places=6)
            self.assertLess(mapped[0]["after_covered_fraction"], 0.90)
        self.assertTrue(all(not edges for edges in self.members[2]["trace_correspondence"]["by_org_trace"].values()))

    def test_references_fixed_windows_and_unsupported_geometry_are_explicit(self):
        halfx, halfy = WINDOW_HALF_MM
        for ordinal, member in self.members.items():
            cx, cy = member["center_org_mm"]
            lo_x, lo_y, hi_x, hi_y = member["window_mm"]
            self.assertAlmostEqual((hi_x - lo_x) / 2, halfx)
            self.assertAlmostEqual((hi_y - lo_y) / 2, halfy)
            self.assertAlmostEqual((lo_x + hi_x) / 2, cx)
            self.assertAlmostEqual((lo_y + hi_y) / 2, cy)
            refs = {entry["layer"]: entry for entry in member["reference_correspondence"]}
            self.assertEqual(refs["F.Mask"]["status"], "SUPPORTED")
            self.assertAlmostEqual(refs["F.Mask"]["candidates"][0]["boundary_hausdorff_distance_mm"], 0.0)
            self.assertEqual(refs["F.Paste"]["status"], "UNMATCHED")
            groups = member["physical_contact_group"]
            self.assertEqual(groups["org"]["count"], len(groups["org"]["source_member_ids"]))
            self.assertEqual(groups["group_correspondence_status"], "NOT_ESTABLISHED")
            self.assertTrue(all(c["object_count"] == len(c["source_identities"])
                                for c in groups["edit_supported_local_components"]
                                if c["status"] == "SUPPORTED_GEOMETRY_COMPONENT"))
            local = member["local_copper_region"]
            self.assertGreater(local["added_area_mm2"], 0)
            self.assertGreater(local["removed_area_mm2"], 0)
            self.assertEqual(len(local["org_source_identities"]), local["org_supported_object_count"])
            self.assertEqual(len(local["edit_source_identities"]), local["edit_supported_object_count"])
        c = self.members[3]["local_copper_region"]
        self.assertEqual(c["status"], "NOT_ESTABLISHED")
        self.assertEqual(len(c["unsupported_edit"]), 2)
        self.assertTrue(all(row["reason"] == "DEGENERATE_ARC" for row in c["unsupported_edit"]))
        self.assertTrue(all(component["completeness"] == "NOT_ESTABLISHED"
                            for component in self.members[3]["physical_contact_group"]["edit_supported_local_components"]))

    def test_audit_scope_registration_and_area_method_are_machine_readable(self):
        quality = self.result["registration_quality"]
        self.assertEqual(quality["matched_anchor_count"], self.result["registration"]["inlier_count"])
        self.assertEqual(quality["residual_summary_mm"]["maximum"],
                         self.result["registration"]["max_inlier_residual_mm"])
        self.assertEqual(len(quality["org_anchor_centroid_bounds_mm"]), 4)
        self.assertGreater(len(self.result["source_record_sha256"]), 100)
        source_by_hash = {
            self.result["sources"]["ORG"]["sha256"]: (ROOT / ORG_REL).read_bytes(),
            self.result["sources"]["EDIT"]["sha256"]: (ROOT / EDIT_REL).read_bytes(),
        }
        for identity, digest in self.result["source_record_sha256"].items():
            source_hash, span = identity.split(":bytes:")
            byte_start, byte_end = map(int, span.split(":"))
            self.assertEqual(hashlib.sha256(source_by_hash[source_hash][byte_start:byte_end]).hexdigest(), digest)
        for member in self.members.values():
            search = member["seed"]["candidate_search"]
            self.assertIn("gr_circle", search["universe"])
            self.assertIn("Other primitive kinds", search["excluded_semantics"])
            self.assertGreater(search["universe_count"], 0)
            mask = next(ref for ref in member["reference_correspondence"] if ref["layer"] == "F.Mask")
            self.assertTrue(mask["candidates"][0]["registration_fit_anchor"]["included"])
            local = member["local_copper_region"]
            method = local["measurement_method"]
            self.assertEqual(method["area_units"], "mm^2")
            self.assertEqual(method["window_bounds_mm"], member["window_mm"])
            self.assertEqual(method["inventory_version"], "native-inventory/2")
            self.assertGreater(method["per_curve_approximation_error_mm"], 0)
            self.assertIn("unioned", method["included_objects"])
            self.assertIn("segment and arc", member["trace_correspondence"]["candidate_scope"])
            for edges in member["trace_correspondence"]["by_org_trace"].values():
                for edge in edges:
                    self.assertEqual(edge["uncovered_edit_extent_status"].split(":",1)[0], "NOT_ESTABLISHED")


if __name__ == "__main__":
    unittest.main()
