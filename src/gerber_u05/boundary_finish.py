"""Subtractive T04 transitions over a prepared native endpoint graph.

Inputs are admitted per-source copper, immutable entry floors and optional fixed
contact supports. No foreign-copper search, ownership reconstruction or clearance
API is available here. Compile components/chains once, construct common references,
then subtract optional copper and inspect the actual finished outline.
"""
from collections import defaultdict
import math
from time import perf_counter
import numpy as np
from shapely import from_wkb,to_wkb
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.errors import GEOSException
from src.native_inventory import ERROR_MM
from src.stage_abi.store import digest
from .finite_profile_union import polygonal
from .ribbon_profile import frame
from .side_profile import extent
from .joint_reconciliation import custody_sections


def key(point):
    return tuple(round(float(v), 10) for v in point)


def polygons(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        return [geometry]
    return [p for child in getattr(geometry,'geoms',[]) for p in polygons(child)]


def component_count(geometry):
    """Count local face contacts without constructing an ownership R-tree."""
    return len(contact_components(geometry))


def contact_components(geometry):
    if not geometry.is_empty and (not geometry.is_valid or geometry.geom_type not in('Polygon','MultiPolygon')):
        raise ValueError('VALID_FILLED_SOURCE_REQUIRED')
    faces=polygons(geometry)
    if len(faces)<2:return [faces]if faces else[]
    parents=list(range(len(faces)))
    def root(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]];i=parents[i]
        return i
    active=[]
    for xmin,ymin,xmax,ymax,i in sorted((*g.bounds,i)for i,g in enumerate(faces)):
        active=[v for v in active if v[0]>=xmin]
        for right,low,high,j in active:
            if high>=ymin and ymax>=low and faces[i].intersects(faces[j]):
                a,b=root(i),root(j);parents[max(a,b)]=min(a,b)
        active.append((xmax,ymin,ymax,i))
    groups=defaultdict(list)
    for i,face in enumerate(faces):groups[root(i)].append(face)
    return list(groups.values())


def retain_carriers(body, floor):
    """Drop optional islands; preserve exact entry carriers and their contacts."""
    from .source_trace_floor import preserve
    if floor.is_empty:return floor
    groups=contact_components(body)
    kept=[face for group in groups if any(face.intersects(floor)for face in group)for face in group]
    result=polygonal(unary_union(kept))
    # Floor-first union only restores input copper; never fabricate a new cap.
    if result.is_empty:return floor
    result,_=preserve(floor,result)
    return result


def subtract_optional(body,cut):
    """Retry a failed exact overlay using only its local intersection.

    Valid tangent operands can produce nested zero-area shells in GEOS.
    Restricting the cut before the difference changes no intended material;
    no snapping, buffering, make-valid or clearance exemption is introduced.
    """
    if not body.is_valid or not cut.is_valid:raise ValueError('VALID_OPTIONAL_SUBTRACTION_OPERANDS_REQUIRED')
    try:result=polygonal(body.difference(cut))
    except GEOSException:result=None
    if result is not None and result.is_valid:return result,'DIRECT'
    local=polygonal(cut.intersection(body))
    if not local.is_valid:raise ValueError('T04_LOCAL_CUT_INTERSECTION_INVALID')
    result=body if local.is_empty else polygonal(body.difference(local))
    if not result.is_valid or result.difference(body).area>1e-12:
        raise ValueError('T04_EXACT_LOCAL_SUBTRACTION_INVALID')
    return result,'EXACT_INTERSECTION_BEFORE_DIFFERENCE'


def hole_regions(geometry):
    return [Polygon(ring)for face in polygons(geometry)for ring in face.interiors
            if Polygon(ring).area>ERROR_MM**2]


def prepare_voids(grown, floor):
    original=hole_regions(floor);admitted=hole_regions(grown)
    return original,admitted,polygonal(unary_union([*original,*admitted]))


def new_pockets(grown, floor, after, *, prepared=None):
    """Distinguish a new pocket from restoring an original input opening.

    Optional growth can have filled a source hole. Returning that space to
    its original void is subtraction, not a newly enclosed pocket. Additional
    disconnected descendants inside one old opening still fail the gate.
    """
    original,admitted,baseline=prepare_voids(grown,floor)if prepared is None else prepared
    current=hole_regions(after)
    new=[hole for hole in current if hole.difference(baseline).area>ERROR_MM**2]
    for region in polygons(baseline):
        descendants=[hole for hole in current if hole.intersection(region).area>ERROR_MM**2]
        allowed=max(sum(h.intersection(region).area>ERROR_MM**2 for h in original),
                    sum(h.intersection(region).area>ERROR_MM**2 for h in admitted))
        for hole in sorted(descendants,key=lambda h:(-h.area,h.bounds))[allowed:]:
            if not any(hole.equals(h)for h in new):new.append(hole)
    return new


