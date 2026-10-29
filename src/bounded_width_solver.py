"""Ceiling-first deterministic scalar search on certified nested width families.

Each immediate parallel group (or singleton) has one factor. Groups are optimized
in stable ID order against every current candidate. Final upper-bracket rejection
establishes coordinate-wise model maximality, not a global aggregate objective.
"""
import hashlib
import json
import math
from .uniform_trace_width_v2 import FAMILY
from .source_offset_width import FAMILY as SOURCE_OFFSET_FAMILY


def solve_width_scales(group_ids,evaluate,*,geometry_family,scale_tolerance=1e-6,max_steps=36):
    ids=sorted(group_ids)
    if not ids or len(set(ids))!=len(ids):raise ValueError('INVALID_GROUP_IDENTITIES')
    if geometry_family not in (FAMILY,SOURCE_OFFSET_FAMILY):raise ValueError('NESTED_WIDTH_GEOMETRY_FAMILY_REQUIRED')
    if (not math.isfinite(scale_tolerance) or scale_tolerance<=0
            or type(max_steps) is not int or not 1<=max_steps<=64):raise ValueError('INVALID_FINITE_SEARCH_BOUNDS')
    scales={sid:1. for sid in ids};checks=[];memo={}
    def check(proposal,*,fresh=False):
        key=tuple(proposal[sid] for sid in ids)
        if not fresh and key in memo:return memo[key]
        report=evaluate(dict(proposal))
        if type(report.get('passed')) is not bool:raise ValueError('EXPLICIT_GEOMETRY_VERDICT_REQUIRED')
        raw=json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        record=dict(index=len(checks),scales=dict(proposal),passed=report['passed'],
            report_sha256=hashlib.sha256(raw).hexdigest(),failures=report.get('failures',[]))
        checks.append(record);memo[key]=record
        return record
    baseline=check(scales)
    if not baseline['passed']:
        return dict(status='PREDECESSOR_GROWTH_CHECK_FAILED',passed=False,selected_scales=scales,
                    evaluations=checks,applied='NONE')
    decisions=[]
    for sid in ids:
        cap=dict(scales);cap[sid]=1.5
        ceiling=check(cap)
        if ceiling['passed']:
            scales=cap
            decisions.append(dict(group_id=sid,selected_factor=1.5,upper_rejected_factor=None,
                status='HARD_CEILING_REACHED',safe_check_index=ceiling['index']))
            continue
        lo,hi=1.,1.5;safe=check(scales);rejected=ceiling;steps=0
        while hi-lo>scale_tolerance and steps<max_steps:
            midpoint=(lo+hi)/2;trial=dict(scales);trial[sid]=midpoint
            result=check(trial);steps+=1
            if result['passed']:lo=midpoint;safe=result
            else:hi=midpoint;rejected=result
        scales[sid]=lo
        decisions.append(dict(group_id=sid,selected_factor=lo,upper_rejected_factor=hi,
            factor_bracket_width=hi-lo,search_steps=steps,safe_check_index=safe['index'],
            rejected_check_index=rejected['index'],
            status='MODEL_BOUND_ESTABLISHED' if hi-lo<=scale_tolerance else 'SEARCH_BUDGET_REACHED'))
    final=check(scales,fresh=True)
    proofs=[]
    for d in decisions:
        sid=d['group_id'];upper=d['upper_rejected_factor']
        if upper is None:
            proofs.append(dict(group_id=sid,status='AT_HARD_CEILING',proved=True))
        else:
            trial=dict(scales);trial[sid]=upper;rejected=check(trial,fresh=True)
            proofs.append(dict(group_id=sid,status='FINAL_NEIGHBORS_REJECT_UPPER_BRACKET' if not rejected['passed'] else 'MAXIMUM_NOT_ESTABLISHED',
                proved=not rejected['passed'] and d['factor_bracket_width']<=scale_tolerance,
                upper_factor=upper,rejection_check_index=rejected['index']))
    proved=final['passed'] and all(p['proved'] for p in proofs)
    return dict(schema='bounded-collective-width-solver/1',
        status='PASS_COORDINATEWISE_MODEL_MAXIMUM' if proved else 'SAFE_PROPOSAL_MAXIMUM_NOT_ESTABLISHED' if final['passed'] else 'FAIL_FINAL_SCENE',
        passed=final['passed'],maximum_established=proved,selected_scales=scales,stable_group_order=ids,
        decisions=decisions,maximum_proofs=proofs,evaluations=checks,evaluation_count=len(checks),
        final_check_index=final['index'],scale_tolerance=scale_tolerance,max_steps_per_group=max_steps,
        geometry_family=geometry_family,hard_ceiling=1.5,applied='NONE',
        scope='Model coordinate-wise maximal to declared bracket under fixed routes and group membership; no native/electrical acceptance')
