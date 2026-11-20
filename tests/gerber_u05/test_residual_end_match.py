import numpy as np
import pytest
from shapely.geometry import box
from src.gerber_u05.ribbon_profile import match_ends
from src.gerber_u05.residual_corridor import Corridors,slab_interval


def end(x,width):
    return dict(normal=[0.,1.],lower_mm=[x,-width/2],upper_mm=[x,width/2])


def test_independent_end_allowance_removes_the_artificial_midpoint_requirement():
    body,q=match_ends([[0.,0.],[.005,0.]],.05,.075,
        ends=[end(0.,.075),end(.005,.065)],maximum_side_slope=1.)
    a,b=q['selected_end_widths_mm']
    assert .9*.075<=a<.075 and b==.065 and a!=b
    assert all(p['passed']and p['endpoint_derivatives']==[0.,0.]for p in q['side_field_proofs'])
    assert len(q['side_field_proofs'])==1
    assert body.covers(box(0.,-.025,.005,.025))
    assert not q['group_interiors_changed']and not q['clearance_certified']
    from src.stage_abi.store import canonical
    assert canonical(q)


def test_matching_can_use_cap_headroom_without_exceeding_it():
    _,q=match_ends([[0.,0.],[.04,0.]],.050038,.07187921,
        ends=[end(0.,.075057),end(.04,.075057)])
    assert q['selected_end_widths_mm']==[.07187921,.07187921]
    assert q['maximum_width_mm']<=.07187921+1e-12
    with pytest.raises(ValueError,match='CAP_OR_10_PERCENT'):
        match_ends([[0.,0.],[.04,0.]],.05,.075,ends=[end(0.,.1),end(.04,.1)])


def test_deviation_retracts_optional_growth_instead_of_cutting_the_nominal_side():
    ends=[dict(normal=[0.,1.],lower_mm=[x,-.025],upper_mm=[x,.05])for x in(0.,.04)]
    body,q=match_ends([[0.,0.],[.04,0.]],.05,.072,ends=ends)
    assert all(.072-1.1e-9<=w<=.072 for w in q['selected_end_widths_mm'])
    assert all(e['lower_mm'][1]==-.025 for e in q['endpoint_sections'])
    assert body.covers(box(0.,-.025,.04,.025))


def test_end_widths_do_not_establish_clearance_in_the_middle():
    candidate=box(0.,-.035,1.,.035)
    corridor=Corridors([('middle_obstacle',('foreign',),box(.45,.04,.55,.06))])
    q=corridor.certify(candidate,[1.,0.],('own',))
    assert not q['passed']and q['unproven_neighbors']==['middle_obstacle']
    assert q['geometry_distance_calls']==q['r_tree_queries']==q['candidate_geometry_verifications']==0


def test_once_compiled_corridor_accounts_for_future_residuals():
    candidate=box(0.,-.035,1.,.035)
    clear=Corridors([('fixed',('foreign',),box(0.,.08,1.,.1))])
    assert clear.certify(candidate,[1.,0.],('own',))['passed']
    reserved=Corridors([('fixed',('foreign',),box(0.,.08,1.,.1))],
        [('future',('foreign',),(0.,.06,1.,.1))])
    assert not reserved.certify(candidate,[1.,0.],('own',))['passed']


def test_slab_bound_sees_copper_even_when_all_vertices_are_outside_slab():
    coords=np.array([[-2.,-.1],[2.,-.1],[2.,.1],[-2.,.1],[-2.,-.1]])
    assert slab_interval(coords,[1.,0.],-.01,.01)==(-.1,.1)
