"""Evidence-bound measurements for the frozen three-member ORG→EDIT family.

This module consumes the existing ORG family profile and independently fitted
F.Mask registration. It does not run recognition or infer manufacturing intent.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from xml.sax.saxutils import escape

from shapely import affinity, wkb
from shapely.geometry import Point, box
from shapely.ops import unary_union

from src.ingestion_files import sha
from src.native_inventory import inventory
from tools.build_copper_group_review import _circle_links, _registered_trace_inputs
from tools.build_identity_review import child, source_object
from src.copper_correspondence import trace_correspondence
import sexpdata


PROFILE_REL = "out/ingestion/audits/20261024_g22_reference_region_profile_v1/profile.json"
REGISTRATION_REL = "out/ingestion/audits/20261023_registered_copper_correspondence_v1/evidence/registration.json"
DATASET_REL = "dataset/szu-comm_3020301113B_intake_ready_20261021_v1/raw"
DATASET_PACKAGE_REL = "dataset/szu-comm_3020301113B_intake_ready_20261021_v1"
ORG_REL = f"{DATASET_REL}/ORG/top.kicad_pcb"
EDIT_REL = f"{DATASET_REL}/EDIT/top_layer.kicad_pcb"
EXPECTED_FAMILY_KEY = "cdca145fddd555c55a8cdd3b94d08fa4546738a9228e4d20cbaa295881ac7d53"
EXPECTED_MEMBERS = (
    "0bcaad306c62b68e069df6bc1daf9472be9c6d294d718fee990ba868655e6ff9",
    "439135b39508c0c2152da7a76150bb5cb34f49a5a1e8cd94a134393fd9ee2569",
    "58155bbdb4e5841e838b31b495f8cb7afe0892da903639e471e044a26b6587dc",
)
WINDOW_HALF_MM = (0.30, 0.42)
MATCH_TOLERANCE_MM = 0.001


def fixed_window(center_mm, half_mm=WINDOW_HALF_MM):
    """Return a same-frame crop with invariant dimensions around the ORG anchor."""
    x, y = map(float, center_mm)
    hx, hy = map(float, half_mm)
    if hx <= 0 or hy <= 0:
        raise ValueError("window dimensions must be positive")
    return [x - hx, y - hy, x + hx, y + hy]


def _xform_geometry(geometry, transform):
    angle = float(transform["rotation_radians"])
    tx, ty = map(float, transform["translation_mm"])
    if angle:
        geometry = affinity.rotate(geometry, math.degrees(angle), origin=(0, 0))
    if tx or ty:
        geometry = affinity.translate(geometry, xoff=tx, yoff=ty)
    return geometry


def _row_geometry(row, payloads, transform=None):
    digest = row.get("geometry_sha256")
    data = payloads.get(digest) if digest else None
    if not data:
        return None
    geom = wkb.loads(data)
    return _xform_geometry(geom, transform) if transform else geom


def _object_identity(source_hash, span):
    return f"{source_hash}:bytes:{span[0]}:{span[1]}"


def _circle_details(raw, row):
    node = sexpdata.loads(raw[row["source_span"][0]:row["source_span"][1]].decode("utf-8"))
    center = child(node, "center")
    edge = child(node, "end")
    c = (float(center[1]), float(center[2]))
    e = (float(edge[1]), float(edge[2]))
    radius = math.dist(c, e)
    return {"center_mm": list(c), "radius_mm": radius,
            "diameter_mm": radius * 2, "area_mm2": math.pi * radius * radius}


def _inventory_side(raw, source_hash):
    inv = inventory(raw)
    rows = inv["objects"]
    for row in rows:
        if row.get("source_sha256") != source_hash:
            raise ValueError("inventory row is not bound to the expected source hash")
        if row.get("id") != _object_identity(source_hash, row["source_span"]):
            raise ValueError("inventory identity does not match its exact byte span")
    return {"rows": rows, "payloads": inv["payloads"], "source_hash": source_hash,
            "inventory_version": inv["version"], "units": inv["units"],
            "coordinates": inv["coordinates"],
            "geometry_error_mm": inv["geometry_error_mm"],
            "per_curve_approximation_error_mm": inv["per_curve_approximation_error_mm"]}


def _registration_quality(record, before_side, after_side):
    """Summarize residuals and the spatial extent of the pinned F.Mask anchors."""
    before_by_id = {row["id"]: row for row in before_side["rows"]}
    residuals = [float(pair["residual_mm"]) for pair in record["keypoint_pairs"]]
    points = []
    for pair in record["keypoint_pairs"]:
        row = before_by_id.get(pair["before_identity"])
        geom = _row_geometry(row, before_side["payloads"]) if row else None
        if geom is None or geom.is_empty:
            raise ValueError("registration anchor geometry is absent from pinned ORG inventory")
        centroid = geom.centroid
        points.append((centroid.x, centroid.y))
    if len(points) != int(record["inlier_count"]) or not residuals:
        raise ValueError("registration anchor count differs from pinned inlier record")
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    ordered = sorted(residuals)
    p95_index = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "matched_anchor_count": len(points),
        "org_anchor_centroid_bounds_mm": [min(xs), min(ys), max(xs), max(ys)],
        "org_anchor_span_mm": [max(xs) - min(xs), max(ys) - min(ys)],
        "residual_summary_mm": {
            "minimum": min(residuals), "median": statistics.median(residuals),
            "p95_nearest_rank": ordered[p95_index], "maximum": max(residuals)},
        "residual_definition": "Recorded point residuals for the pinned mutual-unique F.Mask keypoint pairs.",
        "coverage_limit": "Anchor bounds summarize observed landmark extent only; they are not a statistical registration confidence region or board-wide completeness proof.",
    }


def _source_record_digests(value, sources):
    """Hash exact end-exclusive source byte slices for every emitted object identity."""
    identity_pattern = re.compile(r"^([0-9a-f]{64}):bytes:(\d+):(\d+)$")
    identities = set()

    def visit(item):
        if isinstance(item, dict):
            for nested in item.values():
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)
        elif isinstance(item, str):
            match = identity_pattern.fullmatch(item)
            if match:
                identities.add((item, match.group(1), int(match.group(2)), int(match.group(3))))

    visit(value)
    result = {}
    for identity, source_hash, start, end in sorted(identities):
        raw = sources.get(source_hash)
        if raw is None or start < 0 or end <= start or end > len(raw):
            raise ValueError(f"source span cannot be verified: {identity}")
        result[identity] = hashlib.sha256(raw[start:end]).hexdigest()
    return result


def _circle_candidates(center_org, seed_radius, after_side, raw_after, transform):
    """Enumerate every F.Cu gr_circle in the pinned inventory within center tolerance."""
    universe = [row for row in after_side["rows"]
                if row["kind"] == "gr_circle" and "F.Cu" in row.get("layers", [])]
    candidates = []
    for row in universe:
        details = _circle_details(raw_after, row)
        edit_center_in_org = _xform_geometry(Point(details["center_mm"]), transform)
        distance = math.dist(center_org, tuple(edit_center_in_org.coords[0]))
        if distance <= MATCH_TOLERANCE_MM:
            candidates.append({"identity": row["id"], **details,
                               "center_displacement_mm": distance,
                               "radius_delta_mm": details["radius_mm"] - seed_radius,
                               "area_delta_mm2": details["area_mm2"] - math.pi * seed_radius * seed_radius})
    return universe, sorted(candidates, key=lambda item: item["identity"])


def _verify_dataset_manifest(root):
    """Recheck the sealed package inventory without repairing or normalizing it."""
    package = root / DATASET_PACKAGE_REL
    sums = package / "SHA256SUMS"
    expected = {}
    for line in sums.read_text().splitlines():
        digest, sep, rel = line.partition("  ")
        if not sep or len(digest) != 64 or not rel or rel in expected:
            raise ValueError("invalid package SHA256SUMS entry")
        expected[rel] = digest
    actual = {path.relative_to(package).as_posix(): sha(path)
              for path in package.rglob("*") if path.is_file() and path != sums}
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(path for path in set(expected) & set(actual)
                     if expected[path] != actual[path])
    failures = sorted(set(missing + extra + changed))
    return {"status": "PASS" if not failures else "MISMATCH",
            "manifest_path": f"{DATASET_PACKAGE_REL}/SHA256SUMS",
            "manifest_sha256": sha(sums), "checked_count": len(expected),
            "failed_paths": failures, "missing_paths": missing, "extra_paths": extra,
            "changed_paths": changed,
            "treatment": "Read-only verification. No source bytes, manifest, or package metadata were changed."}


def _supported_copper(side, window_geom, transform=None):
    selected, geometries = [], []
    for row in side["rows"]:
        if "F.Cu" not in row.get("layers", []) or row.get("coverage") != "GEOMETRY_AVAILABLE":
            continue
        geom = _row_geometry(row, side["payloads"], transform)
        if geom is None or geom.is_empty or not geom.intersects(window_geom):
            continue
        selected.append(row)
        geometries.append(geom.intersection(window_geom))
    region = unary_union([g for g in geometries if not g.is_empty]) if geometries else window_geom.difference(window_geom)
    return selected, geometries, region


def _unsupported_in_window(side, raw, window, transform=None):
    """Conservatively surface unsupported copper primitives using source control points."""
    minx, miny, maxx, maxy = window
    area = box(minx, miny, maxx, maxy)
    found = []
    for row in side["rows"]:
        if "F.Cu" not in row.get("layers", []) or row.get("coverage") == "GEOMETRY_AVAILABLE":
            continue
        start, end = row["source_span"]
        try:
            node = sexpdata.loads(raw[start:end].decode("utf-8"))
        except Exception:
            continue
        points = []
        for name in ("start", "mid", "end", "center"):
            item = child(node, name)
            if item and len(item) >= 3:
                point = (float(item[1]), float(item[2]))
                if transform:
                    point = tuple(_xform_geometry(Point(point), transform).coords[0])
                points.append(point)
        if points and any(area.covers(__import__("shapely").geometry.Point(p)) for p in points):
            found.append({"identity": row["id"], "kind": row["kind"],
                          "reason": row.get("unsupported_reason"),
                          "source_span": row["source_span"],
                          "control_points_in_window": points,
                          "coverage_note": "Control-point inclusion is a conservative locator, not reconstructed arc area."})
    return found


def _local_rows(side, window, layer, kinds=None, transform=None):
    region = box(*window)
    result = []
    for row in side["rows"]:
        if layer not in row.get("layers", []):
            continue
        if kinds and row.get("kind") not in kinds:
            continue
        geom = _row_geometry(row, side["payloads"], transform)
        if geom is not None and geom.intersects(region):
            result.append(row)
    return result


def _nearest_nonintersecting(seed_geometry, rows, payloads, excluded_ids, transform=None,
                             tie_tolerance_mm=2e-5):
    candidates = []
    for row in rows:
        if row["id"] in excluded_ids or "F.Cu" not in row.get("layers", []):
            continue
        geom = _row_geometry(row, payloads, transform)
        if geom is None or geom.is_empty or seed_geometry.intersects(geom):
            continue
        distance = seed_geometry.distance(geom)
        if distance > 0:
            candidates.append((distance, row))
    if not candidates:
        return {"status": "NOT_ESTABLISHED", "reason": "No supported nonintersecting local neighbor geometry."}
    minimum = min(distance for distance, _ in candidates)
    return {"status": "MEASURED", "nearest_gap_mm": minimum,
            "neighbors_within_tie_tolerance": [
                {"identity": row["id"], "kind": row["kind"], "gap_mm": distance}
                for distance, row in sorted(candidates, key=lambda item: (item[0], item[1]["id"]))
                if distance <= minimum + tie_tolerance_mm],
            "definition": "Minimum boundary distance from the selected filled seed circle to a supported local F.Cu object that does not intersect that seed; this is not an electrical-clearance verdict."}


def _supported_intersection_component(rows, geometries, seed_ids):
    """Return supported local GEOS-intersection components containing seed candidates."""
    id_to_index = {row["id"]: i for i, row in enumerate(rows)}
    found = []
    for seed_id in seed_ids:
        start = id_to_index.get(seed_id)
        if start is None:
            found.append({"seed_identity": seed_id, "status": "NOT_ESTABLISHED", "source_identities": []})
            continue
        pending = [start]
        component, visited = set(), set()
        while pending:
            index = pending.pop()
            if index in visited:
                continue
            visited.add(index)
            component.add(index)
            for other, candidate in enumerate(geometries):
                if other not in visited and geometries[index].intersects(candidate):
                    pending.append(other)
        found.append({"seed_identity": seed_id, "status": "SUPPORTED_GEOMETRY_COMPONENT",
                      "object_count": len(component),
                      "source_identities": sorted(rows[i]["id"] for i in component),
                      "predicate": "Transitive same-layer F.Cu GEOS-intersects among supported objects clipped to the fixed local window; geometric only."})
    return found


def _contact_relationships(member, before_side, after_side, raw_before, raw_after,
                           registration_record, trace_map, circle_candidates):
    transform = registration_record["fitted_after_to_before"]
    org_seed = next(r for r in before_side["rows"] if r["id"] == member["seed"]["object_id"])
    org_seed_geom = _row_geometry(org_seed, before_side["payloads"])
    before_by_id = {r["id"]: r for r in before_side["rows"]}
    after_by_id = {r["id"]: r for r in after_side["rows"]}
    result = []
    for trace in member["traces"]:
        row = before_by_id[trace["object_id"]]
        geom = _row_geometry(row, before_side["payloads"])
        relation = {"org_seed_identity": org_seed["id"], "org_trace_identity": row["id"],
                    "org_intersection_area_mm2": org_seed_geom.intersection(geom).area,
                    "org_boundary_gap_mm": org_seed_geom.distance(geom),
                    "status": "MEASURED_GEOMETRY_ONLY"}
        org_intersection = org_seed_geom.intersection(geom)
        relation["org_contact_centroid_mm"] = ([org_intersection.centroid.x, org_intersection.centroid.y]
                                                if org_intersection.area > 0 else None)
        edges = trace_map["by_org_trace"].get(row["id"], [])
        after_details = []
        for candidate in circle_candidates:
            circle_row = after_by_id.get(candidate["identity"])
            if not circle_row:
                continue
            circle_geom = _row_geometry(circle_row, after_side["payloads"], transform)
            for edge in edges:
                trace_row = after_by_id.get(edge["after_identity"])
                if not trace_row:
                    continue
                trace_geom = _row_geometry(trace_row, after_side["payloads"], transform)
                after_details.append({"edit_seed_identity": circle_row["id"],
                    "edit_trace_identity": trace_row["id"],
                    "intersection_area_mm2": circle_geom.intersection(trace_geom).area,
                    "boundary_gap_mm": circle_geom.distance(trace_geom),
                    "trace_edge_status": "PARTIAL_OR_FULL_CENTERLINE_CANDIDATE"})
                intersection = circle_geom.intersection(trace_geom)
                after_details[-1]["contact_centroid_mm"] = ([intersection.centroid.x, intersection.centroid.y]
                                                              if intersection.area > 0 else None)
        relation["edit_candidates"] = after_details
        relation["edit_status"] = "AMBIGUOUS" if len(after_details) > 1 else "SUPPORTED_GEOMETRIC_CANDIDATE" if after_details else "NOT_ESTABLISHED"
        result.append(relation)
    return result


def _reference_candidates(profile_member, before_side, after_side, raw_before, raw_after, transform):
    results = []
    for ref in profile_member.get("references", []):
        ref_id = ref["object_id"]
        org_row = next((r for r in before_side["rows"] if r["id"] == ref_id), None)
        if not org_row:
            results.append({"layer": (ref.get("layers") or [None])[0], "status": "NOT_ESTABLISHED",
                            "org_identity": ref_id, "reason": "profile reference identity absent from pinned ORG inventory"})
            continue
        org_shape = _row_geometry(org_row, before_side["payloads"])
        org_detail = _circle_details(raw_before, org_row) if org_row["kind"] == "gr_circle" else None
        layer = (ref.get("layers") or [None])[0]
        candidates = []
        if org_detail:
            predicted = tuple(org_detail["center_mm"])
            for row in after_side["rows"]:
                if layer not in row.get("layers", []) or row["kind"] != org_row["kind"]:
                    continue
                try:
                    detail = _circle_details(raw_after, row)
                except Exception:
                    continue
                mapped = _xform_geometry(Point(detail["center_mm"]), transform)
                displacement = math.dist(predicted, tuple(mapped.coords[0]))
                if displacement <= MATCH_TOLERANCE_MM:
                    after_shape = _row_geometry(row, after_side["payloads"], transform)
                    candidates.append({"identity": row["id"], "center_displacement_mm": displacement,
                                       "before": org_detail, "after": detail,
                                       "symmetric_difference_area_mm2": org_shape.symmetric_difference(after_shape).area,
                                       "boundary_hausdorff_distance_mm": org_shape.boundary.hausdorff_distance(after_shape.boundary)})
        status = "SUPPORTED" if len(candidates) == 1 else "AMBIGUOUS" if len(candidates) > 1 else "UNMATCHED"
        results.append({"layer": layer, "org_identity": ref_id, "status": status,
                        "matching_rule": "same source geometry kind/layer and registered centers within 0.001 mm; size excluded from key",
                        "candidates": candidates,
                        "interpretation": "Geometric feature correspondence only; layer label does not establish process role or fixed status."})
    return results


def _svg_path(geometry, x0, y0, scale):
    """Serialize polygonal effective copper into a compact SVG path."""
    if geometry.is_empty:
        return ""
    polygons = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
    bits = []
    for poly in polygons:
        if poly.geom_type != "Polygon":
            continue
        for ring in (poly.exterior, *poly.interiors):
            pts = list(ring.coords)
            if len(pts) < 3:
                continue
            x, y = pts[0]
            bits.append(f"M{(x-x0)*scale:.2f},{(y-y0)*scale:.2f}")
            bits.extend(f"L{(x-x0)*scale:.2f},{(y-y0)*scale:.2f}" for x,y in pts[1:])
            bits.append("Z")
    return " ".join(bits)


def _render_member_svg(member, profile_member, window, before_rows, before_geoms, after_rows, after_geoms,
                       added, removed, unsupported, references, before_side, after_side, transform):
    width, height, pane_w, pane_h = 1560, 620, 500, 510
    minx, miny, maxx, maxy = window
    scale = min((pane_w - 36)/(maxx-minx), (pane_h-82)/(maxy-miny))
    before_focus = {profile_member["seed"]["object_id"], *(t["object_id"] for t in profile_member["traces"])}
    circle_candidates = member["seed"].get("edit_candidates", [])
    after_focus = {c["identity"] for c in circle_candidates}
    circle_colors = {candidate["identity"]: ("#087f83" if index == 0 else "#d68a0c")
                     for index, candidate in enumerate(circle_candidates)}
    after_focus.update(e["after_identity"] for rel in member["trace_correspondence"]["relations"]
                       for e in rel["candidate_edges"])
    labels = [("ORG · source geometry", "org"), ("EDIT · registered destination", "edit"),
              ("EDIT − ORG · local added / removed", "delta")]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
             '<rect width="100%" height="100%" fill="#f4f7f8"/>',
             f'<text x="24" y="30" font-family="Arial,sans-serif" font-size="21" font-weight="700" fill="#22313b">Member {member["ordinal"]} · same ORG coordinate window</text>',
             f'<text x="24" y="55" font-family="Arial,sans-serif" font-size="13" fill="#52646f">X {minx:.3f}…{maxx:.3f} mm · Y {miny:.3f}…{maxy:.3f} mm · same transform, no per-side recentering</text>']
    for ix, (label, pane) in enumerate(labels):
        px, py = 24 + ix*516, 82
        parts.append(f'<rect x="{px}" y="{py}" width="{pane_w}" height="{pane_h}" rx="8" fill="white" stroke="#cad4d8"/>')
        parts.append(f'<text x="{px+14}" y="{py+23}" font-family="Arial,sans-serif" font-size="15" font-weight="700" fill="#263740">{label}</text>')
        group = [f'<g transform="translate({px+18},{py+42})">']
        if pane == "org":
            for row, geom in zip(before_rows, before_geoms):
                color = "#bd553b" if row["id"] in before_focus else "#99a7ad"
                opacity = "0.95" if row["id"] in before_focus else "0.32"
                path = _svg_path(geom, minx, miny, scale)
                if path:
                    group.append(f'<path d="{path}" fill="{color}" fill-rule="evenodd" opacity="{opacity}" data-source="{escape(row["id"])}"/>')
        elif pane == "edit":
            for row, geom in zip(after_rows, after_geoms):
                color = circle_colors.get(row["id"], "#087f83" if row["id"] in after_focus else "#99a7ad")
                opacity = "0.95" if row["id"] in after_focus else "0.32"
                path = _svg_path(geom, minx, miny, scale)
                if path:
                    fill_opacity = "0.58" if row["id"] in circle_colors and len(circle_colors) > 1 else opacity
                    outline = f' stroke="{color}" stroke-width="1.4"' if row["id"] in circle_colors else ""
                    group.append(f'<path d="{path}" fill="{color}" fill-rule="evenodd" opacity="{opacity}" fill-opacity="{fill_opacity}"{outline} data-source="{escape(row["id"])}"/>')
            for item in unsupported:
                for x,y in item.get("control_points_in_window", []):
                    group.append(f'<circle cx="{(x-minx)*scale:.2f}" cy="{(y-miny)*scale:.2f}" r="5" fill="#7b2cbf" stroke="white" stroke-width="2"><title>Unsupported {escape(item["identity"])}: {escape(item.get("reason") or "unknown")}</title></circle>')
        else:
            for geom, color in ((added, "#149447"), (removed, "#ce4d3c")):
                path = _svg_path(geom, minx, miny, scale)
                if path:
                    group.append(f'<path d="{path}" fill="{color}" fill-rule="evenodd" opacity="0.88"/>')
        for ref in references:
            ref_ids = ([ref["org_identity"]] if pane == "org" else
                       [candidate["identity"] for candidate in ref["candidates"]] if pane == "edit" else [])
            source_side = before_side if pane == "org" else after_side
            for identity in ref_ids:
                row = next((r for r in source_side["rows"] if r["id"] == identity), None)
                if row is None:
                    continue
                geom = _row_geometry(row, source_side["payloads"], transform if pane == "edit" else None)
                path = _svg_path(geom.intersection(box(*window)), minx, miny, scale)
                if path:
                    group.append(f'<path d="{path}" fill="none" stroke="#173b69" stroke-width="1.8" stroke-dasharray="5 3" data-reference="{escape(identity)}"><title>Reference geometry candidate {escape(identity)}</title></path>')
        cx, cy = member["center_org_mm"]
        group.append(f'<circle cx="{(cx-minx)*scale:.2f}" cy="{(cy-miny)*scale:.2f}" r="4" fill="#111" stroke="white" stroke-width="1.5"/>')
        group.append('</g>')
        parts.extend(group)
    parts.extend(['<text x="780" y="612" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="#50636f">ORG highlight: rust · EDIT candidates: teal/orange · dashed blue: reference geometry · added: green · removed: red · violet: unsupported arc controls</text></svg>'])
    return "".join(parts)


def _circle_correspondences(before_side, after_side, raw_before, raw_after, registration):
    raw = {"before": raw_before, "after": raw_after}
    probes = {side: [{k: row[k] for k in ("id", "kind", "layers", "source_span")}
                     for row in data["rows"]]
              for side, data in (("before", before_side), ("after", after_side))}
    links, audit = _circle_links(raw, probes, registration=registration, return_audit=True)
    return links, audit


def _trace_map(member, before_side, after_side, raw_before, raw_after, window, registration_record):
    transform = registration_record["fitted_after_to_before"]
    raws = {"before": raw_before, "after": raw_after}
    trace_ids = {trace["object_id"] for trace in member["traces"]}
    org_trace_rows = [row for row in before_side["rows"] if row["id"] in trace_ids]
    if len(org_trace_rows) != len(trace_ids):
        raise ValueError("one or more frozen ORG trace identities are absent from the pinned inventory")
    before_inputs, excluded = _registered_trace_inputs(raws, {
        "before": org_trace_rows, "after": _local_rows(after_side, window, "F.Cu", {"segment", "arc"}, transform)
    }, registration_record)
    # _registered_trace_inputs keeps every listed ORG trace; restrict after local lines to those
    # whose source centerline bounds intersect the fixed comparison window.
    compared = trace_correspondence(before_inputs["before"], before_inputs["after"],
                                    tolerance_mm=MATCH_TOLERANCE_MM)
    links_by_before = {trace_id: [] for trace_id in trace_ids}
    for relation in compared["relations"]:
        for edge in relation["candidate_edges"]:
            before_item = next(item for item in before_inputs["before"] if item["identity"] == edge["before_identity"])
            after_item = next(item for item in before_inputs["after"] if item["identity"] == edge["after_identity"])
            before_mid = before_item["geometry"].interpolate(0.5, normalized=True)
            after_mid = after_item["geometry"].interpolate(0.5, normalized=True)
            links_by_before.setdefault(edge["before_identity"], []).append({
                k: edge.get(k) for k in ("after_identity", "covered_fraction_of_shorter",
                    "before_covered_fraction", "after_covered_fraction", "before_length_mm",
                    "after_length_mm", "before_width_mm", "after_width_mm", "width_delta_mm",
                    "copper_footprint_comparison")} | {
                "before_width_sample_centerline_midpoint_mm": [before_mid.x, before_mid.y],
                "after_width_sample_centerline_midpoint_mm": [after_mid.x, after_mid.y],
                "uncovered_edit_extent_status": "NOT_ESTABLISHED: the centerline portion outside the matched overlap is not classified as an extension, branch, separate continuation, or unrelated geometry.",
                "width_scope": "Native width is constant along each source primitive; midpoint is the explicit sample location."})
    return {"status": "MEASURED", "rule": "existing trace_correspondence: centerline tolerance 0.001 mm, at least 90% of shorter line and 0.02 mm overlap",
            "candidate_scope": "All local EDIT F.Cu segment and arc centerlines whose source bounds intersect the member window; ORG inputs are the frozen profile's listed trace candidates. Filled polygons and other primitive kinds are not trace-identity candidates. A missing edge is unmatched under this rule only, not evidence of deletion.",
            "before_trace_count": len(before_inputs["before"]), "local_after_trace_count": len(before_inputs["after"]),
            "excluded": excluded, "relations": compared["relations"],
            "by_org_trace": links_by_before}


def build_target_map(root: Path):
    """Build current measurements against the exact frozen profile and source bytes."""
    root = Path(root).resolve()
    profile_path = root / PROFILE_REL
    registration_path = root / REGISTRATION_REL
    profile = json.loads(profile_path.read_text())
    registration_record = json.loads(registration_path.read_text())
    org_path, edit_path = root / ORG_REL, root / EDIT_REL
    raw_before, raw_after = org_path.read_bytes(), edit_path.read_bytes()
    hashes = {"before": hashlib.sha256(raw_before).hexdigest(), "after": hashlib.sha256(raw_after).hexdigest()}
    binding = profile["binding"]
    if binding["family_key"] != EXPECTED_FAMILY_KEY or tuple(binding["member_keys"]) != EXPECTED_MEMBERS:
        raise ValueError("frozen family identity or membership changed")
    if hashes["before"] != binding["org_source_sha256"]:
        raise ValueError("ORG board bytes differ from frozen profile")
    for side, path in (("before", ORG_REL), ("after", EDIT_REL)):
        pinned = registration_record.get("source_files", {}).get(side, {})
        if pinned.get("path") != ("ORG/top.kicad_pcb" if side == "before" else "EDIT/top_layer.kicad_pcb") or pinned.get("sha256") != hashes[side]:
            raise ValueError(f"{side} bytes differ from pinned F.Mask registration")
    transform = registration_record["fitted_after_to_before"]
    if registration_record.get("source_layer") != "F.Mask only; F.Cu excluded from transform fitting":
        raise ValueError("registration is not the pinned F.Mask-only fit")
    before_side = _inventory_side(raw_before, hashes["before"])
    after_side = _inventory_side(raw_after, hashes["after"])
    registration_quality = _registration_quality(registration_record, before_side, after_side)
    package_integrity = _verify_dataset_manifest(root)
    recorded_package = profile["source_material_integrity"]["dataset_sha256_manifest"]
    package_integrity["profile_recorded_status"] = recorded_package.get("status")
    package_integrity["profile_recorded_failed_paths"] = recorded_package.get("failed_paths", [])
    package_integrity["profile_recorded_checked_count"] = recorded_package.get("checked_count")
    package_integrity["differs_from_profile_record"] = (
        package_integrity["status"] != recorded_package.get("status")
        or package_integrity["failed_paths"] != recorded_package.get("failed_paths", [])
        or package_integrity["checked_count"] != recorded_package.get("checked_count"))
    circle_links, circle_audit = _circle_correspondences(before_side, after_side, raw_before, raw_after, registration_record)
    links_by_before = {link["before_identity"]: link for link in circle_links}
    members_out = []
    for m in profile["family"]["members"]:
        center = list(map(float, m["center_mm"]))
        window = fixed_window(center)
        window_geom = box(*window)
        before_rows, before_geoms, before_region = _supported_copper(before_side, window_geom)
        after_rows, after_geoms, after_region = _supported_copper(after_side, window_geom, transform)
        added = after_region.difference(before_region)
        removed = before_region.difference(after_region)
        seed_id = m["seed"]["object_id"]
        seed_row = next(r for r in before_side["rows"] if r["id"] == seed_id)
        seed_before = _circle_details(raw_before, seed_row)
        circle = links_by_before.get(seed_id)
        circle_universe, circle_candidates = _circle_candidates(
            center, seed_before["radius_mm"], after_side, raw_after, transform)
        matched_link = (circle is not None and len(circle_candidates) == 1
                        and circle["after_identity"] == circle_candidates[0]["identity"])
        circle_status = ("AMBIGUOUS" if len(circle_candidates) > 1 else
                         "UNMATCHED" if not circle_candidates else
                         "SUPPORTED" if matched_link else "NOT_ESTABLISHED")
        org_nearest = [{"identity": n.get("object_id"), "kind": n.get("kind"),
                        "gap_mm": n.get("gap_from_seed_mm"),
                        "outside_org_contact_group": n.get("outside_member_contact_group")}
                       for n in m.get("nearby_external_copper_geometry", [])[:4]]
        edit_nearest = []
        after_local_rows = _local_rows(after_side, window, "F.Cu", transform=transform)
        for candidate in circle_candidates:
            candidate_row = next((r for r in after_side["rows"] if r["id"] == candidate["identity"]), None)
            if candidate_row:
                seed_geom = _row_geometry(candidate_row, after_side["payloads"], transform)
                edit_nearest.append({"seed_identity": candidate["identity"], **_nearest_nonintersecting(
                    seed_geom, after_local_rows, after_side["payloads"], {candidate["identity"]}, transform)})
        unsupported_before = _unsupported_in_window(before_side, raw_before, window)
        unsupported_after = _unsupported_in_window(after_side, raw_after, window, transform)
        for nearest in edit_nearest:
            nearest["completeness"] = "NOT_ESTABLISHED" if unsupported_before or unsupported_after else "SUPPORTED_GEOMETRY_ONLY"
            nearest["unsupported_local_object_count"] = len(unsupported_before) + len(unsupported_after)
            org_min_gap = org_nearest[0]["gap_mm"] if org_nearest else None
            nearest["delta_from_org_nearest_distance_statistic_mm"] = (
                nearest.get("nearest_gap_mm") - org_min_gap
                if nearest.get("nearest_gap_mm") is not None and org_min_gap is not None else None)
        local_status = "NOT_ESTABLISHED" if unsupported_before or unsupported_after else "MEASURED_SUPPORTED_GEOMETRY"
        traces = _trace_map(m, before_side, after_side, raw_before, raw_after, window, registration_record)
        refs = _reference_candidates(m, before_side, after_side, raw_before, raw_after, transform)
        fit_pairs = {(pair["before_identity"], pair["after_identity"]): pair
                     for pair in registration_record["keypoint_pairs"]}
        for reference in refs:
            for candidate in reference["candidates"]:
                pair = fit_pairs.get((reference["org_identity"], candidate["identity"]))
                candidate["registration_fit_anchor"] = ({
                    "included": True, "residual_mm": float(pair["residual_mm"])}
                    if pair else {"included": False, "residual_mm": None})
        member_out = {
            "ordinal": m["ordinal"], "member_key": m["member_key"], "center_org_mm": center,
            "coordinate_frame": "ORG KiCad board coordinates (X right, Y down); EDIT mapped by pinned F.Mask-only rigid transform",
            "window_mm": window,
            "seed": {"org_identity": seed_id, "org": seed_before, "edit_status": circle_status,
                     "candidate_search": {
                         "universe_count": len(circle_universe),
                         "universe": "All inventoried EDIT source objects with kind gr_circle and F.Cu layer.",
                         "predicate": "Transformed circle center within 0.001 mm of the frozen ORG seed center; radius and area are measured after candidate search.",
                         "excluded_semantics": "Other primitive kinds, including filled polygons, segments, and arcs, are not circle candidates. They remain part of the local copper-region comparison when supported."},
                     "edit_candidates": circle_candidates,
                     "edit_identity": circle["after_identity"] if circle else None},
            "physical_contact_group": {
                "org": {"status": "PROFILED_ORG_COMPONENT", **m["physical_contact_group"]},
                "edit_supported_local_components": [
                    {**component, "completeness": "NOT_ESTABLISHED" if unsupported_after else "SUPPORTED_GEOMETRY_ONLY"}
                    for component in _supported_intersection_component(after_rows, after_geoms,
                        [candidate["identity"] for candidate in circle_candidates])],
                "group_correspondence_status": "NOT_ESTABLISHED",
                "note": "The ORG component and EDIT local components are separate geometric inventories; no semantic/electrical group identity is asserted."},
            "reference_correspondence": refs,
            "trace_correspondence": traces,
            "neighbor_gaps": {"org_profile_nearest_external_from_seed": org_nearest,
                              "edit_nearest_nonintersecting_from_each_circle_candidate": edit_nearest,
                              "comparison_note": "EDIT nearest-feature gap is not an identity match to the ORG neighbor; closest feature identities may change and are listed separately."},
            "seed_trace_contact": _contact_relationships(m, before_side, after_side, raw_before, raw_after,
                                                          registration_record, traces, circle_candidates),
            "local_copper_region": {"status": local_status,
                "metric_scope": "union of supported native F.Cu effective geometries clipped to the same fixed window; source-object areas are not summed",
                "measurement_method": {
                    "window_bounds_mm": list(window), "window_area_mm2": window_geom.area,
                    "included_objects": "Every inventoried F.Cu object with GEOMETRY_AVAILABLE whose geometry intersects this window; each geometry is clipped to the window, and all clipped shapes are unioned before added/removed area is calculated.",
                    "excluded_objects": "F.Cu objects with unsupported geometry are omitted from the union and listed separately when their source control points fall in the window; any such item makes full-window totals NOT_ESTABLISHED.",
                    "inventory_version": before_side["inventory_version"],
                    "geometry_error_mm": before_side["geometry_error_mm"],
                    "per_curve_approximation_error_mm": before_side["per_curve_approximation_error_mm"],
                    "area_units": "mm^2",
                    "no_board_wide_sum": "Member windows overlap; their areas are not additive and must not be summed."},
                "org_supported_object_count": len(before_rows), "edit_supported_object_count": len(after_rows),
                "org_source_identities": sorted(r["id"] for r in before_rows),
                "edit_source_identities": sorted(r["id"] for r in after_rows),
                "org_union_area_mm2": before_region.area, "edit_union_area_mm2": after_region.area,
                "added_area_mm2": added.area, "removed_area_mm2": removed.area,
                "edit_minus_org_area_mm2": after_region.area - before_region.area,
                "org_union_bounds_mm": list(before_region.bounds) if not before_region.is_empty else None,
                "edit_union_bounds_mm": list(after_region.bounds) if not after_region.is_empty else None,
                "org_union_centroid_mm": [before_region.centroid.x, before_region.centroid.y] if not before_region.is_empty else None,
                "edit_union_centroid_mm": [after_region.centroid.x, after_region.centroid.y] if not after_region.is_empty else None,
                "org_region_wkb_sha256": hashlib.sha256(before_region.wkb).hexdigest(),
                "edit_region_wkb_sha256": hashlib.sha256(after_region.wkb).hexdigest(),
                "added_region_wkb_sha256": hashlib.sha256(added.wkb).hexdigest(),
                "removed_region_wkb_sha256": hashlib.sha256(removed.wkb).hexdigest(),
                "unsupported_org": unsupported_before, "unsupported_edit": unsupported_after},
            "interpretation": "Measured geometry only. Local-window additions/removals are not assigned semantic object identity, net, process purpose, or electrical continuity."
        }
        member_out["_svg"] = _render_member_svg(member_out, m, window, before_rows, before_geoms,
                                                  after_rows, after_geoms, added, removed,
                                                  unsupported_after, refs, before_side, after_side,
                                                  transform)
        members_out.append(member_out)
    source_record_digests = _source_record_digests(members_out, {
        hashes["before"]: raw_before, hashes["after"]: raw_after})
    return {
        "schema": "org-edit-one-family-target-map/1", "status": "REVIEW_EVIDENCE_READY",
        "family_key": binding["family_key"], "member_keys": list(binding["member_keys"]),
        "recognition_rerun": False, "family_membership_changed": False,
        "sources": {"ORG": {"path": ORG_REL, "sha256": hashes["before"]},
                    "EDIT": {"path": EDIT_REL, "sha256": hashes["after"]},
                    "profile": {"path": PROFILE_REL, "sha256": sha(profile_path)},
                    "registration": {"path": REGISTRATION_REL, "sha256": sha(registration_path)}},
        "registration": {k: v for k, v in registration_record.items() if k not in ("keypoint_pairs", "source_files")},
        "registration_quality": registration_quality,
        "comparison": {"coordinate_frame": "ORG board coordinates", "window_half_size_mm": list(WINDOW_HALF_MM),
                       "no_independent_recentering": True, "circle_center_tolerance_mm": MATCH_TOLERANCE_MM},
        "circle_pairing_audit": {k: v for k, v in circle_audit.items() if k not in ("ambiguous_before", "one_sided_before", "unmatched_before", "ambiguous_after", "one_sided_after", "unmatched_after")},
        "observed_pattern": {
            "seed_circles": "Every same-center EDIT circle candidate found for the three fixed ORG sites has a larger radius than its ORG seed. A and C each have one mutual-unique registered-center candidate; B has two concentric EDIT alternatives and remains ambiguous.",
            "reference_geometry": "All three F.Mask reference candidates have one registered geometric counterpart with zero measured boundary and area difference. F.Paste candidates have no same-kind/layer center match; this does not establish deletion.",
            "traces": "A and C each have one partial centerline candidate for an ORG segment, both widening from 0.05004 mm to 0.10000 mm. The other ORG trace in A/C and both traces in B have no candidate under the existing strict rule; no deletion or electrical conclusion follows.",
            "local_regions": "Supported-geometry union additions exceed removals in all three fixed windows; C is NOT_ESTABLISHED as a complete-window measure because two local EDIT arcs are degenerate and unsupported. Windows overlap spatially and must not be summed.",
            "interpretation": "Observed destination geometry only; this is not a common operation sequence or manufacturing rationale."},
        "members": members_out,
        "source_record_sha256": source_record_digests,
        "package_integrity": package_integrity,
        "limits": ["The nine UNKNOWN assessments remain UNKNOWN.",
                   "Source geometry correspondence is not PCB semantic identity or electrical connectivity.",
                   "No manufacturing intent, editing recipe, or edit authority is inferred.",
                   "The user approved the G22 crop-neighborhood review on 2026-10-24; no categorical SUPPORTED/AMBIGUOUS/UNRESOLVED judgment or detailed visual observations were specified."]
    }
