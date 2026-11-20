"""Bounded hybrid component treatment; constructed strips are fixed operands.

Reuses side-profile quads, source offsets, the width verifier and bulk connection
recovery. No constructed strip is ever submitted as a checked trace. Results
remain diagnostic until functional/source-void and assembled connection custody
are integrated; a physical component pass is not full T04 acceptance.
"""
import copy
from time import perf_counter
import numpy as np
from shapely import STRtree, to_wkb
from shapely.geometry import Polygon, box, Point,LineString
from shapely.ops import unary_union
from shapely.affinity import translate
from shapely.errors import GEOSException
from src.trace_width_clearance import verify_width_scene
from src.original_copper_owners import OriginalOwners
from .profile_schedule import SCHEDULE
from .side_profile import quad
from .group_profile import outline
from .limiting_growth import preserve_connections, owner_material
from .route_pose import solve as solve_route_pose
from src.component_distance import distance as owner_distance
from .limiting_math import GUARD, MARGIN
from . import pipeline as p
from .continuous_profile import source_profiles, straight_body, straight_fields, reference_profile, joint_widths, ProfileUnresolved
from .local_profile import profile_part
from src.native_inventory import ERROR_MM
from src import pin_separation as pin
from .arc_group_plan import prepare as prepare_arc_groups,prepare_maximal as prepare_maximal_arcs
from .profile_refinement import clearance_barrier
from .ribbon_profile import build as sided_ribbon,sections as end_sections
from .finite_profile_union import certified_union, polygonal
from src.trace_width_clearance import TraceWidthContract
from .normalized_additions import verify as verify_normalized_additions
from . import corner_transition
from .component_workspace import StripReservations, ResidualScene


def joints(construction,rows=None):
    strips=[]; collars=[]; domains={}
    for g in construction['groups']:
        u=np.asarray(g['axis']);n=np.array([-u[1],u[0]])
        for lane in g['lanes']:
            if not lane['mutable']:continue
            shape=Polygon(lane['vertices_mm']);strips.append((lane,shape))
            for end,sign in ((g['first_mm'],-1),(g['last_mm'],1)):
                a=u*end+n*(lane['left_mm']+lane['right_mm'])/2
                b=u*(end+sign*.05)+n*lane['source_normal_mm']
                # Reuse the quad materializer for endpoint cross sections.
                # This is an untrusted joint candidate, not a side-profile
                # certificate or a newly audited parallel strip.
                collar=quad(dict(a=a.tolist(),b=b.tolist(),normal=n.tolist(),
                                 base=[lane['width_mm']/2]*2+[lane['source_width_mm']/2]*2,
                                 extra=[0.]*4))
                target=lane
                if rows is not None and len(lane['source_ids'])>1:
                    # A merged straight run can contain several native source
                    # occurrences. Bind each collar to its local occurrence,
                    # never replicate it onto every segment of the run.
                    station=end+sign*.025
                    def distance(s):
                        ts=[float(np.dot(pt,u)) for pt in rows[s]['metadata']['route_points_mm']]
                        return max(min(ts)-station,station-max(ts),0.),s
                    target=dict(lane,source_ids=[min(lane['source_ids'],key=distance)])
                collars.append((target,collar))
            extent=max(lane['width_mm'],lane['source_width_mm'])/2+abs(lane['profile_midline_shift_mm'])+.11
            overlap=2*ERROR_MM if construction.get('reference_policy')=='SOURCE_ANCHORED'else 0.
            domain=Polygon(outline(g['axis'],g['first_mm']+overlap,g['last_mm']-overlap,
                                   lane['source_normal_mm']-extent,lane['source_normal_mm']+extent))
            for sid in lane['source_ids']:domains.setdefault(sid,[]).append(domain)
    return strips,collars,{s:unary_union(v) for s,v in domains.items()}


