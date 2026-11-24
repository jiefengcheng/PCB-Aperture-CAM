from src.gerber_u05.continuous_profile import source_profiles


def test_two_group_intervals_do_not_split_a_long_source_segment():
    rows={'s':dict(metadata=dict(route_kind='segment',minimum_caliper_mm=.05,route_points_mm=[[0.,0.],[2.,0.]]))}
    groups=[dict(axis=[1.,0.],first_mm=a,last_mm=b,catalogue_band_index=i,
                 lanes=[dict(mutable=True,source_ids=['s'],source_normal_mm=0.,source_width_mm=.05,width_mm=.075,profile_midline_shift_mm=0.)])
            for i,(a,b)in enumerate(((.2,.6),(.9,1.5)))]
    q=source_profiles(rows,{'route':['s']},{'groups':groups});s=q['segments']['s']
    assert s['length_mm']==2. and s['body_count']==1
    assert len(s['constraints'])==2 and not s['source_segment_split']
    assert s['profile_stations_mm']==[0.,.2,.6,.9,1.5,2.]
    assert not q['geometry_emitted']


def test_other_route_segments_inherit_growth_without_becoming_globally_capped():
    rows={s:dict(metadata=dict(route_kind=kind,minimum_caliper_mm=.05,route_points_mm=pts))
          for s,kind,pts in [('group','segment',[[0.,0.],[1.,0.]]),
                             ('remaining','arc',[[1.,0.],[1.5,.5],[2.,0.]])]}
    c={'groups':[dict(axis=[1.,0.],first_mm=0.,last_mm=1.,catalogue_band_index=0,
                     lanes=[dict(mutable=True,source_ids=['group'],source_normal_mm=0.,
                                 source_width_mm=.05,width_mm=.06,profile_midline_shift_mm=0.)])]}
    q=source_profiles(rows,{'r':['group','remaining']},c)
    assert q['segments']['remaining']['inherited_width_mm']==.06
    assert not q['segments']['remaining']['inheritance_is_ceiling']
    assert q['segments']['remaining']['body_count']==1
    assert q['segments']['remaining']['decision_basis']=='INHERIT_ROUTE_GROWTH'
    assert q['segments']['group']['decision_basis']=='OWN_PARALLEL_GROUP'
    c['default_case_decisions']={'remaining':{'width_mm':.055,'reason':'DEFAULT_CASE_SOLVER'}}
    q=source_profiles(rows,{'r':['group','remaining']},c)
    assert q['segments']['remaining']['decision_basis']=='DEFAULT_CASE'


def test_full_straight_profile_carries_growth_to_real_ends_and_handles_reversed_source():
    from src.gerber_u05.continuous_profile import straight_body
    from shapely.geometry import LineString
    import pytest
    rows={'s':dict(metadata=dict(route_kind='segment',minimum_caliper_mm=.05,route_points_mm=[[2.,0.],[0.,0.]]))}
    construction={'groups':[dict(axis=[1.,0.],first_mm=.5,last_mm=1.,catalogue_band_index=0,
                   lanes=[dict(mutable=True,source_ids=['s'],source_normal_mm=0.,source_width_mm=.05,
                               width_mm=.075,profile_midline_shift_mm=.01)])]}
    q=source_profiles(rows,{'r':['s']},construction)['segments']['s']
    body=straight_body(q,.05)
    assert body.bounds[0]==0 and body.bounds[2]==2
    assert body.intersection(LineString([[.25,-.1],[.25,.1]])).length==pytest.approx(.075)
    assert body.intersection(LineString([[.001,-.1],[.001,.1]])).length==pytest.approx(.075)
    section=body.intersection(LineString([[.75,-.1],[.75,.1]]))
    assert section.centroid.y==pytest.approx(.01)


def test_free_span_uses_all_its_length_and_keeps_tangents_at_group_boundaries():
    from src.gerber_u05.continuous_profile import straight_fields
    record=dict(axis=[1.,0.],length_mm=2.,inherited_width_mm=.06,constraints=[
        dict(first_mm=.5,last_mm=1.,width_mm=.075,profile_midline_shift_mm=.01)])
    q=straight_fields(record,.05)
    assert q['passed'] and len(q['pieces'])==3
    assert q['pieces'][0]['length_mm']==.5 and q['pieces'][-1]['length_mm']==1.
    for a,b in zip(q['pieces'],q['pieces'][1:]):
        assert [c[-1]for c in a['controls']]==[c[0]for c in b['controls']]
        assert a['endpoint_derivatives']==b['endpoint_derivatives']==[0.,0.]
    assert not q['external_corridor_certified']


def test_conflicting_overlap_cannot_create_short_widening_islands():
    from src.gerber_u05.continuous_profile import straight_fields,straight_body,ProfileUnresolved
    import pytest
    record=dict(axis=[1.,0.],start_mm=[0.,0.],length_mm=2.,inherited_width_mm=.06,constraints=[
        dict(first_mm=.5,last_mm=1.,width_mm=.075,profile_midline_shift_mm=.01),
        dict(first_mm=.8,last_mm=1.3,width_mm=.06,profile_midline_shift_mm=0.)])
    assert not straight_fields(record,.05)['passed']
    with pytest.raises(ProfileUnresolved):straight_body(record,.05)


