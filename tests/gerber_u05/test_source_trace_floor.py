import pytest
from shapely.geometry import box,LineString,Polygon
from src.gerber_u05.source_trace_floor import preserve


def test_a_finishing_cut_cannot_remove_original_cap_copper():
    core=LineString([(0,0),(1,0)]).buffer(.025,quad_segs=128)
    body=core.buffer(.01).difference(box(.99,-.05,1.05,.002))
    result,q=preserve(core,body)
    assert q['source_loss_before_mm2']>0 and q['source_loss_after_mm2']==0
    assert core.difference(result).area==0
    assert body.difference(result).area==0
    assert result.difference(core.union(body)).area==0


def test_already_additive_body_is_byte_preserved():
    core=box(0,0,1,.05);body=box(0,-.01,1,.06)
    result,q=preserve(core,body)
    assert result.wkb==body.wkb and not q['changed']


def test_disconnected_source_faces_are_not_silently_dropped():
    core=box(0,0,1,1).union(box(2,0,3,1));body=box(0,0,1.1,1)
    result,q=preserve(core,body)
    assert result.geom_type=='MultiPolygon'and core.difference(result).is_empty


def test_invalid_source_or_output_cannot_be_repaired_silently():
    broken=Polygon([(0,0),(1,1),(0,1),(1,0)])
    with pytest.raises(ValueError,match='VALID_FINITE'):
        preserve(box(0,0,1,1),broken)
