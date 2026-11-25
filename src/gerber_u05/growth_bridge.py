"""Local completion of admitted widening at native straight/arc seams.

The constructor receives a prepared allowance. It has no scene query, owner or
clearance API. A rejected proposal returns the unchanged admitted widening.
"""
import math
import numpy as np
from shapely.geometry import Point, Polygon,LineString
from shapely import from_wkb,to_wkb
from time import perf_counter
from shapely.ops import unary_union
from src.native_inventory import ERROR_MM
from .boundary_finish import key, sharp_points, polygons,compile_graph,new_pockets,component_count
from .finite_profile_union import polygonal
from .ribbon_profile import frame
from .side_profile import extent
from .smooth_transition import certify, tessellate, value


def meaningful_shoulders(image,points):
    """Retain real turns; identify numerical zero-area edge retraces.

    Exact overlays can leave a valid, nearly collinear hairpin along coincident
    rails. Neither its tiny height nor its area exceeds existing native error.
    The geometry is unchanged; right-angle width steps still fail.
    """
    wanted={tuple(p)for p in points};noise=set()
    for face in polygons(image):
        for ring in[face.exterior,*face.interiors]:
            coords=np.asarray(ring.coords)[:-1]
            for i,p in enumerate(coords):
                token=tuple(p)
                if token not in wanted:continue
                a=p-coords[i-1];b=coords[(i+1)%len(coords)]-p
                cross=abs(float(a[0]*b[1]-a[1]*b[0]))
                # The retrace depth is measured against the long rail, not
                # its tiny returning edge. A long sub-coordinate-error sliver
                # can have area above ERROR_MM squared without being a width
                # step. This classifies findings only; no copper is changed.
                if float(a@b)<0 and cross/max(1e-30,max(np.linalg.norm(a),np.linalg.norm(b)))<=ERROR_MM:
                    noise.add(token)
    return [p for p in points if tuple(p)not in noise]


def source_spans(rows,chain):
    if 'source_intervals'in chain:
        return [(a,b,s,rows[s]['metadata'].get('route_kind','segment'))for a,b,s in chain['source_intervals']]
    spans=[]
    for sid in chain['source_ids']:
        pts=rows[sid]['metadata']['route_points_mm']
        a,b=sorted(chain['line'].project(Point(p))for p in(pts[0],pts[-1]))
        spans.append((a,b,sid,rows[sid]['metadata'].get('route_kind','segment')))
    return spans


def affected_sections(rows,chain,before,after,*,interior_nodes=(),frozen_sections=None):
    """Refresh actually changed interior sections, including swept end caps.

    A repair domain can touch a seam just beyond its centreline interval.
    Its required section must come from that source's emitted copper, not
    from a wider, overlapping neighbour in the complete chain.
    """
    result={};length=chain['line'].length
    for a,b,sid,_ in source_spans(rows,chain):
        if to_wkb(before[sid])==to_wkb(after[sid]):continue
        pts=rows[sid]['metadata']['route_points_mm'];p,n,_,_=frame(pts)
        ends=[np.asarray(chain['line'].interpolate(t).coords[0])for t in(a,b)]
        forward=sum(float(np.linalg.norm(v-np.asarray(q)))for v,q in zip(ends,(pts[0],pts[-1])))
        reverse=sum(float(np.linalg.norm(v-np.asarray(q)))for v,q in zip(ends,(pts[-1],pts[0])))
        stations=(a,b)if forward<=reverse else(b,a)
        delta=before[sid].symmetric_difference(after[sid])
        for j,station in zip((0,-1),stations):
            if not 4*ERROR_MM<station<length-4*ERROR_MM and key(pts[j])not in interior_nodes:continue
            center=np.asarray(pts[j]);normal=n[j]/np.linalg.norm(n[j]);reach=chain['width']+.2
            obligation=(frozen_sections or {}).get((sid,key(pts[j])))
            if obligation is not None:
                # The qualified joint can use a transported/miter frame.
                # Refresh in that same frame rather than missing a change
                # which does not reach the raw source-normal plane.
                section=obligation['section'];lower=np.asarray(section['lower_mm']);upper=np.asarray(section['upper_mm'])
                center=(lower+upper)/2;normal=unit_section=upper-lower
                normal=unit_section/np.linalg.norm(unit_section)
                reach=max(reach,float(np.linalg.norm(unit_section))/2+.2)
            probe=LineString([center-normal*reach,center+normal*reach])
            if delta.distance(probe)>2*ERROR_MM:continue
            size=extent(after[sid],center,normal,reach)
            if size is not None:result[sid,key(pts[j])]=dict(normal=normal.tolist(),
                lower_mm=(center-normal*size[1]).tolist(),upper_mm=(center+normal*size[0]).tolist(),
                policy=('CERTIFIED_FLEXIBLE_NATIVE_JUNCTION'if interior_nodes else'CERTIFIED_GAP_BRIDGE')+
                    '; ACTUAL_AFFECTED_SOURCE_SECTION; LOCAL_NONNEGATIVE_GROWTH')
    return result


