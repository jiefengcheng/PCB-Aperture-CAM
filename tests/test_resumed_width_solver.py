import pytest
from src.resumed_width_solver import solve_resumed_width_scales
from src.source_offset_width import FAMILY

def test_reuses_only_freshly_rejected_small_upper_bracket():
 calls=[]
 def evaluate(s):calls.append(s);return dict(passed=s['a']<=1.2,failures=[])
 r=solve_resumed_width_scales(['a'],evaluate,geometry_family=FAMILY,initial_scales={'a':1.1999998},prior_upper_factors={'a':1.2000002})
 assert r['passed'] and r['maximum_established'] and r['selected_scales']['a']==1.1999998
 assert r['decisions'][0]['reused_prior_upper_after_current_scene_rejection']
 assert any(s['a']==1.2000002 for s in calls)

def test_stale_failed_upper_is_not_reused_when_new_context_allows_more():
 r=solve_resumed_width_scales(['a'],lambda s:dict(passed=s['a']<=1.4,failures=[]),geometry_family=FAMILY,initial_scales={'a':1.1999998},prior_upper_factors={'a':1.2000002})
 assert r['passed'] and 1.399999<r['selected_scales']['a']<=1.4

def test_unsafe_seed_is_rechecked_and_not_injected():
 r=solve_resumed_width_scales(['a','b'],lambda s:dict(passed=sum(s.values())<=2.4,failures=[]),geometry_family=FAMILY,initial_scales={'a':1.4,'b':1.4})
 assert r['passed'] and sum(r['selected_scales'].values())<=2.4
 assert r['seed_recheck']=='FULL_SEED_REJECTED_INDIVIDUAL_HINTS_RECHECKED'

def test_invalid_current_baseline_is_not_repaired_by_old_seed():
 r=solve_resumed_width_scales(['a'],lambda s:dict(passed=False),geometry_family=FAMILY,initial_scales={'a':1.2})
 assert not r['passed'] and r['selected_scales']=={'a':1.}

def test_nonfinite_hint_rejected():
 with pytest.raises(ValueError,match='PRIOR_UPPER'):
  solve_resumed_width_scales(['a'],lambda s:dict(passed=True),geometry_family=FAMILY,initial_scales={'a':1.},prior_upper_factors={'a':float('nan')})
