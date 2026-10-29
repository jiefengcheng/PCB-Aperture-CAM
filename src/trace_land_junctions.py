"""Bounded additive T05 land/trace tapers; no routing, land edits or ABI adapter.

Width is checked at declared cross-sections and by a connected eroded witness.
Foreign copper is never exempted by component/net labels. The caller binds
source identities, original contacts, current geometry and the writable window.
"""
from dataclasses import dataclass, asdict
import math
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union


@dataclass(frozen=True)
class JunctionContract:
    construction_gap_mm: float = .02010
    hard_gap_mm: float = .02000
    max_flare_ratio: float = 1.5
    taper_length_widths: float = 2.0
    inside_land_widths: float = .5
    stations: int = 17
    search_steps: int = 12
    geometry_error_mm: float = .00001
    area_epsilon_mm2: float = 1e-12
    comparison_epsilon_mm: float = 1e-12
    robust_erosion_width_fraction: float = .45


def _width(width):
    if not math.isfinite(width) or width <= 0:
        raise ValueError('VERIFIED_POSITIVE_TRACE_WIDTH_REQUIRED')


def _point(line, distance):
    p = line.interpolate(distance)
    return p.x, p.y


def _tangent(line, distance):
    h = min(.0001, line.length / 4096)
    a, b = _point(line, max(0., distance-h)), _point(line, min(line.length, distance+h))
    dx, dy = b[0]-a[0], b[1]-a[1]
    length = math.hypot(dx, dy)
    if not length:
        raise ValueError('UNRESOLVED_LOCAL_ROUTE_TANGENT')
    return dx/length, dy/length


def propose_taper(route_toward_land, trace, land, width, *, alpha=1., contract=JunctionContract()):
    """Follow the current fixed route into a land; return bounded taper geometry.

    route_toward_land terminates inside the qualified land. The final contiguous
    interior interval defines the entry. Original owner geometry is never cut.
    """
    _width(width)
    if contract != JunctionContract():
        raise ValueError('JUNCTION_CONTRACT_CHANGED')
    if type(alpha) not in (float, int) or not math.isfinite(alpha) or not 0 < alpha <= 1:
        raise ValueError('FINITE_BOUNDED_FLARE_REQUIRED')
    line = LineString(route_toward_land)
    if line.length <= width or not line.is_valid or not land.covers(Point(line.coords[-1])):
        raise ValueError('SOURCE_ROUTE_END_INSIDE_LAND_REQUIRED')
    inside = line.intersection(land)
    parts = [inside] if inside.geom_type == 'LineString' else list(getattr(inside, 'geoms', ()))
    intervals = []
    for part in parts:
        if part.geom_type == 'LineString' and part.distance(Point(line.coords[-1])) <= 1e-10:
            intervals.append(min(line.project(Point(p)) for p in part.coords))
    if not intervals:
        raise ValueError('CONTIGUOUS_ROUTE_LAND_ENTRY_NOT_ESTABLISHED')
    entry = max(intervals)
    start = max(0., entry-contract.taper_length_widths*width)
    stop = min(line.length, entry+contract.inside_land_widths*width)
    if entry-start < width*.5 or stop-entry < width*.1:
        raise ValueError('INSUFFICIENT_SOURCE_ROUTE_FOR_BOUNDED_TAPER')
    samples = []
    left, right = [], []
    for i in range(contract.stations):
        s = start+(stop-start)*i/(contract.stations-1)
        p, tangent = _point(line, s), _tangent(line, s)
        u = min(1., max(0., (s-start)/(entry-start)))
        smooth = u*u*(3-2*u)
        local_width = width*(1+alpha*(contract.max_flare_ratio-1)*smooth)
        normal = (-tangent[1], tangent[0])
        left.append((p[0]+normal[0]*local_width/2, p[1]+normal[1]*local_width/2))
        right.append((p[0]-normal[0]*local_width/2, p[1]-normal[1]*local_width/2))
        samples.append(dict(arclength_mm=s, point_mm=p, tangent=tangent,
                            requested_width_mm=local_width))
    patch = Polygon(left+list(reversed(right)))
    if not patch.is_valid or patch.is_empty:
        raise ValueError('INVALID_CURVED_TAPER')
    # The window is independently bounded by the authorized route interval and
    # maximum half-width, rather than inferred from the submitted candidate.
    witness = LineString([r['point_mm'] for r in samples])
    window = witness.buffer(contract.max_flare_ratio*width/2+contract.geometry_error_mm,
                            quad_segs=64)
    return dict(patch=patch, window=window, stations=samples, width_mm=width,
                entry_arclength_mm=entry, start_arclength_mm=start,
                stop_arclength_mm=stop, witness=witness, alpha=alpha)