def seams(rows,chain):
    ends={}
    for a,b,s,kind in source_spans(rows,chain):
        for t in(a,b):ends.setdefault(round(t,10),set()).add(kind)
    return [t for t,kinds in sorted(ends.items())if 'arc'in kinds and 'segment'in kinds
            and 4*ERROR_MM<t<chain['line'].length-4*ERROR_MM]


def change_budget(before,after,domain):
    """Physical copper accounting; a recession is confined to its bridge."""
    added=after.difference(before);removed=before.difference(after);reasons=[]
    if added.area<=ERROR_MM**2:reasons.append('NO_VISIBLE_GAP_COMPLETION')
    if added.area+1e-12<removed.area:reasons.append('LOCAL_GROWTH_LOSS')
    if removed.difference(domain).area>1e-12:reasons.append('RECESSION_OUTSIDE_BRIDGE_WINDOW')
    return added,removed,reasons


def sample(chain,extra=()):
    p,n,t,length=frame(chain['points'],extra_stations=extra)
    raw=[]
    for center,normal in zip(p,n):
        size=float(np.linalg.norm(normal))
        section=extent(chain['body'],center,normal/size,chain['width']+.2)
        raw.append([0.,0.]if section is None else [max(0.,v/size-chain['width']/2)for v in section[::-1]])
    return p,n,t,np.asarray(raw),length


def rates_for(p,n,t,width,extra,slope):
    axes=np.diff(p,axis=0);u=axes/np.linalg.norm(axes,axis=1)[:,None]
    v=np.column_stack((-u[:,1],u[:,0]));dn=np.diff(n,axis=0)/np.diff(t)[:,None]
    radius=width/2+extra
    parallel=np.abs(np.sum(dn*u,axis=1))*radius
    transverse=np.abs(np.sum(dn*v,axis=1))*radius
    n_parallel=np.maximum(np.abs(np.sum(n[:-1]*u,axis=1)),np.abs(np.sum(n[1:]*u,axis=1)))
    n_transverse=np.maximum(np.abs(np.sum(n[:-1]*v,axis=1)),np.abs(np.sum(n[1:]*v,axis=1)))
    return np.maximum(0.,slope*(1-parallel)-transverse)/(1.5*np.maximum(n_transverse+slope*n_parallel,1e-30))


def cone_alignment(axis,native_axis,radius_change):
    """Bound both aperture tangents relative to the unchanged source axis."""
    distance=float(np.linalg.norm(axis))
    if distance<=1e-14 or np.linalg.norm(native_axis)<=1e-14:raise ValueError('BRIDGE_DEGENERATE_APERTURE_SEGMENT')
    ratio=abs(float(radius_change))/distance
    if ratio>=1:raise ValueError('BRIDGE_APERTURE_HAS_NO_EXTERNAL_TANGENT')
    deviation=abs(math.atan2(float(axis[0]*native_axis[1]-axis[1]*native_axis[0]),float(axis@native_axis)))
    return math.degrees(deviation+math.asin(ratio))


