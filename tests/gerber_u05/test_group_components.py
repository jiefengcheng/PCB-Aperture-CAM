from types import SimpleNamespace
import pytest
from shapely.geometry import box
from src.t04_settings import T04Settings
from src.gerber_u05 import group_components as c


def test_positive_addition_keeps_real_growth_and_bounds_source_edge_roundoff():
    import math
    from shapely.geometry import Polygon
    source=box(1.,1.,2.,2.);reference=source;proofs=[]
    # One numerical skin along the old edge and one finite, isolated addition.
    skin=box(2.,1.2,2.+2*math.ulp(2.),1.8)
    growth=box(2.1,1.2,2.2,1.8)
    actual=source.union(skin).union(growth)
    delta=c.positive_addition(actual,reference,source,source_contribution=source,roundoff_proofs=proofs)
    assert delta.equals(growth) and proofs
    assert all(p['complete_face_within_source_roundoff']for p in proofs)
    # Small area alone never excuses a face outside the original edge bound.
    tiny=box(2.1,1.2,2.1+1e-10,1.2+1e-10)
    assert c.positive_addition(source.union(tiny),reference,source,source_contribution=source).equals(tiny)
    beyond=box(2.,1.2,2.+32*math.ulp(2.),1.8)
    assert not c.positive_addition(source.union(beyond),reference,source,source_contribution=source).is_empty


def test_positive_addition_uses_trimmed_entry_and_keeps_threshold_adjacent_growth():
    from shapely.geometry import Polygon
    from src.gerber_u05.limiting_math import GUARD
    entry=box(0.,0.,1.,1.);regrown=box(1.,.2,1.01,.8)
    # Previously removed space is not an exemption for new T04 growth.
    delta=c.positive_addition(entry.union(regrown),entry,entry,source_contribution=entry)
    assert delta.equals(regrown)
    for offset,passed in ((-2e-12,False),(2e-12,True)):
        neighbor=box(1.01+GUARD+offset,.2,1.2,.8)
        assert (delta.distance(neighbor)+1e-12>=GUARD)is passed


def test_roundoff_support_includes_overlapping_original_contributions_and_reuses_preparation():
    import math
    source=box(0.,0.,1.,1.);pad=box(.9,.1,2.,.9)
    floor=source.union(pad);growth=box(.2,1.,.8,1.1)
    actual=source.union(box(.8,.2,2.+2*math.ulp(2.),.8)).union(growth)
    cache={};proofs=[]
    for _ in range(3):
        delta=c.positive_addition(actual,floor,floor,source_contribution=source,
            roundoff_cache=cache,roundoff_proofs=proofs)
        assert delta.equals(growth)
    assert len(cache)<=2 and proofs
    assert all(p['support_scope']=='IMMUTABLE_STAGE_ENTRY_CONTRIBUTIONS'for p in proofs)
    # The owner floor is the trimmed entry, never the raw pad footprint.
    trimmed=source.union(box(.9,.1,1.8,.9))
    delta=c.positive_addition(actual,trimmed,trimmed,source_contribution=source,roundoff_cache=cache)
    assert delta.intersection(box(1.81,.2,1.99,.8)).area>.1


def test_exact_roundoff_proof_covers_a_complete_face_and_cannot_bridge_a_hole():
    import math
    from shapely.geometry import Polygon
    source=box(0.,0.,1.,1.);epsilon=math.ulp(1.)
    face=Polygon([(.4,1.+epsilon),(.6,1.+2*epsilon),(.5,1.+epsilon)])
    proof=c.source_edge_roundoff(face,source,8*epsilon,{})
    assert proof and proof['method']=='EXACT_RATIONAL_SOURCE_EDGE_CAPSULE'
    holed=source.difference(box(.4,.4,.6,.6))
    bridge=Polygon([(.4,.45),(.6,.45),(.5,.6)])
    # Vertices on several different source edges do not prove the interior.
    assert c.source_edge_roundoff(bridge,holed,8*epsilon,{})is None


def test_numerical_source_support_never_excuses_a_foreign_contact():
    import math
    from shapely.geometry import Polygon
    source=box(0.,0.,1.,1.);epsilon=math.ulp(1.)
    face=box(.4,1.,.6,1.+4*epsilon);foreign=box(.4,1.+epsilon,.6,1.1)
    actual=source.union(face)
    delta=c.positive_addition(actual,source,source,source_contribution=source,
        foreign_contact=lambda p:p.intersects(foreign))
    assert not delta.is_empty and delta.distance(foreign)==0


