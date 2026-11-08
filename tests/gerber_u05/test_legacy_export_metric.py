"""The reference exporter uses the same complete indexed metric as final export."""
import pytest
from shapely import get_num_coordinates,set_precision
from shapely.geometry import Point,box
from shapely.geometry.base import BaseGeometry
from src.gerber_u05 import pipeline as p,legacy_export as export
from src.pcb_data_abi.geometry import GRID_MM


@pytest.mark.parametrize('hole',[False,True])
def test_large_legacy_normalization_records_the_original_all_vertex_distance(tmp_path,monkeypatch,hole):
    shape=Point(.00000017,.00000029).buffer(1.00000013,quad_segs=600)
    if hole:shape=shape.difference(box(-.1,-.2,.2,.3))
    normalized=set_precision(shape,GRID_MM,mode='valid_output')
    assert get_num_coordinates(shape)>2048
    expected=shape.hausdorff_distance(normalized)
    native=BaseGeometry.hausdorff_distance
    def bounded_only(a,b):
        if int(get_num_coordinates(a))+int(get_num_coordinates(b))>2048:
            raise AssertionError('Large reference normalization must use the existing bounded index')
        return native(a,b)
    monkeypatch.setattr(BaseGeometry,'hausdorff_distance',bounded_only)
    records=[];blocks=[]
    export.append_regions(shape,'t05','synthetic',records,blocks,p.Store(tmp_path/'runtime'))
    assert records and blocks
    assert all(r['normalization']['qualified_hausdorff_mm']==pytest.approx(expected,abs=1e-15,rel=1e-13)for r in records)
    # A valid positive partition can encode a hole between simple faces.
    # Verify the actual file and exact material parent, not holes per face.
    from src.gerber_u05.native_assembly import weld
    reference,_=export.export_reference(normalized)
    body=b'%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.100000*%\n'+''.join(blocks).encode()+b'M02*\n'
    actual=[p.affine_scale(p.source_profile.object_geometry(o)[0],1,-1,origin=(0,0))for o in export.parse(body).objects]
    identity=('t05','synthetic',p.digest(p.to_wkb(reference)))
    material,proof=weld(records,actual,[(identity,reference)],grid_mm=GRID_MM)
    assert proof['parsed_regions']==len(records) and not proof['tolerance_allowance']
    assert len(material)==1 and len(material[0][1].interiors)==int(hole)
