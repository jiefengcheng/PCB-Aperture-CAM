from types import SimpleNamespace
from shapely.geometry import box
from src.t04_settings import T04Settings
from src.gerber_u05 import group_components as c


def fixture():
    lane=dict(mutable=True,source_ids=['s'],source_normal_mm=0.,width_mm=.06,
              source_width_mm=.05,left_mm=-.03,right_mm=.03,profile_midline_shift_mm=0.,vertices_mm=[[.2,-.03],[.8,-.03],[.8,.03],[.2,.03]])
    construction=dict(groups=[dict(axis=[1.,0.],first_mm=.2,last_mm=.8,catalogue_band_index=0,lanes=[lane])],
                      local_join_width_plan=dict(selected_width_caps_mm={'s':.075}))
    rows={'s':dict(metadata=dict(minimum_caliper_mm=.05,source_port_width_mm=.05,route_kind='segment',route_points_mm=[[0.,0.],[1.,0.]]))}
    current={'s':box(0,-.025,1,.025)}
    settings=T04Settings(1.5,10,.03,'a'*64,b'')
    return lane,construction,rows,current,settings


def test_groups_are_fixed_never_submitted_as_checked_traces(monkeypatch):
    lane,construction,rows,current,settings=fixture();seen=[]
    def verify(traces,fixed):
        seen.extend(t['id'] for t in traces)
        assert any(x['id'].startswith('group:') for x in fixed)
        return dict(passed=True,failures=[])
    monkeypatch.setattr(c,'verify_width_scene',verify)
    q=c.run(rows,current,current,{}, {'r':['s']},construction,settings,SimpleNamespace(ids={'s':('o',)}))
    assert seen and set(seen)=={'s'}
    assert q['constructed_groups_audited']==0 and q['constructed_group_bytes_preserved']
    assert q['residual']['pass_increments']==[1,1,1,1,2,2,2]
    assert not q['publication_ready']


def test_failed_residual_checks_keep_source_and_do_not_claim_acceptance(monkeypatch):
    _,construction,rows,current,settings=fixture()
    monkeypatch.setattr(c,'verify_width_scene',lambda *a:dict(passed=False,failures=[{'reason':'blocked'}]))
    q=c.run(rows,current,current,{}, {'r':['s']},construction,settings,SimpleNamespace(ids={'s':('o',)}))
    assert all(r['selected_factor']==1 for r in q['residual']['reports'])
    assert q['joints']['reports'][0]['passed'] is False


def test_merged_run_collars_bind_only_to_the_local_source_occurrence():
    lane,construction,_,_,_=fixture();lane['source_ids']=['a','b']
    rows={'a':dict(metadata=dict(route_points_mm=[[0.,0.],[.5,0.]])),
          'b':dict(metadata=dict(route_points_mm=[[.5,0.],[1.,0.]]))}
    _,collars,_=c.joints(construction,rows)
    assert [l['source_ids'] for l,g in collars]==[['a'],['b']]


def test_bulk_trim_and_connection_recovery_conflict_are_distinct(monkeypatch):
    _,construction,rows,current,settings=fixture()
    monkeypatch.setattr(c,'verify_width_scene',lambda *a:dict(passed=False,failures=[]))
    for bulk,expected in [(box(.2,.04,.8,.5),None),
                          (box(0,.04,.1,.3).union(box(.9,.04,1,.3)).union(box(0,.04,1,.06)),
                           'BULK_CONNECTION_RECOVERY_REENTERS_RESERVED_CORRIDOR')]:
        material=dict(current,bulk=bulk)
        scope=SimpleNamespace(ids={'s':('T',),'bulk':('B',)},cores={'T':current['s'],'B':bulk})
        q=c.run(rows,material,material,{'bulk':{}},{'r':['s']},construction,settings,scope)
        assert q['bulk']['changed_sources']==['bulk']
        assert q['bulk']['error']==expected
        assert q['constructed_groups_audited']==0


def test_residual_offsets_always_start_from_source_not_already_grown_joint(monkeypatch):
    _,construction,rows,current,settings=fixture();seen=[];offset=c.p.offset_part
    monkeypatch.setattr(c,'verify_width_scene',lambda *a:dict(passed=True,failures=[]))
    def build(core,width,factor,*args,**kw):
        seen.append(core.wkb)
        return offset(core,width,factor,*args,**kw)
    monkeypatch.setattr(c.p,'offset_part',build)
    c.run(rows,current,current,{}, {'r':['s']},construction,settings,SimpleNamespace(ids={'s':('o',)}))
    assert len(seen)==7 and len(set(seen))==1


