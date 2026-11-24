"""Retain positive original trace copper in emitted widening contours.

An original stroke's round cap may lie outside its finite side-profile cell.
Adjacent cells often cover it, but serialization/finishing must not rely on
that accidental coverage. This changes emitted contours, not immutable source
or the recorded group construction operands. Callers recheck final material.
"""
from shapely.ops import unary_union
from .finite_profile_union import polygonal


def preserve(core, body):
    from .pipeline import EPS
    from src.native_inventory import ERROR_MM
    for shape in (core,body):
        if shape.is_empty or not shape.is_valid or shape.geom_type not in ('Polygon','MultiPolygon'):
            raise ValueError('SOURCE_FLOOR_REQUIRES_VALID_FINITE_COPPER')
    missing=core.difference(body)
    if missing.area==0:return body,dict(changed=False,source_loss_before_mm2=0.,source_loss_after_mm2=0.)
    candidate=polygonal(unary_union([core,body]))
    if not candidate.is_valid or candidate.is_empty:
        raise ValueError('SOURCE_FLOOR_INVALID_UNION')
    remainder=core.difference(candidate);lost=remainder.area
    # Independent polygon overlays can subdivide a coincident chord a second
    # time. Use the existing native area AND coordinate error bounds together;
    # neither bound is changed, and a real finishing cut fails these checks.
    if lost>EPS or not remainder.difference(candidate.buffer(ERROR_MM,quad_segs=128)).is_empty:
        raise ValueError('SOURCE_FLOOR_POSITIVE_COPPER_STILL_MISSING')
    return candidate,dict(changed=True,source_loss_before_mm2=missing.area,
        source_loss_after_mm2=lost,optional_copper_removed_mm2=body.difference(candidate).area,
        native_area_error_mm2=EPS,native_coordinate_error_mm=ERROR_MM,
        operation='UNION_WITH_UNCHANGED_ORIGINAL_TRACE; NO_BUFFER_SNAP_OR_ROUNDING')
