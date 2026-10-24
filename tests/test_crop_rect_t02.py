import math
import unittest

from shapely import affinity, to_wkb
from shapely.geometry import box

from src.crop_rect_t02 import (
    RectGrowthPolicy,
    bind_source_dispositions,
    execute,
    rectangular_feature,
    validate_accepted_t01_baseline,
)


def row_for(geom, identity='source-id'):
    return ({'id':identity,'source_span':[10,30],'source_sha256':'source-hash',
             'geometry_sha256':identity+'-shape','kind':'gr_poly','layers':['F.Cu'],
             'coverage':'GEOMETRY_AVAILABLE','geometry_role':'nominal native shape'},
            {identity+'-shape':to_wkb(geom)})


class CropRectT02Tests(unittest.TestCase):
    def test_source_dispositions_preserve_inventory_classes_and_bind_target_outcomes(self):
        inventory = [
            {"source_id": "rect", "source_sha256": "src", "source_span": [1, 2],
             "source_kind": "gr_poly", "source_geometry_sha256": "shape-r",
             "geometric_class": "filled_rectangle", "disposition": "TREAT",
             "reason": "Exact four-corner source rectangle."},
            {"source_id": "poly", "source_sha256": "src", "source_span": [3, 4],
             "source_kind": "gr_poly", "source_geometry_sha256": "shape-p",
             "geometric_class": "crop_crossing_nonrectangle_polygon",
             "disposition": "KEEP_PROTECTED", "reason": "Partial crop polygon; ownership unresolved."},
        ]
        runtime = [
            {"source_id": "rect", "source_sha256": "src", "source_span": [1, 2],
             "source_kind": "gr_poly", "source_geometry_sha256": "shape-r"},
            {"source_id": "poly", "source_sha256": "src", "source_span": [3, 4],
             "source_kind": "gr_poly", "source_geometry_sha256": "shape-p"},
        ]
        decisions = [{"source_id": "rect", "decision": "GROW",
                      "source_size_mm": [1.0, 0.5],
                      "accepted_size_mm_in_source_axes": [1.2, 0.8],
                      "orientation_radians": 0.25, "added_area_mm2": 0.21,
                      "candidate_geometry_sha256": "candidate-r", "verification": {"ok": True}}]

        result = bind_source_dispositions(inventory, runtime, decisions)

        self.assertEqual([row["source_id"] for row in result], ["poly", "rect"])
        by_id = {row["source_id"]: row for row in result}
        self.assertEqual(by_id["poly"]["geometric_class"], "crop_crossing_nonrectangle_polygon")
        self.assertEqual(by_id["poly"]["disposition"], "KEEP_PROTECTED")
        self.assertNotIn("t02_result", by_id["poly"])
        self.assertEqual(by_id["rect"]["t02_result"]["decision"], "GROW")
        self.assertEqual(by_id["rect"]["t02_result"]["candidate_geometry_sha256"], "candidate-r")

    def test_source_disposition_binding_fails_closed_on_set_or_identity_drift(self):
        inventory = [{"source_id": "rect", "source_sha256": "src", "source_span": [1, 2],
                      "source_kind": "gr_poly", "source_geometry_sha256": "shape",
                      "disposition": "TREAT"}]
        runtime = [{"source_id": "rect", "source_sha256": "src", "source_span": [1, 2],
                    "source_kind": "gr_poly", "source_geometry_sha256": "shape"}]
        decision = [{"source_id": "rect", "decision": "KEEP", "source_size_mm": [1, 1],
                     "accepted_size_mm_in_source_axes": [1, 1], "orientation_radians": 0,
                     "added_area_mm2": 0, "candidate_geometry_sha256": "candidate",
                     "verification": {"ok": True}}]
        with self.assertRaisesRegex(ValueError, "T02_RUNTIME_INVENTORY_DISPOSITION_SET_MISMATCH"):
            bind_source_dispositions(inventory, runtime + [{"source_id": "other"}], decision)
        with self.assertRaisesRegex(ValueError, "T02_RUNTIME_SOURCE_BINDING_MISMATCH:source_span"):
            bind_source_dispositions(inventory, [dict(runtime[0], source_span=[1, 3])], decision)
        with self.assertRaisesRegex(ValueError, "T02_DECISION_TARGET_SET_MISMATCH"):
            bind_source_dispositions(inventory, runtime, [])

    def accepted_baseline(self):
        owner = {
            'decision_id': 'accepted', 'status': 'ACCEPTED_VISUAL_CROP',
            'source_sha256': 'source', 'report_sha256': 'report',
            'policy_sha256': 'policy', 'scene_sha256': 'scene',
        }
        profile = {
            'owner_decision_id': 'accepted',
            'claims': {'owner_review': 'ACCEPTED_VISUAL_CROP'},
            'source': {'sha256': 'source'}, 'report_sha256': 'report',
            'policy_sha256': 'policy', 'scene_sha256': 'scene',
            'selection_sha256': 'selection',
        }
        report = {'source_sha256': 'source', 'selection_sha256': 'selection',
                  'viewport_mm': [0, 0, 1, 1]}
        policy = {'source_sha256': 'source', 'viewport_mm': [0, 0, 1, 1]}
        args = dict(
            owner_decision=owner, registry_profile=profile, t01_report=report,
            t01_policy=policy, target_source_sha256='source',
            report_sha256='report', policy_sha256='policy', scene_sha256='scene',
            selection_sha256='selection',
        )
        return owner, profile, report, policy, args

    def test_t01_baseline_must_cover_the_t02_crop(self):
        _, _, _, _, args = self.accepted_baseline()
        with self.assertRaisesRegex(ValueError, 'T01_VIEWPORT_DOES_NOT_COVER_T02_CROP'):
            validate_accepted_t01_baseline(target_viewport_mm=[2, 2, 3, 3], **args)
        validate_accepted_t01_baseline(target_viewport_mm=[0.25, 0.25, 0.75, 0.75], **args)

    def test_t01_baseline_rejects_mismatched_evidence_bindings(self):
        mutations = [
            ('owner_decision', {'status': 'PENDING_OWNER_REVIEW'}, 'T01_OWNER_DECISION_NOT_ACCEPTED'),
            ('registry_profile', {'owner_decision_id': 'other'}, 'T01_PROFILE_DECISION_BINDING_MISMATCH'),
            ('owner_decision', {'source_sha256': 'other'}, 'T01_OWNER_DECISION_SOURCE_MISMATCH'),
            ('report_sha256', 'other', 'T01_REPORT_HASH_BINDING_MISMATCH'),
            ('policy_sha256', 'other', 'T01_POLICY_HASH_BINDING_MISMATCH'),
            ('scene_sha256', 'other', 'T01_SCENE_HASH_BINDING_MISMATCH'),
            ('selection_sha256', 'other', 'T01_SELECTION_HASH_BINDING_MISMATCH'),
        ]
        for key, value, expected in mutations:
            with self.subTest(key=key, expected=expected):
                owner, profile, report, policy, base_args = self.accepted_baseline()
                args = dict(base_args)
                if key in ('owner_decision', 'registry_profile'):
                    target = owner if key == 'owner_decision' else profile
                    target.update(value)
                else:
                    args[key] = value
                with self.assertRaisesRegex(ValueError, expected):
                    validate_accepted_t01_baseline(target_viewport_mm=[0.1,0.1,0.9,0.9], **args)

    def test_t01_viewport_metadata_must_match_policy(self):
        _, _, _, _, args = self.accepted_baseline()
        args['t01_report'] = dict(args['t01_report'], viewport_mm=[0,0,0.9,1])
        with self.assertRaisesRegex(ValueError, 'T01_REPORT_POLICY_VIEWPORT_MISMATCH'):
            validate_accepted_t01_baseline(target_viewport_mm=[0.1,0.1,0.9,0.9], **args)

    def test_rectangular_feature_keeps_rotated_local_orientation(self):
        source=affinity.rotate(box(-1,-.5,1,.5),31,origin=(0,0))
        row,payloads=row_for(source)
        target=rectangular_feature(row,payloads,box(-5,-5,5,5))
        self.assertIsNotNone(target)
        self.assertEqual(sorted(target['source_size_mm']),[1,2])
        # Rectangle orientation is an undirected axis, modulo 90 degrees.
        delta=(target['orientation_radians']-math.radians(31))%(math.pi/2)
        self.assertLess(min(delta,math.pi/2-delta),1e-12)

    def test_rectangle_is_withheld_when_its_full_cap_crosses_review_crop(self):
        row,payloads=row_for(box(.2,.5,1.2,1.5))
        crop=box(0,0,4,4)
        self.assertIsNone(rectangular_feature(row,payloads,crop))
        self.assertIsNotNone(rectangular_feature(row,payloads,crop,enforce_full_cap_in_crop=False))

    def test_rectangle_remains_eligible_when_full_cap_fits_review_crop(self):
        row,payloads=row_for(box(1,1,2,2))
        self.assertIsNotNone(rectangular_feature(row,payloads,box(0,0,3,3)))

    def test_rejects_nonrectangular_and_wrong_layer_sources(self):
        row,payloads=row_for(box(0,0,2,1).buffer(.1))
        self.assertIsNone(rectangular_feature(row,payloads,box(-5,-5,5,5)))
        row,payloads=row_for(box(0,0,2,1));row['layers']=['B.Cu']
        self.assertIsNone(rectangular_feature(row,payloads,box(-5,-5,5,5)))

    def test_scene_preserves_cores_and_updates_revisions(self):
        row1,p1=row_for(box(0,0,1,1),'one')
        row2,p2=row_for(box(1.25,0,2.25,1),'two')
        crop=box(-2,-2,5,4)
        a=rectangular_feature(row1,p1,crop)|{'geometry':box(0,0,1,1),'center_mm':[.5,.5]}
        b=rectangular_feature(row2,p2,crop)|{'geometry':box(1.25,0,2.25,1),'center_mm':[1.75,.5]}
        result=execute([a,b],[],crop)
        self.assertTrue(all(all(d['verification'].values()) for d in result['decisions']))
        self.assertTrue(all(d['output_scene_revision']>=d['input_scene_revision'] for d in result['decisions']))
        for f in (a,b):
            self.assertLess(f['geometry'].difference(result['candidates_by_source'][f['source_id']]).area,1e-10)

    def test_exhausted_optional_growth_is_a_source_preserving_keep(self):
        row,payloads=row_for(box(0,0,1,1),'fully-blocked')
        feature=rectangular_feature(row,payloads,box(-2,-2,4,4))
        crop=box(-2,-2,4,4)
        # Every optional part of the maximum envelope is blocked by already
        # protected copper; the correct result is KEEP, with the source intact.
        blocker=crop.difference(feature['geometry'])
        result=execute([feature],[blocker],crop)
        decision=result['decisions'][0]
        self.assertEqual(decision['decision'],'KEEP')
        self.assertTrue(result['candidates_by_source']['fully-blocked'].equals_exact(feature['geometry'],0))
        self.assertLessEqual(decision['added_area_mm2'],RectGrowthPolicy().area_epsilon_mm2)
        self.assertTrue(all(decision['verification'].values()))

    def test_side_trace_reserves_half_of_its_original_gap(self):
        row,payloads=row_for(box(0,0,1,1),'rect')
        feature=rectangular_feature(row,payloads,box(-2,-2,4,4))
        trace={'source_id':'trace-1','source_kind':'segment','source_span':[40,60],
               'geometry':box(1.2,-1,1.21,2)}
        result=execute([feature],[trace['geometry']],box(-2,-2,4,4),side_traces=[trace])
        decision=result['decisions'][0]
        reservation=decision['trace_gap_reservations'][0]
        candidate=result['candidates_by_source']['rect']
        self.assertAlmostEqual(reservation['org_surface_gap_mm'],0.2,places=9)
        self.assertAlmostEqual(reservation['required_retained_gap_mm'],0.1,places=9)
        self.assertAlmostEqual(candidate.difference(feature['geometry']).distance(trace['geometry']),0.1,places=7)
        self.assertTrue(decision['verification']['half_org_side_trace_gap_preserved'])
        self.assertEqual(decision['orientation_radians'],feature['orientation_radians'])
        self.assertEqual(sorted(decision['accepted_size_mm_in_source_axes']),[1.35,1.5])

    def test_attached_trace_uses_construction_floor_for_future_growth(self):
        row,payloads=row_for(box(0,0,1,1),'rect')
        feature=rectangular_feature(row,payloads,box(-2,-2,4,4))
        trace={'source_id':'trace-touch','source_kind':'segment','source_span':[70,90],
               'geometry':box(1,0.4,2,0.6)}
        result=execute([feature],[trace['geometry']],box(-2,-2,4,4),side_traces=[trace])
        decision=result['decisions'][0]
        reservation=decision['trace_gap_reservations'][0]
        growth=result['candidates_by_source']['rect'].difference(feature['geometry'])
        self.assertEqual(reservation['org_surface_gap_mm'],0)
        self.assertEqual(reservation['required_retained_gap_mm'],RectGrowthPolicy().construction_gap_mm)
        self.assertGreaterEqual(growth.distance(trace['geometry']) + RectGrowthPolicy().geometry_tolerance_mm,
                                reservation['required_retained_gap_mm'])

    def test_policy_rejects_looser_factor_or_gap(self):
        with self.assertRaisesRegex(ValueError,'T02_FACTOR_MUST_BE_1_5'):
            RectGrowthPolicy(max_axis_factor=1.6).validate()
        with self.assertRaisesRegex(ValueError,'CONSTRUCTION_GAP_BELOW_HARD_GAP'):
            RectGrowthPolicy(construction_gap_mm=.01).validate()
        with self.assertRaisesRegex(ValueError,'T02_SIDE_TRACE_GAP_FRACTION_MUST_BE_ONE_HALF'):
            RectGrowthPolicy(side_trace_gap_fraction_of_org=.4).validate()


if __name__=='__main__':
    unittest.main()
