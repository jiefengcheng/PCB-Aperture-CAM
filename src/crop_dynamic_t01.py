"""Bounded, ORG-only circle growth with an evolving scene for crop T01.

This is an experimental geometry demonstration, not electrical or manufacturing
qualification. Inputs and eligibility are frozen by the T00 contract.
"""
from __future__ import annotations

from collections import Counter
from shapely import from_wkb, to_wkb
from shapely.ops import unary_union
from shapely.geometry import box
import sexpdata
from .native_inventory import inventory
from .native_reference import one


V_BOUNDS = (1.2858444444444446, -15.687077777777787,
            4.508066666666666, -12.975966666666665)
GROWTH_CAP_MM = 0.05
PROTECTED_GAP_MM = 0.02
GAP_TOLERANCE_MM = 1e-5
GAP_BUFFER_MARGIN_MM = 0.005
HALO_MM = GROWTH_CAP_MM + PROTECTED_GAP_MM + GAP_BUFFER_MARGIN_MM
MIN_DIAMETER_MM = 0.10
CROP_EDGE_GUARD_MM = 0.01
AREA_EVENT_EPSILON_MM2 = 1e-8


def _components(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [p for p in getattr(g, "geoms", ()) if p.geom_type == "Polygon"]


def run(source: bytes, *, dynamic: bool = True) -> dict:
    """Build the source-bound full-crop circle stage; EDIT is never an input."""
    inv = inventory(source)
    V = box(*V_BOUNDS)
    W = V.buffer(-CROP_EDGE_GUARD_MM)
    H = V.buffer(HALO_MM)
    rows = []
    for obj in inv["objects"]:
        if "F.Cu" not in obj["layers"] or not obj["geometry_sha256"]:
            continue
        geom = from_wkb(inv["payloads"][obj["geometry_sha256"]])
        if geom.intersects(H):
            rows.append((obj, geom))
    circles = []
    for obj, geom in rows:
        if obj["kind"] != "gr_circle" or not W.covers(geom):
            continue
        node = sexpdata.loads(source[slice(*obj["source_span"])].decode("utf-8"))
        if str(one(node, "fill", ["none"])[0]) not in ("yes", "solid"):
            continue
        b = geom.bounds
        diameter = ((b[2] - b[0]) + (b[3] - b[1])) / 2
        if diameter >= MIN_DIAMETER_MM:
            circles.append((obj, geom, diameter))
    circles.sort(key=lambda x: (x[1].centroid.y, x[1].centroid.x, x[0]["id"]))
    circle_ids = {r[0]["id"] for r in circles}
    protected = [(o, g) for o, g in rows if o["id"] not in circle_ids]
    trace_rows = [(o, g) for o, g in rows if o["kind"] in ("segment", "arc")]

    # Stable source-only order. The static baseline always consults ORG; the
    # dynamic run additionally consults all prior accepted enlarged contours.
    accepted = []
    decisions = []
    for order, (obj, core, diameter) in enumerate(circles):
        nominal = core.buffer(GROWTH_CAP_MM, quad_segs=32)
        # All other original geometry remains protected. A prior eligible circle
        # is replaced by its current accepted contour in dynamic mode.
        prior_by_id = {p["source_id"]: p["geometry"] for p in accepted}
        forbidden = []
        effective_obstacles = []
        for other_obj, other_geom in rows:
            if other_obj["id"] == obj["id"]:
                continue
            obstacle = prior_by_id.get(other_obj["id"], other_geom)
            effective_obstacles.append((other_obj["id"], obstacle))
            forbidden.append(obstacle.buffer(PROTECTED_GAP_MM + GAP_BUFFER_MARGIN_MM, quad_segs=32))
        limiting = []
        if dynamic:
            for prior in accepted:
                if nominal.distance(prior["geometry"]) <= GROWTH_CAP_MM + PROTECTED_GAP_MM:
                    limiting.append(prior["source_id"])
        # Only optional growth is clipped. The original core is always retained.
        addition = nominal.difference(core)
        for obstacle in forbidden:
            if addition.is_empty:
                break
            addition = addition.difference(obstacle)
        attached = [p for p in _components(addition) if p.distance(core) <= 1e-7]
        candidate = unary_union([core, *attached]) if attached else core
        # Reapply the complete obstacle union to the assembled optional growth.
        # This guards against small overlay artefacts at component boundaries.
        if forbidden:
            optional = candidate.difference(core).difference(unary_union(forbidden))
            attached = [p for p in _components(optional) if p.distance(core) <= 1e-7]
            candidate = unary_union([core, *attached]) if attached else core
        if not candidate.covers(core):
            lost = core.difference(candidate).area
            if lost > 1e-12:
                raise AssertionError(f"PROTECTED_CORE_LOSS:{obj['id']}:{lost}")
        else:
            lost = 0.0
        if not candidate.is_valid or candidate.is_empty:
            raise AssertionError("INVALID_CANDIDATE_GEOMETRY")
        area_delta = max(0.0, candidate.area - core.area)
        optional_growth = candidate.difference(core)
        gap_rows = [(optional_growth.distance(other_geom), other_id, other_geom)
                    for other_id, other_geom in effective_obstacles]
        minimum_other_gap = min((d for d, _, _ in gap_rows), default=float("inf"))
        if area_delta > AREA_EVENT_EPSILON_MM2 and minimum_other_gap < PROTECTED_GAP_MM - GAP_TOLERANCE_MM:
            nearest_i = min(range(len(gap_rows)), key=lambda i: gap_rows[i][0])
            raise AssertionError(f"PROTECTED_GAP_BREACH:{obj['id']}:{minimum_other_gap}:"
                f"nearest={gap_rows[nearest_i][1]}:"
                f"candidate_to_buffer={optional_growth.distance(forbidden[nearest_i])}")
        decision = {
            "order": order,
            "source_id": obj["id"],
            "source_span": obj["source_span"],
            "source_sha256": obj["source_sha256"],
            "geometry_sha256": obj["geometry_sha256"],
            "center_mm": [core.centroid.x, core.centroid.y],
            "diameter_mm": diameter,
            "nominal_growth_cap_mm": GROWTH_CAP_MM,
            "input_scene_revision": f"scene-{order:03d}",
            "output_scene_revision": f"scene-{order + 1:03d}",
            "nominal_area_delta_mm2": nominal.area - core.area,
            "accepted_area_delta_mm2": area_delta,
            "protected_core_loss_mm2": lost,
            "minimum_optional_growth_gap_mm": minimum_other_gap if area_delta > AREA_EVENT_EPSILON_MM2 else None,
            "candidate_wkb": to_wkb(candidate).hex(),
            "limiting_prior_source_ids": limiting,
            "limiting_trace_source_ids": [o["id"] for o, g in trace_rows
                if nominal.distance(g) <= GROWTH_CAP_MM + PROTECTED_GAP_MM + GAP_BUFFER_MARGIN_MM],
            "adapted_by_prior_acceptance": bool(limiting and area_delta + AREA_EVENT_EPSILON_MM2 < nominal.area - core.area),
            "decision": "GROW" if area_delta > AREA_EVENT_EPSILON_MM2 else "KEEP",
            "policy": "ORG source core retained; optional growth clipped by protected ORG geometry and prior accepted circles",
        }
        decisions.append(decision)
        accepted.append({"source_id": obj["id"], "geometry": candidate})

    # Same target order and policy, but neighbors always remain at ORG geometry.
    static = run_static(inv, V, H, circles, protected)
    static_by_id = {d["source_id"]: d for d in static["decisions"]}
    for decision in decisions:
        baseline = from_wkb(bytes.fromhex(static_by_id[decision["source_id"]]["candidate_wkb"]))
        dynamic_shape = from_wkb(bytes.fromhex(decision["candidate_wkb"]))
        difference = dynamic_shape.symmetric_difference(baseline).area
        decision["dynamic_vs_static_symmetric_difference_mm2"] = difference
        decision["adapted_by_prior_acceptance"] = bool(
            decision["limiting_prior_source_ids"] and difference > AREA_EVENT_EPSILON_MM2)
        decision["adaptation_explanation"] = ("Prior accepted contour changed this site's accepted geometry"
            if decision["adapted_by_prior_acceptance"] else "No measured prior-neighbor effect")
    event_count = sum(d["adapted_by_prior_acceptance"] for d in decisions)
    return {
        "schema": "crop-dynamic-t01/1",
        "mode": "ORG_ONLY_DYNAMIC" if dynamic else "ORG_ONLY_STATIC",
        "source_sha256": inv["source_sha256"],
        "viewport_mm": list(V_BOUNDS), "write_region_mm": list(W.bounds),
        "crop_edge_guard_mm": CROP_EDGE_GUARD_MM, "halo_mm": HALO_MM,
        "supported_halo_object_count": len(rows),
        "supported_halo_kind_counts": dict(Counter(o["kind"] for o, _ in rows)),
        "reserved_trace_object_count": len(trace_rows),
        "unsupported_FCu_intersecting_halo": [o["id"] for o in inv["objects"]
            if "F.Cu" in o["layers"] and o["coverage"] != "GEOMETRY_AVAILABLE"
            and o["bounds_mm"] and box(*o["bounds_mm"]).intersects(H)],
        "eligible_target_count": len(circles),
        "halo_filled_circle_count": sum(o["kind"] == "gr_circle" for o, _ in rows),
        "minimum_target_clearance_from_V_boundary_mm": min((V.boundary.distance(g) for _, g, _ in circles), default=None),
        "eligible_target_ids": sorted(circle_ids),
        "kept_small_circle_count": sum(o["kind"] == "gr_circle" and W.covers(g) and
            ((g.bounds[2]-g.bounds[0])+(g.bounds[3]-g.bounds[1]))/2 < MIN_DIAMETER_MM
            for o, g in rows),
        "abstained_edge_guard_circle_count": sum(o["kind"] == "gr_circle" and not W.covers(g)
            for o, g in rows),
        "abstained_edge_guard_large_circle_count": sum(o["kind"] == "gr_circle" and not W.covers(g) and
            ((g.bounds[2]-g.bounds[0])+(g.bounds[3]-g.bounds[1]))/2 >= MIN_DIAMETER_MM for o, g in rows),
        "abstained_edge_guard_small_circle_count": sum(o["kind"] == "gr_circle" and not W.covers(g) and
            ((g.bounds[2]-g.bounds[0])+(g.bounds[3]-g.bounds[1]))/2 < MIN_DIAMETER_MM for o, g in rows),
        "policy": {"min_diameter_mm": MIN_DIAMETER_MM, "growth_cap_mm": GROWTH_CAP_MM,
                   "protected_gap_mm": PROTECTED_GAP_MM,
                   "gap_tolerance_mm": GAP_TOLERANCE_MM,
                   "gap_buffer_margin_mm": GAP_BUFFER_MARGIN_MM,
                   "selection": "supported filled F.Cu gr_circle geometry fully covered by W=V inset by edge guard, diameter >= threshold",
                   "crop_edge_guard_mm": CROP_EDGE_GUARD_MM,
                   "priority": "ascending source-coordinate centroid Y, then X, then source identity",
                   "EDIT_available_to_constructor": False},
        "decisions": decisions,
        "dynamic_adaptation_event_count": event_count,
        "static_baseline": static,
        "total_growth_area_mm2": sum(d["accepted_area_delta_mm2"] for d in decisions),
        "scope_limit": "Geometry-only local demonstration. No net, pad identity, electrical, manufacturing, or whole-board claim.",
    }


def run_static(inv, V, H, circles, protected):
    decisions = []
    rows = list(inv_rows(inv, H))
    for order, (obj, core, diameter) in enumerate(circles):
        nominal = core.buffer(GROWTH_CAP_MM, quad_segs=32)
        addition = nominal.difference(core)
        for other_obj, obstacle in rows:
            if other_obj["id"] == obj["id"]:
                continue
            addition = addition.difference(obstacle.buffer(PROTECTED_GAP_MM, quad_segs=8))
            if addition.is_empty:
                break
        attached = [p for p in _components(addition) if p.distance(core) <= 1e-7]
        candidate = unary_union([core, *attached]) if attached else core
        decisions.append({"source_id": obj["id"], "accepted_area_delta_mm2": max(0, candidate.area-core.area),
                          "candidate_wkb": to_wkb(candidate).hex()})
    return {"policy": "same source order and protected ORG geometry; no prior accepted circle updates",
            "decisions": decisions,
            "total_growth_area_mm2": sum(d["accepted_area_delta_mm2"] for d in decisions)}


def inv_rows(inv, H):
    for obj in inv["objects"]:
        if "F.Cu" in obj["layers"] and obj["geometry_sha256"]:
            geom = from_wkb(inv["payloads"][obj["geometry_sha256"]])
            if geom.intersects(H):
                yield obj, geom
