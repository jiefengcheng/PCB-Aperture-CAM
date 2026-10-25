"""Bounded ORG-only growth of standalone rectangular copper contributions (T02).

This geometric experiment retains every original source contribution. It does not
infer a pad/net identity from graphics and never consumes EDIT contours.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Sequence
from shapely import STRtree, wkb
from shapely.affinity import scale
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points, unary_union


def validate_accepted_t01_baseline(
    *,
    owner_decision: dict[str, Any],
    registry_profile: dict[str, Any],
    t01_report: dict[str, Any],
    t01_policy: dict[str, Any],
    target_source_sha256: str,
    target_viewport_mm: Sequence[float],
    report_sha256: str,
    policy_sha256: str,
    scene_sha256: str,
    selection_sha256: str,
) -> None:
    """Fail closed unless an owner-accepted T01 scene binds and covers T02's crop."""
    decision_id = owner_decision.get("decision_id")
    if owner_decision.get("status") != "ACCEPTED_VISUAL_CROP":
        raise ValueError("T01_OWNER_DECISION_NOT_ACCEPTED")
    if registry_profile.get("owner_decision_id") != decision_id:
        raise ValueError("T01_PROFILE_DECISION_BINDING_MISMATCH")
    if registry_profile.get("claims", {}).get("owner_review") != "ACCEPTED_VISUAL_CROP":
        raise ValueError("T01_PROFILE_NOT_OWNER_ACCEPTED")
    if owner_decision.get("source_sha256") != target_source_sha256:
        raise ValueError("T01_OWNER_DECISION_SOURCE_MISMATCH")
    if registry_profile.get("source", {}).get("sha256") != target_source_sha256:
        raise ValueError("T01_PROFILE_SOURCE_MISMATCH")
    if t01_report.get("source_sha256") != target_source_sha256 or t01_policy.get("source_sha256") != target_source_sha256:
        raise ValueError("T01_REPORT_OR_POLICY_SOURCE_MISMATCH")

    expected_report = owner_decision.get("report_sha256")
    expected_policy = owner_decision.get("policy_sha256")
    expected_scene = owner_decision.get("scene_sha256")
    if report_sha256 != expected_report or registry_profile.get("report_sha256") != report_sha256:
        raise ValueError("T01_REPORT_HASH_BINDING_MISMATCH")
    if policy_sha256 != expected_policy or registry_profile.get("policy_sha256") != policy_sha256:
        raise ValueError("T01_POLICY_HASH_BINDING_MISMATCH")
    if scene_sha256 != expected_scene or registry_profile.get("scene_sha256") != scene_sha256:
        raise ValueError("T01_SCENE_HASH_BINDING_MISMATCH")
    if selection_sha256 != registry_profile.get("selection_sha256"):
        raise ValueError("T01_SELECTION_HASH_BINDING_MISMATCH")
    if t01_report.get("selection_sha256") != selection_sha256:
        raise ValueError("T01_REPORT_SELECTION_BINDING_MISMATCH")

    report_viewport = t01_report.get("viewport_mm")
    policy_viewport = t01_policy.get("viewport_mm")
    if not report_viewport or list(report_viewport) != list(policy_viewport or []):
        raise ValueError("T01_REPORT_POLICY_VIEWPORT_MISMATCH")
    if len(target_viewport_mm) != 4 or len(report_viewport) != 4:
        raise ValueError("T01_VIEWPORT_INVALID")
    rx0, ry0, rx1, ry1 = map(float, report_viewport)
    tx0, ty0, tx1, ty1 = map(float, target_viewport_mm)
    tolerance = 1e-9
    if rx0 > tx0 + tolerance or ry0 > ty0 + tolerance or rx1 < tx1 - tolerance or ry1 < ty1 - tolerance:
        raise ValueError("T01_VIEWPORT_DOES_NOT_COVER_T02_CROP")


