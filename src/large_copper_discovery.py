"""One deterministic source-supported large-copper boundary survey.

Every broad-owner ring and both native circular-reference families are considered.
Unqualified curves remain explicit; discovery is never permission to cut copper.
"""
from math import hypot

from shapely.geometry import LineString, Point, Polygon

from src.bulk_edge_restore import fit_straight_flanks, fingerprint
from src.native_inventory import ERROR_MM

PROFILE = 'large-copper-source-supported-boundaries/3'
# One execution obligation, never a menu of selectable treatment profiles.
# A required family without generic discovery is an incomplete implementation,
# not an optional family that the operator can switch off.
REQUIRED_FAMILIES = ('STRAIGHT_SOURCE_FLANKS', 'CAUSING_PAD_AREA_NOISE',
    'COMPOUND_OVERLAPPING_SOURCE_NOISE', 'REDUNDANT_ENDPOINT_FLASHES',
    'SHALLOW_SOURCE_TRACE_EDGE', 'NATIVE_PAD_CENTERED_CIRCULAR_VOID',
    'NATIVE_ROUND_STROKE_ENDPOINT_CIRCULAR_VOID')
DISCOVERY_GAPS = ()
MIN_SUPPORT_MM = .02
MAX_SPAN_MM = 1.
LINE_ERROR_MM = 1e-9


def select_cause(rows, original, revision, cap):
    """Choose the unique strongest original contributor, never by denominator.

    Raster/overlapping source draws can extend a physical trace bump beyond the
    individual causing stroke. Its entire unioned area remains the numerator.
    Pads still require complete containment; a grazing nearby pad is no cause.
    Equal contributing geometries are aliases; equal competing support is open.
    """
    candidates = []
    groups = {}
    for sid in revision.sources(cap):
        row = rows[sid]
        if row['kind'] not in ('stroke', 'circle', 'rectangle'):
            continue
        if row['kind'] == 'stroke' and not row['metadata'].get('route_points_mm'):
            continue
        shape = original[sid]
        if row['kind'] != 'stroke' and cap.difference(shape).area > 1e-12:
            continue
        parts = [cap] if cap.geom_type == 'Polygon' else cap.geoms
        if any(p.intersection(shape).area <= 1e-12 for p in parts):
            continue
        overlap = cap.intersection(shape).area
        points=row['metadata'].get('route_points_mm')
        path_retained=(not points or shape.difference(cap).buffer(ERROR_MM,quad_segs=128).covers(LineString(points)))
        root_support=(LineString(points).difference(cap.envelope.buffer(.100,quad_segs=128)).length
                      if points else None)
        candidates.append(dict(source_id=sid, overlap_mm2=overlap,
                               original_area_mm2=shape.area, kind=row['kind'],
                               original_causing_path_retained=path_retained,
                               unchanged_native_root_outside_feature_neighbourhood_mm=root_support))
        groups.setdefault(shape.wkb, []).append((sid, overlap, root_support, path_retained))
    if not groups:
        return None, candidates, 'WHOLE_BUMP_CAUSE_NOT_ESTABLISHED'
    # A short plotting arc entirely inside the physical bump is an overlapping
    # contributor, not its continuing native cause. Prefer sources that retain
    # a source-supported root outside the whole excursion. Original area never
    # ranks causes. If no root is established, downstream guards still reject
    # removal of a whole causing path rather than inventing one.
    eligible=[group for group in groups.values() if group[0][2] is None or group[0][2]>=MIN_SUPPORT_MM]
    ranked = sorted(groups.values(), key=lambda group: group[0][1], reverse=True)
    if not ranked[0][0][3] and eligible:
        ranked=sorted(eligible,key=lambda group:group[0][1],reverse=True)
    if len(ranked) > 1 and ranked[0][0][1] - ranked[1][0][1] <= 1e-12:
        return None, candidates, 'AMBIGUOUS_CAUSING_SOURCE'
    return ranked[0][0][0], candidates, None


