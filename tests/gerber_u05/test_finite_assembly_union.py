import json
from pathlib import Path
import pytest
from shapely import from_wkb
from shapely.geometry import box, Polygon
from shapely.errors import GEOSException
from src.gerber_u05 import finite_profile_union as finite
from src.gerber_u05.native_contact_support import assemble, component_count


def test_exact_failed_local_union_retains_every_area_component():
    raw=json.loads((Path(__file__).parent/'fixtures/l35_local_union.json').read_text())
    parts=[from_wkb(bytes.fromhex(h))for h in raw['wkb_hex']]
    saved=[g.wkb for g in parts];recoveries=[]
    result=finite.assembly_union(parts,recoveries=recoveries,label='captured-source')
    assert result.is_valid and result.area>max(g.area for g in parts)
    assert all(g.difference(result).area==0 for g in parts)
    assert [g.wkb for g in parts]==saved
    assert recoveries[0]['method']=='BINARY_REVERSE_ORDER'
    assert recoveries[0]['all_operand_area_retained']
    assert not recoveries[0]['coordinate_adjustment']


def test_normal_path_stays_byte_identical_and_does_not_add_checks():
    parts=[box(0,0,2,2),box(1,1,3,3)];recoveries=[]
    assert finite.assembly_union(parts,recoveries=recoveries).wkb==finite.unary_union(parts).wkb
    assert recoveries==[]


def test_route_union_recovers_silent_nested_shell_output_without_copper_loss():
    raw=json.loads((Path(__file__).parent/'fixtures/l35_route_union.json').read_text())
    sources=raw['source_ids'];parts=[from_wkb(bytes.fromhex(h))for h in raw['wkb_hex']]
    assert all(g.is_valid for g in parts)
    assert not finite.unary_union(parts).is_valid
    recoveries=[]
    result=assemble(sources,dict(zip(sources,parts)),{},recoveries=recoveries,label=raw['route'])
    assert result.is_valid and component_count(result)==1
    assert all(g.difference(result).area==0 for g in parts)
    assert result.is_valid


def test_redundant_nested_overlay_shells_keep_all_face_area_exactly():
    raw=json.loads((Path(__file__).parent/'fixtures/l35_route_union.json').read_text())
    current=dict(zip(raw['source_ids'],[from_wkb(bytes.fromhex(h))for h in raw['wkb_hex']]))
    bad=finite.unary_union(list(current.values()))
    assert not bad.is_valid
    before={s:g.wkb for s,g in current.items()}
    result=finite.polygonal(bad)
    assert result.is_valid
    assert all(result.covers(face)for face in bad.geoms)
    assert result.wkb in [face.wkb for face in bad.geoms]
    assert before=={s:g.wkb for s,g in current.items()}


def test_exact_failed_shoulder_outline_uses_covered_face_without_new_overlay():
    raw=json.loads((Path(__file__).parent/'fixtures/l35_shoulder_overlay.json').read_text())
    failed=from_wkb(bytes.fromhex(raw['wkb_hex']));saved=failed.wkb
    assert not failed.is_valid and all(face.is_valid for face in failed.geoms)
    result=finite.polygonal(failed)
    assert result.is_valid and all(result.covers(face)for face in failed.geoms)
    assert result.wkb in [face.wkb for face in failed.geoms]
    assert failed.wkb==saved


def test_containment_cannot_fill_holes_or_repair_uncertified_overlaps():
    from shapely.geometry import MultiPolygon
    outer=box(0,0,4,4).difference(box(1,1,3,3))
    island=box(1.5,1.5,2.5,2.5);tiny=box(.1,.1,.1+1e-9,.1+1e-9)
    raw=MultiPolygon([outer,island,tiny]);assert not raw.is_valid
    result=finite.polygonal(raw)
    assert result.is_valid and result.covers(tiny) and result.covers(island)
    assert not result.intersects(box(1.1,1.1,1.3,1.3))
    overlap=MultiPolygon([box(0,0,2,2),box(1,1,3,3)])
    assert not overlap.is_valid and finite.polygonal(overlap).wkb==overlap.wkb


@pytest.mark.parametrize('metadata', ['precision','srid'])
def test_containment_never_changes_precision_or_coordinate_frame(metadata):
    from shapely import get_precision,get_srid,set_precision,set_srid
    from shapely.geometry import MultiPolygon
    g=MultiPolygon([box(0,0,4,4),box(1,1,2,2),box(8,8,9,9)])
    g=set_precision(g,.01,mode='pointwise') if metadata=='precision' else set_srid(g,4326)
    result=finite.polygonal(g)
    assert get_precision(result)==get_precision(g) and get_srid(result)==get_srid(g)
    # When rebuilding a multi-face collection would lose its metadata,
    # retain the original failure rather than silently changing its frame.
    assert result.wkb==g.wkb


def test_fallback_retains_holes_and_disjoint_small_parts(monkeypatch):
    ring=box(0,0,3,3).difference(box(1,1,2,2));tiny=box(4,4,4+1e-8,4+1e-8)
    def failed(_):raise GEOSException('controlled kernel failure')
    monkeypatch.setattr(finite,'unary_union',failed)
    result=finite.assembly_union([ring,tiny])
    assert result.is_valid and len(result.geoms)==2
    assert not result.intersects(box(1.1,1.1,1.9,1.9))
    assert tiny.difference(result).area==0


def test_invalid_operands_and_failed_exact_operations_remain_fatal(monkeypatch):
    def failed(_):raise GEOSException('controlled kernel failure')
    monkeypatch.setattr(finite,'unary_union',failed)
    invalid=Polygon([(0,0),(1,1),(0,1),(1,0),(0,0)])
    with pytest.raises(GEOSException,match='controlled kernel failure'):
        finite.assembly_union([box(0,0,1,1),invalid])
    monkeypatch.setattr(type(box(0,0,1,1)),'union',lambda *_:box(8,8,9,9))
    with pytest.raises(GEOSException,match='controlled kernel failure'):
        finite.assembly_union([box(0,0,1,1),box(1,0,2,1)])
