from shapely.geometry import box
from shapely.ops import unary_union
from src.gerber_u05.tangent_finish import materialize


def test_tip_cleanup_does_not_delete_a_preexisting_separate_joint_contribution():
    floor=box(-.1,-.025,.1,.025);old_separate=box(.07,.06,.071,.061)
    neck=box(0,.024,.002,.032);tip=box(0,.0295,.003,.032)
    patch=unary_union([neck,tip,old_separate])
    finished,proof=materialize([dict(route_id='r',source_id='a',geometry=patch)],dict(a=box(-.001,.0285,.004,.0295)),dict(r=floor))
    assert finished[0]['geometry'].covers(old_separate)
    assert proof['detached_optional_tips_removed']==1
