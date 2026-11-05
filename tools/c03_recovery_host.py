"""Trusted host for explicit C03 jobs; standard source/data preparation reused."""
from pathlib import Path

from src.c03_input_family import selected
from src.c03_round_adapter import PROFILE, STRATEGY, NativeRoundAdapter, english, validate_policy
from src.stage_abi import ABI_VERSION
from src.stage_abi.service import runtime_fingerprint
from src.stage_abi.store import ArtifactStore, digest
from src.t01_crop.paging import store_pages
from src.u03_board.selection import for_root
from tools.t01_operator_host import ROOT, read, check, publish, state, response


def prepare(session):
    raise ValueError('T01_C03_SUBSTITUTE_RETIRED: no new case-specific T01 job')
    check(session)
    if not selected(session):
        raise ValueError('C03_EXPLICIT_JOB_SELECTION_REQUIRED')
    inputs = read(session/'board_inputs.json')
    scope = read(session/'data_board/verified.json')
    manifest_blob = (session/'data_board/source_manifest.json').read_bytes()
    manifest = read(session/'data_board/source_manifest.json')
    raw = Path(inputs['kicad']['path']).read_bytes()
    store = ArtifactStore(session/'runtime')
    objects = []
    for row in manifest['objects']:
        data = (session/'data_board/source_wkb'/(row['geometry_sha256']+'.wkb')).read_bytes()
        if digest(data) != row['geometry_sha256']:
            raise ValueError('C03_NATIVE_SOURCE_CACHE_CHANGED')
        ref = store.put('geometry',data)
        objects.append(dict(source_id=row['id'],kind='circle' if row['kind']=='gr_circle' else 'fixed_source',
            original_ref=ref,geometry_ref=ref,metadata=dict(native_source_kind=row['kind'],
            nominal_width_mm=row['trace_width_mm'])))
    inventory = store_pages(store,objects,binding=dict(source_sha256=digest(raw),
        manifest_sha256=digest(manifest_blob)),kind='t01-source-inventory')
    binding = dict(schema='t01-board-binding/1',source_ref=store.put('native-source',raw),
        manifest_ref=store.put('native-manifest',manifest_blob),source_sha256=digest(raw),
        manifest_sha256=digest(manifest_blob),source_objects=len(objects),source_inventory_ref=inventory,
        viewport_mm=scope['bounds_mm'],scope_ref=store.put('board-binding',(session/'data_board/verified.json').read_bytes()),
        scope_sha256=digest((session/'data_board/verified.json').read_bytes()),reviewed_pairs=[],recess_source_ids=[])
    scene = store.put_json('scene',dict(source_sha256=binding['source_sha256'],frame='native-kicad-mm',
        units='mm',layer='F.Cu',viewport_mm=binding['viewport_mm'],objects=objects,findings=[],lineage=[],
        acceptance=dict(owner='NOT_GRANTED_FOR_NEW_SCENE',independent='NOT_RUN')))
    bref = store.put_json('t01-binding',binding)
    bounds = store.put_json('bounds',dict(max_source_objects=len(objects),max_targets=len(objects),
        max_evaluations=max(10000,8*len(objects)),max_output_bytes=200000000,max_seconds=3600))
    host = dict(schema='c03-round-recovery-host/1',crop_selection_ref=store.put_json('u03-crop-selection',for_root(session)),
        compiler_binding_refs=[bref],stage_registry=dict(schema='stage-agent-registry/1',profiles={},
        authorization_refs=[],decision_refs=[]))
    capsule = dict(schema='t01-language-operator-capsule/1',abi_version=ABI_VERSION,profile_id=PROFILE,
        store_path=str(store.root),binding_ref=bref,scene_ref=scene,bounds_ref=bounds,
        qualification_ref=store.put_json('verification',dict(scene_ref=scene,geometric_status='PASS',
            scope='Actual data-ABI source/layer/scope qualification; no treatment or owner approval')),
        verifier_ref=store.put_json('verifier',dict(family=NativeRoundAdapter().describe()['family'])),
        english_ref=store.put('english-spec',english().encode()),policy_ref=None,plan_ref=None,
        authorization_ref=None,output_scope_ref=None,source_objects=len(objects),viewport_mm=binding['viewport_mm'])
    return publish(session,0,host,capsule)


def register(session,path):
    check(session); capsule=state(session)
    result=response(session,path,'t01_compile')['result']
    store=ArtifactStore(Path(capsule['store_path']))
    policy=store.get_json(result['policy_ref'],kind='policy'); validate_policy(policy)
    if capsule['capsule_revision']!=0 or policy!=result['policy'] or policy['binding_ref']!=capsule['binding_ref']:
        raise ValueError('C03_POLICY_BINDING_INVALID')
    host=read(Path(capsule['registry_path']))
    host['stage_registry']['profiles'][PROFILE]=dict(stage='t01',adapter=PROFILE,policy_ref=result['policy_ref'],
        scene_refs=[capsule['scene_ref']],bounds_ref=capsule['bounds_ref'],verifier_ref=capsule['verifier_ref'])
    return publish(session,1,host,dict(capsule,policy_ref=result['policy_ref']))


def grant(session,path):
    check(session); capsule=state(session)
    result=response(session,path,'t01_plan')['result']; store=ArtifactStore(Path(capsule['store_path']))
    plan=store.get_json(result['plan_ref'],kind='plan')
    if (capsule['capsule_revision']!=1 or plan!=result['plan'] or
            any(plan[k]!=capsule[k] for k in ('profile_id','scene_ref','policy_ref')) or
            plan['bounds_ref']!=capsule['bounds_ref'] or plan['qualification_ref']!=capsule['qualification_ref'] or
            plan['implementation']!=NativeRoundAdapter().describe()['implementation'] or
            plan['runtime']!=runtime_fingerprint() or plan['strategy']!=STRATEGY):
        raise ValueError('C03_PLAN_BINDING_INVALID')
    output=store.put_json('output-scope',dict(kind='immutable-local-artifacts'))
    authorization=store.put_json('authorization',dict(profile_id=PROFILE,scene_ref=capsule['scene_ref'],
        policy_ref=capsule['policy_ref'],plan_ref=result['plan_ref'],operations=['t01_run','t01_verify'],
        authority='Explicit owner-authorized bounded C03 family; blocked obligations retained; no owner acceptance',
        output_scope_ref=output))
    host=read(Path(capsule['registry_path']));host['stage_registry']['authorization_refs'].append(authorization)
    selection=store.get_json(plan['selection_ref'],kind='selection')
    return publish(session,2,host,dict(capsule,plan_ref=result['plan_ref'],authorization_ref=authorization,
        output_scope_ref=output,proof_scope_ref=store.put_json('proof-scope',dict(scope='complete-board-t01-source-reconstruction')),
        viewport_ref=store.put_json('viewport',dict(frame='native-kicad-mm',bounds_mm=capsule['viewport_mm'])),
        evidence_selection_ref=store.put_json('evidence-selection',dict(source_ids=selection['source_ids']))))
