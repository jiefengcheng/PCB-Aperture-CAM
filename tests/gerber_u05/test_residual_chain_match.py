from itertools import product
import numpy as np
import pytest
from shapely import to_wkb
from shapely.geometry import box,LineString
from src.gerber_u05.endpoint_budget import allocate,vertices
from src.gerber_u05.residual_chain_match import chains,run
from src.gerber_u05.corner_transition import describe


def section(x,width):return dict(normal=[0.,1.],lower_mm=[x,-width/2],upper_mm=[x,width/2])


@pytest.mark.parametrize('cap,intervals,allowance',[
    ([3,3,3,3],[(5,6),(0,0)],3),
    ([1,4,4,1],[(4,5),(3,5)],1),
    ([0,5,0,5],[(4,5),(1,2)],1),
    ([4,4,4,4],[(2,5),(2,5)],2),
])
def test_four_face_integer_optimum_matches_exhaustive_lattice(cap,intervals,allowance):
    keys=['0:negative','0:positive','1:negative','1:positive'];caps={k:v*1e-9 for k,v in zip(keys,cap)}
    a,_,_=vertices();b=np.array(cap+[0]*4+[v for lo,hi in intervals for v in(hi,-lo)]+[allowance]*4)
    feasible=[x for x in product(*[range(v+1)for v in cap])if np.all(a@x<=b)]
    if not feasible:
        with pytest.raises(ValueError,match='INFEASIBLE'):allocate(caps,[(lo*1e-9,hi*1e-9)for lo,hi in intervals],allowance*1e-9)
    else:
        q=allocate(caps,[(lo*1e-9,hi*1e-9)for lo,hi in intervals],allowance*1e-9)
        assert np.all(a@q['growth_units']<=b)
        assert sum(q['growth_units'])==max(map(sum,feasible))


def fixture():
    rows={}
    for sid,a,b in [('a',0.,.02),('b',.02,.08)]:
        rows[sid]=dict(original_ref={'source':sid},metadata=dict(route_points_mm=[[a,0.],[b,0.]],minimum_caliper_mm=.05,aperture_family=['C',.05],route_kind='segment'))
    cores={s:box(r['metadata']['route_points_mm'][0][0],-.025,r['metadata']['route_points_mm'][-1][0],.025)for s,r in rows.items()}
    material={s:box(g.bounds[0],-.03,g.bounds[2],.03)for s,g in cores.items()}
    return rows,cores,material


def test_already_grown_chain_uses_full_span_and_preserves_the_floor():
    rows,cores,material=fixture();before=dict(material);fixed=box(-1.,-.035,0.,.035);material['group:0']=fixed;blob=to_wkb(fixed)
    reports=[dict(source_id=s,selected_factor=1.2)for s in rows]
    ribbons,q=run(rows,material,{'route':['a','b']},reports,{('route',(0.,0.)):section(0.,.075)},dict(a=.075,b=.075),set(),lambda s:('own',),source_cores=cores)
    assert q['constructed_chains']==1 and q['constructed_sources']==2 and q['already_grown_sources_considered']==2
    assert q['candidate_geometry_verifications']==1 and q['constructed_groups_audited']==q['r_tree_queries']==0
    assert all(material[s].covers(before[s])for s in rows)and to_wkb(material['group:0'])==blob
    assert ribbons['a']['shared_residual_chain_id']==ribbons['b']['shared_residual_chain_id']
    assert ribbons['a']['real_endpoints']==[True,False]and ribbons['b']['real_endpoints']==[False,True]
    descriptors=describe(rows,{'route':['a','b']},{},set(),ribbons,{})
    assert descriptors['a']['points']==[[0.,0.],[.02,0.],[.08,0.]]
    assert descriptors['a']['member_id']==descriptors['b']['member_id']


