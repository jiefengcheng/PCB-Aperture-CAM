"""25% outer-band refinement anchored to frozen 10% proposal parameters.

No native proof or accepted state is reused. Every baseline body is rebuilt
from the accepted T03 source and checked against the reference shape hash.
Extensions reserve space for every baseline route before fresh T04 checks.
"""
from pathlib import Path
from time import perf_counter
import json,hashlib,math
from shapely import STRtree,to_wkb
from shapely.geometry import LineString,Polygon
from shapely.ops import unary_union
from shapely.affinity import translate
from src.trace_width_clearance import TraceWidthContract
from .limiting_math import GUARD,MARGIN
from .finite_profile_union import certified_union,polygonal


def contains_floor(body,baseline):
    return body.equals_exact(baseline,0) or body.covers(baseline)


def clearance_barrier(geometry,required):
    # GEOS round buffers use inscribed chords. Inflate the radius by a
    # conservative full segment-angle cosine so those chords also reserve the
    # required Euclidean distance, including BOTH checking-envelope margins.
    return geometry.buffer(required/math.cos(math.pi/(2*128)),quad_segs=128)


def band_at(plan,f):
    if plan.get('side_specific_profile'):
        # Progress controls the optional supplement, not an invented symmetric
        # radius. The total cap is fixed and checked at every progress value.
        return plan['corridor_width_mm'],plan['outer_width_ceiling_mm']
    w=plan['source_width_mm'];base=plan.get('construction_floor_profile',plan.get('baseline_profile'))
    if base is None:
        t=(f-1)/.5
        return w+(plan['corridor_width_mm']-w)*t,w+(plan['outer_width_ceiling_mm']-w)*t
    floor=base['factor'];cap=plan['progress_cap']
    if f<=floor+1e-12:
        t=1. if abs(f-floor)<1e-12 else 0. if floor==1 else (f-1)/(floor-1)
        return w+(base['corridor_width_mm']-w)*t,w+(base['outer_width_ceiling_mm']-w)*t
    t=1. if abs(f-cap)<1e-12 else (f-floor)/(cap-floor)
    return base['corridor_width_mm'],base['outer_width_ceiling_mm']+(plan['outer_width_ceiling_mm']-base['outer_width_ceiling_mm'])*t


def body_at(core,width,plan,data,f,*,envelope=False):
    from .translated_profile import profile_body
    low,high=band_at(plan,f);base=plan.get('construction_floor_profile',plan.get('baseline_profile'))
    if abs(f-base['factor'])<1e-12 or f>base['factor'] and data['allowed_extension'].is_empty:body=data['baseline_body']
    elif abs(f-plan['progress_cap'])<1e-12:body=data['maximum_body']
    else:
        proposal_low=low
        if plan.get('incremental_corridor_fill') and f>base['factor']:
            t=(f-base['factor'])/(plan['progress_cap']-base['factor'])
            proposal_low=base['corridor_width_mm']+(plan['outer_width_ceiling_mm']-base['corridor_width_mm'])*t
        body=profile_body(core,width,proposal_low,high,plan['translation_mm'],data['line'],data['forbidden'])
        if f>base['factor']:
            body,_=certified_union(data['baseline_body'],body.intersection(data['allowed_extension']))
    body=polygonal(body)
    return body.buffer(MARGIN,quad_segs=128) if envelope else body


