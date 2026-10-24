import unittest

from shapely.geometry import LineString, Point, box

from src.crop_dynamic_t01_r1 import (
    CONSTRUCTION_BUFFER_MM,
    HARD_GAP_MM,
    MAX_GROWTH_REACH_MM,
    _port_zone,
    _priority_outline,
    grow_in_available_space,
)


class CropDynamicT01R1GeometryTests(unittest.TestCase):
    def test_same_seed_uses_more_space_when_neighbor_is_removed(self):
        core = Point(0, 0).buffer(0.10, quad_segs=64)
        obstacle = Point(0.26, 0).buffer(0.12, quad_segs=64)
        crowded = grow_in_available_space(core, [("right-neighbor", obstacle, "circle_neighbor")], reach_mm=0.02)
        open_space = grow_in_available_space(core, [], reach_mm=0.02)

        self.assertAlmostEqual(MAX_GROWTH_REACH_MM, 0.02013)
        self.assertGreater(open_space["area_delta_mm2"], crowded["area_delta_mm2"])
        self.assertGreater(open_space["candidate"].symmetric_difference(crowded["candidate"]).area, 1e-5)
        self.assertTrue(crowded["limiting_obstacles"])

    def test_smaller_roomy_site_can_finish_larger_than_larger_crowded_site(self):
        smaller = Point(0, 0).buffer(0.11, quad_segs=64)
        larger = Point(1, 0).buffer(0.12, quad_segs=64)
        roomy = grow_in_available_space(smaller, [], reach_mm=0.02)
        # The buffered annulus closes the larger site's calibrated 0.02 mm reach.
        crowded_ring = Point(1, 0).buffer(0.19, quad_segs=64).difference(
            Point(1, 0).buffer(0.15, quad_segs=64))
        crowded_obstacles = [("crowded-annular-neighbor", crowded_ring, "protected_copper")]
        crowded = grow_in_available_space(larger, crowded_obstacles, reach_mm=0.02)

        roomy_max_radius = max(Point(0, 0).distance(Point(x, y)) for x, y in roomy["candidate"].exterior.coords)
        crowded_max_radius = max(Point(1, 0).distance(Point(x, y)) for x, y in crowded["candidate"].exterior.coords)
        self.assertLess(0.11, 0.12)
        self.assertGreater(roomy_max_radius, crowded_max_radius)
        self.assertTrue(crowded["limiting_obstacles"])

    def test_priority_round_outline_is_reserved_after_core_retention(self):
        priority = Point(0, 0).buffer(0.10, quad_segs=64)
        companion = Point(0.25, 0).buffer(0.08, quad_segs=64)
        reserved_outline = _priority_outline(priority, None)
        result = grow_in_available_space(companion,
            [("priority-core", priority, "circle_neighbor")],
            priority_reservations=[("priority", reserved_outline)])
        addition = result["candidate"].difference(companion)
        self.assertTrue(result["candidate"].covers(companion))
        self.assertLessEqual(addition.intersection(reserved_outline).area, 1e-10)

        # Negative control: retaining the round core alone does not prove that
        # another land's addition left its visible perimeter uncovered.
        unreserved_companion = Point(0.17, 0).buffer(0.16, quad_segs=64)
        negative_addition = unreserved_companion.difference(companion)
        self.assertTrue(priority.difference(priority.union(negative_addition)).is_empty)
        self.assertGreater(priority.boundary.intersection(negative_addition).length, 0.01)

    def test_only_the_declared_local_own_trace_port_can_overlap(self):
        core = Point(0, 0).buffer(0.10, quad_segs=64)
        trace = LineString([(0, 0), (0.60, 0)]).buffer(0.015, quad_segs=16)
        zone = _port_zone(core, trace, 0.03)
        self.assertIsNotNone(zone)
        result = grow_in_available_space(core, [("attached-trace", trace, "trace_corridor")],
            port_zones={"attached-trace": zone})
        growth = result["candidate"].difference(core)
        self.assertGreater(growth.intersection(trace).area, 0)
        self.assertLessEqual(growth.intersection(trace.difference(zone)).area, 1e-10)

    def test_non_port_copper_keeps_at_least_the_experimental_gap(self):
        core = Point(0, 0).buffer(0.10, quad_segs=64)
        obstacle = Point(0.34, 0).buffer(0.10, quad_segs=64)
        result = grow_in_available_space(core, [("other-copper", obstacle, "protected_copper")])
        growth = result["candidate"].difference(core)
        self.assertGreaterEqual(growth.distance(obstacle), HARD_GAP_MM - 1e-5)

    def test_construction_buffer_is_not_mislabeled_as_final_gap(self):
        self.assertAlmostEqual(CONSTRUCTION_BUFFER_MM, 0.025)
        self.assertAlmostEqual(HARD_GAP_MM, 0.020)
        self.assertGreater(CONSTRUCTION_BUFFER_MM, HARD_GAP_MM)

    def test_uncalibrated_site_has_zero_growth_reach(self):
        core = Point(0, 0).buffer(0.03, quad_segs=64)
        result = grow_in_available_space(core, [], reach_mm=0.0)
        self.assertEqual(result["area_delta_mm2"], 0.0)
        self.assertTrue(result["candidate"].equals(core))


if __name__ == "__main__":
    unittest.main()
