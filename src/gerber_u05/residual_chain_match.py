"""Route-local residual chains, budgeted before full-span ribbon allocation.

Both nominal and already-grown residuals participate. Native source seams are
custody boundaries, never new taper boundaries. Shared contours follow the
existing maximal-arc representation; constructed groups remain fixed support.
"""
from collections import defaultdict
from time import perf_counter
import numpy as np
from shapely import to_wkb
from shapely.geometry import LineString
from shapely.ops import unary_union
from shapely.errors import GEOSException
from .ribbon_profile import frame,match_ends
from .smooth_transition import value,restrict
from .finite_profile_union import certified_union,polygonal
from .normalized_additions import verify_patch
from .residual_chain_budget import Budgets
from src.native_inventory import ERROR_MM
from src.stage_abi.store import canonical,digest


def point_key(pt):return tuple(round(float(v),10)for v in pt)


def chains(rows,paths,eligible):
    """Follow native endpoints inside each route, never regroup by proximity.

    Only maximal, open, unbranched same-width components receive a shared
    profile. Other components retain their preceding copper and an explicit
    deferral. A chain is a treatment inside a route, not a parallel group.
    """
    result=[];deferred=[]
    for route,sources in sorted(paths.items()):
        live=set(sources)&eligible;incidence=defaultdict(list)
        for s in live:
            pts=rows[s]['metadata']['route_points_mm']
            for pt in(pts[0],pts[-1]):incidence[point_key(pt)].append(s)
        while live:
            seed=min(live);component={seed};todo=[seed]
            while todo:
                s=todo.pop();pts=rows[s]['metadata']['route_points_mm']
                for pt in(pts[0],pts[-1]):
                    for other in incidence[point_key(pt)]:
                        if other not in component:component.add(other);todo.append(other)
            live-=component;endpoints=[]
            for pt,ss in incidence.items():
                count=len(set(ss)&component)
                if count==1:endpoints.append(pt)
                elif count>2:break
            else:
                if len(endpoints)==2:
                    widths=[rows[s]['metadata']['minimum_caliper_mm']for s in component]
                    if max(widths)-min(widths)<=1e-12:
                        cursor=min(endpoints);unused=set(component);points=[];intervals=[];station=0.
                        while unused:
                            s=min(set(incidence[cursor])&unused);unused.remove(s);pts=rows[s]['metadata']['route_points_mm'];forward=point_key(pts[0])==cursor
                            pts=pts if forward else pts[::-1];length=LineString(pts).length
                            points.extend(pts if not points else pts[1:]);intervals.append(dict(source_id=s,first_mm=station,last_mm=station+length,forward=forward));station+=length;cursor=point_key(pts[-1])
                        result.append(dict(route_id=route,source_ids=[x['source_id']for x in intervals],points=points,intervals=intervals,width=widths[0],length_mm=station));continue
            deferred.append(dict(route_id=route,source_ids=sorted(component),reason='BRANCH_CLOSED_OR_NONUNIFORM_CHAIN; PRECEDING_RESULT_RETAINED'))
    return result,deferred


