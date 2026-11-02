"""Explicit file-grid normalization and round-trip measurements."""
import math
from shapely import set_precision

GRID_MM=0.000001
POLYGON_TOLERANCE_MM=0.000002
CIRCLE_TOLERANCE_MM=0.000014


def quantize(shape):
    if shape.geom_type!='Polygon' or not shape.is_valid or shape.is_empty or shape.interiors:
        raise ValueError('UNSUPPORTED_TARGET_POLYGON')
    result=set_precision(shape,GRID_MM,mode='valid_output')
    if result.geom_type!='Polygon' or not result.is_valid or result.is_empty or result.interiors:
        raise ValueError('FILE_GRID_TOPOLOGY_NOT_SUPPORTED')
    area=shape.symmetric_difference(result).area
    area_bound=2*shape.length*GRID_MM+math.pi*GRID_MM**2
    if area>area_bound:
        raise ValueError('FILE_GRID_AREA_CHANGE_EXCEEDS_BOUND')
    return result,dict(grid_mm=GRID_MM,mode='valid_output',raw_boundary_hausdorff_mm=shape.boundary.hausdorff_distance(result.boundary),raw_symmetric_difference_mm2=area,area_change_bound_mm2=area_bound,vertices_before=len(shape.exterior.coords)-1,vertices_after=len(result.exterior.coords)-1,subgrid_collapse_visible=shape.hausdorff_distance(result)>POLYGON_TOLERANCE_MM)


def fidelity(reference,actual,*,native_circle=False):
    if actual.is_empty or not actual.is_valid:
        raise ValueError('REOPENED_GEOMETRY_INVALID')
    if native_circle:
        expected=reference;observed=actual;tol=CIRCLE_TOLERANCE_MM
    else:
        expected,_=quantize(reference)
        observed=set_precision(actual,GRID_MM,mode='valid_output');tol=POLYGON_TOLERANCE_MM
    distance=expected.hausdorff_distance(observed)
    area=expected.symmetric_difference(observed).area
    bound=2*expected.length*tol+math.pi*tol**2
    passed=distance<=tol and area<=bound
    result=dict(passed=passed,comparison='native analytic circle vs bounded source approximation' if native_circle else 'file-grid-normalized verified contour',hausdorff_mm=distance,symmetric_difference_mm2=area,tolerance_mm=tol,area_bound_mm2=bound)
    if not passed:raise ValueError('CONTOUR_FIDELITY_FAILED:'+str(result))
    return result