def test_native_source_seam_does_not_restart_the_maximal_member_taper():
    from src.gerber_u05.continuous_profile import straight_fields
    from src.gerber_u05.smooth_transition import value
    import pytest
    rows={s:dict(metadata=dict(route_kind='segment',minimum_caliper_mm=.05,route_points_mm=pts))
          for s,pts in [('a',[[0.,0.],[1.,0.]]),('b',[[2.,0.],[1.,0.]])]}
    construction=dict(groups=[dict(axis=[1.,0.],first_mm=.2,last_mm=.6,catalogue_band_index=0,
        lanes=[dict(mutable=True,source_ids=['a'],source_normal_mm=0.,source_width_mm=.05,
                    width_mm=.075,profile_midline_shift_mm=.01)])],
        full_member_catalogue=dict(maximal_straight_members=[dict(run_id='whole',source_ids=['a','b'],start=[0.,0.],end=[2.,0.])]))
    profiles=source_profiles(rows,{'r':['a','b']},construction)['segments']
    a,b=(straight_fields(profiles[s],.05)for s in('a','b'))
    assert a['passed'] and b['passed']
    assert not a['source_seam_restarts_transition']
    # b's native direction is reversed. At x=1 the two physical side fields
    # and their tangents agree; neither is forced back to zero side shift.
    pa,pb=a['pieces'][-1],b['pieces'][-1]
    upper=pa['controls'][1][-1];reversed_lower=pb['controls'][0][-1]
    assert upper==pytest.approx(-reversed_lower)
    assert upper>.075/2
    assert (pa['controls'][1][-1]-pa['controls'][1][-2])/pa['length_mm']==pytest.approx(
        (pb['controls'][0][-1]-pb['controls'][0][-2])/pb['length_mm'])


def test_minimum_reference_does_not_inherit_optional_shared_member_growth():
    from src.gerber_u05.continuous_profile import reference_profile,straight_body
    from shapely.geometry import box
    q=dict(axis=[1.,0.],length_mm=2.,constraints=[dict(first_mm=.2,last_mm=1.8,width_mm=.075,profile_midline_shift_mm=.01)],inherited_width_mm=.075)
    source=dict(q,start_mm=[0.,0.],length_mm=1.,member_context=q,
                member_source_start_mm=0.,member_source_direction=1,maximal_member_id='whole')
    minimum=reference_profile(source,.05,zero_side_shift=True)
    assert straight_body(minimum,.05).equals(box(0.,-.025,1.,.025))
    assert q['inherited_width_mm']==.075 and q['constraints'][0]['profile_midline_shift_mm']==.01


def test_joint_widths_agree_across_line_arc_and_reversed_native_directions():
    from src.gerber_u05.continuous_profile import joint_widths
    rows={s:dict(metadata=dict(route_kind=kind,minimum_caliper_mm=.05,route_points_mm=pts))
          for s,kind,pts in [('a','segment',[[0.,0.],[1.,0.]]),
                              ('b','arc',[[2.,.2],[1.5,.1],[1.,0.]])]}
    p=source_profiles(rows,{'r':['a','b']},{'groups':[]})
    joint_widths(p,rows,{'a':.075,'b':.06})
    assert p['segments']['a']['endpoint_widths_mm'][1]==p['segments']['b']['endpoint_widths_mm'][1]==.06
    assert p['segments']['a']['inherited_width_mm']==.075


def side_join_fixture(*,reversed=False,conflicting=False,short=False):
    from src.gerber_u05.continuous_profile import joint_widths
    length=.01 if short else 1.
    rows={s:dict(metadata=dict(route_kind='segment',minimum_caliper_mm=.05,route_points_mm=pts))
          for s,pts in [('a',[[0.,0.],[1.,0.]]),('b',[[1.+length,0.],[1.,0.]]if reversed else[[1.,0.],[1.+length,0.]])]}
    groups=[dict(axis=[1.,0.],first_mm=0.,last_mm=1.,catalogue_band_index=0,
        lanes=[dict(mutable=True,source_ids=['a'],source_normal_mm=0.,source_width_mm=.05,width_mm=.075,profile_midline_shift_mm=.01)])]
    if conflicting:groups.append(dict(axis=[1.,0.],first_mm=1.,last_mm=2.,catalogue_band_index=1,
        lanes=[dict(mutable=True,source_ids=['b'],source_normal_mm=0.,source_width_mm=.05,width_mm=.065,profile_midline_shift_mm=0.)]))
    profiles=source_profiles(rows,{'r':['a','b']},dict(groups=groups))
    joint_widths(profiles,rows,dict(a=.075,b=.06))
    profiles['segments']['a']['inherit_sided_endpoints']=True
    return rows,profiles


