"""Additive land-sized rolling-disc blends of source-qualified neck owners.

Unlike a trace-width-capped taper, closing fills concave circle/trace shoulders.
It never changes source operands or invents an attachment between separate owners.
"""
import math
from shapely.geometry import box


def spindle_blend(owner, radius, window):
    if not math.isfinite(radius) or radius<=0:raise ValueError('POSITIVE_BLEND_RADIUS_REQUIRED')
    if owner.is_empty or not owner.is_valid or owner.geom_type!='Polygon':
        raise ValueError('ONE_CONNECTED_QUALIFIED_OWNER_REQUIRED')
    # Keep exact predecessor contributions. Only the closing's added copper is
    # clipped to the declared local window; never erode the original owner.
    closed=owner.buffer(radius,quad_segs=64).buffer(-radius,quad_segs=64)
    addition=closed.difference(owner).intersection(window)
    return owner.union(addition),addition


def check_spindle(owner, candidate, addition, window, foreign, gap=.0201):
    failures=[];pairs=[]
    if not candidate.is_valid or candidate.geom_type!='Polygon':failures.append('DISCONNECTED_OR_INVALID_CANDIDATE')
    if owner.difference(candidate).area>1e-12:failures.append('OWNER_REMOVED')
    if addition.difference(window).area>1e-12:failures.append('OUTSIDE_WINDOW')
    if candidate.symmetric_difference(owner.union(addition)).area>1e-12:failures.append('DELTA_MISMATCH')
    for sid,g in foreign:
        if g.difference(owner).is_empty:
            pairs.append(dict(source_id=sid,disposition='EXACTLY_COVERED_BY_QUALIFIED_OWNER'));continue
        distance=None if addition.is_empty else addition.distance(g)
        passed=distance is None or distance+1e-12>=gap
        pairs.append(dict(source_id=sid,gap_mm=distance,passed=passed))
        if not passed:failures.append('FOREIGN_CLEARANCE:'+sid)
    return dict(passed=not failures,failures=failures,pairs=pairs)
