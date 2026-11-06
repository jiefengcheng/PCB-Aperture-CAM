"""A harness must not discard original partition vertices before native proof."""
import pytest
from shapely.geometry import Polygon
from src.gerber_u05 import pipeline as p,exporter as e
from src.gerber_u05.contours import partition,verify_partition
from src.gerber_u05.native_assembly import canonical_parent
from tools.qualify_t04_ladder_bundles import serialize_occurrence
from test_gerber_source import source_circle


def test_actual_parsed_partition_uses_original_parent_before_canonical_assembly(tmp_path,monkeypatch):
    shape=Polygon([(0,0),(1,0),(2,0),(2,2),(0,2)])
    def triangles(parent,bridge,*,grid_mm):
        pieces,proof=partition(parent,grid_mm=grid_mm)
        return [(piece,list(piece.exterior.coords)[:-1])for piece in pieces],proof
    monkeypatch.setattr(e,'serializable_contours',triangles)
    store=p.Store(tmp_path/'runtime');records=[];blocks=[]
    parents=serialize_occurrence(shape,'route',records,blocks,store)
    base,_=e.canonical_base(source_circle());parsed=e.parse((base+'\n'+''.join(blocks)+'M02*\n').encode())
    decoded=[]
    for obj in parsed.objects[-len(records):]:
        g,_=p.source_profile.object_geometry(obj);decoded.append(p.affine_scale(g,1,-1,origin=(0,0)))
    _,proof=e.weld_native_material(records,decoded,parents,grid_mm=.000001)
    assert proof['status']=='EXACT_PARSED_NATIVE_MATERIAL'
    # Reproduce the rejected harness target: removing a collinear source
    # vertex early makes a valid source-vertex partition appear to add one.
    with pytest.raises(ValueError,match='PARTITION_INTRODUCED_VERTEX'):
        verify_partition(canonical_parent(parents[0][1],grid_mm=.000001),decoded,grid_mm=.000001)
    with pytest.raises(ValueError):e.weld_native_material(records[:-1],decoded[:-1],parents,grid_mm=.000001)
