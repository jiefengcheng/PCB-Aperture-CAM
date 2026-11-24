"""Reconcile rejected native interfaces by retracting optional widening.

Discovery is a saved endpoint/corner batch. This constructor consumes emitted
route operands and native adjacency; it owns no scene index or clearance search.
Only subtraction is admitted, followed by original-floor, component and pocket
checks. Raw group operands remain immutable construction evidence.
"""
from collections import defaultdict
from time import perf_counter
import math
import numpy as np
from shapely import to_wkb
from shapely.geometry import LineString,Point,Polygon
from shapely.ops import unary_union,substring
from shapely.errors import GEOSException
from .arc_membership import tangent
from .corner_transition import oriented,new_pocket_regions,joint_frame
from .side_profile import extent
from .ribbon_profile import build,frame
from .finite_profile_union import polygonal
from src.component_voids import parts
from src.original_copper_owners import OriginalOwners
from src.native_inventory import ERROR_MM
from src.stage_abi.store import digest


def key(point):return tuple(round(float(v),10)for v in point)


def sample(desc,end,body,normal=None):
    points=oriented(desc,end);center=np.asarray(points[0]);u=tangent(points,False)
    n=np.array([-u[1],u[0]])if normal is None else np.asarray(normal);step=min(2*ERROR_MM,LineString(points).length/4)
    at=center+u*step
    section=extent(body,at,n,desc['source_width_mm']*.75+.11)
    if section is None:raise ValueError('ACTUAL_NATIVE_INTERFACE_SECTION_REQUIRED')
    high,low=section
    return dict(normal=n.tolist(),lower_mm=(center-n*low).tolist(),upper_mm=(center+n*high).tolist()),low+high


def taper(desc,end,body,target,width_cap,*,maximum_side_slope=.25,span_factor=1.):
    """A finite C1 ribbon defines a removal mask, never new copper."""
    points=oriented(desc,end);path=LineString(points);width=desc['source_width_mm']
    own,_=sample(desc,end,body)
    n=np.asarray(own['normal']);same=float(n@target['normal'])>=0
    desired=dict(normal=(np.asarray(target['normal'])*(1 if same else -1)).tolist(),
        lower_mm=target['lower_mm']if same else target['upper_mm'],
        upper_mm=target['upper_mm']if same else target['lower_mm'])
    delta=max(np.linalg.norm(np.asarray(own[k])-desired[k])for k in('lower_mm','upper_mm'))
    required=max(.02,1.5*float(delta)/maximum_side_slope)
    length=min(path.length,required*span_factor)
    local=substring(path,0.,length);local_points=[list(point)for point in local.coords]
    _,normals,stations,_=joint_frame(desc,points,extra_stations=[length])
    i=int(np.argmin(abs(stations-length)));normal=normals[i]/np.linalg.norm(normals[i]);center=np.asarray(local_points[-1])
    section=extent(body,center,normal,width*.75+.11)
    if section is None:raise ValueError('ACTUAL_FAR_INTERFACE_SECTION_REQUIRED')
    far=dict(normal=normal.tolist(),lower_mm=(center-normal*section[1]).tolist(),upper_mm=(center+normal*section[0]).tolist())
    reference_cap=max(width_cap,float(np.linalg.norm(np.subtract(far['upper_mm'],far['lower_mm']))),float(np.linalg.norm(np.subtract(desired['upper_mm'],desired['lower_mm']))))+1e-12
    allowed,recipe=build(local_points,width,reference_cap,ends=[desired,far],direct_transition=True,maximum_side_slope=maximum_side_slope)
    recipe['unchanged_growth_cap_mm']=width_cap
    recipe['reference_profile_only']='OUTPUT_IS_STRICT_SUBSET_OF_PRECEDING_COPPER'
    # Restrict the cut to this native side of the joint and its taper span.
    # A small supported overlap removes coincident boundary ambiguity only.
    radius=width*.75+.11;scale=length+4*radius
    begin=np.asarray(points[0]);u=tangent(points,False);bn=np.array([-u[1],u[0]])
    fn=normal;fu=np.array([fn[1],-fn[0]])
    first=Polygon([begin+u*x+bn*y for x,y in[(-2*ERROR_MM,-scale),(scale,-scale),(scale,scale),(-2*ERROR_MM,scale)]])
    last=Polygon([center+fu*x+fn*y for x,y in[(-scale,-scale),(2*ERROR_MM,-scale),(2*ERROR_MM,scale),(-scale,scale)]])
    domain=local.buffer(radius,quad_segs=128).intersection(first).intersection(last)
    mask=polygonal(body.intersection(domain).difference(allowed))
    return mask,desired,dict(schema='t04-subtractive-native-interface/1',length_mm=length,
        maximum_side_slope=maximum_side_slope,profile=recipe,native_points_mm=local_points,source_width_mm=width,source_path_changed=False,
        copper_added_mm2=0.,width_policy='RETRACT_OPTIONAL_WIDER_END; ORIGINAL_CARRIER_UNCHANGED')