def exposed_alignment(shape,positions,native_positions,radii,angle):
    """Only external tangent rails can impose a visible widening slope.

    Fully buried aperture segments and sub-error rail slivers do not form
    an emitted edge. Retain their count rather than calling them smooth.
    """
    boundary=shape.boundary.buffer(ERROR_MM);maximum=0.;hidden=0;internal=0.
    for i in range(len(positions)-1):
        axis=positions[i+1]-positions[i];distance=float(np.linalg.norm(axis))
        if distance<=1e-14:continue
        native=native_positions[i+1]-native_positions[i];dr=radii[i+1]-radii[i]
        alignment=cone_alignment(axis,native,dr);internal=max(internal,alignment)
        u=axis/distance;v=np.array([-u[1],u[0]]);ratio=float(dr)/distance
        normals=[-ratio*u+sign*math.sqrt(max(0.,1-ratio**2))*v for sign in(-1,1)]
        rails=[LineString([positions[i]+radii[i]*normal,positions[i+1]+radii[i+1]*normal])for normal in normals]
        visible=any(rail.intersection(boundary).length>2*ERROR_MM for rail in rails)
        if not visible:hidden+=1;continue
        if alignment>angle+1e-8:raise ValueError('BRIDGE_NATIVE_EDGE_ALIGNMENT_ANGLE_EXCEEDED')
        maximum=max(maximum,alignment)
    return maximum,hidden,internal


def ribbon(chain,first,last,start,end,angle):
    """Aperture sweep with a certified 10-degree tangent-cone opening.

    Native bends are carried by the centre trajectory. Radius variation is
    bounded in its actual arclength, avoiding nonphysical inward offset folds.
    """
    length=last-first
    p,n,t,_=frame(chain['points'],extra_stations=[first,last])
    keep=(t>=first-1e-12)&(t<=last+1e-12);p,n,t=p[keep],n[keep],t[keep]
    fractions=np.clip((t-first)/length,0.,1.);smooth=3*fractions**2-2*fractions**3
    shifts=(start[1]-start[0])/2+smooth*((end[1]-end[0])-(start[1]-start[0]))/2
    normals=n/np.linalg.norm(n,axis=1)[:,None]
    centers=p+normals*shifts[:,None]
    lengths=np.linalg.norm(np.diff(centers,axis=0),axis=1);stations=np.r_[0.,np.cumsum(lengths)]
    if stations[-1]<=1e-12:raise ValueError('BRIDGE_DEGENERATE_APERTURE_TRAJECTORY')
    radii=[chain['width']/2+float(start.sum())/2,chain['width']/2+float(end.sum())/2]
    radius_proof=certify([radii[0]],[radii[1]],float(stations[-1]),maximum_side_slope=math.sin(math.radians(angle)))
    if not radius_proof['passed']:raise ValueError('BRIDGE_FIELD_ANGLE_EXCEEDED')
    knots=list(stations)
    knots.extend(x for x,_ in tessellate(radius_proof['controls'][0],stations[-1],error_mm=ERROR_MM/10))
    knots=np.asarray(sorted(set(min(float(stations[-1]),max(0.,float(x)))for x in knots)))
    positions=np.column_stack([np.interp(knots,stations,centers[:,j])for j in(0,1)])
    native_positions=np.column_stack([np.interp(knots,stations,p[:,j])for j in(0,1)])
    native=np.interp(knots,stations,t)
    rs=np.asarray([value(radius_proof['controls'][0],x/stations[-1])for x in knots])
    disks=[Point(point).buffer(float(radius),quad_segs=128)for point,radius in zip(positions,rs)]
    cells=[]
    for i in range(len(disks)-1):
        distance=float(np.linalg.norm(positions[i+1]-positions[i]))
        if distance<=1e-14:continue
        ratio=abs(float(rs[i+1]-rs[i]))/distance
        if ratio>math.sin(math.radians(angle))+1e-10:raise ValueError('BRIDGE_APERTURE_CONE_ANGLE_EXCEEDED')
        cells.append((i,disks[i].union(disks[i+1]).convex_hull))
    shape=polygonal(unary_union([g for _,g in cells]))
    maximum,hidden,internal=exposed_alignment(shape,positions,native_positions,rs,angle)
    field_proof=certify(start.tolist(),end.tolist(),length,maximum_side_slope=math.tan(math.radians(angle)))
    if not field_proof['passed']:raise ValueError('BRIDGE_FACE_FIELD_ANGLE_EXCEEDED')
    return shape,dict(maximum_materialized_alignment_angle_degrees=maximum,
        maximum_field_slope=radius_proof['actual_maximum_side_slope'],endpoint_derivatives=[0.,0.],
        controls=field_proof['controls'],radius_controls=radius_proof['controls'][0],
        radius_interval_mm=[float(stations[0]),float(stations[-1])],
        angle_proof='EXPOSED_ROUND_APERTURE_TANGENT_RAILS; ACTUAL_NATIVE_AXIS_ALIGNMENT',
        hidden_internal_aperture_segments=hidden,maximum_internal_axis_angle_degrees=internal,
        inherited_native_bend_turns=True,interval_mm=[first,last],stations=len(knots)),(p,n,t,cells,native)


