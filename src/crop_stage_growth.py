"""Growth-only stage checks: each stage must discharge its own geometry changes.

Historical T01/T02 materializers remain unchanged. These helpers implement the
revised, pairwise F.Cu geometric contract without inferring electrical nets.
"""
from __future__ import annotations

from src.clearance_policy import HARD_GAP_MM, CONSTRUCTION_GAP_MM, CONTACT_BUFFER_MM, LEGACY_CONSTRUCTION_MM, BARRIER_GAP_MM
from dataclasses import dataclass
from math import hypot

from shapely import STRtree
from shapely.affinity import scale
from shapely.geometry import Point
from .crop_attachment_support import qualify_original_support


@dataclass(frozen=True)
class GrowthContract:
    hard_gap_mm: float = HARD_GAP_MM
    construction_gap_mm: float = CONSTRUCTION_GAP_MM
    comparison_epsilon_mm: float = 1e-12
    area_epsilon_mm2: float = 1e-12
    attachment_buffer_gap_mm: float = CONTACT_BUFFER_MM
    quad_segs: int = 128
    search_steps: int = 36


def original_attachment_port(core, obstacle, trace_width_mm, contract):
    """Local permission from an exact original source contact, never a component."""
    if not core.intersects(obstacle):
        return None
    overlap = core.intersection(obstacle)
    return overlap.buffer(max(0.0, trace_width_mm) + contract.attachment_buffer_gap_mm,
                          quad_segs=contract.quad_segs)


def check_proposal(core, candidate, neighbors, *, crop=None, cap=None,
                   contract=GrowthContract(), attachment_supports=()):
    """Check all changed pair relations including corners and endpoints.

    Neighbor records contain current geometry and original source geometry.
    A below-floor original gap may remain unchanged. Any added copper outside a
    source-bound attachment port must meet the construction gap. Existing source
    contacts are preserved by retaining the original core.
    """
    failures = []
    if candidate.is_empty or not candidate.is_valid:
        failures.append({"reason": "INVALID_CANDIDATE"})
        return {"passed": False, "failures": failures, "pairs": []}
    if core.difference(candidate).area > contract.area_epsilon_mm2:
        failures.append({"reason": "SOURCE_CORE_REMOVED"})
    if crop is not None and candidate.difference(crop).area > contract.area_epsilon_mm2:
        failures.append({"reason": "OUTSIDE_VIEWPORT"})
    if cap is not None and candidate.difference(cap).area > contract.area_epsilon_mm2:
        failures.append({"reason": "OUTSIDE_CAP"})
    added = candidate.difference(core)
    pairs = []
    for n in neighbors:
        original = n["original"]
        current = n["geometry"]
        d0 = core.distance(original)
        d1 = candidate.distance(current)
        contact = core.intersects(original)
        port = original_attachment_port(core, original, n.get("trace_width_mm", 0.0), contract)
        support = next((q for q in attachment_supports if q.obstacle_id == n['source_id']), None)
        qualified = (qualify_original_support(core,n,neighbors,support,contract)
                     if support is not None else None)
        if qualified is not None:
            port = qualified['port']
        checked_addition = added if port is None else added.difference(port)
        da = None if checked_addition.is_empty else checked_addition.distance(current)
        reasons = []
        if not contact:
            if candidate.intersects(current):
                reasons.append("NEW_SOURCE_CONTACT")
            if qualified is not None:
                outside_obstacle = current.difference(port)
                outside_gap = None if outside_obstacle.is_empty else candidate.distance(outside_obstacle)
                exposed_addition = added.difference(qualified['feed'].intersection(port))
                exposed_gap = None if exposed_addition.is_empty else exposed_addition.distance(current)
                if outside_gap is not None and outside_gap + contract.comparison_epsilon_mm < contract.hard_gap_mm:
                    reasons.append('OUTSIDE_ORIGINAL_ATTACHMENT_PORT_BELOW_FLOOR')
                if exposed_gap is not None and exposed_gap + contract.comparison_epsilon_mm < contract.construction_gap_mm:
                    reasons.append('EXPOSED_ADDITION_BELOW_CONSTRUCTION_GAP')
            elif d0 >= contract.hard_gap_mm:
                if d1 + contract.comparison_epsilon_mm < contract.hard_gap_mm:
                    reasons.append("INTRODUCED_BELOW_FLOOR_GAP")
            elif d1 + contract.comparison_epsilon_mm < d0:
                reasons.append("WORSENED_PRE_EXISTING_GAP")
        if da is not None and da + contract.comparison_epsilon_mm < contract.construction_gap_mm:
            reasons.append("ADDED_COPPER_BELOW_CONSTRUCTION_GAP_OUTSIDE_PORT")
        row = {"neighbor_id": n["source_id"], "original_surface_gap_mm": d0,
               "candidate_surface_gap_mm": d1, "original_source_contact": contact,
               "attachment_port_area_mm2": None if port is None else port.area,
               "added_copper_gap_outside_port_mm": da, "failures": reasons}
        if qualified is not None:
            row.update(original_attachment_support=qualified['evidence'],
                       candidate_to_obstacle_outside_original_port_gap_mm=outside_gap,
                       exposed_added_copper_to_full_obstacle_gap_mm=exposed_gap)
        pairs.append(row)
        failures.extend({"neighbor_id": n["source_id"], "reason": reason} for reason in reasons)
    return {"passed": not failures, "failures": failures, "pairs": pairs,
            "added_area_mm2": added.area, "source_core_loss_mm2": core.difference(candidate).area}