def test_smooth_chain_replaces_optional_steps_but_preserves_original_copper_and_groups():
    rows,cores,material=fixture();old=dict(material);fixed=box(-1,-.0375,0,.0375);material['group:0']=fixed
    ends={('route',(0.,0.)):section(0.,.075),('route',(.08,0.)):section(.08,.05)}
    ribbons,proof=run(rows,material,{'route':['a','b']},[dict(source_id=s,selected_factor=1.2)for s in rows],ends,
        dict(a=.075,b=.075),set(),lambda s:('own',),source_cores=cores,replace_optional_floor=True)
    assert proof['constructed_sources']==2 and proof['reports'][0]['optional_floor_replaced']
    assert proof['reports'][0]['removed_optional_area_mm2']>0
    assert proof['reports'][0]['addition_check']['passed']and proof['reports'][0]['pocket_check']['passed']
    assert all(material[s].covers(cores[s])for s in rows)
    assert any(not material[s].covers(old[s])for s in rows)and to_wkb(material['group:0'])==to_wkb(fixed)
    assert material['a'].equals_exact(material['b'],0)
    pa,pb=(ribbons[s]['side_field_proofs'][0]for s in('a','b'))
    for side in(0,1):
        assert pa['controls'][side][-1]==pytest.approx(pb['controls'][side][0])
        assert pa['endpoint_derivatives'][side][1]==pytest.approx(pb['endpoint_derivatives'][side][0])


def test_smooth_chain_with_fixed_nominal_ends_retains_a_smooth_interior_growth_field():
    rows,cores,material=fixture();ends={('route',(0.,0.)):section(0.,.05),('route',(.08,0.)):section(.08,.05)}
    ribbons,proof=run(rows,material,{'route':['a','b']},[dict(source_id=s,selected_factor=1.2)for s in rows],ends,
        dict(a=.075,b=.075),set(),lambda s:('own',),source_cores=cores,replace_optional_floor=True)
    assert proof['constructed_sources']==2
    body=material['a'];assert body.intersection(LineString([[.04,-.1],[.04,.1]])).length>.05
    assert body.intersection(LineString([[0,-.1],[0,.1]])).length==pytest.approx(.05)
    assert body.intersection(LineString([[.08,-.1],[.08,.1]])).length==pytest.approx(.05)


def test_piecewise_chain_receipt_retains_the_midpoint_and_reversed_source_tangents():
    from src.gerber_u05.ribbon_profile import build
    from src.gerber_u05.residual_chain_match import local_recipe
    points=[[0.,0.],[.1,0.],[.3,0.]]
    _,recipe=build(points,.05,.075,ends=[section(0.,.05),section(.3,.05)])
    chain=dict(points=points,width=.05,chain_id='RC-pieces',source_ids=['a','b'])
    q=local_recipe(recipe,chain,dict(source_id='b',first_mm=.1,last_mm=.3,forward=False))
    assert len(q['side_field_proofs'])==2
    assert sum(p['length_mm']for p in q['side_field_proofs'])==pytest.approx(.2)
    a,b=q['side_field_proofs'];assert a['controls'][0][-1]==pytest.approx(b['controls'][0][0])
    assert a['endpoint_derivatives'][0][1]==pytest.approx(b['endpoint_derivatives'][0][0])
    assert q['endpoint_sections'][0]['upper_mm'][1]==pytest.approx(-.025)
    assert q['maximum_width_mm']==pytest.approx(.075)


def test_clearance_budget_limits_widths_before_proposal_and_never_moves_a_group():
    rows,cores,material=fixture();material['fixed']=box(-.1,.078,.2,.15);before=to_wkb(material['fixed'])
    reports=[dict(source_id=s,selected_factor=1.2)for s in rows]
    _,q=run(rows,material,{'route':['a','b']},reports,{('route',(0.,0.)):section(0.,.075)},dict(a=.075,b=.075),set(),lambda s:('foreign',)if s=='fixed'else('own',),source_cores=cores)
    assert q['constructed_chains']==1
    record=q['reports'][0]
    assert record['face_budgets_mm']['positive']<=.078-.025-.040128+1e-12
    assert record['addition_check']['passed']and to_wkb(material['fixed'])==before