def sharp_vertices(body, angle):
    """Compute physical turn candidates once for this exact contour/angle."""
    found=[]
    for poly in polygons(body):
        for ring in [poly.exterior,*poly.interiors]:
            points=np.asarray(ring.coords)[:-1]
            if len(points)<3:continue
            before=points-np.roll(points,1,axis=0);after=np.roll(points,-1,axis=0)-points
            a,b=np.linalg.norm(before,axis=1),np.linalg.norm(after,axis=1)
            cosine=np.sum(before*after,axis=1)/np.maximum(a*b,1e-30)
            turns=np.degrees(np.arccos(np.clip(cosine,-1,1)))
            chosen=(turns>angle+1e-4)&(np.minimum(a,b)>2*ERROR_MM)
            found.extend((points[i],before[i],after[i])for i in np.flatnonzero(chosen))
    return body,angle,found


def sharp_points(body, floor, angle, protected=None, *, vertices=None):
    """Physical turns, excluding unchanged original sharp vertices."""
    optional=None
    if not floor.is_empty:
        optional=polygonal(unary_union([g for g in polygons(body.difference(floor)) if g.area>ERROR_MM**2/100]))
        if optional.is_empty:
            return []
    if protected is None:
        protected = set()
        for point in sharp_points(floor, Polygon(), angle, set()):
            cell = tuple(round(v / (2 * ERROR_MM)) for v in point)
            protected.update((cell[0]+x, cell[1]+y) for x in (-1,0,1) for y in (-1,0,1))
    prepared=sharp_vertices(body,angle)if vertices is None else vertices
    if prepared[0]is not body or prepared[1]!=angle:raise ValueError('SHARP_VERTEX_GEOMETRY_OR_ANGLE_CHANGED')
    found=[]
    for p,before,after in prepared[2]:
        if optional is not None and optional.distance(Point(p))>2*ERROR_MM:continue
        if tuple(round(float(v)/(2*ERROR_MM))for v in p)in protected:continue
        samples=[p,p-before*.5,p+after*.5]
        if not floor.is_empty and all(floor.boundary.distance(Point(v))<=ERROR_MM/10 for v in samples):continue
        found.append(p.tolist())
    return found


def board_outline(before_sources, after_sources, angle,terminals=(),*,baseline_sources=None,evaluation=None):
    """One final assembled-image check, never a per-defect reconstruction."""
    if tuple(before_sources)!=tuple(after_sources):
        raise ValueError('T04_BOARD_OUTLINE_SOURCE_ORDER_CHANGED')
    before=polygonal(unary_union(list(before_sources.values())))
    after=polygonal(unary_union(list(after_sources.values())))
    baseline=before
    if baseline_sources is not None:
        if tuple(baseline_sources)!=tuple(before_sources):raise ValueError('T04_BRIDGE_BASELINE_SOURCE_ORDER_CHANGED')
        baseline=polygonal(unary_union(list(baseline_sources.values())))
    receipt=outline_images(before,after,angle,terminals,baseline=baseline if baseline_sources is not None else None,evaluation=evaluation)
    receipt['complete_board_unions']=2+int(baseline_sources is not None)
    return before,after,receipt


def outline_images(before,after,angle,terminals=(),*,baseline=None,evaluation=None):
    """Validate already assembled exact images without repeating their unions."""
    specified=baseline is not None
    if baseline is None:baseline=before
    from .terminal_handoff import interior_t04 as interior
    if evaluation is not None:
        if not evaluation:evaluation['vertices']=sharp_vertices(after,angle)
        vertices=evaluation['vertices']
    else:vertices=None
    all_points=sharp_points(after,baseline,angle,vertices=vertices)
    if specified:
        from .growth_bridge import meaningful_shoulders
        all_points=meaningful_shoulders(after,all_points)
    points=interior(all_points,terminals)
    added=after.difference(baseline).area;removed=baseline.difference(after).area
    pockets=new_pockets(baseline,before,after)if specified else []
    return dict(passed=not points and not pockets and (not specified or added+1e-12>=removed),additional_shoulders=len(points),points_mm=points,
        comparison='PRE_FINISHING_WIDENING'if specified else'STAGE_ENTRY',
        bridge_added_area_mm2=added,bridge_removed_area_mm2=removed,bridge_net_growth_area_mm2=added-removed,
        new_pockets=len(pockets),
        deferred_terminal_shoulders=len(all_points)-len(points),terminal_owner='T05'if terminals else None,
        maximum_transition_angle_degrees=angle,complete_board_unions=0,scene_indexes_built=0,
        geometry_scope='EXACT_FINAL_SERIALIZED_SOURCE_CONTRIBUTIONS')


