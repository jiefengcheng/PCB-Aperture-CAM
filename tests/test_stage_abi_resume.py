import copy,json,subprocess,time
from pathlib import Path
import pytest
from shapely.geometry import Point,box
from tests.test_stage_abi_lands import setup
from tests.test_stage_abi_routes import case as route_case
from tests.test_stage_abi_width import case as width_case
from tests.test_stage_abi_service import environment
from src.stage_abi.journal import ExecutionJournal,execution_journal,journalled
from src.stage_abi.store import ArtifactStore
from src.stage_abi.contracts import StageABIError
ROOT=Path(__file__).resolve().parents[1]


def prepared(tmp_path,stage):
 if stage in ('t01','t02'):
  items=[('pad','circle',Point(0,0).buffer(.1,quad_segs=128),dict(center_mm=[0,0],original_radius_mm=.1,admissible_diameters_mm=[.2,.25,.3],desired_diameter_mm=.3)),('fixed','rectangle',box(2,2,3,3),{})] if stage=='t01' else [('pad','rectangle',box(0,0,.5,.4),{}),('fixed','circle',Point(2,2).buffer(.2),{})]
  s,service,req,plan,auth,scope,_=setup(tmp_path,stage,items,['pad'])
 elif stage=='t05':
  s,service,doc,req,prepare,_=environment(tmp_path);plan,auth,scope=prepare()
 else:
  e=route_case(tmp_path) if stage=='t03' else width_case(tmp_path);s,service,req,plan,auth,scope=[e[k] for k in ['store','service','req','plan','auth','scope']]
 verb='search' if stage=='t03' else 'run';r=req(verb,dict(output_scope_ref=scope),plan_ref=plan,authorization_ref=auth,idempotency_key='crash-recover')
 return s,service,r

@pytest.mark.parametrize('stage',['t01','t02','t03','t04','t05'])
def test_real_process_death_resumes_owned_prefix_without_resetting_ordinals(tmp_path,stage):
 store,service,request=prepared(tmp_path,stage);marker=tmp_path/'committed-event';cfg=tmp_path/'worker.json';cfg.write_text(json.dumps(dict(registry=service.registry.document,store=str(store.root),request=request,crash_after=1,marker=str(marker))));child=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'tests/stage_abi_crash_worker.py'),str(cfg)],capture_output=True,text=True)
 assert child.returncode==73 and marker.exists(),child.stdout+child.stderr
 resumed=service.dispatch(request);assert resumed['status']=='OK',resumed;result=resumed['result'];assert result['job']['status']=='COMPLETED' and result['job']['resume_count']==1;assert result['result']['execution_evidence']['mode']=='OWN_ATTEMPT_PREFIX_REPLAY' and result['result']['execution_evidence']['replayed_events']>=1
 uninterrupted=service.dispatch(dict(request,idempotency_key='fresh-comparison'));assert uninterrupted['status']=='OK',uninterrupted
 assert uninterrupted['result']['result']['candidate_ref']==result['result']['candidate_ref']
 # A completed retry never relaunches and preserves the original result ref.
 again=service.dispatch(request);assert again['result']['reused'] and again['result']['job']==result['job']

def test_live_owner_cannot_be_reclaimed_and_changed_bindings_conflict(tmp_path):
 s=ArtifactStore(tmp_path/'store');key={'id':'one'};binding={'inputs':'same'};won,job=s.begin(key,binding);assert won;assert s.begin(key,binding)==(False,job)
 with pytest.raises(StageABIError) as e:s.begin(key,{'inputs':'different'})
 assert e.value.code=='IDEMPOTENCY_CONFLICT'

def test_recorded_event_replay_never_calls_the_producer_and_rejects_drift(tmp_path):
 s=ArtifactStore(tmp_path/'store');key={'id':'journal'};binding={'inputs':'same'};_,job=s.begin(key,binding)
 with execution_journal(s,key,binding,job) as j:assert journalled('geometry',{'factor':1.25},lambda:{'passed':True})=={'passed':True};j.assert_consumed()
 with execution_journal(s,key,binding,job) as j:
  assert journalled('geometry',{'factor':1.25},lambda:pytest.fail('completed check executed twice'))=={'passed':True};assert j.replayed==1
 with execution_journal(s,key,binding,job):
  with pytest.raises(StageABIError) as e:journalled('geometry',{'factor':1.5},lambda:{'passed':True})
  assert e.value.code=='JOURNAL_REPLAY_MISMATCH'

def test_recovery_does_not_renew_wall_clock_budget(tmp_path):
 from src.stage_abi.runtime import Budget
 s=ArtifactStore(tmp_path/'store');key={'id':'budget'};binding={'inputs':'same'};_,job=s.begin(key,binding);job=dict(job,created_epoch=time.time()-20)
 with execution_journal(s,key,binding,job):
  b=Budget(dict(max_seconds=1,max_evaluations=100,max_output_bytes=10000))
  with pytest.raises(StageABIError) as e:b.evaluation()
  assert e.value.code=='BUDGET_EXHAUSTED'

@pytest.mark.parametrize('stage',['t01','t02','t03','t04','t05'])
def test_actual_verification_worker_death_resumes_same_proof_job(tmp_path,stage):
 store,service,construct=prepared(tmp_path,stage);created=service.dispatch(construct);assert created['status']=='OK',created;candidate=created['result']['result']['candidate_ref'];profile=service.registry.document['profiles'][construct['profile_id']];scope={'t01':'complete-source-land-and-inclusive','t02':'complete-source-land-and-inclusive','t03':'complete-source-parallel-route-and-attachments','t04':'complete-source-nominal-envelope-and-upper-proofs','t05':'complete-source-and-all-patches'}[stage];verify=dict(construct,operation=stage+'_verify',idempotency_key='verify-recover',payload=dict(candidate_ref=candidate,verifier_ref=profile['verifier_ref'],proof_scope_ref=store.put_json('proof-scope',dict(scope=scope))));marker=tmp_path/'verify-event';cfg=tmp_path/'verify-worker.json';cfg.write_text(json.dumps(dict(registry=service.registry.document,store=str(store.root),request=verify,crash_after=1,marker=str(marker))));child=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'tests/stage_abi_crash_worker.py'),str(cfg)],capture_output=True,text=True);assert child.returncode==73 and marker.exists(),child.stdout+child.stderr
 result=service.dispatch(verify);assert result['status']=='OK',result;value=result['result'];assert value['job']['resume_count']==1 and value['result']['execution_evidence']['replayed_events']>=1 and value['result']['verification']['geometric_status']=='PASS'
 fresh=service.dispatch(dict(verify,idempotency_key='verify-fresh'));assert fresh['status']=='OK' and fresh['result']['result']['verification_ref']==value['result']['verification_ref']