def test_rejected_collar_cannot_hide_a_disconnected_group_interface(monkeypatch):
    lane,construction,rows,current,settings=fixture()
    lane.update(left_mm=.2,right_mm=.26,profile_midline_shift_mm=.23,
                vertices_mm=[[.2,.2],[.8,.2],[.8,.26],[.2,.26]])
    monkeypatch.setattr(c,'verify_width_scene',lambda *a:dict(passed=False,failures=[]))
    q=c.run(rows,current,current,{}, {'r':['s']},construction,settings,SimpleNamespace(ids={'s':('o',)}))
    assert not q['joint_connections']['reports'][0]['passed']
    assert q['constructed_groups_audited']==0


def test_local_default_profile_keeps_long_source_continuous_despite_an_end_blocker():
    from shapely import from_wkb
    _,construction,rows,current,settings=fixture()
    current=dict(current,blocker=box(.9,.04,1.1,.1))
    scope=SimpleNamespace(ids={'s':('T',),'blocker':('B',)})
    q=c.run(rows,current,current,{}, {'r':['s']},construction,settings,scope,continuous=True)
    body=from_wkb(bytes.fromhex(q['continuous_source_bodies']['s']['wkb_hex']))
    assert body.bounds[0]<=0 and body.bounds[2]>=1
    assert q['continuous_source_bodies']['s']['connected_components']==1
    assert body.intersection(box(.05,-.04,.15,.04)).area>.1*.05
    assert q['constructed_groups_audited']==0
    assert any(x.get('decision')=='DEFAULT_CASE_CONTINUOUS_PROFILE'
               for x in q['residual']['reports'][0]['attempts'])


def test_incomplete_addition_proxy_cannot_certify_the_normalized_body(monkeypatch):
    _,construction,rows,current,settings=fixture()
    monkeypatch.setattr(c,'certified_union',lambda core,extra:(core,'EXACT_FLOOR_FALLBACK'))
    q=c.run(rows,current,current,{}, {'r':['s']},construction,settings,SimpleNamespace(ids={'s':('o',)}),continuous=True)
    rejected=[a for a in q['residual']['reports'][0]['attempts']
              if a.get('decision')in ('CONTINUOUS_ACQUIRED_PROFILE','DEFAULT_CASE_CONTINUOUS_PROFILE')]
    assert rejected and not rejected[0]['passed']
    assert any(f['reason']=='NORMALIZED_ADDITION_PROXY_INCOMPLETE'for a in rejected for f in a['failures'])


def test_whole_route_reference_moves_straight_and_curve_by_the_same_vector():
    from shapely.geometry import LineString
    lane,construction,rows,current,settings=fixture()
    lane.update(left_mm=-.02,right_mm=.04,profile_midline_shift_mm=.01,
                face_growth_mm=dict(left=-.005,right=.015),
                vertices_mm=[[.2,-.02],[.8,-.02],[.8,.04],[.2,.04]])
    arc=LineString([[1.,0.],[1.2,.2]]).buffer(.025)
    current=dict(current,arc=arc)
    rows=dict(rows,arc=dict(metadata=dict(minimum_caliper_mm=.05,source_port_width_mm=.05,
                                         route_kind='arc',route_points_mm=[[1.,0.],[1.2,.2]])))
    construction['local_join_width_plan']['selected_width_caps_mm']['arc']=.075
    scope=SimpleNamespace(ids={'s':('T',),'arc':('T',)},cores={'T':current['s'].union(arc)})
    q=c.run(rows,current,current,{}, {'r':['s','arc']},construction,settings,scope,continuous=True,coherent_pose=True)
    assert q['reference_checks']['passed']
    assert q['reference_translations_by_source']['s']==q['reference_translations_by_source']['arc']
    assert q['reference_translations_by_source']['s'][1]>.0049
    assert q['constructed_groups_audited']==0


def test_source_anchored_join_has_positive_overlap_not_a_floating_butt_contact():
    from shapely.geometry import Polygon
    from src.original_copper_owners import OriginalOwners
    lane,construction,rows,current,_=fixture()
    construction['reference_policy']='SOURCE_ANCHORED'
    lane['vertices_mm']=[[.2+1e-14,-.03],[.8-1e-14,-.03],[.8-1e-14,.03],[.2+1e-14,.03]]
    strips,_,domains=c.joints(construction,rows)
    residual=current['s'].difference(domains['s'])
    assert residual.intersection(strips[0][1]).area>0
    assert len(OriginalOwners(residual.union(strips[0][1])).owners)==1


