import math
import pytest
from types import SimpleNamespace
from shapely.geometry import LineString
from src.gerber_u05.arc_group_plan import prepare
from src.stage_abi.store import canonical
from src.gerber_u05.arc_group_plan import prepare_maximal
from src.gerber_u05.arc_membership import catalogue


def test_arc_members_get_two_sided_source_budgets_before_contours_are_emitted():
    original={};rows={}
    for s,r in [('a',1.),('b',1.1)]:
        pts=[[r*math.cos(.6*i/100),r*math.sin(.6*i/100)]for i in range(101)]
        original[s]=LineString(pts).buffer(.025,quad_segs=128)
        rows[s]=dict(original_ref=dict(artifact_id='geometry:'+'a'*64,sha256='a'*64),metadata=dict(
            route_points_mm=pts,minimum_caliper_mm=.05,aperture_family=['C',.05]))
    groups=[dict(group_id='g',members=[dict(source_id=s,length_mm=1.)for s in rows])]
    cores,proof=prepare(rows,original,original,groups,set(rows),lambda s:(s,),{},
        SimpleNamespace(maximum_factor=1.5,maximum_total_width_increase_mm=.03),dict(a=.075,b=.075))
    assert set(cores)=={'a','b'} and not proof['geometry_audit']
    assert all(v['negative_growth_mm']+v['positive_growth_mm']<=.025+1e-12 for v in cores.values())
    allocation=proof['models'][0]['allocation']
    assert allocation['primal_objective_doubled_units']==allocation['dual_bound_doubled_units']
    assert canonical(proof)


def test_arc_budgets_reserve_a_neighbors_original_cap_before_it_is_restored():
    from shapely.geometry import Point,box
    from src.gerber_u05.component_workspace import ResidualScene
    original={};rows={}
    for s,r in [('a',1.),('b',1.1)]:
        points=[[r*math.cos(.6*i/100),r*math.sin(.6*i/100)]for i in range(101)]
        original[s]=LineString(points).buffer(.025,quad_segs=128)
        rows[s]=dict(original_ref={},metadata=dict(route_points_mm=points,minimum_caliper_mm=.05,aperture_family=['C',.05]))
    floor=Point(.91*math.cos(.3),.91*math.sin(.3)).buffer(.025,quad_segs=128)
    original['foreign']=floor
    working=dict(original,foreign=box(10,10,11,11))
    scene=ResidualScene(working,source_floors={'foreign':floor})
    _,proof=prepare(rows,original,scene,[dict(group_id='g',members=[dict(source_id=s,length_mm=1.)for s in rows])],
        set(rows),lambda s:(s,),{},SimpleNamespace(maximum_factor=1.5,maximum_total_width_increase_mm=.03),dict(a=.075,b=.075))
    witnesses=[r for r in proof['models'][0]['witnesses']if r.get('foreign_source')=='foreign']
    assert witnesses and min(r['maximum_growth_mm']for r in witnesses)==0.
    assert scene['foreign'].wkb==working['foreign'].wkb


def test_arc_core_inside_a_protected_pin_domain_remains_a_default_case():
    from shapely.geometry import box
    pts=[[math.cos(.6*i/100),math.sin(.6*i/100)]for i in range(101)]
    original={s:LineString(pts).buffer(.025)for s in('a','b')}
    rows={s:dict(original_ref={},metadata=dict(route_points_mm=pts,minimum_caliper_mm=.05,aperture_family=['C',.05]))for s in original}
    cores,proof=prepare(rows,original,original,[dict(group_id='g',members=[dict(source_id=s,length_mm=1.)for s in rows])],
        set(rows),lambda s:(s,),{},SimpleNamespace(maximum_factor=1.5,maximum_total_width_increase_mm=.03),dict(a=.075,b=.075),
        protected_domains=[box(.5,0.,1.5,1.)])
    assert not cores and proof['deferred']


