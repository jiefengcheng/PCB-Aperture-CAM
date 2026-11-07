import copy
from shapely import to_wkb
from shapely.geometry import Point,box,LineString
from src.stage_abi import ABI_VERSION
from src.stage_abi.store import ArtifactStore
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.service import StageService
from src.stage_abi.lands import LandAdapter,land_parameters


def setup(tmp_path,stage,items,targets):
 store=ArtifactStore(tmp_path/'runtime');rows=[]
 for sid,kind,g,metadata in items:
  ref=store.put('geometry',to_wkb(g));rows.append(dict(source_id=sid,kind=kind,geometry_ref=ref,original_ref=ref,metadata=metadata))
 scene=store.put_json('scene',dict(source_sha256='b'*64,frame='native-mm',units='mm',layer='F.Cu',viewport_mm=[-2,-2,4,4],objects=rows,findings=[],lineage=[],acceptance={'owner':'PENDING'}));policy=store.put_json('policy',dict(stage=stage,parameters=land_parameters(stage)));bounds=store.put_json('bounds',dict(max_source_objects=100,max_targets=10,max_evaluations=10000,max_output_bytes=1000000,max_seconds=120));verifier=store.put_json('verifier',dict(family=land_parameters(stage)['family']));registry=dict(schema='stage-agent-registry/1',profiles={'lands':dict(stage=stage,adapter='land',policy_ref=policy,scene_refs=[scene],bounds_ref=bounds,verifier_ref=verifier)},authorization_refs=[],decision_refs=[]);service=StageService(store,TrustedRegistry(store,registry),{'land':LandAdapter(stage)})
 def request(verb,payload,**kw):return dict(abi_version=ABI_VERSION,request_id='r1',operation=stage+'_'+verb,profile_id='lands',scene_ref=scene,policy_ref=policy,plan_ref=kw.get('plan_ref'),authorization_ref=kw.get('authorization_ref'),idempotency_key=kw.get('idempotency_key'),payload=payload)
 inspect=service.dispatch(request('inspect',dict(source_ids=targets,finding_ids=[],page_size=100,cursor=None)));assert inspect['status']=='OK',inspect
 selection=store.put_json('selection',dict(stage=stage,scene_ref=scene,source_ids=targets));qualification=store.put_json('verification',dict(scene_ref=scene,geometric_status='PASS',scope='Synthetic source scene, not external acceptance'));plan=service.dispatch(request('plan',dict(inspection_ref=inspect['result']['inspection_ref'],selection_ref=selection,predecessor_qualification_ref=qualification,bounds_ref=bounds,strategy='round_class_growth' if stage=='t01' else 'whole_rectangle_growth')))
 if plan['status']!='OK':return store,service,request,plan,None,None,verifier
 plan_ref=plan['result']['plan_ref'];scope=store.put_json('output-scope',dict(kind='immutable-local-artifacts'));auth=store.put_json('authorization',dict(profile_id='lands',scene_ref=scene,policy_ref=policy,plan_ref=plan_ref,operations=[stage+'_run',stage+'_verify'],authority='Test-host bound execution',output_scope_ref=scope));registry['authorization_refs'].append(auth)
 return store,service,request,plan_ref,auth,scope,verifier

def execute_and_verify(env):
 store,service,req,plan,auth,scope,verifier=env;r=service.dispatch(req('run',dict(output_scope_ref=scope),plan_ref=plan,authorization_ref=auth,idempotency_key='execute'));assert r['status']=='OK',r
 result=r['result']['result'];proof=store.put_json('proof-scope',dict(scope='complete-source-land-and-inclusive'));v=service.dispatch(req('verify',dict(candidate_ref=result['candidate_ref'],verifier_ref=verifier,proof_scope_ref=proof),plan_ref=plan,authorization_ref=auth,idempotency_key='verify'));assert v['status']=='OK',v;assert v['result']['result']['verification']['geometric_status']=='PASS';return result['candidate'],result['candidate_ref']

def test_t01_real_round_class_construction_and_direct_replay(tmp_path):
 meta=dict(center_mm=[0,0],original_radius_mm=.1,admissible_diameters_mm=[.2,.25,.3],desired_diameter_mm=.3)
 env=setup(tmp_path,'t01',[('circle','circle',Point(0,0).buffer(.1,quad_segs=128),meta),('fixed','rectangle',box(2,2,3,3),{})],['circle']);candidate,_=execute_and_verify(env);d=candidate['decisions'][0];assert d['status']=='GROWN' and d['shape']['diameter_mm']==.3

def test_t02_grows_whole_rectangle_without_moving_fixed_copper(tmp_path):
 env=setup(tmp_path,'t02',[('rect','rectangle',box(0,0,.5,.4),{}),('fixed','circle',Point(2,2).buffer(.2),{})],['rect']);c,_=execute_and_verify(env);assert c['decisions'][0]['shape']['factors']==[1.25,1.25] and c['protected_source_refs'].keys()=={'fixed'}

def test_t02_connected_inclusive_fill_and_scope_identity(tmp_path):
 bridge=LineString([(.2,.5),(1.9,.5)]).buffer(.4,quad_segs=128)
 env=setup(tmp_path,'t02',[('a','rectangle',box(0,0,1,1),{}),('b','rectangle',box(1.1,0,2.1,1),{}),('bridge','trace',bridge,{'nominal_width_mm':.8})],['a','b']);c,_=execute_and_verify(env);assert any(r['status']=='MERGED' for r in c['inclusive_candidates']);assert 'bridge' in c['protected_source_refs']

