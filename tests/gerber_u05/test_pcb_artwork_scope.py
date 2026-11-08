"""PCB-only source selection preserves ordered clears, restorations and atoms."""
from pathlib import Path
import copy
import pytest
from shapely import to_wkb
from shapely.geometry import LineString, Point
from shapely.ops import polygonize, unary_union
from src.gerber_u05 import pipeline as p, pcb_artwork_scope as scope, source_assembly


HEADER = b'%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.200000*%\n%LPD*%\nD10*\n'


def xy(x, y, op):
    return f'X{round(x*1e6):010d}Y{round(y*1e6):010d}D{op:02d}*\n'.encode()


def rectangle(a, b, c, d):
    return b'G36*\n' + xy(a,b,2) + xy(c,b,1) + xy(c,d,1) + xy(a,d,1) + xy(a,b,1) + b'G37*\n'


def fixture():
    vertices=[(0,0),(10,0),(10,10),(0,10),(0,0)]
    outline=HEADER+xy(*vertices[0],2)+b''.join(xy(*point,1)for point in vertices[1:])+b'M02*\n'
    poly=next(iter(polygonize(unary_union([LineString([a,b])for a,b in zip(vertices,vertices[1:])]))))
    raw=(HEADER+rectangle(1,1,9,9)+b'%LPC*%\n'+rectangle(4,4,6,6)+
         b'%LPD*%\n'+xy(5,5,3)+rectangle(20,20,22,22)+xy(25,25,3)+b'M02*\n')
    contract=dict(selected='a-top.art.gbr',outline_name='a-outline.art.gbr',
                  source_sha256=p.digest(raw),outline_source_sha256=p.digest(outline),
                  outline_geometry_sha256=p.digest(to_wkb(poly)),authorization='Synthetic PCB-only scope')
    return raw,outline,contract


def image(raw):
    native,_,_=p.source_profile.parse_source(raw)
    return p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in native.objects)


def test_native_selection_preserves_hole_and_later_dark_restoration_without_clipping():
    raw,outline,contract=fixture();selected,proof=scope.select(raw,outline,contract)
    actual=image(selected)
    assert actual.contains(Point(2,2))and actual.contains(Point(5,5))
    assert not actual.contains(Point(4.5,4.5))and not actual.contains(Point(21,21))
    assert actual.symmetric_difference(image(raw).intersection(scope.outline_geometry(outline,contract['outline_geometry_sha256']))).is_empty
    assert proof['retained_original_ordinals']==[0,1,2]and proof['excluded_objects']==2
    assert [r['polarity_dark']for r in proof['retained_atom_proofs']]==[True,False,True]
    assert len(raw)==len(selected)and not proof['polarity_flattening']and not proof['growth']


def test_exact_complete_set_equality_proves_zero_distance_without_quadratic_distance(monkeypatch):
    from shapely.geometry.base import BaseGeometry
    def forbidden(*args,**kwargs):
        raise AssertionError('Redundant distance must not run after exact complete set equality')
    monkeypatch.setattr(BaseGeometry,'hausdorff_distance',forbidden)
    monkeypatch.setattr(BaseGeometry,'equals',lambda *args:False)
    raw,outline,contract=fixture();_,proof=scope.select(raw,outline,contract)
    comparison=proof['resolved_comparison']
    assert comparison['exact_complete_set_equal']and comparison['hausdorff_mm']==0


def test_nonempty_microscopic_hole_cannot_use_zero_area_as_an_equality_shortcut(monkeypatch):
    from shapely.geometry import box
    from shapely.geometry.base import BaseGeometry
    original=box(0,0,1,1);with_hole=original.difference(box(.5,.5,.5000001,.5000001))
    assert 0<original.difference(with_hole).area<p.EPS
    calls=[]
    def measured(a,b):calls.append(True);return .1
    monkeypatch.setattr(BaseGeometry,'hausdorff_distance',measured)
    with pytest.raises(ValueError,match='RESOLVED_MATERIAL_CHANGED'):
        scope.compare_material(original,with_hole)
    assert calls==[True]


def test_entire_clear_footprint_may_cross_outline_while_its_resolved_cutout_survives():
    raw,outline,contract=fixture();raw=raw.replace(rectangle(4,4,6,6),rectangle(4,4,11,6));contract['source_sha256']=p.digest(raw)
    selected,proof=scope.select(raw,outline,contract)
    assert proof['retained_original_ordinals']==[0,1,2]
    assert not image(selected).contains(Point(8,5))
    assert image(selected).contains(Point(5,5))


