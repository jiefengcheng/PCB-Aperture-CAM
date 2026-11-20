"""Opt-in window-first blend subtraction for bounded retained evaluation.

Closing still uses the complete owner and the original buffer parameters. Only
the subsequent difference is localized, using the set identity
    (closed - owner) intersect window
      = (closed intersect window) - (owner intersect window).
Finite-precision overlays can differ, so bounded reference comparison and all
original checks on the actual candidate remain mandatory. No acceptance or
clearance verdict is cached here.
"""
import math

from shapely import get_num_coordinates, get_precision

from src.junction_spindle_blend import spindle_addition as reference_addition


def spindle_addition(owner, radius, window, *, geometry=None):
    if geometry is None:
        from src.stage_abi.preparation import geometry_memo
        geometry = geometry_memo()
    # Preserve the original validation/errors and unsupported geometry behavior.
    # Grid-snapping overlays do not necessarily obey the same finite arithmetic
    # rearrangement, and therefore retain the complete reference operation.
    # Only large owners justify changing operation order. Small-owner cuts
    # are cheap, and retain their established finite-precision boundary detail.
    # This is a complexity threshold, independent of source ID or acceptance.
    if (not math.isfinite(radius) or radius <= 0 or
            get_num_coordinates(owner) < 32768 or owner.is_empty or
            not owner.is_valid or owner.geom_type != 'Polygon' or
            window.is_empty or not window.is_valid or
            window.geom_type not in ('Polygon', 'MultiPolygon') or
            get_precision(owner) != 0 or get_precision(window) != 0):
        return reference_addition(owner, radius, window, geometry=geometry)

    buffer = (lambda g, r: g.buffer(r, quad_segs=64)) if geometry is None else (
        lambda g, r: geometry.buffer(g, r, quad_segs=64))
    intersection = (lambda a, b: a.intersection(b)) if geometry is None else geometry.intersection
    difference = (lambda a, b: a.difference(b)) if geometry is None else geometry.difference

    def build():
        # Do not clip before closing: remote copper can affect that operation.
        closed = buffer(buffer(owner, radius), -radius)
        # The existing bounded memo binds both complete operands, precision and
        # SRID. The owner/window clip is reusable across radii until either
        # operand changes, without adding a cache or increasing its budget.
        local_owner = intersection(owner, window)
        local_closed = intersection(closed, window)
        return difference(local_closed, local_owner)

    if geometry is None:
        return build()
    # Separate operation identity prevents reuse of an old-order result if both
    # implementations are ever exercised within the same execution context.
    return geometry.construct('windowed-spindle-addition', [owner, window],
                              (radius, 64), build)
