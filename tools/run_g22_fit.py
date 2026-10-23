#!/usr/bin/env python3
"""Run the frozen, bounded ORG-only G22 geometric hypothesis search."""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import sys
import uuid
from pathlib import Path

from shapely import wkb
from shapely.geometry import Point, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ingestion_files import sha  # noqa: E402
from src.native_inventory import inventory  # noqa: E402
from src.g22_reconstruction import (  # noqa: E402
    _geometry_for_change, _named, _point, generate_org_candidate, supported_union,
)

TARGET_MAP = ROOT / "out/ingestion/audits/20261024_g22_org_edit_target_map_v1/target_map.json"
DATA = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v1/raw"
ORG_PATH = DATA / "ORG/top.kicad_pcb"
EDIT_PATH = DATA / "EDIT/top_layer.kicad_pcb"
CONTRACT_DIR = ROOT / "out/g22_family_reconstruction/slice_a"
R1 = (0.0, 0.00953, 0.025)
W1 = (0.0, 0.025, 0.05)
R2 = (0.0, 0.00953, 0.025, 0.05)
W2 = (0.0, 0.025, 0.05)
B2 = (0.005, 0.01, 0.02)
R3 = (0.0, 0.00953, 0.025)
W3 = (0.0, 0.025, 0.05)
B3 = (0.0, 0.01)
MAX_GROWTH = 0.05


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def latest_contract():
    files = list(CONTRACT_DIR.glob("experiment_contract_*.json"))
    if not files:
        raise FileNotFoundError("RUN_SLICE_A_CONTRACT_FIRST")
    path = max(files, key=lambda x: x.stat().st_mtime_ns)
    payload = json.loads(path.read_text())
    return path, payload


def _load_geometry_objects(raw, inv, window):
    clip = box(*window)
    records, unsupported = [], []
    for row in inv["objects"]:
        if "F.Cu" not in row.get("layers", []):
            continue
        if row.get("geometry_sha256"):
            geom = wkb.loads(inv["payloads"][row["geometry_sha256"]])
            if geom.intersects(clip):
                records.append((row, geom))
        elif row.get("coverage") != "GEOMETRY_AVAILABLE":
            # Slice-A's source-local unsupported list governs whether this can affect the window.
            unsupported.append(row)
    return records, unsupported


def _selection(contract, target_map, ordinal, inv, raw):
    member = contract["member_target_qualification"][ordinal - 1]
    tm = target_map["members"][ordinal - 1]
    source_hash = contract["sources"]["ORG"]["sha256"]
    group = set(member["physical_contact_group_source_ids"])
    window = member["window_mm"]
    halo = contract["safety_halo"]["value_mm"]
    envelope = box(window[0]-halo, window[1]-halo, window[2]+halo, window[3]+halo)
    rowmap = {row["id"]: row for row in inv["objects"]}
    by_identity = {o["identity"]: o for o in contract["org_effective_geometry_coverage"]["members"][ordinal-1]["effective_geometry_occurrences"]}
    seed = member["initial_editable_seed_identity"]
    identities = []
    for identity in sorted(group):
        row = rowmap.get(identity)
        occurrence = by_identity.get(identity)
        if not row or not occurrence or not row.get("geometry_sha256"):
            continue
        geom = wkb.loads(inv["payloads"][row["geometry_sha256"]])
        if not envelope.covers(box(*geom.bounds)):
            continue
        if identity == seed or row["kind"] in ("segment", "arc"):
            identities.append(identity)
    if seed not in identities:
        raise ValueError(f"SEED_OUTSIDE_EDIT_ALLOWLIST:member-{ordinal}")
    traces = [x for x in identities if x != seed]
    if not traces:
        raise ValueError(f"NO_LOCAL_TRACE_OBJECTS:member-{ordinal}")
    return {"seed": seed, "trace_ids": traces, "all_ids": identities,
            "member_key": member["member_key"], "window": window, "envelope": envelope,
            "group_ids": group, "target_map_member": tm}


