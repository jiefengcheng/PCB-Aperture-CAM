import unittest
from shapely.geometry import box
from src.bounded_width_solver import solve_width_scales
from src.uniform_trace_width_v2 import construct_uniform_width,FAMILY
from src.trace_width_clearance import verify_width_scene
from tests.test_uniform_trace_width import fixture
from src.source_offset_width import construct_source_offset_width,FAMILY as OFFSET_FAMILY


def source_evaluator(ys,groups,*,remote=False,source_offset=False):
    parts=[f'(segment (start 0 {y}) (end 30 {y}) (width 0.1) (layer F.Cu) (net 0))' for y in ys]
    source,record,rows,blobs=fixture(parts)
    chains={str(i):dict(component_id=str(i),source_ids=[sid]) for i,sid in enumerate(record['source_ids'])}
    def evaluate(scales):
        traces=[]
        for gid,members in groups.items():
            for cid in members:
                if source_offset:
                    _,_,_,original,_,candidate=construct_source_offset_width(source,chains[cid],rows,blobs,scales[gid])
                else:_,_,original,candidate=construct_uniform_width(source,chains[cid],rows,blobs,scales[gid])
                traces.append(dict(id=cid,original=original,candidate=candidate,verified_original_width_mm=.1))
        fixed=[dict(id='remote',geometry=box(29,.11,31,.2))] if remote else []
        return verify_width_scene(traces,fixed)
    return evaluate


class BoundedWidthSolverTests(unittest.TestCase):
    def test_unconstrained_singleton_reaches_ceiling_without_combinatorial_search(self):
        r=solve_width_scales(['g'],source_evaluator([0],{'g':['0']}),geometry_family=FAMILY)
        self.assertEqual(r['selected_scales'],{'g':1.5});self.assertTrue(r['maximum_established'])
        self.assertLessEqual(r['evaluation_count'],3)

    def test_remote_obstacle_sets_full_trace_maximum(self):
        r=solve_width_scales(['g'],source_evaluator([0],{'g':['0']},remote=True),geometry_family=FAMILY)
        self.assertTrue(r['maximum_established'])
        self.assertAlmostEqual(r['selected_scales']['g'],1.3978,delta=1e-6)
        self.assertTrue(r['maximum_proofs'][0]['proved'])

    def test_parallel_traces_share_one_common_scale(self):
        r=solve_width_scales(['g'],source_evaluator([0,.17],{'g':['0','1']}),geometry_family=FAMILY)
        self.assertTrue(r['maximum_established']);self.assertAlmostEqual(r['selected_scales']['g'],1.2988,delta=1e-6)

    def test_group_order_is_stable_and_final_joint_scene_valid(self):
        evaluate=source_evaluator([0,.17],{'a':['0'],'b':['1']})
        r=solve_width_scales(['b','a'],evaluate,geometry_family=FAMILY)
        self.assertEqual(r['stable_group_order'],['a','b']);self.assertTrue(r['maximum_established'])
        self.assertTrue(evaluate(r['selected_scales'])['passed'])

    def test_insufficient_search_budget_does_not_claim_maximum(self):
        r=solve_width_scales(['g'],source_evaluator([0],{'g':['0']},remote=True),geometry_family=FAMILY,max_steps=2)
        self.assertTrue(r['passed']);self.assertFalse(r['maximum_established'])

    def test_failed_baseline_does_not_trigger_repair_or_growth(self):
        r=solve_width_scales(['g'],lambda _:dict(passed=False,failures=['deliberate invalid predecessor']),geometry_family=FAMILY)
        self.assertFalse(r['passed']);self.assertEqual(r['selected_scales'],{'g':1.});self.assertEqual(len(r['evaluations']),1)

    def test_unqualified_geometry_family_rejected(self):
        with self.assertRaisesRegex(ValueError,'NESTED_WIDTH_GEOMETRY_FAMILY_REQUIRED'):
            solve_width_scales(['g'],lambda _:dict(passed=True),geometry_family='adaptive-unknown-family')

    def test_source_offset_parallel_group_obeys_same_collective_bound(self):
        r=solve_width_scales(['g'],source_evaluator([0,.17],{'g':['0','1']},source_offset=True),geometry_family=OFFSET_FAMILY)
        self.assertTrue(r['maximum_established'])
        self.assertAlmostEqual(r['selected_scales']['g'],1.2988,delta=1e-6)

    def test_source_offset_remote_clearance_limits_complete_trace(self):
        r=solve_width_scales(['g'],source_evaluator([0],{'g':['0']},remote=True,source_offset=True),geometry_family=OFFSET_FAMILY)
        self.assertTrue(r['maximum_established'])
        self.assertAlmostEqual(r['selected_scales']['g'],1.3978,delta=1e-6)


if __name__=='__main__':unittest.main()
