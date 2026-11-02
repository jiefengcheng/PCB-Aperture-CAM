"""No general hole support: only exact equivalence to the existing file grid."""
import pytest
from shapely.geometry import Point,Polygon,box,MultiPolygon
from shapely import set_precision,to_wkb
from src.pcb_data_abi.crop_quantization import export_reference
from src.pcb_data_abi.geometry import quantize,GRID_MM,fidelity


def test_ordinary_shapes_keep_same_reference_and_shared_behavior():
    shape=Point(0,0).buffer(.12497,quad_segs=128)
    reference,proof=export_reference(shape)
    assert reference is shape and proof is None
    assert to_wkb(quantize(reference)[0])==to_wkb(quantize(shape)[0])


def test_only_vanishing_hole_is_adapted_without_mutating_verified_geometry():
    hole=box(.2,.2,.2001,.2+1e-16)
    shape=Polygon(box(0,0,1,1).exterior,[hole.exterior]);before=to_wkb(shape)
    with pytest.raises(ValueError,match='UNSUPPORTED_TARGET_POLYGON'):quantize(shape)
    reference,proof=export_reference(shape)
    assert to_wkb(shape)==before and len(shape.interiors)==1
    assert not reference.interiors and proof['collapsed_holes']==1
    assert proof['verified_geometry_unchanged'] and proof['direct_normalization_equal']
    assert quantize(reference)[0].equals(set_precision(shape,GRID_MM,mode='valid_output'))
    assert proof['raw_symmetric_difference_mm2']<=proof['area_change_bound_mm2']
    assert fidelity(reference,quantize(reference)[0])['passed']


def test_resolvable_void_cannot_be_filled_by_export_adapter():
    shape=Polygon(box(0,0,1,1).exterior,[box(.2,.2,.3,.3).exterior])
    with pytest.raises(ValueError,match='RESOLVABLE_TARGET_HOLE'):export_reference(shape)


def test_mixed_resolvable_and_subgrid_holes_still_rejected():
    shape=Polygon(box(0,0,1,1).exterior,[box(.2,.2,.3,.3).exterior,box(.5,.5,.5001,.5+1e-16).exterior])
    with pytest.raises(ValueError,match='RESOLVABLE_TARGET_HOLE'):export_reference(shape)


def test_multipart_and_invalid_polygons_remain_unsupported():
    with pytest.raises(ValueError,match='UNSUPPORTED_TARGET_POLYGON'):
        export_reference(MultiPolygon([box(0,0,1,1),box(2,2,3,3)]))
    with pytest.raises(ValueError):export_reference(Polygon([(0,0),(1,1),(1,0),(0,1),(0,0)]))


def test_crop_reopen_rejects_changed_normalization_receipt(tmp_path):
    import json
    from src.pcb_data_abi.crop import CropDataService
    from src.stage_abi.store import digest
    service=CropDataService.__new__(CropDataService);service.out=tmp_path;service.board=tmp_path/'candidate.kicad_pcb';service.board.write_bytes(b'fixture')
    service.file_grid_normalization=[dict(source_id='actual',direct_normalization_equal=True)]
    (tmp_path/'pcb_kicad_write.json').write_text(json.dumps(dict(board_sha256=digest(b'fixture'),file_grid_normalization=[])))
    with pytest.raises(ValueError,match='NORMALIZATION_PROOF_CHANGED'):service.verify_kicad()


def test_subgrid_reference_uses_unchanged_native_writer_and_protected_checks():
    from src.pcb_data_abi import native
    from src.pcb_data_abi.crop import TEMPLATE
    from src.source_locators import locate
    from src.stage_abi.store import digest
    raw=b'(kicad_pcb (gr_circle (center 1 -1) (end 1.1 -1) (stroke (width 0) (type solid)) (fill yes) (layer F.Cu)) (gr_line (start 0 0) (end 1 0) (stroke (width .01) (type solid)) (layer F.Mask)))'
    outer=Point(1,-1).buffer(.15,quad_segs=128)
    hole=box(1.13,-1,1.131,-1+1e-16)
    verified=Polygon(outer.exterior,[hole.exterior]);reference,proof=export_reference(verified)
    sid=next(s.identity for s in locate(raw) if s.head=='gr_circle')
    decisions=[dict(key='S01',source_id=sid,aliases=[sid],decision='GROW_COMPANION',candidate_ref=dict(sha256=digest(to_wkb(verified))))]
    body,rows=native.write_board(raw,TEMPLATE,decisions,{sid:reference})
    checked=native.verify_board(raw,body,rows,decisions,{sid:reference})
    assert proof['direct_normalization_equal'] and checked['passed'] and checked['modified_occurrences']==1
