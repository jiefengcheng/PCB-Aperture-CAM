#!/usr/bin/env python3
"""Compare bounded proportional caps as separate ORG-only T01 diagnostics.

The accepted T01-R1 receipts are read for source and calibration bindings only;
this tool writes a separate ignored evidence directory and never rewrites them.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from shapely import from_wkb
from shapely.geometry import Point, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.crop_dynamic_t01_r1 as engine  # noqa: E402
from src.native_inventory import inventory  # noqa: E402
from tools import run_crop_dynamic_t01_r1_spacing as base  # noqa: E402


MAIN = ROOT / "out/crop_dynamic_tasks/t01_r1_spacing_driven_20261024"
OUTPUT = ROOT / "out/crop_dynamic_tasks/t01_proportional_cap_diagnostic_20261024"
CAPS = (1.5, 2.0, 3.0)
AREA_EPSILON_MM2 = 1e-10


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _capped_constructor(original_constructor, cap_multiplier):
    """Apply the cap before acceptance so later sites observe capped copper."""
    def construct(core, *args, **kwargs):
        result = original_constructor(core, *args, **kwargs)
        center = core.centroid
        original_radius = (core.bounds[2] - core.bounds[0] +
                           core.bounds[3] - core.bounds[1]) / 4
        permitted_radius = cap_multiplier * original_radius
        permitted_disk = Point(center.x, center.y).buffer(
            permitted_radius, quad_segs=engine.QUAD_SEGS)
        uncapped = result["candidate"]
        candidate = unary_union((core, uncapped.intersection(permitted_disk)))
        if not candidate.is_valid or core.difference(candidate).area > AREA_EPSILON_MM2:
            raise AssertionError("PROPORTIONAL_CAP_INVALID_OR_CORE_LOSS")
        removed_area = max(0.0, uncapped.difference(candidate).area)
        growth = candidate.difference(core)
        attached = [part for part in engine._components(growth)
                    if part.distance(core) <= max(1e-9, engine.ERROR_MM / 2)
                    and part.area > engine.AREA_EPSILON_MM2]
        candidate = unary_union([core, *attached]) if attached else core
        result["candidate"] = candidate
        result["growth"] = candidate.difference(core)
        result["core_loss_mm2"] = core.difference(candidate).area
        result["area_delta_mm2"] = max(0.0, candidate.area - core.area)
        result["growth_cap_touched"] = bool(result["growth_cap_touched"] or
                                             removed_area > AREA_EPSILON_MM2)
        result["growth_cap_only_limiter"] = bool(
            removed_area > AREA_EPSILON_MM2 and not result["limiting_obstacles"])
        result["proportional_cap_removed_area_mm2"] = removed_area
        result["proportional_cap_radius_mm"] = permitted_radius
        return result
    return construct


def _candidate_map(result):
    return {row["source_id"]: from_wkb(bytes.fromhex(row["candidate_wkb"]))
            for row in result["decisions"]}


def _source_cores(source, result):
    source_inventory = inventory(source)
    rows = {row["id"]: row for row in source_inventory["objects"]}
    cores = {}
    for decision in result["decisions"]:
        source_row = rows[decision["source_id"]]
        cores[decision["source_id"]] = from_wkb(
            source_inventory["payloads"][source_row["geometry_sha256"]])
    return source_inventory, cores


def main() -> None:
    source_path = ROOT / base.ORG_REL
    source = source_path.read_bytes()
    source_sha = sha(source)
    if source_sha != base.EXPECTED_ORG_SHA:
        raise SystemExit(f"ORG_SOURCE_HASH_MISMATCH:{source_sha}")
    frozen_path = MAIN / "frozen_policy.json"
    frozen_bytes = frozen_path.read_bytes()
    frozen = json.loads(frozen_bytes)
    if frozen["source_sha256"] != source_sha:
        raise SystemExit("FROZEN_POLICY_SOURCE_BINDING_MISMATCH")
    calibration = {float(key): float(value)
                   for key, value in frozen["calibrated_radius_limits_mm"].items()}

    original_constructor = engine.grow_in_available_space
    accepted_receipt_path = MAIN / "t01_r1_run.json"
    accepted_receipt_bytes = accepted_receipt_path.read_bytes()
    accepted_receipt = json.loads(accepted_receipt_bytes)
    accepted_run = accepted_receipt["run"]
    if accepted_receipt["source_sha256"] != source_sha:
        raise SystemExit("ACCEPTED_T01_R1_SOURCE_BINDING_MISMATCH")
    accepted_shapes = {
        row["source_id"]: from_wkb((ROOT / row["geometry_artifact"]).read_bytes())
        for row in accepted_run["decisions"]
    }
    accepted_decisions = {row["source_id"]: row for row in accepted_run["decisions"]}
    baseline = engine.run(source, calibrated_radius_limits=calibration,
                          order_policy="source_yx")
    baseline_shapes = _candidate_map(baseline)
    same_population = set(accepted_shapes) == set(baseline_shapes)
    baseline_differences = {
        source_id: accepted_shapes[source_id].symmetric_difference(
            baseline_shapes[source_id]).area
        for source_id in accepted_shapes if source_id in baseline_shapes
    }
    baseline_equivalence = {
        "accepted_receipt_path": str(accepted_receipt_path.relative_to(ROOT)),
        "accepted_receipt_sha256": sha(accepted_receipt_bytes),
        "accepted_policy_implementation_sha256": frozen["implementation_sha256"],
        "current_implementation_sha256": sha(
            (ROOT / "src/crop_dynamic_t01_r1.py").read_bytes()),
        "implementation_hashes_match": frozen["implementation_sha256"] == sha(
            (ROOT / "src/crop_dynamic_t01_r1.py").read_bytes()),
        "same_target_population": same_population,
        "topologically_identical_site_count": sum(
            accepted_shapes[source_id].equals(baseline_shapes[source_id])
            for source_id in baseline_differences),
        "maximum_per_site_symmetric_difference_mm2": max(
            baseline_differences.values(), default=0.0),
        "total_per_site_symmetric_difference_mm2": sum(
            baseline_differences.values()),
        "accepted_dynamic_event_count": accepted_run["dynamic_adaptation_event_count"],
        "replayed_dynamic_event_count": baseline["dynamic_adaptation_event_count"],
        "accepted_summed_added_area_mm2": sum(
            row["added_area_mm2"] for row in accepted_run["decisions"]),
        "replayed_summed_added_area_mm2": sum(
            row["added_area_mm2"] for row in baseline["decisions"]),
    }
    if (not same_population or
        baseline_equivalence["topologically_identical_site_count"] != len(accepted_shapes) or
        baseline_equivalence["maximum_per_site_symmetric_difference_mm2"] > AREA_EPSILON_MM2):
        raise SystemExit("CURRENT_BASELINE_DIFFERS_FROM_ACCEPTED_T01_R1")

    runs = {}
    images = {}
    checks = []
    try:
        for cap in CAPS:
            engine.grow_in_available_space = _capped_constructor(
                original_constructor, cap)
            result = engine.run(source, calibrated_radius_limits=calibration,
                                order_policy="source_yx")
            replay = engine.run(source, calibrated_radius_limits=calibration,
                                order_policy="source_yx")
            shapes = _candidate_map(result)
            replay_shapes = _candidate_map(replay)
            source_inventory, cores = _source_cores(source, result)
            priority = result["priority_sites_by_component"]
            priority_ids = set(priority.values())
            deterministic = all(shapes[source_id].equals_exact(
                replay_shapes[source_id], 0.0) for source_id in shapes)
            core_preserved = all(
                cores[source_id].difference(shapes[source_id]).area <= AREA_EPSILON_MM2
                for source_id in shapes)
            priority_preserved = all(shapes[source_id].equals(cores[source_id])
                                     for source_id in priority_ids)
            cap_bound_rows = []
            cap_bound_ok = True
            for decision in result["decisions"]:
                source_id = decision["source_id"]
                core = cores[source_id]
                center = core.centroid
                original_radius = (core.bounds[2] - core.bounds[0] +
                                   core.bounds[3] - core.bounds[1]) / 4
                max_radius = max((Point(center.x, center.y).distance(Point(x, y))
                                  for polygon in engine._components(shapes[source_id])
                                  for x, y, *_ in polygon.exterior.coords),
                                 default=original_radius)
                allowed = cap * original_radius
                within = max_radius <= allowed + engine.ERROR_MM
                cap_bound_ok &= within
                uncapped_max_radius = float(
                    accepted_decisions[source_id]["candidate_radius_max_mm"])
                cap_active = uncapped_max_radius > allowed + engine.ERROR_MM
                cap_bound_rows.append({
                    "source_id": source_id,
                    "decision": decision["decision"],
                    "original_radius_mm": original_radius,
                    "uncapped_baseline_maximum_radius_mm": uncapped_max_radius,
                    "maximum_final_radius_mm": max_radius,
                    "proportional_limit_radius_mm": allowed,
                    "cap_reduced_uncapped_extent": cap_active,
                    "added_area_mm2": max(0.0, shapes[source_id].area - core.area),
                    "area_reduction_vs_uncapped_mm2": max(0.0,
                        float(accepted_decisions[source_id]["added_area_mm2"]) -
                        max(0.0, shapes[source_id].area - core.area)),
                    "within_cap": within,
                })
            no_gap_violations = not result["dynamic_hard_gap_violations"]
            checks_for_cap = {
                "deterministic_replay": deterministic,
                "protected_cores_preserved": core_preserved,
                "priority_shapes_preserved": priority_preserved,
                "proportional_radius_cap": cap_bound_ok,
                "hard_gap": no_gap_violations,
            }
            checks.append({"cap_multiplier": cap, **checks_for_cap})
            view = box(*engine.V_BOUNDS)
            svg = OUTPUT / f"cap_{str(cap).replace('.', '_')}_full_crop.svg"
            png = OUTPUT / f"cap_{str(cap).replace('.', '_')}_full_crop.png"
            base.svg_overlay(source_inventory, view, shapes, cores, svg,
                f"T01 proportional-cap diagnostic · {cap:g}× ORG radius",
                priority, scale=500)
            image = base.rasterize_svg(svg)
            images[str(cap)] = {"svg": str(svg.relative_to(ROOT)), **image}
            runs[str(cap)] = {
                "summary": {
                    "site_count": len(result["decisions"]),
                    "grow_count": sum(d["decision"] == "GROW" for d in result["decisions"]),
                    "keep_priority_count": len(priority_ids),
                    "keep_constrained_count": sum(d["decision"] == "KEEP_CONSTRAINED"
                                                   for d in result["decisions"]),
                    "dynamic_adaptation_events": len(result["dynamic_causal_events"]),
                    "minimum_dynamic_optional_gap_mm": result["minimum_dynamic_optional_gap_mm"],
                    "hard_gap_violation_count": len(result["dynamic_hard_gap_violations"]),
                    "summed_added_area_mm2": sum(row["added_area_mm2"] for row in cap_bound_rows),
                    "union_added_area_mm2": result["dynamic_area"]["union_added_area_mm2"],
                    "sites_where_cap_reduced_uncapped_extent": sum(
                        row["cap_reduced_uncapped_extent"] for row in cap_bound_rows),
                    "summed_area_reduction_vs_uncapped_mm2": sum(
                        row["area_reduction_vs_uncapped_mm2"] for row in cap_bound_rows),
                    "deterministic_replay": deterministic,
                },
                "checks": checks_for_cap,
                "sites": cap_bound_rows,
                "causal_events": [{
                    "source_id": row["source_id"],
                    "prior_accepted_neighbor_ids": row["prior_accepted_neighbor_ids"],
                    "dynamic_vs_static_symmetric_difference_mm2":
                        row["dynamic_vs_static_symmetric_difference_mm2"],
                    "decision": row["decision"],
                } for row in result["dynamic_causal_events"]],
            }
    finally:
        engine.grow_in_available_space = original_constructor

    report = {
        "schema": "crop-dynamic-t01-proportional-cap-diagnostic/1",
        "status": "PASS_WITH_SCOPE_LIMITS" if all(
            all(row[key] for key in ("deterministic_replay", "protected_cores_preserved",
                "priority_shapes_preserved", "proportional_radius_cap", "hard_gap"))
            for row in checks) else "FAIL",
        "source_path": str(base.ORG_REL),
        "source_sha256": source_sha,
        "frozen_r1_policy_path": str(frozen_path.relative_to(ROOT)),
        "frozen_r1_policy_sha256": sha(frozen_bytes),
        "implementation_sha256": sha((ROOT / "src/crop_dynamic_t01_r1.py").read_bytes()),
        "baseline_equivalence": baseline_equivalence,
        "independent_review": {
            "status": "NOT_RUN: CHANNEL_UNAVAILABLE",
            "reason": "The active T01 handoff calls for a local review packet and no authenticated independent-review channel was used.",
        },
        "experiment": {
            "caps": list(CAPS),
            "rule": "each nonpriority target's accepted candidate is clipped during sequential construction to the disk centered at the immutable ORG circle centroid with radius k times the ORG radius; capped geometry enters the evolving scene before the next target",
            "schedule": "frozen source-Y/X companion order; priority sites first",
            "EDIT_used_for_construction": False,
            "accepted_T01_R1_records_modified": False,
            "scope": "separate source-only geometric diagnostic; does not replace or amend T01-R1 acceptance records",
        },
        "checks": checks,
        "caps": runs,
        "visualizations": images,
        "limitations": [
            "Uses the same ORG inventory parser and Shapely geometry kernel as the T01-R1 constructor.",
            "A proportional cap is a geometric guardrail, not a sourced CAM sizing rule or manufacturing rule.",
            "Causal event counts are diagnostic and do not establish desirable sizing or owner acceptance.",
            "The frozen T01-R1 receipts remain unchanged; this experiment is evaluated separately.",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / "proportional_cap_diagnostic.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    files = sorted(path for path in OUTPUT.rglob("*") if path.is_file()
                   and path.name != "SHA256SUMS")
    (OUTPUT / "SHA256SUMS").write_text("".join(
        f"{sha(path.read_bytes())}  {path.relative_to(OUTPUT).as_posix()}\n"
        for path in files))
    print(json.dumps({"status": report["status"], "caps": {
        key: value["summary"] for key, value in runs.items()},
        "evidence": str(OUTPUT.relative_to(ROOT))}, indent=2))
    if report["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
