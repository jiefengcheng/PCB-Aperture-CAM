import hashlib
import unittest

from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Point, box

from src.crop_rect_t02 import (
    RectGrowthPolicy, execute, grow_covered_circles, physical_component_index,
    side_trace_copper_region, trace_clearance_work_items, validate_component_preservation,
)
from tools.render_t02_owner_reopening import (
    future_trace_width_reservation_html, review_relative_link, screenshot_pixel_to_scene,
)


def feature():
    return {"source_id": "rect", "source_span": [1, 2], "source_sha256": "source",
            "geometry_sha256": "rect-shape", "geometry": box(0, 0, 1, 1),
            "center_mm": [.5, .5], "source_size_mm": [1, 1], "orientation_radians": 0}


def trace(line, width=.1, identity="trace", kind="segment"):
    copper = line.buffer(width/2, quad_segs=128)
    return {"source_id": identity, "source_span": [3, 4], "source_kind": kind,
            "geometry": copper, "trace_path_geometry": line, "width_mm": width,
            "geometry_sha256": hashlib.sha256(copper.wkb).hexdigest()}


class T02OwnerReopeningTests(unittest.TestCase):
    policy = RectGrowthPolicy(trace_spacing_mode="surface_side_priority_v15")
    crop = box(-2, -2, 4, 4)

    def test_owner_screenshot_locator_uses_top_down_pixel_to_scene_y(self):
        bounds = [0.0, -10.0, 100.0, 90.0]
        frame = (10.0, 20.0, 110.0, 120.0)
        self.assertEqual(screenshot_pixel_to_scene(10, 20, bounds, frame), (0.0, 90.0))
        self.assertEqual(screenshot_pixel_to_scene(60, 70, bounds, frame), (50.0, 40.0))
        self.assertEqual(screenshot_pixel_to_scene(110, 120, bounds, frame), (100.0, -10.0))

    def test_saved_audit_link_is_relative_to_the_review_page(self):
        self.assertEqual(review_relative_link("/out/run", "/out/run/audit_v1/audit.json"),
                         "audit_v1/audit.json")
        self.assertEqual(review_relative_link("/out/run", "/out/other/audit_v1/audit.json"),
                         "../other/audit_v1/audit.json")

    def test_future_trace_width_reservation_stays_open_without_inventing_target(self):
        doc = {
            "status": "OPEN_UNQUALIFIED_FUTURE_TRACE_WIDTH_RESERVATION",
            "rectangle_review_id": "R67",
            "final_surface_gap_mm": 0.020020000072904057,
            "hard_experimental_gap_mm": 0.02,
            "trace_width_mm": 0.10008,
            "maximum_symmetric_trace_width_increase_with_route_fixed_from_this_side_only_mm": 0.000040000145808,
            "trace_width_must_not_shrink": True,
            "future_trace_width_target_mm": None,
        }
        page = future_trace_width_reservation_html(doc)
        self.assertIn("future trace-width reservation OPEN", page)
        self.assertIn("0.020020000073 mm", page)
        self.assertIn("no future width target is specified", page)
        self.assertIn("separate from the 135 clearance/attachment ledger items", page)
        self.assertIn("preserve original connectivity and attachments", page)
        self.assertIn("M1_gap_and_local_corridor.svg", page)

    def test_future_trace_width_reservation_rejects_implicit_narrowing(self):
        doc = {
            "status": "OPEN_UNQUALIFIED_FUTURE_TRACE_WIDTH_RESERVATION",
            "rectangle_review_id": "R67",
            "final_surface_gap_mm": 0.020020000072904057,
            "hard_experimental_gap_mm": 0.02,
            "trace_width_mm": 0.10008,
            "maximum_symmetric_trace_width_increase_with_route_fixed_from_this_side_only_mm": 0.000040000145808,
            "trace_width_must_not_shrink": False,
            "future_trace_width_target_mm": None,
        }
        with self.assertRaisesRegex(ValueError, "NO_SHRINK_CONTRACT_MISMATCH"):
            future_trace_width_reservation_html(doc)

    def run_feature(self, t, with_component_guard=False):
        f = feature()
        sources = {"rect": f["geometry"], t["source_id"]: t["geometry"]}
        labels, _ = physical_component_index(sources)
        return execute([f], [], self.crop, self.policy, side_traces=[t],
                       source_geometries=sources if with_component_guard else None,
                       component_by_source=labels if with_component_guard else None)

    def test_side_spacing_uses_finite_width_copper_surface_gap(self):
        t = trace(LineString([(1.13, -1), (1.13, 2)]))
        result = self.run_feature(t)
        candidate = result["candidates_by_source"]["rect"]
        self.assertGreaterEqual(candidate.distance(t["geometry"]), .02002 - 1e-9)
        self.assertLessEqual(candidate.bounds[2], 1.06)

    def test_v15_uses_surface_gap_and_keeps_corner_open(self):
        policy = RectGrowthPolicy()
        f = feature()
        side = trace(LineString([(1.13, -1), (1.13, 2)]), width=.1, identity="side")
        sources = {"rect": f["geometry"], "side": side["geometry"]}
        labels, _ = physical_component_index(sources)
        side_result = execute([f], [], self.crop, policy, side_traces=[side],
                              source_geometries=sources, component_by_source=labels)
        side_candidate = side_result["candidates_by_source"]["rect"]
        self.assertGreaterEqual(side_candidate.distance(side["geometry"]), .02002 - 1e-9)
        side_reservation = side_result["decisions"][0]["trace_gap_reservations"][0]
        self.assertEqual(side_reservation["constraint_basis"], "SIDE_SURFACE_GAP")
        self.assertEqual(side_reservation["required_surface_gap_mm"], .02002)
        self.assertEqual(side_result["component_preservation"]["new_component_connection_count"], 0)

        corner = trace(LineString([(1.08, 1.08), (1.09, 1.09)]), width=.01, identity="corner")
        corner_sources = {"rect": f["geometry"], "corner": corner["geometry"]}
        corner_labels, _ = physical_component_index(corner_sources)
        corner_result = execute([f], [], self.crop, policy, side_traces=[corner],
                                source_geometries=corner_sources, component_by_source=corner_labels)
        corner_candidate = corner_result["candidates_by_source"]["rect"]
        corner_gap = corner_candidate.distance(corner["geometry"])
        self.assertGreaterEqual(corner_gap, policy.corner_contact_separation_mm - 1e-9)
        self.assertLess(corner_gap, policy.hard_gap_mm)
        self.assertEqual(corner_result["component_preservation"]["new_component_connection_count"], 0)
        self.assertEqual(corner_result["component_preservation"]["new_source_contact_count"], 0)
        issues = corner_result["decisions"][0]["future_trace_clearance_work_items"]
        self.assertEqual(issues[0]["issue_type"], "CORNER_NEAR_GAP_REQUIRES_FUTURE_TRACE_REVIEW")
        self.assertTrue(any(item["issue_type"] == "CORNER_NEAR_GAP_REQUIRES_FUTURE_TRACE_REVIEW"
                            and item["status"] == "OPEN_FUTURE_TRACE_SESSION" for item in issues))

    def test_rotated_side_region_maps_back_to_board_coordinates(self):
        center, angle = (10.0, 20.0), 0.6
        degrees = angle * 180 / 3.141592653589793
        core = translate(rotate(box(-.5, -.5, .5, .5), degrees, origin=(0, 0)),
                         xoff=center[0], yoff=center[1])
        local_path = LineString([(-.7, .6), (.7, .6)])
        board_path = translate(rotate(local_path, degrees, origin=(0, 0)),
                               xoff=center[0], yoff=center[1])
        copper = board_path.buffer(.05, quad_segs=128)
        trace_row = {"source_id": "rotated-side", "source_kind": "segment",
                     "geometry": copper, "trace_path_geometry": board_path,
                     "width_mm": .1}
        from src.crop_rect_t02 import _scaled_rectangle
        cap = _scaled_rectangle(core, center, angle, 1.25, 1.25)
        region, labels = side_trace_copper_region(core, center, angle, cap, trace_row, .02002)
        self.assertIn("TOP", labels)
        self.assertLess(region.distance(copper), 1e-10)
        self.assertLess(region.centroid.distance(copper.centroid), 1e-9)

    def test_short_parallel_trace_near_end_of_side_cannot_earn_corner_exemption(self):
        t = trace(LineString([(1.13, .92), (1.13, 1.08)]))
        result = self.run_feature(t)
        self.assertTrue(result["decisions"][0]["trace_gap_reservations"][0]["side_by_side_classification"])
        self.assertGreaterEqual(result["candidates_by_source"]["rect"].distance(t["geometry"]), .02)

    def test_arc_is_checked_by_local_side_section(self):
        t = trace(LineString([(1.13, -.3), (1.10, 0), (1.10, 1), (1.13, 1.3)]), kind="arc")
        region, sides = side_trace_copper_region(feature()["geometry"], [.5, .5], 0,
                                                 box(-.125, -.125, 1.125, 1.125), t, .02002)
        self.assertIn("RIGHT", sides)
        self.assertFalse(region.is_empty)
        result = self.run_feature(t)
        self.assertGreaterEqual(result["candidates_by_source"]["rect"].distance(region), .02)

    def test_disconnected_corner_growth_cannot_merge_source_components(self):
        t = trace(LineString([(1.08, 1.08), (1.09, 1.09)]), width=.01)
        corrected = self.run_feature(t, with_component_guard=True)
        self.assertEqual(corrected["component_preservation"]["new_component_connection_count"], 0)
        corner_gap = corrected["candidates_by_source"]["rect"].distance(t["geometry"])
        self.assertGreaterEqual(corner_gap, self.policy.corner_contact_separation_mm - 1e-9)
        self.assertLess(corner_gap, self.policy.hard_gap_mm)
        self.assertTrue(any(item["issue_type"] == "CORNER_NEAR_GAP_REQUIRES_FUTURE_TRACE_REVIEW"
                            and item["status"] == "OPEN_FUTURE_TRACE_SESSION"
                            for item in corrected["decisions"][0]["future_trace_clearance_work_items"]))
        sources = {"rect": feature()["geometry"], "trace": t["geometry"]}
        labels, _ = physical_component_index(sources)
        negative = validate_component_preservation(sources, labels, {"rect": box(0, 0, 1.1, 1.1).difference(box(0, 0, 1, 1))})
        self.assertEqual(negative["status"], "FAIL_NEW_COMPONENT_CONNECTION")

    def test_component_guard_detects_point_contact_between_two_additions(self):
        sources = {"a": box(0, 0, 1, 1), "b": box(2, 2, 3, 3)}
        labels, _ = physical_component_index(sources)
        result = validate_component_preservation(sources, labels,
            {"a": box(1, 1, 1.5, 1.5), "b": box(1.5, 1.5, 2, 2)})
        self.assertGreater(result["new_component_connection_count"], 0)

    def test_same_component_corner_cannot_create_a_new_local_contact_pair(self):
        f = feature()
        t = trace(LineString([(1.08, 1.08), (1.09, 1.09)]), width=.01)
        connector = LineString([(.5, .5), (.5, 2), (1.08, 2), (1.08, 1.08)]).buffer(.005)
        sources = {"rect": f["geometry"], "trace": t["geometry"], "connector": connector}
        labels, _ = physical_component_index(sources)
        self.assertEqual(labels["rect"], labels["trace"])
        result = execute([f], [], self.crop, self.policy, side_traces=[t],
                         source_geometries=sources, component_by_source=labels)
        self.assertEqual(result["component_preservation"]["new_source_contact_count"], 0)
        self.assertFalse(result["candidates_by_source"]["rect"].intersects(t["geometry"]))
        issues = result["decisions"][0]["future_trace_clearance_work_items"]
        self.assertTrue(any(x["issue_type"] == "CORNER_NEAR_GAP_REQUIRES_FUTURE_TRACE_REVIEW" for x in issues))

    def test_baseline_short_side_gap_remains_explicit_open_issue_without_overlap(self):
        t = trace(LineString([(1.015, -1), (1.015, 2)]), width=.01)
        result = self.run_feature(t)
        issues = result["decisions"][0]["future_trace_clearance_work_items"]
        self.assertTrue(any(x["issue_type"] == "SOURCE_SIDE_GAP_REQUIRES_FUTURE_TRACE_REPAIR" for x in issues))
        self.assertEqual(issues[0]["overlap_area_mm2"], 0)
        self.assertFalse(issues[0]["trace_changed_in_t02"])

    def test_baseline_side_gap_below_hard_floor_is_open_inside_tolerance(self):
        # 0.019999 mm is below the 0.020000 mm floor by less than the
        # 0.000010 mm comparison tolerance. It must not be reported as safe.
        t = trace(LineString([(1.069999, -1), (1.069999, 2)]), width=.1)
        result = self.run_feature(t)
        decision = result["decisions"][0]
        issues = decision["future_trace_clearance_work_items"]
        self.assertEqual(decision["decision"], "KEEP")
        self.assertAlmostEqual(decision["trace_gap_reservations"][0]["org_surface_gap_mm"], .019999, places=9)
        self.assertTrue(any(x["issue_type"] == "SOURCE_SIDE_GAP_REQUIRES_FUTURE_TRACE_REPAIR" for x in issues))
        issue = next(x for x in issues if x["issue_type"] == "SOURCE_SIDE_GAP_REQUIRES_FUTURE_TRACE_REPAIR")
        self.assertTrue(issue["side_gap_below_hard_floor"])
        self.assertEqual(issue["hard_floor_assessment"], "BELOW_HARD_FLOOR_WITHIN_COMPARISON_TOLERANCE")
        self.assertEqual(issue["status"], "OPEN_FUTURE_TRACE_SESSION")

    def test_baseline_side_gap_exactly_at_floor_is_not_labeled_below_floor(self):
        t = trace(LineString([(1.07, -1), (1.07, 2)]), width=.1)
        result = self.run_feature(t)
        issues = result["decisions"][0]["future_trace_clearance_work_items"]
        self.assertFalse(any(x["issue_type"] == "SOURCE_SIDE_GAP_REQUIRES_FUTURE_TRACE_REPAIR"
                             for x in issues))

    def test_existing_diagonal_attachment_allows_corner_growth_without_component_merge(self):
        t = trace(LineString([(.9, .9), (1.10, 1.10)]), width=.01)
        result = self.run_feature(t, with_component_guard=True)
        self.assertEqual(result["decisions"][0]["decision"], "GROW")
        self.assertTrue(result["decisions"][0]["future_trace_overlap_records"])
        self.assertEqual(result["component_preservation"]["new_component_connection_count"], 0)

    def test_attachment_port_is_local_and_does_not_exempt_entire_side_trace(self):
        f = feature()
        t = trace(LineString([(1.03, .4), (1.03, 2)]), width=.1)
        region, sides = side_trace_copper_region(f["geometry"], [.5, .5], 0,
                                                 box(-.125, -.125, 1.125, 1.125), t, .02002)
        self.assertFalse(region.is_empty)
        self.assertFalse(region.intersects(f["geometry"]))
        self.assertIn("RIGHT", sides)
        deliberately_bad_cap = box(-.125, -.125, 1.125, 1.125)
        self.assertLess(deliberately_bad_cap.distance(region), self.policy.hard_gap_mm)
        actual = self.run_feature(t)["candidates_by_source"]["rect"]
        self.assertGreaterEqual(actual.distance(region), self.policy.construction_gap_mm - 1e-10)

    def circle_inputs(self, parent):
        core = Point(0, 0).buffer(.1, quad_segs=128)
        site = {"source_id": "circle", "aliases": ["circle"], "core": core,
                "center": [0, 0], "radius": .1, "geometry_sha256": "circle-core"}
        rows = [{"id": "circle", "source_span": [1, 2]}, {"id": "parent", "source_span": [3, 4]}]
        return [site], rows, {"circle": core, "parent": parent}

    def test_embedded_circle_selects_largest_covered_class_below_1_5_cap(self):
        args = self.circle_inputs(box(-.2, -.2, .2, .2))
        result = grow_covered_circles(*args, {}, box(-1, -1, 1, 1), [.2, .25, .3, .4])
        row = result["records"][0]
        self.assertEqual(row["selected_diameter_mm"], .3)
        self.assertEqual(row["visible_added_copper_mm2"], 0)
        self.assertTrue(all(row["checks"].values()))
        self.assertEqual(row["category_candidates"][0]["status"], "EXCEEDS_1_5X_CAP")

    def test_embedded_circle_uses_final_same_parent_and_exact_containment(self):
        args = self.circle_inputs(box(-.11, -.11, .11, .11))
        result = grow_covered_circles(*args, {"parent": box(-.13, -.13, .13, .13)},
                                      box(-1, -1, 1, 1), [.2, .25, .3])
        self.assertEqual(result["records"][0]["selected_diameter_mm"], .25)
        self.assertTrue(result["all_checks_pass"])

    def test_embedded_circle_does_not_infer_coverage_from_union_or_near_cover(self):
        sites, rows, shapes = self.circle_inputs(box(-.1+1e-11, -.2, .2, .2))
        shapes["left"] = box(-.2, -.2, 0, .2)
        rows.append({"id": "left", "source_span": [5, 6]})
        result = grow_covered_circles(sites, rows, shapes, {}, box(-1, -1, 1, 1), [.25, .3])
        self.assertEqual(result["count"], 0)


if __name__ == "__main__":
    unittest.main()
