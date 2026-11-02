"""Crop-only bridge for holes that provably vanish on the existing file grid.

The verified T01 geometry is never edited. This provides an export reference only
when ordinary normalization of that original geometry has exactly the same result.
Resolvable holes and unsupported multipart targets remain rejected.
"""
import math
from shapely import set_precision,to_wkb
from shapely.geometry import Polygon
from src.stage_abi.store import digest
from .geometry import GRID_MM,quantize


def export_reference(shape):
    if shape.geom_type!='Polygon' or not shape.is_valid or shape.is_empty:
        raise ValueError('UNSUPPORTED_TARGET_POLYGON')
    if not shape.interiors:return shape,None
    holes=[Polygon(ring) for ring in shape.interiors]
    if any(not set_precision(h,GRID_MM,mode='valid_output').is_empty for h in holes):
        raise ValueError('UNSUPPORTED_RESOLVABLE_TARGET_HOLE')
    direct=set_precision(shape,GRID_MM,mode='valid_output')
    if direct.geom_type!='Polygon' or not direct.is_valid or direct.is_empty or direct.interiors:
        raise ValueError('FILE_GRID_TOPOLOGY_NOT_SUPPORTED')
    reference=Polygon(shape.exterior)
    normalized,metrics=quantize(reference) # unchanged shared normalization/policy
    if not normalized.equals(direct):raise ValueError('SUBGRID_HOLE_NORMALIZATION_NOT_EQUIVALENT')
    area=shape.symmetric_difference(direct).area;bound=2*shape.length*GRID_MM+math.pi*GRID_MM**2
    if area>bound:raise ValueError('FILE_GRID_AREA_CHANGE_EXCEEDS_BOUND')
    return reference,dict(policy='Existing 0.000001 mm valid_output grid; only holes independently collapsing to empty',
        verified_geometry_sha256=digest(to_wkb(shape,byte_order=1)),export_reference_sha256=digest(to_wkb(reference,byte_order=1)),
        normalized_geometry_sha256=digest(to_wkb(normalized,byte_order=1)),grid_mm=GRID_MM,
        collapsed_holes=len(holes),collapsed_hole_areas_mm2=[h.area for h in holes],
        direct_normalization_equal=True,raw_geometry_hausdorff_mm=shape.hausdorff_distance(direct),
        raw_symmetric_difference_mm2=area,area_change_bound_mm2=bound,
        ordinary_quantization=metrics,verified_geometry_unchanged=True)
