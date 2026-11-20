from shapely.geometry import box
from shapely.ops import unary_union
from src.gerber_u05.tangent_finish import materialize
from src.gerber_u05.corner_transition import new_pocket_regions


def test_trim_cannot_leave_a_new_enclosed_pocket_inside_overlapping_joint_copper():
    floor=box(-.1,-.025,.1,.025);patch=box(-.02,.02,.02,.04);cut=box(-.003,.028,.003,.032)
    before=unary_union([floor,patch])
    finished,proof=materialize([dict(route_id='r',source_id='a',geometry=patch)],dict(a=cut),dict(r=floor))
    actual=unary_union([floor,finished[0]['geometry']])
    assert not new_pocket_regions(before,actual)
    assert actual.difference(before).area==0 and actual.covers(floor)
    assert proof['support_limited_routes']==[]


def test_only_new_trim_pockets_are_restored_and_original_voids_stay_open():
    floor=box(-.1,-.025,.1,.025);original_void=box(.008,.03,.012,.034)
    patch=box(-.02,.02,.02,.04).difference(original_void);before=unary_union([floor,patch])
    finished,proof=materialize([dict(route_id='r',source_id='a',geometry=patch)],dict(a=box(-.003,.028,.003,.032)),dict(r=floor))
    actual=unary_union([floor,finished[0]['geometry']])
    assert not new_pocket_regions(before,actual)
    assert actual.intersection(original_void).area==0
    assert actual.difference(before).area==0


def test_restoration_handles_a_joint_operand_whose_optional_copper_was_entirely_cut():
    floor=box(-.1,-.025,.1,.025);pocket=box(-.003,.028,.003,.032)
    ring=box(-.02,.02,.02,.04).difference(pocket)
    fill=pocket.buffer(.0001,quad_segs=32)
    before=unary_union([floor,ring,fill])
    patches=[dict(route_id='r',source_id='ring',geometry=ring),dict(route_id='r',source_id='fill',geometry=fill)]
    finished,proof=materialize(patches,dict(fill=fill),dict(r=floor))
    actual=unary_union([floor,*[p['geometry']for p in finished]])
    assert not new_pocket_regions(before,actual)
    assert actual.difference(before).area==0 and proof['support_limited_routes']==[]
