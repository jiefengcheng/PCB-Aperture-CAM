import hashlib
import json
import unittest
from pathlib import Path

from src.g22_reconstruction import generate_org_candidate
from src.native_inventory import inventory
from tools.run_g22_fit import _candidate_grid, _select_with_indifference


ROOT = Path(__file__).resolve().parents[1]
ORG_PATH = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v1/raw/ORG/top.kicad_pcb"
CONTRACT_PATH = max((ROOT / "out/g22_family_reconstruction/slice_a").glob("experiment_contract_*.json"),
                    key=lambda p: p.stat().st_mtime_ns)


class G22ReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.org = ORG_PATH.read_bytes()
        cls.org_sha = hashlib.sha256(cls.org).hexdigest()
        cls.contract = json.loads(CONTRACT_PATH.read_text())
        cls.seed = cls.contract["member_target_qualification"][0]["initial_editable_seed_identity"]

    def test_circle_growth_is_applied_only_to_org_copy_and_is_deterministic(self):
        before = hashlib.sha256(self.org).hexdigest()
        candidate, receipt = generate_org_candidate(
            self.org, self.org_sha, {self.seed: {"radius_delta_mm": 0.00953, "width_delta_mm": 0.0}})
        replay, replay_receipt = generate_org_candidate(
            self.org, self.org_sha, {self.seed: {"radius_delta_mm": 0.00953, "width_delta_mm": 0.0}})
        self.assertEqual(candidate, replay)
        self.assertEqual(receipt, replay_receipt)
        self.assertEqual(hashlib.sha256(self.org).hexdigest(), before)
        self.assertNotEqual(hashlib.sha256(candidate).hexdigest(), self.org_sha)
        self.assertFalse(receipt["edit_target_used_as_operator"])
        out = inventory(candidate)
        row = next(r for r in out["objects"]
                   if r["kind"] == "gr_circle" and r["source_span"][0] == 1632220)
        raw = candidate[row["source_span"][0]:row["source_span"][1]].decode()
        self.assertIn("(end 3.07850 -11.20900)", raw)

    def test_rejects_wrong_source_revision_and_unsupported_operator(self):
        with self.assertRaisesRegex(ValueError, "ORG_SOURCE_HASH_MISMATCH"):
            generate_org_candidate(self.org, "0" * 64, {self.seed: {"radius_delta_mm": 0.01}})
        with self.assertRaisesRegex(ValueError, "UNKNOWN_EDITABLE_OCCURRENCE"):
            generate_org_candidate(self.org, self.org_sha, {"0" * 64 + ":bytes:1:2": {"width_delta_mm": 0.01}})

    def test_frozen_search_grid_is_finite_and_contains_the_null_model(self):
        candidates = _candidate_grid()
        self.assertEqual(len(candidates), 63)
        self.assertLessEqual(len(candidates), 64)
        self.assertTrue(any(c["radius_growth_mm"] == c["attached_trace_width_increase_mm"] ==
                            c["junction_blend_radius_mm"] == 0.0 for c in candidates))
        self.assertEqual({c["family"] for c in candidates},
                         {"selective_land_neck", "junction_blended", "neighbor_constrained"})

    def test_indifference_tolerance_advances_to_area_and_missing_is_not_zero(self):
        def row(key, radius, trace, area, parameter):
            return {"candidate_key": key, "candidate_index": parameter,
                    "params": {"family": "test", "radius_growth_mm": parameter,
                               "attached_trace_width_increase_mm": 0.0, "junction_blend_radius_mm": 0.0},
                    "metrics": {"terminal_radius_fit": {"all_edit_alternatives": [{"absolute_radius_error_mm": radius}]},
                                "uniquely_matched_trace_width_fit": {"minimum_absolute_error_mm": trace},
                                "symmetric_difference_area_mm2": area,
                                "union_area_error_envelope_mm2": 0.00001,
                                "boundary_hausdorff_mm": 0.001}}
        a = row("a", 0.000010, 0.000020, 0.020, 0.0)
        b = row("b", 0.000025, 0.000010, 0.010, 0.1)
        c = row("c", 0.000050, None, 0.001, 0.2)
        selected, steps, _ = _select_with_indifference([a, b, c], 0.00002, 0.00002)
        self.assertEqual(selected["candidate_key"], "b")
        self.assertEqual(steps[0]["candidate_count_after"], 2)
        self.assertEqual(steps[1]["candidate_count_after"], 2)

        unavailable = row("missing", 0.00001, None, 0.02, 0.0)
        unavailable2 = row("missing2", 0.000015, None, 0.01, 0.1)
        picked, missing_steps, _ = _select_with_indifference([unavailable, unavailable2], 0.00002, 0.00002)
        self.assertEqual(picked["candidate_key"], "missing2")
        self.assertEqual(missing_steps[1]["status"], "UNAVAILABLE")
        self.assertIn("never zero", missing_steps[1]["rule"])

    def test_indifference_tie_prefers_lower_complexity_recipe(self):
        def row(key, family, index):
            return {"candidate_key": key, "candidate_index": index,
                    "params": {"family": family, "radius_growth_mm": 0.01,
                               "attached_trace_width_increase_mm": 0.02, "junction_blend_radius_mm": 0.0},
                    "metrics": {"terminal_radius_fit": {"all_edit_alternatives": [{"absolute_radius_error_mm": 0.00001}]},
                                "uniquely_matched_trace_width_fit": {"minimum_absolute_error_mm": 0.00001},
                                "symmetric_difference_area_mm2": 0.01, "union_area_error_envelope_mm2": 0.001,
                                "boundary_hausdorff_mm": 0.001}}
        selected, _, survivors = _select_with_indifference(
            [row("blend", "junction_blended", 1), row("simple", "selective_land_neck", 2)], 0.00002, 0.00002)
        self.assertEqual(survivors, 2)
        self.assertEqual(selected["candidate_key"], "simple")


if __name__ == "__main__":
    unittest.main()
