"""Read-only saved-output audit for the owner's reopened T02 requirements.

Fresh process, shared native parser and Shapely. This is not an independent
geometry kernel, electrical verification, manufacturing approval or owner vote.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sexpdata import loads
from shapely import STRtree, wkb
from shapely.affinity import rotate, scale, translate
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

from src.crop_rect_t02 import physical_component_index, side_trace_copper_region, _scaled_rectangle
from src.native_inventory import arc_points
from src.native_reference import one
from src.org_edit_target_map import _inventory_side, _row_geometry


def digest(data):
    return hashlib.sha256(data).hexdigest()


def audit(run, output):
    policy = json.loads((run / "t02_policy.json").read_bytes())
    result = json.loads((run / "t02_result.json").read_bytes())
    decisions = json.loads((run / "t02_decisions.json").read_bytes())["decisions"]
    source = (ROOT / policy["source"]).read_bytes()
    assert digest(source) == policy["source_sha256"] == result["source_sha256"], "SOURCE_BINDING"
    assert digest((run / "t02_policy.json").read_bytes()) == result["policy_sha256"], "POLICY_BINDING"
    rule_mode = policy["trace_interactions"]["rule_mode"]
    assert rule_mode == "surface_side_priority_v15", "CURRENT_T02_AUDIT_REQUIRES_SURFACE_GAP_POLICY_V15"
    inv = _inventory_side(source, digest(source))
    rows = {row["id"]: row for row in inv["rows"] if "F.Cu" in row.get("layers", [])}
    assert all(row.get("coverage") == "GEOMETRY_AVAILABLE" for row in rows.values()), "UNSUPPORTED_FCU"
    geometries = {sid: _row_geometry(row, inv["payloads"]) for sid, row in rows.items()}
    labels, members = physical_component_index(geometries)
    stored_labels = json.loads((run / "physical_component_membership.json").read_bytes())
    assert stored_labels["component_by_source"] == labels, "SOURCE_COMPONENT_MEMBERSHIP"
    crop = box(*policy["crop_bounds_org_mm"])
    hard, tol = policy["hard_experimental_gap_mm"], policy["geometry_tolerance_mm"]
    trace_rows = []
    for sid, row in rows.items():
        if row["kind"] not in policy["trace_interactions"]["trace_source_kinds"]:
            continue
        node = loads(source[slice(*row["source_span"])].decode())
        xy = lambda key: tuple(map(float, one(node, key)))
        points = arc_points(xy("start"), xy("mid"), xy("end")) if row["kind"] == "arc" else [xy("start"), xy("end")]
        trace_rows.append({"source_id": sid, "source_span": row["source_span"],
            "source_kind": row["kind"], "geometry": geometries[sid],
            "trace_path_geometry": LineString(points), "width_mm": float(one(node, "width")[0]),
            "geometry_sha256": row["geometry_sha256"]})
    candidates, additions, side_checks, baseline_side_issues = {}, {}, [], []
    interaction_pairs_scanned, side_surface_pairs, corner_surface_pairs = 0, [], []
    side_safe_corner_pairs = []
    port_witnesses, port_shapes = [], {}
    for d in decisions:
        sid = d["source_id"]
        core = geometries[sid]
        candidate = wkb.loads((run / "t02_candidates" / (digest(sid.encode()) + ".wkb")).read_bytes())
        assert digest(candidate.wkb) == d["candidate_geometry_sha256"], "CANDIDATE_HASH"
        assert candidate.geom_type == "Polygon" and len(candidate.exterior.coords) == 5 and not candidate.interiors, "RECTANGLE_RECESSED"
        assert candidate.centroid.distance(core.centroid) <= 1e-10, "RECTANGLE_CENTER_MOVED"
        assert core.difference(candidate).area <= 1e-10, "RECTANGLE_CORE_LOSS"
        cap = _scaled_rectangle(core, core.centroid.coords[0], d["orientation_radians"],
                                policy["factor_per_axis"], policy["factor_per_axis"])
        assert candidate.difference(cap).area <= 1e-10 and crop.covers(candidate), "RECTANGLE_CAP_OR_CROP"
        candidates[sid] = candidate
        growth = candidate.difference(core)
        if not growth.is_empty:
            additions[sid] = growth
        for trace in trace_rows:
            interaction_pairs_scanned += 1
            if trace["geometry"].distance(cap) > policy["construction_gap_mm"] + tol:
                continue
            region, sides = side_trace_copper_region(core, core.centroid.coords[0], d["orientation_radians"],
                                                     cap, trace, policy["construction_gap_mm"])
            if core.intersects(trace["geometry"]):
                center = core.centroid.coords[0]
                angle = math.degrees(d["orientation_radians"])
                local_core = translate(rotate(core, -angle, origin=center), xoff=-center[0], yoff=-center[1])
                local_trace = translate(rotate(trace["geometry"], -angle, origin=center), xoff=-center[0], yoff=-center[1])
                contact = local_core.intersection(local_trace)
                local_port = contact.buffer(trace["width_mm"] + policy["construction_gap_mm"], quad_segs=128)
                port = rotate(translate(local_port, xoff=center[0], yoff=center[1]), angle, origin=center)
                assert region.intersection(port).area <= 1e-10, "PORT_EXCEPTION_REMOVES_PROTECTED_OUTSIDE_REGION"
                witness_id = digest((sid + trace["source_id"]).encode())
                port_shapes[witness_id + "_port.wkb"] = port.wkb
                port_shapes[witness_id + "_protected_side.wkb"] = region.wkb
                port_shapes[witness_id + "_source_contact_local.wkb"] = contact.wkb
                port_witnesses.append({"rectangle_source_id": sid, "rectangle_source_span": rows[sid]["source_span"],
                    "trace_source_id": trace["source_id"], "trace_source_span": trace["source_span"],
                    "source_sha256": digest(source), "native_trace_width_mm": trace["width_mm"],
                    "contact_geometry_sha256_in_rectangle_frame": digest(contact.wkb),
                    "source_contact_geometry_file_in_rectangle_frame": "port_witness_geometries/" + witness_id + "_source_contact_local.wkb",
                    "rectangle_frame_center_mm": list(center), "rectangle_frame_orientation_radians": d["orientation_radians"],
                    "exemption_buffer_mm": trace["width_mm"] + policy["construction_gap_mm"],
                    "exemption_geometry_file": "port_witness_geometries/" + witness_id + "_port.wkb",
                    "exemption_geometry_sha256": digest(port.wkb),
                    "protected_side_geometry_file": "port_witness_geometries/" + witness_id + "_protected_side.wkb",
                    "protected_side_geometry_sha256": digest(region.wkb),
                    "protected_side_final_gap_mm": candidate.distance(region) if not region.is_empty else None,
                    "protected_side_original_gap_mm": core.distance(region) if not region.is_empty else None,
                    "qualification": "source-bound local geometric port neighborhood; owner acceptance pending"})
            if region.is_empty:
                final_surface_gap = candidate.distance(trace["geometry"])
                original_surface_gap = core.distance(trace["geometry"])
                if (not core.intersects(trace["geometry"]) and
                        (final_surface_gap < hard or original_surface_gap < hard)):
                    corner_surface_pairs.append({"rectangle_source_id": sid, "rectangle_source_span": rows[sid]["source_span"],
                        "trace_source_id": trace["source_id"], "trace_source_span": trace["source_span"],
                        "original_surface_gap_mm": original_surface_gap,
                        "candidate_surface_gap_mm": final_surface_gap,
                        "classification": "NOT_SIDE_BY_SIDE_UNDER_LOCAL_SECTION_CLASSIFIER; OPEN_CORNER_OR_ENDPOINT"})
                continue
            before_gap, after_gap = core.distance(region), candidate.distance(region)
            check = {"rectangle_source_id": sid, "trace_source_id": trace["source_id"],
                     "side_labels": sides, "original_surface_gap_mm": before_gap,
                     "final_surface_gap_mm": after_gap, "required_hard_gap_mm": hard,
                     "measurement_reference": "FINITE_WIDTH_TRACE_COPPER_SURFACE",
                     "hard_floor_assessment": ("BELOW_HARD_FLOOR_WITHIN_COMPARISON_TOLERANCE"
                         if after_gap < hard and after_gap + tol >= hard else
                         "BELOW_HARD_FLOOR_BEYOND_COMPARISON_TOLERANCE"
                         if after_gap < hard else "AT_OR_ABOVE_HARD_FLOOR"),
                     "new_growth_gap_mm": growth.distance(region) if not growth.is_empty else None,
                     "construction_gap_mm": policy["construction_gap_mm"]}
            assert growth.is_empty or growth.distance(region) + 1e-12 >= policy["construction_gap_mm"], "NEW_SIDE_GROWTH_BELOW_CONSTRUCTION_TARGET"
            if after_gap < hard:
                # A sub-floor value is still an open defect when its deficit
                # is within the declared reporting tolerance; tolerance is not
                # a clearance waiver.
                assert before_gap < hard and after_gap + 1e-12 >= before_gap, "NEW_OR_WORSENED_SIDE_GAP_FAILURE"
                baseline_side_issues.append(check)
            side_checks.append(check)
            side_surface_pairs.append(check)
            # A side-local trace section can meet its gap target while a
            # different corner/endpoint of the same trace remains too close.
            # Keep that independent whole-contour issue OPEN; do not conflate
            # it with a side-gap failure or let it waive the side constraint.
            whole_contour_gap = candidate.distance(trace["geometry"])
            if whole_contour_gap < hard and after_gap >= hard:
                side_safe_corner_pairs.append({
                    "rectangle_source_id": sid, "rectangle_source_span": rows[sid]["source_span"],
                    "trace_source_id": trace["source_id"], "trace_source_span": trace["source_span"],
                    "original_surface_gap_mm": core.distance(trace["geometry"]),
                    "candidate_surface_gap_mm": whole_contour_gap,
                    "side_surface_gap_mm": after_gap,
                    "side_labels": sides,
                    "classification": "SIDE_GAP_CHECKED_SEPARATELY; OPEN_CORNER_OR_ENDPOINT",
                })

    addition_union = unary_union(list(additions.values()))
    saved_additions = wkb.loads((run / "t02_additions.wkb").read_bytes())
    assert saved_additions.symmetric_difference(addition_union).area <= 1e-10, "ADDITION_RECONSTRUCTION"
    owner = json.loads((ROOT / "contracts/agent_abi/v0_1/owner_decisions.json").read_bytes())["decisions"][result["accepted_T01_decision_id"]]
    profiles = json.loads((ROOT / "contracts/agent_abi/v0_1/registry.json").read_bytes())["profiles"]
    profile = profiles[owner["profile_id"]]
    scene_bytes = (ROOT / profile["scene"]["path"]).read_bytes()
    assert digest(scene_bytes) == owner["scene_sha256"] == result["accepted_T01_scene_sha256"], "T01_SCENE_BINDING"
    t01_scene = wkb.loads(scene_bytes)
    t01_report_path = ROOT / profile["artifacts"]["report"]["path"]
    t01_report = json.loads(t01_report_path.read_bytes())
    frozen_growth_by_component = defaultdict(list)
    final_source_geometries = dict(geometries)
    for decision in t01_report["decisions"]:
        contour = wkb.loads((Path(ROOT / profile["scene"]["path"]).parent / decision["geometry"]["dynamic"]).read_bytes())
        frozen_growth = contour.difference(geometries[decision["source_id"]]).intersection(crop)
        if not frozen_growth.is_empty:
            frozen_growth_by_component[labels[decision["source_id"]]].append(frozen_growth)
            final_source_geometries[decision["source_id"]] = geometries[decision["source_id"]].union(frozen_growth)
    combined = wkb.loads((run / "t01_accepted_plus_t02.wkb").read_bytes())
    assert t01_scene.difference(combined).area <= 1e-10, "T01_COPPER_LOSS"
    assert combined.symmetric_difference(t01_scene.union(saved_additions)).area <= 1e-10, "FINAL_COMPOSITION"

    # Separate saved-output check: union each complete original component and
    # all owned additions, then test those component regions for new contact.
    comp_ids = sorted(members)
    regions, topology_changes = [], []
    def hole_count(g):
        return len(g.interiors) if g.geom_type == "Polygon" else sum(hole_count(part) for part in g.geoms)
    for cid in comp_ids:
        before = unary_union([geometries[s] for s in members[cid]] + frozen_growth_by_component[cid])
        after = unary_union([before] + [g for sid, g in additions.items() if labels[sid] == cid])
        if hole_count(before) != hole_count(after):
            topology_changes.append({"component": cid, "holes_before": hole_count(before), "holes_after": hole_count(after)})
        regions.append(after)
    assert not topology_changes, "COMPONENT_HOLE_TOPOLOGY_CHANGED:" + str(topology_changes)
    tree = STRtree(regions)
    for i, region in enumerate(regions):
        assert all(int(j) == i for j in tree.query(region, predicate="intersects")), "FINAL_COMPONENTS_MERGED"
    # Physical partition alone does not rule out a new short-circuit contact
    # between branches already connected elsewhere. Check source adjacency too.
    ids = sorted(geometries)
    source_tree = STRtree([geometries[sid] for sid in ids])
    for sid, growth in additions.items():
        for i in source_tree.query(growth, predicate="intersects"):
            other = ids[int(i)]
            assert other == sid or geometries[sid].intersects(geometries[other]), "NEW_LOCAL_SOURCE_CONTACT"
        final_source_geometries[sid] = final_source_geometries[sid].union(growth)
    # Recompute the complete final partition from actual source contributions,
    # rather than concluding no splits solely from absence of bridge records.
    final_labels, final_members = physical_component_index(final_source_geometries)
    assert final_labels == labels, "ORIGINAL_VS_FINAL_COMPONENT_PARTITION_MISMATCH"
    retained_contacts = 0
    contact_hash = hashlib.sha256()
    for i, sid in enumerate(ids):
        assert final_source_geometries[sid].covers(geometries[sid]), "SOURCE_CONTRIBUTION_REMOVED"
        for j in source_tree.query(geometries[sid], predicate="intersects"):
            j = int(j)
            if j <= i:
                continue
            other = ids[j]
            assert final_source_geometries[sid].intersects(final_source_geometries[other]), "ORIGINAL_SOURCE_CONTACT_LOST"
            contact_hash.update((sid + "\t" + other + "\n").encode())
            retained_contacts += 1

    # Inventory exact fully covered circle sites independently of the recorded
    # embedded decisions. Parent unions never count as one coverage witness.
    aliases = defaultdict(list)
    for sid, row in rows.items():
        if row["kind"] != "gr_circle" or not geometries[sid].intersects(crop):
            continue
        node = loads(source[slice(*row["source_span"])].decode())
        if str(one(node, "fill", ["none"])[0]) in ("yes", "solid"):
            aliases[row["geometry_sha256"]].append(sid)
    expected_covered = {}
    for alias_ids in aliases.values():
        sid = min(alias_ids)
        core = geometries[sid]
        parents = sorted(ids[int(i)] for i in source_tree.query(core, predicate="intersects")
                         if ids[int(i)] not in alias_ids and geometries[ids[int(i)]].covers(core))
        if parents:
            expected_covered[sid] = parents
    embedded = json.loads((run / "embedded_covered_circles.json").read_bytes())
    assert set(expected_covered) == {r["source_id"] for r in embedded["records"]}, "COVERED_SITE_CENSUS"
    classes = policy["embedded_covered_circle_pass"]["diameter_classes_mm"]
    frozen_t01_policy = json.loads((ROOT / profile["artifacts"]["policy"]["path"]).read_bytes())
    assert classes == frozen_t01_policy["diameter_classes_mm"], "COVERED_CIRCLE_PALETTE_DIFFERS_FROM_ACCEPTED_T01"
    promoted = 0
    latent_geometries, unpromoted = [], []
    for row in embedded["records"]:
        sid = row["source_id"]
        original = geometries[sid]
        node = loads(source[slice(*rows[sid]["source_span"])].decode())
        center = tuple(map(float, one(node, "center")))
        end = tuple(map(float, one(node, "end")))
        radius = math.dist(center, end)
        candidate = wkb.loads((run / "t02_embedded_circles" / (digest(sid.encode()) + ".wkb")).read_bytes())
        latent_geometries.append(candidate)
        assert candidate.geom_type == "Polygon", "COVERED_CIRCLE_IS_NOT_FILLED_GEOMETRY"
        assert candidate.centroid.distance(Point(*center)) <= 1e-10, "COVERED_CIRCLE_CENTER_MOVED"
        assert candidate.covers(original), "COVERED_CIRCLE_CORE_LOSS"
        parent_id = row["parent_source_id"]
        assert parent_id in expected_covered[sid], "COVERED_PARENT_NOT_ORG_BOUND"
        parent = candidates.get(parent_id, geometries[parent_id])
        assert parent.covers(candidate), "COVERED_CIRCLE_EXPOSED"
        # The saved scene is clipped to the review crop. Unchanged source
        # circles crossing its boundary remain covered by their full native
        # parent; compare only their in-crop portion to this saved scene.
        assert candidate.intersection(crop).difference(combined).area <= 1e-10, "COVERED_CIRCLE_EXPOSED_IN_FINAL_SCENE"
        admissible = []
        for diameter in classes:
            proposed = Point(*center).buffer(diameter/2, quad_segs=128)
            if (diameter > radius*2 + 1e-12 and diameter <= radius*3 + 1e-12 and
                    proposed.covers(original) and crop.covers(proposed) and
                    any(candidates.get(pid, geometries[pid]).covers(proposed) for pid in expected_covered[sid])):
                admissible.append(diameter)
        if admissible:
            selected = max(admissible)
            assert abs(row["selected_diameter_mm"] - selected) <= 1e-12, "COVERED_CIRCLE_NOT_LARGEST_CLASS"
            assert candidate.equals(Point(*center).buffer(selected/2, quad_segs=128)), "COVERED_CIRCLE_NOT_ROUND"
            promoted += 1
        else:
            assert candidate.equals_exact(original, 0), "COVERED_CIRCLE_UNAUTHORIZED_CHANGE"
            unpromoted.append({"source_id": sid, "decision": row["decision"],
                               "source_diameter_mm": radius*2,
                               "category_rejection_evidence": row["category_candidates"]})
    latent_delta = combined.symmetric_difference(combined.union(unary_union(latent_geometries).intersection(crop))).area
    assert latent_delta <= 1e-10, "EMBEDDED_PASS_CHANGES_EXPOSED_COPPER"
    protected_rounds = []
    for decision in t01_report["decisions"]:
        if decision["source_id"] in expected_covered:
            continue
        contour = wkb.loads((Path(ROOT / profile["scene"]["path"]).parent / decision["geometry"]["dynamic"]).read_bytes())
        assert saved_additions.distance(contour) + tol >= hard, "T02_ENCROACHES_UNCOVERED_T01_ROUND_SITE"
        protected_rounds.append(decision["source_id"])

    ledger = json.loads((run / "future_trace_work_items.json").read_bytes())
    expected_pairs = set()
    for sid, growth in additions.items():
        for trace in trace_rows:
            if growth.intersection(trace["geometry"]).area > 1e-12:
                expected_pairs.add((sid, trace["source_id"]))
    assert expected_pairs == {(x["rectangle_source_id"], x["trace_source_id"]) for x in ledger["items"]}, "OVERLAP_LEDGER_INCOMPLETE"
    for issue in ledger["clearance_issues"]:
        assert issue["status"] == "OPEN_FUTURE_TRACE_SESSION" and not issue["repair_applied"] and not issue["trace_changed_in_t02"], "ISSUE_NOT_DEFERRED"
    open_pairs = {(x["rectangle_source_id"], x["trace_source_id"]) for x in ledger["clearance_issues"]}
    open_pairs |= {(x["rectangle_source_id"], x["trace_source_id"]) for x in ledger["items"]}
    corner_issue_pairs = {
        (x["rectangle_source_id"], x["trace_source_id"])
        for x in ledger["clearance_issues"]
        if x["issue_type"] in {
            "CORNER_NEAR_GAP_REQUIRES_FUTURE_TRACE_REVIEW",
            "CORNER_OVERLAP_REQUIRES_FUTURE_TRACE_REVIEW",
        }
    }
    census_corner_pairs = {
        (x["rectangle_source_id"], x["trace_source_id"])
        for x in corner_surface_pairs + side_safe_corner_pairs
    }
    assert census_corner_pairs == corner_issue_pairs, "CORNER_OPEN_PAIR_CROSSWALK_MISMATCH"
    missing_corner_pairs = census_corner_pairs - open_pairs
    assert not missing_corner_pairs, "CORNER_TRACE_INTERACTION_NOT_OPEN:" + repr(sorted(missing_corner_pairs)[:5])
    for check in baseline_side_issues:
        assert any(x["rectangle_source_id"] == check["rectangle_source_id"] and x["trace_source_id"] == check["trace_source_id"]
                   and x["issue_type"] == "SOURCE_SIDE_GAP_REQUIRES_FUTURE_TRACE_REPAIR" for x in ledger["clearance_issues"]), "BASELINE_SIDE_ISSUE_OMITTED"
    negative = json.loads((run / "rejected_v31_component_negative_control.json").read_bytes())
    assert negative["new_component_connection_count"] > 0, "LEGACY_BRIDGE_NEGATIVE_CONTROL_DID_NOT_FAIL"
    # Deliberately violate a protected section just beyond an original port.
    fixture_core = box(0, 0, 1, 1)
    fixture_trace = {"source_id": "port-control", "source_kind": "segment", "width_mm": .1,
                     "trace_path_geometry": LineString([(1.03, .4), (1.03, 2)])}
    fixture_trace["geometry"] = fixture_trace["trace_path_geometry"].buffer(.05, quad_segs=128)
    bad_cap = box(-.125, -.125, 1.125, 1.125)
    protected_section, _ = side_trace_copper_region(fixture_core, (.5, .5), 0, bad_cap, fixture_trace, .02002)
    assert not protected_section.is_empty and bad_cap.distance(protected_section) + tol < hard, "OUTSIDE_PORT_NEGATIVE_CONTROL_DID_NOT_FAIL"
    surface_gaps = [row["final_surface_gap_mm"] for row in side_checks]
    expected_pair_count = len(decisions) * len(trace_rows)
    assert interaction_pairs_scanned == expected_pair_count, "TRACE_PAIRWISE_CENSUS_INCOMPLETE"
    report = {"schema": "t02-owner-reopening-audit/5",
              "status": "PASS_BOUNDED_CHECKS_WITH_OPEN_TRACE_ISSUES",
              "source_sha256": digest(source), "accepted_T01_scene_sha256": digest(scene_bytes),
              "policy_sha256": result["policy_sha256"], "run": run.name,
              "target_count": len(decisions), "rectangle_centers_and_caps_preserved": True,
              "original_source_component_count": len(members), "new_component_connections": 0,
              "final_source_component_count": len(final_members), "original_final_partition_membership_equal": final_labels == labels,
              "original_partition_sha256": digest(json.dumps(labels,sort_keys=True).encode()),
              "final_partition_sha256": digest(json.dumps(final_labels,sort_keys=True).encode()),
              "source_contributions_preserved": len(geometries), "original_source_contacts_retained": retained_contacts,
              "original_source_contact_set_sha256": contact_hash.hexdigest(),
              "source_bound_attachment_port_witnesses": len(port_witnesses),
              "baseline_side_gap_issue_count": len(baseline_side_issues),
              "owner_side_surface_check_count": len(surface_gaps),
              "minimum_owner_side_surface_gap_mm": min(surface_gaps) if surface_gaps else None,
              "rectangle_trace_pairwise_evaluations": interaction_pairs_scanned,
              "trace_records_in_pairwise_scan": len(trace_rows),
              "side_classified_surface_pairs": len(side_surface_pairs),
              "corner_only_open_pairs": len(corner_surface_pairs),
              "side_safe_corner_open_pairs": len(side_safe_corner_pairs),
              "corner_or_endpoint_open_pairs": len(census_corner_pairs),
              "corner_ledger_crosswalk_exact": census_corner_pairs == corner_issue_pairs,
              "surface_gap_diagnostic_count_below_hard_floor": sum(row["final_surface_gap_mm"] < hard for row in side_checks),
              "side_gap_tolerance_is_not_a_minimum_waiver": True,
              "outside_attachment_port_bad_cap_negative_control": "FAIL_EXPECTED_PROTECTED_SIDE_VIOLATION",
              "new_local_source_contact_pairs": 0, "side_copper_checks": len(side_checks),
              "component_hole_topology_changes": topology_changes,
              "new_or_worsened_side_gap_failures": 0, "baseline_side_gap_issues": baseline_side_issues,
              "uncovered_T01_round_sites_protected": len(protected_rounds),
              "exact_covered_circle_sites": len(expected_covered), "largest_covered_round_classes_promoted": promoted,
              "embedded_circle_exposed_added_copper_mm2": 0.0,
              "embedded_promotion_delta_vs_pre_promotion_T02_scene_mm2": latent_delta,
              "embedded_palette_matches_accepted_T01": True, "unpromoted_covered_sites": unpromoted,
              "trace_overlap_pairs_checked": len(expected_pairs),
              "open_trace_work_items": len(ledger["clearance_issues"]),
              "trace_issue_counts": dict(Counter(x["issue_type"] for x in ledger["clearance_issues"])),
              "legacy_v31_new_component_contacts": negative["new_component_connection_count"],
              "owner_acceptance": "PENDING_USER", "trace_geometry_changed": False,
              "limitations": ["Fresh process using the existing parser and Shapely; not independent parser/kernel verification.",
                              "Existing native sub-minimum gaps and recorded corner/attachment issues remain open for a future trace task.",
                              "Physical source-contact graph preservation does not establish electrical intent, manufacturing acceptance or T03 authorization."]}
    output.mkdir(parents=True, exist_ok=False)
    (output / "audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output / "side_gap_checks.json").write_text(json.dumps(side_checks, indent=2, sort_keys=True) + "\n")
    census = {"schema":"t02-trace-interaction-census/3", "source_sha256":digest(source),
            "run":run.name, "policy_sha256":result["policy_sha256"], "rectangle_target_count":len(decisions),
            "trace_record_count":len(trace_rows), "all_rectangle_trace_pairs_evaluated":interaction_pairs_scanned,
            "expected_pair_count":expected_pair_count, "scan_complete":interaction_pairs_scanned==expected_pair_count,
            "side_classifier":"side_trace_copper_region over every candidate-cap/trace pair within copper-envelope prefilter; records native segment/arc section results",
            "required_side_surface_gap_mm":policy["construction_gap_mm"],
            "side_surface_pairs":side_surface_pairs,
            "corner_only_open_pairs":corner_surface_pairs,
            "side_safe_corner_open_pairs":side_safe_corner_pairs,
            "corner_or_endpoint_open_pairs":corner_surface_pairs + side_safe_corner_pairs,
            "limitations":["Same parser, Shapely and side-section classifier; not an independent geometry kernel.",
                "A close pair classified outside side sections is recorded as an OPEN corner or endpoint issue and does not weaken any side spacing rule.",
                "Annotation M4 source-coordinate mapping remains unresolved."]}
    (output / "trace_interaction_census.json").write_text(json.dumps(census,indent=2,sort_keys=True)+"\n")
    (output / "attachment_port_witnesses.json").write_text(json.dumps(port_witnesses,indent=2,sort_keys=True)+"\n")
    (output / "port_witness_geometries").mkdir()
    for name, payload in port_shapes.items():
        (output / "port_witness_geometries" / name).write_bytes(payload)
    (output / "SHA256SUMS.txt").write_text("".join(f"{digest(p.read_bytes())}  {p.relative_to(output).as_posix()}\n" for p in sorted(output.rglob('*')) if p.is_file()))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.run.resolve(), args.output.resolve()), indent=2))
