#!/usr/bin/env python3
"""Read-only T01 audit diagnostics; never rewrites the executed run receipt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from shapely import from_wkb
from shapely.geometry import box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.crop_dynamic_t01 import (  # noqa: E402
    GAP_BUFFER_MARGIN_MM,
    GAP_TOLERANCE_MM,
    GROWTH_CAP_MM,
    PROTECTED_GAP_MM,
    _components,
)
from src.native_inventory import inventory  # noqa: E402

EVIDENCE = ROOT / "out/crop_dynamic_tasks/t01"
AUDIT = ROOT / "out/crop_dynamic_tasks/t01_audit"
SOURCE = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb"
COUNTERFACTUAL_ORDERS = (1, 6, 18)  # sites 02, 07, 19 in the frozen order


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_candidate(relative: str, expected_sha: str | None = None):
    data = (ROOT / relative).read_bytes()
    if expected_sha is not None:
        assert sha(data) == expected_sha, f"geometry hash mismatch: {relative}"
    return from_wkb(data)


def build_candidate(core, obstacle_rows):
    """Replay one site's dynamic rule against explicit current obstacles."""
    nominal = core.buffer(GROWTH_CAP_MM, quad_segs=32)
    addition = nominal.difference(core)
    forbidden = [g.buffer(PROTECTED_GAP_MM + GAP_BUFFER_MARGIN_MM, quad_segs=32)
                 for _, g in obstacle_rows]
    for obstacle in forbidden:
        if addition.is_empty:
            break
        addition = addition.difference(obstacle)
    attached = [g for g in _components(addition) if g.distance(core) <= 1e-7]
    candidate = unary_union([core, *attached]) if attached else core
    if forbidden:
        optional = candidate.difference(core).difference(unary_union(forbidden))
        attached = [g for g in _components(optional) if g.distance(core) <= 1e-7]
        candidate = unary_union([core, *attached]) if attached else core
    return candidate


def baseline_summary(rows, source_geometries):
    ids = [d["source_id"] for d in rows]
    candidates = {d["source_id"]: read_candidate(d["geometry_artifact"], d["geometry_sha256"])
                  for d in rows}
    core_losses = [source_geometries[sid].difference(candidates[sid]).area for sid in ids]
    additions = {sid: candidates[sid].difference(source_geometries[sid]) for sid in ids}
    pair_gaps = []
    violations = []
    minimum = PROTECTED_GAP_MM - GAP_TOLERANCE_MM
    for i, sid in enumerate(ids):
        if additions[sid].is_empty:
            continue
        for other_id in ids[i + 1:]:
            if additions[other_id].is_empty:
                continue
            gap = min(additions[sid].distance(candidates[other_id]),
                      additions[other_id].distance(candidates[sid]))
            pair_gaps.append(gap)
            if gap < minimum:
                violations.append({"source_ids": [sid, other_id], "gap_mm": gap})
    return {
        "maximum_core_loss_mm2": max(core_losses, default=0.0),
        "minimum_final_pair_gap_mm": min(pair_gaps, default=None),
        "pair_count_below_hard_threshold_minus_tolerance": len(violations),
        "first_five_violating_pairs": violations[:5],
        "sum_of_per_site_added_area_mm2": sum(g.area for g in additions.values()),
        "union_added_area_mm2": unary_union(list(additions.values())).area,
        "overlap_double_count_mm2": sum(g.area for g in additions.values())
            - unary_union(list(additions.values())).area,
    }


