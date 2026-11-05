"""Keep every positive polygon exactly; ignore only zero-area overlay lines."""
import math
from shapely import to_wkb
from shapely.geometry import MultiPolygon
from .growth_void_remedy_v09 import surface_parts

def filled_surface(shape):
    surfaces=surface_parts(shape)
    if not surfaces:raise ValueError('FILLED_REMEDY_HAS_NO_SURFACE')
    result=surfaces[0]if len(surfaces)==1 else MultiPolygon(surfaces)
    rebuilt=surface_parts(result)
    exact=sorted(to_wkb(g)for g in surfaces)==sorted(to_wkb(g)for g in rebuilt)
    if not result.is_valid or result.is_empty or not exact or not all(math.isfinite(v)for v in(shape.area,result.area))or shape.symmetric_difference(result).area!=0:
        raise ValueError('FILLED_REMEDY_SURFACE_CHANGED:'+str(dict(raw_type=shape.geom_type,result_valid=result.is_valid,exact_positive_parts=exact,raw_area=shape.area,result_area=result.area,areal_difference=shape.symmetric_difference(result).area)))
    return result
