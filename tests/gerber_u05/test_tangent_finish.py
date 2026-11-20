from shapely.geometry import box,LineString
from shapely.ops import unary_union
from src.gerber_u05.tangent_finish import face_cut
from src.gerber_u05.straight_shoulders import localize
from src.gerber_u05.continuous_profile import straight_fields


def test_tangent_cut_removes_a_tooth_without_thinning_nominal_core_or_group():
    core=box(-.3,-.025,.3,.025)
    support=unary_union([box(-.3,-.035,.3,.035),box(-.002,.035,.002,.038)])
    group=box(-.3,-.035,-.1,.035)
    cut=face_cut(support,[0,0],[1,0],box(-.06,-.06,.06,.06),unary_union([core,group]))
    assert cut.area>1e-7
    result=support.difference(cut)
    assert result.covers(core)and result.covers(group)
    assert result.geom_type=='Polygon'and result.is_valid
    assert cut.difference(support).is_empty
    assert cut.intersection(box(-.06,.0375,.06,.04)).area>0


def test_tangent_finish_retains_a_smooth_straight_face():
    shape=box(-.3,-.035,.3,.035)
    cut=face_cut(shape,[0,0],[1,0],box(-.06,-.06,.06,.06),box(-.3,-.025,.3,.025))
    assert cut.area<1e-10


def test_local_shoulders_keep_original_constraint_and_native_source_extent():
    record=dict(axis=[1,0],length_mm=2.,constraints=[dict(first_mm=.5,last_mm=1.5,width_mm=.075,profile_midline_shift_mm=.005,group_band='group')],inherit_sided_endpoints=True)
    refined=localize(record,.05,.5)
    assert record['constraints'][0]in refined['constraints']and record['inherit_sided_endpoints']
    field=straight_fields(refined,.05)
    assert field['passed']
    assert field['pieces'][0]['first_mm']==0 and field['pieces'][-1]['last_mm']==2
    own=next(p for p in field['pieces']if p['first_mm']==.5 and p['last_mm']==1.5)
    assert own['controls']==[[-.0325]*4,[.042499999999999996]*4]
    assert field['pieces'][0]['controls']==[[-.025]*4,[.025]*4]
