from shapely.geometry import box
from shapely.ops import unary_union
from src.gerber_u05.tangent_finish import materialize


def test_combined_trim_removes_detached_optional_tips_from_all_redundant_patches():
    floor=box(-.1,-.025,.1,.025);before=floor.wkb
    neck=box(0,.024,.002,.032);tip=box(0,.0295,.003,.032)
    patches=[dict(route_id='r',source_id='a',geometry=unary_union([neck,tip])),dict(route_id='r',source_id='b',geometry=tip)]
    finished,proof=materialize(patches,dict(a=box(-.001,.0285,.004,.0295)),dict(r=floor))
    actual=unary_union([floor,*[p['geometry']for p in finished]])
    assert actual.geom_type=='Polygon'and actual.covers(floor)and floor.wkb==before
    assert proof['detached_optional_tips_removed']==1 and proof['support_limited_routes']==[]
    assert all(not p['geometry'].intersects(box(0,.0305,.003,.032))for p in finished)


def test_a_large_detached_lobe_keeps_original_joint_copper_instead_of_silently_deleting_growth():
    floor=box(-.1,-.025,.1,.025)
    patch=unary_union([box(0,.024,.002,.04),box(0,.035,.02,.055)])
    original=[dict(route_id='r',source_id='a',geometry=patch)]
    finished,proof=materialize(original,dict(a=box(-.001,.029,.025,.031)),dict(r=floor))
    assert finished[0]['geometry'].wkb==patch.wkb
    assert proof['support_limited_routes']==['r']
