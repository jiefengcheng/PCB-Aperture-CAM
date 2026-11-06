"""Gerber partitioning keeps pinched holes and every positive grid triangle."""
from pathlib import Path
import pytest
from shapely.geometry import Polygon, box
from shapely import to_wkb, from_wkb
from shapely.ops import unary_union
from src.gerber_u05 import pipeline as p
from src.gerber_u05 import exporter as e
from src.gerber_u05.contours import partition, verify_partition, contours
from src.pcb_data_abi.board_geometry import bridge_contour
from test_gerber_source import source_circle


def pinched_hole():
    return Polygon([(0, 0), (.01, 0), (.01, .01), (0, .01)],
                   holes=[[(0, .005), (.002, .004), (.002, .006)]])


def assert_roundtrip(shape, tmp_path):
    store = p.Store(tmp_path / 'store')
    records, blocks = [], []
    e.append_regions(shape, 'test', 'single-material-owner', records, blocks, store)
    base, _ = e.canonical_base(source_circle())
    actual = e.parse((base + ''.join(blocks) + 'M02*\n').encode())
    decoded = [p.affine_scale(p.source_profile.object_geometry(obj)[0], 1, -1, origin=(0, 0))
               for obj in actual.objects[-len(records):]]
    expected = unary_union([p.geometry(store, row['reference_ref']) for row in records])
    assert e.fidelity(expected, unary_union(decoded))['passed']
    assert all(obj.polarity_dark for obj in actual.objects[-len(records):])
    assert {row['source_id'] for row in records} == {'single-material-owner'}
    return records, unary_union(decoded)


def test_pinched_source_hole_uses_exact_partition_and_stays_empty(tmp_path):
    shape = pinched_hole()
    assert shape.is_valid
    with pytest.raises(Exception, match='non-cut-in contour self-touch|contour intersection outside cut-in endpoints'):
        bridge_contour(shape)
    pieces, proof = partition(shape, grid_mm=1e-6)
    assert proof['new_vertices'] == proof['dropped_positive_parts'] == 0
    assert len(pieces) > 1
    rows, actual = assert_roundtrip(shape, tmp_path)
    hole = Polygon(shape.interiors[0])
    assert actual.intersection(hole).area <= 1e-12
    assert any(row['component_reference_proof']['serialization_partition']['status']
               == 'EXACT_INTEGER_GRID_PARTITION' for row in rows)


def test_missing_positive_triangle_and_new_vertex_are_rejected():
    shape = pinched_hole()
    pieces, _ = partition(shape, grid_mm=1e-6)
    with pytest.raises(ValueError, match='INTEGER_AREA_CHANGED'):
        verify_partition(shape, pieces[:-1], grid_mm=1e-6)
    with pytest.raises(ValueError, match='INTRODUCED_VERTEX'):
        verify_partition(shape, [box(0, 0, .001, .001)], grid_mm=1e-6)


def test_ordinary_and_minimum_grid_triangles_keep_original_encoding(tmp_path):
    for index, shape in enumerate([box(0, 0, .01, .01),
                                  Polygon([(1, 1), (1.000001, 1), (1, 1.000001)])]):
        parts, proof = contours(shape, bridge_contour, grid_mm=1e-6)
        assert proof['status'] == 'ORIGINAL_CUT_IN_ENCODING'
        assert len(parts) == 1
        assert_roundtrip(shape, tmp_path / str(index))


def test_exact_retained_failed_reference_roundtrips_without_copper_change(tmp_path):
    path = Path(__file__).with_name('fixtures') / 'failed_reference.wkb'
    shape = from_wkb(path.read_bytes())
    assert p.digest(path.read_bytes()) == '1dbffe7d018536083957abc91a80d16eb08da15451d9853335b990e647b1f07b'
    pieces, proof = partition(shape, grid_mm=1e-6)
    assert len(pieces) == proof['parts'] == 211
    rows, actual = assert_roundtrip(shape, tmp_path)
    assert len(rows) == 211
    assert e.fidelity(shape, actual)['passed']


def test_valid_hole_without_axial_bridge_has_the_same_exact_alternative():
    shape = pinched_hole()
    def no_axis(polygon):
        if polygon.interiors:
            raise ValueError('BOARD_AXIAL_HOLE_BRIDGE_NOT_ESTABLISHED')
        return bridge_contour(polygon)
    parts, proof = contours(shape, no_axis, grid_mm=1e-6)
    assert proof['original_cut_in_rejection'] == 'BOARD_AXIAL_HOLE_BRIDGE_NOT_ESTABLISHED'
    assert verify_partition(shape, [part for part, _ in parts], grid_mm=1e-6)['status'] == 'EXACT_INTEGER_GRID_PARTITION'


def test_invalid_sources_and_unexpected_encoder_errors_still_stop():
    invalid = Polygon([(0, 0), (.01, .01), (0, .01), (.01, 0)])
    with pytest.raises(ValueError, match='SOURCE_INVALID'):
        contours(invalid, bridge_contour, grid_mm=1e-6)
    def broken(_):
        raise RuntimeError('unexpected implementation error')
    with pytest.raises(RuntimeError, match='unexpected implementation'):
        contours(box(0, 0, .01, .01), broken, grid_mm=1e-6)


def test_constructor_material_is_the_exact_parsed_parent_not_triangle_overlay(tmp_path):
    from src.gerber_u05.native_assembly import weld
    from src.gerber_u05.native_material import equality
    shape=from_wkb((Path(__file__).with_name('fixtures')/'failed_reference.wkb').read_bytes())
    store=p.Store(tmp_path/'store');records=[];blocks=[]
    parents=e.append_regions(shape,'t05','source-owner',records,blocks,store)
    assert len(parents)==1 and len(records)==211
    base,_=e.canonical_base(source_circle());plot=e.parse((base+''.join(blocks)+'M02*\n').encode())
    decoded=[p.affine_scale(p.source_profile.object_geometry(obj)[0],1,-1,origin=(0,0))for obj in plot.objects[-len(records):]]
    first=records[0];identity=(first['stage'],first['source_id'],first['component_reference_proof']['partition_parent_reference_proof']['export_reference_sha256'])
    reference,_=e.export_reference(e.native_grid(shape))
    actual,proof=weld(records,decoded,[(identity,reference)],grid_mm=1e-6)
    assert proof['parsed_regions']==211 and proof['parents']==1
    equality(e.native_grid(shape),actual[0][1],grid_mm=1e-6)
