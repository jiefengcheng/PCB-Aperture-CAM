"""Deterministic nested-width search reusing freshly checked prior brackets.

Prior scales/bounds are hints only. The current scene must independently pass
baseline, seeded vector, every retained expansion and final checks. No original
checker or frozen width solver is changed.
"""
import hashlib,json,math
from .source_offset_width import FAMILY

def solve_resumed_width_scales(group_ids,evaluate,*,geometry_family,initial_scales,
                               prior_upper_factors=None,scale_tolerance=1e-6,max_steps=36):
 ids=sorted(group_ids)
 if not ids or len(ids)!=len(set(ids)) or geometry_family!=FAMILY:raise ValueError('VERIFIED_NESTED_SOURCE_GROUPS_REQUIRED')
 if set(initial_scales)!=set(ids) or any(not math.isfinite(v) or not 1<=v<=1.5 for v in initial_scales.values()):raise ValueError('FINITE_COMPLETE_SEED_SCALES_REQUIRED')
 if not math.isfinite(scale_tolerance) or scale_tolerance<=0 or type(max_steps) is not int or not 1<=max_steps<=64:raise ValueError('FINITE_SEARCH_BOUNDS_REQUIRED')
 upper=prior_upper_factors or {}
 if set(upper)-set(ids) or any(not math.isfinite(v) or not 1<v<=1.5 for v in upper.values()):raise ValueError('FINITE_PRIOR_UPPER_REQUIRED')
 memo={};checks=[]
 def check(values,fresh=False):
  key=tuple(values[s] for s in ids)
  if not fresh and key in memo:return memo[key]
  q=evaluate(dict(values))
  if type(q.get('passed')) is not bool:raise ValueError('EXPLICIT_VERDICT_REQUIRED')
  rec=dict(index=len(checks),scales=dict(values),passed=q['passed'],report_sha256=hashlib.sha256(json.dumps(q,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),failures=q.get('failures',[]));checks.append(rec);memo[key]=rec;return rec
 scales={s:1. for s in ids}
 if not check(scales)['passed']:return dict(status='PREDECESSOR_GROWTH_CHECK_FAILED',passed=False,selected_scales=scales,evaluations=checks,applied='NONE')
 seed=check(initial_scales)
 seed_mode='FULL_SEED_RECHECK_PASSED'
 if seed['passed']:scales=dict(initial_scales)
 else:
  seed_mode='FULL_SEED_REJECTED_INDIVIDUAL_HINTS_RECHECKED'
  for sid in ids:
   trial=dict(scales);trial[sid]=initial_scales[sid]
   if check(trial)['passed']:scales=trial
 decisions=[]
 for sid in ids:
  cap=dict(scales);cap[sid]=1.5;ceiling=check(cap)
  if ceiling['passed']:
   scales=cap;decisions.append(dict(group_id=sid,selected_factor=1.5,upper_rejected_factor=None,status='HARD_CEILING_REACHED'));continue
  lo,hi=scales[sid],1.5;used=False
  hint=upper.get(sid)
  if hint is not None and hint>lo:
   trial=dict(scales);trial[sid]=hint;q=check(trial)
   if q['passed']:lo=hint
   else:hi=hint;used=True
  steps=0
  while hi-lo>scale_tolerance and steps<max_steps:
   mid=(lo+hi)/2;trial=dict(scales);trial[sid]=mid;q=check(trial);steps+=1
   if q['passed']:lo=mid
   else:hi=mid
  scales[sid]=lo;decisions.append(dict(group_id=sid,selected_factor=lo,upper_rejected_factor=hi,factor_bracket_width=hi-lo,search_steps=steps,reused_prior_upper_after_current_scene_rejection=used,status='MODEL_BOUND_ESTABLISHED' if hi-lo<=scale_tolerance else 'SEARCH_BUDGET_REACHED'))
 final=check(scales,True);proofs=[]
 for d in decisions:
  sid=d['group_id'];hi=d['upper_rejected_factor']
  if hi is None:proofs.append(dict(group_id=sid,proved=True,status='AT_HARD_CEILING'));continue
  trial=dict(scales);trial[sid]=hi;q=check(trial,True);proved=not q['passed'] and d['factor_bracket_width']<=scale_tolerance;proofs.append(dict(group_id=sid,proved=proved,upper_factor=hi,status='CURRENT_FINAL_SCENE_REJECTS_UPPER' if proved else 'MAXIMUM_NOT_ESTABLISHED'))
 maximum=final['passed'] and all(p['proved'] for p in proofs)
 return dict(schema='resumed-bounded-source-width-solver/1',status='PASS_COORDINATEWISE_MODEL_MAXIMUM' if maximum else 'SAFE_PROPOSAL_MAXIMUM_NOT_ESTABLISHED' if final['passed'] else 'FAIL_FINAL_SCENE',passed=final['passed'],maximum_established=maximum,selected_scales=scales,stable_group_order=ids,decisions=decisions,maximum_proofs=proofs,evaluations=checks,evaluation_count=len(checks),final_check_index=final['index'],scale_tolerance=scale_tolerance,max_steps_per_group=max_steps,geometry_family=geometry_family,hard_ceiling=1.5,seed_recheck=seed_mode,applied='NONE',scope='Same-scene freshly checked prior hints; coordinatewise model bounds only, no native/independent/global optimum claim')
