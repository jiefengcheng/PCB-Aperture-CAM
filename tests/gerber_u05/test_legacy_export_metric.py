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
    assert sum(len(p.geometry(p.Store(tmp_path/'runtime'),r['geometry_ref']).interiors)for r in records)==int(hole)