def test_insufficient_input_budgets_keep_all_original_growth():
    rows,cores,material=fixture();material['fixed']=box(-.1,.031,.2,.15);before={s:to_wkb(g)for s,g in material.items()}
    reports=[dict(source_id=s,selected_factor=1.2)for s in rows]
    _,q=run(rows,material,{'route':['a','b']},reports,{('route',(0.,0.)):section(0.,.075)},dict(a=.075,b=.075),set(),lambda s:('foreign',)if s=='fixed'else('own',),source_cores=cores)
    assert not q['constructed_sources']and q['reports'][0]['reason']=='RESIDUAL_END_BUDGETS_INFEASIBLE'
    assert all(to_wkb(material[s])==g for s,g in before.items())


def test_chain_order_can_reverse_source_occurrences_without_creating_seams():
    rows,_,_=fixture();rows['b']['metadata']['route_points_mm'].reverse()
    result,deferred=chains(rows,{'route':['b','a']},{'a','b'})
    assert not deferred and len(result)==1 and result[0]['points']==[[0.,0.],[.02,0.],[.08,0.]]
    assert [v['forward']for v in result[0]['intervals']]==[True,False]


def test_new_pocket_from_chain_growth_is_rejected_before_corner_processing():
    pts=[[0,.03],[.1,.03],[.1,.2],[-.1,.2],[-.1,-.2],[.1,-.2],[.1,-.03],[0,-.03]]
    core=LineString(pts).buffer(.025,quad_segs=128);material={'s':core}
    rows={'s':dict(original_ref={},metadata=dict(route_points_mm=pts,minimum_caliper_mm=.05,aperture_family=['C',.05],route_kind='arc'))};ends={}
    for point,normal in((pts[0],[0,1]),(pts[-1],[0,-1])):
        point=np.array(point);n=np.array(normal)
        ends['r',tuple(point)]=dict(normal=normal,lower_mm=(point-n*.0375).tolist(),upper_mm=(point+n*.0375).tolist())
    _,q=run(rows,material,{'r':['s']},[dict(source_id='s',selected_factor=1.)],ends,dict(s=.075),set(),lambda s:('own',),source_cores={'s':core})
    assert q['reports'][0]['status']=='KEEP_PRECEDING_RESULT; NEW_RESIDUAL_POCKET'
    assert q['constructed_sources']==0 and to_wkb(material['s'])==to_wkb(core)


def test_input_operand_binding_is_independent_of_dictionary_insertion_order():
    from src.gerber_u05.residual_corridor import Corridors
    from src.gerber_u05.residual_chain_budget import Budgets
    records=[('b',('b',),box(0,0,1,1)),('a',('a',),box(2,0,3,1))]
    assert Budgets(records).binding==Budgets(records[::-1]).binding
    assert Corridors(records).binding==Corridors(records[::-1]).binding


def test_zero_budget_propagation_keeps_the_global_pair_optimum():
    from src.gerber_u05.residual_chain_budget import allocate_components
    from src.gerber_u05.member_allocation import maximum_pair_packing
    caps={k:.01 for k in 'abcdef'};pairs=[('a','b',.01),('b','c',0.),('c','d',.003),('d','e',.007),('e','f',.01)]
    old=maximum_pair_packing(caps,pairs);new=allocate_components(caps,pairs)
    assert old['primal_objective_doubled_units']==new['primal_objective_doubled_units']
    assert new['growth_mm']['b']==new['growth_mm']['c']==0.
    assert len(new['components'])>1 and new['active_pairs']<new['original_pairs']
    assert new==allocate_components(dict(reversed(list(caps.items()))),pairs[::-1])