def compile_graph(rows, paths, bodies, original, covered, supports):
    """Endpoint equality joins catalogue routes; aliases are one graph edge."""
    parent = {r:r for r in paths}
    def root(r):
        while parent[r] != r:
            parent[r] = parent[parent[r]]
            r = parent[r]
        return r
    endpoints = {}
    for route, sources in sorted(paths.items()):
        for source in sources:
            points = rows[source]['metadata']['route_points_mm']
            for point in (points[0], points[-1]):
                point = key(point)
                if point in endpoints:
                    a,b = root(route),root(endpoints[point])
                    parent[max(a,b)] = min(a,b)
                else:
                    endpoints[point] = route
    groups = defaultdict(list)
    for route in sorted(paths):
        groups[root(route)].append(route)
    result = []
    for identity, routes in groups.items():
        sources = sorted({s for r in routes for s in paths[r] if s in bodies})
        if not sources:
            continue
        pieces=[];source_set=set(sources)
        for route in routes:
            support=supports.get(route)
            if support is None:continue
            if isinstance(support,dict):pieces.extend(g for source,g in support.items()if source not in source_set)
            else:pieces.append(support)
        fixed_support = polygonal(unary_union(pieces))
        floor = polygonal(unary_union([original[s] for s in sources] + [fixed_support]))
        grown = polygonal(unary_union([bodies[s] for s in sources] + [fixed_support]))
        fixed = polygonal(unary_union([bodies[s] for s in sources if s in covered] + [fixed_support]))
        aliases = defaultdict(list)
        for s in sources:
            points=rows[s]['metadata']['route_points_mm']
            aliases[rows[s]['metadata']['minimum_caliper_mm'],tuple(sorted((key(points[0]),key(points[-1])))),original[s].wkb].append(s)
        representatives = {min(ss):ss for ss in aliases.values()}
        nodes = defaultdict(list)
        for s in representatives:
            points = rows[s]['metadata']['route_points_mm']
            for end,point in enumerate((points[0],points[-1])):
                nodes[key(point)].append((s,end))
        locked = {s for s,ss in representatives.items() if set(ss).intersection(covered)}
        def continues(s, point):
            ends = nodes[key(point)]
            width = rows[s]['metadata']['minimum_caliper_mm']
            return (len(ends)==2 and s not in locked and all(t not in locked and
                    abs(rows[t]['metadata']['minimum_caliper_mm']-width)<=1e-12 for t,e in ends))
        visited = set()
        chains = []
        for seed in sorted(representatives, key=lambda s: all(continues(s,p) for p in
                           (rows[s]['metadata']['route_points_mm'][0], rows[s]['metadata']['route_points_mm'][-1]))):
            if seed in visited:
                continue
            native = rows[seed]['metadata']['route_points_mm']
            side = next((e for e,p in enumerate((native[0],native[-1])) if not continues(seed,p)),0)
            source = seed
            points,members,hard_source_joins,source_intervals = [],[],[],[]
            station=0.
            while source not in visited:
                native = rows[source]['metadata']['route_points_mm']
                part = native if side==0 else native[::-1]
                if points:
                    a=np.asarray(points[-1])-np.asarray(points[-2]);b=np.asarray(part[1])-np.asarray(part[0])
                    turn=math.degrees(math.atan2(abs(a[0]*b[1]-a[1]*b[0]),float(a@b)))
                    if turn>1.:hard_source_joins.append(part[0])
                part_length=LineString(part).length
                source_intervals.extend((station,station+part_length,s)for s in representatives[source])
                station+=part_length
                points.extend(part if not points else part[1:])
                members.extend(representatives[source])
                visited.add(source)
                if not continues(source,part[-1]):
                    break
                other = [(s,e) for s,e in nodes[key(part[-1])] if s!=source]
                if len(other)!=1 or other[0][0] in visited:
                    break
                source,side = other[0]
            line = LineString(points)
            if line.length <= 4*ERROR_MM:
                continue
            chains.append(dict(source_ids=members, points=points, line=line,
                source_intervals=source_intervals,
                hard_source_joins=hard_source_joins,
                width=rows[seed]['metadata']['minimum_caliper_mm'], fixed=seed in locked,
                contact_support=fixed_support,
                collars=[max(rows[s]['metadata']['minimum_caliper_mm'] for s,e in nodes[key(p)])/2+4*ERROR_MM
                         for p in(points[0],points[-1])],
                body=polygonal(unary_union([bodies[s] for s in members])),
                floor=polygonal(unary_union([original[s] for s in members]))))
        result.append(dict(identity=identity, route_ids=routes, sources=sources,
                           floor=floor, grown=grown, fixed=fixed, support=fixed_support,nodes=nodes, chains=chains))
    return result


