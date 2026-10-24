#!/usr/bin/env python3
"""Run the T01 circle-growth process on the newly registered crop only."""
from __future__ import annotations
import argparse, hashlib, json, math, platform, shutil, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import shapely
from shapely import STRtree, from_wkb, to_wkb
from shapely.geometry import Point, box
from shapely.ops import unary_union
from src import crop_circle_sources as base
from src.crop_balanced_t01 import CropSettings, WorkingScene, execute
from src.crop_diameter_selection import select_targets
from src.crop_square_neighbor_experiment import geometry_hash

POLICY = ROOT / "contracts/crop_t01_multicircle_crop_policy.json"
DEFAULT_OUT = ROOT / "out/crop_dynamic_tasks/t01_multicircle_new_crop_20261025"


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def put_geometry(out, name, geometry, hashes):
    path = out / (name + ".wkb")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(to_wkb(geometry, byte_order=1))
    hashes[name] = base.sha(path)
    return name + ".wkb"


def local_competition_components(sites, gap):
    """Connected components of potential 1.5x circle-envelope competition."""
    parent = list(range(len(sites)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    edges = []
    for i, a in enumerate(sites):
        for j in range(i + 1, len(sites)):
            b = sites[j]
            center_distance = math.dist(a["center"], b["center"])
            envelope_gap = center_distance - 1.5 * (a["radius"] + b["radius"])
            if envelope_gap <= gap:
                x, y = find(i), find(j)
                if x != y:
                    parent[y] = x
                edges.append({"a": a["source_id"], "b": b["source_id"],
                              "center_distance_mm": center_distance,
                              "cap_envelope_gap_mm": envelope_gap})
    groups = defaultdict(list)
    for index, site in enumerate(sites):
        groups[find(index)].append(site)
    result = []
    for members in groups.values():
        members.sort(key=lambda site: (site["center"][1], site["center"][0], site["source_id"]))
        ids = sorted(site["source_id"] for site in members)
        gid = "LC-" + hashlib.sha256("\n".join(ids).encode()).hexdigest()[:12]
        result.append({"group_id": gid, "site_ids": ids, "members": members,
                       "size": len(members),
                       "rule": "multi_circle_growth" if len(members) > 1 else "keep_unique_round"})
    result.sort(key=lambda group: (group["members"][0]["center"][1],
                                   group["members"][0]["center"][0], group["group_id"]))
    return result, edges


def physical_contact_components(sites):
    """Partition circles by their original whole-board F.Cu physical component."""
    by_component = defaultdict(list)
    for site in sites:
        source_component_id = site.get("physical_component_source_id")
        if not isinstance(source_component_id, str) or len(source_component_id) != 64:
            raise ValueError("MISSING_ORG_PHYSICAL_CONTACT_GROUP")
        by_component[source_component_id].append(site)
    result = []
    for source_component_id, members in by_component.items():
        members.sort(key=lambda site: (site["center"][1], site["center"][0], site["source_id"]))
        ids = sorted(site["source_id"] for site in members)
        result.append({"component_id": "PC-" + source_component_id[:12], "site_ids": ids,
                       "members": members, "size": len(members),
                       "rule": "keep_unique_round" if len(members) == 1 else "multi_circle_growth"})
    result.sort(key=lambda component: (component["members"][0]["center"][1],
                                       component["members"][0]["center"][0], component["component_id"]))
    return result


def choose_component_nonround_sites(sites, priorities, targets, accepted_component_ids):
    """Choose one smallest eligible non-priority companion per accepted component."""
    priority_ids = set(priorities.values())
    chosen = {}
    for component_id in sorted(accepted_component_ids):
        raw_id_prefix = component_id.removeprefix("PC-")
        candidates = [site for site in sites
                      if site["physical_component_source_id"].startswith(raw_id_prefix)
                      and site["source_id"] not in priority_ids
                      and targets[site["source_id"]] > site["radius"]]
        if candidates:
            selected = min(candidates, key=lambda site: (site["radius"], site["source_id"]))
            chosen[component_id] = selected["source_id"]
    return chosen


def exclude_circles_contained_by_source_shape(sites, rows, shapes, *, area_tolerance_mm2=1e-12):
    """Exclude circles directly covered by one other source primitive; hold near-covers out."""
    excluded = {}
    uncertain = {}
    eligible = []
    tree = STRtree(shapes)
    for site in sites:
        own_indexes = set(site["indexes"])
        indexes = sorted({int(index) for index in tree.query(site["core"], predicate="intersects")
                          if int(index) not in own_indexes and not shapes[int(index)].is_empty})
        if not indexes:
            eligible.append(site)
            continue
        individual_cover_indexes = [index for index in indexes if shapes[index].covers(site["core"])]
        near_boundary_indexes = [index for index in indexes
                                 if not shapes[index].covers(site["core"])
                                 and site["core"].difference(shapes[index]).area <= area_tolerance_mm2]
        witness_indexes = individual_cover_indexes or near_boundary_indexes
        sources = [{"source_id": rows[index]["id"], "kind": rows[index]["kind"],
                    "geometry_sha256": rows[index]["geometry_sha256"]}
                   for index in witness_indexes]
        witness = {"coverage_basis": "individual_source_primitive" if individual_cover_indexes
                                      else "individual_source_primitive_near_boundary",
                   "covered_by_source_objects": sources,
                   "minimum_uncovered_circle_area_mm2": min(
                       (site["core"].difference(shapes[index]).area for index in witness_indexes),
                       default=site["core"].area)}
        if individual_cover_indexes:
            excluded[site["source_id"]] = [witness]
        elif near_boundary_indexes:
            uncertain[site["source_id"]] = [witness]
        else:
            eligible.append(site)
    return eligible, excluded, uncertain


def circle_coverage_summary(sites, shapes, directly_covered):
    """Count direct one-primitive covers; collective coverage is not inferred."""
    tree = STRtree(shapes)
    individually_covered = set()
    for site in sites:
        own = set(site["indexes"])
        for raw_index in tree.query(site["core"], predicate="intersects"):
            index = int(raw_index)
            if index not in own and shapes[index].covers(site["core"]):
                individually_covered.add(site["source_id"])
                break
    if individually_covered != set(directly_covered):
        raise ValueError("DIRECT_COVERAGE_SUMMARY_MISMATCH")
    return {"individually_covered_sites": len(individually_covered),
            "additional_collective_coverage_sites_inferred": 0,
            "directly_covered_sites": len(individually_covered)}


def ring_data(geometry, bounds):
    polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
    return {"bounds_mm": list(bounds), "polygons": [
        {"exterior": [[x, y] for x, y, *_ in polygon.exterior.coords],
         "interiors": [[[x, y] for x, y, *_ in ring.coords] for ring in polygon.interiors]}
        for polygon in polygons if polygon.geom_type == "Polygon"]}


def main(out, policy_path=POLICY):
    out = out.resolve()
    if not out.is_relative_to(ROOT / "out") or out.exists():
        raise ValueError("FRESH_PROJECT_OUT_DIRECTORY_REQUIRED")
    policy_path = Path(policy_path).resolve()
    if not policy_path.is_relative_to(ROOT / "contracts"):
        raise ValueError("POLICY_MUST_BE_PROJECT_CONTRACT")
    policy = json.loads(policy_path.read_bytes())
    policy_sha = base.sha(policy_path)
    assets = base.verify_assets()
    source_path = ROOT / policy["source"]
    if base.sha(source_path) != policy["source_sha256"]:
        raise ValueError("ORG_SOURCE_HASH_MISMATCH")
    source = source_path.read_bytes()
    out.mkdir(parents=True)
    shutil.copy2(policy_path, out / "policy.json")
    dump(out / "asset_integrity.json", assets)
    inv, rows, shapes, tree, all_sites = base.source_scene(
        source, {**policy, "radius_multiplier": policy["max_growth_factor"]},
        expected_unique_sites=policy["expected_unique_circle_sites"],
        expected_occurrences=policy["expected_circle_occurrences"])
    eligible_sites, contained_sites, uncertain_sites = exclude_circles_contained_by_source_shape(
        all_sites, rows, shapes)
    coverage_summary = circle_coverage_summary(all_sites, shapes, contained_sites)
    physical_diagnostic_components = physical_contact_components(eligible_sites)
    owner_accepted_physical_components = {
        "PC-a7f115866d96", "PC-6acc2586a685", "PC-b211bc963d11",
        "PC-b44608d50690",
    }
    physical_component_diagnostic = {
        "basis": "whole_board_connected_F.Cu_source_geometry_after_direct_cover_exclusion",
        "used_for_T01_growth_grouping": False,
        "accepted_physical_component_ids": sorted(owner_accepted_physical_components),
        "multi_circle_components": [
            {"component_id": component["component_id"], "site_ids": component["site_ids"],
             "size": component["size"],
             "owner_review_status": ("OWNER_ACCEPTED_PHYSICAL_COMPONENT"
                                     if component["component_id"] in owner_accepted_physical_components
                                     else "ACCEPTANCE_NOT_RECORDED")}
            for component in sorted(physical_diagnostic_components, key=lambda row: row["component_id"])
            if component["size"] > 1]}
    diagnostic_edges = local_competition_components(eligible_sites, policy["construction_gap_mm"])[1]
    if policy.get("t01_envelope_group_basis") != "growth_envelope_competition":
        raise ValueError("UNSUPPORTED_OR_MISSING_T01_ENVELOPE_GROUP_BASIS")
    t01_envelope_groups, _ = local_competition_components(
        eligible_sites, policy["construction_gap_mm"])
    singleton_sites = [group["members"][0] for group in t01_envelope_groups if group["size"] == 1]
    active_groups = [group for group in t01_envelope_groups if group["size"] > 1]
    active_sites = sorted([site for group in active_groups for site in group["members"]],
                          key=lambda site: (site["center"][1], site["center"][0], site["source_id"]))
    t01_groups = [{"group_id": group["group_id"], "site_ids": group["site_ids"],
                   "rule": group["rule"], "apply_square_bound": False}
                  for group in active_groups]
    priorities = {}
    for group in active_groups:
        selected = sorted(group["members"], key=lambda site: (-site["radius"], site["source_id"]))[0]
        priorities[group["group_id"]] = selected["source_id"]
    settings = CropSettings(hard_factor=policy["max_growth_factor"],
                            construction_gap=policy["construction_gap_mm"],
                            hard_gap=policy["hard_gap_mm"], safety=policy["safety_mm"],
                            orientation=policy["orientation_degrees"], qsegs=policy["quad_segs"],
                            area_epsilon=policy["area_epsilon_mm2"],
                            event_epsilon=policy["event_epsilon_mm2"])
    initial = WorkingScene(source, rows, shapes, active_sites, settings)
    targets, size_records, target_limits = select_targets(
        active_sites, t01_groups, priorities, initial, settings, policy["diameter_classes_mm"])
    accepted_physical_ids = set(policy["growth_scope_physical_component_ids"])
    growth_scope_sites = {site["source_id"] for component in physical_diagnostic_components
                          if component["component_id"] in accepted_physical_ids
                          for site in component["members"]}
    for site in active_sites:
        sid = site["source_id"]
        if sid not in growth_scope_sites:
            targets[sid] = site["radius"]
            size_records[sid].update(
                proposed_radius_mm=site["radius"], selected_diameter_mm=2 * site["radius"],
                category_mm=None, original_keep=True,
                scope_limit="OUTSIDE_ACCEPTED_PHYSICAL_COMPONENTS_ROUND")

    # Physical-component allowance is independent of local envelope grouping:
    # keep every T01 round priority round, allow only one companion per accepted
    # physical component to use clipped/non-round growth, and hold the rest at
    # their exact round ORG cores. Prefer the smallest source circles so the
    # visibly prominent circles remain round; ties use the stable source ID.
    nonround_site_by_component = choose_component_nonround_sites(
        active_sites, priorities, targets, accepted_physical_ids)
    pre_component_cap_targets = dict(targets)
    for site in active_sites:
        sid = site["source_id"]
        raw_component_id = site["physical_component_source_id"]
        component_id = "PC-" + raw_component_id[:12]
        if (sid in growth_scope_sites and component_id in accepted_physical_ids
                and sid not in priorities.values()
                and sid != nonround_site_by_component.get(component_id)
                and targets[sid] > site["radius"]):
            targets[sid] = site["radius"]
            size_records[sid].update(
                proposed_radius_mm=site["radius"], selected_diameter_mm=2 * site["radius"],
                category_mm=None, original_keep=True,
                component_shape_limit="ROUND_SOURCE_CORE_NONROUND_SLOT_ALREADY_ASSIGNED")
    selection = {"schema": "t01-multicircle-selection/1", "policy_sha256": policy_sha,
                 "source_sha256": base.sha(source_path),
                 "all_unique_circle_sites": len(all_sites),
                 "source_circle_occurrences": sum(len(site["aliases"]) for site in all_sites),
                 "raw_circle_recognition_crosscheck": inv["circle_recognition_audit"],
                 "eligible_independent_circle_sites": len(eligible_sites),
                 "excluded_circles_covered_by_other_source_primitive": len(contained_sites),
                 "coverage_summary": coverage_summary,
                 "contained_circle_source_ids": sorted(contained_sites),
                 "contained_circle_bindings": contained_sites,
                 "containment_uncertain_circle_sites": len(uncertain_sites),
                 "containment_uncertain_circle_source_ids": sorted(uncertain_sites),
                 "containment_uncertain_bindings": uncertain_sites,
                 "physical_component_diagnostic": physical_component_diagnostic,
                 "singleton_round_site_ids": sorted(site["source_id"] for site in singleton_sites),
                 "t01_envelope_groups": [{"group_id": group["group_id"], "site_ids": group["site_ids"],
                                          "size": group["size"], "rule": group["rule"]}
                                         for group in t01_envelope_groups],
                 "envelope_competition_edges_diagnostic_only": diagnostic_edges,
                 "round_priorities_by_t01_envelope_group": priorities,
                 "target_limits": target_limits,
                 "growth_scope_physical_component_ids": sorted(accepted_physical_ids),
                 "nonround_site_by_accepted_physical_component": nonround_site_by_component,
                 "nonround_site_selector": policy["nonround_site_selector"],
                 "pre_component_cap_targets_mm": pre_component_cap_targets,
                 "diameter_classes": size_records}
    dump(out / "selection.json", selection)
    dynamic = execute(source, rows, shapes, active_sites, t01_groups, priorities,
                      settings=settings, targets=targets, square_guided_ids=())
    static = execute(source, rows, shapes, active_sites, t01_groups, priorities,
                     dynamic=False, settings=settings, counterfactuals=False,
                     targets=targets, square_guided_ids=())
    replay = execute(source, rows, shapes, active_sites, t01_groups, priorities,
                     settings=settings, counterfactuals=False, targets=targets,
                     square_guided_ids=())
    selected_nonround_ids = set(nonround_site_by_component.values())
    for run in (dynamic, static, replay):
        for decision in run["decisions"]:
            if decision["source_id"] not in growth_scope_sites:
                decision["decision"] = "KEEP_OUTSIDE_ACCEPTED_PHYSICAL_COMPONENTS_ROUND"
                decision["growth_scope_reason"] = (
                    "Outside the four owner-accepted physical F.Cu components; exact round source core retained.")
            elif (decision["source_id"] not in selected_nonround_ids
                  and not decision["priority"]
                  and decision["added_area_mm2"] <= settings.area_epsilon):
                decision["decision"] = "KEEP_COMPONENT_ROUND_SHAPE_CAP"
                decision["growth_scope_reason"] = (
                    "The component's single non-round slot is assigned elsewhere; exact round source core retained.")
            decision["nonround_component_slot"] = decision["source_id"] in selected_nonround_ids
    replay_equal = all(geometry_hash(dynamic["scene"].accepted[site["source_id"]]) ==
                       geometry_hash(replay["scene"].accepted[site["source_id"]])
                       for site in active_sites)
    if not replay_equal:
        raise ValueError("SAME_POLICY_REPLAY_MISMATCH")
    accepted = {site["source_id"]: site["core"] for site in singleton_sites}
    accepted.update({site["source_id"]: site["core"] for site in all_sites
                     if site["source_id"] in contained_sites or site["source_id"] in uncertain_sites})
    accepted.update(dynamic["scene"].accepted)
    static_accepted = {site["source_id"]: site["core"] for site in singleton_sites}
    static_accepted.update({site["source_id"]: site["core"] for site in all_sites
                            if site["source_id"] in contained_sites or site["source_id"] in uncertain_sites})
    static_accepted.update(static["scene"].accepted)
    byid = {site["source_id"]: site for site in all_sites}
    decisions_by_id = {decision["source_id"]: decision for decision in dynamic["decisions"]}
    nonround_growth_counts = Counter(
        decision["physical_component"] for decision in dynamic["decisions"]
        if decision["decision"] == "GROW_COMPANION"
        and decision["added_area_mm2"] > settings.area_epsilon)
    if any(nonround_growth_counts.get(component.removeprefix("PC-"), 0) > 1
           for component in accepted_physical_ids):
        raise ValueError("MULTIPLE_NONROUND_GROWTH_SITES_IN_PHYSICAL_COMPONENT")
    if any(not accepted[sid].equals_exact(byid[sid]["core"], 0)
           for sid in set(byid) - growth_scope_sites):
        raise ValueError("OUTSIDE_ACCEPTED_PHYSICAL_COMPONENT_WAS_MODIFIED")
    hashes = {}
    site_keys = {site["source_id"]: f"C{i:03d}" for i, site in enumerate(all_sites, 1)}
    all_decisions = []
    for site in all_sites:
        sid = site["source_id"]
        core = site["core"]
        candidate = accepted[sid]
        core_path = put_geometry(out, f"geometry/{site_keys[sid]}_core", core, hashes)
        candidate_path = put_geometry(out, f"geometry/{site_keys[sid]}_dynamic", candidate, hashes)
        static_path = put_geometry(out, f"geometry/{site_keys[sid]}_static", static_accepted[sid], hashes)
        if sid in decisions_by_id:
            d = decisions_by_id[sid]
            d.update(key=site_keys[sid], size_class=size_records[sid],
                     geometry={"core": core_path, "dynamic": candidate_path, "static": static_path})
            all_decisions.append(d)
        elif sid in contained_sites:
            all_decisions.append({"key": site_keys[sid], "source_id": sid,
                                  "aliases": site["aliases"], "center": site["center"],
                                  "source_radius_mm": site["radius"],
                                  "proposed_radius_mm": site["radius"],
                                  "decision": "KEEP_CIRCLE_COVERED_BY_OTHER_COPPER",
                                  "coverage_witness": contained_sites[sid],
                                  "added_area_mm2": 0.0, "candidate_sha256": geometry_hash(core),
                                  "verification": {"passed": True, "source_core_retained": True,
                                                   "no_growth": True, "containment_rule_applied": True},
                                  "geometry": {"core": core_path, "dynamic": candidate_path,
                                               "static": static_path}})
        elif sid in uncertain_sites:
            all_decisions.append({"key": site_keys[sid], "source_id": sid,
                                  "aliases": site["aliases"], "center": site["center"],
                                  "source_radius_mm": site["radius"],
                                  "proposed_radius_mm": site["radius"],
                                  "decision": "KEEP_CIRCLE_CONTAINMENT_UNCERTAIN",
                                  "near_boundary_source_objects": uncertain_sites[sid],
                                  "added_area_mm2": 0.0, "candidate_sha256": geometry_hash(core),
                                  "verification": {"passed": True, "source_core_retained": True,
                                                   "no_growth": True, "multiplicity_excluded": True,
                                                   "containment_uncertainty_held": True},
                                  "geometry": {"core": core_path, "dynamic": candidate_path,
                                               "static": static_path}})
        else:
            all_decisions.append({"key": site_keys[sid], "source_id": sid,
                                  "aliases": site["aliases"], "center": site["center"],
                                  "source_radius_mm": site["radius"],
                                  "proposed_radius_mm": site["radius"],
                                  "t01_envelope_group_id": next(
                                      g["group_id"] for g in t01_envelope_groups if sid in g["site_ids"]),
                                  "priority": True, "decision": "KEEP_T01_ENVELOPE_SINGLETON_ROUND",
                                  "added_area_mm2": 0.0, "candidate_sha256": geometry_hash(core),
                                  "verification": {"passed": True, "source_core_retained": True,
                                                   "no_growth": True},
                                  "geometry": {"core": core_path, "dynamic": candidate_path,
                                               "static": static_path}})
    viewport = box(*policy["viewport_mm"])
    source_effective = unary_union([geometry.intersection(viewport) for geometry in shapes
                                    if geometry.intersects(viewport)])
    original = ROOT / "out/crop_dynamic_tasks/t02_crop_registration_20261024/org_crop.wkb"
    registered_source = from_wkb(original.read_bytes())
    if source_effective.symmetric_difference(registered_source).area > 1e-8:
        raise ValueError("REGISTERED_ORG_CROP_GEOMETRY_MISMATCH")
    additions = unary_union([geometry.difference(byid[sid]["core"])
                             for sid, geometry in accepted.items()]).intersection(viewport)
    after = unary_union([registered_source, additions])
    for name, geometry in [("original_crop", registered_source),
                           ("t01_multicircle_crop", after),
                           ("t01_additions_crop", additions)]:
        path = out / f"{name}.wkb"
        path.write_bytes(to_wkb(geometry, byte_order=1))
        hashes[name] = base.sha(path)
        dump(out / f"{name}_rings.json", ring_data(geometry, policy["viewport_mm"]))
    adapted = sorted({event["target_source_id"] for event in dynamic["events"]})
    counts = Counter(item["decision"] for item in all_decisions)
    report = {"schema": "t01-multicircle-crop-result/1",
              "status": "NEW_EXPERIMENTAL_CROP_CANDIDATE_PENDING_OWNER_REVIEW",
              "task_sequence": "T01_CIRCLES_FIRST_THEN_T02_RECTANGLES",
              "policy_sha256": policy_sha, "source_sha256": base.sha(source_path),
              "registered_viewport_mm": policy["viewport_mm"],
              "viewport_mm": policy["viewport_mm"],
              "selection_sha256": base.sha(out / "selection.json"),
              "scene_sha256": hashes["t01_multicircle_crop"],
              "all_unique_circle_sites": len(all_sites),
              "source_circle_occurrences": sum(len(site["aliases"]) for site in all_sites),
              "raw_circle_recognition_crosscheck": inv["circle_recognition_audit"],
              "eligible_independent_circle_sites": len(eligible_sites),
              "directly_covered_circle_sites": len(contained_sites),
              "coverage_summary": coverage_summary,
              "contained_circle_source_ids": sorted(contained_sites),
              "containment_uncertain_circle_sites": len(uncertain_sites),
              "containment_uncertain_circle_source_ids": sorted(uncertain_sites),
              "t01_envelope_singleton_sites": len(singleton_sites),
              "t01_envelope_group_sites": len(active_sites),
              "multi_circle_t01_envelope_groups": len(active_groups),
              "t01_envelope_group_basis": policy["t01_envelope_group_basis"],
              "physical_component_diagnostic": physical_component_diagnostic,
              "physical_component_growth_scope_ids": sorted(accepted_physical_ids),
              "one_nonround_growth_site_by_accepted_physical_component": nonround_site_by_component,
              "outside_accepted_physical_components_exact_round": all(
                  accepted[sid].equals_exact(byid[sid]["core"], 0)
                  for sid in set(byid) - growth_scope_sites),
              "nonround_growth_limit_per_accepted_physical_component": 1,
              "t01_envelope_group_size_distribution": dict(
                  sorted(Counter(g["size"] for g in t01_envelope_groups).items())),
              "round_priorities_by_t01_envelope_group": len(priorities), "decision_counts": dict(counts),
              "grown_sites": sum(item["added_area_mm2"] > settings.area_epsilon for item in all_decisions),
              "unchanged_sites": sum(item["added_area_mm2"] <= settings.area_epsilon for item in all_decisions),
              "added_area_union_in_view_mm2": additions.area,
              "actual_neighbor_counterfactual_pairs": len(dynamic["events"]),
              "actual_adapted_later_sites": len(adapted), "adapted_later_source_ids": adapted,
              "same_policy_replay_equal": replay_equal,
              "dynamic_vs_frozen_changed_sites": sum(
                  dynamic["scene"].accepted[sid].symmetric_difference(static["scene"].accepted[sid]).area > 1e-8
                  for sid in dynamic["scene"].accepted),
              "all_per_candidate_checks_pass": all(
                  d["verification"].get("passed", False) for d in dynamic["decisions"]),
              "singleton_source_cores_exact": all(
                  accepted[site["source_id"]].equals_exact(site["core"], 0)
                  for site in singleton_sites),
              "source_fcu_records": len(rows), "unsupported_fcu_records": 0,
              "edit_access_in_constructor": False,
              "native_export": "NOT_RUN", "electrical_status": "NOT_ESTABLISHED",
              "manufacturing_status": "NOT_ESTABLISHED", "EDIT_equivalence": "NOT_ESTABLISHED",
              "owner_status": "PENDING_REVIEW_OF_NEW_CROP_T01_RESULT",
              "cursor_review": "NOT_RUN: CHANNEL_UNAVAILABLE",
              "runtime": {"python": platform.python_version(), "shapely": shapely.__version__,
                          "geos": shapely.geos_version_string},
              "decision_counts": dict(counts), "decisions": all_decisions,
              "geometry_sha256": hashes,
              "code_sha256": {name: base.sha(ROOT / name) for name in [
                  "src/crop_circle_sources.py", "src/crop_balanced_t01.py",
                  "src/crop_diameter_selection.py", "src/crop_square_recess.py",
                  "src/crop_square_neighbor_experiment.py", "src/native_inventory.py",
                  "tools/run_crop_t01_multicircle_crop.py"]},
              "limitations": [
                  "This is a new experimental crop-specific T01 application, not the previously accepted T01 crop.",
                  "Any source circle wholly covered by one other ORG F.Cu source primitive is protected and omitted from group multiplicity; multiple primitives are not combined to infer containment.",
                  "Near-boundary circles with at most 1e-12 mm2 uncovered area against an intersecting primitive are separately held unchanged and omitted from multiplicity as containment-uncertain, not asserted as fully contained.",
                  "T01 envelope groups use the configured local 1.5x growth-envelope competition rule after coverage exclusions; whole-board physical F.Cu components are separate observations and do not define T01 group membership.",
                  "Eligible singleton T01 envelope groups and contained circles are held at exact source geometry; only eligible members of multi-circle T01 envelope groups use the existing provisional diameter palette and 1.5x cap.",
                  "Within the four accepted whole-board physical components, existing largest-radius envelope priorities remain round; at most one non-priority circle per physical component may use clipped growth. The smallest eligible source-radius companion is selected, with stable source-ID tie-break, and other companions remain exact round ORG cores.",
                  "No old-crop site annotations or square-recess exceptions were transferred.",
                  "The registered crop viewport has at least 0.0223 mm raster locator uncertainty; construction uses source-native geometry.",
                  "No native export, electrical correctness, manufacturing sizing, or equivalence to EDIT is established."]}
    dump(out / "report.json", report)
    for event_index, event in enumerate(dynamic["events"], 1):
        event["counterfactual_wkb"] = put_geometry(out, f"events/E{event_index:03d}_counterfactual",
                                                    event["counterfactual"], hashes)
        event["earlier_copper_wkb"] = put_geometry(out, f"events/E{event_index:03d}_earlier",
                                                    event["earlier_copper"], hashes)
        for key in ("counterfactual", "earlier_copper"):
            event.pop(key, None)
    dump(out / "events.json", {"events": dynamic["events"],
                                "static_held_fixed": "same frozen group targets, source and round priorities"})
    report["events_file_sha256"] = base.sha(out / "events.json")
    dump(out / "report.json", report)
    renderer_python = shutil.which("python3")
    if not renderer_python:
        raise ValueError("SYSTEM_PYTHON_FOR_PIL_RENDER_UNAVAILABLE")
    subprocess.run([renderer_python, str(ROOT / "tools/render_crop_t01_multicircle_crop.py"), str(out)],
                   cwd=ROOT, check=True)
    with (out / "audit.log").open("w") as log:
        subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_crop_t01_multicircle_crop.py"), str(out)],
                       cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    print(json.dumps({key: report[key] for key in ["t01_envelope_singleton_sites", "t01_envelope_group_sites",
                                                    "multi_circle_t01_envelope_groups", "decision_counts", "grown_sites",
                                                    "actual_neighbor_counterfactual_pairs",
                                                    "same_policy_replay_equal", "all_per_candidate_checks_pass"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--policy", type=Path, default=POLICY)
    args = parser.parse_args()
    main(args.output, args.policy)