def test_t02_buried_rectangles_cannot_become_inclusive_fill_members(tmp_path):
 bridge=LineString([(.2,.5),(1.9,.5)]).buffer(.51,quad_segs=128)
 env=setup(tmp_path,'t02',[('a','rectangle',box(0,0,1,1),{}),('b','rectangle',box(1.1,0,2.1,1),{}),('bridge','trace',bridge,{'nominal_width_mm':1.02})],['a','b'])
 candidate,_=execute_and_verify(env)
 assert all(d['status']=='KEEP'and d['keep_reason']=='EXPOSED_PERIMETER_BELOW_LIMIT'for d in candidate['decisions'])
 assert candidate['inclusive_candidates']==[]and 'bridge'in candidate['protected_source_refs']

def test_t02_disconnected_rectangles_never_combine(tmp_path):
 env=setup(tmp_path,'t02',[('a','rectangle',box(0,0,1,1),{}),('b','rectangle',box(1.1,0,2.1,1),{})],['a','b']);c,_=execute_and_verify(env);assert all(r['status']=='REJECTED' for r in c['inclusive_candidates'])

def test_t01_does_not_use_a_fake_circle_class_binding(tmp_path):
 meta=dict(center_mm=[0,0],original_radius_mm=.1,admissible_diameters_mm=[.2,.3],desired_diameter_mm=.3)
 env=setup(tmp_path,'t01',[('not-circle','circle',box(-.1,-.1,.1,.1),meta)],['not-circle']);assert env[3]['error']['code']=='SOURCE_CIRCLE_BINDING_MISMATCH'

def test_t02_saved_factor_above_cap_is_rejected_by_verifier(tmp_path):
 env=setup(tmp_path,'t02',[('rect','rectangle',box(0,0,.5,.4),{}),('fixed','circle',Point(2,2).buffer(.2),{})],['rect']);c,_=execute_and_verify(env);store,service,req,plan,auth,scope,verifier=env;bad=copy.deepcopy(c);bad['decisions'][0]['shape']['factors'][0]=1.3;ref=store.put_json('candidate',bad);proof=store.put_json('proof-scope',dict(scope='complete-source-land-and-inclusive'));r=service.dispatch(req('verify',dict(candidate_ref=ref,verifier_ref=verifier,proof_scope_ref=proof),plan_ref=plan,authorization_ref=auth,idempotency_key='bad'));assert r['error']['code']=='RECTANGLE_SCALE_OUT_OF_SCOPE'

def test_t01_uses_explicit_original_native_circle_tessellation(tmp_path):
 meta=dict(center_mm=[0,0],original_radius_mm=.1,original_quad_segs=20,admissible_diameters_mm=[.2,.25,.3],desired_diameter_mm=.3);env=setup(tmp_path,'t01',[('circle','circle',Point(0,0).buffer(.1,quad_segs=20),meta),('fixed','rectangle',box(2,2,3,3),{})],['circle']);c,_=execute_and_verify(env);assert c['decisions'][0]['status']=='GROWN'

def test_t01_rejects_unqualified_native_circle_tessellation(tmp_path):
 meta=dict(center_mm=[0,0],original_radius_mm=.1,original_quad_segs=True,admissible_diameters_mm=[.2,.3],desired_diameter_mm=.3);env=setup(tmp_path,'t01',[('circle','circle',Point(0,0).buffer(.1,quad_segs=128),meta)],['circle']);assert env[3]['error']['code']=='SOURCE_CIRCLE_TESSELLATION_UNSUPPORTED'

def test_t02_repeated_stage_never_compounds_original_ceiling(tmp_path):
 from shapely.affinity import scale
 env=setup(tmp_path,'t02',[('rect','rectangle',box(0,0,.5,.4),{}),('fixed','circle',Point(2,2).buffer(.2),{})],['rect'])
 store,service,req,_,_,_,_=env
 old=store.get_json(req('inspect',{})['scene_ref'],kind='scene')
 source=box(0,0,.5,.4);old['objects'][0]['geometry_ref']=store.put('geometry',to_wkb(scale(source,1.25,1.25,origin=source.centroid)))
 ref=store.put_json('scene',old);scene=store.get_json(ref,kind='scene');adapter=service.adapters['land'];selection=dict(stage='t02',scene_ref=ref,source_ids=['rect']);bounds=dict(max_source_objects=100,max_targets=10,max_evaluations=10000,max_output_bytes=1000000,max_seconds=120);policy={'stage':'t02','parameters':land_parameters('t02')};details=adapter.plan(store,scene,policy,selection,bounds)
 plan=dict(stage='t02',scene_ref=ref,policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details)
 result=adapter.run(store,scene,policy,plan,lambda _:None)
 assert result['decisions'][0]['status']=='KEEP'
 assert result['decisions'][0]['candidate_ref']==old['objects'][0]['geometry_ref']

def test_t02_rejects_translated_or_already_oversized_predecessor(tmp_path):
 env=setup(tmp_path,'t02',[('rect','rectangle',box(0,0,.5,.4),{})],['rect']);store,service,req,*_=env;scene=store.get_json(req('inspect',{})['scene_ref'],kind='scene');scene['objects'][0]['geometry_ref']=store.put('geometry',to_wkb(box(-.1,-.1,.6,.5)))
 import pytest
 from src.stage_abi.contracts import StageABIError
 with pytest.raises(StageABIError) as error:service.adapters['land'].plan(store,scene,{'stage':'t02','parameters':land_parameters('t02')},dict(stage='t02',scene_ref=req('inspect',{})['scene_ref'],source_ids=['rect']),dict(max_source_objects=100,max_targets=10,max_evaluations=1000,max_output_bytes=1000000,max_seconds=120))
 assert error.value.code=='PREDECESSOR_OUTSIDE_RECTANGLE_CAP'
