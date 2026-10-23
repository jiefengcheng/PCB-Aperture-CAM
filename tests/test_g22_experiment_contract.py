import unittest

from tools.build_g22_experiment_contract import build


class G22ExperimentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract, cls.path = build()

    def test_contract_pins_family_and_keeps_package_mismatch(self):
        c = self.contract
        self.assertEqual(c["slice"], "A")
        self.assertEqual(len(c["member_keys"]), 3)
        self.assertEqual(c["sealed_package"]["status"], "MISMATCH")
        self.assertTrue(all(c["sealed_package"]["registered_board_inputs_match_manifest"].values()))
        self.assertEqual(c["owner_visual_decision"]["meaning"],
                         "SUPPORTED only for bounded crop-neighborhood visual review")

    def test_effective_geometry_coverage_includes_crossing_sources_and_retains_c_unknowns(self):
        c = self.contract
        self.assertEqual([m["effective_geometry_count"] for m in c["org_effective_geometry_coverage"]["members"]],
                         [21, 26, 30])
        self.assertEqual([m["effective_geometry_count"] for m in c["edit_effective_geometry_coverage"]["members"]],
                         [234, 218, 302])
        c_unknown = c["member_target_qualification"][2]
        self.assertEqual(c_unknown["target_composition_status"], "NOT_ESTABLISHED")
        arcs = c_unknown["unsupported_edit_occurrences_in_window_plus_halo"]
        self.assertTrue(any(row["kind"] == "arc" and row["reason"] == "DEGENERATE_ARC" for row in arcs))
        self.assertEqual(c_unknown["measurement_coverage"]["supported_union_area"], "SUPPORTED_SUBSET_ONLY")
        self.assertIn("NOT_ESTABLISHED", c_unknown["measurement_coverage"]["unsupported_effect_rule"])

    def test_context_unknowns_and_experiment_assumptions_stay_explicit(self):
        c = self.contract
        for member in c["member_target_qualification"]:
            self.assertEqual(set(member["context_unknowns"].values()), {"UNKNOWN"})
        self.assertEqual(c["safety_halo"]["classification"], "EXPERIMENT_ASSUMPTION")
        self.assertEqual(c["experiment_policy"]["classification"], "EXPERIMENT_ASSUMPTION")
        self.assertEqual(c["overall_authority"]["manufacturing"], "NOT_ESTABLISHED")

    def test_fitting_cannot_hide_incomplete_targets_or_choose_b_by_best_score(self):
        c = self.contract
        safeguards = c["objective_guardrails"]
        self.assertTrue(safeguards["no_occurrence_count_objective"])
        self.assertIn("both recorded same-center", safeguards["B_alternatives"])
        self.assertIn("no whole-target fit score", safeguards["C_incomplete_target"])
        self.assertIn("unchanged ORG", safeguards["null_model"])
        self.assertEqual(len(c["member_target_qualification"][1]["record_correspondence"]["all_edit_seed_candidates"]), 2)
        self.assertEqual(c["experiment_policy"]["candidates_max"], 64)
        self.assertIn("Every generated parameter tuple consumes", c["experiment_policy"]["budget_accounting"])
        self.assertIn("terminal-radius error", c["experiment_policy"]["selection_rule"])
        self.assertIn("Do not let union area compensate", c["experiment_policy"]["selection_rule"])
        self.assertIn("never set to zero", c["experiment_policy"]["numerical_indifference"]["comparison"])
        self.assertAlmostEqual(c["window_overlap"]["pairwise_area_mm2"]["1-2"], 0.1008, places=8)
        self.assertAlmostEqual(c["window_overlap"]["pairwise_area_mm2"]["2-3"], 0.1008, places=8)


if __name__ == "__main__":
    unittest.main()