def proposals(rows,chain,caps,angle):
    """Discover short total-width dips between two widened native sections."""
    joins=seams(rows,chain)
    if not joins or chain['fixed']:return []
    width=chain['width'];reach=max(.3,6*width)
    p,n,t,raw,length=sample(chain,[x for join in joins for x in(max(0.,join-reach),join,min(chain['line'].length,join+reach))])
    spans=source_spans(rows,chain);totals=raw.sum(axis=1);results=[];taken=[]
    def cap_at(station):
        return max([caps.get(s,width)for a,b,s,_ in spans if a-1e-9<=station<=b+1e-9]or[width])-width
    for join in joins:
        if any(a<=join<=b for a,b in taken):continue
        lo=max(0.,join-reach);hi=min(length,join+reach)
        left=np.flatnonzero((t>=lo)&(t<join));right=np.flatnonzero((t>join)&(t<=hi))
        if not len(left)or not len(right):continue
        level=min(float(totals[left].max()),float(totals[right].max()))
        if level<=8*ERROR_MM:continue
        # A side-to-side allocation change is not a naked section. Require a
        # material deficit in total width near the actual straight/arc seam.
        near=np.flatnonzero((t>=join-min(.05,width))&(t<=join+min(.05,width)))
        if not len(near):continue
        bottom=int(near[np.argmin(totals[near])])
        if level-totals[bottom]<=max(8*ERROR_MM,.12*level):continue
        donors_left=np.flatnonzero((t>=lo)&(t<t[bottom])&(totals>=level-2*ERROR_MM))
        donors_right=np.flatnonzero((t>t[bottom])&(t<=hi)&(totals>=level-2*ERROR_MM))
        if not len(donors_left)or not len(donors_right):continue
        first,last=int(donors_left[-1]),int(donors_right[0])
        record=dict(join_station_mm=join,point_mm=list(chain['line'].interpolate(join).coords[0]),
            source_ids=list(chain['source_ids']),status='UNRESOLVED',
            baseline_growth_area_mm2=chain['body'].difference(chain['floor']).area,
            naked_station_mm=float(t[bottom]),baseline_naked_growth_width_mm=float(totals[bottom]))
        reason='BRIDGE_REQUIRES_LONGER_PREPARED_INTERVAL'
        for attempt in range(7):
            start,end=raw[first].copy(),raw[last].copy();a,b=float(t[first]),float(t[last])
            try:patch,proof,grid=ribbon(chain,a,b,start,end,angle)
            except ValueError as error:
                if not str(error).startswith('BRIDGE_'):raise
                reason=str(error)
            else:
                stations=t[first:last+1];fraction=(stations-a)/(b-a);smooth=3*fraction**2-2*fraction**3
                fields=start[None,:]+smooth[:,None]*(end-start)[None,:]
                ceiling=np.asarray([cap_at(x)for x in stations])
                # Existing admitted widths remain the predecessor, never a new
                # permission. A new bridge must obey the stage's width caps.
                if (fields.sum(axis=1)>np.maximum(ceiling,totals[first:last+1])+2*ERROR_MM).any():reason='PREPARED_TOTAL_WIDTH_CAP'
                elif patch.difference(chain['body']).area<=ERROR_MM**2:reason='NO_MATERIAL_GAP_COMPLETION'
                else:
                    p2,n2,t2,sweep_cells,native_stations=grid;radius=width+max(float(start.max()),float(end.max()))+.02
                    low=p2-n2*radius;high=p2+n2*radius
                    domain=polygonal(unary_union([Polygon([low[i],low[i+1],high[i+1],high[i]]).convex_hull for i in range(len(p2)-1)]))
                    record.update(profile=proof,interval_mm=[a,b],domain_wkb_hex=domain.wkb_hex,
                        gap_reference_wkb_hex=patch.wkb_hex,requested_patch_area_mm2=patch.difference(chain['body']).area,
                        attempts=attempt+1)
                    cell_domains={}
                    for k,cell in sweep_cells:
                        station=(native_stations[k]+native_stations[k+1])/2
                        for x,y,sid,_ in spans:
                            if x-1e-10<=station<=y+1e-10:cell_domains.setdefault(sid,[]).append(cell)
                    record['source_domains_wkb_hex']={s:polygonal(unary_union(g)).wkb_hex for s,g in cell_domains.items()}
                    results.append((record,patch));taken.append((a,b));break
            pad=max(.01,.4*(b-a))
            first=max(int(left[0]),int(np.searchsorted(t,a-pad,side='right')-1))
            last=min(int(right[-1]),int(np.searchsorted(t,b+pad,side='left')))
        else:record.update(reason=reason,interval_mm=[float(t[first]),float(t[last])]);results.append((record,None))
    return results


