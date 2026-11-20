"""Compile complete source-neighbour bounds once, before strip allocation.

The existing source scene supplies immutable copper bounds and bulk roles.
Only broad-phase discovery uses an index; the constructor receives scalar
inequalities. No trial contour, normal-section probing or clearance recheck is
performed. Conservative bounds that cannot express a junction stay residual.
"""
import math
from collections import OrderedDict
from shapely import STRtree,get_coordinates
from shapely.geometry import box
from .limiting_math import GUARD, MARGIN
from src.native_inventory import ERROR_MM


def chord_bounds(points, width, axis, first, last):
    """Support bounds of source chord tubes in a longitudinal slab.

    Clipping the CENTERLINE to the slab expanded by its tube radius cannot
    omit copper in the slab. No candidate geometry or line/polygon overlay is
    involved. The native approximation error is included in the tube radius.
    """
    ux, uy = axis;nx, ny = -uy, ux;radius = width/2+2*ERROR_MM
    low, high = first-radius, last+radius;normal = []
    for a, b in zip(points, points[1:]):
        ta, tb = a[0]*ux+a[1]*uy, b[0]*ux+b[1]*uy
        if max(ta, tb) < low or min(ta, tb) > high:continue
        if abs(tb-ta) < 1e-15:f0, f1 = 0., 1.
        else:
            f0, f1 = sorted(((low-ta)/(tb-ta), (high-ta)/(tb-ta)))
            f0, f1 = max(0., f0), min(1., f1)
        if f0 > f1:continue
        for f in (f0, f1):
            x, y = a[0]+f*(b[0]-a[0]), a[1]+f*(b[1]-a[1])
            normal.append(x*nx+y*ny)
    return None if not normal else (min(normal)-radius, max(normal)+radius)


