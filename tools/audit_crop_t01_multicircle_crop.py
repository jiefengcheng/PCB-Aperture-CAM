#!/usr/bin/env python3
"""Fresh-process audit of the saved new-crop T01 candidate."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shapely import from_wkb
from shapely.geometry import Point, box
from shapely.ops import unary_union
from src import crop_circle_sources as base
from src.crop_balanced_t01 import CropSettings, WorkingScene
from src.crop_square_neighbor_experiment import verify_addition
from tools.run_crop_t01_multicircle_crop import (
    local_competition_components,
    physical_contact_components,
)


def independently_recompute_containment(sites, rows, shapes):
    """Independently audit direct one-primitive coverage and near-boundary holds."""
    eligible, contained, uncertain = [], {}, {}
    for circle in sites:
        alias_indexes = set(circle["indexes"])
        intersecting = []
        for source_index, source_geometry in enumerate(shapes):
            if source_index in alias_indexes or source_geometry.is_empty:
                continue
            if source_geometry.intersects(circle["core"]):
                intersecting.append(source_index)
        if not intersecting:
            eligible.append(circle)
            continue
        individual_covers = [index for index in intersecting
                             if shapes[index].covers(circle["core"])]
        near_boundary = [index for index in intersecting
                         if not shapes[index].covers(circle["core"])
                         and circle["core"].difference(shapes[index]).area <= 1e-12]
        witness_indexes = individual_covers or near_boundary
        witness = {"coverage_basis": "individual_source_primitive" if individual_covers
                                      else "individual_source_primitive_near_boundary",
                   "covered_by_source_objects": [
            {"source_id": rows[index]["id"], "kind": rows[index]["kind"],
             "geometry_sha256": rows[index]["geometry_sha256"]}
            for index in witness_indexes],
                   "minimum_uncovered_circle_area_mm2": min(
                       (circle["core"].difference(shapes[index]).area for index in witness_indexes),
                       default=circle["core"].area)}
        if individual_covers:
            contained[circle["source_id"]] = [witness]
        elif near_boundary:
            uncertain[circle["source_id"]] = [witness]
        else:
            eligible.append(circle)
    return eligible, contained, uncertain


def main(bundle):
    bundle = Path(bundle).resolve()
    policy = json.loads((bundle / "policy.json").read_bytes())
    report = json.loads((bundle / "report.json").read_bytes())
    source_path = Path(policy["source"])
    source_path = source_path if source_path.is_absolute() else base.ROOT / source_path
    assert base.sha(source_path) == policy["source_sha256"] == report["source_sha256"]
    source = source_path.read_bytes()
    inv, rows, shapes, tree, all_sites = base.source_scene(
        source, {**policy, "radius_multiplier": policy["max_growth_factor"]},
        expected_unique_sites=policy["expected_unique_circle_sites"],
        expected_occurrences=policy["expected_circle_occurrences"])
    sites, contained, uncertain = independently_recompute_containment(all_sites, rows, shapes)
    individually_covered_ids = set()
    for circle in all_sites:
        own = set(circle["indexes"])
        if any(index not in own and geometry.covers(circle["core"])
               for index, geometry in enumerate(shapes)):
            individually_covered_ids.add(circle["source_id"])
    independently_measured_coverage = {
        "individually_covered_sites": len(individually_covered_ids),
        "additional_collective_coverage_sites_inferred": 0,
        "directly_covered_sites": len(individually_covered_ids)}
    assert independently_measured_coverage == report["coverage_summary"]
    if policy.get("t01_envelope_group_basis") != "growth_envelope_competition":
        raise ValueError("UNSUPPORTED_OR_MISSING_T01_ENVELOPE_GROUP_BASIS")
    t01_envelope_groups, _ = local_competition_components(sites, policy["construction_gap_mm"])
    saved_selection = json.loads((bundle / "selection.json").read_bytes())
    assert saved_selection["growth_scope_physical_component_ids"] == sorted(policy["growth_scope_physical_component_ids"])
    assert report["selection_sha256"] == base.sha(bundle / "selection.json")
    assert report["viewport_mm"] == report["registered_viewport_mm"] == policy["viewport_mm"]
    physical_components = physical_contact_components(sites)
    owner_accepted_physical_components = {
        "PC-a7f115866d96", "PC-6acc2586a685", "PC-b211bc963d11",
        "PC-b44608d50690",
    }
    physical_diagnostic = {
        "basis": "whole_board_connected_F.Cu_source_geometry_after_direct_cover_exclusion",
        "used_for_T01_growth_grouping": False,
        "accepted_physical_component_ids": sorted(owner_accepted_physical_components),
        "multi_circle_components": [
            {"component_id": component["component_id"], "site_ids": component["site_ids"],
             "size": component["size"],
             "owner_review_status": ("OWNER_ACCEPTED_PHYSICAL_COMPONENT"
                                     if component["component_id"] in owner_accepted_physical_components
                                     else "ACCEPTANCE_NOT_RECORDED")}
            for component in sorted(physical_components, key=lambda row: row["component_id"])
            if component["size"] > 1]}
    assert physical_diagnostic == saved_selection["physical_component_diagnostic"]
    assert physical_diagnostic == report["physical_component_diagnostic"]
    recomputed_envelope_groups = sorted(
        [{"group_id": group["group_id"], "site_ids": sorted(group["site_ids"]),
          "size": group["size"], "rule": group["rule"]} for group in t01_envelope_groups],
        key=lambda group: group["group_id"])
    recorded_envelope_groups = sorted(
        [{"group_id": group["group_id"], "site_ids": sorted(group["site_ids"]),
          "size": group["size"], "rule": group["rule"]}
         for group in saved_selection["t01_envelope_groups"]],
        key=lambda group: group["group_id"])
    assert recomputed_envelope_groups == recorded_envelope_groups
    singleton_ids = {group["site_ids"][0] for group in t01_envelope_groups if group["size"] == 1}
    active = [site for group in t01_envelope_groups if group["size"] > 1 for site in group["members"]]
    settings = CropSettings(hard_factor=policy["max_growth_factor"],
                            construction_gap=policy["construction_gap_mm"],
                            hard_gap=policy["hard_gap_mm"], safety=policy["safety_mm"],
                            orientation=policy["orientation_degrees"], qsegs=policy["quad_segs"],
                            area_epsilon=policy["area_epsilon_mm2"],
                            event_epsilon=policy["event_epsilon_mm2"])
    scene = WorkingScene(source, rows, shapes, active, settings)
    by_id = {site["source_id"]: site for site in all_sites}
    checked = []
    seen = set()
    nonround_growth_by_component = {}
    for decision in report["decisions"]:
        sid = decision["source_id"]
        assert sid not in seen
        seen.add(sid)
        file = bundle / decision["geometry"]["dynamic"]
        assert base.sha(file) == report["geometry_sha256"][decision["geometry"]["dynamic"][:-4]]
        candidate = from_wkb(file.read_bytes())
        site = by_id[sid]
        in_scope = any(site["physical_component_source_id"].startswith(
            component.removeprefix("PC-")) for component in policy["growth_scope_physical_component_ids"])
        if not in_scope:
            assert candidate.equals_exact(site["core"], 0), (sid, "OUTSIDE_ACCEPTED_COMPONENT_MODIFIED")
        if not decision.get("priority") and candidate.difference(site["core"]).area > settings.area_epsilon:
            component = site["physical_component_source_id"]
            nonround_growth_by_component[component] = nonround_growth_by_component.get(component, 0) + 1
        core_shave_area = site["core"].difference(candidate).area
        assert core_shave_area <= settings.area_epsilon, (sid, core_shave_area)
        if sid in contained:
            assert decision["decision"] == "KEEP_CIRCLE_COVERED_BY_OTHER_COPPER"
            assert decision["coverage_witness"] == contained[sid]
            assert candidate.equals_exact(site["core"], 0)
            assert decision["added_area_mm2"] == 0.0
            checked.append({"source_id": sid, "status": "PASS_EXACT_DIRECTLY_COVERED_CIRCLE_PROTECTED",
                            "covering_source_ids": [item["source_id"] for item in contained[sid][0]["covered_by_source_objects"]]})
            continue
        if sid in uncertain:
            assert decision["decision"] == "KEEP_CIRCLE_CONTAINMENT_UNCERTAIN"
            assert decision["near_boundary_source_objects"] == uncertain[sid]
            assert candidate.equals_exact(site["core"], 0)
            assert decision["added_area_mm2"] == 0.0
            checked.append({"source_id": sid, "status": "PASS_EXACT_UNCERTAIN_CIRCLE_PROTECTED",
                            "near_boundary_source_ids": [source["source_id"] for item in uncertain[sid]
                                                         for source in item["covered_by_source_objects"]]})
            continue
        if sid in singleton_ids:
            assert decision["decision"] == "KEEP_T01_ENVELOPE_SINGLETON_ROUND"
            assert candidate.equals_exact(site["core"], 0)
            checked.append({"source_id": sid, "status": "PASS_EXACT_ROUND_SINGLETON"})
            continue
        radius = decision["proposed_radius_mm"]
        cap = Point(*site["center"]).buffer(1.5 * site["radius"], quad_segs=settings.qsegs)
        envelope = unary_union([site["core"], Point(*site["center"]).buffer(radius, quad_segs=settings.qsegs)])
        assert candidate.difference(cap).area <= settings.area_epsilon
        result = verify_addition(site["core"], candidate, envelope,
                                 scene.obstacles(site, 0), settings=settings.kernel())
        assert result["passed"], (sid, result)
        checked.append({"source_id": sid, "status": "PASS_SAVED_GEOMETRY_AND_CLEARANCE",
                        "verification": result})
    assert seen == {site["source_id"] for site in all_sites}
    assert all(count <= 1 for component, count in nonround_growth_by_component.items()
               if any(component.startswith(prefix.removeprefix("PC-"))
                      for prefix in policy["growth_scope_physical_component_ids"]))
    selected_slots = saved_selection["nonround_site_by_accepted_physical_component"]
    assert set(selected_slots) <= set(policy["growth_scope_physical_component_ids"])
    assert len(set(selected_slots.values())) == len(selected_slots)
    viewport = box(*policy["viewport_mm"])
    source_crop = from_wkb((base.ROOT / "out/crop_dynamic_tasks/t02_crop_registration_20261024/org_crop.wkb").read_bytes())
    additions = from_wkb((bundle / "t01_additions_crop.wkb").read_bytes())
    after = from_wkb((bundle / "t01_multicircle_crop.wkb").read_bytes())
    reconstructed_additions = unary_union([
        from_wkb((bundle / decision["geometry"]["dynamic"]).read_bytes()).difference(by_id[decision["source_id"]]["core"])
        for decision in report["decisions"]]).intersection(viewport)
    assert additions.symmetric_difference(reconstructed_additions).area <= 1e-8
    assert after.symmetric_difference(unary_union([source_crop, additions])).area <= 1e-8
    source_loss = source_crop.difference(after)
    assert source_loss.area <= 1e-8
    result = {"status": "PASS_FRESH_PROCESS_RETRIEVAL_AND_GEOMETRY_AUDIT",
              "source_sha256": base.sha(source_path), "policy_sha256": base.sha(bundle / "policy.json"),
              "raw_circle_recognition_crosscheck": inv["circle_recognition_audit"],
              "coverage_summary_independent_replay": independently_measured_coverage,
              "t01_envelope_group_basis": policy["t01_envelope_group_basis"],
              "unique_saved_circle_candidates": len(checked),
              "eligible_independent_circle_sites": len(sites),
              "directly_covered_circle_sites": len(contained),
              "directly_covered_circle_source_ids": sorted(contained),
              "containment_uncertain_circle_sites": len(uncertain),
              "containment_uncertain_circle_source_ids": sorted(uncertain),
              "singleton_round_checks": len(singleton_ids),
              "active_growth_checks": len(active),
              "outside_accepted_physical_components_exact_round": True,
              "nonround_growth_by_physical_component": nonround_growth_by_component,
              "one_nonround_slot_per_accepted_component_check": True,
              "selected_nonround_slots": selected_slots,
              "recomputed_t01_envelope_groups": [group for group in recomputed_envelope_groups if group["size"] > 1],
              "checks": checked,
              "view_additions_reconstruct_from_saved_candidates": True,
              "view_result_reconstructs_from_org_plus_additions": True,
              "source_crop_area_loss_mm2": source_loss.area,
              "source_crop_difference_boundary_length_mm": source_loss.length,
              "source_crop_loss_tolerance_mm2": 1e-8,
              "unsupported_native_export_or_electrical_claims": "NOT_ESTABLISHED"}
    base.dump(bundle / "fresh_audit.json", result)
    print(json.dumps({k: result[k] for k in ["status", "unique_saved_circle_candidates",
                                              "eligible_independent_circle_sites",
                                              "directly_covered_circle_sites",
                                              "containment_uncertain_circle_sites",
                                              "singleton_round_checks", "active_growth_checks",
                                              "view_additions_reconstruct_from_saved_candidates",
                                              "view_result_reconstructs_from_org_plus_additions"]}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
