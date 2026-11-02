#!/usr/bin/env python3
"""Coordinator-only source/authority preparation and verbatim T01 JSON transport.

Local Code authors requests and audits responses. This host never discovers sites,
allocates growth or constructs copper; all such work stays behind the T01 ABI.
Existing registries, requests, responses and capsule revisions are never replaced.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.stage_abi.store import ArtifactStore, canonical, digest
from src.stage_abi import ABI_VERSION
from src.stage_abi.service import runtime_fingerprint
from src.t01_abi.adapter import InteractionAdapter
from src.t01_abi.contract import validate_policy
from src.crop_circle_sources import verify_assets
from src.trace_first_pipeline import frozen_fingerprint

PROFILE='c01-interaction-v1'
CACHE=ROOT/'out/crop_dynamic_tasks/c03_final_so_far_freeze_20261030_270/frozen/setup/inputs'
HANDOFF=ROOT/'out/crop_dynamic_tasks/t01_revision_handoff_20261031_295'

def read(p):return json.loads(p.read_bytes())
def fresh(p,value):
    if p.exists():raise ValueError('IMMUTABLE_HOST_RECORD_ALREADY_EXISTS:'+str(p))
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def local(p):
    p=p.resolve()
    if not p.is_relative_to(ROOT/'out'):raise ValueError('PROJECT_OUT_SCOPE_REQUIRED')
    return p
def state(session):
    session=local(session);rows=sorted(session.glob('capsule_*.json'))
    if not rows:raise ValueError('HOST_SESSION_NOT_PREPARED')
    return read(rows[-1])
def check(session):
    start=read(session/'START.json')
    for p,h in read(HANDOFF/'CODE_BASELINE_SHA256.json').items():
        if digest((ROOT/p).read_bytes())!=h:raise ValueError('BASELINE_CODE_CHANGED:'+p)
    for p,h in start['T01_delivery_files'].items():
        if digest((ROOT/p).read_bytes())!=h:raise ValueError('T01_DELIVERY_CODE_CHANGED:'+p)
    freezes=[frozen_fingerprint(ROOT,e) for e in read(HANDOFF/'PROTECTED_FREEZES.json')]
    if freezes!=start['protected_freezes'] or runtime_fingerprint()!=start['runtime_fingerprint'] or InteractionAdapter().describe()['implementation']!=start['T01_implementation']:
        raise ValueError('PROTECTED_EVIDENCE_OR_RUNTIME_CHANGED')
    return dict(status='PASS_CUSTODY_ONLY',assets=verify_assets(),protected_freezes=freezes,baseline_files=484,T01_implementation=start['T01_implementation'])
def publish(session,number,host,cap):
    reg=session/f'host_{number:02d}.json';fresh(reg,host)
    cap=dict(cap,registry_path=str(reg),registry_sha256=digest(reg.read_bytes()),capsule_revision=number)
    fresh(session/f'capsule_{number:02d}.json',cap)
    return cap

def prepare(session):
    session=local(session);check(session)
    if (session/'runtime').exists():raise ValueError('FRESH_OPERATOR_RUNTIME_REQUIRED')
    case=read(ROOT/'contracts/t01/c01.binding.json');raw=(CACHE/'ORG_source.kicad_pcb').read_bytes();mr=(CACHE/'source_manifest.json').read_bytes();manifest=json.loads(mr)
    if digest(raw)!=case['source_sha256'] or digest(mr)!=case['manifest_sha256']:raise ValueError('SOURCE_BINDING_CHANGED')
    store=ArtifactStore(session/'runtime');objects=[]
    for row in manifest['objects']:
        blob=(CACHE/'source_wkb'/(row['geometry_sha256']+'.wkb')).read_bytes()
        if digest(blob)!=row['geometry_sha256']:raise ValueError('ORIGINAL_CACHE_CHANGED')
        g=store.put('geometry',blob)
        objects.append(dict(source_id=row['id'],kind='circle' if row['kind']=='gr_circle' else 'fixed_source',original_ref=g,geometry_ref=g,metadata=dict(native_source_kind=row['kind'],nominal_width_mm=row['trace_width_mm'])))
    binding_ref=store.put_json('t01-binding',dict(case,source_ref=store.put('native-source',raw),manifest_ref=store.put('native-manifest',mr)))
    scene_ref=store.put_json('scene',dict(source_sha256=case['source_sha256'],frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=case['viewport_mm'],objects=objects,findings=[],lineage=[],acceptance=dict(owner='NOT_GRANTED_FOR_NEW_SCENE',independent='NOT_RUN')))
    bounds_ref=store.put_json('bounds',dict(max_source_objects=20000,max_targets=100,max_evaluations=10000,max_output_bytes=200000000,max_seconds=3600))
    qualification_ref=store.put_json('verification',dict(scene_ref=scene_ref,geometric_status='PASS',scope='Original source/cache hashes only; not native/electrical/manufacturing qualification'))
    verifier_ref=store.put_json('verifier',dict(family='t01-priority-companion/1'))
    host=dict(schema='t01-interaction-host/1',compiler_binding_refs=[binding_ref],stage_registry=dict(schema='stage-agent-registry/1',profiles={},authorization_refs=[],decision_refs=[]))
    english_ref=store.put('english-spec',(ROOT/'contracts/t01/c01.english.txt').read_bytes())
    cap=dict(schema='t01-language-operator-capsule/1',abi_version=ABI_VERSION,interface_version='t01-interaction-abi/1.1',profile_id=PROFILE,store_path=str(store.root),binding_ref=binding_ref,scene_ref=scene_ref,bounds_ref=bounds_ref,qualification_ref=qualification_ref,verifier_ref=verifier_ref,english_ref=english_ref,english_path=str(ROOT/'contracts/t01/c01.english.txt'),request_schema_path=str(ROOT/'contracts/t01/request.schema.json'),policy_ref=None,plan_ref=None,authorization_ref=None,output_scope_ref=None,source_objects=len(objects),expected_unique_sites=51,expected_alias_occurrences=53,mode='LOCAL_CODE_AUTHORS_JSON_CODEX_TRANSPORTS_UNCHANGED',next_slice='compile-only')
    return publish(session,0,host,cap)

def response(session,path,operation):
    path=local(path)
    if not path.is_relative_to(session):raise ValueError('SESSION_RESPONSE_REQUIRED')
    r=read(path)
    if r.get('status')!='OK' or r.get('operation')!=operation:raise ValueError('SUCCESSFUL_MATCHING_ABI_RESPONSE_REQUIRED')
    return r

def register(session,path):
    session=local(session);check(session);cap=state(session)
    if cap['capsule_revision']!=0:raise ValueError('COMPILE_REGISTRATION_ORDER_INVALID')
    r=response(session,path,'t01_compile');store=ArtifactStore(Path(cap['store_path']));policy_ref=r['result']['policy_ref'];policy=store.get_json(policy_ref,kind='policy');validate_policy(policy)
    if policy!=r['result']['policy'] or policy['binding_ref']!=cap['binding_ref']:raise ValueError('COMPILED_POLICY_BINDING_MISMATCH')
    host=read(Path(cap['registry_path']));host['stage_registry']['profiles'][PROFILE]=dict(stage='t01',adapter=PROFILE,policy_ref=policy_ref,scene_refs=[cap['scene_ref']],bounds_ref=cap['bounds_ref'],verifier_ref=cap['verifier_ref'])
    return publish(session,1,host,dict(cap,policy_ref=policy_ref,next_slice='discover-inspect-plan-after-each-audit'))

def grant(session,path):
    session=local(session);check(session);cap=state(session)
    if cap['capsule_revision']!=1:raise ValueError('PLAN_AUTHORIZATION_ORDER_INVALID')
    r=response(session,path,'t01_plan');store=ArtifactStore(Path(cap['store_path']));pref=r['result']['plan_ref'];plan=store.get_json(pref,kind='plan')
    if plan!=r['result']['plan'] or any(plan[k]!=cap[k] for k in ('profile_id','scene_ref','policy_ref')) or plan['bounds_ref']!=cap['bounds_ref'] or plan['qualification_ref']!=cap['qualification_ref'] or plan['implementation']!=InteractionAdapter().describe()['implementation'] or plan['runtime']!=runtime_fingerprint() or plan['strategy']!='priority_companion_growth':raise ValueError('SOURCE_PLAN_BINDING_MISMATCH')
    scope=store.put_json('output-scope',dict(kind='immutable-local-artifacts'))
    auth=store.put_json('authorization',dict(profile_id=PROFILE,scene_ref=cap['scene_ref'],policy_ref=cap['policy_ref'],plan_ref=pref,operations=['t01_run','t01_verify'],authority='Codex-coordinated user-authorized Local Code C01 slices',output_scope_ref=scope))
    host=read(Path(cap['registry_path']));host['stage_registry']['authorization_refs'].append(auth)
    proof=store.put_json('proof-scope',dict(scope='complete-c01-priority-companion-source-reconstruction'))
    view=store.put_json('viewport',dict(frame='native-kicad-mm',bounds_mm=read(ROOT/'contracts/t01/c01.binding.json')['viewport_mm']))
    selection=store.get_json(plan['selection_ref'],kind='selection')
    evidence=store.put_json('evidence-selection',dict(source_ids=selection['source_ids']))
    return publish(session,2,host,dict(cap,plan_ref=pref,authorization_ref=auth,output_scope_ref=scope,proof_scope_ref=proof,viewport_ref=view,evidence_selection_ref=evidence,next_slice='run-only-after-plan-audit'))

def response_view(path):
    """Bounded client-readable projection, always bound to the raw wire response."""
    path=local(path);r=read(path);result=r.get('result') or {}
    view=dict(raw_response_path=str(path),raw_response_sha256=digest(path.read_bytes()),operation=r.get('operation'),status=r.get('status'),error=r.get('error'))
    if r.get('status')!='OK':return view
    op=r['operation'].removeprefix('t01_')
    if op=='compile':
        p=result['policy'];view.update(policy_ref=result['policy_ref'],family=p['family'],english_sha256=p['english_sha256'],clause_count=len(p['clause_trace']),settings=p['settings'],binding_ref=p['binding_ref'],construction_status=result['construction_status'])
    elif op=='discover':
        d=result['discovery']
        view.update(selection_ref=result['selection_ref'],discovery_ref=result['discovery_ref'],source_ids=d['source_ids'],source_objects=d['source_objects'],unique_sites=d['unique_sites'],occurrences=d['occurrences'],policy_english_sha256=d['policy_english_sha256'],source_sha256=d['source_sha256'])
    elif op=='inspect':view.update(inspection_ref=result['inspection_ref'],total_records=result['total_records'],selected_source_ids=result['selected_source_ids'],next_cursor=result['next_cursor'])
    elif op=='plan':
        p=result['plan'];a=p['details']['allocation']
        view.update(plan_ref=result['plan_ref'],strategy=p['strategy'],implementation=p['implementation'],runtime=p['runtime'],targets=p['details']['targets'],group_count=len(a['groups']),physical_component_count=len({x['physical_contact_group'] for x in a['sites']}),priority_count=len(a['priorities_by_physical_component']),exceptions=a['priority_exceptions'],class_record_count=len(a['size_classes']),construction_status=result['construction_status'])
    elif op in ('run','verify'):
        job=result['job'];view.update(job_status=job['status'],reused=result['reused'])
        executed=result.get('result') or {};view['execution_evidence']=executed.get('execution_evidence')
        if 'candidate_ref' in executed:
            c=executed['candidate'];view.update(candidate_ref=executed['candidate_ref'],output_scene_ref=c['output_scene_ref'],before_ref=c['before_ref'],after_ref=c['after_ref'],counts=c['counts'],source_objects=c['source_objects'],unique_sites=c['unique_sites'],source_occurrences=c['source_occurrences'],final_check_count=len(c['final_checks']),all_final_checks_passed=all(q['check']['passed'] for q in c['final_checks']),neighbor_response_sites=c['neighbor_response_sites'],neighbor_controls=len(c['events']),evolving_companion_response_sites=c['evolving_companion_response_sites'],square_disabled_controls=c['square_disabled_controls'],owner_status=c['owner_status'],independent_status=c['independent_status'],native_electrical_manufacturing=c['native_electrical_manufacturing'])
        elif 'verification_ref' in executed:view.update(verification_ref=executed['verification_ref'],verification=executed['verification'])
        else:view['result']=executed
    elif op=='compare':view.update(comparison_ref=result['comparison_ref'],added_area_mm2=result['added_area_mm2'],removed_area_mm2=result['removed_area_mm2'],source_change_count=len(result['source_changes']),visuals=result['visuals'])
    else:view['result']=result
    return view

def transport(session,request_path,response_path,operation):
    session=local(session);request_path=local(request_path);response_path=local(response_path)
    if not request_path.is_relative_to(session) or not response_path.is_relative_to(session):raise ValueError('SESSION_WIRE_FILES_REQUIRED')
    if response_path.exists():raise ValueError('FRESH_WIRE_RESPONSE_REQUIRED')
    cap=state(session);req=read(request_path)
    if req.get('operation')!=operation or not operation.startswith('t01_'):raise ValueError('COORDINATOR_SLICE_OPERATION_MISMATCH')
    # Do not validate/fix semantic payloads here. Real ABI rejections must be
    # observable by the operator, including incorrect policy/strategy/authority.
    before=digest(request_path.read_bytes())
    argv=[sys.executable,'-B',str(ROOT/'tools/t01_agent_abi.py'),'--registry',cap['registry_path'],'--registry-sha256',cap['registry_sha256'],'--store',cap['store_path'],'--input',str(request_path)]
    p=subprocess.run(argv,cwd=ROOT,capture_output=True)
    if digest(request_path.read_bytes())!=before:raise ValueError('OPERATOR_REQUEST_CHANGED_DURING_TRANSPORT')
    response_path.parent.mkdir(parents=True,exist_ok=True);response_path.write_bytes(p.stdout)
    stderr=response_path.with_suffix('.stderr.log');stderr.write_bytes(p.stderr)
    receipt=response_path.with_suffix('.transport.json')
    fresh(receipt,dict(status='VERBATIM_TRANSPORT_COMPLETED',request_path=str(request_path),request_sha256=before,response_sha256=digest(p.stdout),registry_sha256=cap['registry_sha256'],argv=argv,returncode=p.returncode,operator_request_modified=False,host_code_sha256=digest(Path(__file__).read_bytes())))
    fresh(response_path.with_suffix('.view.json'),response_view(response_path))
    return dict(response_path=str(response_path),transport_receipt=str(receipt),returncode=p.returncode,abi_status=json.loads(p.stdout).get('status'))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','register','grant','transport','check']);p.add_argument('--session',type=Path,required=True);p.add_argument('--response',type=Path);p.add_argument('--request',type=Path);p.add_argument('--operation')
    a=p.parse_args();session=local(a.session)
    if a.action=='prepare':result=prepare(session)
    elif a.action=='register':result=register(session,a.response)
    elif a.action=='grant':result=grant(session,a.response)
    elif a.action=='transport':result=transport(session,a.request,a.response,a.operation)
    else:result=check(session)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
