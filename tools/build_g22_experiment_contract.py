#!/usr/bin/env python3
"""Freeze source-bound G22 experiment scope and effective-geometry coverage."""
from __future__ import annotations

import hashlib
import json
import importlib.metadata
import importlib.metadata
import platform
import sys
from pathlib import Path

from shapely import wkb
from shapely.geometry import box
from shapely.ops import unary_union
import sexpdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ingestion_files import sha  # noqa: E402
from src.native_inventory import inventory  # noqa: E402

TARGET = ROOT / "out/ingestion/audits/20261024_g22_org_edit_target_map_v1/target_map.json"
PROFILE = ROOT / "out/ingestion/audits/20261024_g22_reference_region_profile_v1/profile.json"
REGISTRATION = ROOT / "out/ingestion/audits/20261023_registered_copper_correspondence_v1/evidence/registration.json"
DECISION = ROOT / "out/ingestion/audits/20261024_org_and_screenshot_mapping_v1/g22_human_review/OWNER_REVIEW_DECISION_20261024.md"
DECISION_SUM = DECISION.with_name("SHA256SUMS.owner-review-decision")
PACKAGE = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v1"
ORG = PACKAGE / "raw/ORG/top.kicad_pcb"
EDIT = PACKAGE / "raw/EDIT/top_layer.kicad_pcb"
OUT = ROOT / "out/g22_family_reconstruction/slice_a"
HALO_MM = 0.075  # EXPERIMENT_ASSUMPTION: bounds the initial 0.05 mm maximum growth plus kernel margin.


def load(path: Path):
    return json.loads(path.read_text())


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_decision():
    expected = {}
    for line in DECISION_SUM.read_text().splitlines():
        digest, _, rel = line.partition("  ")
        expected[rel] = digest
    actual = sha(DECISION)
    if expected.get(DECISION.name) != actual:
        raise ValueError("OWNER_REVIEW_DECISION_HASH_MISMATCH")
    text = DECISION.read_text()
    if "Decision: `SUPPORTED`" not in text or "bounded G22 crop-neighborhood visual review" not in text:
        raise ValueError("OWNER_REVIEW_DECISION_SCOPE_MISMATCH")
    return {"status": "VERIFIED", "path": str(DECISION.relative_to(ROOT)), "sha256": actual,
            "meaning": "SUPPORTED only for bounded crop-neighborhood visual review"}


def package_status():
    sums = PACKAGE / "SHA256SUMS"
    expected = {}
    for line in sums.read_text().splitlines():
        digest, sep, rel = line.partition("  ")
        if not sep:
            raise ValueError("INVALID_PACKAGE_MANIFEST")
        expected[rel] = digest
    actual = {p.relative_to(PACKAGE).as_posix(): sha(p) for p in PACKAGE.rglob("*") if p.is_file() and p != sums}
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(k for k in set(expected) & set(actual) if expected[k] != actual[k])
    board_ok = {"ORG": expected.get("raw/ORG/top.kicad_pcb") == actual.get("raw/ORG/top.kicad_pcb"),
                "EDIT": expected.get("raw/EDIT/top_layer.kicad_pcb") == actual.get("raw/EDIT/top_layer.kicad_pcb")}
    if not all(board_ok.values()):
        raise ValueError("REGISTERED_BOARD_SOURCE_DRIFT")
    return {"status": "MISMATCH" if missing or extra or changed else "PASS",
            "manifest_sha256": sha(sums), "expected_files": len(expected),
            "missing": missing, "extra": extra, "changed": changed,
            "registered_board_inputs_match_manifest": board_ok,
            "policy": "Preserve aggregate MISMATCH; only separately verified registered board bytes may enter this research run."}