def test_chain_receipts_are_prepared_atomically(monkeypatch):
    from src.gerber_u05 import residual_chain_match as module
    rows,cores,material=fixture();before={s:to_wkb(g)for s,g in material.items()};real=module.local_recipe
    def fail_second(recipe,chain,interval):
        if interval['source_id']=='b':raise ValueError('DELIBERATE_RESTRICTION_FAILURE')
        return real(recipe,chain,interval)
    monkeypatch.setattr(module,'local_recipe',fail_second)
    accepted,q=run(rows,material,{'route':['a','b']},[dict(source_id=s,selected_factor=1.2)for s in rows],{('route',(0.,0.)):section(0.,.075)},dict(a=.075,b=.075),set(),lambda s:('own',),source_cores=cores)
    assert not accepted and q['constructed_sources']==0
    assert q['reports'][0]['reason']=='DELIBERATE_RESTRICTION_FAILURE'
    assert all(to_wkb(material[s])==g for s,g in before.items())


@pytest.mark.parametrize('points,reason',[
    ([[0.,0.],[1.,0.],[.01,.1]],'RESIDUAL_MITER_OUTLIER'),
    ([[0.,0.],[1.,0.],[.01,0.]],'RESIDUAL_REVERSAL_JOIN_UNSUPPORTED'),
])
def test_unsupported_chain_frame_keeps_prior_growth_and_decisions(points,reason):
    from copy import deepcopy
    core=LineString(points).buffer(.025);grown=LineString(points).buffer(.03)
    rows={'s':dict(original_ref={},metadata=dict(route_points_mm=points,
        minimum_caliper_mm=.05,aperture_family=['C',.05],route_kind='segment'))}
    material={'s':grown};reports=[dict(source_id='s',selected_factor=1.2)]
    before=deepcopy(reports)
    accepted,q=run(rows,material,{'r':['s']},reports,
        {('r',tuple(points[0])):section(0.,.075)},dict(s=.075),set(),
        lambda s:('own',),source_cores={'s':core})
    assert not accepted and q['constructed_sources']==0
    assert q['reports'][0]['status']=='KEEP_PRECEDING_RESULT; CONSTRUCTION_LIMIT'
    assert q['reports'][0]['reason']==reason
    assert material['s']is grown and reports==before
    assert q['candidate_geometry_verifications']==q['input_rail_distance_calls']==0


def test_unexpected_frame_error_still_propagates(monkeypatch):
    from src.gerber_u05 import residual_chain_match as module
    rows,cores,material=fixture()
    def unexpected(*args,**kwargs):raise ValueError('DELIBERATE_BAD_INPUT')
    monkeypatch.setattr(module,'frame',unexpected)
    with pytest.raises(ValueError,match='DELIBERATE_BAD_INPUT'):
        run(rows,material,{'route':['a','b']},
            [dict(source_id=s,selected_factor=1.2)for s in rows],
            {('route',(0.,0.)):section(0.,.075)},dict(a=.075,b=.075),
            set(),lambda s:('own',),source_cores=cores)


def test_last_source_restriction_clamps_only_roundoff_at_true_chain_end():
    from src.gerber_u05.residual_chain_match import local_recipe
    from src.gerber_u05.ribbon_profile import match_ends
    points=[[0.,0.],[.1,0.],[.3,0.]]
    _,recipe=match_ends(points,.05,.075,ends=[section(0.,.075),section(.3,.075)])
    chain=dict(points=points,width=.05,chain_id='RC-roundoff',source_ids=['a','b'])
    q=local_recipe(recipe,chain,dict(source_id='b',first_mm=.1,last_mm=.30000000000000004,forward=True))
    assert q['real_endpoints']==[False,True]and q['endpoint_sections'][-1]['lower_mm'][0]==.3
    with pytest.raises(ValueError,match='OUTSIDE_NATIVE_PATH'):
        local_recipe(recipe,chain,dict(source_id='b',first_mm=.1,last_mm=.31,forward=True))


