"""Source-only admission of short rectangular draws to the T02 land family.

A native draw need not be a trace: CAM files often draw a short distance with
a square aperture to describe a rectangular terminal. Only complete, exactly
rectangular, axis-aligned draws no longer than the smaller aperture dimension
qualify. Long fingers, ordinary traces and arcs retain their trace authority.
The native stroke/port metadata stays intact for preceding-stage checks.
"""
import math
from gerbonara import graphic_objects as go
from gerbonara.apertures import RectangleAperture
from shapely.geometry import box

FAMILY = 'source-short-rectangular-aperture-terminal/1'


def qualify(obj, complete, resolved):
    if not isinstance(obj, go.Line) or not isinstance(obj.aperture, RectangleAperture):
        return None
    if not obj.polarity_dark or not resolved.equals(complete):
        return None
    width, height = float(obj.aperture.w), float(obj.aperture.h)
    dx, dy = obj.x2 - obj.x1, obj.y2 - obj.y1
    length = math.hypot(dx, dy)
    if (not all(math.isfinite(v) and v > 0 for v in (width, height, length))
            or (dx != 0 and dy != 0) or length > min(width, height)
            or not resolved.equals(box(*resolved.bounds))):
        return None
    return dict(family=FAMILY, aperture_mm=[width, height],
                centerline_length_mm=length, axis='x' if dx else 'y',
                completeness='EXACT_UNCLIPPED_ORIGINAL_RECTANGULAR_SWEEP',
                authority='T02_SOURCE_LAND_BEFORE_T04; native joint metadata retained')
