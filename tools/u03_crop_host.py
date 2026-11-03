"""U03 crop host; the original complete-board T01 host remains unchanged."""
from pathlib import Path
from src.stage_abi.store import ArtifactStore,digest
from src.stage_abi import ABI_VERSION
from src.stage_abi.service import runtime_fingerprint
from src.u03_board.crop_t01 import PROFILE,ImageCropAdapter as BoardAdapter,validate_policy,english
from src.u03_board.selection import for_root
from src.t01_crop.paging import store_pages
from tools.t01_operator_host import ROOT,read,fresh,publish,state,check,response

def prepare(session):
    check(session);inp=read(session/'board_inputs.json');roi=read(session/'data_board/verified.json')
    mr=(session/'data_board/source_manifest.json').read_bytes();manifest=read(session/'data_board/source_manifest.json')
    raw=Path(inp['kicad']['path']).read_bytes();store=ArtifactStore(session/'runtime');objects=[]
    for row in manifest['objects']:
        data=(session/'data_board/source_wkb'/f'{row["geometry_sha256"]}.wkb').read_bytes()
        if digest(data)!=row['geometry_sha256']:raise ValueError('ROI_SOURCE_CACHE_CHANGED')
        ref=store.put('geometry',data);objects.append(dict(source_id=row['id'],kind='circle' if row['kind']=='gr_circle' else 'fixed_source',original_ref=ref,geometry_ref=ref,metadata=dict(native_source_kind=row['kind'],nominal_width_mm=row['trace_width_mm'])))
    directive=read(ROOT/'contracts/t01_crop/source_features.json')['sources'].get(digest(raw),{})
    inventory=store_pages(store,objects,binding=dict(source_sha256=digest(raw),manifest_sha256=digest(mr)),kind='t01-source-inventory')
    b=dict(schema='t01-board-binding/1',source_ref=store.put('native-source',raw),manifest_ref=store.put('native-manifest',mr),source_sha256=digest(raw),manifest_sha256=digest(mr),source_objects=len(objects),source_inventory_ref=inventory,viewport_mm=roi['bounds_mm'],scope_ref=store.put('board-binding',(session/'data_board/verified.json').read_bytes()),scope_sha256=digest((session/'data_board/verified.json').read_bytes()),reviewed_pairs=directive.get('reviewed_pairs',[]),recess_source_ids=directive.get('recess_source_ids',[]))
    scene=store.put_json('scene',dict(source_sha256=b['source_sha256'],frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=b['viewport_mm'],objects=objects,findings=[],lineage=[],acceptance=dict(owner='NOT_GRANTED_FOR_NEW_SCENE',independent='NOT_RUN')))
    binding=store.put_json('t01-binding',b);bounds=store.put_json('bounds',dict(max_source_objects=len(objects),max_targets=len(objects),max_evaluations=max(10000,8*len(objects)),max_output_bytes=200000000,max_seconds=3600))
    selection=store.put_json('u03-crop-selection',for_root(session))
    host=dict(schema='u03-image-crop-t01-host/1',crop_selection_ref=selection,compiler_binding_refs=[binding],stage_registry=dict(schema='stage-agent-registry/1',profiles={},authorization_refs=[],decision_refs=[]))
    cap=dict(schema='t01-language-operator-capsule/1',abi_version=ABI_VERSION,profile_id=PROFILE,store_path=str(store.root),binding_ref=binding,scene_ref=scene,bounds_ref=bounds,qualification_ref=store.put_json('verification',dict(scene_ref=scene,geometric_status='PASS',scope='Data-ABI input correspondence and complete board scope only; not electrical or manufacturing')),verifier_ref=store.put_json('verifier',dict(family='t01-priority-companion/1')),english_ref=store.put('english-spec',english().encode()),policy_ref=None,plan_ref=None,authorization_ref=None,output_scope_ref=None,source_objects=len(objects),viewport_mm=b['viewport_mm'])
    return publish(session,0,host,cap)

def register(session,path):
    check(session);cap=state(session);r=response(session,path,'t01_compile');store=ArtifactStore(Path(cap['store_path']));p=r['result']['policy_ref'];policy=store.get_json(p,kind='policy');validate_policy(policy)
    if cap['capsule_revision']!=0 or policy!=r['result']['policy'] or policy['binding_ref']!=cap['binding_ref']:raise ValueError('BOARD_POLICY_BINDING_INVALID')
    host=read(Path(cap['registry_path']));host['stage_registry']['profiles'][PROFILE]=dict(stage='t01',adapter=PROFILE,policy_ref=p,scene_refs=[cap['scene_ref']],bounds_ref=cap['bounds_ref'],verifier_ref=cap['verifier_ref'])
    return publish(session,1,host,dict(cap,policy_ref=p))

def grant(session,path):
    check(session);cap=state(session);r=response(session,path,'t01_plan');store=ArtifactStore(Path(cap['store_path']));pref=r['result']['plan_ref'];plan=store.get_json(pref,kind='plan')
    if (cap['capsule_revision']!=1 or plan!=r['result']['plan'] or any(plan[k]!=cap[k] for k in ('profile_id','scene_ref','policy_ref')) or plan['bounds_ref']!=cap['bounds_ref'] or plan['qualification_ref']!=cap['qualification_ref'] or plan['implementation']!=BoardAdapter().describe()['implementation'] or plan['runtime']!=runtime_fingerprint() or plan['strategy']!='priority_companion_growth'):raise ValueError('BOARD_PLAN_BINDING_INVALID')
    scope=store.put_json('output-scope',dict(kind='immutable-local-artifacts'))
    auth=store.put_json('authorization',dict(profile_id=PROFILE,scene_ref=cap['scene_ref'],policy_ref=cap['policy_ref'],plan_ref=pref,operations=['t01_run','t01_verify'],authority='User-authorized U03 crop T01; complete source context; no owner acceptance',output_scope_ref=scope))
    host=read(Path(cap['registry_path']));host['stage_registry']['authorization_refs'].append(auth)
    evidence=store.get_json(plan['selection_ref'],kind='selection')
    return publish(session,2,host,dict(cap,plan_ref=pref,authorization_ref=auth,output_scope_ref=scope,proof_scope_ref=store.put_json('proof-scope',dict(scope='complete-board-t01-source-reconstruction')),viewport_ref=store.put_json('viewport',dict(frame='native-kicad-mm',bounds_mm=cap['viewport_mm'])),evidence_selection_ref=store.put_json('evidence-selection',dict(source_ids=evidence['source_ids']))))
