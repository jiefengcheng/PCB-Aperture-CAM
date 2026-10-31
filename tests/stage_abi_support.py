"""Synthetic source fixtures with real module execution, not fake check adapters."""
from src.stage_abi import ABI_VERSION
from src.stage_abi.store import ArtifactStore
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.service import StageService


def host(store,stage,adapter,rows,parameters,selection,*,source_sha256,viewport=None,bounds=None):
 scene=store.put_json('scene',dict(source_sha256=source_sha256,frame='native-mm',units='mm',layer='F.Cu',viewport_mm=viewport or [-2,-2,4,4],objects=rows,findings=[],lineage=[],acceptance=dict(owner='PENDING',independent='NOT_RUN')));policy=store.put_json('policy',dict(stage=stage,parameters=parameters));bounds_ref=store.put_json('bounds',bounds or dict(max_source_objects=100,max_targets=10,max_evaluations=1000,max_output_bytes=10000000,max_seconds=120));verifier=store.put_json('verifier',dict(family=adapter.describe()['family']));doc=dict(schema='stage-agent-registry/1',profiles={'profile':dict(stage=stage,adapter='test-adapter',policy_ref=policy,scene_refs=[scene],bounds_ref=bounds_ref,verifier_ref=verifier)},authorization_refs=[],decision_refs=[]);service=StageService(store,TrustedRegistry(store,doc),{'test-adapter':adapter})
 def req(verb,payload,**kw):return dict(abi_version=ABI_VERSION,request_id='r1',operation=stage+'_'+verb,profile_id='profile',scene_ref=scene,policy_ref=policy,plan_ref=kw.get('plan_ref'),authorization_ref=kw.get('authorization_ref'),idempotency_key=kw.get('idempotency_key'),payload=payload)
 inspection=service.dispatch(req('inspect',dict(source_ids=selection['source_ids'],finding_ids=[],page_size=100,cursor=None)));assert inspection['status']=='OK',inspection
 selected=store.put_json('selection',dict(selection,stage=stage,scene_ref=scene));q=store.put_json('verification',dict(scene_ref=scene,geometric_status='PASS',scope='Synthetic source fixture valid input; not independent engineering acceptance'));strategy=dict(t01='round_class_growth',t02='whole_rectangle_growth',t03='obstacle_directed_single_or_bundle',t04='collective_uniform_width',t05='bounded_additive_spindle')[stage];p=service.dispatch(req('plan',dict(inspection_ref=inspection['result']['inspection_ref'],selection_ref=selected,predecessor_qualification_ref=q,bounds_ref=bounds_ref,strategy=strategy)))
 if p['status']!='OK':return dict(store=store,service=service,req=req,plan_error=p)
 plan=p['result']['plan_ref'];output=store.put_json('output-scope',dict(kind='immutable-local-artifacts'));authority=store.put_json('authorization',dict(profile_id='profile',scene_ref=scene,policy_ref=policy,plan_ref=plan,operations=[stage+('_search' if stage=='t03' else '_run'),stage+'_verify'],authority='Test-host scoped execution',output_scope_ref=output));doc['authorization_refs'].append(authority)
 return dict(store=store,service=service,req=req,plan=plan,auth=authority,scope=output,verifier=verifier,doc=doc,scene=scene)

def run_verify(e,proof):
 verb='search' if e['req']('inspect',{})['operation'].startswith('t03') else 'run';r=e['service'].dispatch(e['req'](verb,dict(output_scope_ref=e['scope']),plan_ref=e['plan'],authorization_ref=e['auth'],idempotency_key='construct'));assert r['status']=='OK',r
 result=r['result']['result'];proof_ref=e['store'].put_json('proof-scope',proof);v=e['service'].dispatch(e['req']('verify',dict(candidate_ref=result['candidate_ref'],verifier_ref=e['verifier'],proof_scope_ref=proof_ref),plan_ref=e['plan'],authorization_ref=e['auth'],idempotency_key='verify'));assert v['status']=='OK',v;assert v['result']['result']['verification']['geometric_status']=='PASS',v
 return result,v['result']['result']
