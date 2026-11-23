"""Opt-in, local bulk-edge restoration; never a global opening/closing filter.

An identified bump/recess needs a source-backed smooth reference and a bounded
feature window. Straight supports and explicit native-centered circular void
supports are qualified separately; ambiguous flanks reject. A full feature may exceed the earlier corner-cut
depth cap under the owner's separate edge-restoration authorization. The shared
provisional maximum is 100 um, configurable independently of trace growth.
"""
from math import hypot, isfinite, atan2, degrees
from statistics import median
from hashlib import sha256
import shapely
from shapely.geometry import Polygon
from src.edge_restoration_settings import capture
from src.gerber_u05.finite_profile_union import polygonal


def fingerprint(g):
    return sha256(shapely.to_wkb(g, include_srid=True)).hexdigest()


def circular_flank_measurements(first, second, center, *, tolerance_mm=.004):
    """The existing exact source fit, without allocating its output geometry."""
    if (len(center)!=2 or not all(isfinite(v) for v in center) or
            not 0<tolerance_mm<=.004):
        raise ValueError('VALID_CIRCULAR_VOID_REFERENCE_REQUIRED')
    radii=[];spans=[];angles=[]
    for flank in (first,second):
        if len(flank)<3 or any(len(p)!=2 or not all(isfinite(v)for v in p)for p in flank):
            raise ValueError('TWO_SUPPORTED_CIRCULAR_FLANKS_REQUIRED')
        aa=sorted(degrees(atan2(p[1]-center[1],p[0]-center[0]))for p in flank)
        if aa[-1]-aa[0]>=180:
            # Native circular supports may cross atan2's branch cut. Unwrap
            # that coordinate discontinuity; it is not a geometric ambiguity.
            aa=sorted(v+360 if v<0 else v for v in aa)
        span=aa[-1]-aa[0]
        if not 10<=span<180:raise ValueError('CIRCULAR_FLANK_ANGULAR_SUPPORT_REQUIRED')
        angles.append((aa[0],aa[-1]));spans.append(span)
        radii.extend(hypot(p[0]-center[0],p[1]-center[1])for p in flank)
    if any(not (angles[0][1]<angles[1][0]+turn or angles[1][1]+turn<angles[0][0])
           for turn in (-360,0,360)):
        raise ValueError('DISJOINT_CIRCULAR_FLANKS_REQUIRED')
    radius=median(radii);residual=max(abs(v-radius)for v in radii)
    if radius<=0 or residual>tolerance_mm:raise ValueError('CIRCULAR_FLANKS_DISAGREE')
    return radius,residual,spans


def fit_circular_void_flanks(first, second, center, domain, *, tolerance_mm=.004):
    """Restore a circular void from two untouched source-bound arc supports.

    The center must be bound by the caller to an actual native circular pad.
    This is an explicit local reference, never a circular-pad removal rule.
    The 4 um maximum fit error accommodates the plotted hatch boundary; it is
    separate from native geometry error and does not relax clearance checks.
    """
    from shapely.geometry import Point, LineString
    if (len(center)!=2 or not all(isfinite(v)for v in center) or
            not 0<tolerance_mm<=.004 or domain.is_empty or not domain.is_valid):
        raise ValueError('VALID_CIRCULAR_VOID_REFERENCE_REQUIRED')
    radius,residual,spans=circular_flank_measurements(first,second,center,tolerance_mm=tolerance_mm)
    circle=Point(center).buffer(radius,quad_segs=512)
    reference=domain.difference(circle)
    return reference,LineString(circle.exterior.coords),dict(
        kind='CIRCULAR_VOID_FLANKS_AT_NATIVE_PAD_CENTER',center_mm=list(center),
        radius_mm=radius,first=[list(p)for p in first],second=[list(p)for p in second],angular_support_degrees=spans,
        maximum_radial_fit_error_mm=residual,fit_tolerance_mm=tolerance_mm,
        native_geometry_error_relaxed=False,reference_sha256=fingerprint(reference))


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
    return reference,dict(kind='TWO_COLLINEAR_SOURCE_FLANKS',first=[list(p)for p in first],second=[list(p)for p in second],
                          tolerance_mm=tolerance_mm,reference_sha256=fingerprint(reference))


def fit_circular_stroke_end_flanks(first, second, row, original_stroke, endpoint, domain):
    """Bind an outer circular edge to an actual round native line endpoint.

    A smaller pad inside a wide round end must not choose its circle centre.
    The original stroke remains fixed context; this grants only a reference.
    """
    from src.native_inventory import ERROR_MM
    from src.gerber_image import disk
    md=row.get('metadata',{});points=md.get('route_points_mm',[]);width=md.get('original_width_mm')
    aperture=md.get('aperture_family',[])
    if (row.get('kind')!='stroke' or md.get('source_kind')!='Line' or len(points)!=2 or endpoint not in (0,1) or
            type(width)not in(float,int) or not isfinite(width) or width<=0 or
            len(aperture)!=2 or aperture[0]!='C' or abs(aperture[1]-width)>1e-12):
        raise ValueError('AUTHENTIC_ROUND_NATIVE_LINE_ENDPOINT_REQUIRED')
    center=points[endpoint];cap=disk(center,width/2)
    if not original_stroke.buffer(ERROR_MM,quad_segs=128).covers(cap):
        raise ValueError('NATIVE_ROUND_ENDPOINT_GEOMETRY_MISMATCH')
    reference,edge,evidence=fit_circular_void_flanks(first,second,center,domain)
    if evidence['radius_mm']<=width/2+ERROR_MM:raise ValueError('REFERENCE_CIRCLE_ENTERS_FIXED_STROKE')
    evidence.update(kind='CIRCULAR_VOID_FLANKS_AT_NATIVE_STROKE_ENDPOINT',
        native_stroke_source_id=row['source_id'],native_stroke_ordinal=md.get('gerber_ordinal'),endpoint_index=endpoint,
        native_stroke_width_mm=width,native_stroke_sha256=fingerprint(original_stroke),
        native_endpoint_disk_sha256=fingerprint(cap),native_coordinate_error_mm=ERROR_MM,
        reference_authority='REFERENCE_ONLY_ORIGINAL_STROKE_REMAINS_FIXED')
    return reference,edge,evidence


