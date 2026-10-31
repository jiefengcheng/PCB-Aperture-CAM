from src.stage_abi.composition import execute_sequence
from src.stage_abi.store import ArtifactStore
from src.stage_abi.width import WidthAdapter,width_parameters
from tests.test_stage_abi_routes import case

def route_sequence(e):
 store=e['store'];plan=store.get_json(e['plan'],kind='plan');selection=store.get_json(plan['selection_ref'],kind='selection');template=store.put_json('selection-template',{k:v for k,v in selection.items() if k not in ('stage','scene_ref')});step=dict(stage='t03',profile_id='profile',selection_template_ref=template,proof_scope_ref=store.put_json('proof-scope',dict(scope='complete-source-parallel-route-and-attachments')));steps=[step,step];scene=store.get_json(e['scene'],kind='scene');grant=store.put_json('composition-grant',dict(authority='Test-host exact sequence',initial_scene_ref=e['scene'],source_sha256=scene['source_sha256'],steps=steps,output_scope_ref=e['scope'],max_steps=2));e['doc']['composition_refs']=[grant];return dict(initial_scene_ref=e['scene'],qualification_ref=plan['qualification_ref'],steps=steps,grant_ref=grant,idempotency_prefix='bounded-sequence')

def test_failed_stage_verification_stops_before_any_dependent_work(tmp_path):
 e=case(tmp_path,bundle=False,fixed_blocker=True);args=route_sequence(e);result=execute_sequence(e['service'],**args)
 assert result['status']=='FAIL_STAGE_VERIFICATION' and result['completed_steps']==[]
 assert [r['request']['operation'] for r in result['transcript']]==['t03_inspect','t03_plan','t03_search','t03_verify']
 assert result['last_qualified_scene_ref']==e['scene'] and result['owner_acceptance']=='NOT_GRANTED'

def test_unregistered_or_changed_composition_grant_cannot_expand_scope(tmp_path):
 import pytest
 from src.stage_abi.contracts import StageABIError
 e=case(tmp_path);args=route_sequence(e);e['doc']['composition_refs']=[]
 with pytest.raises(StageABIError) as error:execute_sequence(e['service'],**args)
 assert error.value.code=='COMPOSITION_GRANT_NOT_REGISTERED'
 e['doc']['composition_refs']=[args['grant_ref']];args['steps']=args['steps'][:1]
 with pytest.raises(StageABIError) as error:execute_sequence(e['service'],**args)
 assert error.value.code=='COMPOSITION_SCOPE_MISMATCH'


def test_actual_adaptive_bundle_search_hands_new_native_routes_to_width(tmp_path):
 e=case(tmp_path);assert 'plan_error' not in e,e;store=e['store'];service=e['service'];doc=e['doc'];route_plan=store.get_json(e['plan'],kind='plan');route_selection=store.get_json(route_plan['selection_ref'],kind='selection');route_template=store.put_json('selection-template',{k:v for k,v in route_selection.items() if k not in ('stage','scene_ref')});policy=store.put_json('policy',dict(stage='t04',parameters=width_parameters()));bounds=store.put_json('bounds',dict(max_source_objects=30,max_targets=5,max_evaluations=1000,max_output_bytes=10000000,max_seconds=120));verifier=store.put_json('verifier',dict(family=width_parameters()['family']));doc['profiles']['width']=dict(stage='t04',adapter='width',policy_ref=policy,scene_refs=[e['scene']],bounds_ref=bounds,verifier_ref=verifier);service.adapters['width']=WidthAdapter();width_template=store.put_json('selection-template',dict(source_ids=['low','upper'],groups=[dict(group_id='parallel',members=['low','upper'])]));steps=[dict(stage='t03',profile_id='profile',selection_template_ref=route_template,proof_scope_ref=store.put_json('proof-scope',dict(scope='complete-source-parallel-route-and-attachments'))),dict(stage='t04',profile_id='width',selection_template_ref=width_template,proof_scope_ref=store.put_json('proof-scope',dict(scope='complete-source-nominal-envelope-and-upper-proofs')))];scene=store.get_json(e['scene'],kind='scene');output=store.put_json('output-scope',dict(kind='immutable-local-artifacts'));grant=store.put_json('composition-grant',dict(authority='Test host: bounded T03 to T04 composition',initial_scene_ref=e['scene'],source_sha256=scene['source_sha256'],steps=steps,output_scope_ref=output,max_steps=2));doc['composition_refs']=[grant];qualification=store.put_json('verification',dict(scene_ref=e['scene'],geometric_status='PASS',scope='Test source fixture qualification'))
 result=execute_sequence(service,initial_scene_ref=e['scene'],qualification_ref=qualification,steps=steps,grant_ref=grant,idempotency_prefix='composition');assert result['status']=='PASS_LOCAL_MODULAR_COMPOSITION',result
 t03=store.get_json(result['steps'][0]['candidate_ref'],kind='candidate');t04=store.get_json(result['steps'][1]['candidate_ref'],kind='candidate');assert t03['status']=='CONSTRUCTED';assert t04['solution']['passed'];assert set(t04['replacement_refs'])=={'low','upper'};assert t03['output_scene_ref']==t04['scene_ref'];assert all(x['route_change']=='NONE' for x in t04['construction']);assert result['owner_acceptance']=='NOT_GRANTED'
 # Same scope and key must reuse each constructed attempt rather than relaunch.
 repeated=execute_sequence(service,initial_scene_ref=e['scene'],qualification_ref=qualification,steps=steps,grant_ref=grant,idempotency_prefix='composition');assert repeated['output_scene_ref']==result['output_scene_ref']

