"""Additive land-sized rolling-disc blends of source-qualified neck owners.

Unlike a trace-width-capped taper, closing fills concave circle/trace shoulders.
It never changes source operands or invents an attachment between separate owners.
"""
from src.clearance_policy import HARD_GAP_MM, CONSTRUCTION_GAP_MM, CONTACT_BUFFER_MM, LEGACY_CONSTRUCTION_MM, BARRIER_GAP_MM
import math
from shapely import get_precision, get_num_coordinates
from shapely.geometry import box
from src.indexed_polygon_distance import distance as exact_distance


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
    candidate_valid = candidate.is_valid
    if not candidate_valid or candidate.geom_type!='Polygon':failures.append('DISCONNECTED_OR_INVALID_CANDIDATE')
    from src.t05_owner_preservation import owner_is_covered
    covered=(geometry is not None and getattr(geometry,'exact_distance_reuse',False)
             and owner_is_covered(owner,candidate,candidate_valid))
    if not covered and difference(owner,candidate).area>1e-12:failures.append('OWNER_REMOVED')
    if difference(addition,window).area>1e-12:failures.append('OUTSIDE_WINDOW')
    assembled = union(owner,addition)
    # The caller commonly supplied this exact owner-plus-addition assembly.
    # Pointwise equality is only an empty symmetric-difference witness; it
    # does not waive owner, window, foreign clearance or pin checks. Matching
    # precision is required, and any other candidate takes the original path.
    identical = (candidate_valid
                 and get_precision(candidate) == get_precision(assembled)
                 and candidate.equals_exact(assembled, 0))
    if not identical and symmetric_difference(candidate,assembled).area>1e-12:failures.append('DELTA_MISMATCH')
    for sid,g in foreign:
        if (g.difference(owner).is_empty if geometry is None else geometry.difference_empty(g,owner)):
            pairs.append(dict(source_id=sid,disposition='EXACTLY_COVERED_BY_QUALIFIED_OWNER'));continue
        # Use the existing bounded exact-distance service only for foreign
        # surfaces large enough for its boundary structures to be retained.
        # Re-indexing many smaller obstacles costs more than their direct
        # measurement. 32768 matches that service's retention threshold.
        # Every original boundary and ordered distance witness is preserved;
        # its precision, threshold and ambiguous-tie fallbacks remain active.
        # Every foreign occurrence still emits its pair and compares the
        # current gap. Cache geometry/measurements, never a clearance verdict.
        distance=(None if addition.is_empty else exact_distance(addition,g)
                  if get_num_coordinates(g)>=32768 else geometry.exact_distance(addition,g)
                  if geometry is not None and getattr(geometry,'exact_distance_reuse',False) else addition.distance(g))
        passed=distance is None or distance+1e-12>=gap
        pairs.append(dict(source_id=sid,gap_mm=distance,passed=passed))
        if not passed:failures.append('FOREIGN_CLEARANCE:'+sid)
    return dict(passed=not failures,failures=failures,pairs=pairs)
