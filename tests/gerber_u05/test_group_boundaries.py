from shapely.geometry import box
from types import SimpleNamespace
from src.gerber_u05.group_boundaries import SourceBoundaries
from src.gerber_u05.group_profile import solve_band


def test_finite_fixed_support_from_geos_coordinates_reaches_integer_allocator():
    runs,band=example()
    current={'a':box(0.,-.025,1.,.025),'b':box(0.,.07,1.,.135)}
    framing=SourceBoundaries(current,{},mutable_sources={'a'}).for_band(runs,band,SETTINGS)
    q=solve_band(runs,band,{'a'},SETTINGS,source_anchored=True,
                 fixed_intervals=framing['fixed_lane_intervals_mm'])
    assert q['status']=='CONSTRUCTED_INTERIOR'
    assert q['constructed_gaps_mm'][0]>=q['construction_clearance_mm']-1e-12


def test_pin_domains_are_deferred_before_constructing_any_strip_inside_them():
    from src.gerber_u05.group_profile import plan
    runs,band=example()
    current={'a':box(0.,-.025,1.,.025),'b':box(0.,.07,1.,.12)}
    boundary=SourceBoundaries(current,{},mutable_sources={'a','b'},
                              protected_domains=[('pin',box(.3,-.05,.7,.16))])
    q=plan(dict(runs=runs,cases={'admitted_0.05':dict(bands=[band])}),['a','b'],SETTINGS,
           boundaries=boundary,source_anchored=True)
    assert q['groups']
    assert all(g['last_mm']<.3 or g['first_mm']>.7 for g in q['groups'])
    assert any(r['reason']=='JUNCTION_WINDOWS'for r in q['residual_groups'])

SETTINGS = SimpleNamespace(maximum_factor=1.5, maximum_total_width_increase_mm=.03)


def example():
    return ([dict(run_id=r, route_id=r, source_ids=[r], start=[0., y], end=[1., y], width_mm=.05)
             for r, y in [('a', 0.), ('b', .095)]],
            dict(axis=[1., 0.], first=0., last=1., members=[0, 1]))


def test_outside_source_becomes_a_numeric_face_constraint():
    runs, band = example()
    boundaries = SourceBoundaries({'foreign': box(0., .16, 1., .18)}, {})
    framing = boundaries.for_band(runs, band, SETTINGS)
    assert not framing['unresolved'] and framing['complete_source_bounds']
    assert framing['face_caps']['b']['right'] < 0
    q = solve_band(runs, band, {'a', 'b'}, SETTINGS, face_caps=framing['face_caps'])
    assert q['status'] == 'CONSTRUCTED_INTERIOR'
    assert .16-q['lanes'][1]['right_mm'] >= q['construction_clearance_mm']-1e-12
    assert boundaries.queries == 1


def test_anchored_planning_reserves_source_copper_without_hypothetical_future_growth():
    runs,band=example();current={'other':box(0.,.18,1.,.20)}
    old=SourceBoundaries(current,{},mutable_sources={'other'}).for_band(runs,band,SETTINGS)
    anchored=SourceBoundaries(current,{},mutable_sources={'other'},reserve_mutable_growth=False).for_band(runs,band,SETTINGS)
    assert old['face_caps']['b']['right']<0<anchored['face_caps']['b']['right']
    assert anchored['witnesses'][0]['other_mutable_reservation_mm']==0


def test_close_source_defers_only_its_joint_window_for_anchored_members():
    from src.gerber_u05.group_boundaries import interior_intervals
    runs,band=example()
    framing=SourceBoundaries({'terminal':box(.01,.15,.1,.2)}, {},defer_close_sources=True).for_band(runs,band,SETTINGS)
    unresolved=[v for v in framing['unresolved']if v['run_id']=='b']
    free,_=interior_intervals(0,1,unresolved)
    assert unresolved and free[0][0]<.2 and free[-1][1]==1


def test_unmodelled_junction_cannot_be_silently_declared_constructed():
    runs, band = example()
    q = SourceBoundaries({'terminal': box(.2, -.01, .3, .01)}, {}).for_band(runs, band, SETTINGS)
    assert q['unresolved'] and q['unresolved'][0]['source_id'] == 'terminal'


def test_editable_bulk_is_recorded_but_never_sets_the_width_cap():
    runs, band = example()
    q = SourceBoundaries({'bulk': box(.2, -.01, .3, .01)}, {'bulk': {}}).for_band(runs, band, SETTINGS)
    assert not q['unresolved'] and not q['witnesses']
    assert q['editable_bulk_source_ids'] == ['bulk']


def test_junction_partition_retains_the_unaffected_middle_of_the_same_group():
    from src.gerber_u05.group_boundaries import interior_intervals
    free, cuts = interior_intervals(0., 1., [dict(longitudinal_interval_mm=[-.1, .1]),
                                           dict(longitudinal_interval_mm=[.9, 1.1])])
    assert free == [[.15000000000000002, .85]]
    assert cuts == [[0., .15000000000000002], [.85, 1.]]


def test_source_chord_support_avoids_the_whole_object_diagonal_box():
    from src.gerber_u05.group_boundaries import chord_bounds
    # A diagonal segment's box contains y=0 at x=.9; its actual chord does not.
    q = chord_bounds([[0., 0.], [1., 1.]], .05, [1., 0.], .9, 1.)
    assert q[0] > .8 and q[1] > 1.


def test_repeated_allocation_reuses_source_framing_but_retains_other_mutable_reach():
    runs, band = example()
    boundaries = SourceBoundaries({'moving_other_group': box(0., .245, 1., .26)}, {},
                                  mutable_sources={'moving_other_group'})
    q = boundaries.for_band(runs, band, SETTINGS)
    assert q['witnesses'][0]['other_mutable_reservation_mm'] == .055
    assert boundaries.for_band(runs, band, SETTINGS) is q
    assert boundaries.queries == 1
