"""Mechanism tests and rejection controls; synthetic cases are not crop events."""
import math
import unittest

from shapely.geometry import Point

from src.crop_square_neighbor_experiment import (
    Settings, construct, inscribed_square, square_facing_lobe, verify_addition,
)


class SquareNeighborExperimentTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()
        self.a_core = Point(0, 0).buffer(1, quad_segs=128)
        self.a_live = Point(0, 0).buffer(1.5, quad_segs=128)
        self.b_core = Point(2.8, 0).buffer(1, quad_segs=128)

    def b(self, neighbor, square_enabled=True):
        return construct(self.b_core, (2.8, 0), 1.5,
                         [{"source_id": "A", "geometry": neighbor}],
                         earlier_neighbor_id="A", earlier_neighbor_center=(0, 0),
                         square_enabled=square_enabled)

    def test_square_changes_real_geometry_and_prior_addition_changes_decision(self):
        live = self.b(self.a_live)
        no_add = self.b(self.a_core)
        no_square = self.b(self.a_live, square_enabled=False)
        self.assertTrue(live["square_consumed"])
        self.assertEqual(live["square_side"], "-X")
        self.assertFalse(no_add["square_consumed"])
        self.assertGreater(live["candidate"].symmetric_difference(no_add["candidate"]).area, 1e-8)
        self.assertGreater(live["candidate"].symmetric_difference(no_square["candidate"]).area, 1e-8)
        self.assertLess(self.b_core.difference(live["candidate"]).area, 1e-10)
        self.assertGreaterEqual(live["candidate"].distance(self.a_live), 0.020)

    def test_square_scales_with_enlarged_envelope_and_vertices_touch_circle(self):
        for radius in (1.5, 2.0):
            square = inscribed_square((2.8, 0), radius)
            self.assertAlmostEqual(square.area, 2*radius*radius)
            for vertex in list(square.exterior.coords)[:4]:
                self.assertAlmostEqual(math.dist((2.8, 0), vertex), radius)

    def test_no_actual_conflict_means_no_square_recess(self):
        result = self.b(self.a_core)
        ordinary = self.b(self.a_core, square_enabled=False)
        self.assertFalse(result["square_consumed"])
        self.assertTrue(result["candidate"].equals(ordinary["candidate"]))

    def test_clearance_corruption_is_rejected(self):
        result = self.b(self.a_live)
        # Reintroduce the untrimmed enlarged disk: validity alone cannot pass it.
        check = verify_addition(self.b_core, result["envelope"], result["envelope"],
                                [{"source_id": "A", "geometry": self.a_live}])
        self.assertFalse(check["passed"])
        self.assertFalse(check["checks"]["hard_gap_outside_source_attachment_ports"])

    def test_source_loss_and_out_of_envelope_corruptions_are_rejected(self):
        result = self.b(self.a_live)
        damaged = result["candidate"].difference(Point(2.8, 0).buffer(.1))
        check = verify_addition(self.b_core, damaged, result["envelope"], [])
        self.assertFalse(check["checks"]["source_core_preserved"])
        out_of_scope = result["candidate"].union(Point(5, 0).buffer(.1))
        check = verify_addition(self.b_core, out_of_scope, result["envelope"], [])
        self.assertFalse(check["checks"]["inside_declared_envelope"])
        self.assertFalse(check["checks"]["all_optional_parts_attached"])

    def test_lobe_never_authorizes_source_core_removal(self):
        core = Point(0, 0).buffer(1, quad_segs=128)
        neighbor = Point(2.15, 0).buffer(1, quad_segs=128)
        # R/sqrt(2) is inside the original core here: only optional growth may go.
        result = construct(core, (0, 0), 1.2,
                           [{"source_id": "other", "geometry": neighbor}],
                           earlier_neighbor_id="other", earlier_neighbor_center=(2.15, 0))
        self.assertTrue(result["square_consumed"])
        self.assertLess(core.difference(result["candidate"]).area, 1e-10)

    def test_nonfinite_orientation_and_coincident_neighbor_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "ORIENTATION"):
            inscribed_square((0, 0), 1, orientation_degrees=float("nan"))
        with self.assertRaisesRegex(ValueError, "COINCIDENT"):
            square_facing_lobe(self.a_live, inscribed_square((0, 0), 1.5), (0, 0), (0, 0))


if __name__ == "__main__":
    unittest.main()
