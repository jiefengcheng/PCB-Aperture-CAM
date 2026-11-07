"""Reconstruct a constructed T02 candidate without repeating its sizing search.

Search-attempt records remain construction evidence. Geometry, eligibility,
caps, protected contributions, complete simultaneous predicates and every whole
logical fill are evaluated afresh. This does not claim another optimizer run.
The caller must first bind the checkpoint to its successful construction proof.
"""
import copy
import math

from shapely.affinity import scale
from shapely import to_wkb

from src.stage_abi.runtime import Budget, output_scene
from src.stage_abi.scene import composed
from src.stage_abi.store import canonical, digest
from src.stage_abi.lands import exposure_eligible
from src import t02_shared_gaps


def _predicate_values(proof):
    value=copy.deepcopy(proof)
    # Cache work counts describe the invocation, not the geometric predicate.
    # All protected-slot identities, geometry checks and coverage stay compared.
    if 'pin_separation' in value:
        value['pin_separation'].pop('reevaluated_slots',None)
    return value


def reconstruct(adapter,store,scene,policy,plan,recorded):
    if adapter.stage!='t02':raise ValueError('T02_RECONSTRUCTION_SCOPE_REQUIRED')
    if canonical(plan)!=canonical(recorded['plan']):
        raise ValueError('T02_CONSTRUCTION_PLAN_CHANGED')
    retained=recorded['candidate'];details=plan['details']
    rows,current,original,checker,crop=adapter._context(store,scene,policy,details)
    ids=details['targets'];decisions=copy.deepcopy(retained['decisions'])
    if ids!=[row['source_id'] for row in decisions]:
        raise ValueError('T02_CONSTRUCTION_TARGETS_CHANGED')
    protected={sid:row['geometry_ref']for sid,row in rows.items()if sid not in ids}
    if protected!=retained['protected_source_refs']:
        raise ValueError('T02_CONSTRUCTION_PROTECTED_SOURCE_CHANGED')
    selected={};attempt_count=0
    for row in decisions:
        sid=row['source_id'];factors=row.get('pre_shared_factors')
        if (type(factors)is not list or len(factors)!=2 or
            any(type(f)not in(int,float)or not math.isfinite(f)or not 1<=f<=1.25 for f in factors)):
            raise ValueError('T02_CONSTRUCTION_FACTORS_CHANGED')
        if row['status']not in('GROWN','KEEP','COVERED_SKIP'):
            raise ValueError('T02_CONSTRUCTION_STATUS_CHANGED')
        held=details['containment'][sid]['contained']or not exposure_eligible(details,sid)
        if held and factors!=[1.,1.]:raise ValueError('T02_CONSTRUCTION_KEEP_CHANGED')
        geometry=current[sid]if factors==[1.,1.]else scale(current[sid],*factors,origin=current[sid].centroid)
        attempts=row['attempts'];attempt_count+=len(attempts)
        if (not attempts or attempts[-1]['passed']is not True or attempts[-1]['failures'] or
            attempts[-1]['candidate_sha256']!=digest(to_wkb(geometry))):
            raise ValueError('T02_CONSTRUCTION_FINAL_PROPOSAL_CHANGED')
        row['shape']={}if factors==[1.,1.]else dict(factors=factors)
        selected[sid]=geometry
    budget=Budget(details['bounds'])
    selected,shared=adapter._shared_project(store,details,rows,current,original,selected,decisions,budget)
    if canonical(decisions)!=canonical(retained['decisions']):
        raise ValueError('T02_CONSTRUCTION_DECISIONS_CHANGED')
    final=adapter._check(checker,current,selected,ids)
    if not final['passed']or _predicate_values(final)!=_predicate_values(retained['checks']):
        raise ValueError('T02_FRESH_COMPLETE_SCENE_CHECK_CHANGED')
    # Establish the real merge entry/exit state. ComponentRectangleAdapter's
    # existing verifier subsequently replays every proposal from this entry,
    # including sticky pin rejection history and whole-fill gap vetoes.
    merges,additions=adapter._merges(store,scene,plan,rows,dict(current,**selected),budget)
    evaluations=retained['evaluations']
    if (type(evaluations)is not int or evaluations!=attempt_count+len(merges)or
        evaluations>details['bounds']['max_evaluations']):
        raise ValueError('T02_CONSTRUCTION_EVALUATION_WITNESS_CHANGED')
    replacements={row['source_id']:row['candidate_ref']for row in decisions}
    out_ref,out=output_scene(store,scene,plan,replacements=replacements,additions=additions,
                            shared_gap_state_ref=store.put_json('shared-gap-state',shared))
    t02_shared_gaps.complete(shared,composed(store,out))
    candidate=dict(status='CONSTRUCTED',before_ref=store.put('geometry',to_wkb(composed(store,scene))),
                   after_ref=store.put('geometry',to_wkb(composed(store,out))),output_scene_ref=out_ref,
                   decisions=decisions,inclusive_candidates=merges,checks=retained['checks'],
                   evaluations=evaluations,protected_source_refs=protected,shared_neighbor_gaps=shared)
    if canonical(candidate)!=canonical(retained):
        raise ValueError('T02_FIXED_CANDIDATE_RECONSTRUCTION_CHANGED')
    return candidate