def test_positive_copper_straddling_outline_is_rejected_as_a_whole():
    raw,outline,contract=fixture();raw=raw.replace(b'M02*',xy(10,5,3)+b'M02*');contract['source_sha256']=p.digest(raw)
    with pytest.raises(ValueError,match='STRADDLES_OUTLINE'):scope.select(raw,outline,contract)


@pytest.mark.parametrize('mutation',['source','outline','cycle'])
def test_bound_source_outline_or_cycle_changes_are_rejected(mutation):
    raw,outline,contract=fixture()
    if mutation=='source':raw=raw.replace(b'0.200000',b'0.210000')
    elif mutation=='outline':outline=outline.replace(b'0.200000',b'0.210000')
    else:contract['outline_geometry_sha256']='a'*64
    with pytest.raises(ValueError,match='HASH_CHANGED|OUTLINE_NOT_UNIQUE'):scope.select(raw,outline,contract)


def test_captured_source_scope_requires_exact_registered_intent_and_original_companion(tmp_path,monkeypatch):
    raw,outline,contract=fixture();contract.update(selected='a-top.art.gbr',outline_name='a-outline.art.gbr')
    monkeypatch.setattr(scope,'REGISTERED',{'board':contract});run=tmp_path/'assembly';run.mkdir()
    inventory=dict(selected=contract['selected']);blobs={contract['selected']:raw,contract['outline_name']:outline}
    scope.capture(run,Path('/input/board'),blobs,inventory)
    assert scope.captured(run)==(contract,outline)
    (run/'pcb_outline.gbr').write_bytes(outline+b'changed')
    with pytest.raises(ValueError,match='OUTLINE_CHANGED'):scope.captured(run)


def test_known_board_cannot_silently_fall_back_to_unscoped_input(tmp_path,monkeypatch):
    raw,outline,contract=fixture();monkeypatch.setattr(scope,'REGISTERED',{'board':contract})
    with pytest.raises(ValueError,match='AUTHORIZATION_AND_OUTLINE_REQUIRED'):
        source_assembly.reconstruct(raw,p.Store(tmp_path/'runtime'))
    with pytest.raises(ValueError,match='INPUT_OR_OUTLINE_CHANGED'):
        scope.capture(tmp_path,Path('/input/board'),{'wrong.gbr':raw},dict(selected='wrong.gbr'))


def test_scope_and_enclosure_proof_retain_original_occurrence_identity(tmp_path):
    raw,outline,contract=fixture();selected,proof=source_assembly.reconstruct(raw,p.Store(tmp_path/'runtime'),(contract,outline))
    assert proof['schema']=='original-to-assembled-gerber/2'
    assert proof['raw_source_sha256']==p.digest(raw)
    assert proof['removed_original_ordinals']==[3,4]
    assert proof['retained_objects']==3
    assert source_assembly.verify_payload(raw,selected,proof,p.Store(tmp_path/'verify'),(contract,outline))==proof
    altered=copy.deepcopy(proof);altered['pcb_scope']['excluded_original_ordinals'].pop()
    with pytest.raises(ValueError,match='AUTHORIZED_CHANGE_OR_PROOF_CHANGED'):
        source_assembly.verify_payload(raw,selected,altered,p.Store(tmp_path/'bad'),(contract,outline))


def test_boundary_marker_is_kept_whole_for_mandatory_frame_removal(tmp_path):
    raw,outline,contract=fixture()
    plots=outline[len(HEADER):outline.index(b'M02*')]
    raw=raw.replace(b'M02*',plots+b'M02*');contract['source_sha256']=p.digest(raw)
    scoped,proof=scope.select(raw,outline,contract)
    assert proof['boundary_marker_original_ordinals']==[5,6,7,8]
    assert image(scoped).bounds[0]<0  # The original centered stroke was not clipped.
    assembled,combined=source_assembly.reconstruct(raw,p.Store(tmp_path/'runtime'),(contract,outline))
    assert set(proof['boundary_marker_original_ordinals'])<=set(combined['removed_original_ordinals'])
    assert image(assembled).bounds==pytest.approx((1,1,9,9))
