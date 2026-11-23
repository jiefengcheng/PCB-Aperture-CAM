"""Native-centred circular references discovered from exact source boundaries.

Local crops survey source vertices only. Admitted flanks are authenticated again
against the one retained T02/T05 ordered boundary structure before construction.
No saved case, source ordinal, angular sector or board window is consumed here.
"""
from collections import Counter
from math import atan2, degrees, hypot, pi
from statistics import median

from shapely import get_coordinates
from shapely.geometry import Point, LineString, box
from shapely.ops import nearest_points

from src.bulk_edge_restore import (fit_circular_void_flanks,
    fit_circular_stroke_end_flanks, fingerprint)
from src.native_inventory import ERROR_MM

FIT_MM = .004


def native_exposure(body, center, radius, *, boundary_lines=None):
    """An interior plotting centre cannot define the external round reference.

    Measure continuous exposed native circumference on the ORIGINAL physical
    fixed owner, using the existing coordinate error. Cropping is outside that
    envelope, so its artificial box edge cannot become exposure evidence.
    """
    from src.gerber_image import disk
    cap=disk(center,radius)
    if boundary_lines is None:
        local=body.intersection(cap.envelope.buffer(2*ERROR_MM).envelope)
        boundary=local.boundary
    else:
        from shapely.ops import unary_union
        boundary=unary_union(boundary_lines)
    exposed=cap.boundary.intersection(boundary.buffer(ERROR_MM,quad_segs=128))
    lines=[exposed] if exposed.geom_type=='LineString' else list(getattr(exposed,'geoms',()))
    longest=max((g.length for g in lines if g.geom_type=='LineString'),default=0.)
    return degrees(longest/radius),fingerprint(cap)


def parts(g):
    if g.is_empty:return []
    if g.geom_type=='Polygon':return [g]
    return [p for child in getattr(g,'geoms',()) for p in parts(child)]


def source_rings(g):
    for p in parts(g):
        yield list(p.exterior.coords)[:-1]
        for r in p.interiors:yield list(r.coords)[:-1]


def arc_span(points, center):
    aa=sorted(degrees(atan2(p[1]-center[1],p[0]-center[0])) for p in points)
    if len(aa)<2:return 0.
    gaps=[b-a for a,b in zip(aa,aa[1:])]+[aa[0]+360-aa[-1]]
    return 360-max(gaps)


def curves_away_from_center(points, center):
    """Reject flat/convex opposite-curvature supports that only fit locally."""
    a,b=points[0],points[-1];dx,dy=b[0]-a[0],b[1]-a[1];length=hypot(dx,dy)
    if length<=ERROR_MM:return False
    side=lambda p:(dx*(p[1]-a[1])-dy*(p[0]-a[0]))/length
    toward=side(center)
    if abs(toward)<=ERROR_MM:return False
    outward=lambda p:-side(p)*(1 if toward>0 else -1)
    mid=LineString(points).interpolate(.5,normalized=True).coords[0]
    middle=[outward(p) for p in points if .25*length<=
            ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length<=.75*length]
    return outward(mid)>ERROR_MM and median(middle or [outward(mid)])>ERROR_MM


def flank_runs(rings, center, radius, excluded):
    """Whole consecutive native runs; split only for non-overlapping arc proof."""
    raw=[]
    for points in rings:
        good=[abs(hypot(p[0]-center[0],p[1]-center[1])-radius)<=FIT_MM and
              excluded.distance(Point(p))>ERROR_MM and
              LineString([points[i-1],p]).distance(Point(center))>=radius-FIT_MM
              for i,p in enumerate(points)]
        if not any(good):continue
        first=next((i for i,v in enumerate(good) if not v),0);run=[]
        for offset in range(len(points)+1):
            i=(first+offset)%len(points)
            if good[i]:run.append(points[i])
            else:
                if len(run)>=3:raw.append(run)
                run=[]
        if len(run)>=3:raw.append(run)
    # Retain complete runs and nested contiguous source intervals. A small
    # fixed sector split must not determine the fitted radius. Dyadic windows
    # admit several support lengths without board-specific angular sectors.
    runs={}
    for run in raw:
        edges=[0]
        for i in range(1,len(run)):
            if arc_span(run[edges[-1]:i+1],center)>=10:edges.append(i)
        if edges[-1]!=len(run)-1:edges.append(len(run)-1)
        intervals=[run]
        for start in range(len(edges)-1):
            for width in (1,2,4,8):
                if start+width<len(edges):intervals.append(run[edges[start]:edges[start+width]+1])
        for r in intervals:
            if (len(r)>=3 and 10<=arc_span(r,center)<180 and
                    curves_away_from_center(r,center)):
                runs[tuple(r)]=r
    return sorted(runs.values(),key=lambda r:(-arc_span(r,center),tuple(r)))


