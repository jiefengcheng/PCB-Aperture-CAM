"""Bounded ORG-only growth of standalone rectangular copper contributions (T02).

This geometric experiment retains every original source contribution. It does not
infer a pad/net identity from graphics and never consumes EDIT contours.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Sequence
from shapely import STRtree, wkb
from shapely.affinity import scale
from shapely.geometry import Polygon
from shapely.ops import unary_union


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


@dataclass(frozen=True)
class RectGrowthPolicy:
    max_axis_factor: float = 1.5
    construction_gap_mm: float = 0.02002
    hard_gap_mm: float = 0.020
    geometry_tolerance_mm: float = 0.00001
    quad_segs: int = 128
    area_epsilon_mm2: float = 1e-10
    side_trace_gap_fraction_of_org: float = 0.5

    def validate(self) -> None:
        if self.max_axis_factor != 1.5:
            raise ValueError("T02_FACTOR_MUST_BE_1_5")
        if self.construction_gap_mm < self.hard_gap_mm:
            raise ValueError("CONSTRUCTION_GAP_BELOW_HARD_GAP")
        if self.quad_segs != 128:
            raise ValueError("T02_CURVE_SETTING_MUST_BE_128")
        if self.side_trace_gap_fraction_of_org != 0.5:
            raise ValueError("T02_SIDE_TRACE_GAP_FRACTION_MUST_BE_ONE_HALF")


def rectangular_feature(row: dict[str, Any], payloads: dict[str, bytes], crop,
                        *, enforce_full_cap_in_crop: bool = True) -> dict[str, Any] | None:
    """Accept only a source-bound rectangle whose full 1.5x envelope fits the crop."""
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
    if enforce_full_cap_in_crop and not crop.covers(scale(geom, xfact=1.5, yfact=1.5, origin=(cx, cy))):
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


def execute(features: list[dict[str, Any]], protected_geometries: list, crop,
            policy: RectGrowthPolicy | None = None,
            side_traces: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Grow each frozen target in deterministic order against the evolving scene."""
    policy = policy or RectGrowthPolicy()
    policy.validate()
    side_traces = side_traces or []
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
        envelope = scale(core, xfact=policy.max_axis_factor, yfact=policy.max_axis_factor, origin=(cx, cy))
        optional = envelope.difference(core)
        # Other original features and accepted earlier additions remain protected.
        local_query = envelope.buffer(policy.construction_gap_mm, quad_segs=policy.quad_segs)
        relevant_traces = []
        trace_keepouts = []
        for trace in side_traces:
            trace_geometry = trace["geometry"]
            if trace_geometry is None or trace_geometry.is_empty or not trace_geometry.intersects(local_query):
                continue
            org_gap = core.distance(trace_geometry)
            required_gap = max(policy.construction_gap_mm,
                               policy.side_trace_gap_fraction_of_org * org_gap)
            relevant_traces.append({
                "source_id": trace["source_id"],
                "source_kind": trace["source_kind"],
                "source_span": list(trace["source_span"]),
                "org_surface_gap_mm": org_gap,
                "required_retained_gap_mm": required_gap,
            })
            trace_keepouts.append(trace_geometry.buffer(required_gap, quad_segs=policy.quad_segs))
        trace_reservation = _union_or_empty(trace_keepouts, crop.difference(crop))
        obstacle_parts = []
        if protected_tree is not None:
            obstacle_parts.extend(protected_geometries[int(i)] for i in sorted(protected_tree.query(local_query)))
        if target_tree is not None:
            obstacle_parts.extend(originals[int(i)] for i in sorted(target_tree.query(local_query)) if originals[int(i)] is not core)
        base_obstacles = unary_union(obstacle_parts) if obstacle_parts else crop.difference(crop)
        baseline_blocked = _union_or_empty([
            base_obstacles.buffer(policy.construction_gap_mm, quad_segs=policy.quad_segs),
            trace_reservation,
        ], crop.difference(crop))
        prior_neighbors = {sid:g for sid,g in accepted_by_source.items() if g.intersects(local_query)}
        obstacle_parts.extend(prior_neighbors.values())
        obstacles = unary_union(obstacle_parts) if obstacle_parts else crop.difference(crop)
        buffered = _union_or_empty([
            obstacles.buffer(policy.construction_gap_mm, quad_segs=policy.quad_segs),
            trace_reservation,
        ], crop.difference(crop))
        permitted = optional.difference(buffered)
        baseline_permitted = optional.difference(baseline_blocked)
        causal_neighbors = []
        for neighbor_id in prior_neighbors:
            cf_obstacles = [base_obstacles, *(g for key,g in prior_neighbors.items() if key != neighbor_id)]
            cf_union = unary_union(cf_obstacles)
            cf_blocked = _union_or_empty([
                cf_union.buffer(policy.construction_gap_mm, quad_segs=policy.quad_segs),
                trace_reservation,
            ], crop.difference(crop))
            cf_permitted = optional.difference(cf_blocked)
            changed_area = cf_permitted.difference(permitted).area
            if changed_area > policy.area_epsilon_mm2:
                causal_neighbors.append({"source_id":neighbor_id,"removed_only_this_prior_addition_area_mm2":changed_area})
        prior_clipped_area = baseline_permitted.difference(permitted).area
        connected, detached = _connected_growth(permitted, core, policy.geometry_tolerance_mm)
        addition = connected.difference(core)
        candidate = core.union(addition)
        # Exact post-assembly invariants.
        lost_core = core.difference(candidate).area
        outside_cap = candidate.difference(envelope).area
        min_gap = addition.distance(obstacles) if not addition.is_empty and not obstacles.is_empty else None
        trace_gap_checks = [
            addition.distance(trace["geometry"]) + policy.geometry_tolerance_mm
                >= reservation["required_retained_gap_mm"]
            for reservation in relevant_traces
            for trace in side_traces
            if trace["source_id"] == reservation["source_id"]
        ]
        min_trace_gap = min((addition.distance(trace["geometry"])
                             for reservation in relevant_traces
                             for trace in side_traces
                             if trace["source_id"] == reservation["source_id"]), default=None)
        checks = {
            "source_core_preserved": lost_core <= policy.area_epsilon_mm2,
            "inside_1_5x_axis_envelope": outside_cap <= policy.area_epsilon_mm2,
            "construction_gap_from_protected_objects": min_gap is None or min_gap + policy.geometry_tolerance_mm >= policy.hard_gap_mm,
            "valid_geometry": candidate.is_valid,
            "addition_connected_to_source": all(part.distance(core) <= policy.geometry_tolerance_mm for part in ([addition] if not addition.is_empty else [])),
            "half_org_side_trace_gap_preserved": all(trace_gap_checks),
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
            "accepted_bounds_mm": list(candidate.bounds), "added_area_mm2": addition.area,
            "candidate_geometry_sha256": hashlib.sha256(candidate.wkb).hexdigest(),
            "discarded_detached_piece_count": len(detached), "minimum_gap_to_original_protected_copper_mm": min_gap,
            "minimum_gap_to_nearby_org_side_traces_mm": min_trace_gap,
            "trace_gap_reservations": relevant_traces,
            "prior_t02_neighbor_clipped_area_mm2": prior_clipped_area,
            "causal_prior_t02_neighbors": causal_neighbors,
            "verification": checks,
        })
    return {"policy": policy, "decisions": decisions,
            "accepted_additions": scene_additions,
            "accepted_additions_by_source": accepted_by_source,
            "candidates_by_source": candidate_by_source,
            "accepted_addition_union": unary_union(scene_additions) if scene_additions else crop.difference(crop),
            "order_source_ids": [f["source_id"] for f in order]}
