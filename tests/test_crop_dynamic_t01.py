import hashlib
import unittest
from pathlib import Path

from shapely import from_wkb
from shapely import affinity
from shapely.geometry import box
import sexpdata

from src.crop_dynamic_t01 import CROP_EDGE_GUARD_MM, V_BOUNDS, run
from src.native_inventory import inventory
from src.native_reference import one


ROOT = Path(__file__).resolve().parents[1]
ORG = ROOT / "dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb"
ORG_SHA = "850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0"


class CropDynamicT01Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ORG.read_bytes()
        cls.inv = inventory(cls.source)
        cls.result = run(cls.source)

    def test_frozen_source_coverage_and_denominator(self):
        self.assertEqual(hashlib.sha256(self.source).hexdigest(), ORG_SHA)
        self.assertEqual(self.result["source_sha256"], ORG_SHA)
        self.assertEqual(self.result["supported_halo_object_count"], 267)
        self.assertEqual(self.result["unsupported_FCu_intersecting_halo"], [])
        self.assertEqual(self.result["eligible_target_count"], 39)
        self.assertEqual(self.result["kept_small_circle_count"], 7)
        self.assertEqual(self.result["halo_filled_circle_count"], 53)
        self.assertEqual(self.result["abstained_edge_guard_circle_count"], 7)
        self.assertEqual(self.result["abstained_edge_guard_large_circle_count"], 7)
        self.assertEqual(self.result["abstained_edge_guard_small_circle_count"], 0)

    def test_scene_revisions_protected_cores_and_gap(self):
        decisions = self.result["decisions"]
        for order, d in enumerate(decisions):
            self.assertEqual(d["input_scene_revision"], f"scene-{order:03d}")
            self.assertEqual(d["output_scene_revision"], f"scene-{order+1:03d}")
            self.assertLessEqual(d["protected_core_loss_mm2"], 1e-12)
            if d["accepted_area_delta_mm2"] > 1e-8:
                self.assertGreaterEqual(d["minimum_optional_growth_gap_mm"],
                                        0.02-self.result["policy"]["gap_tolerance_mm"])
            core = from_wkb(self.inv["payloads"][d["geometry_sha256"]])
            candidate = from_wkb(bytes.fromhex(d["candidate_wkb"]))
            self.assertLessEqual(core.difference(candidate).area, 1e-12)

    def test_real_crop_has_measured_dynamic_effects_against_static_baseline(self):
        events = [d for d in self.result["decisions"] if d["adapted_by_prior_acceptance"]]
        decisions = {d["source_id"]: d for d in self.result["decisions"]}
        self.assertEqual(len(events), self.result["dynamic_adaptation_event_count"])
        self.assertGreaterEqual(len(events), 3)
        self.assertEqual(len({d["source_id"] for d in events}), len(events))
        self.assertTrue(all(d["limiting_prior_source_ids"] for d in events))
        self.assertTrue(all(decisions[n]["accepted_area_delta_mm2"] > 1e-8
                            for d in events for n in d["limiting_prior_source_ids"]))
        self.assertTrue(all(d["dynamic_vs_static_symmetric_difference_mm2"] > 1e-8 for d in events))
        self.assertLess(self.result["total_growth_area_mm2"],
                        self.result["static_baseline"]["total_growth_area_mm2"])
        self.assertEqual(self.result["policy"]["EDIT_available_to_constructor"], False)

    def test_replay_is_canonical_and_revision_queries_are_current(self):
        replay = run(self.source)
        canon = lambda r: [(d["source_id"], d["candidate_wkb"], d["input_scene_revision"],
                            d["output_scene_revision"]) for d in r["decisions"]]
        self.assertEqual(canon(self.result), canon(replay))
        ids = {d["source_id"]: d["order"] for d in replay["decisions"]}
        for d in replay["decisions"]:
            self.assertTrue(all(ids[n] < d["order"] for n in d["limiting_prior_source_ids"]))

    def test_write_denominator_is_stable_under_small_frame_shifts(self):
        V = box(*V_BOUNDS)
        circles = []
        for o in self.inv["objects"]:
            if o["kind"] != "gr_circle" or "F.Cu" not in o["layers"] or not o["geometry_sha256"]:
                continue
            node = sexpdata.loads(self.source[slice(*o["source_span"])].decode("utf-8"))
            if str(one(node, "fill", ["none"])[0]) not in ("yes", "solid"):
                continue
            geom = from_wkb(self.inv["payloads"][o["geometry_sha256"]])
            diameter = ((geom.bounds[2]-geom.bounds[0])+(geom.bounds[3]-geom.bounds[1]))/2
            circles.append((geom, diameter))
        for dx, dy in ((0,0),(.001,0),(-.001,0),(0,.001),(0,-.001)):
            W = affinity.translate(V, xoff=dx, yoff=dy).buffer(-CROP_EDGE_GUARD_MM)
            inside = [(g,d) for g,d in circles if W.covers(g)]
            self.assertEqual(sum(d >= .10 for _,d in inside),39)
            self.assertEqual(sum(d < .10 for _,d in inside),7)


if __name__ == "__main__":
    unittest.main()