def patches(body, center, native_radius, fit, *, maximum_depth_mm=.100, rejected=None):
    """Generate complete connected inward excursions at a native centre.

    `fit` is one of the existing source-bound constructors. The search envelope
    is explicit bounded discovery, not a larger geometric acceptance tolerance.
    """
    # The nearest original material and the unchanged depth bound determine
    # the search annulus. Do not assume a board-specific pad clearance/radius.
    nearest=body.distance(Point(center))
    outer=max(native_radius,nearest)+maximum_depth_mm+FIT_MM
    rejected=[] if rejected is None else rejected
    local=body.intersection(box(center[0]-outer,center[1]-outer,
                                center[0]+outer,center[1]+outer))
    rings=list(source_rings(local))
    radii=[hypot(x-center[0],y-center[1]) for x,y in get_coordinates(local)
           if native_radius+ERROR_MM<hypot(x-center[0],y-center[1])<outer-ERROR_MM]
    if len(radii)<6:return []
    counts=Counter(round(r/FIT_MM) for r in radii)
    seed=max(counts,key=lambda k:(counts[k],-k))*FIT_MM
    selected=[r for r in radii if abs(r-seed)<=FIT_MM]
    if len(selected)<6:return []
    radius=median(selected)
    initial=[g for g in parts(local.intersection(Point(center).buffer(radius,quad_segs=512)))
             if g.area>1e-12 and radius-g.distance(Point(center))>FIT_MM]
    if not initial:return []
    # Every physical piece at this centre uses ONE source-supported circle.
    # The reference is chosen before cause/area acceptance; it cannot be tuned
    # independently per bump or iteratively erode its own support flanks.
    excluded=local.intersection(Point(center).buffer(max(native_radius,radius-FIT_MM),quad_segs=512))
    runs=flank_runs(rings,center,radius,excluded)
    best=None;reasons=set();candidates=[]
    from itertools import combinations
    from shapely.ops import unary_union
    from src.bulk_edge_restore import circular_flank_measurements
    survey_domain=unary_union(initial).envelope.buffer(.01).envelope
    for first,second in combinations(runs,2):
        try:
            fitted,residual,spans=circular_flank_measurements(first,second,center)
        except ValueError as exc:
            reasons.add(str(exc));continue
        if fitted<=native_radius+ERROR_MM:continue
        if any(LineString(run).distance(Point(center))<fitted-FIT_MM for run in (first,second)):
            continue
        key=(abs(fitted-radius),-sum(spans),residual,tuple(first),tuple(second))
        candidates.append((key,first,second))
    # Fit selection is independent of the area classifier. Evaluate source
    # support in a fixed order, then accept the first complete geometric proof.
    for key,first,second in sorted(candidates):
        _,edge,evidence=fit(first,second,survey_domain)
        fitted=evidence['radius_mm']
        caps=[g for g in parts(local.intersection(Point(center).buffer(fitted,quad_segs=512)))
              if g.area>1e-12 and fitted-g.distance(Point(center))>FIT_MM]
        if not caps or any(g.intersection(LineString(run)).length>ERROR_MM
                           for g in caps for run in (first,second)):
            continue
        best=(key,caps,first,second);break
    if best is None:
        rejected.append(dict(reason='TWO_UNTOUCHED_NATIVE_CIRCULAR_FLANKS_NOT_ESTABLISHED',
                             bounds_mm=list(survey_domain.bounds),reference_failures=sorted(reasons)))
        return []
    _,caps,first,second=best
    found=[]
    for cap in caps:
        domain=box(*cap.bounds).buffer(.01).envelope
        _,edge,evidence=fit(first,second,domain)
        x,y=cap.centroid.coords[0];d=hypot(x-center[0],y-center[1])
        if d<=0:continue
        backing=(center[0]+(x-center[0])*(evidence['radius_mm']+.2)/d,
                 center[1]+(y-center[1])*(evidence['radius_mm']+.2)/d)
        connected=None
        if not body.covers(Point(backing).buffer(.125,quad_segs=128)):
            backing=(center[0]+(x-center[0])*(evidence['radius_mm']+2*ERROR_MM)/d,
                     center[1]+(y-center[1])*(evidence['radius_mm']+2*ERROR_MM)/d)
            connected=next((i for i,p in enumerate(parts(body)) if p.area>=1 and
                            p.covers(Point(backing)) and cap.difference(p).area<=1e-12),None)
            if connected is None:
                rejected.append(dict(reason='CONNECTED_BROAD_COPPER_BACKING_REQUIRED',bounds_mm=list(cap.bounds)))
                continue
        if cap.difference(edge.buffer(maximum_depth_mm,quad_segs=64)).area>1e-12:
            rejected.append(dict(reason='CIRCULAR_DEPTH_LIMIT',bounds_mm=list(cap.bounds)))
            continue
        evidence.update(discovery='NATIVE_CENTER_AND_MAXIMAL_CONSECUTIVE_RADIAL_SOURCE_RUNS',
            reference_search_outer_radius_mm=outer,
            reference_selection='ONE_CIRCLE; ROBUST_SOURCE_RADIAL_MODE; UNTOUCHED_ANGULAR_SUPPORT; AREA_NOT_USED',
            source_radial_mode_mm=radius,
            complete_physical_protrusion_sha256=fingerprint(cap.normalize()))
        found.append(dict(domain=domain,removal_mask=cap,smooth_edge=edge,
                          reference_evidence=evidence,backing_point=backing,
                          connected_broad_polygon=connected))
    return found