def _supports(points):
    """Stream maximal collinear runs, retaining original edge indices.

    A source support can contain many short collinear subdivisions. Requiring
    one long individual edge loses genuine flanks without changing any copper.
    This groups search evidence only; all native vertices/indexes stay intact.
    """
    n=len(points)
    def aligned(a,b,c):
        dx,dy=b[0]-a[0],b[1]-a[1];length=hypot(dx,dy)
        return length>0 and abs(dx*(c[1]-a[1])-dy*(c[0]-a[0]))<=LINE_ERROR_MM*length and dx*(c[0]-b[0])+dy*(c[1]-b[1])>=0
    start=0
    while start<n and aligned(points[(start-1)%n],points[start],points[(start+1)%n]):start+=1
    if start==n:return
    used=0
    while used<n:
        i=(start+used)%n;a=points[i];b=points[(i+1)%n];used+=1
        while used<n and aligned(a,b,points[(start+used+1)%n]):
            b=points[(start+used+1)%n];used+=1
        end=(start+used)%n
        length=hypot(b[0]-a[0],b[1]-a[1])
        if length<MIN_SUPPORT_MM:continue
        tx,ty=(b[0]-a[0])/length,(b[1]-a[1])/length
        if tx < -1e-12 or abs(tx)<=1e-12 and ty<0:tx,ty=-tx,-ty
        offset=-ty*a[0]+tx*a[1]
        yield i,end,a,b,tx,ty,(round(float(tx),9),round(float(ty),9),round(float(offset),9))


def _excursions(points, origin, tx, ty):
    """Complete native boundary excursions between actual line crossings.

    An adjacent recess must not hide a protrusion, nor be filled. Partition only
    at the supported line itself, never at depth, width or area limits.
    Interpolated crossings are search evidence; source polygons stay untouched.
    """
    offset=lambda p: -(p[0]-origin[0])*ty+(p[1]-origin[1])*tx
    run=[points[0]]
    for p in points[1:]:
        q=run[-1];a,b=offset(q),offset(p)
        if a*b<0 and abs(a)>LINE_ERROR_MM and abs(b)>LINE_ERROR_MM:
            t=a/(a-b);cross=(q[0]+t*(p[0]-q[0]),q[1]+t*(p[1]-q[1]))
            run.append(cross)
            if len(run)>=3:yield run
            run=[cross,p]
        elif abs(b)<=LINE_ERROR_MM:
            run.append(p)
            if len(run)>=3:yield run
            run=[p]
        else:run.append(p)