def reference(chain, caps, slope):
    """Prepare own-skin budgets once, then a C1 minorant across the chain."""
    from .smooth_transition import certify
    length=chain['line'].length
    left,right=chain['collars']
    p,n,stations,length = frame(chain['points'],extra_stations=[min(left,length),max(0.,length-right)])
    width=chain['width']
    cap=max(0.,min(caps.get(s,width) for s in chain['source_ids'])-width)
    values=[]
    for center,normal in zip(p,n):
        size=float(np.linalg.norm(normal))
        section=extent(chain['body'],center,normal/size,width+cap+.11)
        if section is None:
            values.append([0.,0.]);continue
        values.append([min(cap,max(0.,v/size-width/2-2*ERROR_MM))for v in section[::-1]])
    values=np.asarray(values)
    local=chain.get('local_controls',False)
    if local:
        # A native miter can reverse inside an already filled source bend.
        # Suppress optional width only on those intervals. Their unchanged
        # floor is not itself a newly proposed taper edge.
        axes=np.diff(p,axis=0);bad=np.zeros(len(axes),dtype=bool)
        for rail in(p-n*width/2,p+n*width/2):
            edge=np.diff(rail,axis=0)
            alignment=np.arctan2(np.abs(axes[:,0]*edge[:,1]-axes[:,1]*edge[:,0]),np.sum(axes*edge,axis=1))
            bad|=alignment>math.atan(slope)+1e-8
        for i in np.flatnonzero(bad):values[i:i+2]=0.
        for point in chain['hard_source_joins']:
            station=chain['line'].project(Point(point))
            values[np.abs(stations-station)<=width/2+4*ERROR_MM]=0.
    # Fixed pad/fill contacts can lie inside a source segment. Their prepared
    # original footprint, rather than the primitive's endpoint, sets the end
    # of the nominal collar. This is contact geometry, not a spacing search.
    if not chain['contact_support'].is_empty:
        from shapely import distance,points as geometry_points
        touching=distance(chain['contact_support'],geometry_points(p))<=width/2+cap+4*ERROR_MM
        values[touching]=0.
    # A total cap is shared by both faces, never granted twice.
    totals=values.sum(axis=1)
    values*=np.minimum(1.,cap/np.maximum(totals,1e-30))[:,None]
    # Zero growth throughout each original junction mouth, not just at its
    # centreline point. Otherwise two growing arms intersect beyond the
    # nominal corner and reproduce the same sharp T shoulder.
    left,right=chain['collars']
    values[(stations<=left)|(stations>=length-right)]=0.
    values[0]=values[-1]=0.
    # Cubics with zero knot derivatives have max slope 1.5*delta/span.
    # Two linear passes compute the admissible minorant, not iterative search.
    distances=np.diff(stations)
    normal_derivatives=np.diff(n,axis=0)/distances[:,None]
    # An inside offset rail travels less distance than its native centreline.
    # Reserve that metric before converting a spatial angle to width slope.
    curvature=np.linalg.norm(normal_derivatives,axis=1)
    metric=np.maximum(0.,1-(width/2+cap)*curvature)
    rates=slope*metric/1.5
    if local:
        u=axes/np.linalg.norm(axes,axis=1)[:,None]
        v=np.column_stack((-u[:,1],u[:,0]));radius=width/2+cap
        parallel=np.abs(np.sum(normal_derivatives*u,axis=1))*radius
        transverse=np.abs(np.sum(normal_derivatives*v,axis=1))*radius
        n_parallel=np.maximum(np.abs(np.sum(n[:-1]*u,axis=1)),np.abs(np.sum(n[1:]*u,axis=1)))
        n_transverse=np.maximum(np.abs(np.sum(n[:-1]*v,axis=1)),np.abs(np.sum(n[1:]*v,axis=1)))
        margin=slope*(1-parallel)-transverse
        for i in np.flatnonzero(margin<=0):values[i:i+2]=0.
        rates=np.minimum(rates,np.maximum(0.,margin)/(np.maximum(n_transverse+slope*n_parallel,1e-30)*1.5))
    chain['stations']=stations;chain['values']=values;chain['rates']=rates
    for attempt in range(9 if local else 1):
        minorant(chain)
        try:return materialize(chain,1.,slope)
        except AlignmentRejected as error:
            if not local:raise
            for lo,hi in error.spans:
                reach=width/2+.01
                first=max(0,np.searchsorted(stations,lo-reach,side='right')-1)
                last=min(len(stations),np.searchsorted(stations,hi+reach,side='left')+1)
                values[first:last]=0.
    raise ValueError('T04_LOCAL_ALIGNMENT_REFINEMENT_UNRESOLVED')


def minorant(chain):
    values,stations,rates=chain['values'],chain['stations'],chain['rates']
    for i in range(1,len(values)):
        values[i]=np.minimum(values[i],values[i-1]+rates[i-1]*(stations[i]-stations[i-1]))
    for i in range(len(values)-2,-1,-1):
        values[i]=np.minimum(values[i],values[i+1]+rates[i]*(stations[i+1]-stations[i]))