def topology(g):
    if g.is_empty:return (0,0)
    if g.geom_type=='Polygon':return (1,len(g.interiors))
    if g.geom_type=='MultiPolygon':
        return (len(g.geoms),sum(len(p.interiors)for p in g.geoms))
    raise ValueError('POLYGONAL_MATERIAL_REQUIRED')


def shallow_trace_edge_check(protrusion, original_trace, source_path, smooth_edge,
                             source_width_mm, reference_evidence, *, policy=None):
    """Separate opt-in rule for owner-marked shallow straight-edge artifacts.

    This does not change the 10% area classifier. Two actual source flanks,
    less than half a trace width of depth, and the retained original path are
    required. Complete material/contacts/pins remain the caller's checks.
    """
    from src.native_inventory import ERROR_MM
    policy=capture()if policy is None else policy
    if (not reference_evidence or reference_evidence.get('kind')!='TWO_COLLINEAR_SOURCE_FLANKS' or
            type(source_width_mm)not in(float,int)or not isfinite(source_width_mm)or source_width_mm<=0 or
            source_path.geom_type!='LineString' or source_path.is_empty or not source_path.is_valid or
            any(g.is_empty or not g.is_valid for g in(protrusion,original_trace,smooth_edge))):
        raise ValueError('SOURCE_SUPPORTED_SHALLOW_TRACE_EDGE_REQUIRED')
    if not original_trace.buffer(ERROR_MM,quad_segs=128).covers(source_path):
        raise ValueError('ORIGINAL_TRACE_PATH_BINDING_REQUIRED')
    # Strict half-width bound, with the existing coordinate error held back as
    # a conservative margin. This reference band is never output as copper.
    maximum=min(policy.maximum_depth_mm,source_width_mm/2-ERROR_MM)
    failures=[]
    if maximum<=0 or not smooth_edge.buffer(maximum,quad_segs=128).covers(protrusion):
        failures.append('SHALLOW_TRACE_EDGE_DEPTH_LIMIT')
    remaining=original_trace.difference(protrusion)
    if not remaining.buffer(ERROR_MM,quad_segs=128).covers(source_path):
        failures.append('ORIGINAL_TRACE_PATH_LOST')
    return dict(passed=not failures,failures=failures,
                rule='OWNER_MARKED_SOURCE_SUPPORTED_SHALLOW_EDGE; SEPARATE_FROM_AREA_NOISE',
                source_width_mm=source_width_mm,maximum_normal_depth_mm=maximum,
                maximum_source_width_fraction=.5,original_path_preserved='ORIGINAL_TRACE_PATH_LOST'not in failures,
                reference_evidence=reference_evidence,policy=policy.resolved(),
                disposition='BOUNDED_PROPOSAL_REQUIRES_ASSEMBLED_CONTACT_AND_PIN_CHECKS')


def propose(material, reference, window, *, contacts=(), protected=(), foreign=(),
            gap_mm=.0401, reference_evidence=None, smooth_edge=None, policy=None, trim_only=False, removal_mask=None):
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
    if removal_mask is not None:
        if not trim_only or not removal_mask.is_valid or removal_mask.difference(window).area>1e-12:
            raise ValueError('EXPLICIT_REMOVAL_MASK_REQUIRES_BOUNDED_TRIM_ONLY')
        # An authenticated mask is subtraction by construction. Re-overlaying
        # curved difference boundaries as a target can manufacture round-off
        # "addition" slivers; it is not an addition constructor here.
        if fingerprint(reference)!=fingerprint(material.difference(removal_mask)):
            raise ValueError('EXACT_MASK_DIFFERENCE_REFERENCE_REQUIRED')
        removal=polygonal(material.intersection(window).intersection(removal_mask))
        addition=Polygon()
    else:
        removal=polygonal(material.intersection(window).difference(reference))
        addition=polygonal(reference.intersection(window).difference(material))
    if trim_only and not addition.is_empty:raise ValueError('TRIM_ONLY_ADDITION_FORBIDDEN')
    candidate=polygonal(material.difference(removal)) if trim_only else polygonal(material.difference(removal).union(addition))
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
        operation='TRIM_ONLY' if trim_only else 'BOUNDED_RESTORATION',
        removal_mask_sha256=fingerprint(removal_mask) if removal_mask is not None else None,
        clearance_searches=0 if trim_only else len(clearance),
        clearance_basis='SUBTRACTION_CANNOT_DECREASE_FOREIGN_COPPER_SEPARATION' if trim_only else 'POSITIVE_ADDITION_CLEARANCE',
        disposition='LOCAL_PROPOSAL_ONLY; assembled owner, pin and stage checks required')