def discover(rows, original, revision, progress=lambda **event: None):
    context = revision.context
    features, findings, coverage, physical_caps = [], [], [], []
    seen = set()
    for owner, body in revision.owners.items():
        if body.area < 1 or body.buffer(-.125, quad_segs=128).is_empty:
            continue
        # Source survey is a sequential walk of the already authenticated owner
        # coordinates, not another polygon search tree. Retain the existing
        # T02/T05 32-edge indexes only for the admitted feature batch below.
        polygons = [body] if body.geom_type == 'Polygon' else body.geoms
        for pi, poly in enumerate(polygons):
            connected_component_is_broad = poly.area >= 1 and not poly.buffer(-.125,quad_segs=128).is_empty
            for ri, ring in enumerate([poly.exterior, *poly.interiors]):
                coordinates=ring.coords
                n=len(coordinates)-1
                class Ring:
                    def __len__(self):return n
                    def __getitem__(self,index):
                        if index<0 or index>=n:raise IndexError(index)
                        return coordinates[index]
                points=Ring()
                support_count=sum(1 for _ in _supports(points))
                supported_edges=sum((end-start)%n for start,end,*_ in _supports(points))
                transient_weight=n*16+4096+support_count*384
                if transient_weight>context.limit-context.weight:
                    raise ValueError("CLEANUP_DISCOVERY_CAPACITY_EXCEEDED")
                context._charge(transient_weight)
                try:
                    record = dict(owner=owner, polygon=pi, ring=ri, edges=n,
                        straight_support_edges=supported_edges, straight_support_runs=support_count,
                        shared_sections=(n+31)//32,
                        boundary_preparation='DEFERRED_UNTIL_FEATURE_ADMISSION',
                        unsupported_edge_count=n-supported_edges,
                        unsupported_reason='CURVED_OR_SHORT_SUPPORT_NOT_CLASSIFIED_AS_DEFECT',
                        completeness='EXACT_STRAIGHT_SURVEY; SEE_NATIVE_CIRCULAR_REFERENCE_SURVEY; OTHER_CURVES_NOT_ESTABLISHED')
                    coverage.append(record)
                    last = {}
                    from itertools import chain as join_iterators
                    for item in join_iterators(_supports(points),_supports(points)):
                        i, end, a, b, tx, ty, key = item
                        previous = last.get(key)
                        last[key] = item
                        if previous is None:
                            continue
                        j,begin,c,d,*_=previous
                        distance = (i - begin) % n
                        if distance <= 1 or distance >= n - 1:
                            continue
                        # Quantized keys only discover candidates. Actual support
                        # coordinates must pass the existing exact flank fitter.
                        if abs((a[0]-d[0])*tx+(a[1]-d[1])*ty)>MAX_SPAN_MM:
                            record['over_profile_support_gaps']=record.get('over_profile_support_gaps',0)+1
                            continue
                        # Screen the complete source interval before allocating
                        # a patch polygon. A repeated line elsewhere on a large
                        # owner can enclose most of the board, not a local bump.
                        # Reject that entire interval; never clip it to a small
                        # patch or repeatedly shave its first 100 micrometres.
                        sign=0;outside=None;min_u=max_u=0.
                        for k in range(1,distance):
                            p=points[(begin+k)%n]
                            u=(p[0]-a[0])*tx+(p[1]-a[1])*ty
                            v=-(p[0]-a[0])*ty+(p[1]-a[1])*tx
                            min_u,max_u=min(min_u,u),max(max_u,u)
                            if abs(v)>.100 or max_u-min_u>MAX_SPAN_MM:
                                outside='NONLOCAL_OR_OVER_DEPTH_SOURCE_INTERVAL';break
                        if outside:
                            record.setdefault('unsupported_excursions',[]).append(dict(
                                first_edge=j,second_edge=i,reason=outside,
                                disposition='ENTIRE_SOURCE_INTERVAL_UNCHANGED; NOT_CLASSIFIED_AS_A_REPAIRABLE_DEFECT'))
                            continue
                        if distance*96>context.limit-context.weight:
                            raise ValueError('CLEANUP_LOCAL_DISCOVERY_CAPACITY_EXCEEDED')
                        interval = [points[(begin+k)%n] for k in range(distance+1)]
                        for chain in _excursions(interval,a,tx,ty):
                            if len(chain)<3:
                                continue  # a single intervening edge encloses no bump
                            cap = Polygon(chain)
                            if cap.is_empty or not cap.is_valid or cap.area <= 1e-12:
                                continue
                            center = cap.centroid
                            nx, ny = -ty, tx
                            side = (center.x - a[0]) * nx + (center.y - a[1]) * ny
                            if abs(side) <= LINE_ERROR_MM:
                                continue
                            if side < 0:
                                nx, ny = -nx, -ny
                            heights = [(p[0]-a[0])*nx+(p[1]-a[1])*ny for p in chain]
                            if min(heights) < -LINE_ERROR_MM or max(heights) <= LINE_ERROR_MM:
                                continue
                            # An interior return to the support line separates physical
                            # bumps; never silently split a connected excursion to pass.
                            if any(h <= LINE_ERROR_MM for h in heights[1:-1]):
                                continue
                            us = [(p[0]-a[0])*tx+(p[1]-a[1])*ty for p in chain]
                            lo, hi = min(us), max(us)
                            mid = (lo+hi)/2
                            backing = (a[0]+mid*tx-.2*nx, a[1]+mid*ty-.2*ny)
                            connected_backing = False
                            if not body.covers(Point(backing).buffer(.125, quad_segs=128)):
                                # A thin branch of this same broad original polygon
                                # is still large copper. Authenticate that connected
                                # polygon again in CleanupBatch; never admit a small
                                # disconnected trace by its neighbour's area.
                                backing = (a[0]+mid*tx-2*ERROR_MM*nx,
                                           a[1]+mid*ty-2*ERROR_MM*ny)
                                if not connected_component_is_broad or not poly.covers(Point(backing)):
                                    continue
                                connected_backing = True
                            if cap.difference(body).area > 1e-12:
                                continue
                            signature = fingerprint(cap.normalize())
                            if signature in seen:
                                continue
                            seen.add(signature)
                            xy = lambda u,v: (a[0]+u*tx+v*nx, a[1]+u*ty+v*ny)
                            domain = Polygon([xy(lo-.01,0),xy(hi+.01,0),
                                              xy(hi+.01,max(heights)+.01),xy(lo-.01,max(heights)+.01)])
                            edge = LineString([xy(lo-.02,0),xy(hi+.02,0)])
                            f = dict(index=len(findings), owner=owner, bounds_mm=list(domain.bounds),
                                mask_sha256=signature, physical_protrusion_area_mm2=cap.area,
                                depth_mm=max(heights), span_mm=hi-lo,
                                status='unresolved', reason='CAUSE_NOT_ESTABLISHED')
                            findings.append(f)
                            if hi-lo > MAX_SPAN_MM:
                                f['reason']='STRAIGHT_FLANK_SPAN_OUTSIDE_DISCOVERY_PROFILE'
                                continue
                            try:
                                _, evidence = fit_straight_flanks([c,d],[a,b],backing,domain)
                            except ValueError as exc:
                                f['reason']=str(exc)
                                continue
                            sid, causes, cause_error = select_cause(rows, original, revision, cap)
                            f['causing_candidates']=[c['source_id'] for c in causes]
                            f['causing_contributions']=causes
                            f['cause_selection']='UNIQUE_MAXIMUM_PHYSICAL_CONTRIBUTION; ORIGINAL_AREA_NOT_USED_FOR_SELECTION'
                            if cause_error:
                                f['reason']=cause_error
                                continue
                            f['causing_source_id']=sid
                            f['original_feature_area_mm2']=original[sid].area
                            f['area_fraction']=cap.area/original[sid].area
                            if rows[sid]['kind']=='rectangle':
                                f.update(status='ignored',reason='RECTANGULAR_BUMPS_DEFERRED_BY_POLICY')
                                continue
                            evidence.update(source_sha256=context.binding['source'].get('source_sha256'),
                                owner=owner, polygon=pi, ring=ri, source_flank_edge_indices=[j,i],
                                source_flank_edge_runs=[[j,begin],[i,end]],
                                complete_physical_protrusion_sha256=signature)
                            # Subtract the supported exterior half-window from each
                            # contribution. Re-overlaying the assembled cap boundary
                            # can leave round-off slivers on overlapping native draws.
                            if body.intersection(domain).symmetric_difference(cap).area>1e-12:
                                f['reason']='FULL_PHYSICAL_EXCURSION_NOT_ISOLATED'
                                continue
                            features.append(dict(causing_id=sid, domain=domain, smooth_edge=edge,
                                removal_mask=domain, reference_evidence=evidence, backing_point=backing,
                                connected_broad_polygon=pi if connected_backing else None,
                                finding_index=f['index'], rule='SHALLOW_SOURCE_EDGE' if
                                    rows[sid]['kind']=='stroke' and f['area_fraction']>=.10 else 'AREA_NOISE'))
                            physical_caps.append(cap)
                finally:
                    context.weight-=transient_weight
                progress(phase='discovery', owners_surveyed=len({r['owner'] for r in coverage}),
                         rings_surveyed=len(coverage), candidates=len(findings))
    from src.large_copper_circular_discovery import discover as discover_circular
    prepared_owners={findings[f['finding_index']]['owner'] for f in features}
    for owner in sorted(prepared_owners):context.boundary_index(revision.owners[owner])
    curved,curved_findings,curved_coverage=discover_circular(rows,original,revision,progress,
                                                         prepared_owners=prepared_owners)
    offset=len(findings)
    for finding in curved_findings:finding['index']+=offset
    for feature in curved:feature['finding_index']+=offset
    features.extend(curved);findings.extend(curved_findings);coverage.extend(curved_coverage)
    physical_caps.extend(f['removal_mask'] for f in curved)
    # Alternative references touching the same physical patch cannot yield
    # separate cuts or independent area numerators.
    ambiguous = set();superseded=set()
    from shapely import STRtree
    tree = STRtree(physical_caps)
    for i, feature in enumerate(features):
        for j in tree.query(physical_caps[i], predicate='intersects'):
            j=int(j)
            if i!=j and physical_caps[i].intersection(physical_caps[j]).area>1e-12:
                straight_i=feature['reference_evidence']['kind']=='TWO_COLLINEAR_SOURCE_FLANKS'
                straight_j=features[j]['reference_evidence']['kind']=='TWO_COLLINEAR_SOURCE_FLANKS'
                if straight_i!=straight_j:
                    chosen,other=(i,j) if straight_i else (j,i)
                    superseded.add(other)
                    alternatives=findings[features[other]['finding_index']].setdefault('exact_straight_reference_findings',[])
                    if features[chosen]['finding_index'] not in alternatives:alternatives.append(features[chosen]['finding_index'])
                else:ambiguous.update((i,j))
    for i in ambiguous:
        findings[features[i]['finding_index']]['reason']='OVERLAPPING_REFERENCES_REQUIRE_ONE_PHYSICAL_FEATURE'
    for i in superseded:
        findings[features[i]['finding_index']]['reason']='EXACT_NATIVE_STRAIGHT_REFERENCE_TAKES_PRECEDENCE; ALTERNATE_CIRCULAR_MASK_NOT_APPLIED'
    features=[f for i,f in enumerate(features) if i not in ambiguous|superseded]
    admitted_owners={findings[f['finding_index']]['owner'] for f in features}
    for owner in sorted(admitted_owners):
        context.boundary_index(revision.owners[owner])
    for record in coverage:
        if record['owner'] in admitted_owners:
            record['boundary_preparation']='RETAINED_SHARED_T02_T05_32_EDGE_PREPARATION'
    return features, findings, coverage
