import unittest
from shapely.geometry import box, LineString, Point
from src.crop_stage_growth import GrowthContract, check_proposal, fit_rectangle


class ValidStageGrowthTests(unittest.TestCase):
    def neighbor(self, shape, **extra):
        return {"source_id": "neighbor", "original": shape, "geometry": shape, **extra}

    def test_corner_below_floor_is_rejected_without_component_exemption(self):
        core = box(0, 0, 1, 1)
        trace = LineString([(1.10, 1.21), (1.21, 1.10)]).buffer(.025)
        result = check_proposal(core, box(-.125, -.125, 1.125, 1.125), [self.neighbor(trace)])
        self.assertFalse(result["passed"])
        self.assertTrue(any(f["reason"] == "INTRODUCED_BELOW_FLOOR_GAP" for f in result["failures"]))

    def test_reduced_rectangle_growth_passes_with_complete_outline(self):
        core = box(0, 0, 1, 1)
        obstacle = box(1.1, -.5, 1.2, 1.5)
        candidate, factors, result = fit_rectangle(core, [self.neighbor(obstacle)], box(-1, -1, 2, 2))
        self.assertTrue(result["passed"])
        self.assertGreater(candidate.area, core.area)
        self.assertEqual(len(candidate.exterior.coords), 5)
        self.assertLess(factors[0], 1.25)
        self.assertGreaterEqual(candidate.distance(obstacle) + 1e-12, .02010)

    def test_unchanged_inherited_small_gap_passes_but_worsening_fails(self):
        core = box(0, 0, 1, 1)
        obstacle = box(1.005, 0, 1.1, 1)
        self.assertTrue(check_proposal(core, core, [self.neighbor(obstacle)])["passed"])
        result = check_proposal(core, box(0, 0, 1.001, 1), [self.neighbor(obstacle)])
        self.assertFalse(result["passed"])
        self.assertIn("WORSENED_PRE_EXISTING_GAP", [f["reason"] for f in result["failures"]])

    def test_local_original_attachment_is_preserved_without_blanket_exemption(self):
        core = box(0, 0, 1, 1)
        trace = LineString([(0.5, .5), (1.3, .5), (1.3, 1.3), (.5, 1.3)]).buffer(.025)
        n = self.neighbor(trace, trace_width_mm=.05)
        self.assertTrue(check_proposal(core, core, [n])["passed"])
        self.assertFalse(check_proposal(core, box(0, 0, 1.3, 1.3), [n])["passed"])

    def test_no_new_contact_and_no_core_removal(self):
        core = box(0, 0, 1, 1)
        n = self.neighbor(box(1.1, 0, 2, 1))
        self.assertFalse(check_proposal(core, box(0, 0, 1.1, 1), [n])["passed"])
        self.assertFalse(check_proposal(core, box(.1, .1, .9, .9), [n])["passed"])


if __name__ == "__main__":
    unittest.main()