def local_recipe(recipe,chain,interval):
    """Restrict one shared cubic without turning custody seams into joints.

    Source direction can reverse the local controls and endpoint normals.
    Shared native-chain metadata still identifies the true two outer ends.
    Only floating-point roundoff at those ends may be clamped to [0, 1].
    """
    points,normals,stations,L=frame(chain['points']);w=chain['width']
    first,last=interval['first_mm'],interval['last_mm']
    if first<-1e-12 or last>L+1e-12 or first>last:raise ValueError('CHAIN_SOURCE_INTERVAL_OUTSIDE_NATIVE_PATH')
    first,last=max(0.,first),min(L,last);pieces=[];cursor=0.
    for proof in recipe['side_field_proofs']:
        end=cursor+proof['length_mm'];pieces.append((cursor,end,proof));cursor=end
    if abs(cursor-L)>1e-9:raise ValueError('CHAIN_FIELD_LENGTH_CHANGED')
    sections=[]
    for t in(first,last):
        j=int(np.argmin(abs(stations-t)));center=points[j];n=normals[j]
        if abs(t)<1e-10:n=np.asarray(recipe['endpoint_sections'][0]['normal'])
        elif abs(t-L)<1e-10:n=np.asarray(recipe['endpoint_sections'][1]['normal'])
        lo,hi,proof=next((q for q in pieces if t<=q[1]+1e-12),pieces[-1])
        faces=[value(c,min(1.,max(0.,(t-lo)/(hi-lo))))for c in proof['controls']]
        sections.append(dict(normal=n.tolist(),lower_mm=(center-n*(w/2+faces[0])).tolist(),upper_mm=(center+n*(w/2+faces[1])).tolist()))
    parts=[]
    for lo,hi,proof in pieces:
        a,b=max(first,lo),min(last,hi)
        if b-a<=1e-12:continue
        controls=[restrict(c,max(0.,(a-lo)/(hi-lo)),min(1.,(b-lo)/(hi-lo)))for c in proof['controls']]
        if not interval['forward']:controls=[c[::-1]for c in controls[::-1]]
        length=b-a
        parts.append(dict(proof,controls=controls,length_mm=length,
            endpoint_derivatives=[[3*(c[1]-c[0])/length,3*(c[3]-c[2])/length]for c in controls]))
    if not interval['forward']:
        parts.reverse()
        sections=[dict(normal=(-np.asarray(e['normal'])).tolist(),lower_mm=e['upper_mm'],upper_mm=e['lower_mm'])for e in sections[::-1]]
    return dict(recipe,endpoint_sections=sections,side_field_proofs=parts,length_mm=last-first,
        shared_residual_chain_id=chain['chain_id'],member_source_ids=chain['source_ids'],
        shared_chain_points_mm=chain['points'],shared_chain_side_field_proofs=recipe['side_field_proofs'],
        shared_chain_endpoint_sections=recipe['endpoint_sections'],
        real_endpoints=([abs(first)<1e-10,abs(last-L)<1e-10]if interval['forward']else[abs(last-L)<1e-10,abs(first)<1e-10]),
        source_interval_mm=dict(interval),native_seam_is_transition=False,
        maximum_width_mm=w+max(sum(c[k]for c in part['controls'])for part in parts for k in range(4)))


