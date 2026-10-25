#!/usr/bin/env python3
"""Run one source-only T01-R1 schedule diagnostic without replacing the baseline."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from shapely import from_wkb
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.crop_dynamic_t01_r1 import EVENT_EPSILON_MM2, V_BOUNDS, run  # noqa: E402
from src.native_inventory import inventory  # noqa: E402
from tools import run_crop_dynamic_t01_r1_spacing as base  # noqa: E402


OUTPUT = ROOT / "out/crop_dynamic_tasks/t01_r1_order_diagnostic_20261024"
MAIN = ROOT / "out/crop_dynamic_tasks/t01_r1_spacing_driven_20261024"
ORDER_POLICY = "roomiest_first"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_map(decisions):
    return {row["source_id"]: from_wkb(bytes.fromhex(row["candidate_wkb"]))
            for row in decisions}


def main() -> None:
    source_path = ROOT / base.ORG_REL
    source = source_path.read_bytes()
    source_sha = sha(source)
    if source_sha != base.EXPECTED_ORG_SHA:
        raise SystemExit(f"ORG_SOURCE_HASH_MISMATCH:{source_sha}")
    frozen = json.loads((MAIN / "frozen_policy.json").read_text())
    limits = {float(k): float(v)
              for k, v in frozen["calibrated_radius_limits_mm"].items()}
    if frozen["source_sha256"] != source_sha:
        raise SystemExit("MAIN_POLICY_SOURCE_BINDING_MISMATCH")

    current_default = run(source, calibrated_radius_limits=limits,
                          order_policy="source_yx")
    alternative = run(source, calibrated_radius_limits=limits,
                      order_policy=ORDER_POLICY)
    replay = run(source, calibrated_radius_limits=limits,
                 order_policy=ORDER_POLICY)

    static_rows = {row["source_id"]: row
                   for row in alternative["static_baseline"]["decisions"]}
    dynamic_shapes = candidate_map(alternative["decisions"])
    static_shapes = candidate_map(alternative["static_baseline"]["decisions"])
    default_shapes = candidate_map(current_default["decisions"])
    replay_shapes = candidate_map(replay["decisions"])
    event_rows = []
    order_rows = []
    for decision in alternative["decisions"]:
        source_id = decision["source_id"]
        delta_static = dynamic_shapes[source_id].symmetric_difference(
            static_shapes[source_id]).area
        delta_default = dynamic_shapes[source_id].symmetric_difference(
            default_shapes[source_id]).area
        prior = decision.get("prior_accepted_neighbor_ids", [])
        if delta_static > EVENT_EPSILON_MM2 and prior:
            event_rows.append({"source_id": source_id, "order": decision["order"],
                "accepted_prior_neighbor_ids": prior,
                "dynamic_vs_same_order_static_symmetric_difference_mm2": delta_static,
                "dynamic_vs_default_order_symmetric_difference_mm2": delta_default,
                "nearest_target_spacing_mm": decision["nearest_target_spacing_mm"],
                "growth_reach_mm": decision["maximum_growth_reach_mm"],
                "added_area_mm2": decision["added_area_mm2"],
                "decision": decision["decision"]})
        order_rows.append({"source_id": source_id, "order": decision["order"],
            "decision": decision["decision"],
            "growth_reach_mm": decision["maximum_growth_reach_mm"],
            "dynamic_vs_same_order_static_symmetric_difference_mm2": delta_static,
            "dynamic_vs_default_order_symmetric_difference_mm2": delta_default,
            "accepted_prior_neighbor_ids": prior})

    replay_ok = all(dynamic_shapes[sid].equals_exact(replay_shapes[sid], 0.0)
                    for sid in dynamic_shapes)
    priority = alternative["priority_sites_by_component"]
    inv = inventory(source)
    rows = {row["id"]: row for row in inv["objects"]}
    cores = {row["source_id"]: from_wkb(
        inv["payloads"][rows[row["source_id"]]["geometry_sha256"]])
        for row in alternative["decisions"]}
    view = box(*V_BOUNDS)
    overlay = OUTPUT / "roomiest_first_full_crop.png"
    svg = OUTPUT / "roomiest_first_full_crop.svg"
    base.svg_overlay(inv, view, dynamic_shapes, cores, svg,
        "T01-R1 order diagnostic · roomiest ORG targets first",
        priority, scale=500)
    image_receipt = base.rasterize_svg(svg)

    checks = {
        "source_identity": source_sha == base.EXPECTED_ORG_SHA,
        "same_target_population": len(alternative["decisions"]) == 51 and
            len(current_default["decisions"]) == 51,
        "priority_shapes_preserved": all(
            dynamic_shapes[sid].equals(cores[sid])
            for sid in priority.values()),
        "deterministic_replay": replay_ok,
        "same_policy_static_comparison": len(static_rows) == 51,
    }
    report = {
        "schema": "crop-dynamic-t01-r1-order-diagnostic/1",
        "status": "PASS_WITH_SCOPE_LIMITS" if all(checks.values()) else "FAIL",
        "source_sha256": source_sha,
        "implementation_sha256": sha((ROOT / "src/crop_dynamic_t01_r1.py").read_bytes()),
        "base_run_path": str((MAIN / "t01_r1_run.json").relative_to(ROOT)),
        "order_policy": {
            "name": ORDER_POLICY,
            "rule": "26 source-only priority sites remain first; remaining sites ordered by descending nearest-target spacing reach computed from immutable ORG cores, then stable source ID",
            "role": "single bounded order diagnostic; does not replace the source-Y/X baseline",
            "EDIT_used": False,
        },
        "summary": {
            "sites": len(alternative["decisions"]),
            "grow": sum(row["decision"] == "GROW" for row in alternative["decisions"]),
            "adaptation_events": len(event_rows),
            "geometry_differences_from_default_order": sum(
                row["dynamic_vs_default_order_symmetric_difference_mm2"] >
                EVENT_EPSILON_MM2 for row in order_rows),
            "deterministic_replay": replay_ok,
            "minimum_final_gap_mm": alternative["minimum_dynamic_optional_gap_mm"],
            "hard_gap_violations": len(alternative["dynamic_hard_gap_violations"]),
        },
        "checks": checks,
        "events": event_rows,
        "ordered_decisions": order_rows,
        "visualization": {"svg_path": str(svg.relative_to(ROOT)), **image_receipt},
        "limitations": [
            "Source-Y/X remains the main run; this is a diagnostic alternative only.",
            "An event count does not establish desired sizing or owner acceptance.",
            "Shared native inventory and Shapely geometry kernel; no independent parser or manufacturing qualification.",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "order_diagnostic.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    files = sorted(p for p in OUTPUT.rglob("*") if p.is_file()
                   and p.name != "SHA256SUMS")
    (OUTPUT / "SHA256SUMS").write_text("".join(
        f"{sha(path.read_bytes())}  {path.relative_to(OUTPUT).as_posix()}\n"
        for path in files))
    print(json.dumps({"status": report["status"], **report["summary"],
        "visualization": report["visualization"]["png_path"],
        "evidence": str(OUTPUT.relative_to(ROOT))}, indent=2))
    if report["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
