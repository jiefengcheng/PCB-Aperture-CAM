"""Opt-in, local bulk-edge restoration; never a global opening/closing filter.

An identified bump/recess needs a source-backed smooth reference and a bounded
feature window. This module supports straight flanks; ambiguous/curved flanks
reject rather than guessing. A full feature may exceed the earlier corner-cut
depth cap under the owner's separate edge-restoration authorization. The shared
provisional maximum is 100 um, configurable independently of trace growth.
"""
from math import hypot, isfinite
from hashlib import sha256
import shapely
from shapely.geometry import Polygon
from src.edge_restoration_settings import capture


def fingerprint(g):
    return sha256(shapely.to_wkb(g, include_srid=True)).hexdigest()


def fit_straight_flanks(first, second, inside_point, domain, *, tolerance_mm=1e-9):
    """Construct the material-side half-plane from two collinear support runs.

    Both flanks must have nonzero support and lie on the same fitted line. They
    are outside the feature being repaired, supplied by a source-bound caller.
    This checks support geometry, not whether an arbitrary void is dispensable.
    """
    if (not isfinite(tolerance_mm) or tolerance_mm <= 0 or
            domain.is_empty or not domain.is_valid):
        raise ValueError('VALID_BOUNDED_EDGE_DOMAIN_REQUIRED')
    a,b=first; c,d=second
    dx,dy=b[0]-a[0],b[1]-a[1];length=hypot(dx,dy)
    if length <= tolerance_mm or hypot(d[0]-c[0],d[1]-c[1]) <= tolerance_mm:
        raise ValueError('TWO_NONZERO_FLANKS_REQUIRED')
    tx,ty=dx/length,dy/length;nx,ny=-ty,tx
    offset=lambda p:(p[0]-a[0])*nx+(p[1]-a[1])*ny
    if max(abs(offset(c)),abs(offset(d))) > tolerance_mm:
        raise ValueError('AMBIGUOUS_OR_CURVED_EDGE')
    side=offset(inside_point)
    if abs(side) <= tolerance_mm:
        raise ValueError('MATERIAL_SIDE_REQUIRED')
    if side < 0:nx,ny=-nx,-ny
    xmin,ymin,xmax,ymax=domain.bounds
    corners=[(xmin,ymin),(xmin,ymax),(xmax,ymin),(xmax,ymax)]
    us=[(x-a[0])*tx+(y-a[1])*ty for x,y in corners]
    vs=[(x-a[0])*nx+(y-a[1])*ny for x,y in corners]
    lo,hi=min(us)-1,max(us)+1;top=max(vs)+1
    if top<=0:raise ValueError('DOMAIN_OUTSIDE_MATERIAL_HALF_PLANE')
    xy=lambda u,v:(a[0]+u*tx+v*nx,a[1]+u*ty+v*ny)
    reference=Polygon([xy(lo,0),xy(hi,0),xy(hi,top),xy(lo,top)]).intersection(domain)
    return reference,dict(kind='TWO_COLLINEAR_SOURCE_FLANKS',first=first,second=second,
                          tolerance_mm=tolerance_mm,reference_sha256=fingerprint(reference))


def topology(g):
    if g.is_empty:return (0,0)
    if g.geom_type=='Polygon':return (1,len(g.interiors))
    if g.geom_type=='MultiPolygon':
        return (len(g.geoms),sum(len(p.interiors)for p in g.geoms))
    raise ValueError('POLYGONAL_MATERIAL_REQUIRED')