class AlignmentRejected(ValueError):
    def __init__(self,spans):
        super().__init__('MATERIALIZED_TRANSITION_ANGLE_EXCEEDS_POLICY');self.spans=spans


def materialize(chain, scale, slope):
    from .smooth_transition import certify,tessellate,value
    values=chain['values']*scale
    if values.max()<=2*ERROR_MM:
        return chain['floor'],None
    stations=chain['stations'];proofs=[];knots=[]
    for i in range(len(stations)-1):
        lo,hi=stations[i:i+2]
        proof=certify(values[i].tolist(),values[i+1].tolist(),float(hi-lo),maximum_side_slope=slope)
        if not proof['passed']:raise ValueError('TRANSITION_SIDE_FIELD_SLOPE_CHANGED')
        proofs.append(proof)
        for controls in proof['controls']:
            knots.extend(lo+t for t,v in tessellate(controls,hi-lo,error_mm=ERROR_MM/10))
    if 'native_frame'in chain:
        from .ribbon_profile import window_frame
        native=chain['native_frame']
        p,n,t,length=window_frame(native['points'],*native['interval_mm'],extra_stations=knots)
    else:p,n,t,length=frame(chain['points'],extra_stations=knots)
    offsets=[]
    for station in t:
        i=min(len(proofs)-1,max(0,int(np.searchsorted(stations,station,side='right')-1)))
        fraction=min(1.,max(0.,(station-stations[i])/(stations[i+1]-stations[i])))
        offsets.append([value(c,fraction)for c in proofs[i]['controls']])
    offsets=np.asarray(offsets);width=chain['width']
    lower=p-n*(width/2+offsets[:,0])[:,None];upper=p+n*(width/2+offsets[:,1])[:,None]
    axes=np.diff(p,axis=0)
    alignment=0.;bad=np.zeros(len(axes),dtype=bool);rail_angles=[]
    active=(np.maximum(offsets[:-1].max(axis=1),offsets[1:].max(axis=1))>2*ERROR_MM
            if chain.get('local_controls')else np.ones(len(axes),dtype=bool))
    for rail in(lower,upper):
        edges=np.diff(rail,axis=0)
        angles=np.degrees(np.arctan2(np.abs(axes[:,0]*edges[:,1]-axes[:,1]*edges[:,0]),np.sum(axes*edges,axis=1)))
        rail_angles.append((rail,angles))
        alignment=max(alignment,float(angles[active].max())if active.any()else 0.)
        bad|=active&(angles>math.degrees(math.atan(slope))+1e-8)
    exposed=chain.get('exposed_controls',False)
    if bad.any()and not exposed:raise AlignmentRejected([(float(t[i]),float(t[i+1]))for i in np.flatnonzero(bad)])
    shape=Polygon(lower.tolist()+upper[::-1].tolist())
    if not shape.is_valid:
        cells=[Polygon([lower[i],lower[i+1],upper[i+1],upper[i]]).convex_hull for i in range(len(p)-1)]
        shape=polygonal(unary_union(cells))
    if chain.get('local_controls'):
        # Compose active cross sections with their exact carrier. Removing a
        # separately tessellated zero-width ribbon leaves chord-sized cracks
        # along curved source edges. Zero-field intervals contribute only the
        # original floor; active cells overlap it instead of leaving a seam.
        cells=[Polygon([lower[i],lower[i+1],upper[i+1],upper[i]]).convex_hull
               for i in range(len(p)-1) if active[i]]
        shape=polygonal(unary_union([chain['floor'],*cells]))
    internal_alignment=alignment;hidden=0
    if exposed:
        # Folded offset cells can be completely buried in their neighboring
        # cells or the unchanged source carrier. They are construction
        # operands, not exposed copper edges. Keep the existing angle bound
        # on every rail that actually survives the exact materialization.
        boundary=shape.boundary.buffer(ERROR_MM);alignment=0.;spans=[]
        for rail,angles in rail_angles:
            limit=math.degrees(math.atan(slope))+1e-8
            under=active&(angles<=limit)
            alignment=max(alignment,float(angles[under].max())if under.any()else 0.)
            for i in np.flatnonzero(active&(angles>limit)):
                edge=LineString(rail[i:i+2])
                if edge.intersection(boundary).length<=2*ERROR_MM:
                    hidden+=1;continue
                alignment=max(alignment,float(angles[i]))
                spans.append((float(t[i]),float(t[i+1])))
        if spans:raise AlignmentRejected(spans)
    ends=[dict(normal=n[i].tolist(),lower_mm=lower[i].tolist(),upper_mm=upper[i].tolist())for i in(0,-1)]
    return shape,dict(native_points_mm=chain['points'],source_width_mm=width,length_mm=length,
        profile=dict(endpoint_sections=ends,side_field_proofs=proofs),
        maximum_materialized_alignment_angle_degrees=alignment,
        maximum_internal_rail_angle_degrees=internal_alignment,hidden_internal_rails=hidden,
        rail_visibility_scope='ANGLE_EXCEEDING_RAILS_ONLY'if exposed else'ALL_CONSTRUCTION_RAILS',
        optional_width_scale=scale,source_path_changed=False,clearance_certified=False)