def test_all_five_suites_compose_through_verified_current_scene(tmp_path):
 from dataclasses import asdict
 from shapely import to_wkb,from_wkb
 from shapely.geometry import Point,box
 from src.stage_abi.store import ArtifactStore
 from src.stage_abi.registry import TrustedRegistry
 from src.stage_abi.service import StageService
 from src.stage_abi.lands import LandAdapter,land_parameters
 from src.stage_abi.routes import RouteAdapter,route_parameters
 from src.stage_abi.spindle import SpindleAdapter
 from src.junction_spindle_stage import CONTRACT
 from tests.test_uniform_trace_width import fixture
 store=ArtifactStore(tmp_path/'runtime');raw,chain,meta,blobs=fixture(['(segment (start 0 0) (end 8 0) (width 0.1) (layer F.Cu) (net 0))']);native=store.put_json('native-route',dict(source_ref=store.put('native-source',raw),chain=chain,manifest_rows=meta,geometry_refs={s:store.put('geometry',b) for s,b in blobs.items()}));route_ref=store.put('geometry',next(iter(blobs.values())));quad=(len(from_wkb(next(iter(blobs.values()))).exterior.coords)-3)//4;reference=[[i,0] for i in range(9)];rows=[dict(source_id='trace',kind='trace',original_ref=route_ref,geometry_ref=route_ref,metadata=dict(nominal_width_mm=.1,native_route_ref=native,route_points_mm=reference,route_quad_segs=quad,land_ids=['pad','rect']))]
 for sid,kind,g,metadata in [('pad','circle',Point(0,0).buffer(.12,quad_segs=128),dict(center_mm=[0,0],original_radius_mm=.12,admissible_diameters_mm=[.24,.30,.36],desired_diameter_mm=.36)),('rect','rectangle',box(7.9,-.12,8.15,.12),{}),('corner','rectangle',box(3.35,-.4,3.65,-.2),{})]:
  ref=store.put('geometry',to_wkb(g));rows.append(dict(source_id=sid,kind=kind,original_ref=ref,geometry_ref=ref,metadata=metadata))
 scene=store.put_json('scene',dict(source_sha256=chain['source_sha256'],frame='synthetic-model-with-native-route-mm',units='mm',layer='F.Cu',viewport_mm=[-.5,-.6,8.5,.8],objects=rows,findings=[],lineage=[],acceptance=dict(owner='PENDING',independent='NOT_RUN')));bundle=store.put_json('parallel-bundle',dict(reference_points_mm=reference,members=[dict(source_id='trace',offset_mm=0.)]));corridor=store.put('geometry',to_wkb(box(-.5,-.5,8.5,.5)));templates={
 't01':dict(source_ids=['pad']),
 't03':dict(source_ids=['trace'],seed_ids=['trace'],obstacle_ids=['corner'],bundle_ref=bundle,corridor_ref=corridor,initial_indices=[3,3],objective='explicit-clearance'),
 't04':dict(source_ids=['trace'],groups=[dict(group_id='singleton',members=['trace'])]),
 't02':dict(source_ids=['rect']),
 't05':dict(source_ids=['trace'])}
 adapters=dict(t01=LandAdapter('t01'),t03=RouteAdapter(),t04=WidthAdapter(),t02=LandAdapter('t02'),t05=SpindleAdapter());parameters=dict(t01=land_parameters('t01'),t02=land_parameters('t02'),t03=route_parameters(),t04=width_parameters(),t05=dict(asdict(CONTRACT),radius_scales=list(CONTRACT.radius_scales)));profiles={};steps=[]
 for stage in ['t01','t03','t04','t02','t05']:
  bounds=dict(max_source_objects=50,max_targets=10,max_evaluations=1000,max_output_bytes=10000000,max_seconds=120)
  if stage=='t03':bounds.update(max_displacement_um=100,max_members=1,max_extension_um=3000,max_extension_steps=2,max_recursion_depth=2)
  profiles[stage]=dict(stage=stage,adapter=stage,policy_ref=store.put_json('policy',dict(stage=stage,parameters=parameters[stage])),scene_refs=[scene],bounds_ref=store.put_json('bounds',bounds),verifier_ref=store.put_json('verifier',dict(family=adapters[stage].describe()['family'])))
  scope={'t01':'complete-source-land-and-inclusive','t02':'complete-source-land-and-inclusive','t03':'complete-source-parallel-route-and-attachments','t04':'complete-source-nominal-envelope-and-upper-proofs','t05':'complete-source-and-all-patches'}[stage];steps.append(dict(stage=stage,profile_id=stage,selection_template_ref=store.put_json('selection-template',templates[stage]),proof_scope_ref=store.put_json('proof-scope',dict(scope=scope))))
 out=store.put_json('output-scope',dict(kind='immutable-local-artifacts'));grant=store.put_json('composition-grant',dict(authority='Test-host exact five-stage composition',initial_scene_ref=scene,source_sha256=chain['source_sha256'],steps=steps,output_scope_ref=out,max_steps=5));doc=dict(schema='stage-agent-registry/1',profiles=profiles,authorization_refs=[],decision_refs=[],composition_refs=[grant]);service=StageService(store,TrustedRegistry(store,doc),adapters);q=store.put_json('verification',dict(scene_ref=scene,geometric_status='PASS',scope='Synthetic model with source-parsed native route; no whole-board/native-export qualification'))
 result=execute_sequence(service,initial_scene_ref=scene,qualification_ref=q,steps=steps,grant_ref=grant,idempotency_prefix='five-stages');assert result['status']=='PASS_LOCAL_MODULAR_COMPOSITION',result;assert [s['stage'] for s in result['steps']]==['t01','t03','t04','t02','t05']
 for before,after in zip(result['steps'],result['steps'][1:]):assert store.get_json(after['candidate_ref'],kind='candidate')['scene_ref']==before['scene_ref']