def anchored_joint_fixture(kind='arc'):
    from shapely.geometry import LineString
    _,construction,rows,current,settings=fixture()
    pts=[[1.,0.],[1.2,.02],[1.4,.08]]if kind=='arc'else[[1.,0.],[2.,0.]]
    other=LineString(pts).buffer(.025,quad_segs=128)
    rows['other']=dict(metadata=dict(minimum_caliper_mm=.05,source_port_width_mm=.05,
                                    route_kind=kind,route_points_mm=pts))
    current['other']=other
    construction.update(reference_policy='SOURCE_ANCHORED',
                        source_width_targets_mm=dict(s=.075,other=.075),full_member_catalogue={})
    construction['groups'][0]['lanes'][0].update(route_id='r',face_growth_mm=dict(left=.005,right=.005))
    construction['local_join_width_plan']['selected_width_caps_mm']['other']=.075
    scope=SimpleNamespace(ids={'s':('T',),'other':('T',)},cores={'T':current['s'].union(other)})
    return construction,rows,current,settings,scope


def test_straight_phase_is_frozen_before_arc_and_default_joints():
    construction,rows,current,settings,scope=anchored_joint_fixture()
    q=c.run(rows,current,current,{}, {'r':['s','other']},construction,settings,scope,continuous=True,coherent_pose=True)
    assert [v['phase']for v in q['phase_order']]==['STRAIGHT_GROUPS','ARC_GROUPS','DEFAULT_SEARCH_AND_VERIFY']
    assert q['frozen_straight_hashes']and q['straight_copper_preserved_through_later_phases']
    assert q['inherited_sided_ribbons']['other']['exact_frozen_sections_retained']
    assert q['frozen_endpoint_obligations']['passed']
    assert q['constructed_groups_audited']==0


def test_nongroup_straight_uses_the_verified_default_search():
    construction,rows,current,settings,scope=anchored_joint_fixture('segment')
    q=c.run(rows,current,current,{}, {'r':['s','other']},construction,settings,scope,continuous=True,coherent_pose=True)
    report=next(r for r in q['residual']['reports']if r['source_id']=='other')
    assert report['selected_factor']>1.
    assert report['attempts'][0]['decision']=='ACQUIRED_ROUTE_GROWTH'
    assert report['attempts'][0]['passed']


def test_rejected_default_joint_is_not_silently_a_narrow_keep(monkeypatch):
    construction,rows,current,settings,scope=anchored_joint_fixture()
    verify=c.verify_normalized_additions
    def reject_curve(core,actual,fixed):
        if actual.bounds[2]>1.1:return dict(passed=False,failures=[dict(reason='blocked')])
        return verify(core,actual,fixed)
    monkeypatch.setattr(c,'verify_normalized_additions',reject_curve)
    q=c.run(rows,current,current,{}, {'r':['s','other']},construction,settings,scope,continuous=True,coherent_pose=True)
    assert not q['frozen_endpoint_obligations']['passed']
    assert any(v['source_id']=='other'for v in q['frozen_endpoint_obligations']['failures'])


def test_a_blocked_short_connector_keeps_feasible_growth_instead_of_a_nominal_island():
    from shapely import from_wkb
    from shapely.geometry import LineString
    construction,rows,current,settings,scope=anchored_joint_fixture('segment')
    points=[[1.,0.],[1.06,0.]]
    rows['other']['metadata']['route_points_mm']=points
    current['other']=LineString(points).buffer(.025,quad_segs=128)
    current['blocker']=box(1.025,.075,1.045,.2)
    scope.ids['blocker']=('foreign',)
    scope.cores.update(T=current['s'].union(current['other']),foreign=current['blocker'])
    q=c.run(rows,current,current,{},dict(r=['s','other']),construction,settings,scope,continuous=True,coherent_pose=True)
    report=next(v for v in q['residual']['reports']if v['source_id']=='other')
    assert report['selected_factor']>1.
    assert any(v.get('decision')=='DEFAULT_CASE_LOCAL_CLEARANCE_PROFILE'and v['passed']for v in report['attempts'])
    body=from_wkb(bytes.fromhex(q['continuous_source_bodies']['other']['wkb_hex']))
    assert body.covers(current['other'])
    assert body.intersection(LineString([[1.035,-.1],[1.035,.1]])).length>.05
    assert body.distance(current['blocker'])>=.0401
    assert q['functional_checks']['passed']and q['constructed_groups_audited']==0
