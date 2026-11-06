from pathlib import Path
import pytest
from shapely import from_wkb
from shapely.geometry import Polygon,box
from src.gerber_u05.contours import partition,verify_partition
from src.gerber_u05.compact_contours import coalesce,contours
from src.pcb_data_abi.board_geometry import bridge_contour
from src.gerber_u05.native_material import equality
from src.gerber_image import contour


@pytest.mark.parametrize('shape',[
 Polygon([(0,0),(.01,0),(.01,.01),(0,.01)],holes=[[(0,.005),(.002,.004),(.002,.006)]]),
 box(0,0,.01,.01).difference(box(.003,.003,.007,.007)),
 Polygon([(0,0),(.000001,0),(0,.000001)]),
])
def test_exact_compaction_preserves_all_material_and_holes(shape):
 pieces,old=partition(shape,grid_mm=1e-6);out,proof=coalesce(shape,pieces,grid_mm=1e-6)
 verify_partition(shape,out,grid_mm=1e-6)
 assert len(out)<=len(pieces)
 for g in out:
  points=list(g.exterior.coords);equality(g,contour(points),grid_mm=1e-6)
 assert proof['dropped_positive_parts']==0


def test_retained_211_triangle_case_becomes_small_exact_regions():
 shape=from_wkb((Path(__file__).with_name('fixtures')/'failed_reference.wkb').read_bytes())
 out,proof=contours(shape,bridge_contour,grid_mm=1e-6)
 assert proof['input_triangles']==211
 assert len(out)<20
 verify_partition(shape,[g for g,_ in out],grid_mm=1e-6)


def test_missing_triangle_is_rejected_before_coalescing():
 shape=box(0,0,.01,.01);pieces,_=partition(shape,grid_mm=1e-6)
 with pytest.raises(ValueError,match='INTEGER_AREA_CHANGED'):
  coalesce(shape,pieces[:-1],grid_mm=1e-6)


def test_many_local_addition_fragments_become_one_existing_owner_surface():
 from shapely import union_all
 from src.gerber_u05.export_absorption import compact_supported_region
 owner=box(0,0,1,.1);window=box(-.01,-.01,1.01,.2)
 addition=union_all([box(i/1200,.09,i/1200+.0003,.12)for i in range(1000)])
 region,support,mode=compact_supported_region(addition,owner,window)
 assert mode=='CHECKED_COMPLETE_LOCAL_JOINT_SURFACE'
 assert region.geom_type=='Polygon'
 assert support.difference(owner).area<=1e-12
 assert addition.difference(region).area<=1e-12
 assert owner.union(region).symmetric_difference(owner.union(addition)).area<=1e-12


def test_representation_budget_stops_instead_of_accepting_fragment_explosion():
 from src.gerber_u05.compact_contours import require_budget
 assert require_budget(4,1,8)['passed']
 with pytest.raises(ValueError,match='T05_LOCAL_REGION_BUDGET_EXCEEDED'):
  require_budget(1000,1,8)