def test_roundoff_proof_reuses_the_shared_t02_t05_boundary_structure(tmp_path):
    import math
    from src.shared_copper_context import CopperContext
    source=box(1.,1.,2.,2.);epsilon=math.ulp(2.)
    actual=source.union(box(2.,1.2,2.+2*epsilon,1.8));cache={}
    with CopperContext({'s':source},source_binding={'case':'roundoff-boundary-reuse'},
                       frame={'units':'mm'},root=tmp_path/'prepared')as context:
        for _ in range(3):
            delta=c.positive_addition(actual,source,source,source_contribution=source,
                roundoff_cache=cache,boundary_sections=context.boundary_sections)
            assert delta.is_empty
        assert context.stats['source_index_builds']==1
        assert context.stats['boundary_index_builds']==1
        assert context.stats['boundary_index_hits']>=2


@pytest.mark.parametrize('offset',[-64.125,0.,1000.25])
@pytest.mark.parametrize('angle',[0.,17.,45.])
@pytest.mark.parametrize('hole',[False,True])
def test_source_edge_proofs_generalize_across_frames_overlaps_and_holes(offset,angle,hole):
    from shapely.affinity import rotate,translate
    from shapely.ops import unary_union
    def frame(g):return translate(rotate(g,angle,origin=(0,0)),offset,-offset)
    core=box(0.,0.,1.,1.)
    if hole:core=core.difference(box(.3,.3,.7,.7))
    source=frame(core);alias=frame(box(.8,.1,1.,.9))
    entry=unary_union([source,alias]);reference=unary_union([
        source.difference(frame(box(.1,.1,.2,.2))),alias])
    grown=source.union(frame(box(.95,.2,1.1,.8)))
    delta=c.positive_addition(grown,reference,entry,source_contribution=source)
    # Existing close copper at the opposite edge must not become a false
    # growth violation. The real addition must remain finite and checked.
    neighbor=frame(box(-.2,.1,-.02,.9))
    assert delta.area>.05 and delta.distance(neighbor)>.9


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


def test_source_subtraction_reference_is_not_new_copper_at_an_inherited_close_gap():
    lane,construction,rows,current,settings=fixture()
    construction['reference_policy']='SOURCE_ANCHORED'
    construction['source_width_targets_mm']={'s':.075}
    lane['face_growth_mm']=dict(left=.005,right=.005)
    # Existing source copper is closer than the construction guard near the
    # endpoint. It must remain; only genuinely new copper needs that guard.
    current=dict(current,blocker=box(.9,.06475,1.1,.1))
    scope=SimpleNamespace(ids={'s':('T',),'blocker':('B',)},cores={'T':current['s'],'B':current['blocker']})
    q=c.run(rows,current,current,{}, {'r':['s']},construction,settings,scope,continuous=True,coherent_pose=True)
    assert q['reference_checks']['passed']and q['reference_checks']['source_subtraction_proofs']==1
    assert q['functional_checks']['source_subtraction_proofs']==0
    assert q['functional_checks']['passed']


def test_moved_reference_is_still_checked_against_foreign_copper():
    lane,construction,rows,current,settings=fixture()
    lane.update(left_mm=-.02,right_mm=.04,profile_midline_shift_mm=.01,
                face_growth_mm=dict(left=-.005,right=.015),
                vertices_mm=[[.2,-.02],[.8,-.02],[.8,.04],[.2,.04]])
    current=dict(current,blocker=box(.9,.06475,1.1,.1))
    scope=SimpleNamespace(ids={'s':('T',),'blocker':('B',)},cores={'T':current['s'],'B':current['blocker']})
    q=c.run(rows,current,current,{}, {'r':['s']},construction,settings,scope,continuous=True,coherent_pose=True)
    assert not q['reference_checks']['passed']
    assert q['reference_checks']['source_subtraction_proofs']==0
    assert any(r['reason']=='RESIDUAL_FUNCTIONAL_GAP'for r in q['reference_checks']['failures'])


def test_exact_source_difference_can_have_positive_overlay_slivers_without_adding_copper():
    from shapely.geometry import LineString
    from shapely.affinity import rotate
    x,y=1.2345,-3.4567
    source=LineString([(x,y),(x+1.1,y+.7)]).buffer(.025,quad_segs=128)
    mask=rotate(box(x+.2,y-.2,x+.6,y+.2),45,origin=(x,y))
    residual=source.difference(mask)
    # This is why a constructive subtraction proof is needed. Do not add an
    # area threshold, snap the geometry, or weaken the foreign-copper limit.
    sliver=residual.difference(source)
    assert not sliver.is_empty and 0<sliver.area<1e-12


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
