import unittest
import json
from pathlib import Path

from shapely.geometry import Point, Polygon, box
from src.crop_circle_sources import _raw_filled_circle_scan

from tools.run_crop_t01_multicircle_crop import (
    exclude_circles_contained_by_source_shape,
    circle_coverage_summary,
    local_competition_components,
    physical_contact_components,
    choose_component_nonround_sites,
)


def site(source_id, x, diameter):
    core = Point(x, 0).buffer(diameter / 2, quad_segs=32)
    return {"source_id": source_id, "center": [x, 0],
            "radius": diameter / 2, "core": core}


def physical_site(source_id, x, physical_group):
    result = site(source_id, x, 0.25)
    result["physical_contact_group"] = physical_group
    result["physical_component_source_id"] = physical_group
    return result


class LocalCompetitionTests(unittest.TestCase):
    def test_crop_policy_keeps_local_envelope_groups_as_t01_definition(self):
        policy_path = Path(__file__).resolve().parents[1] / "contracts/crop_t01_multicircle_crop_policy.json"
        policy = json.loads(policy_path.read_text())
        self.assertEqual(policy["t01_envelope_group_basis"], "growth_envelope_competition")
        self.assertIn("construction_gap_mm", policy["t01_envelope_group_definition"])
        self.assertIn("Physical component membership controls", policy["physical_component_shape_rule"])
        self.assertIn("T01 envelope-group membership separately controls", policy["physical_component_shape_rule"])
        self.assertEqual(policy["nonround_site_selector_status"],
                         "DETERMINISTIC_SMALLEST_ELIGIBLE_NONPRIORITY_SOURCE_RADIUS_THEN_SOURCE_ID")
        self.assertIn("largest-source-radius round-priority rule", policy["owner_marked_area_correction"])

    def test_singleton_is_separate_and_round(self):
        groups, edges = local_competition_components([site("a", 0, 0.25),
                                                       site("b", 4, 0.25)], 0.02002)
        self.assertEqual([g["size"] for g in groups], [1, 1])
        self.assertEqual([g["rule"] for g in groups], ["keep_unique_round"] * 2)
        self.assertEqual(edges, [])

    def test_raw_circle_scan_counts_only_filled_fcu_occurrences_and_deduplicates_geometry(self):
        source = b'''(kicad_pcb
          (gr_circle (center 0 0) (end 0.1 0) (layer "F.Cu") (fill yes))
          (gr_circle (center 0 0) (end 0.1 0) (layer "F.Cu") (fill solid))
          (gr_circle (center 0 0) (end 0.1 0) (layer "B.Cu") (fill yes))
          (gr_circle (center 0 0) (end 0.1 0) (layer "F.Cu") (fill none)))'''
        spans, sites = _raw_filled_circle_scan(source, box(-0.2, -0.2, 0.2, 0.2), 32)
        self.assertEqual(len(spans), 2)
        self.assertEqual(sites, {(0.0, 0.0, 0.1): 2})

    def test_transitive_local_competitors_form_one_component(self):
        groups, edges = local_competition_components([site("a", 0, 0.25),
                                                       site("b", 0.30, 0.25),
                                                       site("c", 0.60, 0.25)], 0.02002)
        self.assertEqual([g["size"] for g in groups], [3])
        self.assertEqual([g["rule"] for g in groups], ["multi_circle_growth"])
        self.assertEqual(len(edges), 2)

    def test_edge_uses_each_site_hard_cap(self):
        groups, edges = local_competition_components([site("a", 0, 0.25),
                                                       site("b", 0.79, 0.25)], 0.02002)
        self.assertEqual([g["size"] for g in groups], [1, 1])
        self.assertEqual(edges, [])

    def test_physical_component_membership_does_not_replace_t01_envelope_grouping(self):
        a, b = site("a", 0.0, 0.25), site("b", 4.0, 0.25)
        a["physical_component_source_id"] = b["physical_component_source_id"] = "a" * 64
        groups, edges = local_competition_components([a, b], 0.02002)
        self.assertEqual([group["size"] for group in groups], [1, 1])
        self.assertEqual(edges, [])


