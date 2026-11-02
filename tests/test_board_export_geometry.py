"""Board-only representation retains resolvable holes and rejects real islands."""
from shapely.geometry import Polygon,MultiPolygon,box
from shapely import from_wkb,set_precision
import pytest
from src.native_inventory import geometry
from src.pcb_data_abi import board_native as native
from src.pcb_data_abi.board_geometry import quantize,fidelity,bridge_contour,export_reference
from src.pcb_data_abi.crop import TEMPLATE
from src.pcb_data_abi.geometry import quantize as old_quantize

@pytest.mark.parametrize('holes',[[[(.5,.5),(.5,1),(1,1),(1,.5)]],[[(.5,.5),(.5,1),(1,1),(1,.5)],[(1.5,1.5),(1.5,2),(2,2),(2,1.5)]]])
def test_axial_cutins_preserve_holes_in_native_reopen(holes):
    q=Polygon([(0,0),(3,0),(3,3),(0,3)],holes=holes)
    with pytest.raises(ValueError,match='UNSUPPORTED_TARGET_POLYGON'):old_quantize(q)
    node,metrics,uid=native.polygon_node(q,native.edit_template(TEMPLATE),'source','a'*64)
    reopened=geometry(node,'gr_poly');assert len(reopened.interiors)==len(q.interiors)and fidelity(q,reopened)['passed']
    assert reopened.symmetric_difference(q).area==0
    with pytest.raises(ValueError,match='CONTOUR_FIDELITY_FAILED'):fidelity(q,Polygon(q.exterior))


def test_resolvable_hole_is_retained_in_reference_proof():
    q=Polygon([(0,0),(3,0),(3,3),(0,3)],holes=[[(1,1),(1,2),(2,2),(2,1)]])
    ref,proof=export_reference(q);assert len(ref.interiors)==1 and proof['resolvable_holes_preserved']==1 and proof['direct_normalization_equal']
    assert q.equals(ref)


def test_wrapped_single_grid_polygon_is_unwrapped_without_area_change():
    q=MultiPolygon([box(0,0,1,1)]);ref,proof=export_reference(q)
    assert ref.geom_type=='Polygon'and ref.equals(set_precision(q,.000001))and proof['raw_type']=='MultiPolygon'


def test_genuinely_separate_grid_components_still_reject():
    q=MultiPolygon([box(0,0,1,1),box(2,0,3,1)])
    with pytest.raises(ValueError,match='MULTIPART_NOT_SUPPORTED'):export_reference(q)


def test_plain_polygon_path_keeps_original_export_reference():
    q=box(.0000001,0,1,1);ref,proof=export_reference(q)
    assert ref is q and proof is None


def test_invalid_weak_polygon_is_not_silently_repaired():
    q=Polygon([(0,0),(2,2),(0,2),(2,0)])
    with pytest.raises(ValueError,match='UNSUPPORTED_TARGET_POLYGON'):export_reference(q)
