"""Exact-coordinate indexed distance for the new original-component profile.

Every polygon boundary is retained. GEOS indexed facet distance is exact in the
same floating geometry kernel. Original GEOS traversal remains authoritative at
both unchanged clearance comparison boundaries, including their 1e-12 epsilon.
Legacy primitive-distance/report compatibility code is unchanged.
"""
import math,hashlib
from collections import OrderedDict
from shapely import get_num_coordinates,get_precision
from src import indexed_polygon_distance as legacy
from src.clearance_policy import HARD_GAP_MM,CONSTRUCTION_GAP_MM
VALUES=OrderedDict();MAX_ENTRIES=4096

def distance(left,right):
 key=(legacy.signature(left),legacy.signature(right),float(get_precision(left)),float(get_precision(right)))
 if key in VALUES:
  value,proof=VALUES[key]
  if type(value)is not float or not math.isfinite(value)or hashlib.sha256((repr(key)+value.hex()).encode()).hexdigest()!=proof:raise ValueError('COMPONENT_DISTANCE_CERTIFICATE_CHANGED')
  VALUES.move_to_end(key);return value
 if(left.geom_type not in('Polygon','MultiPolygon')or right.geom_type not in('Polygon','MultiPolygon')or left.is_empty or right.is_empty or max(int(get_num_coordinates(left)),int(get_num_coordinates(right)))<1024 or get_precision(left)!=0 or get_precision(right)!=0):
  value=float(left.distance(right))
 elif left.intersects(right):value=float(left.distance(right))
 else:
  with legacy.CONTROL:
   if legacy.ENGINE is None:legacy.ENGINE=legacy.Engine()
   value=float(legacy.ENGINE.measure(left,right))
  if not math.isfinite(value)or value<0:raise ValueError('INDEXED_ORIGINAL_COMPONENT_DISTANCE_INVALID')
  if value<=1e-12 or any(abs(value-t)<=4e-12 for t in(HARD_GAP_MM,CONSTRUCTION_GAP_MM)):value=legacy.legacy_value(left,right)
 if not math.isfinite(value)or value<0:raise ValueError('ORIGINAL_COMPONENT_DISTANCE_INVALID')
 if len(VALUES)>=MAX_ENTRIES:VALUES.popitem(last=False)
 VALUES[key]=(value,hashlib.sha256((repr(key)+value.hex()).encode()).hexdigest())
 return value
