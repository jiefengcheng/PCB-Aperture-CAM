from dataclasses import asdict
import copy
import pytest
from shapely.geometry import Point,LineString,box
from shapely import to_wkb
from src.stage_abi import ABI_VERSION
from src.stage_abi.store import ArtifactStore
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.service import StageService
from src.stage_abi.spindle import SpindleAdapter
from src.junction_spindle_stage import CONTRACT


def environment(tmp_path, bounds_override=None):
 store=ArtifactStore(tmp_path/'runtime');rows=[]
 for sid,kind,g,metadata in [('trace-1','trace',LineString([(0,0),(1,0)]).buffer(.04,quad_segs=64),{'land_ids':['circle-1'],'nominal_width_mm':.08}),('circle-1','circle',Point(1,0).buffer(.18,quad_segs=64),{}),('fixed','rectangle',box(2,2,2.3,2.3),{})]:
  r=store.put('geometry',to_wkb(g));rows.append(dict(source_id=sid,kind=kind,original_ref=r,geometry_ref=r,metadata=metadata))
 scene=store.put_json('scene',dict(source_sha256='a'*64,frame='native-mm',units='mm',layer='F.Cu',viewport_mm=[-.3,-.5,2.5,2.5],objects=rows,findings=[{'finding_id':'f1','source_ids':['trace-1']}],lineage=[],acceptance={'owner':'PENDING','independent':'NOT_RUN'}))
 policy=store.put_json('policy',dict(stage='t05',parameters=dict(asdict(CONTRACT),radius_scales=list(CONTRACT.radius_scales))));bounds=store.put_json('bounds',dict(dict(max_source_objects=100,max_targets=10,max_evaluations=40,max_output_bytes=1000000,max_seconds=60),**(bounds_override or {})));verifier=store.put_json('verifier',dict(family=CONTRACT.family));doc=dict(schema='stage-agent-registry/1',profiles={'spindle':dict(stage='t05',adapter='spindle',policy_ref=policy,scene_refs=[scene],bounds_ref=bounds,verifier_ref=verifier)},authorization_refs=[],decision_refs=[])
 registry=TrustedRegistry(store,doc);service=StageService(store,registry,{'spindle':SpindleAdapter()})
 def req(verb,payload,**kw):
  return dict(abi_version=ABI_VERSION,request_id='r1',operation='t05_'+verb,profile_id='spindle',scene_ref=None if verb=='describe' else scene,policy_ref=None if verb=='describe' else policy,plan_ref=kw.get('plan_ref'),authorization_ref=kw.get('authorization_ref'),idempotency_key=kw.get('idempotency_key'),payload=payload)
 def make_plan():
  inspect=service.dispatch(req('inspect',dict(source_ids=['trace-1'],finding_ids=[],page_size=100,cursor=None)));assert inspect['status']=='OK',inspect
  selection=store.put_json('selection',dict(stage='t05',scene_ref=scene,source_ids=['trace-1']));qualification=store.put_json('verification',dict(scene_ref=scene,geometric_status='PASS',scope='Test fixture valid source footprints; no independent review'))
  p=service.dispatch(req('plan',dict(inspection_ref=inspect['result']['inspection_ref'],selection_ref=selection,predecessor_qualification_ref=qualification,bounds_ref=bounds,strategy='bounded_additive_spindle')));assert p['status']=='OK',p
  scope=store.put_json('output-scope',dict(kind='immutable-local-artifacts'));authorization=store.put_json('authorization',dict(profile_id='spindle',scene_ref=scene,policy_ref=policy,plan_ref=p['result']['plan_ref'],operations=['t05_run','t05_verify'],authority='Test-host scoped local execution grant',output_scope_ref=scope));doc['authorization_refs'].append(authorization)
  return p['result']['plan_ref'],authorization,scope
 return store,service,doc,req,make_plan,verifier

def test_real_t05_plan_run_verify_compare_and_review(tmp_path):
 s,service,doc,req,prepare,verifier=environment(tmp_path)
 assert service.dispatch(req('describe',dict(requested_contract_version=None)))['status']=='OK'
 plan,auth,scope=prepare();runreq=req('run',dict(output_scope_ref=scope),plan_ref=plan,authorization_ref=auth,idempotency_key='construct-1');run=service.dispatch(runreq);assert run['status']=='OK',run
 result=run['result']['result'];candidate=result['candidate'];assert candidate['coverage']['grown']==1
 again=service.dispatch(dict(runreq,request_id='retry'));assert again['result']['reused'] and again['result']['result']['candidate_ref']==result['candidate_ref']
 proof=s.put_json('proof-scope',dict(scope='complete-source-and-all-patches'));v=service.dispatch(req('verify',dict(candidate_ref=result['candidate_ref'],verifier_ref=verifier,proof_scope_ref=proof),plan_ref=plan,authorization_ref=auth,idempotency_key='verify-1'));assert v['status']=='OK',v;assert v['result']['result']['verification']['geometric_status']=='PASS'
 verification=v['result']['result']['verification_ref'];review=service.dispatch(req('review',dict(candidate_ref=result['candidate_ref'],verification_ref=verification,decision_filters=dict(types=['owner','independent'],page_size=10,cursor=None))));assert review['result']['owner_status']=='PENDING' and review['result']['independent_status']=='NOT_RUN'
 source=doc['profiles']['spindle']['scene_refs'][0];view=s.put_json('viewport',dict(frame='native-mm',bounds_mm=[-.3,-.5,2.5,2.5]));selected=s.put_json('evidence-selection',dict(source_ids=['trace-1']));comparison=service.dispatch(req('compare',dict(left_ref=source,right_ref=source,viewport_ref=view,evidence_selection_ref=selected)));assert comparison['status']=='OK' and comparison['result']['added_area_mm2']==0

