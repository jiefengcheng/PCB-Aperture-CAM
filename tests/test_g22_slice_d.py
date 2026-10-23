import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.build_g22_slice_d import PATH_KEYS, main as build_slice_d, validate_payload
from src.ingestion_registry import _validate_g22_reconstruction_payload


def payload_fixture():
    def case_hash(case):
        return hashlib.sha256(case.encode()).hexdigest()
    members = []
    for index in (1, 2, 3):
        panels = {key: f"M{index} 0 L{index} 1 Z" for key in PATH_KEYS}
        candidate = f"candidate_member_{index}"
        sources = {
            "org": ["ORG"], "candidate": [candidate], "edit": ["EDIT"],
            "candidate_added_vs_org": [candidate, "ORG"],
            "candidate_removed_vs_org": ["ORG", candidate],
            "edit_missing_vs_candidate": ["EDIT", candidate],
            "candidate_extra_vs_edit": [candidate, "EDIT"],
        }
        members.append({
            "member": index,
            "member_key": f"member-{index}",
            "view_box_mm": [0, -3, 6, 3],
            "panels": panels,
            "display_binding": {
                "member": index, "member_key": f"member-{index}",
                "fixed_window_mm": [1, -2, 2, -1], "analysis_window_mm": [0, -3, 6, 0],
                "view_box_mm": [0, -3, 6, 3],
                "panel_source_cases": sources,
                "source_gerber_sha256_by_case": {case: case_hash(case) for case in {x for xs in sources.values() for x in xs}},
                "panel_sha256": {key: hashlib.sha256(path.encode()).hexdigest() for key, path in panels.items()},
            },
            "scope_and_constraints": {"editable_source_occurrences": [{"source_identity": "source"}],
                                      "fixed_window_mm": [0, 0, 1, 1], "protected_scope": "protected",
                                      "source_authorization_and_geometric_containment": {
                                          "status": "PASS", "edit_target_input_to_constructor": False,
                                          "all_source_object_bounds_inside_window_plus_halo": True}},
            "measurements": {
                "local_neighbor_interaction": {"status": "PASS_NO_NEW_LOCAL_CONTACT_OR_FRAGMENTATION"},
                "edit_target_qualification": "NOT_ESTABLISHED" if index == 3 else "MEASURED_SUPPORTED_GEOMETRY",
                "whole_target_fit": "NOT_ESTABLISHED" if index == 3 else "MEASURED",
                "native_to_gerber_fidelity": {f"candidate_member_{index}": {"status": "PASS"}},
                "B_alternatives_retained": [{"identity": "a"}, {"identity": "b"}] if index == 2 else None,
            },
        })
    return {
        "schema": "pcb-g22-family-reconstruction-visual-v1",
        "dataset_id": "dataset",
        "execution_stages": [{"stage_id": str(i), "evidence_sha256": "a" * 64} for i in range(5)],
        "scope_and_constraints": {"named_electrical_ports_status": "NOT_RECORDED", "protected_scope": "protected"},
        "members": members,
    }


