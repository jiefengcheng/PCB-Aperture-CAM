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

EVIDENCE = ROOT / "out/crop_dynamic_tasks/t01_r1"
ORG = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb"


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
    policy_bytes = (EVIDENCE / "frozen_policy.json").read_bytes()
    policy = json.loads(policy_bytes)
    source = ORG.read_bytes()
    source_sha = sha(source)
    check("source_sha256", source_sha == receipt["source_sha256"] == policy["source_sha256"], source_sha)
    check("policy_binding", sha(policy_bytes) == receipt["policy_sha256"] == run_result["contract_sha256"])
    check("policy_implementation_binding",
          policy["implementation_sha256"] == sha((ROOT / "src/crop_dynamic_t01_r1.py").read_bytes()))
    check("handoff_binding", policy["handoff_sha256"] == sha((ROOT / "docs/crop_dynamic_tasks/amendments/T01_R1_20261024/T01_R1_AMENDMENT_HANDOFF.md").read_bytes()))
    check("scope_constants", policy["parameters"]["maximum_growth_reach_mm"] == MAX_GROWTH_REACH_MM and
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
    check("real_dynamic_counterfactuals", len(run_result["controlled_counterfactuals"]) >= 3 and
          all(row["causal_change_observed"] and row["other_prior_candidates_held_fixed"]
              for row in run_result["controlled_counterfactuals"]))
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
    for decision in decisions:
        path = ROOT / decision["geometry_artifact"]
        data = path.read_bytes()
        candidate = from_wkb(data)
        core = from_wkb(source_inv["payloads"][source_rows[decision["source_id"]]["geometry_sha256"]])
        growth = candidate.difference(core)
        geometry_checks.append(sha(data) == decision["geometry_artifact_sha256"] and
            candidate.is_valid and core.difference(candidate).area <= 1e-10 and
            growth.difference(core.buffer(MAX_GROWTH_REACH_MM + ERROR_MM)).area <= 1e-10)
    check("persisted_candidate_geometry", all(geometry_checks), f"{sum(geometry_checks)}/{len(geometry_checks)}")

    # Reconstruct again in this separate interpreter and compare canonical WKB
    # against the persisted files; time/receipt metadata is intentionally ignored.
    replay = run(source)
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
            "The real crop has no non-priority smaller-roomy/larger-crowded reversal; the bounded synthetic counter-control is separately covered by the focused test.",
            "The shared native geometry inventory is not a qualified native KiCad export or electrical-intent checker.",
            "No engineering, manufacturing, DFM, or expert-equivalence acceptance is claimed.",
            "Independent Cursor review: NOT_RUN: CHANNEL_UNAVAILABLE.",
        ]}
    (EVIDENCE / "fresh_verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    receipt["status"]["technical_checks"] = status
    receipt["status"]["fresh_verification_path"] = "out/crop_dynamic_tasks/t01_r1/fresh_verification.json"
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
