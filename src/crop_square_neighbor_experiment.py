"""Isolated square-guided recession experiment; no EDIT-derived construction.

The supporting line of the enlarged circle's inscribed square consumes optional
copper on a conflicting neighbor-facing lobe. This is a provisional mechanism,
not the frozen T01 engine or a qualified CAM sizing policy.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from shapely import to_wkb
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union


@dataclass(frozen=True)
class Settings:
    construction_gap_mm: float = 0.025
    hard_gap_mm: float = 0.020
    orientation_degrees: float = 0.0
    quad_segs: int = 128
    area_epsilon_mm2: float = 1e-10
    event_epsilon_mm2: float = 1e-8


def geometry_hash(geometry):
    return hashlib.sha256(to_wkb(geometry, byte_order=1)).hexdigest()


def inscribed_square(center, enlarged_radius, *, orientation_degrees=0.0):
    """Derive all four corners from the pre-clipping analytic envelope."""
    if enlarged_radius <= 0 or not math.isfinite(enlarged_radius):
        raise ValueError("INVALID_ENLARGED_RADIUS")
    if not math.isfinite(orientation_degrees):
        raise ValueError("NONFINITE_SQUARE_ORIENTATION")
    cx, cy = center
    h = enlarged_radius / math.sqrt(2)
    if orientation_degrees % 360 == 0:
        return Polygon([(cx-h, cy-h), (cx+h, cy-h),
                        (cx+h, cy+h), (cx-h, cy+h)])
    angle = math.radians(orientation_degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    return Polygon([(cx+x*cosine-y*sine, cy+x*sine+y*cosine)
                    for x, y in ((-h,-h),(h,-h),(h,h),(-h,h))])


def facing_square_side(square, center, neighbor_center):
    """Choose the outward side normal most aligned with the actual neighbor."""
    dx, dy = neighbor_center[0]-center[0], neighbor_center[1]-center[1]
    if math.hypot(dx, dy) <= 1e-12:
        raise ValueError("COINCIDENT_NEIGHBOR_CENTERS")
    vertices = list(square.exterior.coords)[:4]
    options = []
    # Preserve the zero-angle +X,+Y,-X,-Y tie order in square-local axes.
    for index, label in ((1,"+X"),(2,"+Y"),(3,"-X"),(0,"-Y")):
        a, b = vertices[index], vertices[(index+1)%4]
        ex, ey = b[0]-a[0], b[1]-a[1]
        length = math.hypot(ex, ey)
        if length <= 1e-12:
            raise ValueError("DEGENERATE_SQUARE_SIDE")
        normal = (ey/length, -ex/length)
        options.append({"label": label, "index": index, "vertices": [a,b],
                        "normal": normal,
                        "midpoint": ((a[0]+b[0])/2,(a[1]+b[1])/2),
                        "alignment": normal[0]*dx+normal[1]*dy})
    return max(enumerate(options), key=lambda item: (item[1]["alignment"],-item[0]))[1]


def square_facing_lobe(envelope, square, center, neighbor_center):
    """Consume the selected supporting line, including rotated square sides."""
    chosen = facing_square_side(square, center, neighbor_center)
    side = chosen["label"]
    minx, miny, maxx, maxy = square.bounds
    ex0, ey0, ex1, ey1 = envelope.bounds
    margin = max(ex1-ex0, ey1-ey0, 1.0)
    vertices = list(square.exterior.coords)[:4]
    axis_aligned = all(abs(a[0]-b[0]) <= 1e-15 or abs(a[1]-b[1]) <= 1e-15
                       for a,b in zip(vertices,vertices[1:]+vertices[:1]))
    if not axis_aligned:
        nx, ny = chosen["normal"]
        tx, ty = -ny, nx
        mx, my = chosen["midpoint"]
        a = (mx+tx*margin,my+ty*margin)
        b = (mx-tx*margin,my-ty*margin)
        halfplane = Polygon([a,b,(b[0]+2*margin*nx,b[1]+2*margin*ny),
                             (a[0]+2*margin*nx,a[1]+2*margin*ny)])
        return envelope.intersection(halfplane), side
    nx,ny = chosen["normal"]
    world_side = max(((nx,"+X"),(ny,"+Y"),(-nx,"-X"),(-ny,"-Y")),key=lambda value:value[0])[1]
    if world_side == "+X":
        halfplane = box(maxx, ey0-margin, ex1+margin, ey1+margin)
    elif world_side == "-X":
        halfplane = box(ex0-margin, ey0-margin, minx, ey1+margin)
    elif world_side == "+Y":
        halfplane = box(ex0-margin, maxy, ex1+margin, ey1+margin)
    else:
        halfplane = box(ex0-margin, ey0-margin, ex1+margin, miny)
    return envelope.intersection(halfplane), side


def largest_feasible_round(core, center, source_radius, radius_ceiling, obstacles,
                           *, settings=Settings(), search_steps=40, safety_mm=0.00002):
    """Select a complete round contour; never accept an asymmetrically clipped one."""
    if not (0 < source_radius <= radius_ceiling and safety_mm >= 0):
        raise ValueError("INVALID_ROUND_RADIUS_RANGE")
    exclusions = []
    for row in obstacles:
        excluded = row["geometry"].buffer(settings.construction_gap_mm,quad_segs=settings.quad_segs)
        if row.get("port_zone") is not None:
            excluded = excluded.difference(row["port_zone"])
        exclusions.append(excluded)
    forbidden = unary_union(exclusions)
    def feasible(radius):
        disc = Point(*center).buffer(radius,quad_segs=settings.quad_segs)
        return disc.difference(core).intersection(forbidden).area <= settings.area_epsilon_mm2
    lower, upper = source_radius, radius_ceiling
    cap_feasible = feasible(upper)
    if cap_feasible:
        selected = upper
    else:
        for _ in range(search_steps):
            midpoint = (lower+upper)/2
            if feasible(midpoint):
                lower = midpoint
            else:
                upper = midpoint
        selected = max(source_radius,lower-safety_mm)
    candidate = Point(*center).buffer(selected,quad_segs=settings.quad_segs)
    if selected-source_radius <= safety_mm or core.difference(candidate).area > settings.area_epsilon_mm2:
        candidate, selected = core, source_radius
    if not candidate.is_valid or core.difference(candidate).area > settings.area_epsilon_mm2:
        raise AssertionError("ROUND_PRIORITY_CORE_LOSS")
    residual = max(abs(math.dist(center,point)-selected)
                   for point in candidate.exterior.coords)
    if residual > 0.00002:
        raise AssertionError("ROUND_PRIORITY_NOT_ROUND")
    return {"candidate":candidate,"radius_mm":selected,"radius_ceiling_mm":radius_ceiling,
            "roundness_residual_mm":residual,"cap_feasible":cap_feasible,
            "search_steps":search_steps,"safety_mm":safety_mm,
            "decision":"ROUND_GROW" if selected>source_radius+safety_mm else "KEEP_ROUND"}


def polygon_parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [part for part in getattr(geometry, "geoms", ())
            if part.geom_type == "Polygon"]


def retain_attached(optional, core, settings):
    parts = polygon_parts(optional)
    attached = [part for part in parts
                if part.area > settings.area_epsilon_mm2
                and part.distance(core) <= 1e-9]
    return unary_union([core, *attached]), len(parts)-len(attached)


def construct(core, center, enlarged_radius, obstacles, *,
              earlier_neighbor_id=None, earlier_neighbor_center=None,
              square_enabled=True, settings=Settings()):
    """Apply square lobe recession before ordinary obstacle constraints.

    Obstacles are dictionaries with source_id, geometry and optional port_zone.
    Port zones permit only source-existing attached segment/arc contacts. The
    original core is retained even where preexisting copper touches it.
    """
    if enlarged_radius <= 0:
        raise ValueError("INVALID_ENLARGED_RADIUS")
    envelope = Point(*center).buffer(enlarged_radius, quad_segs=settings.quad_segs)
    if core.difference(envelope).area > settings.area_epsilon_mm2:
        raise ValueError("ENVELOPE_DOES_NOT_CONTAIN_SOURCE_CORE")
    square = inscribed_square(center, enlarged_radius,
                              orientation_degrees=settings.orientation_degrees)
    optional = envelope.difference(core)
    exclusions = []
    for row in obstacles:
        excluded = row["geometry"].buffer(settings.construction_gap_mm,
                                          quad_segs=settings.quad_segs)
        if row.get("port_zone") is not None:
            excluded = excluded.difference(row["port_zone"])
        exclusions.append((row["source_id"], excluded))
    neighbor_exclusion = unary_union([excluded for source_id, excluded in exclusions
                                      if source_id == earlier_neighbor_id])
    conflict = optional.intersection(neighbor_exclusion)
    lobe = Polygon()
    removed = Polygon()
    side = None
    if square_enabled and conflict.area > settings.event_epsilon_mm2:
        if earlier_neighbor_center is None:
            raise ValueError("NEIGHBOR_CENTER_REQUIRED_FOR_RECESS")
        lobe, side = square_facing_lobe(envelope, square, center,
                                       earlier_neighbor_center)
        removed = optional.intersection(lobe)
        optional = optional.difference(lobe)
    # Complete applicable source/live obstacle set is applied after recession.
    for _, excluded in exclusions:
        optional = optional.difference(excluded)
    candidate, islands = retain_attached(optional, core, settings)
    if not candidate.is_valid or candidate.is_empty:
        raise AssertionError("INVALID_CANDIDATE")
    if core.difference(candidate).area > settings.area_epsilon_mm2:
        raise AssertionError("SOURCE_CORE_LOSS")
    return {"candidate": candidate, "envelope": envelope, "square": square,
            "neighbor_conflict": conflict, "square_lobe": lobe,
            "square_removed_optional": removed, "square_side": side,
            "square_consumed": side is not None,
            "rejected_islands": islands,
            "enlarged_radius_mm": enlarged_radius,
            "construction_exclusions": exclusions}


def verify_addition(core, candidate, envelope, obstacles, *, settings=Settings()):
    """Check novel copper against actual applicable geometry, preserving ports."""
    addition = candidate.difference(core)
    checks = {"valid": candidate.is_valid and not candidate.is_empty,
              "source_core_preserved": core.difference(candidate).area <= settings.area_epsilon_mm2,
              "inside_declared_envelope": candidate.difference(envelope).area <= settings.area_epsilon_mm2,
              "all_optional_parts_attached": all(part.distance(core) <= 1e-9
                                                 for part in polygon_parts(addition))}
    violations = []
    distances = []
    for row in obstacles:
        protected = row["geometry"]
        gap_region = protected.buffer(settings.hard_gap_mm,
                                      quad_segs=settings.quad_segs)
        if row.get("port_zone") is not None:
            gap_region = gap_region.difference(row["port_zone"])
        intrusion = addition.intersection(gap_region).area
        if intrusion > settings.area_epsilon_mm2:
            violations.append({"source_id": row["source_id"], "intrusion_mm2": intrusion})
        if row.get("port_zone") is None and not addition.is_empty:
            distances.append((addition.distance(protected), row["source_id"]))
    checks["hard_gap_outside_source_attachment_ports"] = not violations
    return {"checks": checks, "passed": all(checks.values()),
            "hard_gap_violations": violations,
            "minimum_unexempted_addition_gap_mm": min(distances)[0] if distances else None,
            "minimum_gap_source_id": min(distances)[1] if distances else None}
