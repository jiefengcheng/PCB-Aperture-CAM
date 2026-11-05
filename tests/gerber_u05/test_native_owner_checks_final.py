from shapely.geometry import box
from shapely.ops import unary_union
import pytest
from src.gerber_u05 import pipeline as p
from src import component_clearance as cc
from src.gerber_u05.native_component_checks_final import final_inventory,clearance

def test_actual_source_hole_cannot_disappear_even_when_no_final_hole_is_left():
 ring=box(0,0,2,2).difference(box(.8,.8,1.2,1.2));ctx=cc.bind(ring,'0'*64,dict(ring=ring));own=ctx.owner('ring')
 assert final_inventory(ring,{own:ring})['source_hole_survival']
 with pytest.raises(ValueError,match='SOURCE_HOLE_REMOVED'):final_inventory(ring,{own:box(0,0,2,2)})

def test_actual_distinct_source_components_cannot_become_a_bridge():
 a=box(0,0,1,1);b=box(1.1,0,2.1,1);ctx=cc.bind(unary_union([a,b]),'0'*64,dict(a=a,b=b));before={ctx.owner('a'):a,ctx.owner('b'):b}
 after=dict(before);after[ctx.owner('a')]=box(0,0,1.11,1)
 with pytest.raises(ValueError,match='FOREIGN_ORIGINAL_COMPONENT_CLEARANCE'):clearance(before,after)
 with pytest.raises(ValueError,match='COMPONENT_MERGED'):final_inventory(ctx.index.source,after)


def test_even_subresolution_original_source_hole_cannot_be_wholly_removed():
 from shapely.geometry import Polygon
 hole=Polygon([(0,0),(.000001,0),(0,.000001)]);outer=box(-1,-1,1,1);source=outer.difference(hole);ctx=cc.bind(source,'0'*64,{'original':source});own=ctx.owner('original')
 assert final_inventory(source,{own:source})['source_hole_survival']
 with pytest.raises(ValueError,match='SOURCE_HOLE_REMOVED'):final_inventory(source,{own:outer})
