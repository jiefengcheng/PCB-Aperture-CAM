from pathlib import Path
import pytest
from shapely import from_wkb,to_wkb
from shapely.geometry import Polygon,box
from src.gerber_u05.contours import contours,verify_partition
from src.gerber_u05.native_material import equality
from src.gerber_u05.exact_cut_in import bridge
from src.pcb_data_abi.board_geometry import bridge_contour
from src.gerber_image import contour
from src.native_boundary_metric import distance

@pytest.mark.parametrize('index',[1,2,3])
def test_actual_tolerated_cut_in_material_change_gets_an_exact_encoding(index):
 shape=from_wkb((Path(__file__).with_name('fixtures')/'exact_cut_in'/('target_'+str(index)+'.wkb')).read_bytes());old=bridge_contour(shape);old_shape=contour(old+[old[0]])
 with pytest.raises(ValueError,match='NATIVE_INTEGER_MATERIAL_CHANGED'):equality(shape,old_shape,grid_mm=1e-6)
 pieces,proof=contours(shape,bridge_contour,grid_mm=1e-6)
 if proof['status']=='EXACT_INTEGER_GRID_PARTITION':verify_partition(shape,[g for g,_ in pieces],grid_mm=1e-6)
 else:
  assert proof['status']=='EXACT_AXIAL_CUT_IN_ENCODING'
  for geometry,points in pieces:equality(shape,contour(points+[points[0]]),grid_mm=1e-6)

def test_integer_material_keeps_minimum_triangle_and_rejects_one_grid_change():
 tiny=Polygon([(0,0),(.000001,0),(0,.000001)]);assert equality(tiny,tiny,grid_mm=1e-6)['status']=='EXACT_NATIVE_INTEGER_MATERIAL'
 with pytest.raises(ValueError,match='NATIVE_INTEGER_MATERIAL_CHANGED'):equality(tiny,Polygon([(0,0),(.000002,0),(0,.000001)]),grid_mm=1e-6)

def test_exact_collinear_subdivision_is_not_a_material_change():
 shape=box(0,0,1,1);sub=Polygon([(0,0),(.5,0),(1,0),(1,1),(0,1)]);assert equality(shape,sub,grid_mm=1e-6)['status']=='EXACT_NATIVE_INTEGER_MATERIAL'