def maximal_fixture():
    original={};rows={};arcs=[]
    for s,r,lo,hi,route in [('a',1.,0.,.4,'A'),('b',1.,.4,.9,'A'),('c',1.1,.08,.82,'B')]:
        points=[[r*math.cos(lo+(hi-lo)*i/100),r*math.sin(lo+(hi-lo)*i/100)]for i in range(101)]
        original[s]=LineString(points).buffer(.025,quad_segs=128)
        rows[s]=dict(original_ref=dict(artifact_id='geometry:'+s*64,sha256=s*64),metadata=dict(
            route_points_mm=points,minimum_caliper_mm=.05,aperture_family=['C',.05]))
        arcs.append(dict(source_id=s,route_id=route,width_mm=.05,points=points,length_mm=(hi-lo)*r))
    groups=catalogue(dict(runs=[]),dict(arcs=arcs))['curve_groups']
    return rows,original,groups


@pytest.mark.parametrize('container',[tuple,list])
def test_complete_arc_member_has_no_internal_seam_reserves_or_islands(container):
    rows,original,groups=maximal_fixture()
    cores,proof=prepare_maximal(rows,original,original,groups,set(rows),lambda s:container(['A'if s in('a','b')else'B']),{},
        SimpleNamespace(maximum_factor=1.5,maximum_total_width_increase_mm=.03),dict.fromkeys(rows,.075))
    assert set(cores)==set(rows)
    assert cores['a']['body'].wkb==cores['b']['body'].wkb
    assert cores['a']['first_mm']==0 and cores['a']['last_mm']==pytest.approx(cores['a']['member_length_mm'])
    assert cores['a']['negative_growth_mm']==cores['b']['negative_growth_mm']
    assert cores['a']['positive_growth_mm']==cores['b']['positive_growth_mm']
    assert proof['native_source_seam_reserves']==0 and not proof['geometry_audit']
    assert len(proof['models'][0]['source_members'][cores['a']['member_id']]['source_refs'])==2
    assert canonical(proof)


def test_restored_array_membership_still_rejects_changed_arc_owner():
    rows,original,groups=maximal_fixture()
    with pytest.raises(ValueError,match='MAXIMAL_ARC_SOURCE_OWNER_CHANGED'):
        prepare_maximal(rows,original,original,groups,set(rows),lambda s:[s],{},
            SimpleNamespace(maximum_factor=1.5,maximum_total_width_increase_mm=.03),dict.fromkeys(rows,.075))


def test_a_covered_occurrence_does_not_get_growth_through_a_member_alias():
    rows,original,groups=maximal_fixture()
    cores,proof=prepare_maximal(rows,original,original,groups,{'a','c'},lambda s:('A'if s in('a','b')else'B',),{},
        SimpleNamespace(maximum_factor=1.5,maximum_total_width_increase_mm=.03),dict.fromkeys(rows,.075))
    assert 'a'not in cores and 'b'not in cores
    assert proof['member_deferrals'][0]['reason'].startswith('FIXED_OR_COVERED_OCCURRENCE')


def test_complete_arc_skin_realizes_the_true_tangent_sections_it_freezes():
    from src.gerber_u05.arc_membership import tangent
    from src.native_inventory import ERROR_MM
    rows,original,groups=maximal_fixture()
    cores,_=prepare_maximal(rows,original,original,groups,set(rows),
        lambda s:('A' if s in ('a','b') else 'B',),{},
        SimpleNamespace(maximum_factor=1.5,maximum_total_width_increase_mm=.03),dict.fromkeys(rows,.075))
    members={m['member_id']:m for g in groups for m in g['members']}
    for value in cores.values():
        points=members[value['member_id']]['reference_points_mm']
        for end,center in ((False,points[0]),(True,points[-1])):
            u=tangent(points,end)*(-1 if end else 1);n=(-float(u[1]),float(u[0]))
            ends=[(center[0]+sign*n[0]*(.025+growth),center[1]+sign*n[1]*(.025+growth))
                  for sign,growth in ((-1,value['negative_growth_mm']),(1,value['positive_growth_mm']))]
            assert value['body'].buffer(ERROR_MM,quad_segs=128).covers(LineString(ends))
