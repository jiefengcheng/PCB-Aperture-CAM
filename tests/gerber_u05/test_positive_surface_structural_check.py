import itertools
from shapely.geometry import box,GeometryCollection,Polygon
from shapely import to_wkb
from src.growth_void_encoding import filled_surface
from src.growth_void_remedy_v09 import surface_parts

def test_all_positive_parts_survive_independent_of_area_summation_order():
 pieces=[box(0,0,1,1),box(2,0,2.0001,.0001),Polygon([(3,0),(3.000001,0),(3,.000001)])]
 for order in itertools.permutations(pieces):
  raw=GeometryCollection(order);result=filled_surface(raw)
  assert sorted(to_wkb(g)for g in surface_parts(raw))==sorted(to_wkb(g)for g in surface_parts(result))
  assert all(g.area>0 for g in surface_parts(result))
  assert raw.symmetric_difference(result).area==0
