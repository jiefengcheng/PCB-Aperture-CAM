"""T01-R1: source-bound circular growth by available local space.

This is a bounded, ORG-only construction experiment.  It is deliberately
separate from the frozen T01 implementation and its receipts.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict

import sexpdata
from shapely import STRtree, from_wkb, to_wkb
from shapely.geometry import Point, box
from shapely.ops import unary_union

from .native_inventory import ERROR_MM, inventory
from .native_reference import one


V_BOUNDS = (1.2858444444444446, -15.687077777777787,
            4.508066666666666, -12.975966666666665)
RADIUS_CLASS_MATCH_TOLERANCE_MM = 0.00002
MAX_GROWTH_REACH_MM = 0.02013  # observed maximum from same-job calibration; policy binds calibration receipt
HARD_GAP_MM = 0.020
GAP_TOLERANCE_MM = 0.00001
CONSTRUCTION_BUFFER_MM = 0.025
PORT_EXTENSION_MM = MAX_GROWTH_REACH_MM
PORT_LATERAL_MARGIN_MM = 0.005
ROUND_OUTLINE_TOLERANCE_MM = 2 * ERROR_MM
AREA_EPSILON_MM2 = 1e-10
EVENT_EPSILON_MM2 = 1e-8
QUAD_SEGS = 32


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _components(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [part for part in getattr(geometry, "geoms", ()) if part.geom_type == "Polygon"]


def _filled_circle(source: bytes, row: dict) -> bool:
    if row["kind"] != "gr_circle":
        return False
    node = sexpdata.loads(source[slice(*row["source_span"])].decode("utf-8"))
    return str(one(node, "fill", ["none"])[0]) in ("yes", "solid")


def _circle_metrics(geometry):
    center = geometry.centroid
    radius = (geometry.bounds[2] - geometry.bounds[0] +
              geometry.bounds[3] - geometry.bounds[1]) / 4
    points = list(geometry.exterior.coords) if geometry.geom_type == "Polygon" else []
    residual = max((abs(math.hypot(x-center.x, y-center.y) - radius)
                    for x, y, *_ in points), default=float("inf"))
    return center, radius, residual


def _source_width(source: bytes, row: dict) -> float | None:
    text = source[slice(*row["source_span"])].decode("utf-8")
    match = re.search(r"\(\s*width\s+([0-9]+(?:\.[0-9]+)?)\s*\)", text)
    return float(match.group(1)) if match else None


def _port_zone(core, trace, trace_width: float | None, reach_mm=MAX_GROWTH_REACH_MM):
    """Bound one source-existing attachment port close to its land core."""
    if not trace.intersects(core.buffer(1e-7, quad_segs=QUAD_SEGS)):
        return None
    lateral = max(PORT_LATERAL_MARGIN_MM,
                  (trace_width or 0.0) / 2 + PORT_LATERAL_MARGIN_MM)
    local = trace.buffer(lateral, quad_segs=QUAD_SEGS).intersection(
        core.buffer(reach_mm, quad_segs=QUAD_SEGS))
    return local if not local.is_empty else None


def _priority_outline(core, port_zone):
    band = core.boundary.buffer(CONSTRUCTION_BUFFER_MM, quad_segs=QUAD_SEGS)
    if port_zone is not None and not port_zone.is_empty:
        band = band.difference(port_zone)
    return band


def _nearest_spacing_bound(core, neighbors, *, clearance_mm=HARD_GAP_MM):
    """Bound growth by the nearest other target's current copper and required gap.

    The returned distance is the maximum isotropic reach that cannot pass the
    nearest neighboring target while leaving ``clearance_mm``.  Directional
    obstacles and trace/priority reservations still clip the actual contour.
    ``neighbors`` contains (source id, geometry) pairs and is evaluated against
    the evolving accepted scene by the caller.
    """
    candidates = [(core.distance(geometry), source_id)
                  for source_id, geometry in neighbors
                  if not geometry.is_empty and not geometry.equals(core)]
    if not candidates:
        return 0.0, None, None
    distance, source_id = min(candidates, key=lambda item: (item[0], item[1]))
    return max(0.0, distance - clearance_mm), source_id, distance


def _site_schedule(sites, priorities, order_policy):
    """Return a deterministic priority-first schedule under an allowed policy."""
    priority_ids = [site_id for _, site_id in sorted(priorities.items())]
    priority_set = set(priority_ids)
    companions = [site for site in sites if site["site_id"] not in priority_set]
    if order_policy == "source_yx":
        companions.sort(key=lambda site: (site["center"].y, site["center"].x,
                                          site["site_id"]))
    elif order_policy == "roomiest_first":
        companions.sort(key=lambda site: (-site["growth_reach_mm"], site["site_id"]))
    else:
        raise ValueError(f"UNSUPPORTED_ORDER_POLICY:{order_policy}")
    return priority_ids + [site["site_id"] for site in companions]


def grow_in_available_space(core, obstacle_rows, *, reach_mm=MAX_GROWTH_REACH_MM,
                            construction_buffer_mm=CONSTRUCTION_BUFFER_MM,
                            port_zones=None, priority_reservations=None):
    """Clip a shared physical reach envelope by actual current obstacles.

    obstacle_rows are (source id, full geometry, role).  Existing target cores
    are protected by the caller.  Only declared local own-trace port zones may
    be removed from a trace's buffered obstacle.
    """
    port_zones = port_zones or {}
    priority_reservations = priority_reservations or []
    envelope = core.buffer(reach_mm, quad_segs=QUAD_SEGS)
    forbidden_rows = []
    for source_id, geometry, role in obstacle_rows:
        zone = port_zones.get(source_id)
        forbidden = geometry.buffer(construction_buffer_mm, quad_segs=QUAD_SEGS)
        if zone is not None and not zone.is_empty:
            forbidden = forbidden.difference(zone)
        if not forbidden.is_empty:
            forbidden_rows.append((source_id, role, forbidden))
    for source_id, reservation in priority_reservations:
        if not reservation.is_empty:
            forbidden_rows.append((source_id, "priority_round_outline", reservation))

    addition = envelope.difference(core)
    for _, _, forbidden in forbidden_rows:
        if addition.is_empty:
            break
        addition = addition.difference(forbidden)
    attached = [part for part in _components(addition)
                if part.distance(core) <= max(1e-9, ERROR_MM / 2)
                and part.area > AREA_EPSILON_MM2]
    rejected_islands = [part for part in _components(addition) if part not in attached]
    candidate = unary_union([core, *attached]) if attached else core
    if forbidden_rows:
        optional = candidate.difference(core)
        for _, _, forbidden in forbidden_rows:
            optional = optional.difference(forbidden)
        attached = [part for part in _components(optional)
                    if part.distance(core) <= max(1e-9, ERROR_MM / 2)
                    and part.area > AREA_EPSILON_MM2]
        candidate = unary_union([core, *attached]) if attached else core
    if not candidate.is_valid or candidate.is_empty:
        raise AssertionError("INVALID_CANDIDATE_GEOMETRY")
    core_loss = core.difference(candidate).area
    if core_loss > 1e-12:
        raise AssertionError(f"PROTECTED_CORE_LOSS:{core_loss}")

    growth = candidate.difference(core)
    limiting = []
    if not growth.is_empty:
        for source_id, role, forbidden in forbidden_rows:
            if growth.distance(forbidden) <= ERROR_MM:
                limiting.append({"source_id": source_id, "role": role})
    cap_shell = envelope.boundary.buffer(ERROR_MM, quad_segs=QUAD_SEGS)
    cap_limited = not growth.is_empty and growth.intersection(cap_shell).length > ERROR_MM
    return {
        "candidate": candidate,
        "envelope": envelope,
        "growth": growth,
        "core_loss_mm2": core_loss,
        "rejected_island_count": len(rejected_islands),
        "limiting_obstacles": limiting,
        "growth_cap_touched": cap_limited,
        "growth_cap_only_limiter": cap_limited and not limiting,
        "area_delta_mm2": max(0.0, candidate.area - core.area),
    }


def _component_membership(seed_indexes, rows, shapes, tree):
    """Full-source transitive same-layer physical connectivity by intersection."""
    membership = {}
    records = {}
    next_id = 0
    for seed in seed_indexes:
        if seed in membership:
            continue
        todo = [seed]
        seen = {seed}
        membership[seed] = next_id
        while todo:
            current = todo.pop()
            for result in tree.query(shapes[current], predicate="intersects"):
                index = int(result)
                if index not in seen:
                    seen.add(index)
                    membership[index] = next_id
                    todo.append(index)
        ids = sorted(rows[index]["id"] for index in seen)
        component_id = "org-fcu-physical-" + _sha("\n".join(ids).encode())[:20]
        records[next_id] = {"id": component_id, "member_indexes": sorted(seen),
                            "source_member_ids": ids}
        next_id += 1
    return membership, records


def _record_forbidden_contact(core, candidate, other_core, tolerance=1e-10):
    """For priority feasibility, only existing segment/arc contacts are ports."""
    outside_ports = core.boundary.intersection(other_core.buffer(tolerance))
    return outside_ports.length > tolerance


def _area_summary(decisions, geometries):
    additions = [geometries[row["site_id"]].difference(row["core"])
                 for row in decisions if row["site_id"] in geometries]
    nonempty = [geometry for geometry in additions if not geometry.is_empty]
    return {
        "sum_of_per_site_additions_mm2": sum(g.area for g in nonempty),
        "union_added_area_mm2": unary_union(nonempty).area if nonempty else 0.0,
        "double_counted_overlap_mm2": sum(g.area for g in nonempty) -
            (unary_union(nonempty).area if nonempty else 0.0),
    }


def run(source: bytes, *, dynamic: bool = True,
        calibrated_radius_limits,
        order_policy: str = "source_yx") -> dict:
    """Run ORG-only construction with nearest-target spacing bounds.

    ``calibrated_radius_limits`` is retained only for descriptive class labels;
    it does not select sites or set a construction reach.
    """
    inv = inventory(source)
    viewport = box(*V_BOUNDS)
    fcu_rows = []
    fcu_shapes = []
    unsupported_candidates = []
    for row in inv["objects"]:
        if "F.Cu" not in row["layers"]:
            continue
        if not row["geometry_sha256"]:
            if row.get("bounds_mm"):
                unsupported_candidates.append((row["id"], box(*row["bounds_mm"])))
            continue
        fcu_rows.append(row)
        fcu_shapes.append(from_wkb(inv["payloads"][row["geometry_sha256"]]))
    tree = STRtree(fcu_shapes)

    # Keep every supported filled circular occurrence whose complete source
    # geometry touches the fixed display viewport.  No radius cutoff or inset W.
    occurrence_groups = defaultdict(list)
    geom_by_hash = {}
    for index, (row, geometry) in enumerate(zip(fcu_rows, fcu_shapes)):
        if _filled_circle(source, row) and geometry.intersects(viewport):
            occurrence_groups[row["geometry_sha256"]].append(index)
            geom_by_hash[row["geometry_sha256"]] = geometry

    sites = []
    for geometry_hash, indexes in occurrence_groups.items():
        aliases = sorted(fcu_rows[index]["id"] for index in indexes)
        primary = aliases[0]
        core = geom_by_hash[geometry_hash]
        center, radius, round_error = _circle_metrics(core)
        radius_class = min(calibrated_radius_limits,
            key=lambda value: abs(value-radius), default=None)
        if radius_class is not None and abs(radius_class-radius) > RADIUS_CLASS_MATCH_TOLERANCE_MM:
            radius_class = None
        sites.append({"site_id": primary, "source_ids": aliases,
                      "geometry_sha256": geometry_hash, "core": core,
                      "center": center, "radius_mm": radius,
                      "radius_class_mm": radius_class,
                      "diameter_mm": radius * 2, "roundness_error_mm": round_error,
                      "indexes": indexes})
    sites.sort(key=lambda site: (site["center"].y, site["center"].x, site["site_id"]))
    if not sites:
        raise ValueError("NO_SUPPORTED_CIRCLES_INTERSECT_FIXED_VIEWPORT")

    site_by_id = {site["site_id"]: site for site in sites}
    # Each target receives a local spacing limit derived from the nearest other
    # target core. This is an outer reach bound; all intervening copper,
    # reserved traces, and priority outlines still clip growth directionally.
    for site in sites:
        neighbors = [(other["site_id"], other["core"]) for other in sites
                     if other["site_id"] != site["site_id"] and
                     other["geometry_sha256"] != site["geometry_sha256"]]
        reach, neighbor_id, spacing = _nearest_spacing_bound(site["core"], neighbors)
        site["growth_reach_mm"] = reach
        site["spacing_bound_source_id"] = neighbor_id
        site["nearest_target_spacing_mm"] = spacing
    row_by_id = {row["id"]: (row, geom, index)
                 for index, (row, geom) in enumerate(zip(fcu_rows, fcu_shapes))}
    site_source_to_id = {source_id: site["site_id"] for site in sites
                         for source_id in site["source_ids"]}
    seed_indexes = sorted({index for site in sites for index in site["indexes"]})
    membership, component_records = _component_membership(seed_indexes, fcu_rows,
                                                            fcu_shapes, tree)
    for site in sites:
        component_numbers = {membership[index] for index in site["indexes"]}
        if len(component_numbers) != 1:
            raise ValueError(f"COLOCATED_SITE_SPLIT_COMPONENT:{site['site_id']}")
        site["component_number"] = next(iter(component_numbers))
        site["component_id"] = component_records[site["component_number"]]["id"]

    # The local write domain is the union of complete source envelopes.  Its
    # influence domain adds the declared construction clearance and precision.
    write_envelopes = [site["core"].buffer(site["growth_reach_mm"], quad_segs=QUAD_SEGS)
                       for site in sites]
    write_domain = unary_union(write_envelopes)
    influence_envelopes = [site["core"].buffer(
        site["growth_reach_mm"] + CONSTRUCTION_BUFFER_MM + ERROR_MM,
        quad_segs=QUAD_SEGS) for site in sites]
    influence_domain = unary_union(influence_envelopes)
    unsupported_influence = [object_id for object_id, bounds in unsupported_candidates
                             if bounds.intersects(influence_domain)]
    local_indexes = set()
    for envelope in influence_envelopes:
        local_indexes.update(int(index) for index in tree.query(envelope))
    local_rows = [(fcu_rows[index], fcu_shapes[index], index)
                  for index in sorted(local_indexes)
                  if fcu_shapes[index].intersects(influence_domain)]
    local_ids = {row["id"] for row, _, _ in local_rows}
    for object_id in unsupported_influence:
        # Unknown F.Cu influence is fail-closed for every target in its bbox.
        local_ids.add(object_id)

    # Build local attachment port evidence from ORG-only trace intersections.
    site_ports = {}
    for site in sites:
        port_geometries = []
        port_trace_ids = set()
        trace_zones = {}
        for row, geometry, _ in local_rows:
            if row["kind"] not in ("segment", "arc"):
                continue
            zone = _port_zone(site["core"], geometry, _source_width(source, row),
                              site["growth_reach_mm"])
            if zone is not None:
                port_geometries.append(zone)
                port_trace_ids.add(row["id"])
                trace_zones[row["id"]] = zone
        site_ports[site["site_id"]] = {
            "geometry": unary_union(port_geometries) if port_geometries else None,
            "trace_ids": sorted(port_trace_ids),
            "trace_zones": trace_zones,
        }

    # One feasible round priority per fully inventoried ORG physical component.
    by_component = defaultdict(list)
    for site in sites:
        by_component[site["component_id"]].append(site)
    priorities = {}
    priority_exceptions = []
    for component_id, component_sites in sorted(by_component.items()):
        ranked = sorted(component_sites, key=lambda site: (-site["radius_mm"], site["site_id"]))
        chosen = None
        for candidate in ranked:
            port_ids = set(site_ports[candidate["site_id"]]["trace_ids"])
            boundary = candidate["core"].boundary
            visible_boundary = boundary
            port_zone = site_ports[candidate["site_id"]]["geometry"]
            if port_zone is not None:
                visible_boundary = boundary.difference(port_zone)
            feasible = candidate["roundness_error_mm"] <= ROUND_OUTLINE_TOLERANCE_MM
            reasons = []
            for row, geometry, _ in local_rows:
                if row["id"] in candidate["source_ids"]:
                    continue
                if row["id"] in port_ids:
                    continue
                if geometry.equals(candidate["core"]):
                    continue
                if visible_boundary.intersection(geometry).length > ERROR_MM:
                    feasible = False
                    reasons.append(row["id"])
            if feasible:
                chosen = candidate
                break
        if chosen is None:
            priority_exceptions.append({"component_id": component_id,
                "site_ids": [site["site_id"] for site in ranked],
                "reason": "NO_ROUND_PRIORITY_WITH_SOURCE_BOUND_PORTS"})
        else:
            priorities[component_id] = chosen["site_id"]
            chosen["priority_selection_reason"] = (
                "largest ORG circular core with qualified source-only round outline; stable source id tie-break")

    priority_by_site = {site_id: component_id for component_id, site_id in priorities.items()}
    priority_reservations = {}
    for component_id, site_id in priorities.items():
        site = site_by_id[site_id]
        zone = _priority_outline(site["core"], site_ports[site_id]["geometry"])
        priority_reservations[site_id] = zone

    # Keep the default frozen schedule; one bounded alternative is available
    # for a source-only order diagnostic. Neither order uses EDIT geometry.
    order = _site_schedule(sites, priorities, order_policy)
    accepted = {}
    decisions_by_id = {}
    scene = 0

    def construct(site, *, evolving):
        source_id = site["site_id"]
        if source_id in priority_by_site:
            return {"candidate": site["core"], "envelope": site["core"],
                    "growth": site["core"].difference(site["core"]),
                    "core_loss_mm2": 0.0, "rejected_island_count": 0,
                    "limiting_obstacles": [], "growth_cap_touched": False,
                    "growth_cap_only_limiter": False,
                    "area_delta_mm2": 0.0, "growth_reach_mm": 0.0,
                    "spacing_bound_source_id": site["spacing_bound_source_id"],
                    "nearest_target_spacing_mm": site["nearest_target_spacing_mm"]}
        port = site_ports[source_id]
        obstacle_rows = []
        for row, original, _ in local_rows:
            other_site_id = site_source_to_id.get(row["id"])
            if other_site_id == source_id:
                continue
            # Exact same-geometry duplicate occurrences are aliases, not obstacles.
            if other_site_id and other_site_id != source_id:
                other = site_by_id[other_site_id]
                if other["geometry_sha256"] == site["geometry_sha256"]:
                    continue
            obstacle = accepted.get(other_site_id, original) if (evolving and other_site_id) else original
            role = "circle_neighbor" if other_site_id else (
                "trace_corridor" if row["kind"] in ("segment", "arc") else "protected_copper")
            obstacle_rows.append((row["id"], obstacle, role))
        spacing_neighbors = [(other_id, accepted.get(other_id, other["core"]) if evolving else other["core"])
            for other_id, other in site_by_id.items()
            if other_id != source_id and
            other["geometry_sha256"] != site["geometry_sha256"]]
        dynamic_reach, spacing_source_id, nearest_spacing = _nearest_spacing_bound(
            site["core"], spacing_neighbors)
        reservations = [(priority_id, zone) for priority_id, zone in priority_reservations.items()
                       if priority_id != source_id]
        port_zones = port["trace_zones"]
        result = grow_in_available_space(site["core"], obstacle_rows,
            reach_mm=dynamic_reach,
            port_zones=port_zones, priority_reservations=reservations)
        result["spacing_bound_source_id"] = spacing_source_id
        result["nearest_target_spacing_mm"] = nearest_spacing
        result["growth_reach_mm"] = dynamic_reach
        result["obstacle_rows"] = obstacle_rows
        return result

    for site_order, site_id in enumerate(order):
        site = site_by_id[site_id]
        source_id = site["site_id"]
        input_scene = scene
        result = construct(site, evolving=dynamic)
        candidate = result["candidate"]
        output_scene = scene + 1
        scene = output_scene
        accepted[source_id] = candidate
        if source_id in priority_by_site:
            status = "KEEP_PRIORITY_ROUND"
        else:
            status = ("GROW" if result["area_delta_mm2"] > AREA_EPSILON_MM2
                else "KEEP_CONSTRAINED")
        center = site["center"]
        decision_reach = result.get("growth_reach_mm", site["growth_reach_mm"])
        decision = {
            "order": site_order, "source_id": source_id,
            "source_occurrence_ids": site["source_ids"],
            "source_span_by_id": {row["id"]: row["source_span"] for row, _, _ in local_rows
                                  if row["id"] in site["source_ids"]},
            "source_sha256": inv["source_sha256"],
            "geometry_sha256": site["geometry_sha256"],
            "center_mm": [center.x, center.y], "original_radius_mm": site["radius_mm"],
            "calibrated_org_radius_class_mm": site["radius_class_mm"],
            "maximum_final_radius_mm": site["radius_mm"] + decision_reach,
            "spacing_bound_source_id": result.get("spacing_bound_source_id", site["spacing_bound_source_id"]),
            "nearest_target_spacing_mm": result.get("nearest_target_spacing_mm", site["nearest_target_spacing_mm"]),
            "original_area_mm2": site["core"].area,
            "physical_component_id": site["component_id"],
            "component_member_count": len(component_records[site["component_number"]]["source_member_ids"]),
            "component_source_member_ids": component_records[site["component_number"]]["source_member_ids"],
            "priority_site_id": priorities.get(site["component_id"]),
            "priority_selection_reason": site.get("priority_selection_reason"),
            "priority_port_trace_ids": site_ports[source_id]["trace_ids"] if source_id in priority_by_site else [],
            "attachment_port_trace_ids": site_ports[source_id]["trace_ids"],
            "port_zone_wkb": to_wkb(site_ports[source_id]["geometry"]).hex()
                if site_ports[source_id]["geometry"] is not None else None,
            "attachment_port_zone_wkb_by_trace": {trace_id: to_wkb(zone).hex()
                for trace_id, zone in sorted(site_ports[source_id]["trace_zones"].items())},
            "priority_outline_wkb": to_wkb(priority_reservations[source_id]).hex()
                if source_id in priority_reservations else None,
            "input_scene_revision": f"t01-r1-scene-{input_scene:03d}",
            "output_scene_revision": f"t01-r1-scene-{output_scene:03d}",
            "original_core_area_mm2": site["core"].area,
            "final_effective_area_mm2": candidate.area,
            "added_area_mm2": result["area_delta_mm2"],
            "protected_core_loss_mm2": result["core_loss_mm2"],
            "maximum_growth_reach_mm": decision_reach,
            "limiting_obstacles": result["limiting_obstacles"],
            "limiting_source_ids": [item["source_id"] for item in result["limiting_obstacles"]],
            "growth_cap_touched": result["growth_cap_touched"],
            "growth_cap_only_limiter": result["growth_cap_only_limiter"],
            "rejected_detached_island_count": result["rejected_island_count"],
            "decision": status,
            "candidate_wkb": to_wkb(candidate).hex(),
            "candidate_radius_max_mm": max((math.hypot(x-center.x, y-center.y)
                for polygon in _components(candidate) for x, y, *_ in polygon.exterior.coords),
                default=site["radius_mm"]),
            "policy": ("round priority core reserved" if source_id in priority_by_site else
                "ORG core plus nearest-target-spacing envelope clipped by current copper, trace reservations, and priority outlines"),
        }
        decisions_by_id[source_id] = decision

    decisions = [decisions_by_id[site_id] for site_id in order]
    dynamic_geometries = {site_id: from_wkb(bytes.fromhex(row["candidate_wkb"]))
                          for site_id, row in decisions_by_id.items()}

    # Fair frozen-neighbor comparator: same source set, schedule, reach, gap,
    # priorities, ports, obstacles and clipping law; only accepted-neighbor
    # updates are withheld.
    static_geometries = {}
    static_decisions = []
    for site_id in order:
        site = site_by_id[site_id]
        result = construct(site, evolving=False)
        static_geometries[site_id] = result["candidate"]
        static_decisions.append({"source_id": site_id,
            "candidate_wkb": to_wkb(result["candidate"]).hex(),
            "added_area_mm2": result["area_delta_mm2"],
            "growth_cap_touched": result["growth_cap_touched"],
            "growth_cap_only_limiter": result["growth_cap_only_limiter"],
            "limiting_obstacles": result["limiting_obstacles"]})

    # Recompute causal evidence against the fair static geometry and retain
    # the exact earlier accepted source objects that changed each candidate.
    causal_events = []
    for decision in decisions:
        source_id = decision["source_id"]
        dynamic_shape = dynamic_geometries[source_id]
        static_shape = static_geometries[source_id]
        difference = dynamic_shape.symmetric_difference(static_shape).area
        decision["dynamic_vs_static_symmetric_difference_mm2"] = difference
        prior_neighbors = []
        for other_id in order[:decision["order"]]:
            other_site = site_by_id[other_id]
            if dynamic_geometries[other_id].equals(other_site["core"]):
                continue
            if dynamic_geometries[other_id].distance(site_by_id[source_id]["core"]) <= site_by_id[source_id]["growth_reach_mm"] + CONSTRUCTION_BUFFER_MM + ERROR_MM:
                prior_neighbors.append(other_id)
        decision["prior_accepted_neighbor_ids"] = prior_neighbors
        decision["adapted_by_prior_acceptance"] = bool(
            difference > EVENT_EPSILON_MM2 and prior_neighbors)
        if decision["adapted_by_prior_acceptance"]:
            causal_events.append(decision)

    # Three controlled single-neighbor counterfactuals; other prior candidates
    # stay at their recorded dynamic geometry.
    counterfactuals = []
    for target in causal_events:
        if len(counterfactuals) == 3:
            break
        target_id = target["source_id"]
        removable = [candidate_id for candidate_id in target["prior_accepted_neighbor_ids"]
                     if not dynamic_geometries[candidate_id].equals(site_by_id[candidate_id]["core"])]
        if not removable:
            continue
        removed_id = removable[0]
        site = site_by_id[target_id]
        port = site_ports[target_id]
        obstacle_rows = []
        for row, original, _ in local_rows:
            other_site_id = site_source_to_id.get(row["id"])
            if other_site_id == target_id:
                continue
            if other_site_id and site_by_id[other_site_id]["geometry_sha256"] == site["geometry_sha256"]:
                continue
            if other_site_id and other_site_id in dynamic_geometries and decisions_by_id[other_site_id]["order"] < target["order"]:
                obstacle = site_by_id[other_site_id]["core"] if other_site_id == removed_id else dynamic_geometries[other_site_id]
            else:
                obstacle = original
            role = "circle_neighbor" if other_site_id else (
                "trace_corridor" if row["kind"] in ("segment", "arc") else "protected_copper")
            obstacle_rows.append((row["id"], obstacle, role))
        reservation_rows = [(pid, zone) for pid, zone in priority_reservations.items() if pid != target_id]
        zones = port["trace_zones"]
        replay = grow_in_available_space(site["core"], obstacle_rows,
            reach_mm=site["growth_reach_mm"], port_zones=zones,
            priority_reservations=reservation_rows)["candidate"]
        recorded = dynamic_geometries[target_id]
        delta = recorded.symmetric_difference(replay).area
        counterfactuals.append({"target_source_id": target_id,
            "removed_prior_source_id": removed_id,
            "other_prior_candidates_held_fixed": True,
            "recorded_added_area_mm2": recorded.difference(site["core"]).area,
            "counterfactual_added_area_mm2": replay.difference(site["core"]).area,
            "symmetric_difference_mm2": delta,
            "causal_change_observed": delta > EVENT_EPSILON_MM2})

    # Assembly checks include source cores, source-connected traces, every
    # dynamic site, and hard gaps against the original source geometry.
    site_source_ids = set(site_source_to_id)
    priority_outline_results = []
    for component_id, site_id in priorities.items():
        site = site_by_id[site_id]
        outline = site["core"].boundary
        ports = site_ports[site_id]["geometry"]
        visible_outline = outline.difference(ports) if ports is not None else outline
        covered_by_growth = 0.0
        for other_id, geom in dynamic_geometries.items():
            if other_id == site_id:
                continue
            covered_by_growth += visible_outline.intersection(geom.difference(site_by_id[other_id]["core"])).length
        priority_outline_results.append({"component_id": component_id,
            "priority_source_id": site_id,
            "visible_outline_length_mm": visible_outline.length,
            "outline_covered_by_companion_growth_mm": covered_by_growth,
            "roundness_error_mm": site["roundness_error_mm"],
            "roundness_tolerance_mm": ROUND_OUTLINE_TOLERANCE_MM,
            "status": "ROUND_OUTLINE_PRESERVED" if covered_by_growth <= ERROR_MM and
                site["roundness_error_mm"] <= ROUND_OUTLINE_TOLERANCE_MM else "ROUND_OUTLINE_FAILED"})

    minimum_gap = float("inf")
    min_gap_pair = None
    gap_violations = []
    port_contact_violations = []
    for decision in decisions:
        site_id = decision["source_id"]
        core = site_by_id[site_id]["core"]
        addition = dynamic_geometries[site_id].difference(core)
        if addition.is_empty:
            continue
        for trace_id in site_ports[site_id]["trace_ids"]:
            trace = next(geometry for row, geometry, _ in local_rows if row["id"] == trace_id)
            zone = site_ports[site_id]["trace_zones"][trace_id]
            spill = addition.intersection(trace.difference(zone))
            if spill.area > AREA_EPSILON_MM2:
                port_contact_violations.append({"source_ids": [site_id, trace_id],
                    "overlap_outside_port_area_mm2": spill.area})
        for row, original, _ in local_rows:
            other_site_id = site_source_to_id.get(row["id"])
            if other_site_id == site_id:
                continue
            if other_site_id and site_by_id[other_site_id]["geometry_sha256"] == site_by_id[site_id]["geometry_sha256"]:
                continue
            # A source-existing, explicitly localized trace attachment is not
            # an optional clearance pair.  Its connection is preserved as an
            # ORG physical-contact relation; only non-port copper is subject
            # to the 0.020 mm experimental separation test.
            if row["id"] in site_ports[site_id]["trace_ids"]:
                continue
            measured_addition = addition
            if measured_addition.is_empty:
                continue
            other = dynamic_geometries.get(other_site_id, original)
            gap = measured_addition.distance(other)
            if gap < minimum_gap:
                minimum_gap = gap
                min_gap_pair = [site_id, row["id"]]
            if gap < HARD_GAP_MM - GAP_TOLERANCE_MM:
                gap_violations.append({"source_ids": [site_id, row["id"]], "gap_mm": gap})

    # Same-seed open/crowded control is run on a real ORG candidate with fixed
    # numeric policy and two actual neighbor sets.  Smaller/larger ordering is
    # searched only in the real crop results; the comparison is reported whether
    # or not a natural reversal exists.
    space_control = _real_space_control(sites, local_rows, site_ports, site_source_to_id,
                                        dynamic_geometries, priority_reservations)
    size_order_examples = _size_order_examples(decisions, site_by_id, dynamic_geometries)

    occurrence_rows = []
    dynamic_d_by_id = decisions_by_id
    for site in sites:
        decision = dynamic_d_by_id[site["site_id"]]
        for source_id in site["source_ids"]:
            row = row_by_id[source_id][0]
            occurrence_rows.append({"source_id": source_id, "source_span": row["source_span"],
                "source_revision_sha256": inv["source_sha256"],
                "geometry_sha256": row["geometry_sha256"],
                "center_mm": [site["center"].x, site["center"].y],
                "radius_mm": site["radius_mm"], "component_id": site["component_id"],
                "site_id": site["site_id"],
                "prior_disposition": _prior_disposition(source_id, site["core"]),
                "revised_disposition": decision["decision"],
                "priority_site_id": priorities.get(site["component_id"]),
                "added_area_mm2": decision["added_area_mm2"],
                "limiting_source_ids": decision["limiting_source_ids"],
                "owner_locator_regions": [],
                "note": "Source candidate included by complete-geometry intersection with fixed viewport; marked-image review locator regions will be attached by the evidence runner."})

    return {
        "schema": "crop-dynamic-t01-r1/1",
        "mode": "ORG_ONLY_DYNAMIC" if dynamic else "ORG_ONLY_STATIC",
        "source_sha256": inv["source_sha256"],
        "inventory_version": inv["version"],
        "inventory_geometry_error_mm": inv["geometry_error_mm"],
        "viewport_mm": list(V_BOUNDS),
        "write_domain_bounds_mm": list(write_domain.bounds),
        "write_domain_wkb": to_wkb(write_domain).hex(),
        "influence_domain_bounds_mm": list(influence_domain.bounds),
        "influence_domain_wkb": to_wkb(influence_domain).hex(),
        "full_component_geometry_available": not unsupported_influence,
        "unsupported_FCu_influence_ids": unsupported_influence,
        "local_support_count": len(local_rows),
        "local_support_kind_counts": dict(Counter(row["kind"] for row, _, _ in local_rows)),
        "local_support_source_ids": sorted(row["id"] for row, _, _ in local_rows),
        "target_occurrence_count": sum(len(site["source_ids"]) for site in sites),
        "target_site_count": len(sites),
        "target_occurrences": occurrence_rows,
        "site_count": len(sites),
        "eligible_site_ids": [site["site_id"] for site in sites],
        "priority_policy": "Within each complete ORG same-layer intersection component, choose largest eligible circular core with a source-bound round outline outside direct attached-trace ports; stable source-id tie break; reserve all chosen outline bands before companion growth.",
        "priority_sites_by_component": priorities,
        "priority_exceptions": priority_exceptions,
        "priority_outline_checks": priority_outline_results,
        "decisions": decisions,
        "dynamic_adaptation_event_count": len(causal_events),
        "dynamic_causal_events": [{"source_id": row["source_id"],
            "prior_accepted_neighbor_ids": row["prior_accepted_neighbor_ids"],
            "dynamic_vs_static_symmetric_difference_mm2": row["dynamic_vs_static_symmetric_difference_mm2"]}
            for row in causal_events],
        "controlled_counterfactuals": counterfactuals,
        "same_seed_space_control": space_control,
        "smaller_roomier_vs_larger_crowded": size_order_examples,
        "static_baseline": {"policy": "same reach, source set, component priorities, ports, gap buffers, geometry kernel and schedule; only accepted-neighbor updates are disabled",
            "decisions": static_decisions,
            "area": _area_summary([{"site_id": key, "core": site_by_id[key]["core"]} for key in order], static_geometries),
            "assembled_hard_gap_violation_count": _assembled_pair_gap_violations(static_geometries, site_by_id)},
        "dynamic_area": _area_summary([{"site_id": key, "core": site_by_id[key]["core"]} for key in order], dynamic_geometries),
        "minimum_dynamic_optional_gap_mm": None if minimum_gap == float("inf") else minimum_gap,
        "minimum_dynamic_gap_pair_source_ids": min_gap_pair,
        "dynamic_hard_gap_violations": gap_violations,
        "attached_trace_port_violations": port_contact_violations,
        "policy": {"growth_reach_rule": "distance from ORG core to nearest other current target geometry minus HARD_GAP_MM; clipped at zero",
            "maximum_growth_reach_mm": max((row["maximum_growth_reach_mm"] for row in decisions), default=0.0),
            "calibrated_radius_limits_mm": {str(key): value for key, value in calibrated_radius_limits.items()},
            "hard_experimental_gap_mm": HARD_GAP_MM,
            "gap_tolerance_mm": GAP_TOLERANCE_MM,
            "construction_buffer_mm": CONSTRUCTION_BUFFER_MM,
            "nominal_construction_buffer_is_not_final_clearance": True,
            "port_extension_mm": PORT_EXTENSION_MM,
            "port_lateral_margin_mm": PORT_LATERAL_MARGIN_MM,
            "round_outline_tolerance_mm": ROUND_OUTLINE_TOLERANCE_MM,
            "curve_quadrant_segments": QUAD_SEGS,
            "viewport_selection": "complete supported filled F.Cu gr_circle occurrences whose full source geometry intersects fixed V; no minimum size threshold or inset write guard",
            "write_domain": "union of every complete supported ORG target core buffered by its nearest-other-target edge spacing minus the 0.020 mm hard gap (floor zero); EDIT class labels do not set reach",
            "influence_domain": "each complete write envelope expanded by 0.025 mm construction buffer plus 0.00001 mm inventory precision allowance; crossing full source objects retrieved by geometry intersection",
            "decision_order_policy": order_policy,
            "schedule": ("priority sites first by component id; companions then ascending ORG centroid Y, X, stable source identity"
                if order_policy == "source_yx" else
                "priority sites first by component id; companions by descending ORG-only nearest-target spacing reach, then stable source identity"),
            "EDIT_geometry_available_to_constructor": False,
            "EDIT_class_caps_frozen_from_separate_calibration": True,
            "smoothing": "none",
            "source_core_loss_tolerance_mm2": 1e-12},
        "shared_parser_and_kernel_qualification": "Same source inventory and Shapely kernel as prior T01; geometry-only internal evidence, not an independent parser/kernel check.",
        "scope_limit": "Local physical copper geometry demonstration only; physical connectivity does not imply net intent or electrical correctness; no manufacturing qualification; no T02-T07 work.",
    }


def _prior_disposition(source_id: str, geometry) -> str:
    # The historical run used an inset 0.01 mm write window and a 0.10 mm
    # diameter threshold; source identities remain bound in the historical run.
    old_write_region = box(*V_BOUNDS).buffer(-0.01)
    diameter = (geometry.bounds[2] - geometry.bounds[0] +
                geometry.bounds[3] - geometry.bounds[1]) / 2
    if not old_write_region.covers(geometry):
        return "EDGE_GUARD_ABSTAIN"
    if diameter < 0.10:
        return "SMALL_CIRCLE_KEEP"
    return "IN_OLD_39_SITE_SET"


def _real_space_control(sites, local_rows, site_ports, site_source_to_id,
                        dynamic_geometries, reservations):
    """Choose deterministic same-seed controls from actual crop obstacles."""
    by_id = {site["site_id"]: site for site in sites}
    choices = []
    for site in sites:
        source_id = site["site_id"]
        if source_id in {sid for sid in reservations}:
            continue
        core = site["core"]
        # For each real nonpriority site, compare its observed neighborhood with
        # an open replay that removes only the closest non-core obstacle.  All
        # other geometry and numeric policy remains fixed.
        candidate_obstacles = []
        for row, geom, _ in local_rows:
            other_id = site_source_to_id.get(row["id"])
            if other_id == source_id:
                continue
            if other_id and by_id[other_id]["geometry_sha256"] == site["geometry_sha256"]:
                continue
            current = dynamic_geometries.get(other_id, geom)
            distance = core.distance(current)
            if site["growth_reach_mm"] > 0 and distance <= site["growth_reach_mm"] + CONSTRUCTION_BUFFER_MM and distance > 1e-8:
                candidate_obstacles.append((distance, row, current, other_id))
        if len(candidate_obstacles) < 1:
            continue
        candidate_obstacles.sort(key=lambda item: (item[0], item[1]["id"]))
        closest = candidate_obstacles[0]
        port = site_ports[source_id]
        obstacles = []
        open_obstacles = []
        for row, geom, _ in local_rows:
            other_id = site_source_to_id.get(row["id"])
            if other_id == source_id:
                continue
            if other_id and by_id[other_id]["geometry_sha256"] == site["geometry_sha256"]:
                continue
            current = dynamic_geometries.get(other_id, geom)
            role = "circle_neighbor" if other_id else ("trace_corridor" if row["kind"] in ("segment", "arc") else "protected_copper")
            entry = (row["id"], current, role)
            obstacles.append(entry)
            if row["id"] != closest[1]["id"]:
                open_obstacles.append(entry)
        zones = port["trace_zones"]
        pr = [(pid, zone) for pid, zone in reservations.items() if pid != source_id]
        crowded = grow_in_available_space(core, obstacles, reach_mm=site["growth_reach_mm"], port_zones=zones,
                                           priority_reservations=pr)
        open_result = grow_in_available_space(core, open_obstacles, reach_mm=site["growth_reach_mm"], port_zones=zones,
                                               priority_reservations=pr)
        delta = open_result["candidate"].symmetric_difference(crowded["candidate"]).area
        if delta > EVENT_EPSILON_MM2:
            return {"status": "PASS", "source_id": source_id,
                "held_fixed": ["same ORG core", f"same nearest-target spacing-derived {site['growth_reach_mm']:.5f} mm reach", "same 0.025 mm construction buffer", "same priority reservations", "same attachment ports", "all other real crop obstacles"],
                "crowded_obstacle_source_id_removed_for_open_replay": closest[1]["id"],
                "crowded_added_area_mm2": crowded["area_delta_mm2"],
                "open_added_area_mm2": open_result["area_delta_mm2"],
                "symmetric_difference_mm2": delta,
                "crowded_limit_reasons": crowded["limiting_obstacles"],
                "open_limit_reasons": open_result["limiting_obstacles"]}
    return {"status": "NOT_DEMONSTRATED", "reason": "No real-crop same-seed open/crowded replay changed the accepted contour under fixed settings."}


def _size_order_examples(decisions, site_by_id, geometries):
    rows = []
    for a in decisions:
        for b in decisions:
            if (a["source_id"] == b["source_id"] or
                    b["original_radius_mm"] - a["original_radius_mm"] <= 2 * ERROR_MM or
                    a["decision"] == "KEEP_PRIORITY_ROUND" or
                    b["decision"] == "KEEP_PRIORITY_ROUND" or
                    not a["limiting_source_ids"] or not b["limiting_source_ids"]):
                continue
            if a["candidate_radius_max_mm"] > b["candidate_radius_max_mm"] + ERROR_MM:
                rows.append({"smaller_source_id": a["source_id"], "larger_source_id": b["source_id"],
                    "smaller_original_radius_mm": a["original_radius_mm"],
                    "larger_original_radius_mm": b["original_radius_mm"],
                    "smaller_final_max_radius_mm": a["candidate_radius_max_mm"],
                    "larger_final_max_radius_mm": b["candidate_radius_max_mm"],
                    "smaller_added_area_mm2": a["added_area_mm2"],
                    "larger_added_area_mm2": b["added_area_mm2"],
                    "smaller_limiting_source_ids": a["limiting_source_ids"],
                    "larger_limiting_source_ids": b["limiting_source_ids"]})
    if rows:
        rows.sort(key=lambda row: (row["smaller_final_max_radius_mm"] - row["larger_final_max_radius_mm"],
                                   row["smaller_source_id"], row["larger_source_id"]), reverse=True)
        return {"status": "PASS_REAL_CROP_REVERSAL", "example": rows[0], "candidate_pair_count": len(rows)}
    return {"status": "NOT_DEMONSTRATED_REAL_CROP", "candidate_pair_count": 0,
            "reason": "No smaller original site ended with a larger maximum radial reach than a larger original site in the real crop."}


def _assembled_pair_gap_violations(geometries, site_by_id):
    violations = []
    ids = sorted(geometries)
    for i, left_id in enumerate(ids):
        left_addition = geometries[left_id].difference(site_by_id[left_id]["core"])
        if left_addition.is_empty:
            continue
        for right_id in ids[i + 1:]:
            right_addition = geometries[right_id].difference(site_by_id[right_id]["core"])
            if right_addition.is_empty:
                continue
            gap = min(left_addition.distance(geometries[right_id]),
                      right_addition.distance(geometries[left_id]))
            if gap < HARD_GAP_MM - GAP_TOLERANCE_MM:
                violations.append({"source_ids": [left_id, right_id], "gap_mm": gap})
    return violations
