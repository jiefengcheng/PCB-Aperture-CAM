#!/usr/bin/env python3
"""Fresh-process, source-bound verification for the local T01-R1 crop receipt."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from shapely import from_wkb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.crop_dynamic_t01_r1 import (  # noqa: E402
    CONSTRUCTION_BUFFER_MM, ERROR_MM, GAP_TOLERANCE_MM, HARD_GAP_MM,
    MAX_GROWTH_REACH_MM, run,
)
from src.native_inventory import inventory  # noqa: E402

EVIDENCE = ROOT / "out/crop_dynamic_tasks/t01_r1_edit_calibrated"
ORG = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb"
EDIT = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/EDIT/top_layer.kicad_pcb"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    errors = []
    checks = []

    def check(name, condition, detail=""):
        checks.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})
        if not condition:
            errors.append(name)

    receipt_bytes = (EVIDENCE / "t01_r1_run.json").read_bytes()
    receipt = json.loads(receipt_bytes)
    run_result = receipt["run"]
    check("owner_acceptance_not_inferred", receipt["status"].get("owner_acceptance") == "NOT_ACCEPTED")
    policy_bytes = (EVIDENCE / "frozen_policy.json").read_bytes()
    policy = json.loads(policy_bytes)
    calibration_path = ROOT / policy["edit_calibration_path"]
    calibration_bytes = calibration_path.read_bytes()
    calibration = json.loads(calibration_bytes)
    calibrated_radius_limits = {float(key): float(value)
        for key, value in policy["calibrated_radius_limits_mm"].items()}
    source = ORG.read_bytes()
    source_sha = sha(source)
    check("source_sha256", source_sha == receipt["source_sha256"] == policy["source_sha256"], source_sha)
    check("policy_binding", sha(policy_bytes) == receipt["policy_sha256"] == run_result["contract_sha256"])
    check("EDIT_calibration_binding", sha(calibration_bytes) == policy["edit_calibration_sha256"] and
          sha(EDIT.read_bytes()) == policy["edit_sha256"] == calibration["edit_sha256"] and
          calibration["org_sha256"] == source_sha and
          calibration["status"] == "CALIBRATION_ONLY_SAME_JOB_NOT_BLIND_GENERALIZATION")
    check("EDIT_calibration_range_census", calibration["exact_center_unique_match_count"] == 46 and
          calibration["unmatched_org_count"] == 5 and calibration["ambiguous_org_count"] == 0 and
          policy["same_job_calibration_counts"]["unique_org_sites"] == 51)
    derived_limits = {float(row["org_radius_class_mm"]):
        float(row["frozen_constructor_max_final_radius_mm"]) for row in calibration["class_ranges"]}
    check("class_caps_derived_from_calibration", calibrated_radius_limits == derived_limits)
    check("policy_implementation_binding",
          policy["implementation_sha256"] == sha((ROOT / "src/crop_dynamic_t01_r1.py").read_bytes()))
    check("handoff_binding", policy["handoff_sha256"] == sha((ROOT / "docs/crop_dynamic_tasks/amendments/T01_R1_20261024/T01_R1_AMENDMENT_HANDOFF.md").read_bytes()))
    check("scope_constants", abs(policy["parameters"]["maximum_growth_reach_mm"] - MAX_GROWTH_REACH_MM) < 1e-12 and
          policy["parameters"]["hard_experimental_separation_mm"] == HARD_GAP_MM and
          policy["parameters"]["gap_tolerance_mm"] == GAP_TOLERANCE_MM and
          policy["parameters"]["construction_buffer_mm"] == CONSTRUCTION_BUFFER_MM)
    check("complete_supported_circle_census", run_result["target_occurrence_count"] == 53 and
          run_result["target_site_count"] == 51 and not run_result["unsupported_FCu_influence_ids"])
    check("all_component_priorities", len(run_result["priority_sites_by_component"]) == 26 and
          not run_result["priority_exceptions"] and
          all(row["status"] == "ROUND_OUTLINE_PRESERVED" for row in run_result["priority_outline_checks"]))
    check("assembled_non_port_gap", not run_result["dynamic_hard_gap_violations"] and
          run_result["minimum_dynamic_optional_gap_mm"] >= HARD_GAP_MM - GAP_TOLERANCE_MM - 1e-10,
          str(run_result["minimum_dynamic_optional_gap_mm"]))
    check("bounded_attachment_ports", not run_result["attached_trace_port_violations"])
    check("range_limited_dynamic_behavior_reported",
          run_result["dynamic_adaptation_event_count"] == 0 and
          run_result["controlled_counterfactuals"] == [],
          "No dynamic-neighbor event occurred under the EDIT-calibrated range; none is claimed.")
    check("real_open_crowded_control", run_result["same_seed_space_control"]["status"] == "PASS" and
          run_result["same_seed_space_control"]["symmetric_difference_mm2"] > 1e-8 and
          run_result["same_seed_space_control"]["open_limit_reasons"])
    check("real_crop_size_order_limitation_explicit",
          run_result["smaller_roomier_vs_larger_crowded"]["status"] in
          ("PASS_REAL_CROP_REVERSAL", "NOT_DEMONSTRATED_REAL_CROP"))

    map_doc = json.loads((EVIDENCE / "selection_and_priority_map.json").read_text())
    details = json.loads((EVIDENCE / "owner_issue_site_details.json").read_text())
    check("owner_source_mapping", len(map_doc["target_occurrences"]) == 53 and
          len(details["sites"]) == 51 and details["occurrence_count"] == 53 and
          all(row["source_id"] and row["source_span_by_id"] and row["limiting_obstacles"] is not None
              for row in details["sites"]))

    source_inv = inventory(source)
    source_rows = {row["id"]: row for row in source_inv["objects"]}
    geometry_checks = []
    decisions = run_result["decisions"]
    uncalibrated_unchanged = []
    class_bounds = []
    for decision in decisions:
        path = ROOT / decision["geometry_artifact"]
        data = path.read_bytes()
        candidate = from_wkb(data)
        core = from_wkb(source_inv["payloads"][source_rows[decision["source_id"]]["geometry_sha256"]])
        growth = candidate.difference(core)
        radius_class = decision["calibrated_org_radius_class_mm"]
        if radius_class is None:
            uncalibrated_unchanged.append(growth.area <= 1e-10 and
                decision["maximum_growth_reach_mm"] == 0.0)
        else:
            class_bounds.append(abs(decision["original_radius_mm"] - radius_class) <= 0.00002 and
                abs(decision["maximum_final_radius_mm"] - calibrated_radius_limits[radius_class]) <= 1e-12 and
                abs(decision["maximum_growth_reach_mm"] - max(0.0, calibrated_radius_limits[radius_class] - decision["original_radius_mm"])) <= 1e-12 and
                decision["maximum_final_radius_mm"] <= calibrated_radius_limits[radius_class] + ERROR_MM and
                decision["candidate_radius_max_mm"] <= calibrated_radius_limits[radius_class] + ERROR_MM and
                decision["maximum_growth_reach_mm"] <= calibrated_radius_limits[radius_class] - radius_class + ERROR_MM)
        geometry_checks.append(sha(data) == decision["geometry_artifact_sha256"] and
            candidate.is_valid and core.difference(candidate).area <= 1e-10 and
            growth.difference(core.buffer(decision["maximum_growth_reach_mm"] + ERROR_MM)).area <= 1e-10)
    check("persisted_candidate_geometry", all(geometry_checks), f"{sum(geometry_checks)}/{len(geometry_checks)}")
    check("EDIT_class_radius_bounds", all(class_bounds), f"{sum(class_bounds)}/{len(class_bounds)}")
    check("unmatched_shapes_unchanged", len(uncalibrated_unchanged) == 5 and all(uncalibrated_unchanged),
          f"{sum(uncalibrated_unchanged)}/5")

    # Reconstruct again in this separate interpreter and compare canonical WKB
    # against the persisted files; time/receipt metadata is intentionally ignored.
    replay = run(source, calibrated_radius_limits=calibrated_radius_limits)
    deterministic = True
    for decision in replay["decisions"]:
        artifact = next(row for row in decisions if row["source_id"] == decision["source_id"])
        expected = (ROOT / artifact["geometry_artifact"]).read_bytes()
        deterministic &= bytes.fromhex(decision["candidate_wkb"]) == expected
    check("fresh_process_determinism", deterministic)

    # Preserve the historical source mismatch as recorded evidence, not a new failure.
    old_audit = policy["old_t01_artifact_manifest_audit"]
    check("historical_baseline_preservation",
          old_audit["status"] == "PRESERVED_BASELINE_HAS_EXISTING_MISMATCH" and
          old_audit["mismatch_paths"] == ["t01_full_crop.png"])

    status = "PASS_WITH_SCOPE_LIMITS" if not errors else "FAIL"
    report = {"schema": "crop-dynamic-t01-r1-fresh-verification/1",
        "status": status, "source_sha256": source_sha,
        "policy_sha256": sha(policy_bytes), "fresh_process_replay": True,
        "checks": checks, "failed_checks": errors,
        "scope_limits": [
            "EDIT radius limits are calibrated on the same ORG/EDIT job from exact-center matches; they are not universal PCB rules.",
            "Five ORG shapes without a unique same-center EDIT match are intentionally unchanged.",
            "No dynamic-neighbor adaptation event occurred under these tight bounds; that behavior is not demonstrated by this run.",
            "The real crop has no non-priority smaller-roomy/larger-crowded reversal; the bounded synthetic counter-control is separately covered by the focused test.",
            "The shared native geometry inventory is not a qualified native KiCad export or electrical-intent checker.",
            "No engineering, manufacturing, DFM, or expert-equivalence acceptance is claimed.",
            "Independent Cursor review: NOT_RUN: CHANNEL_UNAVAILABLE.",
        ]}
    (EVIDENCE / "fresh_verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    receipt["status"]["technical_checks"] = status
    receipt["status"]["fresh_verification_path"] = "out/crop_dynamic_tasks/t01_r1_edit_calibrated/fresh_verification.json"
    (EVIDENCE / "t01_r1_run.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    report_path = EVIDENCE / "t01_r1_report.md"
    report_text = report_path.read_text()
    report_text = report_text.replace("RUN COMPLETE; TECHNICAL VERIFICATION PENDING", status)
    report_text += f"\nFresh-process verification: `{status}`; see `fresh_verification.json`.\n"
    report_path.write_text(report_text)
    manifest_paths = sorted(path for path in EVIDENCE.rglob("*")
                            if path.is_file() and path.name != "SHA256SUMS")
    (EVIDENCE / "SHA256SUMS").write_text("".join(
        f"{sha(path.read_bytes())}  {path.relative_to(EVIDENCE).as_posix()}\n"
        for path in manifest_paths))
    print(json.dumps({"status": status, "checks_passed": sum(c["status"] == "PASS" for c in checks),
        "checks_total": len(checks), "failed_checks": errors,
        "verification_path": str(EVIDENCE / "fresh_verification.json")}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