def _blend_point(selection, inv, raw):
    seed_row = next(r for r in inv["objects"] if r["id"] == selection["seed"])
    a, b = seed_row["source_span"]
    seed_node = __import__("sexpdata").loads(raw[a:b].decode("utf-8"))
    center = _point(seed_node, "center")
    endpoint = _point(seed_node, "end")
    radius = math.dist(center, endpoint)
    circle = Point(center).buffer(radius, quad_segs=96)
    candidates = []
    for identity in selection["trace_ids"]:
        row = next(r for r in inv["objects"] if r["id"] == identity)
        a, b = row["source_span"]
        node = __import__("sexpdata").loads(raw[a:b].decode("utf-8"))
        start, end = _point(node, "start"), _point(node, "end")
        if row["kind"] == "segment":
            line = __import__("shapely").geometry.LineString([start, end])
        else:
            from src.native_inventory import arc_points
            line = __import__("shapely").geometry.LineString(arc_points(start, _point(node, "mid"), end))
        cross = line.intersection(circle.boundary)
        points = list(cross.geoms) if hasattr(cross, "geoms") else [cross]
        pts = [p for p in points if not p.is_empty and p.geom_type == "Point"]
        if pts:
            candidates.append((min(math.dist(center, p.coords[0]) for p in pts), identity, pts[0].coords[0]))
    if not candidates:
        return None
    return min(candidates, key=lambda x: (x[0], x[1]))[2]


def _params(family, radius, width, blend):
    return {"family": family, "radius_growth_mm": radius,
            "attached_trace_width_increase_mm": width, "junction_blend_radius_mm": blend}


def _candidate_shapes(selection, inv, raw, params, factor=1.0):
    op_map = {}
    for identity in selection["all_ids"]:
        op_map[identity] = {"radius_delta_mm": 0.0, "width_delta_mm": 0.0}
    op_map[selection["seed"]]["radius_delta_mm"] = params["radius_growth_mm"] * factor
    for identity in selection["trace_ids"]:
        op_map[identity]["width_delta_mm"] = params["attached_trace_width_increase_mm"] * factor
    geometries = {}
    added = []
    rowmap = {r["id"]: r for r in inv["objects"]}
    for identity, ops in op_map.items():
        row = rowmap[identity]
        a, b = row["source_span"]
        old = wkb.loads(inv["payloads"][row["geometry_sha256"]])
        new = _geometry_for_change(row, raw[a:b], row["kind"],
                                   radius_delta=ops["radius_delta_mm"],
                                   width_delta=ops["width_delta_mm"])
        geometries[identity] = new
        delta = new.difference(old)
        if not delta.is_empty:
            added.append(delta)
    point = _blend_point(selection, inv, raw)
    blend_radius = params["junction_blend_radius_mm"] * factor
    blend_geom = Point(point).buffer(blend_radius, quad_segs=64) if point and blend_radius else None
    if blend_geom is not None:
        added.append(blend_geom)
    return op_map, geometries, blend_geom, point, unary_union(added) if added else None


def _safe_against_foreign(selection, inv, raw, params, factor=1.0):
    op_map, changed, blend_geom, blend_point, added = _candidate_shapes(selection, inv, raw, params, factor)
    if added is None:
        return True, {"reason": "NO_ADDED_GEOMETRY", "factor": factor}, (op_map, changed, blend_geom, blend_point)
    if not selection["envelope"].covers(box(*added.bounds)):
        return False, {"reason": "INFLUENCE_EXCEEDS_DECLARED_HALO", "factor": factor, "added_bounds_mm": list(added.bounds)}, (op_map, changed, blend_geom, blend_point)
    clip = box(*selection["window"])
    original_unsupported = []
    for row in inv["objects"]:
        if "F.Cu" not in row.get("layers", []) or row["id"] in selection["group_ids"]:
            continue
        if row.get("geometry_sha256"):
            geom = wkb.loads(inv["payloads"][row["geometry_sha256"]])
            if not geom.intersects(selection["envelope"]):
                continue
            if added.intersects(geom):
                return False, {"reason": "NEW_GEOMETRIC_CONTACT_TO_SEPARATE_ORG_COMPONENT",
                               "factor": factor, "obstacle_identity": row["id"]}, (op_map, changed, blend_geom, blend_point)
        elif row.get("coverage") != "GEOMETRY_AVAILABLE":
            original_unsupported.append(row["id"])
    if original_unsupported:
        return False, {"reason": "UNSUPPORTED_NEIGHBOR_CONTEXT", "factor": factor,
                       "unsupported_occurrences": original_unsupported}, (op_map, changed, blend_geom, blend_point)
    return True, {"reason": "NO_NEW_SEPARATE_COMPONENT_CONTACT", "factor": factor}, (op_map, changed, blend_geom, blend_point)