def custody_sections(recipe,body,native_sites):
    """Derive obligations from the admitted field and its immutable input skin.

    This runs before the final output audit. It never reads the output as its
    own target and never turns an internal occurrence seam into a taper end.
    """
    from .smooth_transition import value
    points=recipe['native_points_mm'];profile=recipe['profile'];width=recipe['source_width_mm']
    p,n,stations,length=frame(points)
    for i,section in zip((0,-1),profile['endpoint_sections']):n[i]=section['normal']
    pieces=[];cursor=0.
    for proof in profile['side_field_proofs']:
        pieces.append((cursor,cursor+proof['length_mm'],proof));cursor+=proof['length_mm']
    result={}
    for center,normal,t in zip(p,n,stations):
        site=key(center)
        if site not in native_sites or t<=1e-12 or t>=length-1e-12:continue
        lo,hi,proof=next((q for q in pieces if t<=q[1]+1e-12),pieces[-1])
        fraction=min(1.,max(0.,float((t-lo)/(hi-lo))))
        growth=[value(c,fraction)for c in proof['controls']]
        size=float(np.linalg.norm(normal));unit=normal/size
        lower=(width/2+growth[0])*size;upper=(width/2+growth[1])*size
        actual=extent(body,center,unit,max(lower,upper)+.11)
        if actual is None:raise ValueError('NATIVE_TAPER_INPUT_SECTION_REQUIRED')
        lower=min(lower,actual[1]);upper=min(upper,actual[0])
        result[site]=dict(normal=unit.tolist(),lower_mm=(center-unit*lower).tolist(),upper_mm=(center+unit*upper).tolist())
    return result


def outer_cap_mask(body,center,ends,descriptors,width_caps):
    """Retract unsupported optional cap outside BOTH incoming native spans.

    Per-arm taper masks intentionally stop at their native endpoint planes.
    Their union therefore misses the outer quadrant of a turn, or a thin
    coincident end-plane spur. Treat that joint cap once, without clipping
    either incoming taper. The caller protects the exact original floor.
    """
    radius=math.sqrt(2)*max(width_caps.get(s,descriptors[s]['source_width_mm'])for s,e in ends)/2+2*ERROR_MM
    domain=Point(center).buffer(radius,quad_segs=128);scale=4*radius
    for s,e in ends:
        u=tangent(oriented(descriptors[s],e),False);n=np.array([-u[1],u[0]])
        plane=Polygon([center+u*x+n*y for x,y in[(-scale,-scale),(2*ERROR_MM,-scale),
                       (2*ERROR_MM,scale),(-scale,scale)]])
        domain=domain.intersection(plane)
    # The exact source floor is the cap reference. A separately tessellated
    # circle can leave thin cap fragments between its facets and that floor.
    return polygonal(body.intersection(domain))


