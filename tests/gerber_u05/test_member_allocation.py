from itertools import product
from src.gerber_u05.member_allocation import maximum_faces,maximum_pair_packing


def test_one_long_face_obeys_multiple_neighbors_without_being_split():
    q=maximum_faces(['long','first','second'],dict(long=.03,first=.02,second=.02),
                    [('long','first',.01),('long','second',.005)],
                    face_caps={r:dict(left=.03,right=.03)for r in('long','first','second')})
    a=q['face_growth_mm']
    assert a['long']['right']+a['first']['left']<=.01+1e-12
    assert a['long']['right']+a['second']['left']<=.005+1e-12
    assert q['total_width_growth_units']==q['dual_cost_units']
    assert not q['geometry_audit']


def test_integer_optimum_matches_exhaustive_small_multi_neighbor_problems():
    quantum=1e-9;members=['a','b','c'];pairs=[('a','b',2*quantum),('a','c',quantum),('b','c',quantum)]
    caps=dict(a=3*quantum,b=2*quantum,c=3*quantum)
    q=maximum_faces(members,caps,pairs,face_caps={r:dict(left=2*quantum,right=2*quantum)for r in members})
    best=0
    for values in product(range(3),repeat=6):
        a={r:dict(left=values[2*i],right=values[2*i+1])for i,r in enumerate(members)}
        if any(sum(a[r].values())>v for r,v in zip(members,(3,2,3))):continue
        if any(a[x]['right']+a[y]['left']>v for x,y,v in[('a','b',2),('a','c',1),('b','c',1)]):continue
        best=max(best,sum(values))
    assert q['total_width_growth_units']==q['dual_cost_units']==best


def test_zero_width_and_face_caps_remain_fixed():
    q=maximum_faces(['a','fixed'],dict(a=.025,fixed=0.),[('a','fixed',.003)],
        face_caps=dict(a=dict(left=.025,right=.025),fixed=dict(left=0.,right=0.)))
    assert q['face_growth_units']['fixed']==dict(left=0,right=0)
    assert q['face_growth_mm']['a']['right']<=.003


def test_double_cover_solves_a_nonbipartite_three_face_budget_exactly():
    q=maximum_pair_packing(dict(a=3e-9,b=3e-9,c=3e-9),[('a','b',3e-9),('a','c',3e-9),('b','c',3e-9)])
    assert all(abs(v-1.5e-9)<1e-20 for v in q['growth_mm'].values())
    assert q['primal_objective_doubled_units']==q['dual_bound_doubled_units']==9