def run(rows,material,paths,reports,endpoint_sections,width_caps,fixed_sources,owner,*,deviation=.1,protected_domains=(),source_cores=None,route_supports=None,replace_optional_floor=False):
    """Budget and admit residual chains after default growth, before joints.

    ``material`` and matching source decisions in ``reports`` are updated only
    for admitted chains. All source recipes are prepared before any member is
    changed. The return value is (accepted source recipes, diagnostic report).
    Nominal and already-grown residuals participate; ``fixed_sources`` excludes
    group interiors. Each registered end has its own matching interval.

    Budgets precede allocation. The existing positive-addition and differential
    pocket checks then govern only residual changes. Any construction limit
    retains the preceding chain, including its entire grown copper floor.
    """
    started=perf_counter();fixed=set(fixed_sources);decisions={v['source_id']:v for v in reports}
    if replace_optional_floor and source_cores is None:raise ValueError('SMOOTH_CHAIN_REQUIRES_AUTHENTICATED_SOURCE_CORES')
    eligible={s for ss in paths.values()for s in ss if s not in fixed and s in material and s in decisions and rows[s]['metadata']['aperture_family'][0]=='C'}
    grown_count=sum(decisions[s]['selected_factor']>1+1e-10 for s in eligible)
    planned,deferred=chains(rows,paths,eligible);records=[];ready={};accepted={};verifications=0;addition_distances=0;route_floors={}
    for chain in planned:
        sources=chain['source_ids'];w=chain['width'];ends=[endpoint_sections.get((chain['route_id'],point_key(pt)))for pt in(chain['points'][0],chain['points'][-1])]
        wider=any(e is not None and np.linalg.norm(np.subtract(e['upper_mm'],e['lower_mm']))>w+ERROR_MM for e in ends)
        if not wider and not(replace_optional_floor and any(decisions[s]['selected_factor']>1+1e-10 for s in sources)):
            deferred.append(dict(route_id=chain['route_id'],source_ids=sources,reason='NO_REGISTERED_WIDER_BOUNDARY'));continue
        cid='RC-'+digest(canonical([chain['route_id'],sources]))[:16];chain['chain_id']=cid
        cap=min(width_caps[s]for s in sources)-(0. if replace_optional_floor else 2*ERROR_MM)
        row=dict(chain_id=cid,route_id=chain['route_id'],source_ids=sources,length_mm=chain['length_mm'],preceding_factors={s:decisions[s]['selected_factor']for s in sources})
        records.append(row)
        if cap<=w:row.update(status='KEEP_PRECEDING_RESULT; CONSTRUCTION_LIMIT',reason='NO_WIDTH_HEADROOM_FOR_NOMINAL_SKIN');continue
        try:pts,n,ts,L=frame(chain['points'])
        except ValueError as error:
            if str(error) not in ('RESIDUAL_MITER_OUTLIER','RESIDUAL_REVERSAL_JOIN_UNSUPPORTED'):raise
            row.update(status='KEEP_PRECEDING_RESULT; CONSTRUCTION_LIMIT',reason=str(error));continue
        # Match the constructor's endpoint frame before deriving rail budgets.
        for j,end in zip((0,-1),ends):
            if end is not None:
                vector=np.subtract(end['upper_mm'],end['lower_mm']);normal=vector/np.linalg.norm(vector);n[j]=normal if n[j]@normal>=0 else-normal
        ratio=max(1.,float(np.linalg.norm(n,axis=1).max()))
        chain.update(owner=tuple(owner(sources[0])),ends=ends,target=cap,normal_ratio=ratio,wider_boundary=wider,
            reach_cap=(cap-w)*ratio,total_growth_cap=(cap-w)*ratio,
            rails={side:LineString(pts+sign*n*w/2)for side,sign in(('negative',-1),('positive',1))},record=row)
        if any(tuple(owner(s))!=chain['owner']for s in sources):row.update(status='KEEP_PRECEDING_RESULT; CONSTRUCTION_LIMIT',reason='CHAIN_OWNER_CHANGED');continue
        ready[cid]=chain
    tick=perf_counter();operands=[(s,owner(s),g)for s,g in material.items()];operands.extend((f'protected:{i}',(f'protected:{i}',),g)for i,g in enumerate(protected_domains))
    workspace=Budgets(operands);allocation,witnesses=workspace.allocate(ready);budget_wall=perf_counter()-tick
    if allocation is not None:
        for cid,c in sorted(ready.items()):
            row=c['record'];sources=c['source_ids'];w=c['width'];floor=unary_union([material[s]for s in sources]);own=c['owner']
            try:
                budgets={side:allocation['growth_mm'][cid+'#'+side]/c['normal_ratio']for side in('negative','positive')}
                slope=1. if len(sources)==1 and rows[sources[0]]['metadata']['route_kind']=='segment'and c['length_mm']<=.1 else .25
                if replace_optional_floor and not c['wider_boundary']:
                    from .ribbon_profile import build
                    target=min(c['target'],w+2*min(budgets.values()))
                    body,recipe=build(c['points'],w,target,ends=c['ends'],maximum_side_slope=slope)
                    recipe['transition_policy']='SHARED_FULL_CHAIN_CUBIC; ORIGINAL_FLOOR_ONLY'
                elif replace_optional_floor:
                    from .ribbon_profile import exact_ends
                    body,recipe=exact_ends(c['points'],w,c['target'],ends=c['ends'],face_budgets=budgets,maximum_side_slope=slope)
                else:
                    body,recipe=match_ends(c['points'],w,c['target'],ends=c['ends'],deviation=deviation,
                        maximum_side_slope=slope,face_budgets=budgets,free_unmatched_ends=True)
                if replace_optional_floor:
                    from .source_trace_floor import preserve
                    core=unary_union([source_cores[s]for s in sources])
                    proposed,floor_proof=preserve(core,body);method='AUTHENTICATED_SOURCE_FLOOR; OPTIONAL_PROFILE_REPLACED'
                    row['original_floor_check']=floor_proof
                else:proposed,method=certified_union(floor,body)
                if method=='EXACT_FLOOR_FALLBACK'and source_cores is not None:
                    core=unary_union([source_cores[s]for s in sources]);body=unary_union([body,core.buffer(ERROR_MM,quad_segs=128)]);proposed,method=certified_union(floor,body)
                if method=='EXACT_FLOOR_FALLBACK':raise ValueError('CHAIN_CANNOT_RETAIN_EXACT_GROWN_FLOOR')
                delta=polygonal(proposed.difference(floor))
                fixed_neighbors=[]if delta.is_empty else[dict(id=k,geometry=g)for k,g in workspace.neighbors(delta,own,.0401+ERROR_MM)]
                q=verify_patch(delta,fixed_neighbors);verifications+=1
                addition_distances+=len(q['pairs'])
                row.update(recipe=recipe,addition_check=q,finite_union=method,face_budgets_mm=budgets)
                if not q['passed']:row.update(status='KEEP_PRECEDING_RESULT; RESIDUAL_ADDITION_CONFLICT');continue
                # The existing corner check starts AFTER residual growth.
                # Reuse its differential kernel here as well, against this
                # route's exact floor and fixed group support, never an audit
                # of a constructed group submitted as a candidate.
                from .corner_transition import new_pocket_regions
                route=c['route_id']
                if route not in route_floors:
                    route_floors[route]=unary_union([material[s]for s in paths[route]if s in material]+list((route_supports or {}).get(route,())))
                trial=(unary_union([proposed,*[material[s]for s in paths[route]if s not in sources and s in material],
                                   *list((route_supports or {}).get(route,()))])if replace_optional_floor else
                       unary_union([route_floors[route],proposed]))
                pockets=new_pocket_regions(route_floors[route],trial)
                row['pocket_check']=dict(passed=not pockets,new_pocket_areas_mm2=[g.area for g in pockets],constructed_groups_audited=0)
                if pockets:row.update(status='KEEP_PRECEDING_RESULT; NEW_RESIDUAL_POCKET');continue
                # Deterministic input pair budgets cover every future chain.
                # Existing floor remains fixed; no rejected proposal is reserved.
                # Prepare every source receipt before mutating any member.
                # A failed restriction must retain the entire previous chain.
                local={interval['source_id']:local_recipe(recipe,c,interval)for interval in c['intervals']}
                for interval in c['intervals']:
                    s=interval['source_id']
                    material[s]=proposed
                    accepted[s]=local[s]
                    d=decisions[s];factor=accepted[s]['maximum_width_mm']/w
                    d.update(selected_factor=factor if replace_optional_floor else max(d['selected_factor'],factor),status='MATCHED_RESIDUAL_CHAIN_ENDS',
                             factor_semantics='PROFILE_CEILING; ORIGINAL_SOURCE_FLOOR_RETAINED'if replace_optional_floor else'PROFILE_CEILING; GROWN_FLOOR_RETAINED')
                    d.setdefault('attempts',[]).append(dict(passed=True,failures=[],decision='BUDGETED_RESIDUAL_CHAIN',chain_id=cid,geometry_verification_scope='RESIDUAL_POSITIVE_ADDITIONS_ONLY'))
                row.update(status='MATCHED_CHAIN_FLOOR; TRANSITIONS_EXTENDED'if delta.is_empty else'CONSTRUCTED_FROM_MATCHED_CHAIN_ENDS',shared_contour_sha256=digest(to_wkb(proposed)),source_seams_are_treatments=False,added_area_mm2=delta.area)
                row.update(optional_floor_replaced=replace_optional_floor,removed_optional_area_mm2=floor.difference(proposed).area if replace_optional_floor else 0.)
                route_floors[route]=trial
                workspace.add('accepted:'+cid,own,delta)
            except(ValueError,GEOSException)as error:row.update(status='KEEP_PRECEDING_RESULT; CONSTRUCTION_LIMIT',reason=str(error))
    return accepted,dict(schema='t04-residual-chain-end-match/1',deviation=deviation,reports=records,deferred_chains=deferred,
        eligible_sources=len(eligible),proposed_sources=sum(len(c['source_ids'])for c in ready.values()),constructed_sources=len(accepted),
        constructed_chains=sum(v['status']=='CONSTRUCTED_FROM_MATCHED_CHAIN_ENDS'for v in records),
        profiled_chains=sum(v['status']in('CONSTRUCTED_FROM_MATCHED_CHAIN_ENDS','MATCHED_CHAIN_FLOOR; TRANSITIONS_EXTENDED')for v in records),
        new_copper_sources=sum(len(v['source_ids'])for v in records if v['status']=='CONSTRUCTED_FROM_MATCHED_CHAIN_ENDS'),
        already_grown_sources_considered=grown_count,
        group_interiors_changed=False,constructed_groups_audited=0,r_tree_queries=0,
        candidate_geometry_verifications=verifications,input_rail_distance_calls=workspace.distance_calls,
        residual_addition_distance_calls=addition_distances,geometry_distance_calls=workspace.distance_calls+addition_distances,
        complete_operand_binding=workspace.binding,accepted_operand_extensions=workspace.accepted,input_rail_allocation=allocation,input_rail_witnesses=witnesses,
        input_bounds_screen=dict(proof='COMPLETE_RAIL_SEGMENT_BUCKET_AABB_EXCLUSION',queries=workspace.screen_queries,
            excluded_nonbinding_pairs=workspace.screen_rejections,workspace_cells=workspace.screen_cells,candidates_dropped=0),
        budget_setup_wall_s=budget_wall,wall_s=perf_counter()-started)
