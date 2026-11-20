from types import SimpleNamespace
import pytest
from src.gerber_u05.group_profile import solve_band, plan, transition_guard

SETTINGS = SimpleNamespace(maximum_factor=1.5, maximum_total_width_increase_mm=.03)


def example():
    runs = [dict(run_id=r, route_id=r, source_ids=[r], start=[0., y], end=[1., y], width_mm=.05)
            for r, y in [('a', 0.), ('b', .095)]]
    return runs, dict(axis=[1., 0.], first=0., last=1., members=[0, 1])


def test_two_faces_spend_full_caps_with_a_narrow_inner_gap():
    runs, band = example()
    q = solve_band(runs, band, {'a', 'b'}, SETTINGS)
    assert q['status'] == 'CONSTRUCTED_INTERIOR' and not q['geometry_audit']
    assert all(abs(x['width_mm']-.075) < 1e-12 for x in q['lanes'])
    assert min(q['constructed_gaps_mm']) >= q['construction_clearance_mm']-1e-12
    assert q['allocation']['minimum_cut_units'] == q['allocation']['total_width_growth_units']


def test_width_change_does_not_retain_source_edge_noise_or_impose_route_band():
    runs, band = example()
    q = solve_band(runs, band, {'a'}, SETTINGS)
    a, b = q['lanes']
    assert b['face_growth_mm'] == {'left': 0., 'right': 0.}
    assert b['width_mm'] == b['source_width_mm']
    assert len(a['vertices_mm']) == 4
    assert a['source_ids'] == ['a'] and a['route_id'] == 'a'
    assert q['source_edge_policy'] == 'NEW_IDEAL_STRAIGHT_BOUNDARIES'


def test_approximate_angles_stay_residual_but_positioning_can_open_a_close_gap():
    runs, band = example();runs[1]['end'][1] += .001
    assert solve_band(runs, band, {'a', 'b'}, SETTINGS)['status'] == 'RESIDUAL'
    runs, band = example();runs[1]['start'][1] = runs[1]['end'][1] = .07
    q = solve_band(runs, band, {'a', 'b'}, SETTINGS)
    assert q['status'] == 'CONSTRUCTED_INTERIOR'
    assert q['constructed_gaps_mm'][0] >= q['construction_clearance_mm']-1e-12
    assert all(x['width_mm'] >= x['source_width_mm'] for x in q['lanes'])
    assert all(abs(x['profile_midline_shift_mm']) <= .025+1e-12 for x in q['lanes'])
    assert solve_band(runs, band, set(), SETTINGS)['reason'] == 'GROUP_POSITION_BOUNDS_INFEASIBLE'


def test_external_bounds_are_constructor_inputs_not_trial_geometry():
    runs, band = example()
    q = solve_band(runs, band, {'a', 'b'}, SETTINGS,
                   face_caps={'a': {'left': 0., 'right': 0.}, 'b': {'left': 0., 'right': .01}})
    assert q['lanes'][0]['width_mm'] == .05
    assert q['lanes'][1]['width_mm'] == pytest.approx(.06)
    assert not q['geometry_audit']


def test_plan_cannot_claim_a_complete_t04_before_hybrid_assembly():
    runs, band = example()
    q = plan(dict(runs=runs, cases={'admitted_0.05': {'bands': [band]}}), ['a'], SETTINGS)
    assert not q['publication_ready'] and not q['full_board_run']
    assert q['width_deviation']['scope'] == 'CONSECUTIVE_SEGMENTS_ONLY'
    with pytest.raises(ValueError, match='EXPLICIT_BOUNDED'):
        plan({}, [], SETTINGS)


def test_outlier_guard_is_not_a_whole_route_width_constraint():
    q = transition_guard(.03, .025)
    assert q['maximum_extra_reach_mm'] == .11
    assert not q['whole_route_width_band']


def test_real_endpoint_adjacency_keeps_full_outer_growth_beyond_a_constrained_joint():
    from src.gerber_u05.group_profile import route_join_plan
    rows = {s: dict(metadata=dict(minimum_caliper_mm=.05, route_points_mm=[[i, 0.], [i+1, 0.]]))
            for i, s in enumerate(('corridor', 'joint', 'outer'))}
    construction = dict(groups=[dict(lanes=[dict(source_ids=['corridor'], width_mm=.05)])])
    q = route_join_plan(rows, {'one_route': list(rows)}, construction, SETTINGS)
    assert q['selected_width_caps_mm'] == {'corridor': .05, 'joint': .0625, 'outer': .075}
    assert not q['whole_route_band']


def test_source_anchored_allocation_spends_both_sides_without_forcing_route_motion():
    from src.gerber_u05.route_pose import solve
    runs,band=example()
    q=solve_band(runs,band,{'a','b'},SETTINGS,source_anchored=True)
    assert q['status']=='CONSTRUCTED_INTERIOR'
    assert all(min(lane['face_growth_mm'].values())>=0 for lane in q['lanes'])
    assert q['allocation']['minimum_cut_units']==q['allocation']['total_width_growth_units']
    pose=solve(dict(groups=[q],reference_policy='SOURCE_ANCHORED'),{'a':['a'],'b':['b']})
    assert pose['passed'] and all(v['translation_mm']==[0.,0.]for v in pose['routes'].values())


def test_fixed_lane_uses_its_actual_finite_support_not_its_minimum_caliper():
    runs,band=example()
    q=solve_band(runs,band,{'a'},SETTINGS,source_anchored=True,
                 fixed_intervals={'b':[.07,.135]})
    assert q['status']=='CONSTRUCTED_INTERIOR'
    assert q['lanes'][1]['left_mm']<=.07+1e-12
    assert q['lanes'][1]['right_mm']>=.135-1e-12
    assert q['constructed_gaps_mm'][0]>=q['construction_clearance_mm']-1e-12
