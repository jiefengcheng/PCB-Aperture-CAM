import math
import unittest

from shapely import affinity, to_wkb
from shapely.geometry import box

from src.crop_rect_t02 import (
    RectGrowthPolicy,
    bind_source_dispositions,
    execute,
    limiting_constraints,
    rectangular_feature,
    validate_accepted_t01_baseline,
)


def row_for(geom, identity='source-id'):
    return ({'id':identity,'source_span':[10,30],'source_sha256':'source-hash',
             'geometry_sha256':identity+'-shape','kind':'gr_poly','layers':['F.Cu'],
             'coverage':'GEOMETRY_AVAILABLE','geometry_role':'nominal native shape'},
            {identity+'-shape':to_wkb(geom)})


class CropRectT02Tests(unittest.TestCase):
    def test_limiting_constraints_name_the_source_trace_and_prior_scene_geometry(self):
        addition = box(0, 0, 1, 1)
        result = limiting_constraints(
            addition,
            target_source_id="target",
            source_geometries={"target": box(0, 0, 0.5, 0.5), "source": box(1.03, 0, 2, 1)},
            source_metadata={"source": {"kind": "gr_poly", "source_span": [10, 20]}},
            prior_t02_additions={"prior": box(-0.06, 0, -0.03, 1)},
            trace_reservations=[{"source_id": "trace", "source_kind": "segment",
                                 "source_span": [30, 40], "org_surface_gap_mm": 0.07,
                                 "required_retained_gap_mm": 0.035}],
            trace_geometries={"trace": box(0, 1.04, 1, 2)},
            hard_gap_mm=0.02,
            construction_gap_mm=0.02002,
            tolerance_mm=0.00001,
        )

        self.assertEqual(result["nearest_original_protected_source"]["source_id"], "source")
        self.assertAlmostEqual(result["nearest_original_protected_source"]["measured_gap_mm"], 0.03)
        self.assertEqual(result["nearest_prior_t02_addition"]["source_id"], "prior")
        self.assertEqual(result["trace_reservations"][0]["source_id"], "trace")
        self.assertAlmostEqual(result["trace_reservations"][0]["measured_final_gap_mm"], 0.04)
        self.assertEqual(result["tightest_recorded_constraint"]["source_id"], "trace")
        self.assertEqual(result["tightest_recorded_constraint"]["constraint_type"],
                         "deferred_non_side_trace_interaction")

    def test_limiting_constraints_fail_closed_when_reserved_trace_is_missing(self):
        with self.assertRaisesRegex(ValueError, "T02_TRACE_RESERVATION_SOURCE_MISSING:missing"):
            limiting_constraints(
                box(0, 0, 1, 1), target_source_id="target", source_geometries={},
                source_metadata={}, prior_t02_additions={},
                trace_reservations=[{"source_id": "missing", "required_retained_gap_mm": 0.02}],
                trace_geometries={}, hard_gap_mm=0.02, construction_gap_mm=0.02002,
                tolerance_mm=0.00001,
            )

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

    def test_corner_trace_overlap_is_recorded_for_future_trace_session(self):
        row,payloads=row_for(box(0,0,1,1),'rect')
        feature=rectangular_feature(row,payloads,box(-2,-2,4,4))
        line=__import__('shapely.geometry',fromlist=['LineString']).LineString([(1.05,1.05),(1.06,1.06)])
        trace={'source_id':'trace-1','source_kind':'segment','source_span':[40,60],
               'geometry':line.buffer(.001,quad_segs=128),'trace_path_geometry':line,'width_mm':.002}
        result=execute([feature],[],box(-2,-2,4,4), side_traces=[trace])
        decision=result['decisions'][0]
        reservation=decision['trace_gap_reservations'][0]
        candidate=result['candidates_by_source']['rect']
        self.assertFalse(reservation['side_by_side_classification'])
        self.assertAlmostEqual(reservation['org_surface_gap_mm'],2**0.5*0.05-.001,places=9)
        self.assertEqual(reservation['required_retained_gap_mm'],RectGrowthPolicy().corner_contact_separation_mm)
        self.assertFalse(decision['future_trace_overlap_records'])
        self.assertTrue(any(item['trace_source_id']=='trace-1' and
                            item['status']=='OPEN_FUTURE_TRACE_SESSION' and
                            item['disposition']=='DEFERRED_TO_FUTURE_TRACE_SESSION'
                            for item in decision['future_trace_clearance_work_items']))
        self.assertEqual(decision['orientation_radians'],feature['orientation_radians'])

    def test_side_by_side_trace_uses_finite_width_surface_gap(self):
        row,payloads=row_for(box(0,0,1,1),'rect')
        feature=rectangular_feature(row,payloads,box(-2,-2,4,4))
        trace={'source_id':'trace-side','source_kind':'segment','source_span':[91,110],
               'trace_path_geometry':__import__('shapely.geometry',fromlist=['LineString']).LineString([(1.135,-1),(1.135,2)]),
               'width_mm':.01}
        trace['geometry']=trace['trace_path_geometry'].buffer(trace['width_mm']/2,quad_segs=128)
        result=execute([feature],[],box(-2,-2,4,4),side_traces=[trace])
        decision=result['decisions'][0]
        growth=result['candidates_by_source']['rect'].difference(feature['geometry'])
        reservation=decision['trace_gap_reservations'][0]
        self.assertTrue(reservation['side_by_side_classification'])
        self.assertEqual(reservation['required_surface_gap_mm'],RectGrowthPolicy().construction_gap_mm)
        self.assertGreaterEqual(growth.distance(trace['geometry']) + RectGrowthPolicy().geometry_tolerance_mm,
                                reservation['required_surface_gap_mm'])

    def test_side_by_side_copper_gap_prevents_new_trace_intersection(self):
        row,payloads=row_for(box(0,0,1,1),'rect-wide-trace')
        feature=rectangular_feature(row,payloads,box(-2,-2,4,4))
        path=__import__('shapely.geometry',fromlist=['LineString']).LineString([(1.13,-1),(1.13,2)])
        trace={'source_id':'wide-trace','source_kind':'segment','source_span':[111,130],
               'geometry':path.buffer(.05,quad_segs=128),'trace_path_geometry':path,
               'width_mm':.1,'geometry_sha256':'wide-trace-shape'}
        result=execute([feature],[],box(-2,-2,4,4),side_traces=[trace])
        decision=result['decisions'][0]
        candidate=result['candidates_by_source']['rect-wide-trace']
        self.assertLess(candidate.difference(feature['geometry']).intersection(trace['geometry']).area,1e-12)
        self.assertAlmostEqual(candidate.distance(trace['geometry']),
                               RectGrowthPolicy().construction_gap_mm,places=6)
        self.assertFalse(decision['future_trace_overlap_records'])

    def test_attached_corner_trace_overlap_is_deferred(self):
        row,payloads=row_for(box(0,0,1,1),'rect')
        feature=rectangular_feature(row,payloads,box(-2,-2,4,4))
        trace={'source_id':'trace-touch','source_kind':'segment','source_span':[70,90],
               'geometry':box(1,0.4,2,0.6)}
        result=execute([feature],[],box(-2,-2,4,4),side_traces=[trace])
        decision=result['decisions'][0]
        reservation=decision['trace_gap_reservations'][0]
        growth=result['candidates_by_source']['rect'].difference(feature['geometry'])
        self.assertEqual(reservation['org_surface_gap_mm'],0)
        self.assertEqual(reservation['required_retained_gap_mm'],0)
        self.assertTrue(decision['future_trace_overlap_records'])

    def test_policy_rejects_looser_factor_or_gap(self):
        with self.assertRaisesRegex(ValueError,'T02_FACTOR_OUT_OF_AUTHORIZED_RANGE'):
            RectGrowthPolicy(max_axis_factor=1.6).validate()
        with self.assertRaisesRegex(ValueError,'CONSTRUCTION_GAP_BELOW_HARD_GAP'):
            RectGrowthPolicy(construction_gap_mm=.01).validate()
        with self.assertRaisesRegex(ValueError,'T02_SIDE_TRACE_GAP_FRACTION_OUT_OF_RANGE'):
            RectGrowthPolicy(side_trace_gap_fraction_of_org=1.1).validate()

    def test_neighboring_round_copper_limits_axis_but_cannot_recess_rectangle(self):
        row,payloads=row_for(box(0,0,1,1),'rect')
        feature=rectangular_feature(row,payloads,box(-2,-2,4,4))
        circle=affinity.translate(affinity.scale(box(-.2,-.2,.2,.2).buffer(1,quad_segs=32),.25,.25),xoff=1.3,yoff=.5)
        result=execute([feature],[circle],box(-2,-2,4,4))
        decision=result['decisions'][0]
        candidate=result['candidates_by_source']['rect']
        self.assertTrue(decision['verification']['candidate_is_full_rectangle_without_recess'])
        self.assertEqual(len(candidate.exterior.coords),5)
        self.assertEqual(len(candidate.interiors),0)
        self.assertTrue(candidate.covers(feature['geometry']))
        self.assertGreaterEqual(candidate.difference(feature['geometry']).distance(circle) +
                                RectGrowthPolicy().geometry_tolerance_mm,
                                RectGrowthPolicy().construction_gap_mm)
        self.assertLessEqual(candidate.difference(affinity.scale(feature['geometry'],1.25,1.25,origin=(.5,.5))).area,
                             RectGrowthPolicy().area_epsilon_mm2)


if __name__=='__main__':
    unittest.main()
