from types import SimpleNamespace
from src.gerber_u05.maximal_group_plan import MaximalGroups

SETTINGS=SimpleNamespace(maximum_factor=1.5,maximum_total_width_increase_mm=.03)


def fixture(spec):
    runs=[dict(run_id=str(i),route_id=str(i),source_ids=[str(i)],start=[lo,y],end=[hi,y],
               length_mm=hi-lo,width_mm=.05)for i,(lo,hi,y)in enumerate(spec)]
    membership=dict(straight_groups=[dict(group_id='group',members=[dict(route_id=r['route_id'],native_run_indices=[i])for i,r in enumerate(runs)])])
    return dict(runs=runs),membership


def test_members_keep_unequal_native_lengths_and_one_allocation_each():
    straight,membership=fixture([(0.,2.,0.),(.3,1.5,.095)])
    q=MaximalGroups(straight,membership,['0','1'],SETTINGS).plan()
    assert len(q['groups'])==2 and len(q['member_allocation_models'])==1
    assert q['groups'][0]['member_domain_mm']==[0.,2.]
    assert q['groups'][1]['member_domain_mm']==[.3,1.5]
    assert q['groups'][0]['first_mm']<q['groups'][1]['first_mm']
    assert q['groups'][0]['last_mm']>q['groups'][1]['last_mm']
    assert not q['geometry_audit']


def test_long_member_shares_one_face_decision_with_two_sequential_neighbors():
    straight,membership=fixture([(0.,2.,0.),(0.,.8,.095),(1.2,2.,.096)])
    q=MaximalGroups(straight,membership,['0','1','2'],SETTINGS).plan()
    assert len(q['groups'])==3
    model=q['member_allocation_models'][0]['allocation']
    assert len(model['pair_budget_units'])==2
    assert model['total_width_growth_units']==model['dual_cost_units']
    assert len([g for g in q['groups']if g['lanes'][0]['run_id']=='0'])==1


def test_covered_source_is_fixed_even_when_its_route_has_an_active_source():
    straight,membership=fixture([(0.,2.,0.),(0.,2.,.095)])
    straight['runs'][1]['route_id']='0'
    membership['straight_groups'][0]['members'][1]['route_id']='0'
    q=MaximalGroups(straight,membership,['0'],SETTINGS,mutable_sources={'0'}).plan()
    assert all(g['lanes'][0]['source_ids']==['0']for g in q['groups'])
    allocation=q['member_allocation_models'][0]['allocation']
    assert allocation['growth_cap_units']['1']==0


def test_mixed_covered_run_stays_whole_and_uses_default_for_exposed_sources():
    straight,membership=fixture([(0.,2.,0.),(0.,2.,.095)])
    straight['runs'][0]['source_ids']=['0','covered']
    q=MaximalGroups(straight,membership,['0','1'],SETTINGS,mutable_sources={'0','1'}).plan()
    assert all('0'not in g['lanes'][0]['source_ids']for g in q['groups'])
    assert any(v['reason'].startswith('MIXED_COVERED_NATIVE_RUN')for v in q['residual_groups'])


def test_bad_nominal_pair_does_not_discard_unrelated_free_lanes():
    straight,membership=fixture([(0.,2.,0.),(0.,2.,.03),(0.,2.,.2),(0.,2.,.3)])
    q=MaximalGroups(straight,membership,['0','1','2','3'],SETTINGS).plan()
    assert {g['lanes'][0]['run_id']for g in q['groups']}=={'2','3'}
    assert all(g['lanes'][0]['width_mm']>.05 for g in q['groups'])
    assert q['residual_groups'][0]['members']==['0','1']