def constrained_reference(chain,record,allowance,caps,rows,angle):
    """Reallocate only a prepared gap window; no foreign search or new budget."""
    from shapely.ops import substring
    from .side_profile import allowance as ray_allowance
    from .boundary_finish import minorant,materialize,AlignmentRejected
    first,last=record['interval_mm'];line=substring(chain['line'],first,last)
    points=list(line.coords)
    try:p,n,t,length=frame(points)
    except ValueError as error:
        if str(error)not in ('NONDEGENERATE_NATIVE_PROFILE_PATH_REQUIRED','RESIDUAL_REVERSAL_JOIN_UNSUPPORTED','RESIDUAL_MITER_OUTLIER'):raise
        return None
    width=chain['width'];half=width/2
    spans=source_spans(rows,chain);wanted=[];values=[]
    controls=record['profile']['controls']
    for center,normal,station in zip(p,n,t):
        f=min(1.,max(0.,station/length));goal=np.asarray([value(c,f)for c in controls]);wanted.append(goal)
        size=float(np.linalg.norm(normal));unit=normal/size
        old=extent(chain['body'],center,unit,width+.2)
        existing=np.asarray([0.,0.]if old is None else[max(0.,v/size-half)for v in old[::-1]])
        free=np.asarray([max(0.,ray_allowance(allowance['forbidden'],center,sign*unit,width+.2)/size-half-2*ERROR_MM)for sign in(-1,1)])
        budget=np.maximum(existing,free);v=np.minimum(goal,budget)
        cap=max([caps.get(s,width)for a,b,s,_ in spans if a-1e-9<=first+station<=b+1e-9]or[width])-width
        cap=max(cap,float(existing.sum()))
        if v.sum()>cap:v*=cap/v.sum()
        values.append(v)
    values=np.asarray(values);wanted=np.asarray(wanted)
    local=dict(chain,points=points,line=line,floor=chain['floor'].intersection(from_wkb(bytes.fromhex(record['domain_wkb_hex']))),
        stations=t,values=values,rates=rates_for(p,n,t,width,float(values.max()),math.tan(math.radians(angle))),local_controls=True)
    minorant(local)
    if max(np.max(np.abs(values[0]-wanted[0])),np.max(np.abs(values[-1]-wanted[-1])))>2*ERROR_MM:return None
    try:shape,proof=materialize(local,1.,math.tan(math.radians(angle)))
    except AlignmentRejected:return None
    if proof is None:return None
    radius=width+float(values.max())+.02;low=p-n*radius;high=p+n*radius;by_source={}
    for i in range(len(t)-1):
        station=first+(t[i]+t[i+1])/2
        cell=Polygon([low[i],low[i+1],high[i+1],high[i]]).convex_hull
        for a,b,s,_ in spans:
            if a-1e-10<=station<=b+1e-10:by_source.setdefault(s,[]).append(cell)
    value_record=dict(record,profile=dict(maximum_materialized_alignment_angle_degrees=proof['maximum_materialized_alignment_angle_degrees'],
        angle_proof='PREPARED_BUDGET_CUBICS; MATERIALIZED_NATIVE_RAILS',endpoint_derivatives=[0.,0.],
        local_stations_mm=t.tolist(),local_face_growth_mm=values.tolist()),
        source_domains_wkb_hex={s:shape.intersection(unary_union(cells)).wkb_hex for s,cells in by_source.items()})
    return value_record,shape