class GrowthScene:
    """Full-source spatial index with explicit current replacements."""
    def __init__(self, source_objects, contract=GrowthContract()):
        self.contract = contract
        self.objects = {r["source_id"]: r for r in source_objects}
        if len(self.objects) != len(source_objects):
            raise ValueError("DUPLICATE_SOURCE_ID")
        self.ids = sorted(self.objects)
        self.tree = STRtree([self.objects[s]["geometry"] for s in self.ids])
        self.replacements = {}

    def neighbors(self, source_id, cap, aliases=()):
        omit = set(aliases) | {source_id}
        query = cap.buffer(self.contract.construction_gap_mm + 0.001,
                           quad_segs=self.contract.quad_segs)
        ids = {self.ids[int(i)] for i in self.tree.query(query)}
        ids.update(s for s,g in self.replacements.items() if g.intersects(query))
        result = []
        for sid in sorted(ids - omit):
            row = self.objects[sid]
            result.append({"source_id": sid, "original": row["geometry"],
                           "geometry": self.replacements.get(sid, row["geometry"]),
                           "trace_width_mm": row.get("trace_width_mm", 0.0)})
        return result

    def accept(self, source_id, geometry):
        self.replacements[source_id] = geometry


def fit_rectangle(core, neighbors, crop, *, max_factor=1.25,
                  contract=GrowthContract(), attachment_supports=()):
    """Two fixed axis orders; select largest valid result in this bounded search."""
    center = core.centroid
    cap = scale(core, max_factor, max_factor, origin=center)

    def shape(sx, sy):
        return core if sx == sy == 1.0 else scale(core, sx, sy, origin=center)

    def feasible(sx, sy):
        return check_proposal(core, shape(sx, sy), neighbors, crop=crop, cap=cap,
                              contract=contract, attachment_supports=attachment_supports)["passed"]

    def axis(fixed, variable):
        lo, hi = 1.0, max_factor
        for _ in range(contract.search_steps):
            mid = (lo + hi) / 2
            sx, sy = (mid, fixed) if variable == 0 else (fixed, mid)
            if feasible(sx, sy): lo = mid
            else: hi = mid
        return lo

    solutions = [(1.0, 1.0)]
    for first in (0, 1):
        sx = sy = 1.0
        for _ in range(2):
            if first == 0: sx, sy = axis(sy, 0), sy; sy = axis(sx, 1)
            else: sy, sx = axis(sx, 1), sx; sx = axis(sy, 0)
        if feasible(sx, sy): solutions.append((sx, sy))
    sx, sy = max(solutions, key=lambda p: (p[0]*p[1], sum(p), p))
    result = shape(sx, sy)
    return result, (sx, sy), check_proposal(core, result, neighbors, crop=crop, cap=cap,
                                          contract=contract, attachment_supports=attachment_supports)


def fit_round_circle(core, center, original_radius, desired_radius, neighbors, crop,
                     *, contract=GrowthContract()):
    """Preserve roundness and center, retaining the exact source core."""
    if desired_radius > 1.5 * original_radius + contract.comparison_epsilon_mm:
        raise ValueError("CIRCLE_RADIUS_CAP_EXCEEDED")
    cap = Point(*center).buffer(1.5 * original_radius, quad_segs=contract.quad_segs)
    def shape(radius):
        if radius == original_radius: return core
        return Point(*center).buffer(radius, quad_segs=contract.quad_segs).union(core)
    lo, hi = original_radius, desired_radius
    for _ in range(contract.search_steps):
        mid = (lo + hi) / 2
        if check_proposal(core, shape(mid), neighbors, crop=crop, cap=cap, contract=contract)["passed"]:
            lo = mid
        else: hi = mid
    candidate = shape(lo)
    return candidate, lo, check_proposal(core, candidate, neighbors, crop=crop, cap=cap,
                                        contract=contract)