def run(rows,paths,bodies,descriptors,sites,width_caps,original,*,covered=()):
    started=perf_counter();covered=set(covered);working=dict(bodies);nodes=defaultdict(list)
    reports=[];replacements={};cuts={};protected={};route_cache={};seam_replacements={};native_sites=defaultdict(set)
    for route,sources in sorted(paths.items()):
        for s in sources:
            if s not in descriptors:continue
            pts=rows[s]['metadata']['route_points_mm']
            for end,point in enumerate((pts[0],pts[-1])):
                native_sites[route].add(key(point));site=(route,key(point))
                if site in sites and descriptors[s].get('real_endpoints',[True,True])[end]:nodes[site].append((s,end))
    for site,ends in sorted(nodes.items()):
        route,point=site;sources=paths[route];record=dict(route_id=route,endpoint_mm=list(point),attempts=[])
        if len(ends)!=2:
            record['status']='KEEP_NATIVE_BRANCH_OR_TRUE_END';reports.append(record);continue
        if route not in protected:protected[route]=unary_union([original[s]for s in sources])
        if route not in route_cache:route_cache[route]=unary_union([working[s]for s in sources])
        before=route_cache[route]
        try:
            (sa,ea),(sb,eb)=ends
            ta=tangent(oriented(descriptors[sa],ea),False);tb=tangent(oriented(descriptors[sb],eb),False)
            axis=ta-tb
            if np.linalg.norm(axis)<1e-12:raise ValueError('OPPOSING_NATIVE_INTERFACE_REQUIRED')
            axis/=np.linalg.norm(axis);normal=np.array([-axis[1],axis[0]]);center=np.asarray(point)
            measured=[(s,e,*sample(descriptors[s],e,working[s],normal))for s,e in ends]
            lows=[-float((np.asarray(q['lower_mm'])-center)@normal)for _,_,q,_ in measured]
            highs=[float((np.asarray(q['upper_mm'])-center)@normal)for _,_,q,_ in measured]
            low,high=min(lows),min(highs)
            native_half=max(descriptors[s]['source_width_mm']/2 for s,e in ends)
            targets=[('COMMON_EMITTED_SECTION',low,high)]
            # A sampled wider skin can be absent at the exact joint, or a
            # matched-width sharp turn can reject every additive transition.
            # Retry a subtraction-only taper to the original carrier width.
            # The original copper floor remains protected throughout; no
            # width cap, clearance check or endpoint predicate is relaxed.
            if min(low,high)>=native_half-ERROR_MM and max(low,high)>native_half+ERROR_MM:
                targets.append(('ORIGINAL_CARRIER_SECTION',native_half,native_half))
            for target_mode,low,high in targets:
                attempt_start=len(record['attempts'])
                center=np.asarray(point)
                target=dict(normal=normal.tolist(),lower_mm=(center-normal*low).tolist(),upper_mm=(center+normal*high).tolist())
                optional=[(s,e)for i,(s,e,_,_)in enumerate(measured)if lows[i]-low>ERROR_MM or highs[i]-high>ERROR_MM]
                record.update(source_ids=[s for s,e in ends],target_section=target,target_width_mm=low+high,target_mode=target_mode)
                if min(low,high)<max(descriptors[s]['source_width_mm']/2 for s,e in ends)-ERROR_MM:
                    record['status']='KEEP_ORIGINAL_WIDTH_TRANSITION';break
                if not optional:
                    continue
                if any(s in covered or s not in width_caps for s,e in optional):
                    record['status']='KEEP_FIXED_WIDER_CONTRIBUTION';break
                for slope,factor in ((.25,1.),(.25,2.),(.25,4.),(.25,8.),(1.,1.),(1.,2.),(1.,4.)):
                    masks=[];recipes=[];seam_candidates={};problem=None
                    for s,e in optional:
                        from .joint_receiver_chain import extend
                        extension=extend(rows,[k for k in sources if k not in covered],descriptors,s,e,.66)
                        proposal_desc=descriptors[s]if extension is None else extension
                        proposal_end=e if extension is None else 0
                        proposal_body=working[s]if extension is None else unary_union([working[k]for k in extension['joint_receiver_source_ids']])
                        try:mask,_,recipe=taper(proposal_desc,proposal_end,proposal_body,target,width_caps[s],maximum_side_slope=slope,span_factor=factor)
                        except (ValueError,GEOSException)as error:problem=str(error);break
                        masks.append(mask);recipes.append(dict(source_id=s,recipe=recipe))
                        for pt,section in custody_sections(recipe,proposal_body,native_sites[route]).items():
                            if pt in seam_candidates:
                                other=seam_candidates[pt];center=np.asarray(pt);n=np.asarray(section['normal'])
                                old=sorted(float((np.asarray(other[k])-center)@n)for k in('lower_mm','upper_mm'))
                                current=sorted(float((np.asarray(section[k])-center)@n)for k in('lower_mm','upper_mm'))
                                section=dict(normal=n.tolist(),lower_mm=(center+n*max(old[0],current[0])).tolist(),
                                             upper_mm=(center+n*min(old[1],current[1])).tolist())
                            seam_candidates[pt]=section
                    if problem is not None:
                        record['attempts'].append(dict(passed=False,reason=problem,slope_limit=slope));continue
                    if target_mode=='ORIGINAL_CARRIER_SECTION':
                        masks.append(outer_cap_mask(before,np.asarray(point),ends,descriptors,width_caps))
                    mask=polygonal(unary_union(masks).difference(protected[route]))
                    if covered.intersection(sources):mask=polygonal(mask.difference(unary_union([working[s]for s in sources if s in covered])))
                    # An interior cut island changes no exterior edge and would
                    # create a new pocket. Keep that optional interior copper.
                    mask_parts=parts(mask);open_parts=[g for g in mask_parts if g.intersects(before.boundary)]
                    mask=polygonal(unary_union(open_parts))
                    if mask.is_empty:
                        record['attempts'].append(dict(passed=False,reason='ORIGINAL_OR_FIXED_COPPER_PROTECTS_INTERFACE'));continue
                    from .source_trace_floor import preserve
                    from .pipeline import EPS
                    tip_records=[];representation=[];floor_proofs={};changed={};invalid=False;complete=False
                    for refinement in range(4):
                        changed={};representation=[];floor_proofs={}
                        for s in sources:
                            if s in covered or not working[s].intersects(mask):continue
                            g=polygonal(working[s].difference(mask))
                            if not working[s].covers(g):
                                for left,right in ((g,working[s]),(working[s],g)):
                                    clipped=polygonal(left.intersection(right))
                                    if working[s].covers(clipped):g=clipped;break
                            if g.is_empty or not g.is_valid:invalid=True;break
                            g,floor_proofs[s]=preserve(original[s],g);changed[s]=g
                            extra=polygonal(g.difference(working[s]));outside=extra.difference(working[s].buffer(ERROR_MM,quad_segs=128))
                            representation.append(dict(source_id=s,area_mm2=extra.area,within_coordinate_bound=outside.is_empty))
                        if invalid:break
                        if any(r['area_mm2']>EPS or not r['within_coordinate_bound']for r in representation):break
                        after=polygonal(unary_union([changed.get(s,working[s])for s in sources]))
                        detached=[g for g in parts(after)if not g.intersects(protected[route])]
                        tips=[g for g in detached if g.area<=.005**2 and g.distance(mask)<=2*ERROR_MM]
                        if not tips:complete=True;break
                        tip_records.extend(dict(area_mm2=g.area,wkb_hex=to_wkb(g).hex())for g in tips)
                        extra_mask=unary_union(tips).buffer(2*ERROR_MM,quad_segs=32).difference(protected[route])
                        if covered.intersection(sources):extra_mask=extra_mask.difference(unary_union([working[s]for s in sources if s in covered]))
                        mask=polygonal(unary_union([mask,extra_mask]))
                    if any(r['area_mm2']>EPS or not r['within_coordinate_bound']for r in representation):
                        record['attempts'].append(dict(passed=False,reason='SUBTRACTION_MUST_ADD_NO_COPPER',representation=representation));continue
                    if invalid or not complete or not changed or any(g.is_empty or not g.is_valid for g in changed.values()):
                        record['attempts'].append(dict(passed=False,reason='INVALID_SUBTRACTIVE_INTERFACE'));continue
                    if len(OriginalOwners(after).owners)>len(OriginalOwners(before).owners)or new_pocket_regions(before,after):
                        record['attempts'].append(dict(passed=False,reason='NATIVE_CONNECTION_OR_POCKET_LIMIT',components_before=len(OriginalOwners(before).owners),components_after=len(OriginalOwners(after).owners),detached=[dict(area_mm2=g.area,source_overlap_mm2=g.intersection(protected[route]).area)for g in parts(after)if not g.intersects(protected[route])],pocket_areas_mm2=[g.area for g in new_pocket_regions(before,after)]));continue
                    expected=LineString([target['lower_mm'],target['upper_mm']])
                    if expected.difference(after.buffer(ERROR_MM,quad_segs=128)).length>ERROR_MM:
                        record['attempts'].append(dict(passed=False,reason='NEW_INTERFACE_NOT_REALIZED'));continue
                    # Internal custody seams inherit this same field. Validate
                    # every saved target against this proposal before publishing
                    # it; the separate final route audit repeats on final output.
                    selected={};after_buffer=after.buffer(ERROR_MM,quad_segs=128)
                    for pt,section in seam_candidates.items():
                        line=LineString([section['lower_mm'],section['upper_mm']])
                        if not mask.envelope.buffer(ERROR_MM).intersects(line):continue
                        if line.difference(after_buffer).length>ERROR_MM:
                            problem='NATIVE_TAPER_CUSTODY_SECTION_NOT_REALIZED';break
                        selected[route,pt]=section
                    if problem is not None:
                        record['attempts'].append(dict(passed=False,reason=problem));continue
                    seam_replacements.update(selected)
                    for s,g in changed.items():working[s]=g;cuts[s]=polygonal(unary_union([cuts.get(s,Polygon()),mask]))
                    route_cache[route]=after;replacements[site]=target
                    record.update(status='TRIMMED_OPTIONAL_INTERFACE',profiles=recipes,detached_optional_tips=tip_records,retained_interior_cut_parts=len(mask_parts)-len(open_parts),removed_area_mm2=before.difference(after).area,
                        custody_sections=[dict(point_mm=list(k[1]),section=v)for k,v in sorted(selected.items())],
                        mask_sha256=digest(to_wkb(mask)),mask_wkb_hex=to_wkb(mask).hex(),changed_source_ids=sorted(changed),
                        original_floor_proofs=floor_proofs,subtraction_representation=representation,native_area_bound_mm2=EPS,native_coordinate_bound_mm=ERROR_MM,
                        original_copper_removed_mm2=0.,copper_added_mm2=0.,components_before=len(OriginalOwners(before).owners),components_after=len(OriginalOwners(after).owners))
                    break
                for attempt in record['attempts'][attempt_start:]:attempt.update(target_mode=target_mode,target_width_mm=low+high)
                if 'status'in record:break
            if 'status'not in record:record['status']='KEEP_UNRESOLVED_INTERFACE'
        except (ValueError,GEOSException)as error:record.update(status='KEEP_NUMERICAL_INTERFACE_LIMIT',error=repr(error))
        reports.append(record)
    for site,section in seam_replacements.items():replacements.setdefault(site,section)
    # A whole mutable chain bounded by fixed original-width continuations
    # cannot publish an infeasible widening profile. Withdraw its OPTIONAL
    # growth as one constructor decision, rather than leaving a width step.
    # This is the established KEEP fallback, not a new eligibility exclusion.
    kept_components=[];seen=set()
    failed_sites={(r['route_id'],key(r['endpoint_mm']))for r in reports if r['status']=='KEEP_UNRESOLVED_INTERFACE'}
    for route,sources in sorted(paths.items()):
        adjacency=defaultdict(list)
        for s in sources:
            pts=rows[s]['metadata']['route_points_mm']
            for point in(pts[0],pts[-1]):adjacency[key(point)].append(s)
        mutable=set(sources).intersection(width_caps)-covered
        for seed in sorted(mutable):
            if seed in seen:continue
            component={seed};queue=[seed];boundary=[];valid=True
            while queue:
                s=queue.pop();pts=rows[s]['metadata']['route_points_mm']
                for point in(pts[0],pts[-1]):
                    incident=adjacency[key(point)]
                    if len(incident)!=2:valid=False;continue
                    for other in incident:
                        if other in covered:boundary.append((key(point),other))
                        elif other in mutable and other not in component:component.add(other);queue.append(other)
                        elif other not in mutable:valid=False
            seen.update(component)
            component_sites={(route,key(point))for s in component for point in(rows[s]['metadata']['route_points_mm'][0],rows[s]['metadata']['route_points_mm'][-1])}
            if not valid or len(boundary)!=2 or not failed_sites.intersection(component_sites):continue
            widths=[descriptors[s]['source_width_mm']for s in component|{s for _,s in boundary}]
            if max(widths)-min(widths)>1e-12:continue
            if route not in route_cache:route_cache[route]=unary_union([working[s]for s in sources])
            previous=route_cache[route]
            trial={s:original[s]for s in component}
            candidate=polygonal(unary_union([trial.get(s,working[s])for s in sources]))
            if len(OriginalOwners(candidate).owners)>len(OriginalOwners(previous).owners)or new_pocket_regions(previous,candidate):continue
            selected={};buffered=candidate.buffer(ERROR_MM,quad_segs=128)
            for s in sorted(component):
                pts=rows[s]['metadata']['route_points_mm']
                for end,point in enumerate((pts[0],pts[-1])):
                    u=tangent(pts,bool(end));n=np.array([-u[1],u[0]]);center=np.asarray(point);half=widths[0]/2
                    section=dict(normal=n.tolist(),lower_mm=(center-n*half).tolist(),upper_mm=(center+n*half).tolist())
                    if LineString([section['lower_mm'],section['upper_mm']]).difference(buffered).length>ERROR_MM:valid=False;break
                    selected[route,key(point)]=section
                if not valid:break
            if not valid:continue
            for s in component:
                cut=polygonal(working[s].difference(original[s]));cuts[s]=polygonal(unary_union([cuts.get(s,Polygon()),cut]));working[s]=original[s]
            route_cache[route]=candidate;replacements.update(selected)
            kept_components.append(dict(route_id=route,source_ids=sorted(component),fixed_boundary_source_ids=[s for _,s in boundary],
                reason='KEEP_ORIGINAL_PROFILE; NO_ADMISSIBLE_C1_TRANSITION_BETWEEN_FIXED_CONTINUATIONS',
                removed_optional_area_mm2=previous.difference(candidate).area,original_copper_changed=False,
                source_geometry_sha256={s:digest(to_wkb(original[s]))for s in sorted(component)}))
            for record in reports:
                if (record['route_id'],key(record['endpoint_mm']))in component_sites:
                    record.update(status='KEPT_ORIGINAL_BOUNDED_COMPONENT',optional_widening_withdrawn=True)
    return working,cuts,replacements,dict(schema='t04-subtractive-interface-reconciliation/1',reports=reports,
        transported_custody_sites=[dict(route_id=r,point_mm=list(pt))for r,pt in sorted(seam_replacements)],
        trimmed_joints=sum(r['status']=='TRIMMED_OPTIONAL_INTERFACE'for r in reports),kept_original_components=kept_components,wall_s=perf_counter()-started,
        scene_indexes_built=0,clearance_queries=0,source_path_changed=False,
        raw_constructed_group_operands_changed=False,validation='SOURCE_FLOOR; NO_ADDITION; LOCAL_ROUTE_COMPONENTS_AND_POCKETS; FINAL_CHECKS_REQUIRED')
