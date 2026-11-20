"""Additive land-sized rolling-disc blends of source-qualified neck owners.

Unlike a trace-width-capped taper, closing fills concave circle/trace shoulders.
It never changes source operands or invents an attachment between separate owners.
"""
from src.clearance_policy import HARD_GAP_MM, CONSTRUCTION_GAP_MM, CONTACT_BUFFER_MM, LEGACY_CONSTRUCTION_MM, BARRIER_GAP_MM
import math
from shapely.geometry import box


def spindle_addition(owner, radius, window, *, geometry=None):
    """Return the clipped rolling-disc addition before obstacle subtraction."""
    if geometry is None:
        from src.stage_abi.preparation import geometry_memo
        geometry=geometry_memo()
    if not math.isfinite(radius) or radius<=0:raise ValueError('POSITIVE_BLEND_RADIUS_REQUIRED')
    if owner.is_empty or not owner.is_valid or owner.geom_type!='Polygon':
        raise ValueError('ONE_CONNECTED_QUALIFIED_OWNER_REQUIRED')
    # Keep exact predecessor contributions. Only the closing's added copper is
    # clipped to the declared local window; never erode the original owner.
    if geometry is None:
        closed=owner.buffer(radius,quad_segs=64).buffer(-radius,quad_segs=64)
        return closed.difference(owner).intersection(window)

    def build():
        closed = geometry.buffer(geometry.buffer(owner, radius, quad_segs=64),
                                 -radius, quad_segs=64)
        return geometry.intersection(geometry.difference(closed, owner), window)

    # The nominal addition can be requested for both attachment need and a
    # full-radius proposal. Reuse the result before barrier/void subtraction:
    # those operands can change independently and are checked by the caller.
    return geometry.construct('spindle-addition', [owner, window], (radius, 64), build)


def spindle_blend(owner, radius, window, *, geometry=None):
    if geometry is None:
        from src.stage_abi.preparation import geometry_memo
        geometry = geometry_memo()
    addition = spindle_addition(owner, radius, window, geometry=geometry)
    candidate = owner.union(addition) if geometry is None else geometry.union(owner, addition)
    return candidate, addition


def check_spindle(owner, candidate, addition, window, foreign, gap=CONSTRUCTION_GAP_MM, *, geometry=None):
    if geometry is None:
        from src.stage_abi.preparation import geometry_memo
        geometry=geometry_memo()
    failures=[];pairs=[]
    difference=(lambda a,b:a.difference(b)) if geometry is None else geometry.difference
    union=(lambda a,b:a.union(b)) if geometry is None else geometry.union
    symmetric_difference=(lambda a,b:a.symmetric_difference(b)) if geometry is None else geometry.symmetric_difference
    if not candidate.is_valid or candidate.geom_type!='Polygon':failures.append('DISCONNECTED_OR_INVALID_CANDIDATE')
    if difference(owner,candidate).area>1e-12:failures.append('OWNER_REMOVED')
    if difference(addition,window).area>1e-12:failures.append('OUTSIDE_WINDOW')
    if symmetric_difference(candidate,union(owner,addition)).area>1e-12:failures.append('DELTA_MISMATCH')
    for sid,g in foreign:
        if (g.difference(owner).is_empty if geometry is None else geometry.difference_empty(g,owner)):
            pairs.append(dict(source_id=sid,disposition='EXACTLY_COVERED_BY_QUALIFIED_OWNER'));continue
        distance=None if addition.is_empty else addition.distance(g)
        passed=distance is None or distance+1e-12>=gap
        pairs.append(dict(source_id=sid,gap_mm=distance,passed=passed))
        if not passed:failures.append('FOREIGN_CLEARANCE:'+sid)
    return dict(passed=not failures,failures=failures,pairs=pairs)
