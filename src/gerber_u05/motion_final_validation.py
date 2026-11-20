"""Mandatory post-construction checks against the actual pre-motion scene.

The translated reference is not used to excuse copper introduced by the move.
All new route surfaces are checked against complete actual foreign owners.
"""
from time import perf_counter
import math
from shapely import STRtree,to_wkb
from shapely.geometry import Polygon
from shapely.ops import unary_union
from src.component_distance import distance
from src.original_copper_owners import OriginalOwners
from src import source_channel_scope as sc,component_clearance as cc
from . import pipeline as p
from .limiting_growth import owner_material
from .limiting_math import GUARD


def verify(store,result,construction):
    start=perf_counter();scope=sc.ACTIVE if sc.ACTIVE is not None else cc.ACTIVE
    if getattr(scope,'frame_ids',()):raise ValueError('T04_TRANSLATED_INTEGRAL_SOURCE_REQUIRED')
    rows,nominal,original=p.operands(store,store.get_json(result['output_scene_ref'],kind='scene'))
    before=construction.before_owners;selected=result['solution']['selected_scales'];failures=[];proofs={};reduced_corridors=[]
    for label,envelope in (('nominal',False),('envelope',True)):
        material=dict(nominal)
        if envelope:
            for r in construction.paths:material[r]=construction.route(r,selected[r],True)
        after=owner_material(scope,material);ids=sorted(after);tree=STRtree([after[o] for o in ids]);deltas={}
        for r in sorted(construction.paths):
            owner=construction.receipt['route_owners'][r];body=material[r]
            data=getattr(construction,'data',{}).get(r,{})
            from .profile_refinement import contains_floor
            if 'baseline_body' in data:
                standalone=construction.receipt.get('standalone_profile',False)
                floor=construction.receipt.get('route_plans',{}).get(r,{}).get('construction_floor_profile',{}).get('factor',1.)
                # A source-calculated corridor is still a proposal. Below its
                # progress rung the native ladder's smaller accepted geometry
                # is authoritative; historical accepted reference floors remain
                # unconditional. No physical/native safety predicate is waived.
                if standalone and selected[r]<floor-1e-12:
                    if not envelope:reduced_corridors.append(dict(route=r,selected_progress=selected[r],proposed_corridor_progress=floor))
                elif not contains_floor(body,data['baseline_body']):failures.append(dict(reason='CONSTRUCTED_CORRIDOR_COPPER_REGRESSED' if standalone else 'REFERENCE_10_PERCENT_COPPER_REGRESSED',scope=label,route=r))
            # Byte-identical untouched contributions are the established KEEP
            # case; never label global overlay roundoff as newly added copper.
            if construction.chosen[r]['pose']==(0.,0.) and body.equals_exact(construction.oldcores[r],0):continue
            delta=body.difference(before[owner])
            if not delta.is_empty:deltas.setdefault(owner,[]).append(delta)
        pairs=[]
        for own,parts in sorted(deltas.items()):
            delta=unary_union(parts)
            for i in sorted(map(int,tree.query(delta.envelope.buffer(GUARD+1e-12)))):
                other=ids[i]
                if other==own:continue
                gap=float(distance(delta,after[other]));passed=gap+1e-12>=GUARD;pairs.append(dict(owner=own,foreign_owner=other,gap_mm=gap,passed=passed))
                if not passed:failures.append(dict(reason='NEW_TRANSLATED_COPPER_BELOW_FOREIGN_OWNER_GAP',scope=label,owner=own,foreign_owner=other,gap_mm=gap))
        proofs[label]=dict(passed=not any(not q['passed'] for q in pairs),pairs=pairs,changed_owner_count=len(deltas),reference='ACTUAL_PRE_MOTION_OWNER_MATERIAL; old trace footprint is not restored',required_gap_mm=GUARD,actual_owner_material_refs={own:p.geomref(store,g) for own,g in after.items()})
    # Verify every original terminal, including those outside the mutable set.
    image=unary_union([nominal[s] for s in sorted(nominal) if not nominal[s].is_empty]);index=OriginalOwners(image);forward={};reverse={};terminals=0
    for sid,row in construction.rows.items():
        if row['kind'] not in ('circle','rectangle'):continue
        if not nominal[sid].equals_exact(construction.input_current[sid],0):failures.append(dict(reason='PROTECTED_TERMINAL_COPPER_CHANGED',source_id=sid))
        point=construction.original[sid].representative_point();old_owners=construction.source_owner_ids[sid];hits=list(map(int,index.tree.query(point,predicate='intersects')))
        if len(old_owners)!=1 or len(hits)!=1:failures.append(dict(reason='TERMINAL_OWNER_UNBOUND_AFTER_TRANSLATION',source_id=sid));continue
        old=old_owners[0];new=index.ids[hits[0]];forward.setdefault(old,set()).add(new);reverse.setdefault(new,set()).add(old);terminals+=1
    splits=sum(len(v)>1 for v in forward.values());merges=sum(len(v)>1 for v in reverse.values())
    if splits or merges:failures.append(dict(reason='TERMINAL_PARTITION_CHANGED_BY_TRANSLATION',splits=splits,merges=merges))
    source_refs={o:p.geomref(store,g) for o,g in before.items()}
    proof=dict(source_corridor_proposals_reduced_by_native_ladder=reduced_corridors,schema='t04-complete-motion-scene-validation/1',passed=not failures,failures=failures,source_sha256=result['limiting_construction']['source_sha256'],nominal=proofs['nominal'],envelope=proofs['envelope'],pre_motion_owner_refs=source_refs,source_owner_ids={sid:list(ids) for sid,ids in construction.source_owner_ids.items()},terminal_points_checked=terminals,terminal_owner_splits=splits,terminal_owner_merges=merges,physical_components_after=len(index.owners),serialized_material_sha256=p.digest(to_wkb(image)),wall_s=perf_counter()-start)
    ref=store.put_json('t04-motion-final-validation',proof)
    if not proof['passed']:raise ValueError('T04_TRANSLATED_FULL_SCENE_REJECTED:'+p.canonical(ref).decode())
    return dict(proof,report_ref=ref)