def test_shared_physical_sides_remove_asymmetric_step_without_geometry_search():
    from src.gerber_u05.continuous_profile import joint_side_fields,straight_fields,straight_body
    from shapely.geometry import LineString
    import pytest
    rows,profiles=side_join_fixture()
    a,b=(profiles['segments'][s]for s in('a','b'))
    old_a,old_b=(straight_fields(q,.05)for q in(a,b))
    assert old_a['pieces'][-1]['controls'][1][-1]!=old_b['pieces'][0]['controls'][1][0]
    proof=joint_side_fields(profiles,rows)
    assert len(proof['resolved'])==1 and not proof['unresolved']and proof['geometry_searches']==0
    new_a,new_b=(straight_fields(q,.05)for q in(a,b))
    for side in(0,1):
        assert new_a['pieces'][-1]['controls'][side][-1]==pytest.approx(new_b['pieces'][0]['controls'][side][0])
        assert new_a['pieces'][-1]['endpoint_derivatives'][side]==new_b['pieces'][0]['endpoint_derivatives'][side]==0
    line=LineString([[1.,-.2],[1.,.2]])
    assert straight_body(a,.05).intersection(line).normalize().equals_exact(straight_body(b,.05).intersection(line).normalize(),1e-12)


def test_shared_physical_sides_respect_reversed_native_direction():
    from src.gerber_u05.continuous_profile import joint_side_fields,straight_fields
    import pytest
    rows,profiles=side_join_fixture(reversed=True);joint_side_fields(profiles,rows)
    a,b=(straight_fields(profiles['segments'][s],.05)for s in('a','b'))
    assert a['pieces'][-1]['controls'][1][-1]==pytest.approx(-b['pieces'][-1]['controls'][0][-1])
    assert a['passed']and b['passed']


def test_incompatible_frozen_sides_remain_unresolved_and_are_never_averaged():
    from src.gerber_u05.continuous_profile import joint_side_fields
    rows,profiles=side_join_fixture(conflicting=True);proof=joint_side_fields(profiles,rows)
    assert proof['unresolved'][0]['reason']=='FROZEN_GROUP_SIDES_DISAGREE'
    assert not proof['resolved']and all('endpoint_sides_mm'not in q for q in profiles['segments'].values())


def test_too_short_shared_transition_remains_rejected_by_existing_slope_bound():
    from src.gerber_u05.continuous_profile import joint_side_fields,straight_fields,straight_body,ProfileUnresolved
    import pytest
    rows,profiles=side_join_fixture(short=True);joint_side_fields(profiles,rows)
    b=profiles['segments']['b'];assert not straight_fields(b,.05)['passed']
    with pytest.raises(ProfileUnresolved):straight_body(b,.05)


def test_covered_continuation_remains_in_endpoint_plan_without_growing_it():
    from src.gerber_u05.continuous_profile import joint_widths,fixed_continuation_sections,straight_fields
    from src.gerber_u05.ribbon_profile import build
    import pytest
    rows={s:dict(metadata=dict(route_kind=kind,minimum_caliper_mm=.05,route_points_mm=points))
          for s,kind,points in [('covered','segment',[[0.,0.],[1.,0.]]),
                                ('arc','arc',[[1.,0.],[1.5,.1],[2.,.5]])]}
    profiles=source_profiles(rows,{'r':['arc']},dict(groups=[]));joint_widths(profiles,rows,dict(arc=.075))
    ends=fixed_continuation_sections(profiles,rows,{'r':['covered','arc']})
    assert set(ends)=={'arc'}and ends['arc'][0]is not None and ends['arc'][1]is None
    _,recipe=build(rows['arc']['metadata']['route_points_mm'],.05,.075,ends=ends['arc'])
    assert recipe['endpoint_faces_mm'][0]==pytest.approx([0.,0.])
    assert recipe['side_field_proofs'][0]['endpoint_derivatives']==[0.,0.]
    assert profiles['fixed_continuation_joints']['records'][0]['fixed_continuation_source_ids']==['covered']
    assert 'covered'not in profiles['segments']


def test_fixed_continuation_caps_true_member_end_without_restarting_internal_seams():
    from src.gerber_u05.continuous_profile import joint_widths,fixed_continuation_sections,straight_fields
    rows={s:dict(metadata=dict(route_kind='segment',minimum_caliper_mm=.05,route_points_mm=points))
          for s,points in [('fixed',[[0.,0.],[1.,0.]]),('a',[[1.,0.],[2.,0.]]),('b',[[3.,0.],[2.,0.]])]}
    construction=dict(groups=[],full_member_catalogue=dict(maximal_straight_members=[dict(run_id='m',source_ids=['a','b'],start=[1.,0.],end=[3.,0.])]))
    profiles=source_profiles(rows,{'r':['a','b']},construction);joint_widths(profiles,rows,dict(a=.075,b=.075))
    fixed_continuation_sections(profiles,rows,{'r':['fixed','a','b']})
    a,b=(straight_fields(profiles['segments'][s],.05)for s in('a','b'))
    assert a['pieces'][0]['controls'][0][0]==-.025
    assert a['pieces'][-1]['controls'][1][-1]==-b['pieces'][-1]['controls'][0][-1]
    assert not a['source_seam_restarts_transition']and a['passed']and b['passed']
