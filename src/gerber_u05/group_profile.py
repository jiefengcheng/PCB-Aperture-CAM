"""Parallel-group construction over the existing source-wide straight catalogue.

The catalogue selects relationships; this adapter turns ordered, exactly
parallel native centerlines into a one-dimensional strip problem. It does not
import a saved 10%/25% copper floor or run the dense side-profile scanner.
Group interiors are construction results. Joins, bulk and outside-neighbour
dependencies remain explicit work items until the hybrid caller resolves them.
"""
import math
from time import perf_counter
from .group_allocation import maximum_faces, consecutive_widths
from .limiting_math import GUARD, MARGIN, SHARED_LENGTH

SCHEMA = 't04-direct-parallel-group-profile/1'


def outline(axis, first, last, left, right):
    """Fresh butt-ended ideal strip, not an offset of noisy source polygons."""
    ux, uy = axis; nx, ny = -uy, ux
    return [[t*ux+n*nx, t*uy+n*ny]
            for t, n in ((first, left), (last, left), (last, right), (first, right))]


def solve_band(runs, band, mutable_routes, settings, *, width_caps=None, face_caps=None, source_anchored=False,fixed_intervals=None):
    """Construct one group interior; callers supply external face limits.

    An angularly approximate relation is not silently promoted to an exact
    parallel strip. Such a relation stays in the existing residual path.
    """
    axis = band['axis']; ux, uy = axis; nx, ny = -uy, ux
    first, last = band['first'], band['last']
    if (len(axis) != 2 or any(not math.isfinite(x) for x in axis) or
            abs(math.hypot(*axis)-1.) > 1e-10 or
            not math.isfinite(first) or not math.isfinite(last) or last-first < SHARED_LENGTH-1e-10):
        raise ValueError('VALID_SHARED_PARALLEL_INTERVAL_REQUIRED')
    lanes = []
    for i in band['members']:
        run = runs[i]; a, b = run['start'], run['end']
        normal = [(p[0]*nx+p[1]*ny) for p in (a, b)]
        if abs(normal[0]-normal[1]) > 1e-9:
            return dict(status='RESIDUAL', reason='APPROXIMATE_DIRECTION_REQUIRES_ITS_OWN_SCHEME')
        width = run['width_mm']
        if run['route_id']not in mutable_routes and fixed_intervals and run['run_id']in fixed_intervals:
            low,high=fixed_intervals[run['run_id']]
            width=max(width,high-low);normal=[(high+low)/2]*2
        if type(width) not in (int, float) or not math.isfinite(width) or width <= 0:
            raise ValueError('POSITIVE_SOURCE_WIDTH_REQUIRED')
        cap = min(width*settings.maximum_factor, width+settings.maximum_total_width_increase_mm)
        if width_caps is not None:cap = min(cap, width_caps.get(run['run_id'], cap))
        if cap < width-1e-12:
            return dict(status='RESIDUAL', reason='LOCAL_JOIN_LIMIT_BELOW_SOURCE_WIDTH')
        lanes.append(dict(run_id=run['run_id'], route_id=run['route_id'], source_ids=run['source_ids'],
                          source_width_mm=width, source_normal_mm=sum(normal)/2,
                          maximum_width_mm=cap, mutable=run['route_id'] in mutable_routes))
    lanes.sort(key=lambda r: (r['source_normal_mm'], r['run_id']))
    if len(lanes) < 2 or len({r['run_id'] for r in lanes}) != len(lanes):
        raise ValueError('DISTINCT_PARALLEL_LANES_REQUIRED')
    gaps = [b['source_normal_mm']-a['source_normal_mm']-(a['source_width_mm']+b['source_width_mm'])/2
            for a, b in zip(lanes, lanes[1:])]
    required = GUARD+2*MARGIN
    caps = {q['run_id']: max(0., q['maximum_width_mm']-q['source_width_mm']) if q['mutable'] else 0.
            for q in lanes}
    # With each face in [-recession, cap+recession], the physical strip
    # midline can move at most .025 mm. Negative faces do not shrink width:
    # the flow's lower trace bound enforces left+right >= 0 exactly.
    recess = {q['run_id']: max(0., .025-caps[q['run_id']]/2) if q['mutable'] and not source_anchored else 0. for q in lanes}
    limits = {q['run_id']: {s: min(caps[q['run_id']]+recess[q['run_id']], face_caps.get(q['run_id'], {}).get(s, caps[q['run_id']]+recess[q['run_id']]))
                           if face_caps is not None else caps[q['run_id']]+recess[q['run_id']]
                           for s in ('left', 'right')} for q in lanes}
    try:
        allocation = maximum_faces([q['run_id'] for q in lanes], caps,
                                   [g-required for g in gaps], face_caps=limits, recessions=recess)
    except ValueError as error:
        if str(error) != 'GROUP_POSITION_BOUNDS_INFEASIBLE':raise
        return dict(status='RESIDUAL', reason='GROUP_POSITION_BOUNDS_INFEASIBLE')
    for q in lanes:
        growth = allocation['face_growth_mm'][q['run_id']]
        left = q['source_normal_mm']-q['source_width_mm']/2-growth['left']
        right = q['source_normal_mm']+q['source_width_mm']/2+growth['right']
        q.update(left_mm=left, right_mm=right, width_mm=q['source_width_mm']+sum(growth.values()),
                 profile_midline_shift_mm=(growth['right']-growth['left'])/2,
                 face_growth_mm=growth,
                 vertices_mm=outline(axis, first, last, left, right))
    # Endpoint inequalities describe the complete straight strips, including
    # their whole shared interval. This is algebra, not sampled geometry.
    clearance = [b['left_mm']-a['right_mm'] for a, b in zip(lanes, lanes[1:])]
    if any(g < required-1e-12 for g in clearance):
        raise ValueError('PARALLEL_STRIP_BUDGET_IDENTITY_CHANGED')
    return dict(status='CONSTRUCTED_INTERIOR', axis=axis, first_mm=first, last_mm=last,
                reference_policy='SOURCE_ANCHORED' if source_anchored else 'BOUNDED_GROUP_REPOSITIONING',
                lanes=lanes, allocation=allocation, source_gaps_mm=gaps,
                constructed_gaps_mm=clearance, construction_clearance_mm=required,
                geometry_audit=False, source_edge_policy='NEW_IDEAL_STRAIGHT_BOUNDARIES',
                external_constraints='CALLER_OWNED', joints='CALLER_OWNED')


