import pytest
from src.gerber_u05.ribbon_profile import build


def test_arc_inherits_both_frozen_sides_not_only_total_width():
    end=dict(normal=[0.,1.],lower_mm=[0.,-.028],upper_mm=[0.,.047])
    body,q=build([[0.,0.],[.1,.01],[.2,.04],[.3,.09]],.05,.075,ends=[end,None])
    assert q['endpoint_sections'][0]==end
    assert q['endpoint_faces_mm'][0]==pytest.approx([.003,.022])
    assert q['endpoint_faces_mm'][1]==pytest.approx([.003,.022])
    assert body.is_valid and q['exact_frozen_sections_retained']
    from src.stage_abi.store import canonical
    assert canonical(q)


def test_default_search_cannot_shrink_a_previously_frozen_end():
    end=dict(normal=[0.,1.],lower_mm=[0.,-.025],upper_mm=[0.,.05])
    _,q=build([[0.,0.],[.2,.01],[.4,.04]],.05,.075,ends=[end,None],interior_width=.055)
    assert q['maximum_width_mm']==pytest.approx(.075)
    assert q['endpoint_sections'][0]==end
    assert q['endpoint_faces_mm'][0]==pytest.approx([0.,.025])


def test_a_long_two_point_source_has_a_smooth_profile_not_two_endpoint_values():
    end=dict(normal=[0.,1.],lower_mm=[0.,-.025],upper_mm=[0.,.025])
    body,q=build([[0.,0.],[2.,0.]],.05,.075,ends=[end,None])
    assert len(body.exterior.coords)>100 and q['midpoint_faces_mm']==pytest.approx([.0125,.0125])
    assert q['maximum_width_mm']==pytest.approx(.075)


def test_conflicting_frozen_sections_are_not_moved_to_make_a_short_joint_fit():
    a=dict(normal=[0.,1.],lower_mm=[0.,-.025],upper_mm=[0.,.05])
    b=dict(normal=[0.,1.],lower_mm=[.01,-.05],upper_mm=[.01,.025])
    with pytest.raises(ValueError,match='FROZEN_JOINT_TRANSITION_TOO_SHORT'):
        build([[0.,0.],[.01,0.]],.05,.075,ends=[a,b])


def test_tight_default_bend_uses_a_swept_body_when_inner_rail_collapses():
    import math
    from shapely.geometry import LineString
    points=[[.02*math.cos(t),.02*math.sin(t)]for t in[0,.1,.2,.3,.4,.5,.6]]
    body,q=build(points,.1,.13)
    assert body.is_valid and body.covers(LineString(points))
    assert q['materialization']=='DEFAULT_SWEEP_CELL_UNION; CLEARANCE_VERIFICATION_REQUIRED'
    assert not q['clearance_certified']


def test_outlier_reach_limit_rejects_a_transition_without_moving_its_ends():
    with pytest.raises(ValueError,match='RESIDUAL_TRANSITION_REACH_OUTLIER'):
        build([[0.,0.],[1.,0.]],.05,.075,maximum_extra_reach_mm=.001)
def test_valid_outline_must_realize_its_complete_native_cross_sections():
    import numpy as np
    from shapely.geometry import LineString
    from src.gerber_u05.ribbon_profile import build,frame
    from src.gerber_u05.smooth_transition import value
    from src.native_inventory import ERROR_MM
    points=[[0.,0.],[.010425132833193,.002181591039488],[.011,.002],
            [.012200335611277,.002586769519859],[.109,.025]]
    body,recipe=build(points,.0508,.07618)
    assert recipe['folded_cross_section_cells']>0
    p,n,stations,length=frame(points)
    for point,normal,t in zip(p,n,stations):
        i=0 if t<=length/2 else 1;f=(t-i*length/2)/(length/2)
        offsets=[value(c,min(1.,max(0.,f)))for c in recipe['side_field_proofs'][i]['controls']]
        section=LineString([point-normal*(.0254+offsets[0]),point+normal*(.0254+offsets[1])])
        assert section.difference(body.buffer(ERROR_MM,quad_segs=128)).length<=ERROR_MM


def test_exact_interfaces_are_not_shrunk_by_free_interior_face_budgets():
    from src.gerber_u05.ribbon_profile import exact_ends
    from shapely.geometry import LineString
    ends=[dict(normal=[0.,1.],lower_mm=[x,-.0375],upper_mm=[x,.0375])for x in(0.,1.)]
    body,recipe=exact_ends([[0.,0.],[1.,0.]],.05,.075,ends=ends,face_budgets=dict(negative=.004,positive=.006))
    assert recipe['end_deviation']==0
    for end in ends:assert body.covers(LineString([end['lower_mm'],end['upper_mm']]))
    assert body.intersection(LineString([[.5,-.1],[.5,.1]])).length<.075