def run(rows,paths,bodies,original,caps,*,covered=(),supports=None,terminals=None,
        maximum_transition_angle_degrees=10.,prepare=None,progress=None):
    started=perf_counter();angle=maximum_transition_angle_degrees
    if type(angle)not in(int,float)or not math.isfinite(angle)or not 0<angle<45:raise ValueError('VALID_TRANSITION_ANGLE_REQUIRED')
    plans=[];working=dict(bodies);sections={};changed={};reports=[];checks=[]
    for batch in compile_graph(rows,paths,bodies,original,set(covered),supports or {}):
        for chain in batch['chains']:
            for record,patch in proposals(rows,chain,caps,angle):
                record.update(route_id=batch['identity'],route_ids=batch['route_ids'],kind='STRAIGHT_BEND_GAP',
                    optional_growth_withdrawn=False,maximum_transition_angle_degrees=angle)
                plans.append(dict(chain=chain,batch=batch,record=record,patch=patch))
    if prepare is None and any(p['patch']is not None for p in plans):raise ValueError('BRIDGE_PREPARED_ALLOWANCE_REQUIRED')
    allowances,preparation=prepare(plans)if prepare is not None else ({},dict(queries=0))
    for index,plan in enumerate(plans):
        record,patch,chain=plan['record'],plan['patch'],plan['chain']
        if patch is None:
            record.update(baseline_preserved=True,added_area_mm2=0.,removed_area_mm2=0.,net_growth_area_mm2=0.)
            reports.append(record);continue
        allowance=allowances[index];sources=chain['source_ids'];baseline={s:working[s]for s in sources}
        before=polygonal(unary_union(list(baseline.values())))
        domain=from_wkb(bytes.fromhex(record['domain_wkb_hex']))
        floor=polygonal(unary_union([original[s]for s in sources]))
        background=allowance['context'];entry=polygonal(unary_union([floor,background]))
        before_image=polygonal(unary_union([before,background]));accepted=None;failures=[]
        original_record=record;original_patch=patch
        constrained=None
        for variant,mode in((0,'ADD_ONLY'),(0,'LOCAL_RECESSION_WITH_GAP_GAIN'),(1,'ADD_ONLY'),(1,'LOCAL_RECESSION_WITH_GAP_GAIN')):
            if variant and constrained is None:constrained=constrained_reference(chain,original_record,allowance,caps,rows,angle)
            if variant and constrained is None:break
            record,patch=constrained if variant else(original_record,original_patch)
            trial={};floor_rejection=None
            for sid in sources:
                old=baseline[sid]
                addition=from_wkb(bytes.fromhex(record['source_domains_wkb_hex'][sid]))if sid in record['source_domains_wkb_hex']else Polygon()
                carrier=old if mode=='ADD_ONLY'else polygonal(unary_union([old.difference(domain),original[sid]]))
                from .source_trace_floor import preserve
                proposed=polygonal(unary_union([carrier,addition]))
                required=carrier
                try:
                    trial[sid],_=preserve(required,proposed)
                    if mode=='LOCAL_RECESSION_WITH_GAP_GAIN':
                        # Recession's carrier was itself an overlay. Validate
                        # the immutable source floor directly as well.
                        required=original[sid];proposed=trial[sid]
                        trial[sid],_=preserve(required,proposed)
                except ValueError as error:
                    if str(error)!='SOURCE_FLOOR_POSITIVE_COPPER_STILL_MISSING':raise
                    # This proposed overlay failed the unchanged floor check.
                    # Keep its operands as evidence and reject the proposal,
                    # rather than publishing it or withdrawing prior growth.
                    floor_rejection=dict(source_id=sid,carrier_wkb_hex=required.wkb_hex,
                        proposed_wkb_hex=proposed.wkb_hex,missing_area_mm2=required.difference(proposed).area)
                    break
            if floor_rejection is not None:
                failures.append(dict(mode=mode,prepared_budget_variant=variant,
                    reasons=['SOURCE_FLOOR_POSITIVE_COPPER_STILL_MISSING'],source_floor_rejection=floor_rejection))
                continue
            after=polygonal(unary_union(list(trial.values())));image=polygonal(unary_union([after,background]))
            added,removed,reasons=change_budget(before_image,image,domain)
            # Every alternative must fit the upper envelope reserved before
            # the batch. A locally reallocated field cannot enlarge it behind
            # a different proposal's already prepared dependencies.
            if added.difference(original_patch).area>1e-12:reasons.append('OUTSIDE_RESERVED_BRIDGE_ENVELOPE')
            if any(original[s].difference(trial[s]).area>1e-12 for s in sources):reasons.append('ORIGINAL_SOURCE_COPPER_REMOVED')
            if not added.is_empty and added.intersection(allowance['forbidden']).area>1e-12:reasons.append('OUTSIDE_PREPARED_GROWTH_ALLOWANCE')
            if patch.difference(image).area>max(1e-12,ERROR_MM**2):reasons.append('GAP_NOT_COVERED_BY_SERIALIZED_SOURCES')
            if component_count(after)>component_count(before):reasons.append('SOURCE_CHAIN_DISCONNECTED')
            if new_pockets(before_image,entry,image):reasons.append('NEW_POCKET')
            # The proposed patch is not its own outline oracle. Compare with
            # the retained widening so capsule/old-edge intersections cannot
            # introduce an unreported shoulder at either end of the bridge.
            points=sharp_points(image,before_image,angle)
            delta=polygonal(unary_union([added,removed]))
            # Round end caps extend beyond the flat recession window. The
            # existing outline check must cover all actual changed copper,
            # including those caps, rather than accepting an unseen end turn.
            remaining=meaningful_shoulders(image,[p for p in points if delta.distance(Point(p))<=2*ERROR_MM])
            if remaining:reasons.append('BRIDGE_OUTLINE_HAS_SHOULDER')
            # Check the emitted source image against its own prepared scalar
            # limits, including native seams inside the bridge. No scene scan.
            spans=source_spans(rows,chain);p2,n2,t2,_=frame(chain['points'],extra_stations=record['interval_mm'])
            for center,normal,station in zip(p2,n2,t2):
                if not record['interval_mm'][0]-1e-10<=station<=record['interval_mm'][1]+1e-10:continue
                size=float(np.linalg.norm(normal));span=extent(after,center,normal/size,chain['width']+.2)
                if span is None:reasons.append('SOURCE_CENTERLINE_NOT_COVERED');break
                cap=max([caps.get(s,chain['width'])for a,b,s,_ in spans if a-1e-9<=station<=b+1e-9]or[chain['width']])
                old=extent(before,center,normal/size,chain['width']+.2)
                admitted=0. if old is None else sum(old)/size
                if sum(span)/size>max(cap,admitted)+2*ERROR_MM:reasons.append('EMITTED_BRIDGE_WIDTH_CAP');break
            if reasons:
                failures.append(dict(mode=mode,prepared_budget_variant=variant,reasons=sorted(set(reasons)),added_area_mm2=added.area,removed_area_mm2=removed.area,
                    remaining_shoulders=len(remaining),remaining_points_mm=remaining));continue
            accepted=trial
            record.update(status='BRIDGED',mode=mode,added_area_mm2=added.area,removed_area_mm2=removed.area,
                net_growth_area_mm2=added.area-removed.area,remaining_shoulders=0,
                baseline_preserved=removed.area<=1e-12,original_removed_area_mm2=0.,allowance_neighbors=len(allowance['neighbors']))
            if failures:record['validation_attempts']=failures
            checks.append(dict(passed=True,remaining_shoulders=0,new_pockets=0,added_area_mm2=added.area,
                removed_area_mm2=removed.area,net_growth_area_mm2=added.area-removed.area,original_removed_area_mm2=0.))
            break
        if accepted is None:record=original_record
        if accepted is None:
            record.update(status='UNRESOLVED',reason='BASELINE_RETAINED; '+','.join(failures[-1]['reasons']),attempts=failures,
                added_area_mm2=0.,removed_area_mm2=0.,net_growth_area_mm2=0.,baseline_preserved=True)
        else:
            working.update(accepted)
            for s,g in accepted.items():
                if to_wkb(g)!=to_wkb(bodies[s]):changed[s]=polygonal(bodies[s].symmetric_difference(g))
            # Only a qualified bridge can supersede an optional interior
            # section. Original source floors and terminal sections stay fixed.
            sections.update(affected_sections(rows,chain,baseline,accepted))
        for k in('domain_wkb_hex','source_domains_wkb_hex','gap_reference_wkb_hex'):record.pop(k,None)
        reports.append(record)
        if progress:progress(dict(event='growth_gap_bridge',route_id=record['route_id'],status=record['status'],
            added_mm2=record['added_area_mm2'],removed_mm2=record['removed_area_mm2']))
    pending=terminals or []
    from .terminal_handoff import interior
    for r in pending:
        support=(supports or {}).get(r['route_id'],{});extras=list(support.values())if isinstance(support,dict)else[support]
        image=polygonal(unary_union([working[s]for s in r['source_ids']]+extras))
        floor=polygonal(unary_union([original[s]for s in r['source_ids']]+extras))
        region=from_wkb(bytes.fromhex(r['window_wkb_hex']))
        r['optional_scope_wkb_hex']=image.difference(floor).intersection(region).wkb_hex
        points=sharp_points(image,floor,angle);outside={tuple(p)for p in interior(points,[r])}
        r['points_mm']=[p for p in points if tuple(p)not in outside]
    pending=[r for r in pending if r['points_mm']]
    return working,changed,sections,dict(schema='t04-growth-gap-bridges/1',reports=reports,
        maximum_transition_angle_degrees=angle,smoothed=sum(r['status']=='BRIDGED'for r in reports),partial=0,
        unresolved=sum(r['status']=='UNRESOLVED'for r in reports),preserved_unresolved=True,
        chains=[],withdrawn_growth=[],finished_assembly_checks=checks,deferred_terminals=pending,
        local_controls=True,preparation=preparation,scene_indexes_built=0,clearance_queries=0,
        owner_reconstructions=0,complete_board_unions=0,original_copper_removed_mm2=0.,
        added_copper_mm2=sum(r.get('added_area_mm2',0.)for r in reports),
        removed_optional_copper_mm2=sum(r.get('removed_area_mm2',0.)for r in reports),wall_s=perf_counter()-started)