class SourceBoundaries:
    def __init__(self, current, roles, rows=None, mutable_sources=(), *, protected_domains=(), reserve_mutable_growth=True,defer_close_sources=False):
        self.ids = sorted(s for s, g in current.items() if not g.is_empty)
        self.bounds = [current[s].bounds for s in self.ids]
        self.tree = STRtree([box(*b) for b in self.bounds])
        self.roles = set(roles)
        self.rows = rows or {}
        self.mutable_sources = set(mutable_sources)
        self.reserve_mutable_growth = reserve_mutable_growth
        self.defer_close_sources = defer_close_sources
        self.current=current
        self.protected_domains=list(protected_domains)
        self.queries = 0
        self.frames = OrderedDict()

    def for_band(self, runs, band, settings):
        from .group_profile import outline
        key = (tuple(band['axis']), band['first'], band['last'], tuple(band['members']),
               settings.maximum_factor, settings.maximum_total_width_increase_mm)
        if key in self.frames:
            self.frames.move_to_end(key)
            return self.frames[key]
        ux, uy = band['axis']; nx, ny = -uy, ux
        members = [runs[i] for i in band['members']]
        used = {s for r in members for s in r['source_ids']}
        lanes = {}
        for r in members:
            mid = [(a+b)/2 for a, b in zip(r['start'], r['end'])]
            center = mid[0]*nx+mid[1]*ny
            w = r['width_mm'];cap = min(w*settings.maximum_factor, w+settings.maximum_total_width_increase_mm)-w
            lanes[r['run_id']] = (center-w/2, center+w/2, cap)
        reach = .025+settings.maximum_total_width_increase_mm
        required = GUARD+2*MARGIN
        lo = min(v[0] for v in lanes.values())-2*reach-required
        hi = max(v[1] for v in lanes.values())+2*reach+required
        corners = outline(band['axis'], band['first']-required-reach, band['last']+required+reach, lo, hi)
        query = box(min(p[0] for p in corners), min(p[1] for p in corners),
                    max(p[0] for p in corners), max(p[1] for p in corners))
        limits = {r: dict(left=cap+reach, right=cap+reach) for r, (_, _, cap) in lanes.items()}
        witnesses = [];bulk = [];unresolved = []
        fixed_intervals={}
        for r in members:
            if any(s in self.mutable_sources for s in r['source_ids']):continue
            if not all(s in self.current for s in r['source_ids']):continue # obstacle-only helper API
            values=[float(x*nx+y*ny) for s in r['source_ids']for x,y in get_coordinates(self.current[s])]
            fixed_intervals[r['run_id']]=[min(values),max(values)]
        for label,domain in self.protected_domains:
            x0,y0,x1,y1=domain.bounds
            ts=[x*ux+y*uy for x in(x0,x1)for y in(y0,y1)]
            ns=[x*nx+y*ny for x in(x0,x1)for y in(y0,y1)]
            if max(ts)<band['first']-required or min(ts)>band['last']+required:continue
            for r,(left,right,cap)in lanes.items():
                if max(ns)+required>=left-reach and min(ns)-required<=right+reach:
                    unresolved.append(dict(run_id=r,source_id=label,
                        longitudinal_interval_mm=[min(ts)-required,max(ts)+required],
                        reason='PROTECTED_PIN_DOMAIN_DEFERRED_BEFORE_CONSTRUCTION'))
        self.queries += 1
        for i in sorted(map(int, self.tree.query(query))):
            sid = self.ids[i]
            if sid in used:continue
            x0, y0, x1, y1 = self.bounds[i]
            pts = [(x, y) for x in (x0, x1) for y in (y0, y1)]
            ts = [x*ux+y*uy for x, y in pts]
            ns = [x*nx+y*ny for x, y in pts]
            reservation = reach if self.reserve_mutable_growth and sid in self.mutable_sources else 0.
            if max(ts) < band['first']-required-reservation or min(ts) > band['last']+required+reservation:continue
            if max(ns) < lo or min(ns) > hi:continue
            if sid in self.roles:
                bulk.append(sid);continue
            row = self.rows.get(sid, {});md = row.get('metadata', {})
            support = None
            if (row.get('kind') == 'stroke' and row.get('geometry_ref') == row.get('original_ref')
                    and md.get('route_points_mm') and md.get('source_port_width_mm', 0) > 0):
                support = chord_bounds(md['route_points_mm'], md['source_port_width_mm'],
                                       band['axis'], band['first']-required-reservation, band['last']+required+reservation)
                if support is None:continue
                ns = list(support)
            if reservation:
                ns = [min(ns)-reservation, max(ns)+reservation]
                ts = [min(ts)-reservation, max(ts)+reservation]
            witness = dict(source_id=sid, bounds_mm=list(self.bounds[i]),
                           normal_interval_mm=[min(ns), max(ns)],
                           longitudinal_interval_mm=[min(ts), max(ts)],
                           support='SOURCE_CHORD_TUBE_PLUS_2_NATIVE_ERRORS' if support else 'WHOLE_OBJECT_BOUNDS',
                           other_mutable_reservation_mm=reservation)
            witnesses.append(witness)
            for r, (left, right, _) in lanes.items():
                # An originally close neighbour is a local joint obligation,
                # not a negative face cap over the whole maximal member.
                # Compile its longitudinal support before allocating strips.
                close=(max(ns)<=left and left-max(ns)<required)or(min(ns)>=right and min(ns)-right<required)
                if close and self.defer_close_sources:
                    span=None
                    if support is not None:
                        transverse=chord_bounds(md['route_points_mm'],md['source_port_width_mm'],
                                                [nx,ny],left-required,right+required)
                        if transverse is not None:span=[-transverse[1]-reservation,-transverse[0]+reservation]
                    unresolved.append(dict(run_id=r,source_id=sid,longitudinal_interval_mm=span or [min(ts)-required,max(ts)+required],
                        reason='CLOSE_SOURCE_NEIGHBOUR_NEEDS_LOCAL_JOINT_SCHEME'))
                    continue
                if max(ns) <= left:
                    limits[r]['left'] = min(limits[r]['left'], left-max(ns)-required)
                elif min(ns) >= right:
                    limits[r]['right'] = min(limits[r]['right'], min(ns)-right-required)
                else:
                    span = None
                    if support is not None:
                        transverse = chord_bounds(md['route_points_mm'], md['source_port_width_mm'],
                                                  [nx, ny], left-required, right+required)
                        if transverse is not None:span = [-transverse[1]-reservation, -transverse[0]+reservation]
                    unresolved.append(dict(run_id=r, source_id=sid,
                                           longitudinal_interval_mm=span or [min(ts)-required, max(ts)+required],
                                           reason='JUNCTION_OR_INTRUSION_NEEDS_RESIDUAL_SCHEME'))
        result = dict(face_caps=limits, witnesses=witnesses, editable_bulk_source_ids=sorted(bulk),
                    fixed_lane_intervals_mm=fixed_intervals,
                    protected_domain_compilation='WHOLE_DOMAIN_BOUNDS_BEFORE_ALLOCATION',
                    unresolved=unresolved, complete_source_bounds=True,
                    semantics='CONSERVATIVE_SOURCE_BOUND_CONSTRAINTS; NO_CANDIDATE_GEOMETRY_QUERY')
        self.frames[key] = result
        while len(self.frames) > 256:self.frames.popitem(last=False)
        return result


def interior_intervals(first, last, unresolved, *, transition=.05):
    """Subtract recorded junction windows, leaving the rest of the same group.

    This partitions source relations before allocation. It never searches for
    a passing width or discards a whole long group because one end has a pad.
    """
    cuts = sorted((max(first, q['longitudinal_interval_mm'][0]-transition),
                   min(last, q['longitudinal_interval_mm'][1]+transition)) for q in unresolved)
    cursor = first;free = [];merged = []
    for lo, hi in cuts:
        if hi <= lo:continue
        if merged and lo <= merged[-1][1]:merged[-1][1] = max(merged[-1][1], hi)
        else:merged.append([lo, hi])
    for lo, hi in merged:
        if lo > cursor:free.append([cursor, lo])
        cursor = max(cursor, hi)
    if cursor < last:free.append([cursor, last])
    return free, merged
