"""Compare source-derived F.Cu geometry with a fresh KiCad Gerber plot.

The result is measurement evidence only. It does not establish board-wide
growth, electrical connectivity, or engineering/manufacturing acceptance.
"""
from __future__ import annotations

import math
from shapely import from_wkb
from shapely.geometry import LineString, box
from shapely.ops import unary_union

from .native_inventory import steps
from .native_reference import one
import sexpdata


def collinear_arc_fallback(source: bytes, item: dict, tolerance_mm: float = 1e-10):
    """Return a diagnostic round stroke only for exactly linear arc records.

    `native_inventory` deliberately leaves these records unsupported. This
    diagnostic hypothesis is retained separately and never mutates that
    inventory classification.
    """
    if item.get('kind') not in ('arc', 'gr_arc', 'fp_arc'):
        return None
    start, end = item['source_span']
    node = sexpdata.loads(source[start:end].decode('utf-8'))
    a = tuple(map(float, one(node, 'start')))
    m = tuple(map(float, one(node, 'mid')))
    b = tuple(map(float, one(node, 'end')))
    width = float(one(node, 'width', [0])[0])
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length <= 0 or not math.isfinite(width) or width <= 0:
        return None
    deviation = abs(dx * (a[1] - m[1]) - (a[0] - m[0]) * dy) / length
    if deviation > tolerance_mm:
        return None
    radius = width / 2
    shape = LineString([a, b]).buffer(radius, quad_segs=steps(radius),
                                      cap_style='round', join_style='round')
    return {
        'geometry': shape,
        'midpoint_deviation_mm': deviation,
        'width_mm': width,
        'centerline_length_mm': length,
        'fallback_kind': 'collinear_arc_as_round_stroke_diagnostic',
        'source_identity': item['id'],
    }


def board_copper_inventory(source: bytes, inventory: dict):
    """Return supported F.Cu geometries and explicit geometry omissions."""
    supported, unsupported = [], []
    for item in inventory['objects']:
        if 'F.Cu' not in item.get('layers', []):
            continue
        geometry_hash = item.get('geometry_sha256')
        if geometry_hash:
            supported.append((item, from_wkb(inventory['payloads'][geometry_hash])))
        elif item.get('unsupported_reason'):
            unsupported.append(item)
    fallbacks = []
    unresolved = []
    for item in unsupported:
        fallback = collinear_arc_fallback(source, item)
        if fallback is None:
            unresolved.append(item)
        else:
            fallbacks.append((item, fallback))
    return supported, unsupported, fallbacks, unresolved


def bounds_intersect(bounds, region):
    if not bounds:
        return False
    x0, y0, x1, y1 = bounds
    return not (x1 < region[0] or x0 > region[2]
                or y1 < region[1] or y0 > region[3])


def diagnostic_arc_roi(fallback: dict, context_widths: float = 2.0,
                       minimum_context_mm: float = 0.05):
    """Bound a diagnostic window around a fallback stroke, including context.

    The window is an axis-aligned square centered on the stroke bounds. Its
    half-size is the larger half-extent of the stroke plus a fixed context
    rule (two stroke widths, with a 0.05 mm floor). This is a measurement
    scope rule, not an acceptance tolerance.
    """
    geometry = fallback['geometry']
    x0, y0, x1, y1 = geometry.bounds
    width = float(fallback['width_mm'])
    if not math.isfinite(width) or width <= 0:
        raise ValueError('fallback width must be finite and positive')
    if not math.isfinite(context_widths) or context_widths < 0:
        raise ValueError('context_widths must be finite and nonnegative')
    if not math.isfinite(minimum_context_mm) or minimum_context_mm < 0:
        raise ValueError('minimum_context_mm must be finite and nonnegative')
    half_extent = max(x1 - x0, y1 - y0) / 2
    padding = max(context_widths * width, minimum_context_mm)
    center_x, center_y = (x0 + x1) / 2, (y0 + y1) / 2
    half_size = half_extent + padding
    return box(center_x - half_size, center_y - half_size,
               center_x + half_size, center_y + half_size)


def comparison_metrics(expected, plotted):
    """Compare two filled geometries; caller defines and retains scope."""
    intersection = expected.intersection(plotted)
    difference = expected.symmetric_difference(plotted)
    return {
        'status': 'MEASURED',
        'expected_area_mm2': expected.area,
        'plotted_area_mm2': plotted.area,
        'intersection_area_mm2': intersection.area,
        'expected_covered_fraction': intersection.area / expected.area if expected.area else None,
        'plotted_covered_fraction': intersection.area / plotted.area if plotted.area else None,
        'signed_area_delta_mm2': plotted.area - expected.area,
        'symmetric_difference_area_mm2': difference.area,
        'boundary_hausdorff_distance_mm': expected.boundary.hausdorff_distance(plotted.boundary),
    }


def local_scope(supported, unsupported, fallbacks, unresolved, center, radius_mm):
    """Enumerate every source geometry intersecting a bounded square ROI."""
    x, y = center
    region = box(x - radius_mm, y - radius_mm, x + radius_mm, y + radius_mm)
    supported_rows = [(item, geom) for item, geom in supported
                      if bounds_intersect(geom.bounds, region.bounds) and geom.intersects(region)]
    fallback_by_id = {item['id']: fallback for item, fallback in fallbacks}
    unsupported_rows = []
    for item in unsupported:
        bounds = (fallback_by_id[item['id']]['geometry'].bounds
                  if item['id'] in fallback_by_id else item.get('bounds_mm'))
        # If an unsupported record has no bound, retain it as unresolved in
        # every selected ROI rather than silently claiming local completeness.
        if bounds_intersect(bounds, region.bounds) or not bounds:
            unsupported_rows.append(item)
    unresolved_local = []
    for item in unresolved:
        if item.get('bounds_mm') and bounds_intersect(item['bounds_mm'], region.bounds):
            unresolved_local.append(item)
        elif not item.get('bounds_mm'):
            unresolved_local.append(item)
    fallback_rows = [(item, fallback_by_id[item['id']]) for item in unsupported_rows
                     if item['id'] in fallback_by_id]
    expected = unary_union([geom.intersection(region) for _, geom in supported_rows])
    fallback_expected = unary_union([expected, *[entry['geometry'].intersection(region)
                                                 for _, entry in fallback_rows]])
    return {
        'region': region,
        'region_bounds_mm': list(region.bounds),
        'supported_source_identities': sorted(item['id'] for item, _ in supported_rows),
        'unsupported_source_identities': sorted(item['id'] for item in unsupported_rows),
        'unresolved_unsupported_source_identities': sorted(item['id'] for item in unresolved_local),
        'supported_source_count': len(supported_rows),
        'unsupported_source_count': len(unsupported_rows),
        'unresolved_unsupported_source_count': len(unresolved_local),
        'fallback_diagnostics': [
            {k: v for k, v in entry.items() if k != 'geometry'}
            for _, entry in fallback_rows
        ],
        'expected_supported_geometry': expected,
        'expected_with_fallback_geometry': fallback_expected,
    }