def plan(straight, route_ids, settings, *, width_caps=None, face_caps=None, boundaries=None, source_anchored=False):
    start = perf_counter()
    routes = set(route_ids)
    if not routes or len(routes) != len(route_ids) or len(routes) > 128:
        raise ValueError('EXPLICIT_BOUNDED_GROUP_ROUTES_REQUIRED')
    runs = straight['runs']; groups = []; residual = []
    for index, band in enumerate(straight['cases']['admitted_0.05']['bands']):
        if not any(runs[i]['route_id'] in routes for i in band['members']):continue
        framing = boundaries.for_band(runs, band, settings) if boundaries is not None else None
        if framing is not None and framing['unresolved']:
            from .group_boundaries import interior_intervals
            intervals, cuts = interior_intervals(band['first'], band['last'], framing['unresolved'])
            residual.append(dict(status='RESIDUAL', reason='JUNCTION_WINDOWS',
                                 catalogue_band_index=index, intervals_mm=cuts,
                                 source_boundary_constraints=framing))
            parts = [dict(band, first=a, last=b) for a, b in intervals if b-a >= SHARED_LENGTH]
        else:parts = [band]
        for part in parts:
            if part is not band:framing = boundaries.for_band(runs, part, settings)
            if framing is not None and framing['unresolved']:
                result = dict(status='RESIDUAL', reason='JUNCTION_OR_INTRUSION_NEEDS_RESIDUAL_SCHEME')
            else:
                result = solve_band(runs, part, routes, settings, width_caps=width_caps,
                                    face_caps=framing['face_caps'] if framing is not None else face_caps,
                                    fixed_intervals=framing.get('fixed_lane_intervals_mm')if framing is not None else None,
                                    source_anchored=source_anchored)
            if framing is not None:result['source_boundary_constraints'] = framing
            result['catalogue_band_index'] = index
            (groups if result['status'] == 'CONSTRUCTED_INTERIOR' else residual).append(result)
    return dict(schema=SCHEMA, status='GROUP_INTERIORS_CONSTRUCTED; HYBRID_ASSEMBLY_PENDING',
                reference_policy='SOURCE_ANCHORED' if source_anchored else 'BOUNDED_GROUP_REPOSITIONING',
                requested_routes=sorted(routes), groups=groups, residual_groups=residual,
                width_deviation=dict(value=.25, scope='CONSECUTIVE_SEGMENTS_ONLY', route_wide=False),
                objective='MAXIMUM_SUM_WIDTH_GROWTH_PER_GROUP',
                geometry_audit=False, native_final_audit='NOT_RUN_BY_DESIGN',
                full_board_run=False, replay=False, export=False,
                planning_wall_s=perf_counter()-start,
                publication_ready=False,
                pending=['CROSS_GROUP_AND_ROUTE_JOIN_ASSEMBLY', 'EDITABLE_BULK', 'RESIDUAL_GROWTH'])