def run(rows,current,original,roles,paths,construction,settings,scope,*,progress=None,continuous=False,coherent_pose=False):
    pose_proof=None
    if coherent_pose:
        pose_proof=solve_route_pose(construction,paths)
        if not pose_proof['passed']:raise ValueError('T04_COMMON_ROUTE_POSE_UNRESOLVED')
        construction=dict(construction,route_poses=pose_proof['routes'])
    started=perf_counter();strips,collars,domains=joints(construction,rows)
    if coherent_pose:collars=[] # source-end profiles replace artificial island collars
    group_fixed={f'group:{i}':g for i,(_,g) in enumerate(strips)}
    before_hash={s:p.digest(to_wkb(g)) for s,g in group_fixed.items()}
    tick=perf_counter();changed=dict(current);bulk_changes={};bulk_error=None
    # Original terminal/trace cores remain protected during the existing bulk
    # recovery algorithm. Never restore material silently through a new strip.
    reservations=StripReservations(strips,scope.ids)
    for sid in sorted(roles):
        own=scope.ids[sid]
        foreign=reservations.foreign(own,current[sid])
        if foreign:
            removal=unary_union(foreign);new=current[sid].difference(removal)
            if not new.equals_exact(current[sid],0):changed[sid]=new;bulk_changes[sid]=removal
    del reservations
    restored=[]
    if bulk_changes:
        affected={scope.ids[s][0] for s in bulk_changes};subset={s:g for s,g in current.items() if scope.ids[s][0] in affected}
        narrowed=copy.copy(scope);narrowed.cores={o:g for o,g in scope.cores.items() if o in affected}
        try:
            recovered,restored,_=preserve_connections(narrowed,subset,{s:changed[s] for s in subset})
            changed.update(recovered)
            conflicts=[s for s in restored if not changed[s].intersection(bulk_changes[s]).is_empty]
            if conflicts:bulk_error='BULK_CONNECTION_RECOVERY_REENTERS_RESERVED_CORRIDOR'
        except ValueError as error:bulk_error=str(error)
    bulk_wall=perf_counter()-tick
    used={s for ss in paths.values() for s in ss}
    profiles=source_profiles(rows,paths,construction) if continuous else None
    anchored=coherent_pose and construction.get('reference_policy')=='SOURCE_ANCHORED'
    if anchored:
        joint_widths(profiles,rows,construction['source_width_targets_mm'])
        for q in profiles['segments'].values():
            if q['axis']is not None and (q['constraints']or q.get('member_context',{}).get('constraints')):
                q['inherit_sided_endpoints']=True
                if 'member_context'in q:q['member_context']=dict(q['member_context'],inherit_sided_endpoints=True)
    smooth_plans={s:straight_fields(q,rows[s]['metadata']['minimum_caliper_mm'])
                  for s,q in profiles['segments'].items() if q['axis'] is not None} if continuous else {}
    references=dict(original)
    if coherent_pose:
        for s in used:
            record=profiles['segments'][s];tx,ty=record['route_translation_mm']
            moved=translate(original[s],xoff=tx,yoff=ty)
            if record['axis'] is not None and (tx!=0. or ty!=0.):
                w=rows[s]['metadata']['minimum_caliper_mm']
                minimum=reference_profile(record,w,zero_side_shift=True)
                caps=unary_union([moved.intersection(Point(pt).buffer(w/2+MARGIN,quad_segs=128))
                                 for pt in (record['reference_start_mm'],record['reference_end_mm'])])
                moved=polygonal(unary_union([straight_body(minimum,w),caps]))
            references[s]=moved
    residual={s:references[s].difference(domains[s]) if s in domains else references[s] for s in used}
    material=ResidualScene({s:g for s,g in changed.items() if s not in used and not g.is_empty})
    material.update({s:g for s,g in residual.items() if not g.is_empty});material.update(group_fixed)
    joint_owners={}
    def changed_owner_checks(before_material,after_material):
        shadow=copy.copy(scope);shadow.ids=dict(scope.ids)
        shadow.ids.update({f'group:{i}':scope.ids[lane['source_ids'][0]] for i,(lane,_)in enumerate(strips)})
        shadow.ids.update(joint_owners)
        before=owner_material(shadow,before_material)
        after=owner_material(shadow,after_material)
        ids=sorted(after);tree=STRtree([after[o]for o in ids]);failures=[];checked=0
        additions={}
        for s in used|set(joint_owners):
            if s not in after_material:continue
            own=shadow.ids[s][0];delta=polygonal(after_material[s].difference(before[own]))
            if not delta.is_empty:additions.setdefault(own,[]).append(delta)
        for own,pieces in additions.items():
            delta=polygonal(unary_union(pieces))
            for i in sorted(map(int,tree.query(delta.envelope.buffer(GUARD)))):
                other=ids[i]
                if other==own:continue
                checked+=1;gap=owner_distance(delta,after[other])
                if gap+1e-12<GUARD:failures.append(dict(owner=own,neighbor=other,gap_mm=gap,reason='RESIDUAL_FUNCTIONAL_GAP'))
        for own in {scope.ids[s][0]for s in used}:
            if len(OriginalOwners(after[own]).owners)>len(OriginalOwners(before[own]).owners):
                failures.append(dict(owner=own,reason='ROUTE_ATTACHMENT_DISCONNECTED'))
        return dict(passed=not failures,failures=failures,pairs_checked=checked,
                    checked_candidates='RESIDUAL_ONLY; GROUPS_FIXED_SUPPORT')
    reference_material=dict(material)
    reference_checks=changed_owner_checks(current,material) if coherent_pose else None
    if reference_checks is not None and not reference_checks['passed']:
        return dict(status='COMMON_ROUTE_REFERENCE_REJECTED; NO_FRAGMENT_FALLBACK',
                    smooth_source_field_plans=smooth_plans,
                    reference_checks=reference_checks,route_pose=pose_proof,continuous_source_bodies={},
                    constructed_groups_audited=0,constructed_group_bytes_preserved=True,
                    joints=dict(wall_s=0.,reports=[]),bulk=dict(wall_s=bulk_wall,changed_sources=sorted(bulk_changes),restored_sources=restored,error=bulk_error),
                    residual=dict(wall_s=0.,reports=[]),joint_connections=dict(wall_s=0.,reports=[]),
                    wall_s=perf_counter()-started,pending=['DEFAULT_CASE_COMMON_ROUTE_POSE'],
                    publication_ready=False,output_scene_ref=None,full_board_run=False,replay=False)
    joint_by_source={}
    for lane,g in collars:
        for s in lane['source_ids']:joint_by_source.setdefault(s,[]).append(g)
    def owner(k):
        if k in joint_owners:return joint_owners[k]
        if k.startswith('group:'):return scope.ids[strips[int(k.split(':')[1])][0]['source_ids'][0]]
        return scope.ids[k]
    def neighbours(s,candidate):
        window=candidate.envelope.buffer(GUARD+2*MARGIN)
        ids=[k for k in material.query(window) if k!=s and (not anchored or owner(k)!=scope.ids[s])]
        fixed=[dict(id=k,geometry=material[k],trace_width_mm=rows.get(k,{}).get('metadata',{}).get('source_port_width_mm',0.))
               for k in ids]
        return fixed
    def check(s,core,candidate):
        return verify_width_scene([dict(id=s,original=core,candidate=candidate,
                                  verified_original_width_mm=rows[s]['metadata']['source_port_width_mm'])],neighbours(s,candidate))
    def additions_check(s,core,actual):
        if anchored:
            return verify_normalized_additions(core,actual,neighbours(s,actual)),actual
        proxy,method=certified_union(core,actual)
        if not proxy.covers(actual):
            if anchored:
                # A conservative checking operand only; actual copper and
                # its smooth fields remain unchanged. Native error headroom
                # avoids coincident-edge overlay loss, never a clearance waiver.
                proxy,method=certified_union(core,actual.buffer(ERROR_MM,quad_segs=128))
            if not proxy.covers(actual):
                return dict(passed=False,failures=[dict(reason='NORMALIZED_ADDITION_PROXY_INCOMPLETE',finite_union=method)]),proxy
        return check(s,core,proxy),proxy
    endpoint_sections={};section_conflicts=[];ribbon_recipes={};accepted_ribbons={};frozen_straights={};arc_cores={};arc_proof=None
    def endpoint_key(s,pt):return profiles['segments'][s]['route_id'],tuple(round(v,10)for v in pt)
    def register_sections(s,values):
        for pt,section in zip(rows[s]['metadata']['route_points_mm'][::len(rows[s]['metadata']['route_points_mm'])-1],values):
            if section is None:continue
            key=endpoint_key(s,pt)
            if key not in endpoint_sections:endpoint_sections[key]=section
            else:
                old=endpoint_sections[key]
                same=float(np.asarray(old['normal'])@section['normal'])>=0
                mismatch=max(np.linalg.norm(np.asarray(old[name])-section[name if same else other])
                             for name,other in(('lower_mm','upper_mm'),('upper_mm','lower_mm')))
                if mismatch>ERROR_MM:
                    section_conflicts.append(dict(source_id=s,endpoint_mm=pt,mismatch_mm=float(mismatch),reason='FROZEN_CROSS_SECTIONS_DISAGREE'))
    def curve_candidate(s,factor,profile):
        w=rows[s]['metadata']['minimum_caliper_mm'];radial=(factor-1)*w/2
        if anchored:
            pts=rows[s]['metadata']['route_points_mm']
            ends=[endpoint_sections.get(endpoint_key(s,pt))for pt in(pts[0],pts[-1])]
            try:
                candidate,recipe=sided_ribbon(pts,w,construction['source_width_targets_mm'][s],ends=ends,
                    interior_width=w*factor,plateau=arc_cores.get(s))
                ribbon_recipes[s]=recipe
                return candidate,None
            except ValueError as error:
                if str(error)=='FROZEN_JOINT_TRANSITION_TOO_SHORT'and rows[s]['metadata']['route_kind']=='segment'and LineString(pts).length<=.1 and all(v is not None for v in ends):
                    try:
                        candidate,recipe=sided_ribbon(pts,w,construction['source_width_targets_mm'][s],ends=ends,
                            interior_width=w*factor,plateau=arc_cores.get(s),maximum_side_slope=1.)
                        recipe['short_connector_transition_policy']='EXISTING_1_TO_1_JOINT_SLOPE_LIMIT; WIDTH_AND_REACH_CAPS_UNCHANGED'
                        ribbon_recipes[s]=recipe;return candidate,None
                    except ValueError as tight_error:error=tight_error
                return None,dict(passed=False,failures=[dict(reason=str(error))])
        ends=[min(radial,max(0.,(v-w)/2))for v in profile['endpoint_widths_mm']]
        if 1.5*(radial-min(ends))/(profile['length_mm']/2)>.25+1e-12:
            return None,dict(passed=False,failures=[dict(reason='DEFAULT_TRANSITION_TOO_SHORT_FOR_SIDE_SLOPE')])
        try:
            candidate=profile_part(residual[s],rows[s]['metadata']['route_points_mm'],w,
                dict(route_floor_radial_mm=0.,radial_mm=radial,
                     start_radial_mm=ends[0],end_radial_mm=ends[1],
                     transition_length_mm=profile['length_mm']/2),1.,False)
        except (ValueError,GEOSException)as error:
            if isinstance(error,ValueError)and str(error)not in('LOCAL_PROFILE_SOURCE_CORE_CHANGED','LOCAL_PROFILE_UPPER_CAP_CHANGED'):raise
            return None,dict(passed=False,failures=[dict(reason=str(error))])
        return candidate,None
    reports=[];joint_reports=[];tick=perf_counter()
    for s in sorted(residual):
        core=residual[s]
        if core.is_empty:continue
        supplement=unary_union(joint_by_source.get(s,[]))
        if s in domains:supplement=supplement.difference(domains[s])
        candidate=unary_union([core,supplement])
        if candidate.equals_exact(core,0):continue
        q=check(s,core,candidate);joint_reports.append(dict(source_id=s,passed=q['passed'],failures=q['failures']))
        if q['passed']:material[s]=candidate
    joint_wall=perf_counter()-tick;tick=perf_counter()
    direct_straight={s for s,q in profiles['segments'].items()if q.get('inherit_sided_endpoints')}if anchored else set()
    maximal_arc_groups=construction.get('maximal_curve_catalogue',{}).get('curve_groups')
    grouped_arcs=({s for g in maximal_arc_groups for m in g['members']for s in m['source_ids']}if maximal_arc_groups is not None else
                  {m['source_id']for g in construction.get('full_member_catalogue',{}).get('curve_groups',[])for m in g['members']})
    def phase(s):return 0 if s in direct_straight else 2
    order=sorted(residual,key=lambda s:(phase(s),0 if s in grouped_arcs else 1,s))if anchored else sorted(residual)
    phases=[];last_phase=None;phase_started=None
    component_setup_wall=perf_counter()-started
    for index,s in enumerate(order):
        if anchored and phase(s)!=last_phase:
            if phase_started is not None:phases[-1]['wall_s']=perf_counter()-phase_started
            last_phase=phase(s);name=('STRAIGHT_GROUPS','ARC_GROUPS','DEFAULT_SEARCH_AND_VERIFY')[last_phase]
            if last_phase>0 and arc_proof is None:
                phases.append(dict(phase='ARC_GROUPS',started_after_sources=index))
                phase_started=perf_counter()
                if progress:progress(dict(event='assembly_phase',phase='ARC_GROUPS',index=index,sources=len(residual)))
                before_arc=dict(material)
                prepare_arcs=prepare_arc_groups if maximal_arc_groups is None else prepare_maximal_arcs
                arc_cores,arc_proof=prepare_arcs(rows,original,material,
                    construction.get('full_member_catalogue',{}).get('curve_groups',[])if maximal_arc_groups is None else maximal_arc_groups,used,owner,roles,
                    settings,construction['source_width_targets_mm'],
                    protected_domains=[]if pin.ACTIVE is None else[s.domain for s in pin.ACTIVE.slots])
                new_strips=[];seen_arc_members=set()
                for source,value in sorted(arc_cores.items()):
                    mid=value.get('member_id',source)
                    if mid in seen_arc_members:continue
                    seen_arc_members.add(mid)
                    lane=dict(source_ids=value.get('member_source_ids',[source]),route_id=profiles['segments'][source]['route_id'],mutable=True,arc_group_id=value['group_id'])
                    key=f'group:{len(strips)}';strips.append((lane,value['body']));new_strips.append((lane,value['body']))
                    group_fixed[key]=value['body'];material[key]=value['body'];before_hash[key]=p.digest(to_wkb(value['body']))
                arc_bulk={};reservations=StripReservations(new_strips,scope.ids)
                for source in sorted(roles):
                    foreign=reservations.foreign(scope.ids[source],material[source])
                    if not foreign:continue
                    mask=unary_union(foreign);new=material[source].difference(mask)
                    if not new.equals_exact(material[source],0):
                        arc_bulk[source]=mask;material[source]=new
                del reservations
                if arc_bulk:
                    affected={scope.ids[k][0]for k in arc_bulk};shadow=copy.copy(scope);shadow.ids=dict(scope.ids)
                    shadow.ids.update({f'group:{i}':scope.ids[lane['source_ids'][0]]for i,(lane,g)in enumerate(strips)})
                    shadow.cores={o:g for o,g in scope.cores.items()if o in affected}
                    before_subset={k:g for k,g in before_arc.items()if owner(k)[0]in affected}
                    after_subset={k:g for k,g in material.items()if owner(k)[0]in affected}
                    try:
                        recovered,kept,_=preserve_connections(shadow,before_subset,after_subset);material.update(recovered);restored.extend(kept)
                        if any(not material[k].intersection(arc_bulk[k]).is_empty for k in kept if k in arc_bulk):
                            bulk_error='ARC_BULK_CONNECTION_RECOVERY_REENTERS_RESERVED_CORRIDOR'
                    except ValueError as error:bulk_error=str(error)
                    for source,mask in arc_bulk.items():
                        bulk_changes[source]=mask if source not in bulk_changes else unary_union([bulk_changes[source],mask])
                        changed[source]=material[source]
                for source,value in arc_cores.items():
                    mask=value['domain'].buffer(-2*ERROR_MM,quad_segs=128)
                    domains[source]=mask;residual[source]=references[source].difference(mask);material[source]=residual[source]
                if progress:progress(dict(event='arc_group_construction',groups=len(arc_proof['models']),sources=len(arc_cores),wall_s=arc_proof['wall_s']))
                phases[-1]['wall_s']=perf_counter()-phase_started
            phases.append(dict(phase=name,started_after_sources=index))
            phase_started=perf_counter()
            if progress:progress(dict(event='assembly_phase',phase=name,index=index,sources=len(residual)))
        if s in arc_cores and arc_cores[s].get('complete_member'):
            value=arc_cores[s];w=rows[s]['metadata']['minimum_caliper_mm'];growth=value['negative_growth_mm']+value['positive_growth_mm']
            interval=value['source_interval_mm'];points=np.asarray(value['member_points_mm']);values=[]
            for t in([interval['first_mm'],interval['last_mm']]if interval['direction']==1 else[interval['last_mm'],interval['first_mm']]):
                if abs(t)<1e-10:center=points[0];u=corner_transition.tangent(points,False)
                elif abs(t-value['member_length_mm'])<1e-10:center=points[-1];u=-corner_transition.tangent(points,True)
                else:values.append(None);continue
                u=u/np.linalg.norm(u);n=np.array([-u[1],u[0]])
                values.append(dict(normal=n.tolist(),lower_mm=(center-n*(w/2+value['negative_growth_mm'])).tolist(),
                                   upper_mm=(center+n*(w/2+value['positive_growth_mm'])).tolist()))
            register_sections(s,values)
            reports.append(dict(source_id=s,selected_factor=1+growth/w,status='CONSTRUCTED_MAXIMAL_ARC_MEMBER',
                                member_id=value['member_id'],native_seam_is_transition=False,
                                constructed_group_geometry_audit=False))
            if progress:progress(dict(event='hybrid_residual',index=index+1,sources=len(residual)))
            continue
        core=material.get(s)
        if core is None or core.is_empty:continue
        w=rows[s]['metadata']['minimum_caliper_mm'];cap=construction['local_join_width_plan']['selected_width_caps_mm'][s]
        chosen=1.;attempts=[];accepted_rung=0
        if continuous:
            profile=profiles['segments'][s]
            physical_cap=min(w*settings.maximum_factor,w+settings.maximum_total_width_increase_mm)
            physical_factor=min(settings.maximum_factor,physical_cap/w)
            if profile['axis'] is not None and (profile['constraints'] or profile['inherited_factor'] is not None)and(not anchored or s in direct_straight):
                try:target=straight_body(profile,w)
                except ProfileUnresolved as error:
                    reports.append(dict(source_id=s,selected_factor=1.,status='UNRESOLVED; NO_SHORT_ISLAND_FALLBACK',
                        attempts=[dict(passed=False,decision='SMOOTH_PROFILE_CONSTRUCTION',failures=[dict(reason=str(error))])]))
                    continue
                minimum_profile=reference_profile(profile,w,zero_side_shift=coherent_pose)
                carrier=straight_body(minimum_profile,w)
                anchors=unary_union([references[s].intersection(Point(pt).buffer(w/2+MARGIN,quad_segs=128))
                                     for pt in (profile['reference_start_mm'],profile['reference_end_mm'])])
                carrier=certified_union(carrier,anchors)[0]
                if s in domains:carrier=polygonal(carrier.difference(domains[s]))
                actual=certified_union(target,anchors)[0]
                if s in domains:actual=polygonal(actual.difference(domains[s]))
                # The existing growth verifier certifies positive additions.
                # Its conservative checked operand retains the old core;
                # the actual normalized body is separately bound below. This
                # does not turn a core-removal check into a false actual PASS.
                q,proxy=additions_check(s,residual[s],actual)
                field_width=max((c[1][i]-c[0][i]for piece in smooth_plans[s]['pieces']for c in [piece['controls']]for i in range(4)),default=w)
                attempts.append(dict(factor=min(physical_factor,max(1.,field_width/w)),
                    passed=q['passed'],failures=q['failures'],decision='CONTINUOUS_ACQUIRED_PROFILE',
                    check_scope='POSITIVE_ADDITIONS_ONLY; NORMALIZED_BODY_CONNECTION_CHECK_SEPARATE'))
                if anchored and s in direct_straight and not q['passed']:
                    # A source-bound joint may limit the end faces, but never
                    # retroactively reduce the constructed straight interior.
                    limited=dict(profile,inherit_sided_endpoints=False,
                                 endpoint_widths_mm=[w,w])
                    if 'member_context'in limited:limited['member_context']=dict(limited['member_context'],inherit_sided_endpoints=False,endpoint_widths_mm=[w,w])
                    try:
                        candidate=certified_union(straight_body(limited,w),anchors)[0]
                        if s in domains:candidate=polygonal(candidate.difference(domains[s]))
                        limited_check,_=additions_check(s,residual[s],candidate)
                        attempts.append(dict(factor=attempts[0]['factor'],passed=limited_check['passed'],
                            failures=limited_check['failures'],decision='DEFAULT_JOINT_END_LIMIT; STRAIGHT_INTERIOR_FROZEN'))
                        if limited_check['passed']:
                            actual=candidate;q=limited_check;profile=limited
                            smooth_plans[s]=straight_fields(limited,w)
                    except ProfileUnresolved as error:
                        attempts.append(dict(passed=False,decision='DEFAULT_JOINT_END_LIMIT',failures=[dict(reason=str(error))]))
                if anchored and s in direct_straight and not q['passed']:
                    from .straight_shoulders import localize
                    for fraction in (.75,.5,.25,.125):
                        refined=localize(profile,w,fraction)
                        try:
                            candidate=certified_union(straight_body(refined,w),anchors)[0]
                            if s in domains:candidate=polygonal(candidate.difference(domains[s]))
                        except ProfileUnresolved:continue
                        refined_check,_=additions_check(s,residual[s],candidate)
                        attempts.append(dict(factor=attempts[0]['factor'],passed=refined_check['passed'],failures=refined_check['failures'],
                            decision='LOCAL_FREE_SPAN_SHOULDERS; GROUP_INTERIOR_FROZEN',fraction=fraction))
                        if refined_check['passed']:
                            actual=candidate;q=refined_check;profile=refined;smooth_plans[s]=straight_fields(refined,w);break
                if not q['passed'] and not coherent_pose:
                    barriers=[];contract=TraceWidthContract()
                    for fixed in neighbours(s,proxy):
                        barrier=clearance_barrier(fixed['geometry'],GUARD+2*MARGIN)
                        contact=residual[s].intersection(fixed['geometry'])
                        if not contact.is_empty:barrier=barrier.difference(contact.buffer(max(rows[s]['metadata']['source_port_width_mm'],fixed['trace_width_mm'])+contract.original_port_buffer_gap_mm,quad_segs=128))
                        barriers.append(barrier)
                    # Clipping optional growth cannot thin the nominal carrier.
                    # A carrier that conflicts is rejected by the addition
                    # verifier; it is never silently shaved into a neck.
                    actual=certified_union(carrier,polygonal(actual.difference(unary_union(barriers))))[0]
                    if s in domains:actual=polygonal(actual.difference(domains[s]))
                    q,proxy=additions_check(s,residual[s],actual)
                    attempts.append(dict(factor=physical_factor,passed=q['passed'],failures=q['failures'],
                        decision='DEFAULT_CASE_CONTINUOUS_PROFILE',check_scope='POSITIVE_ADDITIONS_ONLY'))
                attached=[g for lane,g in strips if s in lane['source_ids']]
                complete=polygonal(unary_union([actual,*attached]))
                connected=len(OriginalOwners(complete).owners)==1
                if q['passed'] and connected:
                    material[s]=actual
                    if anchored:
                        register_sections(s,end_sections(profile,smooth_plans[s]))
                        if s in direct_straight:frozen_straights[s]=p.digest(to_wkb(actual))
                    reports.append(dict(source_id=s,selected_factor=attempts[0]['factor'],attempts=attempts,
                        factor_semantics='CONTINUOUS_PROFILE_CEILING',
                        actual_body_sha256=p.digest(to_wkb(complete)),
                        removed_input_copper_mm2=original[s].difference(complete).area))
                    if progress:progress(dict(event='hybrid_residual',index=index+1,sources=len(residual)))
                    continue
                attempts.append(dict(passed=False,decision='CONTINUOUS_PROFILE_UNRESOLVED',
                    failures=[dict(reason='SOURCE_INTERFACE_DISCONNECTED')] if not connected else q['failures']))
                if coherent_pose:
                    reports.append(dict(source_id=s,selected_factor=1.,attempts=attempts,
                                        status='UNRESOLVED; NO_SHORT_ISLAND_FALLBACK'))
                    continue
            factor=profile['inherited_factor']
            if anchored:factor=construction['source_width_targets_mm'][s]/w
            if profile['constraints']:factor=max(x['width_mm']/w for x in profile['constraints'])
            if factor is not None and factor>1:
                factor=min(factor,physical_factor)
                if anchored:
                    candidate,invalid=curve_candidate(s,factor,profile)
                else:candidate=p.offset_part(residual[s],w,factor)
                if candidate is not None:
                    if s in domains:candidate=candidate.difference(domains[s])
                    candidate=certified_union(candidate,core)[0]if anchored else certified_union(core,candidate)[0]
                    q=additions_check(s,core,candidate)[0]if anchored else check(s,core,candidate)
                else:q=invalid
                attempts.append(dict(factor=factor,passed=q['passed'],failures=q['failures'],decision='ACQUIRED_ROUTE_GROWTH'))
                if q['passed'] and not polygonal(candidate.difference(core)).is_empty:
                    material[s]=candidate;chosen=ribbon_recipes[s]['maximum_width_mm']/w if anchored and s in ribbon_recipes else factor
                    if anchored and s in ribbon_recipes:accepted_ribbons[s]=ribbon_recipes[s]
            # An explicit default-case decision may vary width locally. The
            # previous uniform fallback reduced the entire long source when
            # only its end had a blocker, producing the short-island outcome.
            local_connector=(anchored and s not in direct_straight and s not in arc_cores
                and rows[s]['metadata']['route_kind']=='segment'and profile['length_mm']<=.1)
            if chosen==1. and (not anchored or local_connector):
                upper=curve_candidate(s,physical_factor,profile)[0]if local_connector else p.offset_part(residual[s],w,physical_factor)
                if upper is None:upper=residual[s]
                barriers=[];contract=TraceWidthContract()
                for fixed in neighbours(s,upper):
                    obstacle=fixed['geometry'];barrier=clearance_barrier(obstacle,GUARD+2*MARGIN)
                    contact=residual[s].intersection(obstacle)
                    if not contact.is_empty:
                        barrier=barrier.difference(contact.buffer(max(rows[s]['metadata']['source_port_width_mm'],fixed['trace_width_mm'])+contract.original_port_buffer_gap_mm,quad_segs=128))
                    barriers.append(barrier)
                extension=polygonal(upper.difference(unary_union(barriers)))
                if s in domains:extension=polygonal(extension.difference(domains[s]))
                candidate,method=certified_union(core,extension)
                if (local_connector and method=='EXACT_FLOOR_FALLBACK'
                        and construction['source_width_targets_mm'][s]>=w+2*ERROR_MM
                        and not polygonal(extension.difference(core)).is_empty):
                    # Give the exact source floor a positive assembly overlap.
                    # This is new candidate copper, not a containment epsilon:
                    # the unchanged verifier below checks the entire addition.
                    extension=unary_union([extension,core.buffer(ERROR_MM,quad_segs=128)])
                    candidate,retry=certified_union(core,extension)
                    method='SOURCE_SKIN_STITCH; '+retry
                q=check(s,core,candidate)
                attempts.append(dict(factor=physical_factor,passed=q['passed'],failures=q['failures'],
                                     decision='DEFAULT_CASE_LOCAL_CLEARANCE_PROFILE',finite_union=method))
                if q['passed'] and not polygonal(candidate.difference(core)).is_empty:
                    material[s]=candidate;chosen=physical_factor
                    if local_connector:
                        # The clipped body is an explicit default decision,
                        # not the original exact inherited ribbon recipe.
                        accepted_ribbons.pop(s,None)
                        attempts[-1]['endpoint_policy']='ACTUAL_CLIPPED_SKIN; FROZEN_SECTION_OBLIGATIONS_REMAIN_EXPLICIT'
            if chosen>1.:
                if anchored and s in accepted_ribbons:register_sections(s,accepted_ribbons[s]['endpoint_sections'])
                reports.append(dict(source_id=s,selected_factor=chosen,attempts=attempts,
                                    factor_semantics='PROFILE_CEILING; LOCAL_WIDTH_MAY_BE_SMALLER'))
                if progress:progress(dict(event='hybrid_residual',index=index+1,sources=len(residual)))
                continue
        for step in SCHEDULE:
            rung=min(settings.step_count,accepted_rung+step)
            candidate_settings=settings.rung(w,rung)
            if not candidate_settings['within_growth_limits'] or candidate_settings['resulting_width_mm']>cap+1e-12:continue
            if anchored:
                f=candidate_settings['factor'];profile=profiles['segments'][s]
                candidate,invalid=curve_candidate(s,f,profile)
            else:candidate=p.offset_part(residual[s],w,candidate_settings['factor'])
            if candidate is not None:
                if s in domains:
                    candidate=polygonal(candidate.difference(domains[s]))
                    candidate=certified_union(candidate,core)[0]if anchored else candidate.union(core)
                q=additions_check(s,core,candidate)[0]if anchored else check(s,core,candidate)
            else:q=invalid
            attempts.append(dict(factor=candidate_settings['factor'],passed=q['passed'],failures=q['failures']))
            if q['passed']:
                material[s]=candidate;chosen=ribbon_recipes[s]['maximum_width_mm']/w if anchored and s in ribbon_recipes else candidate_settings['factor'];accepted_rung=rung
                if anchored and s in ribbon_recipes:accepted_ribbons[s]=ribbon_recipes[s]
        reports.append(dict(source_id=s,selected_factor=chosen,attempts=attempts))
        if anchored and s in accepted_ribbons and chosen>1.:register_sections(s,accepted_ribbons[s]['endpoint_sections'])
        if progress:progress(dict(event='hybrid_residual',index=index+1,sources=len(residual)))
    residual_wall=perf_counter()-tick
    material.close()
    if phase_started is not None:phases[-1]['wall_s']=perf_counter()-phase_started
    corner_patches=[];corner_report=None;resolved_joint_sites=set()
    native_paths=construction.get('native_trace_source_ids_by_route',paths)
    if anchored and construction.get('corner_smoothing'):
        if progress:progress(dict(event='assembly_phase',phase='JOINT_CORNER_FILLS',sources=len(residual)))
        support_started=perf_counter()
        supports={s:unary_union(([material[s]]if s in material else[])+[g for lane,g in strips if s in lane['source_ids']])
                  for s in {s for ss in native_paths.values()for s in ss}}
        descriptors=corner_transition.describe(rows,native_paths,smooth_plans,frozen_straights,accepted_ribbons,arc_cores,supports=supports)
        support_wall=perf_counter()-support_started
        corner_patches,corner_report=corner_transition.run(rows,native_paths,material,owner,descriptors,
            covered=construction.get('covered_trace_projection',{}).get('covered_source_ids',[]),
            protected_domains=[]if pin.ACTIVE is None else[s.domain for s in pin.ACTIVE.slots],
            maximum_reach_mm=construction['transition_outlier_guard']['maximum_extra_reach_mm'])
        corner_report['support_preparation_wall_s']=support_wall
        corner_report['wall_s']+=support_wall
        for i,value in enumerate(corner_patches):
            key='joint:'+str(i);material[key]=value['geometry'];joint_owners[key]=scope.ids[value['source_id']]
        sites={}
        for record in corner_report['reports']:
            key=record['route_id'],tuple(round(v,10)for v in record['endpoint_mm'])
            sites.setdefault(key,[]).append(record['status'])
        resolved_joint_sites={key for key,statuses in sites.items()if all(s in('FILLED','ALREADY_COVERED')for s in statuses)}
        phases.append(dict(phase='JOINT_CORNER_FILLS',wall_s=corner_report['wall_s']))
        if progress:progress(dict(event='joint_corner_fills',filled=corner_report['filled'],unresolved=corner_report['unresolved'],wall_s=corner_report['wall_s']))
    assembly_cuts={};finish_report=None
    if anchored and corner_report is not None:
        from .tangent_finish import run as finish
        assembled_sources={s:unary_union(([material[s]]if s in material else[])+[g for lane,g in strips if s in lane['source_ids']]+
            [v['geometry']for v in corner_patches if v['source_id']==s])for ss in native_paths.values()for s in ss}
        assembly_cuts,finish_report=finish(rows,native_paths,assembled_sources,descriptors,
            [(lane['source_ids'],g)for lane,g in strips],covered=construction.get('covered_trace_projection',{}).get('covered_source_ids',[]),source_cores=references)
        phases.append(dict(phase='SUBTRACTIVE_TANGENT_FINISH',wall_s=finish_report['wall_s']))
        if progress:progress(dict(event='tangent_finish',trimmed=finish_report['trimmed_joints'],wall_s=finish_report['wall_s']))
    # Finishing removes only optional corner copper. Never subtract a mask
    # from a frozen source/group body: even a coincident-edge difference can
    # mint numerical fragments in an otherwise unchanged support.
    finished_patches=corner_patches
    if finish_report is not None:
        from .tangent_finish import materialize as materialize_finish
        floor_started=perf_counter()
        route_floors={r:unary_union([material[s]for s in ss if s in material]+[g for lane,g in strips if lane.get('route_id')==r or set(lane['source_ids']).intersection(ss)])for r,ss in native_paths.items()}
        finished_patches,attachment=materialize_finish(corner_patches,assembly_cuts,route_floors)
        finish_report['attachment']=attachment
        finish_report['wall_s']+=perf_counter()-floor_started
        phases[-1]['wall_s']=finish_report['wall_s']
    tick=perf_counter();connections=[]
    for r,ss in sorted(native_paths.items()):
        baseline=unary_union([original[s] for s in ss])
        attached=[g for lane,g in strips if lane.get('route_id')==r or set(lane['source_ids']).intersection(ss)]
        assembled=unary_union([material[s]for s in ss if s in material]+attached+[v['geometry']for v in finished_patches if v['route_id']==r])
        old_count=len(OriginalOwners(baseline).owners)
        new_count=len(OriginalOwners(assembled).owners)
        connections.append(dict(route_id=r,source_components=old_count,assembled_components=new_count,
                                passed=new_count<=old_count))
    connection_wall=perf_counter()-tick
    final_material=dict(material)
    for i,v in enumerate(finished_patches):final_material['joint:'+str(i)]=v['geometry']
    functional_checks=changed_owner_checks(reference_material,final_material) if coherent_pose else None
    bodies={}
    if continuous:
        for s in sorted(used):
            attached=[g for lane,g in strips if s in lane['source_ids']]
            body=unary_union(([material[s]] if s in material else [])+attached+[v['geometry']for v in finished_patches if v['source_id']==s])
            bodies[s]=dict(wkb_hex=to_wkb(body).hex(),source_segment_split=False,
                           connected_components=len(OriginalOwners(body).owners))
            if s in arc_cores and arc_cores[s].get('complete_member'):
                bodies[s].update(body_scope='MAXIMAL_MEMBER_SHARED_CONTOUR',
                                 shared_arc_member_id=arc_cores[s]['member_id'],
                                 member_source_ids=arc_cores[s]['member_source_ids'])
            added_joints=sum(v['source_id']==s for v in corner_patches)
            if added_joints:
                bodies[s]['joint_additions']=added_joints
                if s in arc_cores and arc_cores[s].get('complete_member'):
                    bodies[s]['body_scope']='MAXIMAL_MEMBER_SHARED_CONTOUR_PLUS_JOINT_ADDITIONS'
    # A rejected default joint cannot quietly remain a narrow KEEP next to a
    # widened frozen end. This is an interface/custody gate on defaults, not a
    # clearance audit of the constructed group.
    endpoint_failures=[f for f in section_conflicts if endpoint_key(f['source_id'],f['endpoint_mm'])not in resolved_joint_sites];endpoint_checked=0
    if anchored:
        for s in sorted(used):
            if s in arc_cores and arc_cores[s].get('complete_member'):continue
            body=material.get(s)
            if body is None:continue
            attached=[g for lane,g in strips if s in lane['source_ids']]
            body=unary_union([body,*attached])
            pts=rows[s]['metadata']['route_points_mm']
            for pt in(pts[0],pts[-1]):
                if endpoint_key(s,pt)in resolved_joint_sites:continue
                section=endpoint_sections.get(endpoint_key(s,pt))
                if section is None:continue
                endpoint_checked+=1
                line=LineString([section['lower_mm'],section['upper_mm']])
                missing=line.difference(body.buffer(ERROR_MM,quad_segs=128)).length
                if missing>ERROR_MM:
                    endpoint_failures.append(dict(source_id=s,endpoint_mm=pt,missing_section_length_mm=missing,reason='FROZEN_END_SECTION_NOT_REALIZED_BY_DEFAULT_JOINT'))
    assert before_hash=={s:p.digest(to_wkb(g)) for s,g in group_fixed.items()}
    assert all(p.digest(to_wkb(material[s]))==h for s,h in frozen_straights.items())
    covered_ids=construction.get('covered_trace_projection',{}).get('covered_source_ids',[])
    assert all(to_wkb(material[s])==to_wkb(current[s])for s in covered_ids)
    return dict(schema='t04-hybrid-components/1',status='COMPONENT_DIAGNOSTIC; NOT_COMPLETE_T04',
                joints=dict(wall_s=joint_wall,reports=joint_reports),
                bulk=dict(wall_s=bulk_wall,changed_sources=sorted(bulk_changes),restored_sources=restored,error=bulk_error),
                residual=dict(wall_s=residual_wall,reports=reports,pass_increments=list(SCHEDULE)),
                joint_connections=dict(wall_s=connection_wall,reports=connections),
                continuous_source_bodies=bodies,
                smooth_source_field_plans=smooth_plans,
                phase_order=phases,frozen_straight_hashes=frozen_straights,
                component_setup_wall_s=component_setup_wall,
                frozen_endpoint_obligations=dict(passed=not endpoint_failures,checked=endpoint_checked,failures=endpoint_failures),
                straight_copper_preserved_through_later_phases=True,
                covered_trace_copper_preserved=True,covered_trace_sources=covered_ids,
                assembly_overlap_mm=2*ERROR_MM if anchored else 0.,
                inherited_sided_ribbons=accepted_ribbons,
                corner_smoothing=corner_report,
                tangent_finishing=finish_report,
                tangent_cut_shapes={s:dict(wkb_hex=to_wkb(cut).hex())for s,cut in assembly_cuts.items()},
                corner_fill_shapes=[dict(source_id=v['source_id'],route_id=v['route_id'],endpoint_mm=v['endpoint_mm'],side=v['side'],wkb_hex=to_wkb(v['geometry']).hex(),recipe=v['recipe'])for v in corner_patches],
                finished_corner_fill_shapes=[dict(source_id=v['source_id'],route_id=v['route_id'],wkb_hex=to_wkb(v['geometry']).hex())for v in finished_patches],
                resolved_joint_sites=[dict(route_id=r,endpoint_mm=list(pt),resolution='ADDITIVE_NATIVE_FRAME_JOINT_FIELD; END_SECTIONS_MAY_DIFFER')for r,pt in sorted(resolved_joint_sites)],
                arc_group_construction=arc_proof,
                arc_core_shapes={k:dict(wkb_hex=to_wkb(v['body']).hex(),group_id=v['group_id'],
                                       member_id=v.get('member_id'),member_source_ids=v.get('member_source_ids',[k]))for k,v in arc_cores.items()},
                changed_bulk_copper={s:dict(wkb_hex=to_wkb(material[s]).hex())for s in bulk_changes},
                route_pose=pose_proof,reference_checks=reference_checks,functional_checks=functional_checks,
                reference_translations_by_source={s:profiles['segments'][s]['route_translation_mm']for s in used} if coherent_pose else {},
                constructed_groups_audited=0,constructed_group_bytes_preserved=True,
                output_scene_ref=None,publication_ready=False,wall_s=perf_counter()-started,
                pending=['FUNCTIONAL_SOURCE_VOID_CHECKS','REJECTED_JOINT_REFINEMENT','FINAL_WIDTH_BAND_RECONCILIATION'],
                full_board_run=False,replay=False)