def inventory_coverage(path: Path, expected_hash: str, windows: list[list[float]]):
    raw = path.read_bytes()
    if sha_bytes(raw) != expected_hash:
        raise ValueError(f"SOURCE_HASH_MISMATCH:{path}")
    inv = inventory(raw)
    rows = []
    for member_index, win in enumerate(windows, 1):
        x0, y0, x1, y1 = win
        search = box(x0 - HALO_MM, y0 - HALO_MM, x1 + HALO_MM, y1 + HALO_MM)
        touched = []
        unsupported = []
        window_copper_geometries = []
        semantic_counts = {}
        for row in inv["objects"]:
            if "F.Cu" not in row.get("layers", []):
                continue
            geom = wkb.loads(inv["payloads"][row["geometry_sha256"]]) if row.get("geometry_sha256") else None
            if geom is not None and geom.intersects(search):
                source_node = sexpdata.loads(raw[row["source_span"][0]:row["source_span"][1]].decode("utf-8"))
                fill_form = next((x for x in source_node if isinstance(x, list) and str(x[0]) == "fill"), None)
                fill_token = str(fill_form[1]) if fill_form and len(fill_form) > 1 else "UNDECLARED"
                geometry_semantics = "FILLED_AREA" if fill_token in ("yes", "solid") else "STROKED_OR_BOUNDARY" if row["kind"] in ("segment", "arc", "gr_line", "gr_arc") else "OUTLINE_OR_UNFILLED"
                semantic_counts[geometry_semantics] = semantic_counts.get(geometry_semantics, 0) + 1
                fixed = box(x0, y0, x1, y1)
                touched.append({"identity": row["id"], "kind": row["kind"],
                                "source_span": row["source_span"], "coverage": row["coverage"],
                                "geometry_sha256": row["geometry_sha256"],
                                "bounds_mm": list(geom.bounds), "fill_token": fill_token,
                                "measurement_semantics": geometry_semantics,
                                "crosses_fixed_window_boundary": bool(geom.intersects(fixed.boundary)),
                                "relation": "INTERSECTS_FIXED_WINDOW_PLUS_HALO"})
                if geom.intersects(fixed):
                    window_copper_geometries.append(geom.intersection(fixed))
            elif geom is None and row.get("coverage") != "GEOMETRY_AVAILABLE":
                # Conservatively bound unsupported occurrences from their exact source bytes.
                start, end = row["source_span"]
                node = sexpdata.loads(raw[start:end].decode("utf-8"))
                pts, stack = [], [node]
                while stack:
                    item = stack.pop()
                    if isinstance(item, list):
                        if len(item) >= 3 and str(item[0]) in ("start", "mid", "end", "center", "xy"):
                            try:
                                pts.append((float(item[1]), float(item[2])))
                            except (TypeError, ValueError):
                                pass
                        stack.extend(v for v in item if isinstance(v, list))
                bounds = None
                if pts:
                    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                    width_forms = [x for x in node if isinstance(x, list) and str(x[0]) == "width"]
                    pad = float(width_forms[0][1]) / 2 if width_forms else 0.0
                    if row["kind"] in ("arc", "gr_arc", "fp_arc"):
                        center_forms = [x for x in node if isinstance(x, list) and str(x[0]) == "center"]
                        if center_forms:
                            cx, cy = float(center_forms[0][1]), float(center_forms[0][2])
                            radius = max(((x-cx)**2 + (y-cy)**2)**0.5 for x, y in pts)
                            bounds = [cx-radius-pad, cy-radius-pad, cx+radius+pad, cy+radius+pad]
                    if bounds is None:
                        bounds = [min(xs)-pad, min(ys)-pad, max(xs)+pad, max(ys)+pad]
                if bounds and search.intersects(box(*bounds)):
                    unsupported.append({"identity": row["id"], "kind": row["kind"],
                                        "source_span": row["source_span"],
                                        "reason": row.get("unsupported_reason"),
                                        "bounds_mm": bounds})
        window_union = unary_union(window_copper_geometries) if window_copper_geometries else None
        rows.append({"member_ordinal": member_index, "fixed_window_mm": win,
                     "safety_halo_mm": HALO_MM, "effective_geometry_occurrences": touched,
                     "effective_geometry_count": len(touched), "unsupported_with_intersecting_bounds": unsupported,
                     "unsupported_count": len(unsupported),
                     "source_semantics_count": semantic_counts,
                     "supported_window_union_area_mm2": window_union.area if window_union else 0.0,
                     "supported_window_union_sha256": sha_bytes(wkb.dumps(window_union)) if window_union else None,
                     "coverage_rule": "Every effective F.Cu object whose full geometry intersects fixed window expanded by safety halo is retained by exact source occurrence; crossing primitives included regardless of endpoints."})
    return {"source_sha256": expected_hash, "inventory_version": inv["version"],
            "units": inv["units"], "coordinates": inv["coordinates"],
            "geometry_error_mm": inv["geometry_error_mm"],
            "per_curve_approximation_error_mm": inv["per_curve_approximation_error_mm"],
            "source_objects": inv["source_objects"], "geometry_available": inv["geometry_available"],
            "unsupported_reasons": inv["unsupported_reasons"], "members": rows}