def run(rows, paths, bodies, original, width_caps, *, covered=(), supports=None,
        maximum_transition_angle_degrees=10., places=None, progress=None,terminals=None,local_controls=False):
    started = perf_counter()
    angle = maximum_transition_angle_degrees
    if type(angle)not in(int,float) or not math.isfinite(angle) or not 0 < angle < 45:
        raise ValueError('VALID_TRANSITION_ANGLE_REQUIRED')
    slope = math.tan(math.radians(angle))
    covered = set(covered)
    working,cuts,sections,reports,plans = dict(bodies),{},{},[],[]
    batches = compile_graph(rows,paths,bodies,original,covered,supports or {})
    withdrawals=[];assembled_checks=[];void_restorations=[];terminal_records=terminals or [];overlay_retries=[]
    from .terminal_handoff import interior
    for batch in batches:
        floor,grown,fixed = batch['floor'],batch['grown'],batch['fixed']
        regions=[r for r in terminal_records if set(r['source_ids']).intersection(batch['sources'])]
        initial = interior(sharp_points(grown,floor,angle),regions)
        if not initial or (places is not None and not any(math.dist(p,q[:2])<=q[2] for p in initial for q in places)):
            continue
        chains = batch['chains']
        voids=prepare_voids(grown,floor)
        refs,recipes,scales = [],[],[]
        for chain in chains:
            chain['local_controls']=local_controls
            chain['unchanged']=local_controls and not any(chain['line'].distance(Point(p))<=chain['width']/2+.11 for p in initial)
            try:
                shape,recipe = (chain['body'],None) if chain['fixed']or chain['unchanged'] else reference(chain,width_caps,slope)
            except ValueError as error:
                if str(error)not in('MATERIALIZED_TRANSITION_ANGLE_EXCEEDS_POLICY','RESIDUAL_REVERSAL_JOIN_UNSUPPORTED','RESIDUAL_MITER_OUTLIER'):
                    raise
                chain['withdrawal_reason']=str(error)
                shape,recipe = chain['floor'],None
            refs.append(shape);recipes.append(recipe);scales.append(1. if recipe else 0.)
        attempts=[]
        for iteration in range(9):
            common = polygonal(unary_union([fixed,*refs]))
            mask = polygonal(grown.difference(common).difference(floor).difference(fixed))
            inactive={s for chain,recipe in zip(chains,recipes)if not chain['fixed']and not chain['unchanged']and recipe is None for s in chain['source_ids']}
            trial={}
            for s in batch['sources']:
                if s in covered:
                    trial[s]=bodies[s]
                elif s in inactive:
                    trial[s]=original[s]
                else:
                    cut=polygonal(mask.difference(original[s]))
                    if local_controls:
                        subtracted,method=subtract_optional(bodies[s],cut)
                        if method!='DIRECT':overlay_retries.append(dict(source_id=s,component=batch['identity'],iteration=iteration,method=method))
                    else:subtracted=polygonal(bodies[s].difference(cut))
                    trial[s]=retain_carriers(subtracted,original[s])
                if trial[s].difference(bodies[s]).area>1e-12 or original[s].difference(trial[s]).area>1e-12:
                    raise ValueError('T04_SOURCE_TRANSITION_SCOPE_BROKEN')
            # The correction loop consumes the actual per-source assembly.
            # A smooth common reference alone is not an acceptance target.
            # Covered sources are already in trial. Append external original
            # contact support once, preserving the floor's operand order.
            after=polygonal(unary_union([*trial.values(),batch['support']]))
            remaining = interior(sharp_points(after,floor,angle),regions)
            pockets=new_pockets(grown,floor,after,prepared=voids)
            attempts.append(dict(iteration=iteration,remaining_shoulders=len(remaining),new_pockets=len(pockets)))
            if not remaining and not pockets:
                break
            # Reduce only prepared chains touching an offending outline. No
            # new neighbour discovery or clearance operation is performed.
            bad = {i for i,c in enumerate(chains) if not c['fixed'] and scales[i]>0 and
                   (any(c['line'].distance(Point(p)) <= c['width']/2+.11 for p in remaining) or
                    any(c['line'].distance(hole)<=c['width']/2+.11 for hole in pockets))}
            activated=False
            if local_controls:
                # Trimming one arm can expose an adjacent arm's optional
                # edge. Admit that already prepared chain to this local
                # construction batch; do not treat its unchanged status as
                # a permanent exemption from the actual-outline check.
                for i,chain in enumerate(chains):
                    if chain['fixed'] or not chain['unchanged']:continue
                    span=chain['width']/2+.11
                    if not (any(chain['line'].distance(Point(p))<=span for p in remaining) or
                            any(chain['line'].distance(hole)<=span for hole in pockets)):continue
                    chain['unchanged']=False
                    try:refs[i],recipes[i]=reference(chain,width_caps,slope)
                    except ValueError as error:
                        if str(error)not in('MATERIALIZED_TRANSITION_ANGLE_EXCEEDS_POLICY','RESIDUAL_REVERSAL_JOIN_UNSUPPORTED','RESIDUAL_MITER_OUTLIER'):raise
                        chain['withdrawal_reason']=str(error);refs[i],recipes[i]=chain['floor'],None
                    scales[i]=1. if recipes[i] else 0.
                    activated=True
                if activated:continue
            if iteration==7:
                bad={i for i,c in enumerate(chains) if not c['fixed'] and scales[i]>0}
            if not bad:
                break
            for i in bad:
                if local_controls:
                    chain=chains[i];span=chain['width']/2+.11
                    sites=[chain['line'].project(Point(p))for p in remaining if chain['line'].distance(Point(p))<=span]
                    sites += [chain['line'].project(hole.representative_point())for hole in pockets if chain['line'].distance(hole)<=span]
                    for station in sites:
                        radius=span*(1.6**iteration)
                        chain['values'][np.abs(chain['stations']-station)<=radius]=0.
                    if not sites:chain['values']*=.5
                    minorant(chain);refs[i],recipes[i]=materialize(chain,1.,slope)
                    scales[i]=1. if recipes[i]else 0.
                else:
                    scales[i] = 0. if iteration>=6 else scales[i]/2
                    refs[i],recipes[i] = (chains[i]['floor'],None) if not scales[i] else materialize(chains[i],scales[i],slope)
        passed = not remaining and not pockets
        if not passed:
            # An unqualified local proposal never becomes the displayed result.
            reports.append(dict(route_id=batch['identity'],route_ids=batch['route_ids'],
                point_mm=initial[0],kind='FINISHED_OUTLINE',status='UNRESOLVED',
                reason='NEW_INTERIOR_POCKET'if pockets else'NO_ADMISSIBLE_SMOOTH_SUBTRACTIVE_TRANSITION',remaining_shoulders=len(remaining),attempts=attempts,profiles=[]))
            continue
        if after.difference(grown).area>1e-12 or floor.difference(after).area>1e-12:
            raise ValueError('T04_SUBTRACTIVE_TRANSITION_SCOPE_BROKEN')
        if len(hole_regions(after))>len(hole_regions(grown)):
            void_restorations.append(dict(component=batch['identity'],original_voids=len(hole_regions(floor)),
                admitted_voids=len(hole_regions(grown)),final_voids=len(hole_regions(after)),new_pockets=0))
        native_sites=set(batch['nodes'])
        active=[];withdrawn=set();active_sources=set()
        for chain,recipe,scale in zip(chains,recipes,scales):
            if chain['fixed']or chain['unchanged']:
                continue
            if recipe:
                inherited=custody_sections(recipe,chain['body'],native_sites)
                for pt,section in zip((key(chain['points'][0]),key(chain['points'][-1])),recipe['profile']['endpoint_sections']):
                    inherited[pt]=section
                active.append(dict(source_ids=chain['source_ids'],recipe=recipe))
                active_sources.update(chain['source_ids'])
                for s in chain['source_ids']:
                    points=rows[s]['metadata']['route_points_mm']
                    for pt in (key(points[0]),key(points[-1])):
                        if pt in inherited:
                            sections[s,pt]=inherited[pt]
                        if local_controls:
                            station=chain['line'].project(Point(pt))
                            amount=max(float(np.interp(station,chain['stations'],chain['values'][:,i]))for i in(0,1))
                            if amount<=2*ERROR_MM:
                                centers,normals,_,_=frame(points);i=0 if pt==key(points[0])else -1
                                sections[s,pt]=dict(normal=normals[i].tolist(),
                                    lower_mm=(centers[i]-normals[i]*chain['width']/2).tolist(),
                                    upper_mm=(centers[i]+normals[i]*chain['width']/2).tolist(),
                                    policy='ZERO_OPTIONAL_FIELD; UNCHANGED_NATIVE_SOURCE_WIDTH')
            elif chain['body'].difference(chain['floor']).area>1e-12:
                withdrawn.update(chain['source_ids'])
                withdrawals.append(dict(source_ids=chain['source_ids'],reason=chain.get('withdrawal_reason','OPTIONAL_WIDTH_WITHDRAWN_TO_MEET_FINISHED_OUTLINE'),original_retained=True))
            if not recipe:
                for source in chain['source_ids']:
                    points=rows[source]['metadata']['route_points_mm']
                    centers,normals,_,_=frame(points)
                    width=rows[source]['metadata']['minimum_caliper_mm']
                    for i in(0,-1):
                        sections[source,key(points[i])]=dict(normal=normals[i].tolist(),
                            lower_mm=(centers[i]-normals[i]*width/2).tolist(),
                            upper_mm=(centers[i]+normals[i]*width/2).tolist())
            plans.append(dict(source_ids=chain['source_ids'],optional_width_scale=scale,recipe=recipe))
        for s in batch['sources']:
            if s in covered:
                continue
            result=trial[s]
            if result.wkb!=bodies[s].wkb:
                working[s]=result;cuts[s]=polygonal(bodies[s].difference(result))
        nodes=batch['nodes']
        emitted=after
        emitted_shoulders=remaining
        assembled_checks.append(dict(component=batch['identity'],passed=not emitted_shoulders,
            remaining_shoulders=len(emitted_shoulders),added_area_mm2=emitted.difference(grown).area,
            original_removed_area_mm2=floor.difference(emitted).area,new_pockets=len(pockets)))
        if emitted_shoulders:
            reports.append(dict(route_id=batch['identity'],route_ids=batch['route_ids'],point_mm=emitted_shoulders[0],
                kind='FINISHED_OUTLINE',status='UNRESOLVED',reason='SERIALIZED_SOURCE_ASSEMBLY_HAS_SHOULDER',profiles=[]))
        for pt,ends in nodes.items():
            width=max(rows[s]['metadata']['minimum_caliper_mm'] for s,e in ends)
            if not any(math.dist(pt,p)<=max(.1,2*width) for p in initial):
                continue
            reports.append(dict(route_id=batch['identity'],route_ids=batch['route_ids'],point_mm=list(pt),
                kind='THREE_WAY' if len(ends)==3 else 'CONNECTION' if len(ends)==2 else 'FIXED_OR_TRUE_END',
                source_ids=[s for s,e in ends],status='SMOOTHED',remaining_shoulders=0,
                optional_growth_withdrawn=all(s in withdrawn for s,e in ends),
                maximum_transition_angle_degrees=angle,attempts=attempts,profiles=[],
                removed_area_mm2=mask.area,added_area_mm2=0.,original_removed_area_mm2=0.))
        for point in initial:
            if any(math.dist(point,r['point_mm'])<=.1 for r in reports if r['route_id']==batch['identity']):continue
            nearest=min(chains,key=lambda c:c['line'].distance(Point(point)))
            reports.append(dict(route_id=batch['identity'],route_ids=batch['route_ids'],point_mm=point,
                source_ids=nearest['source_ids'],kind='SECTION_SHOULDER',status='SMOOTHED',remaining_shoulders=0,
                optional_growth_withdrawn=not bool(set(nearest['source_ids'])&active_sources),profiles=[],
                maximum_transition_angle_degrees=angle))
        if active and reports:
            reports[-1]['profiles']=active
        if progress:
            progress(dict(component=batch['identity'],finished_shoulders=len(initial),remaining_shoulders=0))
    for r in terminal_records:
        ss=r['source_ids'];region=from_wkb(bytes.fromhex(r['window_wkb_hex']))
        # Include prepared native contacts, never foreign board reconstruction.
        support=supports.get(r['route_id'],{})if supports else{}
        extras=list(support.values())if isinstance(support,dict)else[support]
        image=polygonal(unary_union([working[s]for s in ss]+extras))
        floor=polygonal(unary_union([original[s]for s in ss]+extras))
        points=sharp_points(image,floor,angle)
        outside={tuple(p)for p in interior(points,[r])}
        r['points_mm']=[p for p in points if tuple(p)not in outside]
    terminal_records=[r for r in terminal_records if r['points_mm']]
    return working,cuts,sections,dict(schema='t04-subtractive-boundary-transitions/1',reports=reports,
        maximum_transition_angle_degrees=angle,smoothed=sum(r['status']=='SMOOTHED' for r in reports),
        partial=0,unresolved=sum(r['status']=='UNRESOLVED' for r in reports),chains=plans,withdrawn_growth=withdrawals,
        finished_assembly_checks=assembled_checks,
        original_void_restorations=void_restorations,
        deferred_terminals=terminal_records,local_controls=local_controls,
        exact_overlay_retries=overlay_retries,
        scene_indexes_built=0,clearance_queries=0,owner_reconstructions=0,complete_board_unions=0,
        original_copper_removed_mm2=0.,added_copper_mm2=0.,wall_s=perf_counter()-started)