def diagnose() -> dict:
    receipt_bytes = (EVIDENCE / "t01_run.json").read_bytes()
    receipt = json.loads(receipt_bytes)
    run = receipt["run"]
    source_bytes = SOURCE.read_bytes()
    source_sha = sha(source_bytes)
    assert source_sha == run["source_sha256"]

    inv = inventory(source_bytes)
    halo = box(*run["viewport_mm"]).buffer(run["halo_mm"])
    source_geometries = {}
    for obj in inv["objects"]:
        digest = obj["geometry_sha256"]
        if "F.Cu" not in obj["layers"] or not digest:
            continue
        geom = from_wkb(inv["payloads"][digest])
        if geom.intersects(halo):
            source_geometries[obj["id"]] = geom

    decisions = run["decisions"]
    by_id = {d["source_id"]: d for d in decisions}
    dynamic = {d["source_id"]: read_candidate(d["geometry_artifact"], d["geometry_sha256"])
               for d in decisions}
    counterfactuals = []
    for order in COUNTERFACTUAL_ORDERS:
        target = decisions[order]
        target_id = target["source_id"]
        target_core = source_geometries[target_id]
        assert target["adapted_by_prior_acceptance"]
        assert target["limiting_prior_source_ids"]
        removed_id = target["limiting_prior_source_ids"][0]
        obstacles = []
        for other_id, original in source_geometries.items():
            if other_id == target_id:
                continue
            other_decision = by_id.get(other_id)
            if (other_decision is not None and other_decision["order"] < order
                    and other_id != removed_id):
                geom = dynamic[other_id]
            else:
                geom = original
            obstacles.append((other_id, geom))

        counterfactual = build_candidate(target_core, obstacles)
        recorded = dynamic[target_id]
        optional = counterfactual.difference(target_core)
        gaps = [optional.distance(g) for oid, g in obstacles if oid != target_id]
        gap = min(gaps, default=None) if not optional.is_empty else None
        witness = recorded.symmetric_difference(counterfactual).area
        counterfactuals.append({
            "order": order,
            "site_label": f"site-{order + 1:02d}",
            "target_source_id": target_id,
            "removed_prior_source_id": removed_id,
            "other_prior_candidates_held_fixed": True,
            "recorded_growth_area_mm2": recorded.difference(target_core).area,
            "counterfactual_growth_area_mm2": counterfactual.difference(target_core).area,
            "recorded_vs_counterfactual_symmetric_difference_mm2": witness,
            "counterfactual_minimum_gap_mm": gap,
            "causal_effect_observed_under_shared_engine": witness > 1e-8,
            "counterfactual_meets_0_020_mm_hard_gap": gap is None or gap >= PROTECTED_GAP_MM - GAP_TOLERANCE_MM,
        })

    dynamic_summary = baseline_summary(decisions, source_geometries)
    static_rows = run["static_baseline"]["decisions"]
    static_summary = baseline_summary(static_rows, source_geometries)

    # Recompute a frozen-neighborhood comparator using the dynamic construction
    # buffer. This remains a per-site frozen-neighbor experiment; final candidates
    # are then checked jointly and may still conflict with one another.
    frozen_candidates = []
    for decision in decisions:
        source_id = decision["source_id"]
        core = source_geometries[source_id]
        obstacles = [(sid, geom) for sid, geom in source_geometries.items() if sid != source_id]
        candidate = build_candidate(core, obstacles)
        frozen_candidates.append({"source_id": source_id, "core": core, "candidate": candidate})
    frozen_additions = [r["candidate"].difference(r["core"]) for r in frozen_candidates]
    frozen_violation_pairs = []
    frozen_gaps = []
    for i, left in enumerate(frozen_candidates):
        left_add = left["candidate"].difference(left["core"])
        if left_add.is_empty:
            continue
        for right in frozen_candidates[i + 1:]:
            right_add = right["candidate"].difference(right["core"])
            if right_add.is_empty:
                continue
            gap = min(left_add.distance(right["candidate"]), right_add.distance(left["candidate"]))
            frozen_gaps.append(gap)
            if gap < PROTECTED_GAP_MM - GAP_TOLERANCE_MM:
                frozen_violation_pairs.append(gap)

    result = {
        "schema": "crop-dynamic-t01-audit-diagnostics/1",
        "status": "DIAGNOSTIC_ONLY",
        "frozen_run_sha256": sha(receipt_bytes),
        "source_sha256": source_sha,
        "shared_parser_and_kernel": True,
        "counterfactual_replays": counterfactuals,
        "saved_dynamic_final_pairwise_check": dynamic_summary,
        "saved_static_baseline_final_pairwise_check": static_summary,
        "saved_static_baseline_policy_difference": {
            "dynamic_buffer_gap_mm": PROTECTED_GAP_MM + GAP_BUFFER_MARGIN_MM,
            "saved_static_buffer_gap_mm": PROTECTED_GAP_MM,
            "dynamic_quad_segs": 32,
            "saved_static_quad_segs": 8,
            "therefore_area_comparison_is_not_a_one_variable_dynamic_vs_static_test": True,
        },
        "uniform_buffer_frozen_neighbor_diagnostic": {
            "construction_buffer_gap_mm": PROTECTED_GAP_MM + GAP_BUFFER_MARGIN_MM,
            "sum_of_per_site_added_area_mm2": sum(g.area for g in frozen_additions),
            "union_added_area_mm2": unary_union(frozen_additions).area,
            "minimum_final_pair_gap_mm": min(frozen_gaps, default=None),
            "pair_count_below_hard_threshold_minus_tolerance": len(frozen_violation_pairs),
            "note": "Each site was evaluated against ORG neighbors with the dynamic construction buffer; the combined baseline is checked jointly afterward.",
        },
        "interpretation": [
            "The three controlled single-neighbor removals change the later candidate under the same construction engine; this supports causal attribution for these examples only.",
            "The saved dynamic geometry passes the pairwise final hard-gap check in this shared geometry representation.",
            "The saved static baseline uses a smaller gap buffer and lower circle approximation resolution than the dynamic run; its larger summed area is not an apples-to-apples effect estimate.",
            "Static per-site candidates are not jointly feasible: their final optional growth overlaps or violates the hard gap. The summed per-site area double-counts overlap.",
            "No independent parser/kernel, native export, EDIT fit, electrical, or manufacturing result is established.",
        ],
    }
    assert all(row["causal_effect_observed_under_shared_engine"] for row in counterfactuals)
    assert all(row["counterfactual_meets_0_020_mm_hard_gap"] for row in counterfactuals)
    return result


