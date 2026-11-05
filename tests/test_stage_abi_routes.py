import copy
from shapely import to_wkb
from shapely.geometry import LineString,box
from src.parallel_route_geometry import parallel_points
from src.stage_abi.store import ArtifactStore
from src.stage_abi.routes import RouteAdapter,route_parameters
from tests.stage_abi_support import host,run_verify


def case(tmp_path,*,bundle=True,extension=True,fixed_blocker=False):
 store=ArtifactStore(tmp_path/'runtime');reference=[[i,0] for i in range(9)];members=[dict(source_id='low',offset_mm=0.)]+([dict(source_id='upper',offset_mm=.15)] if bundle else []);rows=[]
 for member in members:
  p=parallel_points(reference,member['offset_mm']);g=LineString(p).buffer(.05,quad_segs=128);ref=store.put('geometry',to_wkb(g));rows.append(dict(source_id=member['source_id'],kind='trace',geometry_ref=ref,original_ref=ref,metadata=dict(nominal_width_mm=.1,route_points_mm=p)))
 obstacles=[('corner',box(3.35,-.2,3.65,-.055))]
 if fixed_blocker:obstacles.append(('fixed-upper',box(0,.08,8,.5)))
 for sid,g in obstacles:
  ref=store.put('geometry',to_wkb(g));rows.append(dict(source_id=sid,kind='rectangle',geometry_ref=ref,original_ref=ref,metadata={}))
 bundle_ref=store.put_json('parallel-bundle',dict(reference_points_mm=reference,members=members));corridor=store.put('geometry',to_wkb(box(-.5,-.5,8.5,.8)));ids=[m['source_id'] for m in members];selection=dict(source_ids=ids,seed_ids=['low'],obstacle_ids=['corner'],bundle_ref=bundle_ref,corridor_ref=corridor,initial_indices=[3,3],objective='explicit-clearance');bounds=dict(max_source_objects=20,max_targets=5,max_evaluations=100,max_output_bytes=1000000,max_seconds=120,max_displacement_um=40,max_members=len(ids),max_extension_um=3000 if extension else 1,max_extension_steps=2,max_recursion_depth=2)
 return host(store,'t03',RouteAdapter(),rows,route_parameters(),selection,source_sha256='c'*64,viewport=[-.5,-.5,8.5,.8],bounds=bounds)

def test_adaptive_single_trace_extension_with_fixed_width_and_ports(tmp_path):
 e=case(tmp_path,bundle=False);assert 'plan_error' not in e,e;c,v=run_verify(e,dict(scope='complete-source-parallel-route-and-attachments'));candidate=c['candidate'];chosen=candidate['chosen'];assert candidate['status']=='CONSTRUCTED' and chosen['expanded_indices']!=chosen['initial_indices'] and chosen['extension_mm']>0;assert chosen['moving']==['low'];assert v['verification']['check']['reconstructed_routes']==1
 out=e['store'].get_json(candidate['output_scene_ref']);old=e['store'].get_json(e['scene']);a=old['objects'][0]['metadata'];b=out['objects'][0]['metadata'];assert a['nominal_width_mm']==b['nominal_width_mm'] and a['route_points_mm'][0]==b['route_points_mm'][0] and a['route_points_mm'][-1]==b['route_points_mm'][-1]

def test_recursive_parallel_bundle_moves_together_with_analytic_proof(tmp_path):
 e=case(tmp_path);assert 'plan_error' not in e,e;c,v=run_verify(e,dict(scope='complete-source-parallel-route-and-attachments'));chosen=c['candidate']['chosen'];assert chosen['moving']==['low','upper'] and chosen['recursion_depth']==1;proof=v['verification']['check']['parallel_proof'];assert len(proof)==2 and all('Analytic' in p['proof'] for p in proof)

def test_fixed_blocker_stops_candidate_without_width_shrink_or_scope_escape(tmp_path):
 e=case(tmp_path,bundle=False,fixed_blocker=True);r=e['service'].dispatch(e['req']('search',dict(output_scope_ref=e['scope']),plan_ref=e['plan'],authorization_ref=e['auth'],idempotency_key='search'));assert r['status']=='OK',r;c=r['result']['result']['candidate'];assert c['status']=='NO_IMPROVEMENT_FOUND' and c['replacement_refs']=={} and not c['objective_satisfied'];proof=e['store'].put_json('proof-scope',dict(scope='complete-source-parallel-route-and-attachments'));v=e['service'].dispatch(e['req']('verify',dict(candidate_ref=r['result']['result']['candidate_ref'],verifier_ref=e['verifier'],proof_scope_ref=proof),plan_ref=e['plan'],authorization_ref=e['auth'],idempotency_key='verify'));assert v['result']['result']['verification']['geometric_status']=='FAIL'

def test_no_authorized_extension_does_not_jump_cut_ports(tmp_path):
 e=case(tmp_path,bundle=False,extension=False);r=e['service'].dispatch(e['req']('search',dict(output_scope_ref=e['scope']),plan_ref=e['plan'],authorization_ref=e['auth'],idempotency_key='search'));assert r['status']=='OK' and r['result']['result']['candidate']['status']=='NO_IMPROVEMENT_FOUND'

def test_changed_shared_reference_fails_direct_reconstruction(tmp_path):
 e=case(tmp_path);c,_=run_verify(e,dict(scope='complete-source-parallel-route-and-attachments'));bad=copy.deepcopy(c['candidate']);bad['chosen']['reference_points_mm'][3][1]+=.001;ref=e['store'].put_json('candidate',bad);proof=e['store'].put_json('proof-scope',dict(scope='complete-source-parallel-route-and-attachments'));r=e['service'].dispatch(e['req']('verify',dict(candidate_ref=ref,verifier_ref=e['verifier'],proof_scope_ref=proof),plan_ref=e['plan'],authorization_ref=e['auth'],idempotency_key='tampered'));assert r['error']['code']=='PARALLEL_REFERENCE_MISMATCH'
