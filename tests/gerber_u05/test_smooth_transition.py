import pytest
from src.gerber_u05.smooth_transition import certify,value,tessellate


def test_both_sides_use_a_shared_c1_field_inside_the_allocated_gap():
    q=certify([0.,.1],[.02,.13],.5,paired_budgets=[(0,1,.08,.08)])
    assert q['passed'] and q['endpoint_derivatives']==[0.,0.]
    assert all(v>=0 for v in q['spare_gap_controls_mm'][0])
    assert value(q['controls'][0],.5)==pytest.approx(.01)
    assert not q['geometry_audit']


def test_short_abrupt_change_is_rejected_rather_than_made_into_a_kink():
    q=certify([0.],[.025],.05)
    assert not q['passed'] and q['failures']==['TRANSITION_TOO_SHORT_FOR_SIDE_SLOPE']


def test_clear_endpoints_alone_do_not_certify_a_changing_gap_budget():
    # Ends satisfy an affine budget, but the smoothstep lags its rising bound.
    q=certify([0.,.04],[0.,.08],1.,paired_budgets=[(0,1,.04,.08)])
    assert not q['passed']
    assert 'PAIRED_CORRIDOR_CONTROL_BUDGET_EXCEEDED'in q['failures']


def test_polygonal_approximation_has_an_explicit_error_bound():
    c=[0.,0.,.025,.025];samples=tessellate(c,.3,error_mm=1e-7)
    for (a,x),(b,y)in zip(samples,samples[1:]):
        for f in(.25,.5,.75):
            t=(a+(b-a)*f)/.3
            assert abs(value(c,t)-(x+(y-x)*f))<=1e-7+1e-14
