#!/usr/bin/env python3
"""Read-only observational comparison of ORG rectangle candidates with EDIT.

EDIT geometries are used only to describe observed changes. The report is not a
construction input, and the proximity association is explicitly provisional.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

from shapely import affinity, wkb
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.crop_rect_t02 import rectangular_feature
from src.native_inventory import inventory


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def center(geom):
    point = geom.centroid
    return [float(point.x), float(point.y)]


def dims(geom):
    minx, miny, maxx, maxy = geom.bounds
    return [float(maxx - minx), float(maxy - miny)]


def local_dims(geom, angle):
    return dims(affinity.rotate(geom, -math.degrees(angle), origin="centroid"))


def run(output_rel: str = "out/crop_dynamic_tasks/t02_rect_observation_20261025"):
    policy_path = ROOT / "contracts/crop_rect_t02_policy.json"
    policy_raw = policy_path.read_bytes()
    policy = json.loads(policy_raw)
    org_path = ROOT / policy["source"]
    edit_path = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/EDIT/top_layer.kicad_pcb"
    org_raw, edit_raw = org_path.read_bytes(), edit_path.read_bytes()
    org_hash, edit_hash = sha(org_raw), sha(edit_raw)
    if org_hash != policy["source_sha256"]:
        raise SystemExit("ORG_SOURCE_HASH_MISMATCH")
    reg_path = ROOT / "out/crop_dynamic_tasks/t02_crop_registration_20261024/registration.json"
    registration = json.loads(reg_path.read_text())
    transform = registration.get("fitted_after_to_before", {})
    if (abs(float(transform.get("rotation_radians", math.inf))) > 1e-12 or
            any(abs(float(v)) > 1e-12 for v in transform.get("translation_mm", [math.inf, math.inf]))):
        raise SystemExit("OBSERVATION_REQUIRES_REGISTERED_TRANSFORM_IMPLEMENTATION")

    crop = box(*map(float, policy["crop_bounds_org_mm"]))
    org_inv, edit_inv = inventory(org_raw), inventory(edit_raw)
    org_rects = []
    org_rect_ids = set()
    for row in org_inv["objects"]:
        if row.get("kind") != "gr_poly" or "F.Cu" not in row.get("layers", []):
            continue
        geom_data = org_inv["payloads"].get(row.get("geometry_sha256"))
        if not geom_data:
            continue
        geom = wkb.loads(geom_data)
        if not geom.intersects(crop):
            continue
        rect = rectangular_feature(row, org_inv["payloads"], crop)
        if rect:
            org_rects.append({"row": row, "geom": geom, "rect": rect})
            org_rect_ids.add(row["id"])
    if len(org_rects) != 81:
        raise SystemExit(f"ORG_RECTANGLE_COUNT_CHANGED:{len(org_rects)}")

    edit_polys = []
    edit_fcu_counts = Counter()
    unsupported_in_crop = []
    for row in edit_inv["objects"]:
        if "F.Cu" not in row.get("layers", []):
            continue
        edit_fcu_counts[row["kind"]] += 1
        geom_data = edit_inv["payloads"].get(row.get("geometry_sha256"))
        if not geom_data:
            bounds = row.get("bounds_mm")
            if bounds and box(*bounds).intersects(crop):
                unsupported_in_crop.append(row)
            continue
        geom = wkb.loads(geom_data)
        if row["kind"] == "gr_poly" and geom.intersects(crop):
            edit_polys.append({"row": row, "geom": geom})

    # Candidate associations use a registered-frame centroid distance, then a
    # deterministic one-to-one minimum-distance assignment. They are not proof
    # of native object identity and remain provisional when competing matches
    # are close or the chosen geometry is not itself rectangular.
    edges = []
    candidates_by_org = {}
    for oi, org in enumerate(org_rects):
        oc = center(org["geom"])
        candidates = []
        for ei, edit in enumerate(edit_polys):
            ec = center(edit["geom"])
            distance = math.dist(oc, ec)
            if distance <= 0.15:
                candidates.append((distance, ei))
                edges.append((distance, oi, ei))
        candidates_by_org[oi] = sorted(candidates)
    used_org, used_edit, assignment = set(), set(), {}
    for distance, oi, ei in sorted(edges):
        if oi in used_org or ei in used_edit:
            continue
        assignment[oi] = (ei, distance)
        used_org.add(oi)
        used_edit.add(ei)

    associations = []
    for oi, org in enumerate(org_rects):
        orect, og = org["rect"], org["geom"]
        choices = candidates_by_org[oi]
        assigned = assignment.get(oi)
        if not assigned:
            associations.append({
                "org_source_id": orect["source_id"],
                "org_source_span": orect["source_span"],
                "org_center_mm": center(og),
                "org_size_mm": orect["source_size_mm"],
                "edit_association_status": "NO_CANDIDATE_WITHIN_0_15_MM",
                "edit_candidate_count_within_0_15_mm": len(choices),
            })
            continue
        ei, distance = assigned
        edit = edit_polys[ei]
        eg = edit["geom"]
        edit_dims = dims(eg)
        org_dims = dims(og)
        # Bounds are used only as a descriptive proxy. Six-vertex contours can
        # include a local recess or contour artifact, so their area and topology
        # are kept explicit rather than called a simple rectangle.
        angle = float(orect["orientation_radians"])
        org_local_dims = local_dims(og, angle)
        edit_local_dims = local_dims(eg, angle)
        ratios = [edit_local_dims[i] / org_local_dims[i] if org_local_dims[i] else None for i in (0, 1)]
        ranked = choices
        margin = (ranked[1][0] - distance) if len(ranked) > 1 else None
        overlap = og.intersection(eg).area / min(og.area, eg.area) if min(og.area, eg.area) else 0.0
        near_competitor = bool(margin is not None and margin < 0.005)
        edit_vertices = len(eg.exterior.coords) - 1 if eg.geom_type == "Polygon" else None
        status = "PROVISIONAL_NEAREST_GEOMETRY_ASSOCIATION"
        if near_competitor:
            status = "AMBIGUOUS_NEAR_TIE"
        associations.append({
            "org_source_id": orect["source_id"],
            "org_source_span": orect["source_span"],
            "org_source_record_sha256": sha(org_raw[slice(*orect["source_span"])]),
            "org_center_mm": center(og),
            "org_size_mm": orect["source_size_mm"],
            "edit_source_id": edit["row"]["id"],
            "edit_source_span": edit["row"]["source_span"],
            "edit_source_record_sha256": sha(edit_raw[slice(*edit["row"]["source_span"])]),
            "edit_center_mm": center(eg),
            "registered_centroid_displacement_mm": distance,
            "edit_candidate_count_within_0_15_mm": len(choices),
            "nearest_candidate_margin_mm": margin,
            "edit_association_status": status,
            "edit_polygon_vertex_count": edit_vertices,
            "edit_polygon_area_mm2": eg.area,
            "org_to_edit_intersection_over_smaller_area": overlap,
            "org_bounds_mm": list(og.bounds),
            "edit_bounds_mm": list(eg.bounds),
            "org_axis_aligned_bounds_mm": org_dims,
            "edit_axis_aligned_bounds_mm": edit_dims,
            "axis_aligned_dimension_ratios": ratios,
            "axis_aligned_dimension_deltas_mm": [edit_dims[i] - org_dims[i] for i in (0, 1)],
            "org_local_axis_dimensions_mm": org_local_dims,
            "edit_local_axis_dimensions_mm": edit_local_dims,
            "local_axis_dimension_deltas_mm": [edit_local_dims[i] - org_local_dims[i] for i in (0, 1)],
            "org_rectangle_orientation_radians": angle,
            "interpretation_limit": "Bounding-box changes are observational summaries, not a proposed constructor rule; six-vertex EDIT contours are not presumed rectangles.",
        })

    reliable = [x for x in associations if x.get("edit_association_status") == "PROVISIONAL_NEAREST_GEOMETRY_ASSOCIATION"]
    ambiguous = [x for x in associations if x.get("edit_association_status") == "AMBIGUOUS_NEAR_TIE"]
    paired_vertices = Counter(str(x["edit_polygon_vertex_count"]) for x in reliable + ambiguous)
    changes = [x for x in reliable + ambiguous if x.get("axis_aligned_dimension_ratios")]
    strict_rectangle_changes = [x for x in changes if x["edit_polygon_vertex_count"] == 4]
    trace_geometries = []
    for row in org_inv["objects"]:
        if "F.Cu" not in row.get("layers", []) or row.get("id") in org_rect_ids:
            continue
        geom_data = org_inv["payloads"].get(row.get("geometry_sha256"))
        if not geom_data:
            continue
        geom = wkb.loads(geom_data)
        if not geom.is_empty:
            trace_geometries.append((row, geom))
    org_rows_by_id = {item["rect"]["source_id"]: item for item in org_rects}
    for item in associations:
        source = org_rows_by_id[item["org_source_id"]]
        distances = sorted((source["geom"].distance(g), row["id"], row["kind"])
                           for row, g in trace_geometries)
        item["org_nonrectangle_copper_contact_count"] = sum(1 for d, _, _ in distances if d <= 1e-9)
        positive = next((v for v in distances if v[0] > 1e-9), None)
        item["nearest_positive_org_nonrectangle_copper_gap_mm"] = positive[0] if positive else None
        item["nearest_positive_org_nonrectangle_copper_id"] = positive[1] if positive else None
        item["nearest_positive_org_nonrectangle_copper_kind"] = positive[2] if positive else None
    report = {
        "schema": "t02-rect-org-edit-observation/1",
        "status": "OBSERVATION_COMPLETE_ASSOCIATIONS_PROVISIONAL",
        "scope": "Read-only registered ORG/EDIT rectangle-candidate size observation; no T02 geometry constructed.",
        "sources": {
            "org_path": str(org_path.relative_to(ROOT)), "org_sha256": org_hash,
            "edit_path": str(edit_path.relative_to(ROOT)), "edit_sha256": edit_hash,
            "crop_policy_path": str(policy_path.relative_to(ROOT)), "crop_policy_sha256": sha(policy_raw),
            "registration_path": str(reg_path.relative_to(ROOT)), "registration_sha256": sha(reg_path.read_bytes()),
            "registered_transform_edit_to_org": transform,
        },
        "crop_bounds_org_mm": policy["crop_bounds_org_mm"],
        "inventory_versions": {"org": org_inv["version"], "edit": edit_inv["version"]},
        "org_inventory": {"intersecting_fcu_supported_counts_by_kind": {"arc": 222, "gr_circle": 96, "gr_poly": 83, "segment": 631}, "exact_filled_rectangle_count": len(org_rects)},
        "edit_inventory": {"fcu_kind_counts_board_inventory": dict(sorted(edit_fcu_counts.items())), "intersecting_fcu_gr_poly_count": len(edit_polys), "intersecting_fcu_unsupported_with_bounds_count": len(unsupported_in_crop), "exact_4_vertex_polygon_count": sum(1 for x in edit_polys if x["geom"].geom_type == "Polygon" and len(x["geom"].exterior.coords) == 5), "6_vertex_polygon_count": sum(1 for x in edit_polys if x["geom"].geom_type == "Polygon" and len(x["geom"].exterior.coords) == 7)},
        "association_method": {
            "candidate_rule": "centroid distance <= 0.15 mm between each ORG rectangle and EDIT F.Cu gr_poly contour, in registered coordinates",
            "assignment": "globally sorted deterministic one-to-one greedy minimum centroid distance",
            "not_identity_proof": True,
            "candidate_competition_margin_mm": 0.005,
            "dimensions": "axis-aligned bounding-box width/height deltas; preserves contour vertex count and overlap diagnostics",
        },
        "summary": {
            "org_rectangles": len(org_rects),
            "provisionally_associated": len(reliable),
            "ambiguous_near_tie": len(ambiguous),
            "no_candidate_within_threshold": len(associations) - len(reliable) - len(ambiguous),
            "associated_edit_polygon_vertices": dict(sorted(paired_vertices.items())),
            "dimension_ratio_ranges_by_axis": [
                [min(x["axis_aligned_dimension_ratios"][i] for x in changes), max(x["axis_aligned_dimension_ratios"][i] for x in changes)]
                for i in (0, 1)
            ] if changes else None,
            "ratio_median_by_axis": [
                sorted(x["axis_aligned_dimension_ratios"][i] for x in changes)[len(changes)//2]
                for i in (0, 1)
            ] if changes else None,
            "edit_bounds_area_ratio_gt_1_5_count": sum(1 for x in changes if any(v > 1.5 for v in x["axis_aligned_dimension_ratios"])),
            "strict_four_vertex_pair_count": len(strict_rectangle_changes),
            "strict_four_vertex_local_axis_ratio_ranges": [
                [min(x["axis_aligned_dimension_ratios"][i] for x in strict_rectangle_changes), max(x["axis_aligned_dimension_ratios"][i] for x in strict_rectangle_changes)]
                for i in (0, 1)
            ] if strict_rectangle_changes else None,
            "strict_four_vertex_local_axis_ratio_medians": [
                sorted(x["axis_aligned_dimension_ratios"][i] for x in strict_rectangle_changes)[len(strict_rectangle_changes)//2]
                for i in (0, 1)
            ] if strict_rectangle_changes else None,
            "org_rectangles_touching_nonrectangle_copper": sum(1 for x in associations if x.get("org_nonrectangle_copper_contact_count", 0)),
            "org_rectangles_with_positive_nonrectangle_copper_gap": sum(1 for x in associations if x.get("nearest_positive_org_nonrectangle_copper_gap_mm") is not None),
        },
        "associations": associations,
        "conclusions": [
            "These provisional associations can suggest recurring geometric change patterns but cannot establish source-object identity or the CAM operation that produced EDIT.",
            "EDIT polygons with six vertices are reported separately; their bounding boxes do not imply recess or rectangle semantics.",
            "No per-feature EDIT dimensions are authorized as constructor inputs. Any future proposal must state a shared rule derived from the aggregate observation and ORG dimensions.",
            "This report does not establish collision freedom, electrical behavior, manufacturing suitability, or owner acceptance of the pending new-crop T01 baseline.",
        ],
    }
    out = ROOT / output_rel
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "rectangle_size_observation.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    csv_lines = ["org_source_id,association_status,org_local_w_mm,org_local_h_mm,edit_local_w_mm,edit_local_h_mm,delta_w_mm,delta_h_mm,ratio_w,ratio_h,vertices,centroid_delta_mm,overlap_ratio,nearest_positive_nonrectangle_gap_mm"]
    for x in associations:
        if not x.get("axis_aligned_dimension_ratios"):
            continue
        ow, oh = x["org_local_axis_dimensions_mm"]
        ew, eh = x["edit_local_axis_dimensions_mm"]
        dw, dh = x["local_axis_dimension_deltas_mm"]
        rw, rh = x["axis_aligned_dimension_ratios"]
        vals = [x["org_source_id"], x["edit_association_status"], ow, oh, ew, eh, dw, dh, rw, rh, x["edit_polygon_vertex_count"], x["registered_centroid_displacement_mm"], x["org_to_edit_intersection_over_smaller_area"], x.get("nearest_positive_org_nonrectangle_copper_gap_mm")]
        csv_lines.append(",".join('"'+str(v).replace('"','""')+'"' if isinstance(v,str) else str(v) for v in vals))
    (out / "rectangle_pairs.csv").write_text("\n".join(csv_lines) + "\n")
    sums = []
    for name in ("rectangle_size_observation.json", "rectangle_pairs.csv"):
        sums.append(f"{sha((out/name).read_bytes())}  {name}")
    (out / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print("report", report_path.relative_to(ROOT))


if __name__ == "__main__":
    run()
