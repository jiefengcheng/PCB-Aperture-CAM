import json
from pathlib import Path
import pytest
from shapely import from_wkb
from shapely.geometry import box, GeometryCollection, LineString, Point, Polygon
from src.gerber_u05.normalized_additions import verify, verify_patch, _area_delta
from src.native_inventory import ERROR_MM
from src.trace_width_clearance import TraceWidthContract


def test_normalization_removes_noise_without_a_false_core_preservation_claim():
    core=box(0,0,1,.05).union(box(.4,-.000001,.6,0))
    actual=box(0,0,1,.06)
    report=verify(core,actual,[dict(id='foreign',geometry=box(0,.11,1,.2))])
    assert report['passed']and report['removed_area_mm2']>0
    assert report['constructed_groups_audited']==0


def test_new_bridge_cannot_hide_behind_another_candidate_or_port_exemption():
    core=box(0,0,1,.05);actual=box(0,0,1,.07)
    report=verify(core,actual,[dict(id='foreign',geometry=box(0,.10,1,.2))])
    assert not report['passed']
    assert report['failures'][0]['reason']=='NEW_EXPOSED_COPPER_BELOW_CONSTRUCTION_GUARD'


def test_unchanged_old_close_copper_is_not_a_new_addition():
    core=box(0,0,1,.05)
    assert verify(core,core,[dict(id='foreign',geometry=box(0,.06,1,.2))])['passed']


def test_default_envelope_has_the_unchanged_error_margin():
    core=box(0,0,1,.05);actual=box(0,0,1,.06)
    guard=TraceWidthContract().construction_gap_mm
    foreign=box(0,.06+guard+ERROR_MM/2,1,.2)
    assert not verify(core,actual,[dict(id='foreign',geometry=foreign)])['passed']


def test_valid_overlay_keeps_all_exact_area_parts_and_clearance_failures():
    fixture=json.loads((Path(__file__).parent/'fixtures/l35_addition_overlay.json').read_text())
    core=from_wkb(bytes.fromhex(fixture['core_wkb_hex']))
    actual=from_wkb(bytes.fromhex(fixture['actual_wkb_hex']))
    difference=actual.difference(core)
    assert core.is_valid and actual.is_valid and difference.is_valid
    assert difference.geom_type=='GeometryCollection'
    delta=_area_delta(difference)
    assert delta.area==difference.area
    assert [p.wkb for p in delta.geoms]==[p.wkb for p in difference.geoms if p.geom_type=='Polygon']
    report=verify(core,actual,[])
    assert report['passed'] and report['added_area_mm2']==difference.area
    # A genuine foreign-copper collision still fails on the same exact delta.
    assert not verify(core,actual,[dict(id='foreign',geometry=delta)])['passed']


def test_area_extraction_keeps_tiny_polygons_and_nested_parts():
    tiny=box(2,2,2+1e-9,2+1e-9)
    parts=GeometryCollection([box(0,0,1,1),GeometryCollection([tiny,Point(3,3)]),LineString([(4,4),(5,5)])])
    delta=_area_delta(parts)
    assert delta.area==parts.area and len(delta.geoms)==2
    assert delta.geoms[1].wkb==tiny.wkb
    assert _area_delta(GeometryCollection([Point(0,0)])).is_empty


def test_invalid_bodies_and_direct_mixed_patches_remain_fatal():
    invalid=Polygon([(0,0),(1,1),(0,1),(1,0),(0,0)])
    with pytest.raises(ValueError,match='INVALID_FINITE_COPPER_GEOMETRY'):
        verify(box(0,0,1,1),invalid,[])
    with pytest.raises(ValueError,match='INVALID_FINITE_COPPER_GEOMETRY'):
        verify(box(0,0,1,1),box(0,0,2,2),[dict(id='foreign',geometry=invalid)])
    with pytest.raises(ValueError,match='INVALID_FINITE_COPPER_GEOMETRY'):
        verify_patch(GeometryCollection([box(0,0,1,1),Point(2,2)]),[])
    with pytest.raises(ValueError,match='INVALID_FINITE_COPPER_GEOMETRY'):
        _area_delta(invalid)
