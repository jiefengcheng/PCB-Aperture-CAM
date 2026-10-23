from pathlib import Path
import sys
import unittest
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.reference_region_profile import (  # noqa: E402
    build_profile,
    reference_authority_status,
    resolve_context_claim,
)


class ReferenceRegionProfileTests(unittest.TestCase):
    def test_pinned_family_profile_measures_each_confirmed_member_without_qualifying_it(self):
        profile = build_profile(ROOT)
        members = profile["family"]["members"]

        self.assertEqual([member["physical_contact_group"]["count"] for member in members], [22, 18, 10])
        self.assertEqual(len({member["physical_contact_group"]["key"] for member in members}), 3)
        self.assertEqual([round(member["seed"]["diameter_mm"], 5) for member in members], [0.24994] * 3)
        for member in members:
            self.assertEqual(len(member["references"]), 2)
            self.assertEqual({tuple(ref["layers"]) for ref in member["references"]}, {("F.Mask",), ("F.Paste",)})
            self.assertTrue(all(ref["geos_equals_seed"] for ref in member["references"]))
            self.assertTrue(all(ref["seed_center_offset_mm"] == [0.0, 0.0] for ref in member["references"]))
            self.assertTrue(all(ref["authority_status"] == "UNKNOWN" for ref in member["references"]))
            self.assertEqual(len(member["traces"]), 2)
            self.assertTrue(all(trace["seed_intersects"] and trace["net_id"] == 0 for trace in member["traces"]))
            self.assertTrue(all(neighbor["gap_from_seed_mm"] <= 0.5 for neighbor in member["nearby_external_copper_geometry"]))
            layer_geometry = {item["path"].split("/")[-1]: item for item in member["additional_org_layer_geometry"]["seed"]}
            for name in ("top_layer.gdo.gbr", "top_soldermask.gdo.gbr", "top_solderpaste.gdo.gbr"):
                self.assertTrue(layer_geometry[name]["seed_bbox_matches_feature_bbox_within_5um"])
                self.assertEqual(layer_geometry[name]["seed_to_feature_bbox_distance_lower_bound_mm"], 0.0)
            for name in ("cvl_top.gdo.gbr", "cvl_bottom.gdo.gbr", "sus_bottom.gdo.gbr", "outboard.gdo.gbr"):
                self.assertFalse(layer_geometry[name]["seed_bbox_matches_feature_bbox_within_5um"])
                self.assertGreater(layer_geometry[name]["seed_to_feature_bbox_distance_lower_bound_mm"], 0)
            self.assertTrue(all(item["strict_project_geometry_parser_probe"]["status"] == "UNSUPPORTED" for item in layer_geometry.values()))
            self.assertEqual(len(member["additional_org_layer_geometry"]["traces"]), 2)
            for trace_geometry in member["additional_org_layer_geometry"]["traces"]:
                trace_layers = {item["path"].split("/")[-1]: item for item in trace_geometry["layers"]}
                self.assertGreater(trace_layers["cvl_top.gdo.gbr"]["seed_to_feature_bbox_distance_lower_bound_mm"], 0)
                self.assertGreater(trace_layers["sus_bottom.gdo.gbr"]["seed_to_feature_bbox_distance_lower_bound_mm"], 0)
            self.assertEqual(member["context"]["seed"]["subject_id"], member["seed_source_id"])
            context_subjects = [member["context"]["seed"], *member["context"]["traces"]]
            self.assertEqual(len(context_subjects), 3)
            self.assertTrue(all(claim["status"] == "UNKNOWN" for subject in context_subjects for claim in subject["claims"].values()))

        expected_layer_gaps = [
            [[2.195523678, 5.400149894, 1.132530000, 0.631530000], [1.895156958, 5.371528986, 0.874482047, 0.373482047], [2.169938690, 5.491439810, 1.143480000, 0.642480000]],
            [[1.913337434, 5.722710934, 1.132530000, 0.631530000], [1.785106666, 5.687502224, 0.993480005, 0.492480005], [1.907717794, 5.734087704, 1.108480000, 0.607480000]],
            [[1.714995563, 6.065715768, 0.878859792, 0.202530000], [1.415038985, 6.082871344, 0.744482047, 0.101482047], [1.703991103, 6.165669774, 0.872257695, 0.213480000]],
        ]
        layer_names = ("cvl_top.gdo.gbr", "cvl_bottom.gdo.gbr", "sus_bottom.gdo.gbr", "outboard.gdo.gbr")
        for member, expected_subjects in zip(members, expected_layer_gaps):
            subjects = [member["additional_org_layer_geometry"]["seed"], *[row["layers"] for row in member["additional_org_layer_geometry"]["traces"]]]
            self.assertEqual(len(subjects), 3)
            for measured_rows, expected_values in zip(subjects, expected_subjects):
                measured = {row["path"].split("/")[-1]: row["seed_to_feature_bbox_distance_lower_bound_mm"] for row in measured_rows}
                for name, expected in zip(layer_names, expected_values):
                    self.assertAlmostEqual(measured[name], expected, places=9)

        self.assertEqual(profile["family"]["status"], "PROVISIONAL_PATTERN_HYPOTHESIS")
        self.assertEqual(profile["project_defaults"]["netclass_assignments"], {})
        self.assertTrue(profile["source_material_integrity"]["ORG_board_sha256_matches_pin"])
        self.assertEqual(profile["source_material_integrity"]["dataset_sha256_manifest"]["status"], "MISMATCH")
        searched_raw = [row for row in profile["source_search"]["files"] if row["path"].startswith("dataset/szu-comm_3020301113B_intake_ready_20261021_v1/raw/")]
        self.assertEqual(len(searched_raw), len(json.loads((ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v1/metadata/profile.json").read_text())["files"]))
        self.assertEqual([row["path"].split("/raw/", 1)[1] for row in profile["source_search"]["skipped_raw_sources"]], [".DS_Store"])
        self.assertIn("zero hits do not prove semantic absence", profile["source_search"]["method_and_limit"].lower())

    def test_layer_labels_and_geometric_coincidence_do_not_grant_reference_authority(self):
        for label in ("F.Mask", "F.Paste", "F.Cu", "CVL_TOP", "APPROVED_REFERENCE"):
            self.assertEqual(reference_authority_status(label, True), "UNKNOWN")

    def test_missing_and_wrong_revision_context_annotations_remain_unknown(self):
        claim = "active_bending"
        subject = "member-a"
        self.assertEqual(resolve_context_claim([], claim=claim, subject_id=subject, revision="r2")["status"], "UNKNOWN")

        old_revision = [{"claim": claim, "subject_id": subject, "source_revision": "r1", "value": True}]
        result = resolve_context_claim(old_revision, claim=claim, subject_id=subject, revision="r2")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["rejected_wrong_revision_evidence"], old_revision)

    def test_conflicting_current_revision_context_annotations_are_not_resolved_by_precedence(self):
        evidence = [
            {"claim": "supported_termination", "subject_id": "member-a", "source_revision": "r2", "value": True, "source_id": "a"},
            {"claim": "supported_termination", "subject_id": "member-a", "source_revision": "r2", "value": False, "source_id": "b"},
        ]
        result = resolve_context_claim(evidence, claim="supported_termination", subject_id="member-a", revision="r2")
        self.assertEqual(result["status"], "CONFLICT")
        self.assertEqual(result["applicable_evidence"], evidence)

    def test_conflicting_reference_authority_declarations_are_not_resolved_by_layer_name(self):
        evidence = [
            {"claim": "reference_authority", "subject_id": "mask-candidate", "source_revision": "r2", "value": True},
            {"claim": "reference_authority", "subject_id": "mask-candidate", "source_revision": "r2", "value": False},
        ]
        result = resolve_context_claim(evidence, claim="reference_authority", subject_id="mask-candidate", revision="r2")
        self.assertEqual(result["status"], "CONFLICT")