def bind_source_dispositions(
    inventory_rows: list[dict[str, Any]],
    runtime_rows: list[dict[str, Any]],
    decision_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join T02 decisions onto the frozen, source-bound ORG disposition census.

    Inventory classifications are authoritative for source identity and eligibility;
    this helper only adds the outcome for eligible rectangles. It fails closed when
    the runtime census or the decision set differs from that frozen inventory.
    """
    def unique_by_source(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            source_id = row.get("source_id", row.get("id"))
            if not source_id or source_id in result:
                raise ValueError(f"T02_{label}_SOURCE_ID_INVALID_OR_DUPLICATE")
            result[source_id] = row
        return result

    inventory = unique_by_source(inventory_rows, "INVENTORY")
    runtime = unique_by_source(runtime_rows, "RUNTIME_CENSUS")
    decisions = unique_by_source(decision_rows, "DECISION")
    if set(inventory) != set(runtime):
        raise ValueError("T02_RUNTIME_INVENTORY_DISPOSITION_SET_MISMATCH")
    treated = {source_id for source_id, row in inventory.items()
               if row.get("disposition") == "TREAT"}
    if set(decisions) != treated:
        raise ValueError("T02_DECISION_TARGET_SET_MISMATCH")

    identity_fields = ("source_sha256", "source_span", "source_kind",
                       "source_geometry_sha256")
    merged = []
    for source_id in sorted(inventory):
        source = dict(inventory[source_id])
        live = runtime[source_id]
        for field in identity_fields:
            live_value = live.get(field)
            if field == "source_span" and live_value is not None:
                live_value = list(live_value)
            if source.get(field) != live_value:
                raise ValueError(f"T02_RUNTIME_SOURCE_BINDING_MISMATCH:{field}:{source_id}")
        if source.get("disposition") == "TREAT":
            decision = decisions[source_id]
            source["t02_result"] = {
                "decision": decision["decision"],
                "source_size_mm": decision["source_size_mm"],
                "accepted_size_mm_in_source_axes": decision["accepted_size_mm_in_source_axes"],
                "orientation_radians": decision["orientation_radians"],
                "added_area_mm2": decision["added_area_mm2"],
                "candidate_geometry_sha256": decision["candidate_geometry_sha256"],
                "verification": decision["verification"],
            }
        merged.append(source)
    return merged


@dataclass(frozen=True)
class RectGrowthPolicy:
    max_axis_factor: float = 1.25
    construction_gap_mm: float = 0.02002
    hard_gap_mm: float = 0.020
    geometry_tolerance_mm: float = 0.00001
    quad_segs: int = 128
    area_epsilon_mm2: float = 1e-10
    side_trace_gap_fraction_of_org: float = 0.5
    trace_spacing_mode: str = "surface_side_priority_v15"
    corner_contact_separation_mm: float = 0.00002

    def validate(self) -> None:
        if not 1.0 <= self.max_axis_factor <= 1.5:
            raise ValueError("T02_FACTOR_OUT_OF_AUTHORIZED_RANGE")
        if self.construction_gap_mm < self.hard_gap_mm:
            raise ValueError("CONSTRUCTION_GAP_BELOW_HARD_GAP")
        if self.quad_segs != 128:
            raise ValueError("T02_CURVE_SETTING_MUST_BE_128")
        if not 0.0 <= self.side_trace_gap_fraction_of_org <= 1.0:
            raise ValueError("T02_SIDE_TRACE_GAP_FRACTION_OUT_OF_RANGE")
        if self.trace_spacing_mode != "surface_side_priority_v15":
            raise ValueError("T02_UNSUPPORTED_TRACE_SPACING_MODE")


def rectangular_feature(row: dict[str, Any], payloads: dict[str, bytes], crop,
                        *, enforce_full_cap_in_crop: bool = True,
                        max_axis_factor: float = 1.5) -> dict[str, Any] | None:
    """Accept only a source-bound rectangle whose full configured cap fits the crop."""
    if row.get("kind") != "gr_poly" or "F.Cu" not in row.get("layers", []):
        return None
    if row.get("coverage") != "GEOMETRY_AVAILABLE" or row.get("geometry_role") != "nominal native shape":
        return None
    blob = payloads.get(row.get("geometry_sha256"))
    if not blob:
        return None
    geom = wkb.loads(blob)
    if geom.geom_type != "Polygon" or len(geom.interiors) or not geom.intersects(crop):
        return None
    pts = list(geom.exterior.coords)[:-1]
    if len(pts) != 4 or len(set((round(x, 9), round(y, 9)) for x, y in pts)) != 4:
        return None
    edges = [(pts[(i + 1) % 4][0] - pts[i][0], pts[(i + 1) % 4][1] - pts[i][1]) for i in range(4)]
    eps = 1e-9
    lengths = [math.hypot(dx, dy) for dx, dy in edges]
    if min(lengths) <= eps or abs(lengths[0]-lengths[2]) > eps or abs(lengths[1]-lengths[3]) > eps:
        return None
    dot = edges[0][0]*edges[1][0] + edges[0][1]*edges[1][1]
    if abs(dot) > eps * lengths[0] * lengths[1]:
        return None
    if not math.isclose(geom.area, lengths[0] * lengths[1], rel_tol=0, abs_tol=1e-9):
        return None
    cx, cy = geom.centroid.x, geom.centroid.y
    if enforce_full_cap_in_crop and not crop.covers(scale(geom, xfact=max_axis_factor, yfact=max_axis_factor, origin=(cx, cy))):
        return None
    lengths_mm = [lengths[0], lengths[1]]
    return {"source_id": row["id"], "source_span": list(row["source_span"]),
            "source_sha256": row["source_sha256"], "geometry_sha256": row["geometry_sha256"],
            "net_name": row.get("net_name"), "reference": row.get("reference"),
            "center_mm": [cx, cy], "source_bounds_mm": list(geom.bounds),
            "source_size_mm": lengths_mm,
            "orientation_radians": math.atan2(edges[0][1], edges[0][0]), "source_area_mm2": geom.area,
            "geometry": geom}


def _connected_growth(growth, core, tol):
    """Keep only additions connected to this source core; report discarded islands."""
    if growth.is_empty:
        return growth, []
    parts = list(growth.geoms) if hasattr(growth, "geoms") else [growth]
    keep, discard = [], []
    for part in parts:
        (keep if part.distance(core) <= tol else discard).append(part)
    return (unary_union(keep) if keep else core.difference(core), discard)


def _union_or_empty(geometries, empty):
    items = [g for g in geometries if g is not None and not g.is_empty]
    return unary_union(items) if items else empty


def _projected_size(geometry, center, orientation_radians):
    """Return candidate extents in the rectangle's source-local axes."""
    from shapely.affinity import rotate
    local = rotate(geometry, -math.degrees(orientation_radians), origin=tuple(center))
    return [local.bounds[2] - local.bounds[0], local.bounds[3] - local.bounds[1]]


def _scaled_rectangle(core, center, orientation_radians, xfactor, yfactor):
    """Scale a rectangle along its own axes and preserve its four straight sides."""
    from shapely.affinity import rotate
    local = rotate(core, -math.degrees(orientation_radians), origin=tuple(center))
    local = scale(local, xfact=xfactor, yfact=yfactor, origin=tuple(center))
    return rotate(local, math.degrees(orientation_radians), origin=tuple(center))


def is_side_by_side_trace(core, center, orientation_radians, trace, source_kind,
                          angular_tolerance_degrees=15.0):
    """Identify a straight native trace running alongside a rectangle side.

    Curved arcs and corner-only contacts remain in the non-side-by-side class.
    This geometric label does not infer electrical attachment.
    """
    if source_kind != "segment" or trace.is_empty:
        return False
    if trace.geom_type != "LineString":
        return False
    try:
        coords = list(trace.coords)
        edges = [(coords[i + 1][0] - coords[i][0], coords[i + 1][1] - coords[i][1])
                 for i in range(len(coords) - 1)]
        longest = max(edges, key=lambda edge: math.hypot(*edge))
        length = math.hypot(*longest)
        if length <= 1e-12:
            return False
        tx, ty = longest[0] / length, longest[1] / length
        ux, uy = math.cos(orientation_radians), math.sin(orientation_radians)
        vx, vy = -uy, ux
        alignment = math.cos(math.radians(angular_tolerance_degrees))
        trace_points = coords
        local_points = [((x - center[0]) * ux + (y - center[1]) * uy,
                         (x - center[0]) * vx + (y - center[1]) * vy)
                        for x, y in trace_points]
        tx_min, tx_max = min(p[0] for p in local_points), max(p[0] for p in local_points)
        ty_min, ty_max = min(p[1] for p in local_points), max(p[1] for p in local_points)
        size_x, size_y = _projected_size(core, center, orientation_radians)
        half_x, half_y = size_x / 2.0, size_y / 2.0
        if abs(tx * ux + ty * uy) >= alignment:
            beside_top = ty_min >= half_y and min(tx_max, half_x * 0.8) > max(tx_min, -half_x * 0.8)
            beside_bottom = ty_max <= -half_y and min(tx_max, half_x * 0.8) > max(tx_min, -half_x * 0.8)
            return beside_top or beside_bottom
        if abs(tx * vx + ty * vy) >= alignment:
            beside_right = tx_min >= half_x and min(ty_max, half_y * 0.8) > max(ty_min, -half_y * 0.8)
            beside_left = tx_max <= -half_x and min(ty_max, half_y * 0.8) > max(ty_min, -half_y * 0.8)
            return beside_right or beside_left
    except (AttributeError, ValueError, ZeroDivisionError):
        return False
    return False


def side_trace_copper_region(core, center, orientation_radians, envelope, trace, gap_mm):
    """Return the actual copper beside a side, including short segments and arcs.

    The full capped side span is used, rather than the central 80% of the source
    side. Arc chords are classified locally; an arc cannot receive a blanket
    corner exemption. A source-attached feed is not mistaken for a gap.
    """
    from shapely.affinity import rotate, translate
    copper = trace["geometry"]
    line = trace.get("trace_path_geometry")
    empty = core.difference(core)
    if line is None or line.geom_type != "LineString":
        # Without a qualified source path, nearby disjoint copper remains a
        # conservative side obstacle; it cannot earn a corner-only exemption.
        return (copper if not core.intersects(copper) else empty), ["UNQUALIFIED_TRACE_PATH"]
    def local(g):
        return translate(rotate(g, -math.degrees(orientation_radians), origin=tuple(center)),
                         xoff=-center[0], yoff=-center[1])
    c, e, l, cu = local(core), local(envelope), local(line), local(copper)
    x0, y0, x1, y1 = c.bounds
    ex0, ey0, ex1, ey1 = e.bounds
    width = float(trace.get("width_mm", 0.0))
    if width <= 0 and trace.get("source_kind") == "segment":
        coords = list(l.coords)
        angle = math.atan2(coords[-1][1]-coords[0][1], coords[-1][0]-coords[0][0])
        width = _projected_size(cu, (0, 0), angle)[1]
    if width <= 0:
        raise ValueError("T02_TRACE_WIDTH_UNAVAILABLE:" + trace["source_id"])
    # A pre-existing source contact is an attachment port, not an empty-space
    # gap. Exempt only its local, source-bound neighborhood; an attached arc's
    # other side-facing portions remain constrained.
    original_contact = c.intersection(cu)
    port = (original_contact.buffer(width + gap_mm, quad_segs=128)
            if not original_contact.is_empty else empty)
    reach = gap_mm + width
    strips = {"TOP": box(ex0, y1, ex1, ey1+reach),
              "BOTTOM": box(ex0, ey0-reach, ex1, y0),
              "RIGHT": box(x1, ey0, ex1+reach, ey1),
              "LEFT": box(ex0-reach, ey0, x0, ey1)}
    parts, sides = [], set()
    alignment = math.cos(math.radians(15))
    coords = list(l.coords)
    for a, b in zip(coords, coords[1:]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = math.hypot(dx, dy)
        if length <= 1e-12:
            continue
        labels = ("TOP", "BOTTOM") if abs(dx)/length >= alignment else (
                 ("RIGHT", "LEFT") if abs(dy)/length >= alignment else ())
        for label in labels:
            section = LineString([a, b]).intersection(strips[label])
            if section.length <= 1e-10:
                continue
            actual = section.buffer(width/2, quad_segs=128).intersection(cu)
            if not port.is_empty:
                actual = actual.difference(port)
            if actual.is_empty or actual.distance(e) > gap_mm + 1e-10:
                continue
            parts.append(actual)
            sides.add(label)
    # A disconnected trace approaching the interior of a side is also a side
    # conflict, even when its tangent is oblique rather than parallel.
    if not core.intersects(copper) and copper.distance(envelope) < gap_mm:
        point_on_core, _ = nearest_points(c, cu)
        px, py = point_on_core.x, point_on_core.y
        if ((x0+1e-10 < px < x1-1e-10) or (y0+1e-10 < py < y1-1e-10)):
            parts.append(cu)
            sides.add("SIDE_APPROACH")
    if not parts:
        return empty, []
    region = unary_union(parts)
    # `local()` first rotates around the board-space center, then translates
    # that center to the origin. Invert those operations in reverse order:
    # rotate about the origin, then translate back to the board-space center.
    region = rotate(region, math.degrees(orientation_radians), origin=(0, 0))
    return translate(region, xoff=center[0], yoff=center[1]), sorted(sides)


def physical_component_index(source_geometries):
    """Label whole-source F.Cu contact components using exact represented contact."""
    ids = sorted(source_geometries)
    geometries = [source_geometries[sid] for sid in ids]
    tree = STRtree(geometries)
    parent = list(range(len(ids)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, geometry in enumerate(geometries):
        for j in tree.query(geometry, predicate="intersects"):
            j = int(j)
            if j > i:
                a, b = find(i), find(j)
                if a != b:
                    parent[max(a, b)] = min(a, b)
    members = {}
    for i, sid in enumerate(ids):
        members.setdefault(find(i), []).append(sid)
    component_ids = {key: "PC-" + hashlib.sha256("\n".join(value).encode()).hexdigest()[:12]
                     for key, value in members.items()}
    labels = {sid: component_ids[find(i)] for i, sid in enumerate(ids)}
    return labels, {component_ids[key]: value for key, value in members.items()}


def validate_component_preservation(source_geometries, component_by_source, additions_by_source):
    """Check all source-member relationships after additions, including point bridges.

    Original geometry is immutable, so additions cannot split a source component.
    Checking every addition against full-board source and other additions proves
    that no two distinct original component labels acquire physical contact.
    """
    ids = sorted(source_geometries)
    geometries = [source_geometries[sid] for sid in ids]
    tree = STRtree(geometries)
    bridges, new_contacts = [], []
    add_ids = sorted(additions_by_source)
    add_geometries = [additions_by_source[sid] for sid in add_ids]
    add_tree = STRtree(add_geometries) if add_geometries else None
    for sid, addition in zip(add_ids, add_geometries):
        own = component_by_source[sid]
        for i in tree.query(addition, predicate="intersects"):
            other_id = ids[int(i)]
            if other_id != sid and not source_geometries[sid].intersects(source_geometries[other_id]):
                new_contacts.append({"target_source_id": sid, "other_source_id": other_id,
                                     "same_original_component": component_by_source[other_id] == own})
            if component_by_source[other_id] != own:
                bridges.append({"target_source_id": sid, "other_source_id": other_id,
                                "target_component": own, "other_component": component_by_source[other_id]})
        for i in add_tree.query(addition, predicate="intersects"):
            other_id = add_ids[int(i)]
            if other_id > sid and component_by_source[other_id] != own:
                bridges.append({"target_source_id": sid, "other_addition_source_id": other_id,
                                "target_component": own, "other_component": component_by_source[other_id]})
    return {"status": "FAIL_NEW_COMPONENT_CONNECTION" if bridges else "FAIL_NEW_SOURCE_CONTACT" if new_contacts else
                      "PASS_SOURCE_COMPONENT_AND_CONTACTS_PRESERVED",
            "source_count": len(ids), "source_component_count": len(set(component_by_source.values())),
            "new_component_connections": bridges, "new_component_connection_count": len(bridges),
            "new_source_contacts": new_contacts, "new_source_contact_count": len(new_contacts),
            "scope": "whole-board native F.Cu source contact partition, including point contacts; shared parser/kernel, not electrical net intent"}


def future_trace_overlap_records(candidate, core, trace_rows):
    """Record T02 corner/non-side trace overlaps as deferred future-trace work.

    Trace copper is deliberately not modified here. Each record binds the
    interaction to the ORG trace identity and reports the candidate overlap so
    a later, separately authorized trace task can assess it.
    """
    growth = candidate.difference(core)
    records = []
    for trace in trace_rows:
        copper = trace.get("geometry")
        if copper is None or copper.is_empty:
            continue
        intersection = growth.intersection(copper)
        if intersection.is_empty or intersection.area <= 1e-12:
            continue
        records.append({
            "trace_source_id": trace["source_id"],
            "trace_source_kind": trace["source_kind"],
            "trace_source_span": list(trace["source_span"]),
            "trace_geometry_sha256": trace.get("geometry_sha256"),
            "interaction_class": ("SIDE_BY_SIDE_SURFACE_GAP_CONSTRAINED"
                                  if trace.get("side_by_side") else "NON_SIDE_DEFERRED"),
            "overlap_area_mm2": intersection.area,
            "growth_trace_copper_intersection_wkb_sha256": hashlib.sha256(intersection.wkb).hexdigest(),
            "disposition": "DEFERRED_TO_FUTURE_TRACE_SESSION",
            "trace_changed_in_t02": False,
        })
    return records


def trace_clearance_work_items(candidate, core, envelope, trace_rows, *, policy,
                               target_component=None, component_by_source=None):
    """Keep source-bound near-gap issues as well as positive-area intersections."""
    items = []
    growth = candidate.difference(core)
    for trace in trace_rows:
        copper = trace["geometry"]
        if copper.distance(envelope) > policy.construction_gap_mm:
            continue
        attached = core.intersects(copper)
        side_copper, sides = side_trace_copper_region(
            core, core.centroid.coords[0], trace.get("rectangle_orientation_radians", 0),
            envelope, trace, policy.construction_gap_mm)
        original_gap, final_gap = core.distance(copper), candidate.distance(copper)
        overlap = growth.intersection(copper)
        side_gap = candidate.distance(side_copper) if not side_copper.is_empty else None
        baseline_side_gap = core.distance(side_copper) if not side_copper.is_empty else None
        # Geometry comparison tolerance does not waive the owner's hard
        # minimum. A baseline side gap below the floor stays OPEN even when
        # its shortfall is smaller than the comparison tolerance.
        if side_gap is not None and side_gap < policy.hard_gap_mm:
            issue = "SOURCE_SIDE_GAP_REQUIRES_FUTURE_TRACE_REPAIR"
        elif attached and overlap.area > 1e-12:
            issue = "EXISTING_ATTACHMENT_EXTENSION_REVIEW"
        elif ((not growth.is_empty and growth.distance(copper) + policy.geometry_tolerance_mm < policy.hard_gap_mm)
              or (side_copper.is_empty and original_gap < policy.hard_gap_mm)):
            issue = ("EXISTING_ATTACHMENT_EXTENSION_REVIEW" if attached else
                     "CORNER_OVERLAP_REQUIRES_FUTURE_TRACE_REVIEW" if overlap.area > 1e-12 else
                     "CORNER_NEAR_GAP_REQUIRES_FUTURE_TRACE_REVIEW")
        else:
            continue
        other_component = component_by_source.get(trace["source_id"]) if component_by_source else None
        assessed_gap = final_gap if side_gap is None else side_gap
        floor_assessment = ("AT_OR_ABOVE_HARD_FLOOR" if assessed_gap >= policy.hard_gap_mm else
                            "BELOW_HARD_FLOOR_WITHIN_COMPARISON_TOLERANCE"
                            if assessed_gap + policy.geometry_tolerance_mm >= policy.hard_gap_mm else
                            "BELOW_HARD_FLOOR_BEYOND_COMPARISON_TOLERANCE")
        item = {"trace_source_id": trace["source_id"],
                      "trace_source_span": list(trace["source_span"]),
                      "trace_geometry_sha256": trace.get("geometry_sha256"),
                      "issue_type": issue, "status": "OPEN_FUTURE_TRACE_SESSION",
                      "original_attachment": attached, "side_labels": sides,
                      "original_surface_gap_mm": original_gap, "final_surface_gap_mm": final_gap,
                      "final_side_surface_gap_mm": side_gap,
                      "original_side_surface_gap_mm": baseline_side_gap,
                      "side_gap_below_hard_floor": side_gap is not None and side_gap < policy.hard_gap_mm,
                      "hard_floor_assessment": floor_assessment,
                      "required_safe_gap_mm": policy.hard_gap_mm,
                      "overlap_area_mm2": overlap.area,
                      "overlap_wkb_sha256": hashlib.sha256(overlap.wkb).hexdigest(),
                      "target_component": target_component, "trace_component": other_component,
                      "disposition": "DEFERRED_TO_FUTURE_TRACE_SESSION",
                      "trace_changed_in_t02": False, "repair_applied": False,
                      "repair_choice": "UNDECIDED; a later trace task must inspect the source-bound interaction"}
        items.append(item)
    return items


def grow_covered_circles(sites, source_rows, source_geometries, final_parents, crop,
                         diameter_classes_mm, max_factor=1.5):
    """T02-local latent T01 pass: largest round class fully inside one parent.

    Parents are identified from ORG coverage, then use that same parent's final
    T02 contour. This pass adds no copper outside existing parent occupation.
    It neither changes accepted T01 artifacts nor uses component multiplicity.
    """
    row_by_id = {row["id"]: row for row in source_rows}
    ids = sorted(source_geometries)
    tree = STRtree([source_geometries[sid] for sid in ids])
    records, geometries = [], {}
    for site in sites:
        core, sid = site["core"], site["source_id"]
        aliases = set(site["aliases"])
        nearby = [ids[int(i)] for i in tree.query(core, predicate="intersects") if ids[int(i)] not in aliases]
        parents = sorted(pid for pid in nearby if source_geometries[pid].covers(core))
        if not parents:
            continue
        cap_diameter = 2 * site["radius"] * max_factor
        choices = []
        considered = []
        for diameter in sorted(set(map(float, diameter_classes_mm)), reverse=True):
            if diameter <= 2 * site["radius"] + 1e-12:
                continue
            candidate = Point(*site["center"]).buffer(diameter/2, quad_segs=128)
            admissible_parents = [pid for pid in parents
                                  if final_parents.get(pid, source_geometries[pid]).covers(candidate)]
            reason = ("EXCEEDS_1_5X_CAP" if diameter > cap_diameter + 1e-12 else
                      "SOURCE_CORE_NOT_COVERED" if not candidate.covers(core) else
                      "CROSSES_CROP" if not crop.covers(candidate) else
                      "NOT_FULLY_COVERED_BY_ONE_FINAL_PARENT" if not admissible_parents else "ADMISSIBLE")
            considered.append({"diameter_mm": diameter, "status": reason,
                               "covering_parent_source_ids": admissible_parents})
            if reason == "ADMISSIBLE":
                choices.append((diameter, admissible_parents[0], candidate))
        if choices:
            diameter, parent_id, candidate = choices[0]
        else:
            diameter, parent_id, candidate = 2*site["radius"], parents[0], core
        parent = final_parents.get(parent_id, source_geometries[parent_id])
        if not parent.covers(candidate) or not candidate.covers(core):
            raise ValueError("T02_COVERED_CIRCLE_CONTAINMENT_OR_CORE_LOSS:" + sid)
        geometries[sid] = candidate
        records.append({"source_id": sid, "aliases": sorted(aliases),
                        "source_spans": [list(row_by_id[a]["source_span"]) for a in sorted(aliases)],
                        "source_geometry_sha256": site["geometry_sha256"],
                        "center_mm": list(site["center"]), "source_radius_mm": site["radius"],
                        "maximum_diameter_mm": cap_diameter,
                        "selected_diameter_mm": diameter,
                        "selected_shared_class_mm": diameter if choices else None,
                        "decision": "COVERED_ROUND_GROW" if choices else "KEEP_NO_LARGER_ADMISSIBLE_CLASS",
                        "treatment_multiplicity": "UNIQUE_COVERED_SITE; no physical component inference",
                        "parent_source_id": parent_id, "parent_source_span": list(row_by_id[parent_id]["source_span"]),
                        "parent_final_geometry_sha256": hashlib.sha256(parent.wkb).hexdigest(),
                        "original_covering_parent_source_ids": parents,
                        "category_candidates": considered,
                        "candidate_geometry_sha256": hashlib.sha256(candidate.wkb).hexdigest(),
                        "visible_added_copper_mm2": candidate.difference(parent).area,
                        "checks": {"source_core_preserved": candidate.covers(core),
                                   "fully_covered_by_one_final_parent": parent.covers(candidate),
                                   "center_preserved": candidate.centroid.distance(Point(*site["center"])) < 1e-10,
                                   "cap_preserved": diameter <= cap_diameter + 1e-12,
                                   "largest_admissible_class": not choices or diameter == max(c[0] for c in choices),
                                   "round_shape_preserved": not choices or candidate.equals(Point(*site["center"]).buffer(diameter/2, quad_segs=128))}})
    return {"schema": "t02-embedded-covered-circle-pass/1", "records": records,
            "geometries_by_source": geometries, "count": len(records),
            "grown_count": sum(r["decision"] == "COVERED_ROUND_GROW" for r in records),
            "visible_added_copper_mm2": 0.0,
            "all_checks_pass": all(all(r["checks"].values()) for r in records)}


def _largest_clear_rectangle(core, center, orientation_radians, max_factor,
                              obstacles, trace_limits, gap, epsilon):
    """Deterministically maximize rectangle area using bounded axis searches.

    The candidate is always a single scaled rectangle. Nearby copper can limit an
    axis, but cannot carve a recess or create a circle-shaped bite in the contour.
    """
    def feasible(sx, sy):
        candidate = _scaled_rectangle(core, center, orientation_radians, sx, sy)
        growth = candidate.difference(core)
        if growth.is_empty:
            return True
        if not obstacles.is_empty and growth.distance(obstacles) + 1e-12 < gap:
            return False
        return all(growth.distance(trace) + 1e-12 >= required
                   for trace, required in trace_limits)

    def maximize_axis(fixed, variable_axis):
        low, high = 1.0, max_factor
        for _ in range(28):
            mid = (low + high) / 2.0
            pair = (mid, fixed) if variable_axis == 0 else (fixed, mid)
            if feasible(*pair):
                low = mid
            else:
                high = mid
        return low

    solutions = []
    for first_axis in (0, 1):
        sx = sy = 1.0
        for _ in range(4):
            if first_axis == 0:
                sx = maximize_axis(sy, 0)
                sy = maximize_axis(sx, 1)
            else:
                sy = maximize_axis(sx, 1)
                sx = maximize_axis(sy, 0)
        if feasible(sx, sy):
            solutions.append((sx * sy, sx + sy, sx, sy))
    if not solutions:
        factors = (1.0, 1.0)
    else:
        _, _, sx, sy = max(solutions)
        factors = (sx, sy)
    return _scaled_rectangle(core, center, orientation_radians, *factors), factors


def limiting_constraints(
    addition,
    *,
    target_source_id: str,
    source_geometries: dict[str, Any],
    source_metadata: dict[str, dict[str, Any]],
    prior_t02_additions: dict[str, Any],
    trace_reservations: list[dict[str, Any]],
    trace_geometries: dict[str, Any],
    hard_gap_mm: float,
    construction_gap_mm: float,
    tolerance_mm: float,
) -> dict[str, Any]:
    """Name the nearest source objects and tightest recorded clearance margins.

    This is reporting over the already-constructed addition; it does not alter or
    accept geometry. Source identities come from the frozen ORG census and T02
    prior-addition identities come from the deterministic accepted-scene order.
    """
    if addition.is_empty:
        return {
            "nearest_original_protected_source": None,
            "nearest_prior_t02_addition": None,
            "trace_reservations": [],
            "tightest_recorded_constraint": None,
        }

    def nearest(candidates, threshold, constraint_type):
        rows = []
        for source_id, geometry in candidates.items():
            gap = float(addition.distance(geometry))
            meta = source_metadata.get(source_id, {})
            rows.append({
                "constraint_type": constraint_type,
                "source_id": source_id,
                "source_kind": meta.get("kind"),
                "source_span": list(meta.get("source_span", [])),
                "source_geometry_sha256": meta.get("geometry_sha256"),
                "measured_gap_mm": gap,
                "required_gap_mm": threshold,
                "margin_mm": gap - threshold,
                "meets_required_gap_exact": gap + 1e-12 >= threshold,
                "passes_tolerance": gap + tolerance_mm >= threshold,
            })
        return min(rows, key=lambda row: (row["margin_mm"], row["source_id"])) if rows else None

    original_sources = {
        sid: geom for sid, geom in source_geometries.items()
        if sid != target_source_id
    }
    nearest_source = nearest(original_sources, construction_gap_mm,
                             "original_protected_source_construction_gap")
    nearest_prior = nearest(prior_t02_additions, construction_gap_mm, "prior_t02_addition_construction_gap")
    trace_rows = []
    for reservation in trace_reservations:
        source_id = reservation["source_id"]
        geometry = trace_geometries.get(source_id)
        if geometry is None:
            raise ValueError(f"T02_TRACE_RESERVATION_SOURCE_MISSING:{source_id}")
        gap = float(addition.distance(geometry))
        surface_rule = reservation.get("required_surface_gap_mm") is not None
        required = float(reservation["required_surface_gap_mm"] if surface_rule
                         else reservation["required_retained_gap_mm"])
        trace_row = {
            **reservation,
            "source_geometry_sha256": source_metadata.get(source_id, {}).get("geometry_sha256"),
            "measured_final_surface_gap_mm" if surface_rule else "measured_final_gap_mm": gap,
            "clearance_margin_mm": gap - required,
            "meets_required_gap_exact": gap + 1e-12 >= required,
            "passes_tolerance": gap + tolerance_mm >= required,
        }
        trace_rows.append(trace_row)
    tightest = min(
        [row for row in [nearest_source, nearest_prior] if row is not None]
        + [{
            "constraint_type": ("side_by_side_trace_surface_minimum_gap"
                                if row.get("required_surface_gap_mm") is not None and row.get("side_by_side_classification")
                                else "deferred_non_side_trace_interaction"),
            "source_id": row["source_id"],
            "source_kind": row["source_kind"],
            "source_span": row["source_span"],
            "source_geometry_sha256": row.get("source_geometry_sha256"),
            "measured_gap_mm": row.get("measured_final_surface_gap_mm", row.get("measured_final_gap_mm")),
            "required_gap_mm": row.get("required_surface_gap_mm") if row.get("required_surface_gap_mm") is not None else row.get("required_retained_gap_mm"),
            "margin_mm": row["clearance_margin_mm"],
            "meets_required_gap_exact": row["meets_required_gap_exact"],
            "passes_tolerance": row["passes_tolerance"],
        } for row in trace_rows],
        key=lambda row: (row["margin_mm"], row["source_id"]),
    ) if (nearest_source or nearest_prior or trace_rows) else None
    return {
        "nearest_original_protected_source": nearest_source,
        "nearest_prior_t02_addition": nearest_prior,
        "trace_reservations": trace_rows,
        "tightest_recorded_constraint": tightest,
    }


def envelope_constraint_records(candidate, cap, crop, *, accepted_size_mm, maximum_size_mm,
                                policy_sha256: str, tolerance_mm: float,
                                area_epsilon_mm2: float) -> dict[str, Any]:
    """Record the separately checked growth-cap and review-crop boundaries."""
    accepted = [float(value) for value in accepted_size_mm]
    maximum = [float(value) for value in maximum_size_mm]
    active_axes = [axis for axis, (value, limit) in enumerate(zip(accepted, maximum))
                   if abs(value - limit) <= tolerance_mm]
    outside_cap_area = float(candidate.difference(cap).area)
    outside_crop_area = float(cap.difference(crop).area)
    crop_clearance = float(cap.distance(crop.boundary)) if outside_crop_area <= area_epsilon_mm2 else 0.0
    return {
        "policy_cap": {
            "source_id": f"T02_POLICY:{policy_sha256}",
            "source_kind": "maximum_per_axis_growth_envelope",
            "policy_sha256": policy_sha256,
            "maximum_size_mm": maximum,
            "accepted_size_mm": accepted,
            "active_axes": active_axes,
            "outside_cap_area_mm2": outside_cap_area,
            "passes": outside_cap_area <= area_epsilon_mm2,
        },
        "crop_boundary": {
            "source_id": "T02_REVIEW_CROP",
            "source_kind": "full_cap_envelope_review_boundary",
            "crop_bounds_mm": list(crop.bounds),
            "full_cap_inside_crop": outside_crop_area <= area_epsilon_mm2,
            "cap_to_crop_boundary_mm": crop_clearance,
            "passes": outside_crop_area <= area_epsilon_mm2,
            "active": crop_clearance <= tolerance_mm,
        },
    }


def execute(features: list[dict[str, Any]], protected_geometries: list, crop,
            policy: RectGrowthPolicy | None = None,
            side_traces: list[dict[str, Any]] | None = None,
            source_geometries: dict[str, Any] | None = None,
            component_by_source: dict[str, str] | None = None) -> dict[str, Any]:
    """Grow each frozen target in deterministic order against the evolving scene."""
    policy = policy or RectGrowthPolicy()
    policy.validate()
    side_traces = side_traces or []
    surface_mode = True
    side_priority_mode = True
    if component_by_source is not None and source_geometries is None:
        raise ValueError("T02_COMPONENT_GUARD_SOURCE_GEOMETRY_MISSING")
    originals = [f["geometry"] for f in features]
    if len({f["source_id"] for f in features}) != len(features):
        raise ValueError("DUPLICATE_T02_SOURCE_ID")
    scene_additions = []
    accepted_by_source = {}
    candidate_by_source = {}
    order = sorted(features, key=lambda f: (f["center_mm"][1], f["center_mm"][0], f["source_id"]))
    decisions = []
    protected_tree = STRtree(protected_geometries) if protected_geometries else None
    target_tree = STRtree(originals) if originals else None
    accepted_revision = 0
    for feature in order:
        core = feature["geometry"]
        cx, cy = feature["center_mm"]
        envelope = _scaled_rectangle(core, (cx, cy), feature["orientation_radians"],
                                     policy.max_axis_factor, policy.max_axis_factor)
        optional = envelope.difference(core)
        # Other original features and accepted earlier additions remain protected.
        local_query = envelope.buffer(policy.construction_gap_mm, quad_segs=policy.quad_segs)
        relevant_traces = []
        trace_limits = []
        constraint_geometry_by_id = {}
        side_trace_by_id = {trace["source_id"]: trace["geometry"] for trace in side_traces}
        for trace in side_traces:
            trace_geometry = trace["geometry"]
            if trace_geometry is None or trace_geometry.is_empty:
                continue
            if side_priority_mode and trace_geometry.distance(envelope) > policy.construction_gap_mm + policy.geometry_tolerance_mm:
                continue
            org_gap = core.distance(trace_geometry)
            side_copper, side_labels = (side_trace_copper_region(
                core, (cx, cy), feature["orientation_radians"], envelope, trace,
                policy.construction_gap_mm) if side_priority_mode else (None, []))
            side_by_side = not side_copper.is_empty
            # Side-by-side spacing is measured from candidate rectangle copper
            # to the protected trace-copper region. Corner-only interactions
            # remain separate deferred issues; T02 never edits trace geometry.
            foreign_component = bool(component_by_source is not None and
                component_by_source[feature["source_id"]] != component_by_source[trace["source_id"]])
            unattached_corner = side_priority_mode and not side_by_side and not core.intersects(trace_geometry)
            required_gap = (policy.construction_gap_mm if side_by_side else
                            policy.corner_contact_separation_mm if unattached_corner or foreign_component else 0.0)
            constraint_geometry = (side_copper if side_by_side else trace_geometry)
            # A trace only constrains this candidate if the maximum envelope
            # could reduce its original surface gap below the required gap.
            # Buffering by the full ORG gap would incorrectly mark nearly every
            # distant trace as relevant and can flood the receipt with records.
            envelope_trace_distance = trace_geometry.distance(envelope)
            if ((required_gap > 0 and envelope_trace_distance > required_gap + policy.geometry_tolerance_mm)
                    or (required_gap == 0 and envelope_trace_distance > policy.geometry_tolerance_mm)):
                continue
            relevant_traces.append({
                "source_id": trace["source_id"],
                "source_kind": trace["source_kind"],
                "source_span": list(trace["source_span"]),
                "org_surface_gap_mm": org_gap,
                "required_retained_gap_mm": required_gap,
                "required_surface_gap_mm": required_gap if side_by_side else None,
                "constraint_basis": ("SIDE_SURFACE_GAP" if side_by_side else
                                     "FOREIGN_COMPONENT_NO_CONTACT_GUARD" if foreign_component else
                                     "CORNER_NO_NEW_SOURCE_CONTACT" if unattached_corner else
                                     "CORNER_DEFERRED"),
                "side_labels": side_labels,
                "side_by_side_classification": side_by_side,
            })
            constraint_geometry_by_id[trace["source_id"]] = constraint_geometry
            if required_gap > 0:
                trace_limits.append((constraint_geometry, required_gap))
            # The side-specific surface region may contain only part of an
            # arc. Keep every otherwise-disconnected trace copper shape
            # physically separate at corners/endpoints as a topology guard;
            # this guard does not replace or weaken the side surface gap.
            if surface_mode and not core.intersects(trace_geometry):
                trace_limits.append((trace_geometry, policy.corner_contact_separation_mm))
        obstacle_parts = []
        if protected_tree is not None:
            obstacle_parts.extend(protected_geometries[int(i)] for i in sorted(protected_tree.query(local_query))
                                  if not (surface_mode and core.covers(protected_geometries[int(i)])))
        if target_tree is not None:
            obstacle_parts.extend(originals[int(i)] for i in sorted(target_tree.query(local_query)) if originals[int(i)] is not core)
        base_obstacles = unary_union(obstacle_parts) if obstacle_parts else crop.difference(crop)
        prior_neighbors = {sid:g for sid,g in accepted_by_source.items() if g.intersects(local_query)}
        obstacle_parts.extend(prior_neighbors.values())
        obstacles = unary_union(obstacle_parts) if obstacle_parts else crop.difference(crop)
        empty = crop.difference(crop)
        obstacle_union = unary_union(obstacles) if obstacles else empty
        candidate, factors = _largest_clear_rectangle(
            core, (cx, cy), feature["orientation_radians"], policy.max_axis_factor,
            obstacle_union, trace_limits, policy.construction_gap_mm,
            policy.geometry_tolerance_mm)
        causal_neighbors = []
        for neighbor_id in prior_neighbors:
            cf_obstacles = [base_obstacles, *(g for key,g in prior_neighbors.items() if key != neighbor_id)]
            cf_union = unary_union([g for g in cf_obstacles if not g.is_empty]) if any(not g.is_empty for g in cf_obstacles) else empty
            counterfactual_candidate, _ = _largest_clear_rectangle(
                core, (cx, cy), feature["orientation_radians"], policy.max_axis_factor,
                cf_union, trace_limits, policy.construction_gap_mm,
                policy.geometry_tolerance_mm)
            changed_area = counterfactual_candidate.difference(candidate).area
            if changed_area > policy.area_epsilon_mm2:
                causal_neighbors.append({"source_id":neighbor_id,"removed_only_this_prior_addition_area_mm2":changed_area})
        addition = candidate.difference(core)
        detached = []
        prior_clipped_area = max(0.0, (candidate.area - core.area))
        # Exact post-assembly invariants.
        lost_core = core.difference(candidate).area
        outside_cap = candidate.difference(envelope).area
        min_gap = addition.distance(obstacles) if not addition.is_empty and not obstacles.is_empty else None
        trace_gap_checks = [
            addition.is_empty or
            addition.distance(constraint_geometry_by_id[reservation["source_id"]])
                + 1e-12 >= reservation["required_retained_gap_mm"]
            for reservation in relevant_traces
            if reservation["required_retained_gap_mm"] > 0
        ]
        min_trace_gap = min((addition.distance(constraint_geometry_by_id[reservation["source_id"]])
                             for reservation in relevant_traces if reservation["required_retained_gap_mm"] > 0),
                            default=None) if not addition.is_empty else None
        deferred_overlaps = future_trace_overlap_records(candidate, core, [
            {**trace, "side_by_side": next((r["side_by_side_classification"] for r in relevant_traces
                                             if r["source_id"] == trace["source_id"]), False)}
            for trace in side_traces
        ])
        checks = {
            "source_core_preserved": lost_core <= policy.area_epsilon_mm2,
            "inside_configured_per_axis_envelope": outside_cap <= policy.area_epsilon_mm2,
            "construction_gap_from_protected_objects": min_gap is None or min_gap + 1e-12 >= policy.construction_gap_mm,
            "valid_geometry": candidate.is_valid,
            "candidate_is_full_rectangle_without_recess": len(candidate.exterior.coords) == 5 and not candidate.interiors,
            "addition_connected_to_source": all(part.distance(core) <= policy.geometry_tolerance_mm for part in ([addition] if not addition.is_empty else [])),
            "side_surface_gap_and_component_separation_preserved": all(trace_gap_checks),
            "source_center_preserved": candidate.centroid.distance(Point(cx, cy)) <= 1e-10,
        }
        accepted = all(checks.values())
        if accepted and not addition.is_empty:
            scene_additions.append(addition)
            accepted_by_source[feature["source_id"]] = addition
            accepted_revision += 1
        else:
            addition = core.difference(core)
            candidate = core
        candidate_by_source[feature["source_id"]] = candidate
        decisions.append({
            "source_id": feature["source_id"], "source_sha256": feature["source_sha256"],
            "source_span": feature["source_span"], "source_geometry_sha256": feature["geometry_sha256"],
            "decision": "GROW" if accepted and addition.area > policy.area_epsilon_mm2 else "KEEP",
            "input_scene_revision": accepted_revision - (1 if accepted and addition.area > policy.area_epsilon_mm2 else 0), "output_scene_revision": accepted_revision,
            "source_size_mm": feature["source_size_mm"],
            "maximum_size_mm": [x * policy.max_axis_factor for x in feature["source_size_mm"]],
            "orientation_radians": feature["orientation_radians"],
            "accepted_size_mm_in_source_axes": _projected_size(candidate, feature["center_mm"], feature["orientation_radians"]),
            "accepted_axis_scale_factors": list(factors),
            "accepted_bounds_mm": list(candidate.bounds), "added_area_mm2": addition.area,
            "candidate_geometry_sha256": hashlib.sha256(candidate.wkb).hexdigest(),
            "discarded_detached_piece_count": len(detached), "minimum_gap_to_original_protected_copper_mm": min_gap,
            "minimum_gap_to_nearby_org_side_traces_mm": min_trace_gap,
            "trace_gap_reservations": relevant_traces,
            "future_trace_overlap_records": deferred_overlaps,
            "future_trace_clearance_work_items": trace_clearance_work_items(
                candidate, core, envelope,
                [{**trace, "rectangle_orientation_radians": feature["orientation_radians"]} for trace in side_traces],
                policy=policy, target_component=component_by_source.get(feature["source_id"]) if component_by_source else None,
                component_by_source=component_by_source) if side_priority_mode else [],
            "prior_t02_neighbor_clipped_area_mm2": prior_clipped_area,
            "causal_prior_t02_neighbors": causal_neighbors,
            "verification": checks,
        })
    component_audit = (validate_component_preservation(source_geometries, component_by_source, accepted_by_source)
                       if component_by_source is not None else None)
    if component_audit is not None and (component_audit["new_component_connection_count"] or
                                        component_audit["new_source_contact_count"]):
        contact = (component_audit["new_component_connections"] or component_audit["new_source_contacts"])[0]
        target_decision = next(d for d in decisions if d["source_id"] == contact["target_source_id"])
        reservation = next((r for r in target_decision["trace_gap_reservations"]
                           if r.get("source_id") == contact.get("other_source_id")), None)
        raise ValueError("T02_COMPONENT_PRESERVATION_FAILED:" + json.dumps({
            "new_component_connection_count": component_audit["new_component_connection_count"],
            "new_source_contact_count": component_audit["new_source_contact_count"],
            "first_component_connections": component_audit["new_component_connections"][:3],
            "first_new_source_contacts": component_audit["new_source_contacts"][:3],
            "first_contact_reservation": reservation,
            "first_contact_candidate_to_source_gap_mm": accepted_by_source[contact["target_source_id"]].distance(
                source_geometries[contact.get("other_source_id", component_audit["new_component_connections"][0]["other_source_id"])]) if contact.get("other_source_id") else None,
        }, sort_keys=True))
    return {"policy": policy, "decisions": decisions,
            "component_preservation": component_audit,
            "accepted_additions": scene_additions,
            "accepted_additions_by_source": accepted_by_source,
            "candidates_by_source": candidate_by_source,
            "accepted_addition_union": unary_union(scene_additions) if scene_additions else crop.difference(crop),
            "order_source_ids": [f["source_id"] for f in order]}