class PhysicalContactGroupingTests(unittest.TestCase):
    def test_nearby_envelopes_do_not_make_distinct_physical_groups_multi_circle(self):
        components = physical_contact_components([
            physical_site("a", 0.0, "a" * 64),
            physical_site("b", 0.30, "b" * 64),
        ])
        self.assertEqual([component["size"] for component in components], [1, 1])
        self.assertTrue(all(component["rule"] == "keep_unique_round" for component in components))

    def test_same_physical_component_is_multi_circle_even_when_envelopes_do_not_compete(self):
        components = physical_contact_components([
            physical_site("a", 0.0, "a" * 64),
            physical_site("b", 4.0, "a" * 64),
        ])
        self.assertEqual([component["size"] for component in components], [2])
        self.assertEqual(components[0]["rule"], "multi_circle_growth")
        self.assertTrue(all("group_id" not in component for component in components))
        self.assertTrue(all("component_id" in component for component in components))

    def test_missing_physical_contact_binding_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "MISSING_ORG_PHYSICAL_CONTACT_GROUP"):
            physical_contact_components([site("a", 0.0, 0.25)])

    def test_component_nonround_slot_uses_smallest_nonpriority_circle_with_stable_tie_break(self):
        sites = [physical_site("large", 0.0, "a" * 64),
                 physical_site("z-small", 1.0, "a" * 64),
                 physical_site("a-small", 2.0, "a" * 64),
                 physical_site("other", 3.0, "b" * 64)]
        sites[1]["radius"] = sites[2]["radius"] = 0.05
        targets = {site["source_id"]: site["radius"] + 0.1 for site in sites}
        selected = choose_component_nonround_sites(
            sites, {"local-group": "large"}, targets, {"PC-" + "a" * 12})
        self.assertEqual(selected, {"PC-" + "a" * 12: "a-small"})


class ContainedCircleExclusionTests(unittest.TestCase):
    def circle(self, source_id, x, indexes):
        item = physical_site(source_id, x, "a" * 64)
        item["indexes"] = indexes
        item["aliases"] = indexes
        return item

    def row(self, source_id, kind):
        return {"id": source_id, "kind": kind, "geometry_sha256": source_id * 64}

    def test_circle_inside_rectangle_is_excluded_before_grouping(self):
        inner = self.circle("circle", 0, [0])
        rectangle = box(-1, -1, 1, 1)
        rows = [self.row("circle", "filled_circle"), self.row("rect", "filled_rectangle")]
        eligible, excluded, uncertain = exclude_circles_contained_by_source_shape(
            [inner], rows, [inner["core"], rectangle])
        self.assertEqual(eligible, [])
        self.assertEqual([item["source_id"] for item in
                          excluded["circle"][0]["covered_by_source_objects"]], ["rect"])
        self.assertEqual(uncertain, {})

    def test_circle_inside_arbitrary_copper_polygon_is_excluded(self):
        inner = self.circle("circle", 0, [0])
        polygon = Polygon([(-1, -1), (1, -1), (0.2, 0.1), (1, 1), (-1, 1)])
        rows = [self.row("circle", "filled_circle"), self.row("poly", "filled_polygon")]
        eligible, excluded, uncertain = exclude_circles_contained_by_source_shape(
            [inner], rows, [inner["core"], polygon])
        self.assertEqual(eligible, [])
        self.assertIn("circle", excluded)
        self.assertEqual(uncertain, {})

    def test_multiple_shapes_are_not_combined_to_infer_circle_coverage(self):
        inner = self.circle("circle", 0, [0])
        left, right = box(-1, -1, 0, 1), box(0, -1, 1, 1)
        rows = [self.row("circle", "filled_circle"),
                self.row("left", "filled_rectangle"),
                self.row("right", "filled_rectangle")]
        eligible, excluded, uncertain = exclude_circles_contained_by_source_shape(
            [inner], rows, [inner["core"], left, right])
        self.assertEqual([site["source_id"] for site in eligible], ["circle"])
        self.assertEqual(uncertain, {})
        self.assertEqual(circle_coverage_summary([inner], [inner["core"], left, right],
                                                 {}),
                         {"individually_covered_sites": 0,
                          "additional_collective_coverage_sites_inferred": 0,
                          "directly_covered_sites": 0})

    def test_partial_overlap_is_not_containment(self):
        inner = self.circle("circle", 0, [0])
        partial = box(-1, -1, 0.05, 1)
        rows = [self.row("circle", "filled_circle"), self.row("rect", "filled_rectangle")]
        eligible, excluded, uncertain = exclude_circles_contained_by_source_shape(
            [inner], rows, [inner["core"], partial])
        self.assertEqual([site["source_id"] for site in eligible], ["circle"])
        self.assertEqual(excluded, {})
        self.assertEqual(uncertain, {})

    def test_same_site_alias_is_not_treated_as_another_shape(self):
        inner = self.circle("circle", 0, [0, 1])
        rows = [self.row("circle-a", "filled_circle"), self.row("circle-b", "filled_circle")]
        eligible, excluded, uncertain = exclude_circles_contained_by_source_shape(
            [inner], rows, [inner["core"], inner["core"]])
        self.assertEqual([site["source_id"] for site in eligible], ["circle"])
        self.assertEqual(excluded, {})
        self.assertEqual(uncertain, {})

    def test_tiny_boundary_sliver_is_held_uncertain_not_called_contained(self):
        inner = self.circle("circle", 0, [0])
        almost_cover = box(-1, -1, 0.124999999999, 1)
        rows = [self.row("circle", "filled_circle"), self.row("rect", "filled_rectangle")]
        eligible, excluded, uncertain = exclude_circles_contained_by_source_shape(
            [inner], rows, [inner["core"], almost_cover])
        self.assertEqual(eligible, [])
        self.assertEqual(excluded, {})
        self.assertIn("circle", uncertain)

if __name__ == "__main__":
    unittest.main()