class G22SliceDTests(unittest.TestCase):
    def test_dynamic_slice_c_input_must_be_complete_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "receipt.json"
            receipt.write_text(json.dumps({"schema": "wrong", "aggregate_export_status": "FAILED"}))
            digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "SLICE_C_RECEIPT_NOT_COMPLETE"):
                build_slice_d(receipt_path=receipt, expected_receipt_sha256=digest)

    def test_visual_payload_requires_three_source_bound_member_panels(self):
        validate_payload(payload_fixture())
        payload = payload_fixture()
        payload["members"][1]["panels"].pop("edit_missing_vs_candidate")
        with self.assertRaisesRegex(ValueError, "PANEL_BINDING_INVALID"):
            validate_payload(payload)

    def test_visual_payload_rejects_swapped_member_or_panel_reference(self):
        payload = payload_fixture()
        payload["members"][0]["display_binding"] = copy.deepcopy(payload["members"][1]["display_binding"])
        with self.assertRaisesRegex(ValueError, "DISPLAY_BINDING_INVALID"):
            validate_payload(payload)
        payload = payload_fixture()
        payload["members"][0]["panels"]["candidate"] = payload["members"][1]["panels"]["candidate"]
        with self.assertRaisesRegex(ValueError, "PANEL_CONTENT_HASH_MISMATCH"):
            validate_payload(payload)

    def test_visual_payload_fails_closed_on_wrong_member_order_or_frame(self):
        payload = payload_fixture()
        payload["members"][2]["member"] = 2
        with self.assertRaisesRegex(ValueError, "MEMBER_SET_INVALID"):
            validate_payload(payload)

    def test_visual_payload_requires_bound_execution_and_does_not_invent_ports(self):
        payload = payload_fixture()
        payload["execution_stages"][0].pop("evidence_sha256")
        with self.assertRaisesRegex(ValueError, "EXECUTION_STAGES_UNBOUND"):
            validate_payload(payload)
        payload = payload_fixture()
        payload["scope_and_constraints"]["named_electrical_ports_status"] = "PASS"
        with self.assertRaisesRegex(ValueError, "MUST_NOT_INVENT_NAMED_PORTS"):
            validate_payload(payload)
        payload = payload_fixture()
        payload["members"][0]["scope_and_constraints"]["protected_scope"] = "different"
        with self.assertRaisesRegex(ValueError, "PROTECTED_SCOPE_MISMATCH"):
            validate_payload(payload)
        payload = payload_fixture()
        payload["members"][0]["scope_and_constraints"]["source_authorization_and_geometric_containment"]["all_source_object_bounds_inside_window_plus_halo"] = False
        with self.assertRaisesRegex(ValueError, "SCOPE_CHECK_NOT_PASS"):
            validate_payload(payload)
        payload = payload_fixture()
        payload["members"][0]["view_box_mm"] = [2, 0, -1, 1]
        with self.assertRaisesRegex(ValueError, "FRAME_INVALID"):
            validate_payload(payload)

    def test_renderer_payload_cannot_strengthen_receipt_statuses_or_replace_b_alternatives(self):
        payload = payload_fixture()
        receipt, fit = {"windows": {}, "cases": {}}, {"transfer": []}
        def case_hash(case):
            return hashlib.sha256(case.encode()).hexdigest()
        for case in ("ORG", "EDIT"):
            receipt["cases"][case] = {"gerbers": {"F.Cu": {"sha256": case_hash(case)}}}
        for row in payload["members"]:
            n, key = row["member"], str(row["member"])
            alternatives = [{"identity": "edit-a"}, {"identity": "edit-b"}] if n == 2 else []
            edit_status = "NOT_ESTABLISHED" if n == 3 else "MEASURED_SUPPORTED_GEOMETRY"
            fit_status = "NOT_ESTABLISHED" if n == 3 else "MEASURED"
            topology = {"status": "PASS_NO_NEW_LOCAL_CONTACT_OR_FRAGMENTATION", "analysis_boundary_open": False,
                        "window_bounds_mm": [0, -3, 6, 0]}
            fidelity = {"candidate_member_" + key: {"status": "PASS"}}
            refs = {"F.Mask": {"whole_layer_normalized_byte_check": {"status": "PASS"}}}
            exported = {"candidate_vs_org": {"symmetric_difference_area_mm2": .02},
                        "candidate_vs_edit": {"symmetric_difference_area_mm2": .12},
                        "unchanged_org_vs_edit": {"symmetric_difference_area_mm2": .14},
                        "local_neighbor_interaction": topology}
            receipt["windows"][key] = {"bounds_org_mm": [1, -2, 2, -1],
                                       "exported_copper_comparison": exported,
                                       "native_export_fidelity": fidelity}
            digest = "candidate-" + key
            receipt["cases"]["candidate_member_" + key] = {"source_sha256": digest,
                                                           "gerbers": {"F.Cu": {"sha256": case_hash("candidate_member_" + key)}},
                                                           "reference_layer_preservation_vs_org": refs}
            fit["transfer"].append({"member": n, "member_key": row["member_key"],
                                    "target_composition_status": edit_status,
                                    "whole_target_fit_status": fit_status,
                                    "edit_candidate_alternatives_retained": alternatives})
            row["candidate_board_sha256"] = digest
            row["measurements"] = {**exported, "native_to_gerber_fidelity": fidelity,
                                   "reference_layer_preservation_vs_org": refs,
                                   "edit_target_qualification": edit_status,
                                   "whole_target_fit": fit_status,
                                   "B_alternatives_retained": alternatives if n == 2 else None}
        _validate_g22_reconstruction_payload(payload, receipt, fit, "dataset")
        payload["members"][0]["display_binding"]["source_gerber_sha256_by_case"]["ORG"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "display/source binding mismatch"):
            _validate_g22_reconstruction_payload(payload, receipt, fit, "dataset")
        payload["members"][0]["display_binding"]["source_gerber_sha256_by_case"]["ORG"] = case_hash("ORG")
        payload["members"][2]["measurements"]["whole_target_fit"] = "MEASURED"
        with self.assertRaisesRegex(ValueError, "qualification differs|falsely qualifies"):
            _validate_g22_reconstruction_payload(payload, receipt, fit, "dataset")


if __name__ == "__main__":
    unittest.main()