def _member_score(selection, inv, target_inv, raw, target_raw, params, factor=1.0):
    op_map, changed_shapes, blend_geom, blend_point, _added = _candidate_shapes(selection, inv, raw, params, factor)
    records, _ = _load_geometry_objects(raw, inv, selection["window"])
    clip = box(*selection["window"])
    pieces = []
    rowmap = {r["id"]: r for r in inv["objects"]}
    for row, geom in records:
        use = changed_shapes.get(row["id"], geom)
        if use.intersects(clip):
            pieces.append(use.intersection(clip))
    if blend_geom is not None and blend_geom.intersects(clip):
        pieces.append(blend_geom.intersection(clip))
    candidate_region = unary_union(pieces) if pieces else clip.difference(clip)
    target_records, _ = _load_geometry_objects(target_raw, target_inv, selection["window"])
    target_region = unary_union([g.intersection(clip) for _, g in target_records]) if target_records else clip.difference(clip)
    sym = candidate_region.symmetric_difference(target_region)
    coverage = "SUPPORTED_SUBSET_ONLY" if selection["target_map_member"]["local_copper_region"]["status"] == "NOT_ESTABLISHED" else "COMPLETE_FOR_FIXED_WINDOW_GEOMETRY"
    seed_row = next(row for row in inv["objects"] if row["id"] == selection["seed"])
    seed_start, seed_end = seed_row["source_span"]
    seed_node = __import__("sexpdata").loads(raw[seed_start:seed_end].decode("utf-8"))
    source_radius = math.dist(_point(seed_node, "center"), _point(seed_node, "end"))
    candidate_radius = source_radius + params["radius_growth_mm"] * factor
    seed_alternatives = selection["target_map_member"]["seed"].get("edit_candidates", [])
    circle_radius_errors = [{"edit_identity": x["identity"], "edit_radius_mm": x["radius_mm"],
                             "absolute_radius_error_mm": abs(candidate_radius - x["radius_mm"])}
                            for x in seed_alternatives]
    trace_width_errors = []
    for relation in selection["target_map_member"]["trace_correspondence"].get("relations", []):
        for edge in relation.get("candidate_edges", []):
            if edge.get("before_identity") not in selection["trace_ids"]:
                continue
            trace_row = next((r for r in inv["objects"] if r["id"] == edge["before_identity"]), None)
            if trace_row is None:
                continue
            ts, te = trace_row["source_span"]
            trace_node = __import__("sexpdata").loads(raw[ts:te].decode("utf-8"))
            source_width_form = _named(trace_node, "width")
            source_width = float(source_width_form[1]) if source_width_form else None
            if source_width is None or edge.get("after_width_mm") is None:
                continue
            candidate_width = source_width + params["attached_trace_width_increase_mm"] * factor
            trace_width_errors.append({"org_identity": edge["before_identity"],
                                       "edit_identities": relation.get("after_identities", []),
                                       "org_width_mm": source_width, "candidate_width_mm": candidate_width,
                                       "edit_width_mm": edge["after_width_mm"],
                                       "absolute_width_error_mm": abs(candidate_width - edge["after_width_mm"])})
    try:
        boundary_error = candidate_region.boundary.hausdorff_distance(target_region.boundary)
    except Exception:
        boundary_error = None
    return {"candidate_window_union_area_mm2": candidate_region.area,
            "target_supported_window_union_area_mm2": target_region.area,
            "candidate_window_union_perimeter_mm": candidate_region.length,
            "target_supported_window_union_perimeter_mm": target_region.length,
            "symmetric_difference_area_mm2": sym.area,
            "union_area_error_envelope_mm2": (candidate_region.length + target_region.length) * inv["geometry_error_mm"] + 2 * math.pi * inv["geometry_error_mm"]**2,
            "added_area_mm2": candidate_region.difference(target_region).area,
            "removed_area_mm2": target_region.difference(candidate_region).area,
            "boundary_hausdorff_mm": boundary_error,
            "target_coverage": coverage,
            "target_fit_claim": "NOT_ESTABLISHED" if coverage != "COMPLETE_FOR_FIXED_WINDOW_GEOMETRY" else "MEASURED_SUPPORTED_TARGET",
            "candidate_geometry_sha256": digest_bytes(wkb.dumps(candidate_region)),
            "target_supported_geometry_sha256": digest_bytes(wkb.dumps(target_region)),
            "source_object_counts_are_not_used_as_fit_metric": True,
            "terminal_radius_fit": {"candidate_radius_mm": candidate_radius,
                                    "all_edit_alternatives": circle_radius_errors,
                                    "status": "MEASURED" if circle_radius_errors else "NOT_ESTABLISHED"},
            "uniquely_matched_trace_width_fit": {"measurements": trace_width_errors,
                                                   "minimum_absolute_error_mm": min((x["absolute_width_error_mm"] for x in trace_width_errors), default=None),
                                                   "status": "PARTIAL_GEOMETRIC_CORRESPONDENCE" if trace_width_errors else "UNMATCHED"},
            "blend_point_org_mm": list(blend_point) if blend_point else None,
            "editable_occurrence_count": len(op_map)}


