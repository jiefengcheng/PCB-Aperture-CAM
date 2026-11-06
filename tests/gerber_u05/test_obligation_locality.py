import pytest
from shapely.geometry import box,Polygon
from shapely.ops import unary_union
from src.u05_board.attachment_export import obligation_check,FILE_UNCERTAINTY_MM
from src.junction_spindle_stage import CONTRACT

def original(required,before,regions,already=False):
    physical=unary_union(regions).difference(before)if regions else Polygon()
    present=before if already else before.union(unary_union(regions))
    missing=required.difference(present.buffer(FILE_UNCERTAINTY_MM,quad_segs=64))
    if missing.area>CONTRACT.area_epsilon_mm2:raise ValueError('U05_ACTUAL_ATTACHMENT_EXTENT_MISSING')
    effective=physical.intersection(required.buffer(FILE_UNCERTAINTY_MM,quad_segs=64)).area
    if not already and(required.area<=CONTRACT.minimum_visible_addition_mm2 or effective<=CONTRACT.minimum_visible_addition_mm2):raise ValueError('U05_ACTUAL_ATTACHMENT_NO_EFFECT')
    return dict(passed=True,required_area_mm2=required.area,missing_beyond_file_uncertainty_mm2=missing.area,effective_actual_addition_mm2=effective,file_uncertainty_mm=FILE_UNCERTAINTY_MM)

@pytest.mark.parametrize('already',[False,True])
def test_remote_copper_cannot_change_complete_obligation_result(already):
    required=box(.8,.2,1.2,.8);local=box(0,0,1.3 if already else 1.,1.)
    before=unary_union([local,*[box(20+i,20,20.5+i,20.5)for i in range(100)]])
    regions=[]if already else[box(.9,.1,1.3,.9)]
    assert obligation_check(required,before,regions,already=already)==original(required,before,regions,already)

@pytest.mark.parametrize('offset,passed',[(.0000015,True),(.0000025,False)])
def test_existing_two_nanometre_boundary_gate_is_unchanged(offset,passed):
    before=box(0,0,1,1);required=box(.9,.1,1+offset,.9)
    if passed:assert obligation_check(required,before,[],already=True)==original(required,before,[],True)
    else:
        with pytest.raises(ValueError,match='EXTENT_MISSING'):obligation_check(required,before,[],already=True)
        with pytest.raises(ValueError,match='EXTENT_MISSING'):original(required,before,[],True)

def test_actual_positive_effect_stays_mandatory():
    required=box(.2,.2,.8,.8);before=box(0,0,1,1)
    with pytest.raises(ValueError,match='NO_EFFECT'):obligation_check(required,before,[required])
    with pytest.raises(ValueError,match='NO_EFFECT'):original(required,before,[required])

def test_empty_already_satisfied_extent_retains_original_fields():
    assert obligation_check(Polygon(),box(0,0,1,1),[],already=True)==original(Polygon(),box(0,0,1,1),[],True)