def bind_native_ring(body, sections, evidence, cap, center):
    """Bind both complete source flanks and the bump to one native ring.

    Local overlay output can reverse a ring. Restore the authenticated native
    edge order; a clipped chord, skipped edge, or another hole cannot qualify.
    """
    from bisect import bisect_right
    from src.indexed_polygon_distance import boundary_rings
    rings=boundary_rings(body);starts=[r['first'] for r in rings]
    edges={};deep=nearest_points(cap,Point(center))[0];deep_rings=set()
    for index,part in sections:
        r=rings[bisect_right(starts,index)-1];identity=(r['polygon'],r['ring'])
        coords=list(part.coords)
        for a,b in zip(coords,coords[1:]):edges.setdefault((tuple(a),tuple(b)),set()).add(identity)
        if part.distance(deep)<=ERROR_MM:deep_rings.add(identity)
    common=deep_rings;normalized={};orders=[]
    for key in ('first','second'):
        points=[tuple(p) for p in evidence[key]]
        forward=[edges.get((a,b),set()) for a,b in zip(points,points[1:])]
        reverse=[edges.get((b,a),set()) for a,b in zip(points,points[1:])]
        first=set.intersection(*forward) if forward else set()
        second=set.intersection(*reverse) if reverse else set()
        if first:
            normalized[key]=points;orders.append('NATIVE_FORWARD');common=common&first
        elif second:
            normalized[key]=list(reversed(points));orders.append('RESTORED_NATIVE_FORWARD');common=common&second
        else:raise ValueError('CIRCULAR_FLANK_NOT_A_COMPLETE_CONSECUTIVE_NATIVE_SOURCE_RUN')
    if len(common)!=1:raise ValueError('CIRCULAR_FLANKS_AND_BUMP_NOT_ONE_NATIVE_RING')
    return normalized,next(iter(common)),orders