def _station_width(geometry, station, reach):
    p, t = station['point_mm'], station['tangent']
    n = -t[1], t[0]
    cross = LineString([(p[0]-n[0]*reach,p[1]-n[1]*reach),
                        (p[0]+n[0]*reach,p[1]+n[1]*reach)])
    hit = geometry.intersection(cross)
    parts = [hit] if hit.geom_type == 'LineString' else list(getattr(hit,'geoms',()))
    widths = [g.length for g in parts if g.geom_type=='LineString' and g.distance(Point(p))<=1e-10]
    return max(widths, default=0.)


def verify_taper(proposal, trace, land, foreign_copper, *, contract=JunctionContract()):
    """Check a proposed local patch; no constructor or caller evaluator fallback."""
    if contract != JunctionContract():
        raise ValueError('JUNCTION_CONTRACT_CHANGED')
    width = proposal['width_mm']; _width(width)
    patch, window = proposal['patch'], proposal['window']
    reasons=[];pairs=[];stations=[]
    if patch.is_empty or not patch.is_valid:
        return dict(passed=False,failures=['INVALID_PATCH'],pairs=[],stations=[])
    if patch.difference(window).area>contract.area_epsilon_mm2:reasons.append('OUTSIDE_WRITABLE_WINDOW')
    if patch.intersection(trace).area<=contract.area_epsilon_mm2:reasons.append('DISCONNECTED_FROM_TRACE')
    if patch.intersection(land).area<=contract.area_epsilon_mm2:reasons.append('DISCONNECTED_FROM_LAND')
    owner=trace.union(land);candidate=owner.union(patch);addition=patch.difference(owner)
    if (trace.difference(candidate).area>contract.area_epsilon_mm2
            or land.difference(candidate).area>contract.area_epsilon_mm2):
        reasons.append('PROTECTED_OWNER_COPPER_REMOVED')
    for row in foreign_copper:
        geom=row['geometry']
        # Exact coverage by the two explicitly qualified owner operands is a
        # source-bound internal primitive witness, never a component exemption.
        if geom.difference(owner).is_empty:
            pairs.append(dict(source_id=row['id'],disposition='FULLY_COVERED_BY_QUALIFIED_OWNER_UNION'))
            continue
        gap=None if addition.is_empty else addition.distance(geom)
        failed=gap is not None and gap+contract.comparison_epsilon_mm<contract.construction_gap_mm
        if failed:reasons.append('FOREIGN_COPPER_CLEARANCE:'+row['id'])
        pairs.append(dict(source_id=row['id'],added_surface_gap_mm=gap,passed=not failed))
    for station in proposal['stations']:
        measured=_station_width(candidate,station,max(width*4,contract.construction_gap_mm*2))
        required=max(0.,width-2*contract.geometry_error_mm)
        passed=measured+contract.comparison_epsilon_mm>=required
        if not passed:reasons.append('THIN_NECK_AT_DECLARED_STATION')
        stations.append(dict(point_mm=station['point_mm'],measured_width_mm=measured,
                             required_width_mm=required,passed=passed))
    eroded=candidate.buffer(-contract.robust_erosion_width_fraction*width,quad_segs=64)
    robust=not eroded.is_empty and eroded.covers(proposal['witness'])
    if not robust:reasons.append('ROBUST_CONNECTED_NECK_NOT_ESTABLISHED')
    return dict(passed=not reasons,failures=sorted(set(reasons)),pairs=pairs,stations=stations,
                robust_witness_passed=robust,added_area_mm2=addition.area,
                source_width_mm=width,contract=asdict(contract),
                scope='Declared station widths plus eroded route witness; not native/electrical or continuous differential-width proof')


def fit_taper(route_toward_land, trace, land, width, foreign_copper, *, contract=JunctionContract()):
    attempts=[];best=None;lo,hi=0.,1.
    for i in range(contract.search_steps+1):
        alpha=1. if i==0 else (lo+hi)/2
        try:
            proposal=propose_taper(route_toward_land,trace,land,width,alpha=alpha,contract=contract)
            check=verify_taper(proposal,trace,land,foreign_copper,contract=contract)
        except ValueError as e:
            attempts.append(dict(alpha=alpha,passed=False,error=str(e)));hi=alpha
            continue
        attempts.append(dict(alpha=alpha,passed=check['passed'],failures=check['failures']))
        if check['passed']:
            best=proposal,check;lo=alpha
            if alpha==1.:break
        else:hi=alpha
    return best,attempts