def build():
    target = load(TARGET)
    profile = load(PROFILE)
    registration = load(REGISTRATION)
    if target["family_key"] != "cdca145fddd555c55a8cdd3b94d08fa4546738a9228e4d20cbaa295881ac7d53":
        raise ValueError("FAMILY_KEY_DRIFT")
    if len(target["members"]) != 3 or target["registration"]["fitted_after_to_before"] != registration.get("fitted_after_to_before"):
        raise ValueError("PINNED_MEMBER_OR_TRANSFORM_DRIFT")
    pkg = package_status()
    if pkg["status"] != target["package_integrity"]["status"]:
        raise ValueError("PACKAGE_STATUS_DRIFT")
    windows = [m["window_mm"] for m in target["members"]]
    org = inventory_coverage(ORG, target["sources"]["ORG"]["sha256"], windows)
    edit = inventory_coverage(EDIT, target["sources"]["EDIT"]["sha256"], windows)
    regions = []
    org_coverage_by_ordinal = {m["member_ordinal"]: m for m in org["members"]}
    for member, prof_member, target_member, edit_cov in zip(target["members"], profile["family"]["members"], target["members"], edit["members"]):
        exact_component_ids = member["physical_contact_group"]["org"]["source_member_ids"]
        coverage_ids = {o["identity"] for o in org_coverage_by_ordinal[member["ordinal"]]["effective_geometry_occurrences"]}
        outside_halo = sorted(set(exact_component_ids) - coverage_ids)
        unsupported_local = edit_cov["unsupported_with_intersecting_bounds"]
        observable_status = "SUPPORTED_SUBSET_ONLY" if unsupported_local else "COMPLETE_FOR_FIXED_WINDOW_GEOMETRY"
        regions.append({"ordinal": member["ordinal"], "member_key": member["member_key"],
                        "center_org_mm": member["center_org_mm"], "window_mm": member["window_mm"],
                        "record_correspondence": {"seed": target_member["seed"]["edit_status"],
                                                  "all_edit_seed_candidates": target_member["seed"].get("edit_candidates", []),
                                                  "trace": target_member["trace_correspondence"].get("relations", []),
                                                  "trace_unmatched": target_member["trace_correspondence"].get("by_org_trace", {})},
                        "target_composition_status": target_member["local_copper_region"]["status"],
                        "target_unsupported_edit": target_member["local_copper_region"].get("unsupported_edit", []),
                        "unsupported_edit_occurrences_in_window_plus_halo": unsupported_local,
                        "measurement_coverage": {"supported_union_area": observable_status,
                                                 "boundary_metrics": "ONLY_INTERNAL_BOUNDARIES_AFTER_EXCLUDING_WINDOW_CLIP_EDGES",
                                                 "neighbor_clearance": "COMPLETE_ONLY_WHEN_FULL_BOARD_LOCAL_SUPPORT_WITHIN_CANDIDATE_INFLUENCE_RADIUS_IS_SUPPORTED_OR_CONSERVATIVELY_BOUNDED",
                                                 "unsupported_effect_rule": "If an unsupported feature can influence a metric, that metric is NOT_ESTABLISHED; it is never treated as empty geometry."},
                        "profile_context": prof_member.get("context", {}),
                        "context_unknowns": {k: v.get("status_by_object", "UNKNOWN")
                                             for k, v in profile["region_context_summary"].items()},
                        "physical_contact_group_source_ids": exact_component_ids,
                        "initial_editable_seed_identity": member["seed"]["org_identity"],
                        "candidate_specific_component_allowlist_must_be_subset_of_covered_occurrences": True,
                        "component_occurrences_outside_window_plus_halo": outside_halo})
    window_shapes = [box(*w) for w in windows]
    overlap_areas = {}
    for i in range(3):
        for j in range(i + 1, 3):
            area = window_shapes[i].intersection(window_shapes[j]).area
            overlap_areas[f"{i+1}-{j+1}"] = area
    unique_window_area = unary_union(window_shapes).area
    result = {
        "schema": "g22-family-experiment-contract/1", "slice": "A",
        "status": "LOCKED_FOR_BOUNDED_EXPERIMENT" if not any(m["unsupported_count"] for m in org["members"]) else "LOCKED_WITH_EXPLICIT_COVERAGE_LIMITS",
        "sources": {"target_map": {"path": str(TARGET.relative_to(ROOT)), "sha256": sha(TARGET)},
                    "profile": {"path": str(PROFILE.relative_to(ROOT)), "sha256": sha(PROFILE)},
                    "registration": {"path": str(REGISTRATION.relative_to(ROOT)), "sha256": sha(REGISTRATION)},
                    "ORG": {"path": str(ORG.relative_to(ROOT)), "sha256": sha(ORG)},
                    "EDIT": {"path": str(EDIT.relative_to(ROOT)), "sha256": sha(EDIT)}},
        "family_key": target["family_key"], "member_keys": target["member_keys"],
        "owner_visual_decision": verify_decision(), "sealed_package": pkg,
        "coordinate_frame": "ORG KiCad board coordinates; X right, Y down; EDIT identity transform from pinned F.Mask-only registration; no local recentering.",
        "coordinate_pipeline": {"source_coordinates": "KiCad board mm, X right/Y down",
                                "registration": "EDIT-to-ORG identity transform fitted only on F.Mask anchors",
                                "comparison_coordinates": "same absolute ORG millimetre frame; fixed windows, no member recentering",
                                "Gerber_coordinates": "expected X unchanged/Y sign inverted relative to KiCad plot coordinates; recorded candidate/export readers must explicitly apply the inverse before comparison",
                                "render_coordinates": "display-only Y inversion, never used for fitting or measurements"},
        "registration": target["registration"], "windows": windows,
        "window_overlap": {"pairwise_area_mm2": overlap_areas,
                           "unique_family_window_area_mm2": unique_window_area,
                           "warning": "Per-member values are not additive where windows overlap; family delta must use a geometric union and shared support attribution."},
        "safety_halo": {"value_mm": HALO_MM, "classification": "EXPERIMENT_ASSUMPTION",
                         "purpose": "covers initial candidate growth budget 0.05 mm plus 0.025 mm geometry/kernel margin; does not declare a design rule",
                         "qualification": "For each candidate predicate, calculate operation influence radius. The fixed-window plus halo must contain every full source geometry within that radius. If an operation exceeds the allowance or a source is unsupported, mark the affected measurement incomplete and reject its acceptance claim."},
        "org_effective_geometry_coverage": org,
        "edit_effective_geometry_coverage": edit,
        "member_target_qualification": regions,
        "editable_occurrences": "Candidate-specific allowlists are source occurrence IDs in member_target_qualification. The initial editable seed is explicit; any neck/junction operation may only add component members that lie in the fixed window plus halo, have supported geometry, and pass local relationship checks. Component membership is geometric only and grants no net or fabrication meaning.",
        "protected_occurrences": "All other source bytes and objects, all non-F.Cu layers, F.Mask geometry, board outline, and any F.Cu occurrences outside the candidate-specific allowlist.",
        "reference_roles": {"F.Mask": "pinned registration reference; preserve exact source and exported geometry; process interpretation remains UNKNOWN", "F.Paste": "not an editing target; no manufacturing interpretation inferred", "F.Cu": "artwork layer under experimental geometric treatment"},
        "geometry_kernel": {"inventory_version": org["inventory_version"], "geometry_error_mm": org["geometry_error_mm"],
                            "curve_approximation_error_mm": org["per_curve_approximation_error_mm"],
                            "rule": "Unsupported geometries remain explicit; they cannot be omitted from affected topology/clearance claims."},
        "experiment_policy": {"families_max": 3, "candidates_max": 64,
                               "budget_accounting": "Every generated parameter tuple consumes one of 64 slots, including invalid, rejected, and unobservable candidates; report generated/evaluated/rejected/unobservable counts and reasons.",
                               "calibration": "Member A; EDIT-derived low-dimensional fitting only, explicitly in-sample.",
                               "transfer": "Freeze selected A parameters and transfer without retuning to B and C; transfer is non-retuned, not blind holdout.",
                               "candidate_growth_max_mm": 0.05, "candidate_cutback_max_mm": 0.02,
                               "minimum_clearance_mm": 0.0, "minimum_neck_width_mm": 0.025,
                               "selection_rule": "Freeze before scoring: require research-invariant eligibility, then compare directly qualified terminal-radius error, uniquely matched attached-trace width error, supported-domain union symmetric-difference area, and boundary discrepancy in that lexicographic order. Within numerical indifference at all metrics, prefer the lower-complexity family in order selective_land_neck, junction_blended, neighbor_constrained, then smaller parameter magnitudes and lexicographic vector. Keep null model and every B alternative independent. Do not let union area compensate for a miss on the terminal or matched neck.",
                               "numerical_indifference": {"terminal_radius_abs_error_mm": org["geometry_error_mm"],
                                                          "uniquely_matched_trace_width_abs_error_mm": org["geometry_error_mm"],
                                                          "boundary_hausdorff_mm": 2 * org["per_curve_approximation_error_mm"] + target["registration"]["max_inlier_residual_mm"],
                                                          "union_symmetric_difference_area_mm2": "candidate_union_perimeter_mm * geometry_error_mm + target_union_perimeter_mm * geometry_error_mm + 2*pi*geometry_error_mm^2; calculated per candidate pair",
                                                          "comparison": "At each priority, treat values within the larger of the candidate and current-best error envelopes as tied, then advance to the next metric. Missing observations stay explicitly unavailable and are never set to zero; if an A-priority metric is unavailable, record that fact and advance only under this frozen policy."},
                               "classification": "EXPERIMENT_ASSUMPTION", "rationale": "bounded numerical guardrails for candidate safety only; no factory/process authority"},
        "fit_metrics": ["symmetric_difference_area_mm2", "added_and_removed_area_mm2", "boundary_hausdorff_mm_where_supported", "circle_radius_delta_mm", "trace_width_profiles_mm", "reference_relative_offsets_mm", "target_coverage_fraction"],
        "measurement_hierarchy": ["source-record occurrences with exact byte spans", "primitive effective-geometry interpretation and fill/stroke token", "per-member union of supported copper geometry after clipping to the fixed window", "overlap-aware family union; never sum per-object areas or per-window deltas as disjoint copper", "unsupported/conservatively retained occurrences listed separately and excluded only from explicitly supported-subset metrics"],
        "objective_guardrails": {"null_model": "unchanged ORG geometry under identical transform, clipping, union and scoring pipeline", "no_occurrence_count_objective": True, "B_alternatives": "score both recorded same-center EDIT circle alternatives independently; do not select identity by best candidate score", "C_incomplete_target": "no whole-target fit score or full-reproduction claim while any local unsupported target geometry can influence the comparison; only separately justified supported subdomains may be scored", "failed_search_claim": "NOT_FOUND_WITHIN_SEARCH_BUDGET, never proof that no explanation exists"},
        "boundary_and_precision_controls": {"window_clipping": "Record whether each contributing geometry crosses the fixed-window boundary. Do not interpret a clip edge as a physical endpoint.",
                                             "halo_vs_predicate": "Check the candidate-specific influence radius against 0.075 mm; outside-support influence marks the predicate unobservable.",
                                             "contact_semantics": "GEOS intersection is geometric contact only; never call it electrical continuity.",
                                             "tolerance_mm": {"native_geometry_error": org["geometry_error_mm"], "curve_approximation_error": org["per_curve_approximation_error_mm"], "registration_limit": target["registration"]["tolerance_mm"], "candidate_kernel_max_error": org["per_curve_approximation_error_mm"]},
                                             "area_error": "Compute an envelope from the measured union perimeter and declared boundary error (including the round-offset term); do not use one constant area epsilon for regions of different perimeter."},
        "technical_validity": ["exact source scope", "reference geometry unchanged", "locally observed port contacts preserved", "no newly introduced local disconnection or unsupported topology claim", "export fidelity", "deterministic replay"],
        "overall_authority": {"engineering": "NOT_ESTABLISHED", "electrical": "NOT_ESTABLISHED", "manufacturing": "NOT_ESTABLISHED", "independent_cursor": "NOT_RUN: CHANNEL_UNAVAILABLE"},
        "software": {"python": platform.python_version(), "platform": platform.platform(),
                     "packages": {name: importlib.metadata.version(name) for name in ("Shapely", "sexpdata", "gerbonara")}}}
    OUT.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    contract_digest = sha_bytes(payload.encode())
    out = OUT / f"experiment_contract_{contract_digest[:16]}.json"
    if out.exists() and out.read_text() != payload:
        raise ValueError("IMMUTABLE_SLICE_A_RECEIPT_COLLISION")
    if not out.exists():
        out.write_text(payload)
    return result, out


if __name__ == "__main__":
    contract, path = build()
    print(json.dumps({"status": contract["status"], "contract": str(path.relative_to(ROOT)),
                      "org_coverage": [m["effective_geometry_count"] for m in contract["org_effective_geometry_coverage"]["members"]],
                      "edit_coverage": [m["effective_geometry_count"] for m in contract["edit_effective_geometry_coverage"]["members"]],
                      "package": contract["sealed_package"]["status"],
                      "unsupported_org": [m["unsupported_count"] for m in contract["org_effective_geometry_coverage"]["members"]]}, indent=2))
