import unittest

from shapely.geometry import MultiPolygon, Polygon, box

from src.org_svg_geometry_fidelity import (
    compare_path_to_wkb,
    geometry_from_evenodd_path,
    simplified_round_trip_status,
    stored_round_trip_pass,
)
from src.visual_scene import svg_path


class OrgSvgGeometryFidelityTests(unittest.TestCase):
    def test_stored_path_round_trips_polygon_with_same_winding_hole(self):
        # SVG's default nonzero fill would incorrectly fill this hole because
        # both closed subpaths have the same winding direction.
        geometry = Polygon(
            [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)],
            [[(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)]],
        )
        path = svg_path(geometry, tolerance=None, coordinate_precision=9)
        restored = geometry_from_evenodd_path(path)
        self.assertAlmostEqual(restored.area, 12.0)
        metrics = compare_path_to_wkb(geometry, path)
        self.assertEqual(metrics["source_topology"], {"polygon_components": 1, "interior_rings": 1})
        self.assertTrue(stored_round_trip_pass(metrics, 9))

    def test_simplified_round_trip_measures_bounded_path_and_topology(self):
        geometry = MultiPolygon([box(0, 0, 1, 1), box(2, 0, 3, 1)])
        path = svg_path(geometry, tolerance=0.00005, coordinate_precision=5)
        metrics = compare_path_to_wkb(geometry, path)
        result = simplified_round_trip_status(metrics, 0.00005, 5)
        self.assertEqual(result["status"], "PASS_OBSERVED_BOUNDED")
        self.assertTrue(metrics["topology_counts_match"])
        self.assertEqual(metrics["symmetric_difference_area_mm2"], 0)

    def test_unsupported_svg_syntax_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported syntax"):
            geometry_from_evenodd_path("M0 0 C1 0 1 1 0 1Z")


if __name__ == "__main__":
    unittest.main()
