"""Coordinate-based grid reference; transient GEOS precision tags are not evidence."""
import math
from shapely import from_wkb,to_wkb,get_coordinates,set_precision
from src.stage_abi.store import digest
from src.native_boundary_metric import distance as boundary_distance
from src.pcb_data_abi.geometry import GRID_MM,POLYGON_TOLERANCE_MM

def normalize(shape):
 if shape.is_empty or not shape.is_valid or shape.geom_type not in('Polygon','MultiPolygon'):raise ValueError('NATIVE_GRID_VALID_POLYGON_REQUIRED')
 raw=from_wkb(to_wkb(shape));coords=get_coordinates(raw)
 if any(not math.isfinite(float(v))for row in coords for v in row):raise ValueError('NATIVE_GRID_NONFINITE')
 exact=all(abs(float(v)-round(float(v),6))<=4*max(math.ulp(float(v)),math.ulp(round(float(v),6)))for row in coords for v in row)
 q=set_precision(raw,GRID_MM,mode='pointwise'if exact else'valid_output')
 if q.is_empty or not q.is_valid or q.geom_type not in('Polygon','MultiPolygon'):raise ValueError('NATIVE_GRID_TOPOLOGY_UNSUPPORTED')
 area=raw.symmetric_difference(q).area;bound=2*raw.length*GRID_MM+math.pi*GRID_MM**2
 if area>bound:raise ValueError('NATIVE_GRID_AREA_CHANGE_EXCEEDS_BOUND')
 return q

def reference(shape):
 q=normalize(shape)
 if q.geom_type=='MultiPolygon'and len(q.geoms)==1:q=q.geoms[0]
 if q.geom_type!='Polygon':raise ValueError('NATIVE_REFERENCE_SINGLE_PART_REQUIRED')
 before=len(shape.interiors)if shape.geom_type=='Polygon'else sum(len(p.interiors)for p in shape.geoms)
 return q,dict(policy='Exact already-grid coordinates retained, including all valid minimum-grid positive surfaces and holes; otherwise one coordinate-based existing-grid normalization. Precision metadata ignored.',verified_geometry_sha256=digest(to_wkb(shape)),export_reference_sha256=digest(to_wkb(q)),grid_mm=GRID_MM,raw_type=shape.geom_type,holes_before=before,holes_after=len(q.interiors),native_boundary_tolerance_mm=POLYGON_TOLERANCE_MM,raw_geometry_hausdorff_mm=boundary_distance(shape,q),raw_symmetric_difference_mm2=shape.symmetric_difference(q).area,area_change_bound_mm2=2*shape.length*GRID_MM+math.pi*GRID_MM**2,verified_geometry_unchanged=True)

def fidelity(reference,actual,*,native_circle=False):
 if actual.is_empty or not actual.is_valid:raise ValueError('REOPENED_GEOMETRY_INVALID')
 expected=reference if native_circle else normalize(reference);observed=actual if native_circle else normalize(actual)
 from src.pcb_data_abi.geometry import CIRCLE_TOLERANCE_MM
 tol=CIRCLE_TOLERANCE_MM if native_circle else POLYGON_TOLERANCE_MM
 distance=boundary_distance(expected,observed);area=expected.symmetric_difference(observed).area;bound=2*expected.length*tol+math.pi*tol**2
 result=dict(passed=all(math.isfinite(v)for v in(distance,area,bound))and distance<=tol and area<=bound,comparison='native analytic circle vs bounded source approximation'if native_circle else'coordinate-bound file-grid contour including preserved holes',hausdorff_mm=distance,symmetric_difference_mm2=area,tolerance_mm=tol,area_bound_mm2=bound)
 if not result['passed']:raise ValueError('CONTOUR_FIDELITY_FAILED:'+str(result))
 return result