def test_unregistered_authority_cannot_execute(tmp_path):
 s,service,doc,req,prepare,_=environment(tmp_path);plan,auth,scope=prepare();doc['authorization_refs'].clear();r=service.dispatch(req('run',dict(output_scope_ref=scope),plan_ref=plan,authorization_ref=auth,idempotency_key='one'));assert r['error']['code']=='AUTHORIZATION_NOT_REGISTERED';assert not list((s.root/'jobs').iterdir())

def test_stale_cursor_and_empty_selection_reject(tmp_path):
 s,service,doc,req,_,_=environment(tmp_path);r=req('inspect',dict(source_ids=['trace-1','circle-1'],finding_ids=[],page_size=1,cursor=None));first=service.dispatch(r);assert first['status']=='OK';cursor=first['result']['next_cursor'];second=copy.deepcopy(r);second['payload']['cursor']=cursor;assert service.dispatch(second)['status']=='OK';second['payload']['source_ids']=['fixed'];assert service.dispatch(second)['error']['code']=='STALE_CURSOR'

def test_forged_patch_fails_real_source_replay_and_terminal_job_preserved(tmp_path):
 s,service,doc,req,prepare,verifier=environment(tmp_path);plan,auth,scope=prepare();run=service.dispatch(req('run',dict(output_scope_ref=scope),plan_ref=plan,authorization_ref=auth,idempotency_key='run'));candidate=copy.deepcopy(run['result']['result']['candidate']);candidate['decisions'][0]['patch_ref']=s.put('geometry',to_wkb(box(0,0,.1,.1)));forged=s.put_json('candidate',candidate);proof=s.put_json('proof-scope',dict(scope='complete-source-and-all-patches'));r=req('verify',dict(candidate_ref=forged,verifier_ref=verifier,proof_scope_ref=proof),plan_ref=plan,authorization_ref=auth,idempotency_key='verify');failed=service.dispatch(r);assert failed['error']['code']=='PATCH_RECONSTRUCTION_MISMATCH';retry=service.dispatch(r);assert retry['result']['reused'] and retry['result']['job']['status']=='FAILED'

def test_compare_renders_exact_same_frame_and_output_scene_verifies(tmp_path):
 from src.stage_abi.scene import validate_scene,composed
 s,service,doc,req,prepare,verifier=environment(tmp_path);plan,auth,scope=prepare();run=service.dispatch(req('run',dict(output_scope_ref=scope),plan_ref=plan,authorization_ref=auth,idempotency_key='r'));candidate=run['result']['result']['candidate'];output=validate_scene(s,candidate['output_scene_ref']);before=validate_scene(s,doc['profiles']['spindle']['scene_refs'][0]);assert len(output['objects'])==len(before['objects'])+1;assert composed(s,before).difference(composed(s,output)).area<=1e-12
 view=s.put_json('viewport',dict(frame='native-mm',bounds_mm=before['viewport_mm']));selection=s.put_json('evidence-selection',dict(source_ids=['trace-1']));r=service.dispatch(req('compare',dict(left_ref=doc['profiles']['spindle']['scene_refs'][0],right_ref=candidate['output_scene_ref'],viewport_ref=view,evidence_selection_ref=selection)));assert r['status']=='OK' and r['result']['added_area_mm2']>0
 for visual in r['result']['visuals'].values():assert b'<svg' in s.get(visual,kind='visual')

def test_wrong_plan_and_verification_scope_fail_without_mutating_source(tmp_path):
 s,service,doc,req,prepare,verifier=environment(tmp_path);plan,auth,scope=prepare();before=s.get(doc['profiles']['spindle']['scene_refs'][0]);wrong=s.get_json(plan,kind='plan');wrong['implementation']='wrong';bad=s.put_json('plan',wrong);r=service.dispatch(req('run',dict(output_scope_ref=scope),plan_ref=bad,authorization_ref=auth,idempotency_key='bad'));assert r['error']['code']=='STALE_PLAN';assert s.get(doc['profiles']['spindle']['scene_refs'][0])==before

def test_spindle_admission_rejects_conflicting_source_alias(tmp_path):
 s,service,doc,req,_,_=environment(tmp_path);scene=s.get_json(req('inspect',{})['scene_ref'],kind='scene');alias=copy.deepcopy(scene['objects'][1]);alias['source_id']='conflicting-alias';alias['geometry_ref']=s.put('geometry',to_wkb(Point(1,0).buffer(.2,quad_segs=64)));scene['objects'].append(alias)
 with pytest.raises(Exception,match='circle-1') as error:SpindleAdapter().plan(s,scene,s.get_json(req('inspect',{})['policy_ref'],kind='policy'),dict(stage='t05',scene_ref=req('inspect',{})['scene_ref'],source_ids=['trace-1']),dict(max_source_objects=100,max_targets=10,max_evaluations=40,max_output_bytes=1000000,max_seconds=60))
 assert error.value.code=='LAND_ALIAS_CONFLICT'

def test_spindle_circle_role_does_not_admit_ring_or_box():
 from src.stage_abi.spindle import filled_circle
 assert filled_circle(Point(0,0).buffer(.2,quad_segs=20))
 assert not filled_circle(Point(0,0).buffer(.2).difference(Point(0,0).buffer(.1)))
 assert not filled_circle(box(-.2,-.2,.2,.2))