def local_join_caps(proposed, actual_source_edges, *, deviation=.25):
    """Apply the reusable limiting propagation to real adjacent sections only."""
    return consecutive_widths(proposed, actual_source_edges, deviation=deviation)


def route_join_plan(rows, paths, construction, settings,*,source_width_caps=None):
    """Reuse source endpoints and limiting propagation, without a route band.

    Group solutions supply constrained widths; otherwise the default is the
    original physical source cap. Only segments sharing a native endpoint in
    the same route exchange a 25% bound. No geometric neighbour is inferred.
    """
    from collections import defaultdict
    from decimal import Decimal
    from itertools import combinations
    owner = {s: r for r, ss in paths.items() for s in ss}
    proposed = {s: min(rows[s]['metadata']['minimum_caliper_mm']*settings.maximum_factor,
                       rows[s]['metadata']['minimum_caliper_mm']+settings.maximum_total_width_increase_mm)
                for s in owner}
    for group in construction['groups']:
        for lane in group['lanes']:
            for s in lane['source_ids']:
                if s in proposed:proposed[s] = min(proposed[s], lane['width_mm'])
    if source_width_caps is not None:
        for s,w in source_width_caps.items():
            if s not in proposed or not math.isfinite(w) or w<rows[s]['metadata']['minimum_caliper_mm']-1e-12:
                raise ValueError('SOURCE_DEFAULT_WIDTH_CAP_INVALID')
            proposed[s]=min(proposed[s],w)
    endpoints = defaultdict(set)
    for s, r in owner.items():
        md = rows[s]['metadata'];pts = md.get('endpoints_decimal_mm') or (md['route_points_mm'][0], md['route_points_mm'][-1])
        for pt in pts:endpoints[r, tuple(Decimal(str(x)) for x in pt)].add(s)
    edges = sorted({tuple(sorted((a, b))) for ss in endpoints.values() for a, b in combinations(sorted(ss), 2)})
    selected = local_join_caps(proposed, edges)
    selected={s:max(rows[s]['metadata']['minimum_caliper_mm'],w)for s,w in selected.items()}
    return dict(schema='t04-consecutive-segment-width-plan/1', proposed_widths_mm=proposed,
                selected_width_caps_mm=selected, adjacency=[list(e) for e in edges],
                deviation=.25, whole_route_band=False,
                geometry_disposition='JOIN_SHAPES_STILL_REQUIRE_CATEGORY_CONSTRUCTION_OR_RESIDUAL_VERIFICATION')


def transition_guard(maximum_total_growth_mm, maximum_translation_mm, *, headroom=2.):
    values = (maximum_total_growth_mm, maximum_translation_mm, headroom)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values) or min(values[:2]) < 0 or headroom <= 1:
        raise ValueError('TRANSITION_OUTLIER_GUARD_PARAMETERS_INVALID')
    return dict(maximum_extra_reach_mm=headroom*(maximum_total_growth_mm+maximum_translation_mm),
                basis='OUTLIER_ONLY; CLEARANCE_COMES_FROM_ASSIGNED_CORRIDOR', headroom=headroom,
                whole_route_width_band=False)
