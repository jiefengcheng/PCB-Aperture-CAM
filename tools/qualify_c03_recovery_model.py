#!/usr/bin/env python3
"""Engineering model execution on a retained source snapshot; no native gates.

This never runs, advances, reseals or substitutes for a managed native job. It
exists to check the new family while native code/evidence custody is blocked.
Only original source/cache/scope records are read from the retained case.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.c03_input_family import retention_proof, specification
from src.c03_round_adapter import NativeRoundAdapter, PROFILE, compile_policy, english, context
from src.stage_abi.scene import validate_scene
from src.stage_abi.store import ArtifactStore, canonical, digest
from src.t01_crop.paging import store_pages
from src.u03_board.selection import for_root,window
from tools.pcb_workspace import configure,WORK


def execute(native,output):
    configure();native=Path(native).absolute();output=Path(output).absolute()
    if not native.is_relative_to(WORK) or not output.is_relative_to(WORK) or output.exists():
        raise ValueError('C03_FRESH_LACIE_MODEL_OUTPUT_REQUIRED')
    output.mkdir(parents=True);store=ArtifactStore(output/'runtime');inputs={}
    code={str(p.relative_to(ROOT)):digest(p.read_bytes()) for folder in ('src','tools','contracts')
          for p in (ROOT/folder).rglob('*') if p.is_file() and (p.suffix=='.py' or folder=='contracts')}
    def body(path,sha=None):
        path=Path(path)
        if path.is_symlink() or not path.is_file():raise ValueError('C03_MODEL_INPUT_UNSAFE')
        blob=path.read_bytes();actual=digest(blob)
        if sha is not None and actual!=sha:raise ValueError('C03_MODEL_INPUT_HASH_CHANGED')
        inputs[str(path)]=actual;return blob
    def read(path):return json.loads(body(path))
    def original_artifact(ref):return body(native/'runtime/artifacts'/ref['artifact_id'],ref['sha256'])
    def save(name,value):
        with (output/name).open('xb') as stream:stream.write(canonical(value))
    started=time.monotonic();spec,_,sha=specification()
    receipt=read(native/'RECEIPT.json')
    old_binding=json.loads(original_artifact(receipt['binding_ref']))
    raw=original_artifact(old_binding['source_ref'])
    manifest_blob=original_artifact(old_binding['manifest_ref']);manifest=json.loads(manifest_blob)
    scope_blob=original_artifact(old_binding['scope_ref']);scope=json.loads(scope_blob)
    if digest(raw)!=spec['source_sha256']:raise ValueError('C03_MODEL_SOURCE_CHANGED')
    objects=[]
    for row in manifest['objects']:
        blob=body(native/'data_board/source_wkb'/(row['geometry_sha256']+'.wkb'),row['geometry_sha256'])
        ref=store.put('geometry',blob)
        objects.append(dict(source_id=row['id'],kind='circle' if row['kind']=='gr_circle' else 'fixed_source',
            original_ref=ref,geometry_ref=ref,metadata=dict(native_source_kind=row['kind'],nominal_width_mm=row['trace_width_mm'])))
    inventory=store_pages(store,objects,binding=dict(source_sha256=digest(raw),manifest_sha256=digest(manifest_blob)),kind='t01-source-inventory')
    binding=dict(schema='t01-board-binding/1',source_ref=store.put('native-source',raw),
        manifest_ref=store.put('native-manifest',manifest_blob),source_sha256=digest(raw),
        manifest_sha256=digest(manifest_blob),source_objects=len(objects),source_inventory_ref=inventory,
        viewport_mm=scope['bounds_mm'],scope_ref=store.put('board-binding',scope_blob),
        scope_sha256=digest(scope_blob),reviewed_pairs=[],recess_source_ids=[])
    binding_ref=store.put_json('t01-binding',binding)
    selection=for_root(native)
    policy=compile_policy(english(),binding_ref,store.put_json('u03-crop-selection',selection))
    scene_ref=store.put_json('scene',dict(source_sha256=digest(raw),frame='native-kicad-mm',units='mm',
        layer='F.Cu',viewport_mm=scope['bounds_mm'],objects=objects,findings=[],lineage=[],
        acceptance=dict(owner='NOT_GRANTED_FOR_NEW_SCENE',independent='NOT_RUN')))
    scene=validate_scene(store,scene_ref);adapter=NativeRoundAdapter()
    policy_ref=store.put_json('policy',policy)
    bounds=dict(max_source_objects=len(objects),max_targets=len(objects),max_evaluations=100000,
                max_output_bytes=200000000,max_seconds=3600)
    print('C03_MODEL_PLAN',flush=True)
    discovery=adapter.discovery(store,scene,policy,bounds)
    selection_set=dict(stage='t01',scene_ref=scene_ref,source_ids=discovery['source_ids'])
    detail=adapter.plan(store,scene,policy,selection_set,bounds)
    plan=dict(stage='t01',scene_ref=scene_ref,policy_ref=policy_ref,profile_id=PROFILE,
              implementation=adapter.describe()['implementation'],details=detail)
    print('C03_MODEL_CONSTRUCT',flush=True)
    candidate=adapter.run(store,scene,policy,plan,lambda value:None)
    save('MODEL_CANDIDATE.json',candidate)
    print('C03_MODEL_INDEPENDENT_RECONSTRUCTION',flush=True)
    check=adapter.verify(store,scene,policy,plan,candidate,
                         dict(scope='complete-board-t01-source-reconstruction'),lambda value:None)
    print('C03_MODEL_CONTACT_RECONSTRUCTION',flush=True)
    _,_,_,_,sites=context(store,scene,policy)
    original={r['source_id']:store.get(r['geometry_ref'],kind='geometry') for r in objects}
    current=dict(original)
    for sid,ref in candidate['replacements'].items():current[sid]=store.get(ref,kind='geometry')
    proof=retention_proof(raw,manifest,original,current,sites,window(selection))
    save('CONTACT_PROOF.json',proof)
    controls=[]
    def rejected(name,expected,operation):
        try:operation()
        except ValueError as error:
            if not str(error).startswith(expected):raise
            controls.append(dict(name=name,expected=expected,error=str(error),status='PASS_EXPECTED_REJECTION'))
        else:raise ValueError('C03_MODEL_CONTROL_DID_NOT_REJECT:'+name)
    missing=dict(current);missing.pop(sites[0]['source_id'])
    rejected('missing_source','C03_COMPLETE_PREDECESSOR_PARTITION_REQUIRED',
             lambda:retention_proof(raw,manifest,original,missing,sites,window(selection)))
    omitted=dict(current)
    grown=next(sid for sid in current if current[sid]!=original[sid]);omitted[grown]=original[grown]
    rejected('omitted_required_round','C03_EXACT_ROUND_INPUT_REQUIRED',
             lambda:retention_proof(raw,manifest,original,omitted,sites,window(selection)))
    wrong_sites=[dict(s) for s in sites];wrong_sites[0]['radius']+=.001
    rejected('altered_native_radius','C03_NATIVE_CONTACT_SITE_PARAMETERS_CHANGED',
             lambda:retention_proof(raw,manifest,original,current,wrong_sites,window(selection)))
    # Exercise the separate closed compiler and negative wording on this actual
    # source binding, without constructing or advancing a managed native route.
    from src.c03_round_service import C03RoundService
    from src.stage_abi import ABI_VERSION
    service=C03RoundService(store,dict(schema='c03-round-recovery-host/1',
        compiler_binding_refs=[binding_ref],crop_selection_ref=policy['u03_selection_ref'],
        stage_registry=dict(schema='stage-agent-registry/1',profiles={},authorization_refs=[],decision_refs=[])))
    request=dict(abi_version=ABI_VERSION,request_id='c03-model-compile',operation='t01_compile',
        profile_id=None,scene_ref=None,policy_ref=None,plan_ref=None,authorization_ref=None,
        idempotency_key=None,payload=dict(english=english(),binding_ref=binding_ref))
    response=service.dispatch(request)
    if response['status']!='OK' or response['result']['policy']!=policy:
        raise ValueError('C03_MODEL_CLOSED_COMPILER_MISMATCH:'+str(response))
    request['payload']['english']=english().replace('hard gap 0.020 mm','hard gap 0.001 mm')
    negative=service.dispatch(request)
    if negative['status']!='REJECTED' or negative['error']['code']!='T01_ENGLISH_UNSUPPORTED':
        raise ValueError('C03_MODEL_NEGATIVE_COMPILER_DID_NOT_REJECT')
    controls.append(dict(name='altered_clearance_english',expected='T01_ENGLISH_UNSUPPORTED',
                         error=negative['error'],status='PASS_EXPECTED_REJECTION'))
    save('MODEL_CONTROLS.json',controls)
    for path,expected in inputs.items():
        if digest(Path(path).read_bytes())!=expected:raise ValueError('C03_MODEL_INPUT_MUTATED')
    for name,expected in code.items():
        if digest((ROOT/name).read_bytes())!=expected:raise ValueError('C03_MODEL_PRODUCER_CHANGED:'+name)
    report=dict(schema='c03-recovery-engineering-model/1',status='PASS_MODEL_ONLY',
        native_qualification='NOT_RUN: CODE_AND_EVIDENCE_CUSTODY_BLOCKED',
        source_scope='RETAINED_ORIGINAL_SOURCE_SNAPSHOT; not a fresh native source qualification',
        managed_pipeline_advancement=False,contract_sha256=sha,source_sha256=digest(raw),
        crop_sha256=selection['crop_sha256'],reconstruction=check,counts=candidate['counts'],
        original_obligations=candidate['original_coverage'],
        trace_occurrences=len(proof['trace_records']),
        retained_generic_failure_pairs=len(proof['retained_generic_source_port_failures']),
        deliberate_controls=controls,
        input_files=inputs,producer_files=code,elapsed_seconds=time.monotonic()-started,
        owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',
        electrical_manufacturing='NOT_ESTABLISHED')
    save('MODEL_REPORT.json',report)
    print(json.dumps(dict(status=report['status'],output=str(output),elapsed_seconds=report['elapsed_seconds'])),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();execute(args.native,args.output)
