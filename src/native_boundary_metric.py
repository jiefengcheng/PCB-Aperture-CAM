"""The existing discrete Hausdorff metric, with bounded indexing for large inputs."""
from shapely import get_num_coordinates,to_wkb
from .indexed_hausdorff import distance as indexed_distance

def distance(first,second):
 if int(get_num_coordinates(first))+int(get_num_coordinates(second))<=2048:
  return first.hausdorff_distance(second)
 if first.is_valid and second.is_valid and to_wkb(first)==to_wkb(second):
  return 0.
 # Full vertex coverage and native GEOS point/segment probes; no sampling or
 # simplification. Index/query budgets fail closed, never become a verdict.
 return indexed_distance(first,second)[0]
