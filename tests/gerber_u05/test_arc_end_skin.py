import math
from shapely.geometry import LineString,box
from src.gerber_u05.arc_end_skin import retain_native_end_planes


def test_optional_grown_round_caps_do_not_protrude_past_internal_native_joins():
    points=[[math.sin(t),1-math.cos(t)]for t in [i*.6/100 for i in range(101)]]
    path=LineString(points);original=path.buffer(.025,quad_segs=128);grown=path.buffer(.0375,quad_segs=128)
    result,proof=retain_native_end_planes(grown,original,points)
    assert proof['applied'] and original.difference(result).area<=1e-12
    assert original.difference(result).difference(result.buffer(.00001)).is_empty
    assert grown.difference(result).area>0
    assert result.difference(original).intersection(box(-.1,-.1,-.00003,.1)).area<1e-12
    assert not proof['source_path_changed']


def test_a_returning_native_path_is_kept_without_clipping_its_interior():
    points=[[0,0],[1,0],[1,1],[-1,1]];original=LineString(points).buffer(.025);grown=LineString(points).buffer(.0375)
    result,proof=retain_native_end_planes(grown,original,points)
    assert not proof['applied'] and result.wkb==grown.wkb
