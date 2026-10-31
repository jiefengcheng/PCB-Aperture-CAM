import copy
import pytest
from src.stage_abi import ABI_VERSION
from src.stage_abi.contracts import validate_request,StageABIError,STAGES
REF={'artifact_id':'scene:'+'a'*64,'sha256':'a'*64}
STRATEGY=dict(t01='round_class_growth',t02='whole_rectangle_growth',t03='obstacle_directed_single_or_bundle',t04='collective_uniform_width',t05='bounded_additive_spindle')
def request(stage,verb):
 r=dict(abi_version=ABI_VERSION,request_id='test-1',operation=stage+'_'+verb,profile_id=None if verb=='describe' else 'profile-1',scene_ref=None,policy_ref=None,plan_ref=None,authorization_ref=None,idempotency_key=None,payload={})
 if verb!='describe':r.update(scene_ref=REF,policy_ref=REF)
 if verb in ('run','search','verify'):r.update(plan_ref=REF,authorization_ref=REF,idempotency_key='key-1')
 r['payload']={
 'describe':dict(requested_contract_version=None),
 'inspect':dict(source_ids=['source/1'],finding_ids=[],page_size=10,cursor=None),
 'plan':dict(inspection_ref=REF,selection_ref=REF,predecessor_qualification_ref=REF,bounds_ref=REF,strategy=STRATEGY[stage]),
 'run':dict(output_scope_ref=REF),'search':dict(output_scope_ref=REF),
 'verify':dict(candidate_ref=REF,verifier_ref=REF,proof_scope_ref=REF),
 'compare':dict(left_ref=REF,right_ref=REF,viewport_ref=REF,evidence_selection_ref=REF),
 'review':dict(candidate_ref=REF,verification_ref=None,decision_filters=dict(types=['owner','independent'],page_size=10,cursor=None))}[verb]
 return copy.deepcopy(r)
CASES=[(s,v) for s in STAGES for v in ['describe','inspect','plan','verify','compare','review','search' if s=='t03' else 'run']]
@pytest.mark.parametrize('stage,verb',CASES)
def test_all_suite_request_shapes(stage,verb):assert validate_request(request(stage,verb))==(stage,verb)
@pytest.mark.parametrize('mutate',[
 lambda r:r.update(extra='x'),lambda r:r.update(abi_version='0.1'),lambda r:r.update(profile_id=None),
 lambda r:r.update(plan_ref=REF),lambda r:r.update(authorization_ref=REF),lambda r:r.update(idempotency_key='not-needed'),
 lambda r:r['payload'].update(page_size=True),lambda r:r['payload'].update(page_size=101),
 lambda r:r['payload'].update(source_ids=[]),lambda r:r['payload'].update(source_ids=[{}]),
 lambda r:r['payload'].update(cursor={'artifact_id':'../x','sha256':'a'*64}),
 lambda r:r['payload'].update(page_size=float('nan')),lambda r:r['payload'].update(extra=None),
])
def test_inspection_invalid_inputs_reject(mutate):
 r=request('t04','inspect');mutate(r)
 with pytest.raises(StageABIError):validate_request(r)
def test_no_t03_run_alias_or_cross_suite_strategy():
 for r in [request('t03','run'),request('t04','plan')]:
  if r['operation']=='t04_plan':r['payload']['strategy']='bounded_additive_spindle'
  with pytest.raises(StageABIError):validate_request(r)
def test_run_and_verification_require_bound_authorization():
 for verb in ['run','verify']:
  r=request('t05',verb);r['authorization_ref']=None
  with pytest.raises(StageABIError):validate_request(r)