def _candidate_grid():
    candidates = []
    for r, w in itertools.product(R1, W1):
        candidates.append(_params("selective_land_neck", r, w, 0.0))
    for r, w, b in itertools.product(R2, W2, B2):
        candidates.append(_params("junction_blended", r, w, b))
    for r, w, b in itertools.product(R3, W3, B3):
        candidates.append(_params("neighbor_constrained", r, w, b))
    if len(candidates) > 64:
        raise ValueError("FROZEN_CANDIDATE_BUDGET_EXCEEDED")
    return candidates


def _select_with_indifference(valid, geometry_error_mm, boundary_error_mm):
    """Sequential tolerance-aware lexicographic filter; unavailable never means zero."""
    survivors = list(valid)
    steps = []
    specs = [
        ("terminal_radius_abs_error_mm",
         lambda t: min((x["absolute_radius_error_mm"] for x in t["metrics"]["terminal_radius_fit"]["all_edit_alternatives"]), default=None),
         geometry_error_mm),
        ("uniquely_matched_trace_width_abs_error_mm",
         lambda t: t["metrics"]["uniquely_matched_trace_width_fit"]["minimum_absolute_error_mm"], geometry_error_mm),
        ("union_symmetric_difference_area_mm2",
         lambda t: t["metrics"]["symmetric_difference_area_mm2"],
         lambda t: t["metrics"]["union_area_error_envelope_mm2"]),
        ("boundary_hausdorff_mm", lambda t: t["metrics"]["boundary_hausdorff_mm"], boundary_error_mm),
    ]
    for name, value_of, tolerance_of in specs:
        measured = [(row, value_of(row)) for row in survivors]
        measured = [(row, value) for row, value in measured if value is not None and math.isfinite(value)]
        if not measured:
            steps.append({"metric": name, "status": "UNAVAILABLE", "candidate_count_unchanged": len(survivors),
                          "rule": "Missing measurements are unavailable, never zero; continue only under this frozen policy."})
            continue
        best_value = min(value for _, value in measured)
        best_row = next(row for row, value in measured if value == best_value)
        best_tol = tolerance_of(best_row) if callable(tolerance_of) else tolerance_of
        previous_count = len(survivors)
        survivors = [row for row, value in measured
                     if value <= best_value + max(float(tolerance_of(row) if callable(tolerance_of) else tolerance_of), float(best_tol))]
        steps.append({"metric": name, "status": "MEASURED", "best_value": best_value,
                      "indifference_tolerance": best_tol, "candidate_count_before": previous_count,
                      "candidate_count_after": len(survivors)})
        if len(survivors) <= 1:
            break
    if not survivors:
        raise ValueError("TOLERANCE_AWARE_SELECTION_DROPPED_ALL_CANDIDATES")
    family_complexity = {"selective_land_neck": 0, "junction_blended": 1, "neighbor_constrained": 2}
    selected = min(survivors, key=lambda t: (family_complexity.get(t["params"]["family"], len(family_complexity)), t["params"]["radius_growth_mm"],
                                              t["params"]["attached_trace_width_increase_mm"],
                                              t["params"]["junction_blend_radius_mm"], t["candidate_index"]))
    return selected, steps, len(survivors)