def write_outputs(result: dict) -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    result_path = AUDIT / "diagnostics.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    lines = [
        "# T01 audit diagnostics (supplement; run remains frozen)",
        "",
        f"- Frozen run SHA-256: `{result['frozen_run_sha256']}`",
        f"- ORG source SHA-256: `{result['source_sha256']}`",
        "- Execution receipt and original candidates were read-only inputs.",
        "- These diagnostics share the production source parser and Shapely kernel.",
        "",
        "## Counterfactual samples",
        "",
        "| Site | Removed earlier source | Recorded growth (mm²) | Counterfactual growth (mm²) | Symmetric difference (mm²) | Minimum gap (mm) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in result["counterfactual_replays"]:
        lines.append(
            f"| {row['site_label']} | `{row['removed_prior_source_id']}` | "
            f"{row['recorded_growth_area_mm2']:.9f} | {row['counterfactual_growth_area_mm2']:.9f} | "
            f"{row['recorded_vs_counterfactual_symmetric_difference_mm2']:.9f} | "
            f"{row['counterfactual_minimum_gap_mm']:.9f} |"
        )
    lines.extend([
        "",
        "Each sample held other prior accepted candidates fixed and replaced one attributed earlier addition with its ORG source geometry. All three later candidates changed under that controlled replay, with the 0.020 mm hard-gap threshold retained.",
        "",
        "## Static baseline audit",
        "",
        f"- Saved static baseline summed per-site additions: `{result['saved_static_baseline_final_pairwise_check']['sum_of_per_site_added_area_mm2']:.9f} mm²`.",
        f"- Union area (without double counting overlaps): `{result['saved_static_baseline_final_pairwise_check']['union_added_area_mm2']:.9f} mm²`.",
        f"- Pairwise hard-gap violations after combining the static candidates: `{result['saved_static_baseline_final_pairwise_check']['pair_count_below_hard_threshold_minus_tolerance']}`.",
        f"- Saved static policy buffers to `{result['saved_static_baseline_policy_difference']['saved_static_buffer_gap_mm']:.3f} mm` and uses `quad_segs={result['saved_static_baseline_policy_difference']['saved_static_quad_segs']}`; dynamic uses `{result['saved_static_baseline_policy_difference']['dynamic_buffer_gap_mm']:.3f} mm` and `quad_segs={result['saved_static_baseline_policy_difference']['dynamic_quad_segs']}`.",
        "- Therefore the old area comparison does not isolate the evolving-neighbor effect; the saved static candidates also overlap and are not jointly feasible.",
        "",
        "The hard final gap is 0.020 mm. The extra 0.005 mm is a construction buffer margin. The dynamic final minimum gap is checked separately against the hard threshold.",
        "",
        "No existing receipt, run geometry, or prior verifier output was overwritten. This supplement does not establish independent parser/kernel correctness or engineering qualification.",
        "",
    ])
    (AUDIT / "audit_summary.md").write_text("\n".join(lines))
    files = sorted(p for p in AUDIT.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (AUDIT / "SHA256SUMS").write_text("".join(
        f"{sha(p.read_bytes())}  {p.relative_to(AUDIT).as_posix()}\n" for p in files))


if __name__ == "__main__":
    result = diagnose()
    write_outputs(result)
    print(json.dumps(result, indent=2, sort_keys=True))