def discover(rows, original, revision, progress=lambda **event: None, *, prepared_owners=()):
    """Survey native centres against their nearest independent broad owner.

    This is bounded source-supported discovery, not a declaration that every
    arbitrary curved contour is a dispensable defect. Unqualified references
    remain in the saved coverage; no pinned case identity is consulted.
    """
    from src.large_copper_discovery import select_cause
    from src.viewer_abi.publisher import digest
    from shapely import to_wkb
    broad={o:g for o,g in revision.owners.items() if g.area>=1 and
           not g.buffer(-.125,quad_segs=128).is_empty}
    centres={}
    for sid,row in rows.items():
        md=row['metadata'];kind=row['kind'];refs=[]
        if kind=='circle' and md.get('center_mm') is not None and md.get('radius_mm',0)>0:
            refs=[(md['center_mm'],md['radius_mm'],None)]
        elif kind=='stroke' and md.get('source_kind')=='Line' and len(md.get('route_points_mm',[]))==2:
            width=md.get('original_width_mm');ap=md.get('aperture_family',[])
            if (isinstance(width,(int,float)) and width>0 and len(ap)==2 and ap[0]=='C' and
                    abs(ap[1]-width)<=1e-12):
                refs=[(p,width/2,i) for i,p in enumerate(md['route_points_mm'])]
        own=revision.membership[sid]
        if len(own)!=1:continue
        for center,radius,endpoint in refs:
            centres.setdefault(tuple(center),[]).append((sid,radius,endpoint,own[0]))
    features=[];findings=[];coverage=[];seen=set()
    prepared_owners=set(prepared_owners)
    weight=len(centres)*768+len(broad)*256
    revision.context._charge(weight)
    try:
        for ordinal,(center,refs) in enumerate(centres.items()):
            if ordinal%100==0:
                progress(phase='circular_discovery',native_centres_surveyed=ordinal+1,
                         native_centres=len(centres),candidates=len(findings))
            # Same native centre is one reference, regardless of duplicated
            # flashes/incident strokes. The widest actual fixed source bounds
            # its interior; original source order breaks identical aliases.
            sid,native_radius,endpoint,fixed_owner=max(refs,key=lambda r:r[1])
            row=dict(rows[sid],source_id=sid);point=Point(center)
            boundary_lines=None
            if fixed_owner in prepared_owners:
                window=box(center[0]-native_radius-2*ERROR_MM,center[1]-native_radius-2*ERROR_MM,
                           center[0]+native_radius+2*ERROR_MM,center[1]+native_radius+2*ERROR_MM)
                boundary_lines=[part for _,part in revision.context.boundary_sections(revision.owners[fixed_owner],window)]
            exposure,cap_sha=native_exposure(revision.owners[fixed_owner],center,native_radius,boundary_lines=boundary_lines)
            if exposure<10:
                coverage.append(dict(kind='NATIVE_REFERENCE_INTERIOR',owner=fixed_owner,
                    reference_source_id=sid,center_mm=list(center),exposed_native_degrees=exposure,
                    unsupported_edge_count=0,completeness='HIDDEN_NATIVE_CAP_NOT_A_REFERENCE; ORIGINAL_COPPER_UNCHANGED'))
                continue
            def bbox_distance(item):
                x0,y0,x1,y1=item[1].bounds
                return hypot(max(x0-center[0],0,center[0]-x1),max(y0-center[1],0,center[1]-y1))
            best=None;distance=float('inf')
            for owner,body in sorted(((o,b) for o,b in broad.items() if o!=fixed_owner),key=bbox_distance):
                lower=bbox_distance((owner,body))
                if lower>distance+ERROR_MM:break
                actual=body.distance(point)
                if actual<distance:
                    best=(owner,body);distance=actual
            if best is None:continue
            owner,body=best
            def fit(first,second,domain):
                if endpoint is None:
                    return fit_circular_void_flanks(first,second,center,domain)
                return fit_circular_stroke_end_flanks(first,second,row,original[sid],endpoint,domain)
            rejected=[]
            proposed=patches(body,center,native_radius,fit,rejected=rejected)
            coverage.append(dict(kind='NATIVE_CIRCULAR_REFERENCE_SURVEY',owner=owner,
                reference_source_id=sid,reference_owner=fixed_owner,center_mm=list(center),
                nearest_original_material_mm=distance,proposals=len(proposed),
                unsupported_edge_count=0,reference_rejections=rejected,
                completeness='NEAREST_INDEPENDENT_BROAD_OWNER; OTHER_CURVES_NOT_ESTABLISHED'))
            for feature in proposed:
                cap=feature['removal_mask'];signature=fingerprint(cap.normalize())
                if signature in seen:continue
                seen.add(signature)
                cause,candidates,error=select_cause(rows,original,revision,cap)
                finding=dict(index=len(findings),owner=owner,bounds_mm=list(feature['domain'].bounds),
                    physical_protrusion_area_mm2=cap.area,mask_sha256=signature,status='unresolved',
                    reason=error or 'CAUSE_NOT_ESTABLISHED',causing_candidates=[c['source_id'] for c in candidates],
                    causing_contributions=candidates,reference_source_id=sid,
                    reference_family='NATIVE_PAD_CENTERED_CIRCULAR_VOID' if endpoint is None else
                                     'NATIVE_ROUND_STROKE_ENDPOINT_CIRCULAR_VOID')
                findings.append(finding)
                if error:continue
                finding.update(causing_source_id=cause,original_feature_area_mm2=original[cause].area,
                               area_fraction=cap.area/original[cause].area)
                if rows[cause]['kind']=='rectangle':
                    finding.update(status='ignored',reason='RECTANGULAR_BUMPS_DEFERRED_BY_POLICY');continue
                # Authenticate actual flank vertices using the SAME retained
                # ordered boundary sections as T02/T05; crop-created vertices
                # cannot become source evidence.
                sections=revision.context.boundary_sections(body,box(center[0]-distance-.104,
                    center[1]-distance-.104,center[0]+distance+.104,center[1]+distance+.104))
                prepared_owners.add(owner)
                native={tuple(p) for _,part in sections for p in part.coords}
                evidence=feature['reference_evidence']
                if any(tuple(p) not in native for k in ('first','second') for p in evidence[k]):
                    finding['reason']='CIRCULAR_FLANK_VERTEX_NOT_AUTHENTICATED';continue
                try:
                    normalized,ring_id,orders=bind_native_ring(body,sections,evidence,cap,center)
                except ValueError as exc:
                    finding['reason']=str(exc);continue
                _,native_edge,native_fit=fit(normalized['first'],normalized['second'],feature['domain'])
                if native_fit['radius_mm']!=evidence['radius_mm']:
                    raise ValueError('NATIVE_SOURCE_ORDER_CHANGED_CIRCULAR_REFERENCE')
                evidence.update(native_fit,source_polygon_index=ring_id[0],source_ring_index=ring_id[1],
                                source_order=orders)
                feature['smooth_edge']=native_edge
                evidence.update(source_sha256=revision.context.binding['source'].get('source_sha256'),
                    source_revision=revision.key,owner=owner,reference_source_id=sid,
                    reference_source_sha256=fingerprint(original[sid]),reference_owner=fixed_owner,
                    exposed_native_cap_degrees=exposure,native_cap_sha256=cap_sha,
                    source_boundary_section_ids=[i for i,_ in sections],
                    source_boundary_section_sha256=digest(b''.join(to_wkb(g) for _,g in sections)))
                evidence['native_exposure_preparation']='RETAINED_SHARED_T02_T05_32_EDGE' if boundary_lines is not None else 'LOCAL_ORIGINAL_SOURCE_SURVEY'
                feature.update(causing_id=cause,reference_owner=fixed_owner,
                    reference_source_ids=[sid],
                    finding_index=finding['index'],rule='AREA_NOISE')
                features.append(feature)
            if ordinal%100==0:
                progress(phase='circular_discovery',native_centres_surveyed=ordinal+1,
                         native_centres=len(centres),candidates=len(findings))
    finally:
        revision.context.weight-=weight
    return features,findings,coverage