def run():
    contract_path, contract = latest_contract()
    target_map = json.loads(TARGET_MAP.read_text())
    org_raw, edit_raw = ORG_PATH.read_bytes(), EDIT_PATH.read_bytes()
    org_hash, edit_hash = digest_bytes(org_raw), digest_bytes(edit_raw)
    if org_hash != contract["sources"]["ORG"]["sha256"] or edit_hash != contract["sources"]["EDIT"]["sha256"]:
        raise ValueError("PINNED_G22_SOURCE_DRIFT")
    org_inv, edit_inv = inventory(org_raw), inventory(edit_raw)
    selections = [_selection(contract, target_map, i, org_inv, org_raw) for i in (1, 2, 3)]
    candidates = _candidate_grid()
    trials, ordinal = [], 0
    for family in ("selective_land_neck", "junction_blended", "neighbor_constrained"):
        family_rows = [(i, p) for i, p in enumerate(candidates, 1) if p["family"] == family]
        for i, params in family_rows:
            ordinal += 1
            selection_a = selections[0]
            factor = 1.0
            safe, reason, built = _safe_against_foreign(selection_a, org_inv, org_raw, params, 1.0)
            if family == "neighbor_constrained" and not safe:
                lo, hi = 0.0, 1.0
                for _ in range(18):
                    mid = (lo + hi) / 2
                    ok, _, _ = _safe_against_foreign(selection_a, org_inv, org_raw, params, mid)
                    if ok:
                        lo = mid
                    else:
                        hi = mid
                factor = lo
                safe, reason, built = _safe_against_foreign(selection_a, org_inv, org_raw, params, factor)
            if safe:
                metrics = _member_score(selection_a, org_inv, edit_inv, org_raw, edit_raw, params, factor)
                status = "EVALUATED"
            else:
                metrics = None
                status = "REJECTED"
            trials.append({"candidate_index": ordinal, "candidate_key": f"{family}-{ordinal:03d}",
                           "params": params, "calibration_member": "A", "factor": factor,
                           "status": status, "eligibility": reason, "metrics": metrics,
                           "budget_slot_consumed": True})
    valid = [t for t in trials if t["status"] == "EVALUATED" and t["metrics"]["target_coverage"] == "COMPLETE_FOR_FIXED_WINDOW_GEOMETRY"]
    if not valid:
        selected = None
        fit_status = "NO_VALID_CANDIDATE_WITHIN_SEARCH_BUDGET"
        selection_steps, selection_tied_count = [], 0
    else:
        indifference = contract["experiment_policy"]["numerical_indifference"]
        selected, selection_steps, selection_tied_count = _select_with_indifference(
            valid, indifference["terminal_radius_abs_error_mm"],
            indifference["boundary_hausdorff_mm"])
        fit_status = "BEST_WITHIN_DECLARED_SEARCH_SPACE"
    transfer, native_candidates = [], {}
    if selected:
        for selection, ordinal_i in zip(selections, (1, 2, 3)):
            params = selected["params"]
            factor = selected["factor"] if params["family"] != "neighbor_constrained" else 1.0
            # The neighbor rule is deterministic and may cap a shared nominal request differently by local obstacles.
            if params["family"] == "neighbor_constrained":
                lo, hi = 0.0, 1.0
                for _ in range(18):
                    mid = (lo + hi) / 2
                    ok, _, _ = _safe_against_foreign(selection, org_inv, org_raw, params, mid)
                    if ok:
                        lo = mid
                    else:
                        hi = mid
                factor = lo
            ok, reason, built = _safe_against_foreign(selection, org_inv, org_raw, params, factor)
            if not ok:
                transfer.append({"member": ordinal_i, "status": "REJECTED_BY_FROZEN_INVARIANT", "reason": reason})
                continue
            op_map, changed_shapes, blend_geom, blend_point = built[0], built[1], built[2], built[3]
            point = _blend_point(selection, org_inv, org_raw)
            blends = [(point, params["junction_blend_radius_mm"] * factor)] if point and params["junction_blend_radius_mm"] * factor > 0 else []
            candidate_bytes, receipt = generate_org_candidate(org_raw, org_hash, op_map,
                                                               blend_points=blends, member_key=selection["member_key"])
            candidate_inv = inventory(candidate_bytes)
            score = _member_score(selection, org_inv, edit_inv, org_raw, edit_raw, params, factor)
            code_hash = digest_bytes(Path(__file__).read_bytes())
            run_key = hashlib.sha256((contract_path.name + selected["candidate_key"] + org_hash + edit_hash + code_hash).encode()).hexdigest()[:16]
            run_dir = ROOT / "out/g22_family_reconstruction/slice_b" / f"run-{run_key}"
            board_path = run_dir / "candidates" / f"member-{ordinal_i}" / "top.kicad_pcb"
            board_path.parent.mkdir(parents=True, exist_ok=True)
            if board_path.exists() and digest_bytes(board_path.read_bytes()) != digest_bytes(candidate_bytes):
                raise ValueError("IMMUTABLE_CANDIDATE_COLLISION")
            if not board_path.exists():
                board_path.write_bytes(candidate_bytes)
            transfer.append({"member": ordinal_i, "member_key": selection["member_key"],
                             "status": "GENERATED_NOT_EXPORTED", "parameters_shared": params,
                             "constraint_factor": factor, "neighbor_rule": reason,
                             "source_occurrence_operations": receipt["editable_source_occurrences"],
                             "candidate_receipt": receipt, "candidate_board_path": str(board_path.relative_to(ROOT)),
                             "candidate_board_sha256": digest_bytes(candidate_bytes),
                             "predicted_supported_geometry": score,
                             "candidate_inventory_source_objects": candidate_inv["source_objects"],
                             "edit_candidate_alternatives_retained": selection["target_map_member"]["seed"].get("edit_candidates", []),
                             "target_composition_status": selection["target_map_member"]["local_copper_region"]["status"],
                             "whole_target_fit_status": "NOT_ESTABLISHED" if score["target_coverage"] != "COMPLETE_FOR_FIXED_WINDOW_GEOMETRY" else "MEASURED"})
    code_hash = digest_bytes(Path(__file__).read_bytes())
    run_key = hashlib.sha256((contract_path.name + (selected["candidate_key"] if selected else "none") + org_hash + edit_hash + code_hash).encode()).hexdigest()[:16]
    run_dir = ROOT / "out/g22_family_reconstruction/slice_b" / f"run-{run_key}"
    run_dir.mkdir(parents=True, exist_ok=True)
    report = {"schema": "g22-org-fit-search/1", "run_id": run_key,
              "status": fit_status, "inputs": {"contract": str(contract_path.relative_to(ROOT)), "contract_sha256": sha(contract_path),
                                                  "target_map": str(TARGET_MAP.relative_to(ROOT)), "target_map_sha256": sha(TARGET_MAP),
                                                  "ORG_sha256": org_hash, "EDIT_sha256": edit_hash},
              "hypothesis": "Can these compact ORG-derived geometric transformations approximate observed supported EDIT geometry in the fixed windows? Does not recover expert intent or manufacturing rationale.",
              "candidate_budget": {"max": 64, "generated": len(trials),
                                   "evaluated": sum(t["status"] == "EVALUATED" for t in trials),
                                   "rejected": sum(t["status"] == "REJECTED" for t in trials),
                                   "unobservable": 0, "remaining": 64-len(trials)},
              "selection_rule": contract["experiment_policy"]["selection_rule"],
              "selection_steps": selection_steps,
              "final_indifference_tie_count": selection_tied_count,
              "grid": {"families": ["selective_land_neck", "junction_blended", "neighbor_constrained"],
                       "family_counts": {name: sum(t["params"]["family"] == name for t in trials) for name in ("selective_land_neck", "junction_blended", "neighbor_constrained")},
                       "parameter_values": {"radius_growth_mm": {"selective_land_neck": R1, "junction_blended": R2, "neighbor_constrained": R3},
                                            "trace_width_increase_mm": {"selective_land_neck": W1, "junction_blended": W2, "neighbor_constrained": W3},
                                            "blend_radius_mm": {"selective_land_neck": [0.0], "junction_blended": B2, "neighbor_constrained": B3}},
                       "treatment_parameters_are_experimental_assumptions": True},
              "null_model": next((t for t in trials if all(p == 0 for p in (t["params"]["radius_growth_mm"], t["params"]["attached_trace_width_increase_mm"], t["params"]["junction_blend_radius_mm"]))), None),
              "selected": selected, "trials": trials, "transfer": transfer,
              "interpretation_limits": {"target_informed_calibration": "in-sample on A", "transfer": "non-retuned, not blind holdout",
                                         "B": "both same-center EDIT candidates retained; geometric scoring does not establish identity",
                                         "C": "supported-subset comparison only; complete target and whole-window fit remain NOT_ESTABLISHED",
                                         "electrical": "NOT_ESTABLISHED", "manufacturing": "NOT_ESTABLISHED"}}
    report_path = run_dir / "fit_report.json"
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if report_path.exists() and report_path.read_text() != payload:
        raise ValueError("IMMUTABLE_FIT_REPORT_COLLISION")
    if not report_path.exists():
        report_path.write_text(payload)
    print(json.dumps({"status": report["status"], "run_dir": str(run_dir.relative_to(ROOT)),
                      "candidate_budget": report["candidate_budget"],
                      "selected": report["selected"]["candidate_key"] if report["selected"] else None,
                      "selected_params": report["selected"]["params"] if report["selected"] else None,
                      "A_symdiff_mm2": report["selected"]["metrics"]["symmetric_difference_area_mm2"] if report["selected"] else None,
                      "transfer_statuses": [x["status"] for x in report["transfer"]]}, indent=2))
    return report


if __name__ == "__main__":
    run()