def propose(material, reference, window, *, contacts=(), protected=(), foreign=(),
            gap_mm=.0401, reference_evidence=None, smooth_edge=None, policy=None):
    """Restore only the bounded feature, retaining explicit addition/removal.

    Base protected objects are not edited. Existing contacts must stay positive
    (or touching for original point/line contact), and component/hole topology
    must survive. Every addition is checked against complete foreign operands;
    deletion alone cannot establish acceptance of a newly grown trace.
    The caller still runs source/owner and pin checks on the assembled result.
    """
    policy = capture() if policy is None else policy
    if (not reference_evidence or not isfinite(gap_mm) or gap_mm<=0 or
            any(not g.is_valid for g in (material,reference,window))):
        raise ValueError('VALID_GEOMETRY_AND_REFERENCE_EVIDENCE_REQUIRED')
    if smooth_edge is None:
        # Only the fitted support line is eligible, never the window perimeter:
        # using that perimeter would hide a deep feature near a window edge.
        if reference_evidence.get('kind') != 'TWO_COLLINEAR_SOURCE_FLANKS':
            raise ValueError('SUPPORTED_SMOOTH_EDGE_REQUIRED')
        from shapely.geometry import LineString
        a,b=reference_evidence['first'];dx,dy=b[0]-a[0],b[1]-a[1]
        length=hypot(dx,dy);tx,ty=dx/length,dy/length
        xmin,ymin,xmax,ymax=window.bounds
        us=[(x-a[0])*tx+(y-a[1])*ty for x,y in
            [(xmin,ymin),(xmin,ymax),(xmax,ymin),(xmax,ymax)]]
        smooth_edge=LineString([(a[0]+u*tx,a[1]+u*ty)for u in (min(us)-1,max(us)+1)])
    if smooth_edge.is_empty or not smooth_edge.is_valid or smooth_edge.geom_type not in ('LineString','MultiLineString'):
        raise ValueError('SUPPORTED_SMOOTH_EDGE_REQUIRED')
    # Separate deltas make intentional subtraction auditable without demanding
    # equality to the old copper. No repeated erosion or global morphology.
    removal=material.intersection(window).difference(reference)
    addition=reference.intersection(window).difference(material)
    candidate=material.difference(removal).union(addition)
    failures=[]
    # Buffer containment checks every point of both deltas. A polygonal round
    # buffer is conservative at curved supports; no sampled-distance pass can
    # admit an over-limit feature. Reject a large feature, do not shave 100 um
    # repeatedly until it disappears. Callers bind this to the original source.
    depth_band=smooth_edge.buffer(policy.maximum_depth_mm,quad_segs=64)
    if not depth_band.covers(removal.union(addition)) and not (removal.is_empty and addition.is_empty):
        failures.append('EDGE_RESTORATION_DEPTH_LIMIT')
    if not candidate.is_valid or topology(candidate)!=topology(material):
        failures.append('CONNECTED_COMPONENT_OR_HOLE_TOPOLOGY_CHANGED')
    for sid,g in contacts:
        old=material.intersection(g);new=candidate.intersection(g)
        if (not old.is_empty and new.is_empty)or(old.area>0 and new.area<=0):
            failures.append('CONTACT_LOST:'+sid)
    for sid,g in protected:
        if removal.intersection(g).area>0 or addition.intersection(g).area>0:
            failures.append('PROTECTED_FEATURE_CHANGED:'+sid)
    clearance=[]
    if not addition.is_empty:
        for sid,g in foreign:
            if g.is_empty:continue
            distance=addition.distance(g);passed=distance+1e-12>=gap_mm
            clearance.append(dict(source_id=sid,gap_mm=distance,passed=passed))
            if not passed:failures.append('ADDED_COPPER_CLEARANCE:'+sid)
    return candidate,removal,addition,dict(
        passed=not failures,failures=failures,reference_evidence=reference_evidence,
        policy=policy.resolved(),smooth_edge_sha256=fingerprint(smooth_edge),
        before_sha256=fingerprint(material),after_sha256=fingerprint(candidate),
        window_sha256=fingerprint(window),reference_sha256=fingerprint(reference),
        removal_sha256=fingerprint(removal),addition_sha256=fingerprint(addition),
        removed_area_mm2=removal.area,added_area_mm2=addition.area,
        topology_before=list(topology(material)),topology_after=list(topology(candidate)),
        contacts_checked=len(contacts),protected_checked=len(protected),clearance=clearance,
        disposition='LOCAL_PROPOSAL_ONLY; assembled owner, pin and stage checks required')
