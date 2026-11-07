"""Check complete frozen gaps without overlaying unrelated board material.

Intersection distributes over union. Each window strictly contains its full
gap and expected walls, so clipping cannot manufacture a checked boundary.
No coordinates, copper, tolerances or existing gap predicates are changed.
"""
from shapely import STRtree, from_wkb
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from src import t02_shared_gaps as gaps
from src.stage_abi.store import canonical


def complete_parts(proof, parts, *, tolerance_mm=0.):
    parts = tuple(parts)
    tree = STRtree(parts)
    # Retain policy-wide predicates (including registered cross-slot matching)
    # separately from the complete local copper and boundary checks below.
    result = gaps.check(proof, Polygon(), tolerance_mm=tolerance_mm)
    checks, boundaries = [], []
    for row in proof['zones']:
        domain = gaps.corridor(row['axis'], row['left'], row['right'], row['lo'], row['hi'])
        witnesses = [domain]
        witnesses.extend(from_wkb(bytes.fromhex(w['contour_wkb_hex'])) for w in row['entry_walls'])
        bounds = [shape.bounds for shape in witnesses if not shape.is_empty]
        margin = max(row['gap_mm'], 4 * max(tolerance_mm, gaps.EPS))
        window = box(min(b[0] for b in bounds) - margin,
                     min(b[1] for b in bounds) - margin,
                     max(b[2] for b in bounds) + margin,
                     max(b[3] for b in bounds) + margin)
        if any(not window.contains(shape) for shape in witnesses):
            raise ValueError('SHARED_GAP_PROJECTION_DOMAIN_NOT_INTERIOR')
        clipped = [polygon for i in tree.query(window, predicate='intersects')
                   for polygon in gaps.surfaces(parts[int(i)].intersection(window))]
        # Tangencies introduced on the distant window edge have no copper
        # area and cannot affect a checked wall strictly inside the window.
        local = unary_union(clipped) if clipped else Polygon()
        # The original checker sees every contributor throughout the complete
        # slot, including both endpoints and every inherited wall segment.
        checked = gaps.complete(dict(proof, zones=[row]), local, tolerance_mm=tolerance_mm)
        checks.extend(checked['checks'])
        boundaries.extend(checked['boundaries'])
    if not proof['zones']:
        return gaps.complete(proof, Polygon(), tolerance_mm=tolerance_mm)
    if not result['passed']:
        raise ValueError('T02_SHARED_NEIGHBOR_UNIFORMITY_FAILED:' + canonical(
            dict(failed_slots=[], failed_boundaries=[])).decode())
    return dict(result, checks=checks, boundaries=boundaries)
