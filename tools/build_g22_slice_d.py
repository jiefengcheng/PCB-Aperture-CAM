#!/usr/bin/env python3
"""Build a source-bound visual payload for the existing ORG family sheet.

All displayed copper comes from the final Slice C Gerber exports. This builder
does not rerun fitting, modify candidate geometry, or turn comparison into an
acceptance decision.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.visual_scene import svg_path
from tools.run_g22_slice_c import FIT, CONTRACT, parsed_layer_regions, sha

RUN = ROOT / "out/g22_family_reconstruction/slice_c/run_20261023T191905_425702Z"
RECEIPT = RUN / "run_receipt.json"
OUTPUT = ROOT / "out/g22_family_reconstruction/slice_d/presentation.json"
BUILD_RECEIPT = ROOT / "out/g22_family_reconstruction/slice_d/build_receipt.json"
AUDIT = ROOT / "out/g22_family_reconstruction/slice_c/chatgpt_audit_receipt.md"
PATH_KEYS = {"org", "candidate", "edit", "candidate_added_vs_org", "candidate_removed_vs_org",
             "edit_missing_vs_candidate", "candidate_extra_vs_edit"}


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_fcu(receipt: dict, case: str) -> Path:
    relative = receipt["cases"][case]["gerbers"]["F.Cu"]["path"]
    path = ROOT / relative
    if not path.is_file() or sha(path) != receipt["cases"][case]["gerbers"]["F.Cu"]["sha256"]:
        raise ValueError(f"SLICE_C_GERBER_BINDING_MISMATCH:{case}")
    return path


def validate_payload(payload: dict) -> None:
    if payload.get("schema") != "pcb-g22-family-reconstruction-visual-v1":
        raise ValueError("G22_VISUAL_PAYLOAD_SCHEMA_INVALID")
    if [row.get("member") for row in payload.get("members", [])] != [1, 2, 3]:
        raise ValueError("G22_VISUAL_PAYLOAD_MEMBER_SET_INVALID")
    if not payload.get("execution_stages") or not payload.get("scope_and_constraints"):
        raise ValueError("G22_VISUAL_EXECUTION_OR_SCOPE_RECORD_MISSING")
    if payload["scope_and_constraints"].get("named_electrical_ports_status") != "NOT_RECORDED":
        raise ValueError("G22_VISUAL_MUST_NOT_INVENT_NAMED_PORTS")
    if len(payload["execution_stages"]) < 5 or any(not row.get("evidence_sha256") for row in payload["execution_stages"]):
        raise ValueError("G22_VISUAL_EXECUTION_STAGES_UNBOUND")
    for row in payload["members"]:
        if not row.get("member_key") or set(row.get("panels", {})) != PATH_KEYS:
            raise ValueError(f"G22_VISUAL_MEMBER_PANEL_BINDING_INVALID:{row.get('member')}")
        view_box = row.get("view_box_mm", [])
        if len(view_box) != 4 or not all(math.isfinite(float(value)) for value in view_box) or view_box[2] <= 0 or view_box[3] <= 0:
            raise ValueError(f"G22_VISUAL_MEMBER_FRAME_INVALID:{row.get('member')}")
        if any(not isinstance(path, str) for path in row["panels"].values()):
            raise ValueError(f"G22_VISUAL_MEMBER_GEOMETRY_INVALID:{row.get('member')}")
        measurements = row.get("measurements", {})
        if measurements.get("local_neighbor_interaction", {}).get("status") not in {
            "PASS_NO_NEW_LOCAL_CONTACT_OR_FRAGMENTATION",
            "FAIL_NEW_GEOMETRIC_CONTACT", "FAIL_POSSIBLE_LOCAL_FRAGMENTATION",
            "NOT_ESTABLISHED_LOCAL_COMPONENTS_TOUCH_ANALYSIS_BOUNDARY",
        }:
            raise ValueError(f"G22_VISUAL_TOPOLOGY_STATUS_MISSING:{row.get('member')}")
        if measurements.get("edit_target_qualification") not in {
            "MEASURED_SUPPORTED_GEOMETRY", "NOT_ESTABLISHED",
        } or measurements.get("whole_target_fit") not in {"MEASURED", "NOT_ESTABLISHED"}:
            raise ValueError(f"G22_VISUAL_TARGET_STATUS_MISSING:{row.get('member')}")
        candidate_key = f"candidate_member_{row['member']}"
        fidelity = measurements.get("native_to_gerber_fidelity", {}).get(candidate_key, {}).get("status")
        if fidelity not in {"PASS", "FAIL", "NOT_ESTABLISHED"}:
            raise ValueError(f"G22_VISUAL_LOCAL_FIDELITY_STATUS_MISSING:{row.get('member')}")
        if row["member"] == 2 and len(measurements.get("B_alternatives_retained") or []) != 2:
            raise ValueError("G22_VISUAL_B_ALTERNATIVES_NOT_RETAINED")
        if row["member"] == 3 and measurements.get("whole_target_fit") != "NOT_ESTABLISHED":
            raise ValueError("G22_VISUAL_C_TARGET_FALSE_PASS")
        constraints = row.get("scope_and_constraints", {})
        if not constraints.get("editable_source_occurrences") or not constraints.get("fixed_window_mm"):
            raise ValueError(f"G22_VISUAL_MEMBER_SCOPE_MISSING:{row.get('member')}")
        if constraints.get("protected_scope") != payload["scope_and_constraints"].get("protected_scope"):
            raise ValueError(f"G22_VISUAL_MEMBER_PROTECTED_SCOPE_MISMATCH:{row.get('member')}")
        replay = constraints.get("source_authorization_and_geometric_containment", {})
        if (replay.get("status") != "PASS" or replay.get("edit_target_input_to_constructor") is not False
                or replay.get("all_source_object_bounds_inside_window_plus_halo") is not True):
            raise ValueError(f"G22_VISUAL_MEMBER_SCOPE_CHECK_NOT_PASS:{row.get('member')}")
        binding = row.get("display_binding", {})
        candidate_case = f"candidate_member_{row['member']}"
        expected_sources = {
            "org": ["ORG"], "candidate": [candidate_case], "edit": ["EDIT"],
            "candidate_added_vs_org": [candidate_case, "ORG"],
            "candidate_removed_vs_org": ["ORG", candidate_case],
            "edit_missing_vs_candidate": ["EDIT", candidate_case],
            "candidate_extra_vs_edit": [candidate_case, "EDIT"],
        }
        if (binding.get("member") != row["member"] or binding.get("member_key") != row["member_key"]
                or binding.get("view_box_mm") != view_box
                or set(binding.get("panel_sha256", {})) != PATH_KEYS
                or binding.get("panel_source_cases") != expected_sources
                or set(binding.get("source_gerber_sha256_by_case", {})) != {case for cases in expected_sources.values() for case in cases}):
            raise ValueError(f"G22_VISUAL_MEMBER_DISPLAY_BINDING_INVALID:{row.get('member')}")
        if any(not isinstance(digest, str) or len(digest) != 64
               or any(character not in "0123456789abcdef" for character in digest)
               for digest in binding["source_gerber_sha256_by_case"].values()):
            raise ValueError(f"G22_VISUAL_MEMBER_SOURCE_HASH_INVALID:{row.get('member')}")
        if any(binding["panel_sha256"].get(key) != digest_bytes(path.encode("utf-8"))
               for key, path in row["panels"].items()):
            raise ValueError(f"G22_VISUAL_MEMBER_PANEL_CONTENT_HASH_MISMATCH:{row.get('member')}")


def main(receipt_path: Path | None = None, expected_receipt_sha256: str | None = None,
         output_path: Path | None = None) -> int:
    receipt_path = receipt_path or RECEIPT
    output_path = output_path or OUTPUT
    receipt_path = Path(receipt_path).resolve()
    output_path = Path(output_path).resolve()
    if not receipt_path.is_file():
        raise FileNotFoundError("SLICE_C_RECEIPT_ABSENT")
    if expected_receipt_sha256 and sha(receipt_path) != expected_receipt_sha256:
        raise ValueError("SLICE_C_RECEIPT_HASH_MISMATCH")
    # The default invocation is pinned to the accepted C receipt. A fresh C run
    # may be supplied explicitly by the full experiment entrypoint, which
    # captures and binds its receipt digest before building this payload.
    if receipt_path == RECEIPT and sha(RECEIPT) != "de23d6d50602d6b98288c9b1d1fdb694815a19eb88cc8d7595a282e0b3b33956":
        raise ValueError("SLICE_C_FINAL_RECEIPT_HASH_MISMATCH")
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("schema") != "g22-slice-c-export-readback/1" or receipt.get("aggregate_export_status") != "EXPORTS_AND_GERBER_REREAD_COMPLETED":
        raise ValueError("SLICE_C_RECEIPT_NOT_COMPLETE")
    fit = json.loads(FIT.read_text())
    contract = json.loads(CONTRACT.read_text())
    windows = [box(*bounds) for bounds in contract["windows"]]
    halo = float(contract["safety_halo"]["value_mm"])
    analysis = [window.buffer(halo, join_style="mitre") for window in windows]
    parsed: dict[str, list] = {}
    case_names = ["ORG", "EDIT", *(f"candidate_member_{i}" for i in range(1, 4))]
    for name in case_names:
        path = get_fcu(receipt, name)
        _, regions = parsed_layer_regions(path, analysis)
        parsed[name] = [row["geometry"] for row in regions]

    members = []
    for transfer in fit["transfer"]:
        number = transfer["member"]
        key = str(number)
        org, candidate, edit = (parsed["ORG"][number - 1],
                                parsed[f"candidate_member_{number}"][number - 1],
                                parsed["EDIT"][number - 1])
        candidate_added = candidate.difference(org)
        candidate_removed = org.difference(candidate)
        edit_missing = edit.difference(candidate)
        candidate_extra = candidate.difference(edit)
        exported = receipt["windows"][key]["exported_copper_comparison"]
        qualification = contract["member_target_qualification"][number - 1]
        interaction = exported["local_neighbor_interaction"]
        replay_scope = receipt["source_isolation"]["org_only_constructor_replay"][key]
        candidate_case = f"candidate_member_{number}"
        panel_source_cases = {
            "org": ["ORG"], "candidate": [candidate_case], "edit": ["EDIT"],
            "candidate_added_vs_org": [candidate_case, "ORG"],
            "candidate_removed_vs_org": ["ORG", candidate_case],
            "edit_missing_vs_candidate": ["EDIT", candidate_case],
            "candidate_extra_vs_edit": [candidate_case, "EDIT"],
        }
        panel_hashes = {panel: digest_bytes(path.encode("utf-8")) for panel, path in {
            "org": svg_path(org, tolerance=None, coordinate_precision=6),
            "candidate": svg_path(candidate, tolerance=None, coordinate_precision=6),
            "edit": svg_path(edit, tolerance=None, coordinate_precision=6),
            "candidate_added_vs_org": svg_path(candidate_added, tolerance=None, coordinate_precision=6),
            "candidate_removed_vs_org": svg_path(candidate_removed, tolerance=None, coordinate_precision=6),
            "edit_missing_vs_candidate": svg_path(edit_missing, tolerance=None, coordinate_precision=6),
            "candidate_extra_vs_edit": svg_path(candidate_extra, tolerance=None, coordinate_precision=6),
        }.items()}
        members.append({
            "member": number,
            "member_key": transfer["member_key"],
            "view_box_mm": [analysis[number - 1].bounds[0], analysis[number - 1].bounds[1],
                            analysis[number - 1].bounds[2] - analysis[number - 1].bounds[0],
                            analysis[number - 1].bounds[3] - analysis[number - 1].bounds[1]],
            "panels": {
                "org": svg_path(org, tolerance=None, coordinate_precision=6),
                "candidate": svg_path(candidate, tolerance=None, coordinate_precision=6),
                "edit": svg_path(edit, tolerance=None, coordinate_precision=6),
                "candidate_added_vs_org": svg_path(candidate_added, tolerance=None, coordinate_precision=6),
                "candidate_removed_vs_org": svg_path(candidate_removed, tolerance=None, coordinate_precision=6),
                "edit_missing_vs_candidate": svg_path(edit_missing, tolerance=None, coordinate_precision=6),
                "candidate_extra_vs_edit": svg_path(candidate_extra, tolerance=None, coordinate_precision=6),
            },
            "measurements": {
                "candidate_vs_org": exported["candidate_vs_org"],
                "candidate_vs_edit": exported["candidate_vs_edit"],
                "unchanged_org_vs_edit": exported["unchanged_org_vs_edit"],
                "local_neighbor_interaction": exported["local_neighbor_interaction"],
                "edit_target_qualification": exported["edit_target_qualification"],
                "whole_target_fit": exported["whole_target_fit"],
                "native_to_gerber_fidelity": receipt["windows"][key]["native_export_fidelity"],
                "reference_layer_preservation_vs_org": receipt["cases"][f"candidate_member_{number}"]["reference_layer_preservation_vs_org"],
                "B_alternatives_retained": transfer["edit_candidate_alternatives_retained"] if number == 2 else None,
                "C_unsupported_retained": transfer["target_composition_status"] == "NOT_ESTABLISHED" if number == 3 else None,
            },
            "recipe": {**transfer["candidate_receipt"],
                       "parameters_shared": transfer["parameters_shared"]},
            "candidate_board_sha256": transfer["candidate_board_sha256"],
            "scope_and_constraints": {
                "fixed_window_mm": qualification["window_mm"],
                "safety_halo_mm": halo,
                "editable_source_occurrences": transfer["candidate_receipt"]["editable_source_occurrences"],
                "protected_scope": contract["protected_occurrences"],
                "reference_roles": contract["reference_roles"],
                "candidate_allowlist_subset_of_covered_occurrences": qualification["candidate_specific_component_allowlist_must_be_subset_of_covered_occurrences"],
                "interaction_rule": transfer["neighbor_rule"],
                "interaction_result": interaction,
                "context_unknowns": qualification["context_unknowns"],
                "source_authorization_and_geometric_containment": replay_scope,
                "fixed_ports_disposition": "No named electrical ports are recorded in the contract. Non-allowlisted source bytes are preserved; the reported interaction check is local plotted geometry only.",
            },
            "display_binding": {
                "member": number,
                "member_key": transfer["member_key"],
                "fixed_window_mm": receipt["windows"][key]["bounds_org_mm"],
                "analysis_window_mm": interaction["window_bounds_mm"],
                "view_box_mm": [analysis[number - 1].bounds[0], analysis[number - 1].bounds[1],
                                analysis[number - 1].bounds[2] - analysis[number - 1].bounds[0],
                                analysis[number - 1].bounds[3] - analysis[number - 1].bounds[1]],
                "panel_source_cases": panel_source_cases,
                "source_gerber_sha256_by_case": {
                    case: receipt["cases"][case]["gerbers"]["F.Cu"]["sha256"]
                    for case in sorted({name for names in panel_source_cases.values() for name in names})
                },
                "panel_sha256": panel_hashes,
            },
        })

    def evidence_stage(stage_id: str, title: str, path: Path, detail: str) -> dict:
        return {"stage_id": stage_id, "title": title, "evidence_path": str(path.relative_to(ROOT)),
                "evidence_sha256": sha(path), "detail": detail}

    execution_stages = [
        evidence_stage("A", "Freeze target and experiment contract", CONTRACT,
                       "Bound ORG/EDIT revisions, fixed member windows, transform, halo, allowlists, assumptions, UNKNOWN context and incomplete-target rules."),
        evidence_stage("B", "Fit finite recipe candidates", FIT,
                       "Recorded bounded search and selection; A calibrated the shared parameters, then the same parameters transferred to B/C without per-member retuning."),
        evidence_stage("B-candidates", "Generate ORG-derived candidate boards", FIT,
                       "The fit report binds each candidate board hash and source-located operation list. This report is the execution receipt; no separate intermediate geometry replay was captured."),
        evidence_stage("C", "Export and independently reread artwork", receipt_path,
                       f"Pinned KiCad {receipt.get('cli_version', receipt.get('tool_versions', {}).get('kicad_cli', 'version recorded in receipt'))} exported the bound cases; Gerbonara reread the exported Gerbers and the injected out-of-scope copper fault was rejected."),
        evidence_stage("D", "Compare fixed-window plotted geometry", receipt_path,
                       "The final plotted-image comparisons, residuals, local interaction checks and status qualifications are recorded in this same Slice C receipt; no intermediate geometry animation is implied."),
    ]
    scope_and_constraints = {
        "protected_scope": contract["protected_occurrences"],
        "reference_roles": contract["reference_roles"],
        "fixed_window_plus_halo_mm": halo,
        "editable_scope_rule": contract["editable_occurrences"],
        "named_electrical_ports_status": "NOT_RECORDED",
        "port_interpretation": "The recipe and export checks preserve source-located non-allowlisted bytes and test local geometric contact/fragmentation only; they do not identify semantic nets or named electrical ports.",
        "objective_guardrails": contract["objective_guardrails"],
        "unknown_context_policy": "UNKNOWN stays UNKNOWN; no support, bend or electrical classification is inferred.",
    }

    payload = {
        "schema": "pcb-g22-family-reconstruction-visual-v1",
        "dataset_id": "client:szu-comm:3020301113b:intake-20261021:v1",
        "status": "EXPERIMENTAL_COMPARISON_ONLY",
        "source_receipt": str(receipt_path.relative_to(ROOT)),
        "source_receipt_sha256": sha(receipt_path),
        "slice_b_report_sha256": sha(FIT),
        "experiment_contract_sha256": sha(CONTRACT),
        "producer_code": {
            "tools/build_g22_slice_d.py": sha(Path(__file__).resolve()),
            "src/visual_scene.py": sha(ROOT / "src/visual_scene.py"),
            "tools/run_g22_slice_c.py": sha(ROOT / "tools/run_g22_slice_c.py"),
        },
        "org_sha256": fit["inputs"]["ORG_sha256"],
        "edit_sha256": fit["inputs"]["EDIT_sha256"],
        "coordinate_basis": "Registered native ORG coordinates; fixed member windows plus declared 0.075 mm halo; Gerber Y mapped through the recorded X2 SameCoordinates frame; no per-member recentering or fitted transform.",
        "geometry_basis": "F.Cu effective plotted geometry reread from the exact KiCad exports bound by the Slice C receipt. Display SVG paths are unsimplified but rounded to 6 decimal places; measurement receipts retain full precision.",
        "execution_stages": execution_stages,
        "scope_and_constraints": scope_and_constraints,
        "limitations": [
            "This compares a frozen experimental candidate with ORG and the observed EDIT export; it does not reconstruct expert intent or manufacturing rules.",
            "EDIT native-to-export fidelity is NOT_ESTABLISHED because its complete F.Cu native inventory contains 84 unsupported arcs. EDIT comparison is therefore shown only as the reread KiCad plotted image, not as a qualified complete target.",
            "B preserves two competing EDIT circle identities; neither is resolved by the candidate score.",
            "C target composition remains NOT_ESTABLISHED. Partial plotted-image measurements are not whole-target fit.",
            "Local neighbor checks describe plotted geometry in each fixed neighborhood plus halo, not global clearance or electrical connectivity.",
            "Package inventory status remains MISMATCH. DRC was NOT_RUN; electrical, manufacturing, factory, and owner engineering acceptance are NOT_ESTABLISHED.",
        ],
        "review": {"chatgpt_summary_audit": "Slice C: CONDITIONAL PASS to proceed to D; Slice D: CONDITIONAL ACCEPT, source-to-display binding condition locally verified; summary-only review",
                   "chatgpt_audit_receipt": str(AUDIT.relative_to(ROOT)),
                   "chatgpt_audit_receipt_sha256": sha(AUDIT),
                   "cursor": "NOT_RUN: CHANNEL_UNAVAILABLE"},
        "members": members,
    }
    validate_payload(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    output_path.write_bytes(encoded)
    build_receipt = {
        "schema": "g22-slice-d-build-receipt/1",
        "status": "SOURCE_BOUND_VISUAL_PAYLOAD_BUILT",
        "input_slice_c_receipt": str(receipt_path.relative_to(ROOT)),
        "input_slice_c_receipt_sha256": sha(receipt_path),
        "input_slice_b_report_sha256": sha(FIT),
        "input_experiment_contract_sha256": sha(CONTRACT),
        "output_payload": str(output_path.relative_to(ROOT)),
        "output_payload_sha256": digest_bytes(encoded),
        "builder_sha256": sha(Path(__file__).resolve()),
        "limitations": ["Build receipt records payload generation only; workbench publication verification is recorded separately."],
    }
    BUILD_RECEIPT.write_text(json.dumps(build_receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"output": str(output_path.relative_to(ROOT)), "sha256": digest_bytes(encoded),
                      "build_receipt": str(BUILD_RECEIPT.relative_to(ROOT)),
                      "build_receipt_sha256": sha(BUILD_RECEIPT), "members": len(members), "bytes": len(encoded)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