def plan(rows,current,original,paths,roles,context,settings,rule,progress=None):
    from . import pipeline as p
    from .translated_profile import profile_body,SCHEMA
    started=perf_counter();incremental=bool(rule.get('incremental_corridor_fill'));contract=TraceWidthContract();raw=p.canonical(rule['baseline_seed_data']) if 'baseline_seed_data' in rule else Path(rule['baseline_seed']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=rule['baseline_seed_sha256']:raise ValueError('T04_PROFILE_REFERENCE_HASH_CHANGED')
    seed=json.loads(raw)
    if seed['schema']!='t04-profile-refinement-reference/1' or seed['source_sha256']!=rule['input_binding']['source_sha256'] or seed['input_scene_sha256']!=rule['input_binding']['scene_ref']['sha256'] or set(seed['routes'])!=set(paths):raise ValueError('T04_PROFILE_REFERENCE_BINDING_CHANGED')
    if not seed['reference_only'] or seed['proof_reuse']:raise ValueError('T04_PROFILE_REFERENCE_PROOF_REUSE_FORBIDDEN')
    used={s for ss in paths.values() for s in ss};cores={r:unary_union([original[s] for s in ss]) for r,ss in paths.items()}
    fixedids=sorted(s for s in set(rows)-used-set(roles) if not current[s].is_empty);fixed=[current[s] for s in fixedids];tree=STRtree(fixed)
    owner={r:context.ids[ss[0]] for r,ss in paths.items()};data={};plans={};bodies={}
    for r,ss in sorted(paths.items()):
        ref=seed['routes'][r];w=rows[ss[0]]['metadata']['minimum_caliper_mm'];cap=min(w*settings.maximum_factor,w+settings.maximum_total_width_increase_mm)
        if ss!=ref['source_ids'] or w!=ref['source_width_mm'] or any(rows[s]['metadata']['minimum_caliper_mm']!=w or context.ids[s]!=owner[r] for s in ss):raise ValueError('T04_PROFILE_REFERENCE_ROUTE_CHANGED')
        pose=tuple(ref['translation_mm']);low=ref['corridor_width_mm'];basehigh=ref['outer_width_ceiling_mm']
        if math.hypot(*pose)>.025+1e-12 or not w<=low<=basehigh<=min(cap,low*1.10)+1e-12:raise ValueError('T04_PROFILE_REFERENCE_BAND_INVALID')
        high=min(cap,low*rule['width_variation_limit']+low)
        hits=sorted(map(int,tree.query(cores[r],predicate='dwithin',distance=(cap-w)/2+.025+GUARD+2*MARGIN)))
        foreign=[fixed[i] for i in hits if context.ids[fixedids[i]]!=owner[r]]
        forbidden=unary_union([g.buffer(GUARD+2*MARGIN,quad_segs=128) for g in foreign])
        lines=[LineString(rows[s]['metadata']['route_points_mm']) for s in ss];straight=[g for s,g in zip(ss,lines) if rows[s]['metadata']['route_kind']=='segment'];line=max(straight or lines,key=lambda g:g.length)
        body=profile_body(cores[r],w,low,basehigh,pose,line,forbidden)
        if p.digest(to_wkb(body))!=ref['body_sha256']:raise ValueError('T04_PROFILE_REFERENCE_RECONSTRUCTION_CHANGED:'+r)
        # The actual v2 caller uses an abstract 1..maximum_factor profile
        # progress for every route. Numeric width caps govern the band itself;
        # physical source-width rung eligibility is not this progress scale.
        top=settings.maximum_factor;floor=1+(top-1)*.4
        plans[r]=dict(translation_mm=list(pose),source_width_mm=w,source_width_cap_mm=cap,corridor_width_mm=low,outer_width_ceiling_mm=high,progress_cap=top,baseline_profile=dict(factor=floor,corridor_width_mm=low,outer_width_ceiling_mm=basehigh,body_sha256=ref['body_sha256']),candidate_count=2,fixed_contact_components=None)
        plans[r]['incremental_corridor_fill']=incremental
        data[r]=dict(width=w,cap=cap,line=line,foreign=unary_union(foreign),forbidden=forbidden,baseline_body=body,fixed_hits=hits)
        bodies[r]=body
    # All immutable foreign surfaces and ALL baseline routes reserve their
    # corridors. Subsequent optional extensions may consume only free space.
    baseline_tree=STRtree([bodies[r] for r in sorted(paths)]);keys=sorted(paths);chosen={};clipped=0;coverage_fallback=[];protected_pair_count=0;union_methods={};normalized_supplements=0
    moved={r:translate(cores[r],xoff=q['translation_mm'][0],yoff=q['translation_mm'][1]) for r,q in plans.items()}
    halo=max((d['cap']-d['width'])/2 for d in data.values())
    for idx,r in enumerate(keys):
        q=plans[r];d=data[r];rawbody=profile_body(cores[r],d['width'],q['outer_width_ceiling_mm'] if incremental else q['corridor_width_mm'],q['outer_width_ceiling_mm'],q['translation_mm'],d['line'],d['forbidden'])
        barriers_list=[]
        for i in sorted(map(int,baseline_tree.query(rawbody.envelope.buffer(GUARD+2*MARGIN+halo)))):
            other=keys[i]
            if other==r:continue
            if owner[other]!=owner[r] or incremental:
                block=chosen[other]['body'] if other in chosen else bodies[other]
                barrier=clearance_barrier(block,GUARD+2*MARGIN)
                if owner[other]==owner[r]:
                    contact=moved[r].intersection(moved[other])
                    if not contact.is_empty:
                        # Only source-defined original contact is exempt. The
                        # smaller source width gives a conservative port.
                        port=contact.buffer(min(d['width'],data[other]['width'])+contract.original_port_buffer_gap_mm,quad_segs=contract.port_quad_segs)
                        barrier=barrier.difference(port)
                    protected_pair_count+=1
                barriers_list.append(barrier)
        if incremental:
            # Physical owner equality does not erase protected local branches.
            # Preserve source ports while reserving the other fixed surfaces.
            for i in d['fixed_hits']:
                sid=fixedids[i];barrier=clearance_barrier(fixed[i],GUARD+2*MARGIN)
                if context.ids[sid]==owner[r]:
                    contact=moved[r].intersection(original[sid])
                    if not contact.is_empty:
                        port=contact.buffer(d['width']+contract.original_port_buffer_gap_mm,quad_segs=contract.port_quad_segs)
                        barrier=barrier.difference(port)
                    protected_pair_count+=1
                barriers_list.append(barrier)
        barriers=unary_union(barriers_list)
        extension=rawbody.difference(bodies[r]).difference(barriers)
        normalized_supplements+=extension.geom_type not in ('Polygon','MultiPolygon')
        extension=polygonal(extension)
        body,method=certified_union(bodies[r],extension)
        union_methods[method]=union_methods.get(method,0)+1
        if method=='EXACT_FLOOR_FALLBACK':
            coverage_fallback.append(dict(route=r,discarded_extension_mm2=extension.area,baseline_uncovered_mm2=0.));extension=Polygon()
        d['allowed_extension']=extension;d['maximum_body']=body
        if not contains_floor(body,bodies[r]) or not body.is_valid or body.geom_type not in ('Polygon','MultiPolygon'):raise ValueError('T04_PROFILE_BASELINE_NOT_RETAINED:'+r)
        clipped+=rawbody.difference(body).area>1e-12
        chosen[r]=dict(pose=tuple(q['translation_mm']),low=q['corridor_width_mm'],high=q['outer_width_ceiling_mm'],body=body,delta=body.difference(context.cores[owner[r][0]]))
        if progress:progress(dict(event='profile_refinement',route=r,index=idx+1,routes=len(paths)))
    receipt=dict(finite_union_methods=union_methods,non_polygonal_supplements_normalized=normalized_supplements,incremental_corridor_fill=incremental,protected_same_owner_reservations=protected_pair_count,incremental_policy='REBUILD_EXACT_SAVED_10_FROM_T03; RESERVE_ALL_FLOORS; SOURCE_PORT_AWARE_CORRIDOR_AND_OUTER_SUPPLEMENTS' if incremental else 'OUTER_ONLY',schema=SCHEMA,width_variation_limit=rule['width_variation_limit'],maximum_translation_mm=.025,transition_length_mm=.05,route_plans=plans,planning_seconds=perf_counter()-started,exact_pair_checks=0,baseline_reference=dict(seed_sha256=rule['baseline_seed_sha256'],source_stage_sha256=seed['source_stage_sha256'],reference_only=True,proof_reuse=False),baseline_retention='EVERY_REBUILT_REFERENCE_BODY_RESERVED_BEFORE_OPTIONAL_EXTENSION',clipped_outer_profiles=clipped,exact_baseline_coverage_fallbacks=coverage_fallback,extension_barrier=dict(required_distance_mm=GUARD+2*MARGIN,quad_segs=128,radius_mm=(GUARD+2*MARGIN)/math.cos(math.pi/(2*128)),role='CIRCUMSCRIBED_CONSTRUCTION_RESERVATION; physical clearance threshold unchanged'))
    return chosen,data,cores,receipt