def test_component_solver_retains_the_existing_optimum_on_mixed_sparse_graphs():
    from src.gerber_u05.residual_chain_budget import allocate_components
    from src.gerber_u05.member_allocation import maximum_pair_packing
    rng=np.random.default_rng(20261121);keys=list('abcdef')
    for _ in range(40):
        caps={k:float(int(rng.integers(0,21)))*1e-9 for k in keys}
        pairs=[(a,b,float(int(rng.integers(0,41)))*1e-9)for i,a in enumerate(keys)for b in keys[i+1:]if rng.random()<.4]
        old=maximum_pair_packing(caps,pairs);new=allocate_components(caps,pairs)
        assert new['primal_objective_doubled_units']==old['primal_objective_doubled_units']


def test_local_rail_bounds_skip_distant_diagonal_copper_without_losing_nearby_copper():
    from src.gerber_u05.residual_chain_budget import Budgets
    rail=LineString(np.linspace([0,0],[10,10],1001));records=[('near',('other',),box(3.,3.04,3.05,3.07)),('far',('other',),box(1.,8.,1.1,8.1))]
    for cells in(1,3,64,262144):
        ws=Budgets(records,screen_cells=cells);hits=ws.neighbors(rail,('own',),.08)
        assert [k for k,g in hits]==['near']and ws.screen_rejections==1
        assert all(g.distance(rail)>.08 for k,o,g in records if k not in{k for k,g in hits})


def test_rail_bounds_match_brute_distance_caps_over_saved_style_curves_and_budgets():
    from src.gerber_u05.residual_chain_budget import Budgets
    rng=np.random.default_rng(20261122);t=np.linspace(0,np.pi*1.6,257);rail=LineString(np.column_stack([np.cos(t),np.sin(t)]))
    records=[]
    for i in range(100):
        x,y=rng.uniform(-1.4,1.4,2);records.append((str(i),('other',),box(x,y,x+.03,y+.04)))
    required=.040128;cap=.03;expected=min([cap,*[max(0.,rail.distance(g)-required)for _,_,g in records]])
    hashes=[]
    for cells in(1,19,262144):
        ws=Budgets(records,screen_cells=cells);hits=ws.neighbors(rail,('own',),cap+required)
        actual=min([cap,*[max(0.,rail.distance(g)-required)for _,g in hits]])
        assert actual==expected
        hashes.append([k for k,g in hits])
    assert hashes[0]==hashes[1]==hashes[2]


def test_shared_chain_descriptor_uses_true_outer_receipts_for_reversed_custody():
    from src.gerber_u05.ribbon_profile import build
    from src.gerber_u05.residual_chain_match import local_recipe
    from src.gerber_u05.corner_transition import corners
    points=[[0.,0.],[.001,.002],[.1,.002],[.3,.002]]
    ends=[section(0.,.075),dict(normal=[0.,1.],lower_mm=[.3,-.0355],upper_mm=[.3,.0395])]
    _,recipe=build(points,.05,.075,ends=ends)
    chain=dict(points=points,width=.05,chain_id='true-ends',source_ids=['b'])
    length=LineString(points).length
    local=local_recipe(recipe,chain,dict(source_id='b',first_mm=.05,last_mm=length,forward=False))
    rows={'b':dict(metadata=dict(route_points_mm=[[.3,.002],[.05,.002]],minimum_caliper_mm=.05,aperture_family=['C',.05],route_kind='segment'))}
    desc=describe(rows,{'r':['b']},{},set(),{'b':local},{})['b']
    assert desc['endpoint_sections'][0]['lower_mm']==ends[1]['upper_mm']
    assert desc['endpoint_sections'][1]['upper_mm']==ends[0]['lower_mm']
    values,_=corners(desc,0,skin=False)
    assert np.array_equal(values,[ends[1]['upper_mm'],ends[1]['lower_mm']])
