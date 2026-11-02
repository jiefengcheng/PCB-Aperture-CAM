#!/usr/bin/env python3
"""Reproduce C01 through recorded JSON subprocess calls only.

Host setup imports original immutable inputs and registers authority. No host-side
discovery, allocation, priorities or contour construction is permitted here.
Frozen candidate files are opened only after run/verify, as comparison oracles.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.stage_abi import ABI_VERSION
from src.stage_abi.store import ArtifactStore, canonical, digest
from src.crop_circle_sources import verify_assets
from src.trace_first_pipeline import frozen_fingerprint, verify_files

CASE=ROOT/'contracts/t01/c01.binding.json'
CACHE=ROOT/'out/crop_dynamic_tasks/c03_final_so_far_freeze_20261030_270/frozen/setup/inputs'
HIST=ROOT/'out/crop_dynamic_tasks/c01_existing_t01_freeze_20261029_239'
HANDOFF=ROOT/'out/crop_dynamic_tasks/t01_revision_handoff_20261031_295'

def read(p):return json.loads(p.read_bytes())
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(canonical(x))
def sha(p):return digest(p.read_bytes())

def main(out):
    out=out.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'out'):raise ValueError('FRESH_PROJECT_LOCAL_OUTPUT_REQUIRED')
    assets=verify_assets();freezes=read(HANDOFF/'PROTECTED_FREEZES.json')
    protected_before=[frozen_fingerprint(ROOT,r) for r in freezes]
    baseline=read(HANDOFF/'CODE_BASELINE_SHA256.json')
    preserved_before={p:sha(ROOT/p) for p in baseline}
    if preserved_before!=baseline:raise ValueError('BASELINE_IMPLEMENTATION_CHANGED')
    out.mkdir(parents=True)
    write(out/'START.json',dict(branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),assets=assets,protected=protected_before,code_baseline=preserved_before))
    store=ArtifactStore(out/'runtime');case=read(CASE)
    source=(CACHE/'ORG_source.kicad_pcb').read_bytes();manifest_raw=(CACHE/'source_manifest.json').read_bytes();manifest=json.loads(manifest_raw)
    if digest(source)!=case['source_sha256'] or digest(manifest_raw)!=case['manifest_sha256']:raise ValueError('C01_SOURCE_OR_CACHE_CHANGED')
    objects=[]
    for row in manifest['objects']:
        blob=(CACHE/'source_wkb'/(row['geometry_sha256']+'.wkb')).read_bytes()
        if digest(blob)!=row['geometry_sha256']:raise ValueError('SOURCE_GEOMETRY_CHANGED')
        ref=store.put('geometry',blob)
        objects.append(dict(source_id=row['id'],kind='circle' if row['kind']=='gr_circle' else 'fixed_source',original_ref=ref,geometry_ref=ref,
                            metadata=dict(native_source_kind=row['kind'],nominal_width_mm=row['trace_width_mm'])))
    source_ref=store.put('native-source',source);manifest_ref=store.put('native-manifest',manifest_raw)
    binding=dict(case,source_ref=source_ref,manifest_ref=manifest_ref)
    binding_ref=store.put_json('t01-binding',binding)
    scene=dict(source_sha256=case['source_sha256'],frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=case['viewport_mm'],objects=objects,findings=[],lineage=[],acceptance=dict(owner='NOT_GRANTED_FOR_NEW_SCENE',independent='NOT_RUN'))
    scene_ref=store.put_json('scene',scene)
    bounds_ref=store.put_json('bounds',dict(max_source_objects=20000,max_targets=100,max_evaluations=10000,max_output_bytes=200000000,max_seconds=3600))
    host=dict(schema='t01-interaction-host/1',compiler_binding_refs=[binding_ref],stage_registry=dict(schema='stage-agent-registry/1',profiles={},authorization_refs=[],decision_refs=[]))
    profile='c01-interaction-v1';calls=[]
    def request(verb,payload,*,plan_ref=None,authorization_ref=None,key=None):
        empty=verb in ('compile','describe')
        return dict(abi_version=ABI_VERSION,request_id=f'c01-{len(calls)+1:03d}',operation='t01_'+verb,
                    profile_id=None if verb=='compile' else profile,scene_ref=None if empty else scene_ref,policy_ref=None if empty else policy_ref,
                    plan_ref=plan_ref,authorization_ref=authorization_ref,idempotency_key=key,payload=payload)
    def call(req,*,expected='OK'):
        ordinal=len(calls)+1;prefix=f'{ordinal:03d}_{req["operation"]}'
        reg=out/'wire'/(prefix+'_registry.json');inp=out/'wire'/(prefix+'_request.json');resp=out/'wire'/(prefix+'_response.json')
        write(reg,host);write(inp,req)
        argv=[sys.executable,'-B',str(ROOT/'tools/t01_agent_abi.py'),'--registry',str(reg),'--registry-sha256',sha(reg),'--store',str(store.root),'--input',str(inp)]
        print(f'{prefix}: running',flush=True)
        p=subprocess.run(argv,cwd=ROOT,capture_output=True)
        resp.write_bytes(p.stdout);(out/'wire'/(prefix+'_stderr.log')).write_bytes(p.stderr)
        calls.append(dict(operation=req['operation'],argv=argv,registry_sha256=sha(reg),request_sha256=sha(inp),response_sha256=sha(resp),returncode=p.returncode))
        write(out/'TRANSCRIPT.json',calls)
        r=json.loads(p.stdout)
        if r['status']!=expected:raise ValueError(f'{prefix}: expected {expected}: '+str(r.get('error')))
        print(f'{prefix}: {r["status"]}',flush=True)
        return r
    english=(ROOT/'contracts/t01/c01.english.txt').read_text()
    compiled=call(request('compile',dict(english=english,binding_ref=binding_ref)))['result']
    policy_ref=compiled['policy_ref'];policy=compiled['policy']
    verifier=store.put_json('verifier',dict(family='t01-priority-companion/1'))
    host['stage_registry']['profiles'][profile]=dict(stage='t01',adapter=profile,policy_ref=policy_ref,scene_refs=[scene_ref],bounds_ref=bounds_ref,verifier_ref=verifier)
    call(request('describe',dict(requested_contract_version=ABI_VERSION)))
    discovery=call(request('discover',dict(bounds_ref=bounds_ref)))['result']
    targets=discovery['discovery']['source_ids']
    inspected=call(request('inspect',dict(source_ids=targets,finding_ids=[],page_size=100,cursor=None)))['result']
    qualification=store.put_json('verification',dict(scene_ref=scene_ref,geometric_status='PASS',scope='Hash-bound original source/cache input; no native re-export or electrical acceptance'))
    planned=call(request('plan',dict(inspection_ref=inspected['inspection_ref'],selection_ref=discovery['selection_ref'],predecessor_qualification_ref=qualification,bounds_ref=bounds_ref,strategy='priority_companion_growth')))['result']
    plan_ref=planned['plan_ref'];scope=store.put_json('output-scope',dict(kind='immutable-local-artifacts'))
    auth=store.put_json('authorization',dict(profile_id=profile,scene_ref=scene_ref,policy_ref=policy_ref,plan_ref=plan_ref,operations=['t01_run','t01_verify'],authority='User-authorized dedicated T01 branch/C01 reproduction',output_scope_ref=scope))
    host['stage_registry']['authorization_refs'].append(auth)
    run_request=request('run',dict(output_scope_ref=scope),plan_ref=plan_ref,authorization_ref=auth,key='c01-construction')
    executed=call(run_request)['result']['result'];candidate=executed['candidate']
    proof=store.put_json('proof-scope',dict(scope='complete-c01-priority-companion-source-reconstruction'))
    verified=call(request('verify',dict(candidate_ref=executed['candidate_ref'],verifier_ref=verifier,proof_scope_ref=proof),plan_ref=plan_ref,authorization_ref=auth,key='c01-verification'))['result']['result']
    if verified['verification']['geometric_status']!='PASS':raise ValueError('REPRODUCTION_NOT_VERIFIED')
    duplicate=call(run_request)['result']
    if not duplicate['reused'] or duplicate['result']['candidate_ref']!=executed['candidate_ref']:raise ValueError('IDEMPOTENCY_NOT_ESTABLISHED')
    view=store.put_json('viewport',dict(frame=scene['frame'],bounds_mm=case['viewport_mm']))
    evidence_selection=store.put_json('evidence-selection',dict(source_ids=targets))
    comparison=call(request('compare',dict(left_ref=scene_ref,right_ref=candidate['output_scene_ref'],viewport_ref=view,evidence_selection_ref=evidence_selection)))['result']
    call(request('review',dict(candidate_ref=executed['candidate_ref'],verification_ref=verified['verification_ref'],decision_filters=dict(types=['owner','independent','local'],page_size=100,cursor=None))))
    # Actual wire negative controls. Keep all rejected responses as evidence.
    negatives=[]
    bad=request('compile',dict(english=english.replace('0.020 mm','0.001 mm'),binding_ref=binding_ref))
    negatives.append(call(bad,expected='REJECTED')['error'])
    bad=request('compile',dict(english=english.replace('R09:', 'R08:'),binding_ref=binding_ref))
    negatives.append(call(bad,expected='REJECTED')['error'])
    bad=request('run',dict(output_scope_ref=scope),plan_ref=plan_ref,authorization_ref=store.put_json('authorization',dict(forged=True)),key='unauthorized')
    negatives.append(call(bad,expected='REJECTED')['error'])
    # A candidate can preserve the cumulative visible union while swapping a
    # covered individual contribution. Verification must reject source semantics.
    import copy
    bad_candidate=copy.deepcopy(candidate)
    d=next(d for d in bad_candidate['decisions'] if d['added_area_mm2']>1e-8)
    d['proposed_radius_mm']*=1.001
    bad_ref=store.put_json('candidate',bad_candidate)
    bad=request('verify',dict(candidate_ref=bad_ref,verifier_ref=verifier,proof_scope_ref=proof),plan_ref=plan_ref,authorization_ref=auth,key='tampered-diameter')
    negatives.append(call(bad,expected='REJECTED')['error'])
    # Open the independent frozen C01 comparison only after ABI construction.
    historical_receipt=read(HIST/'FREEZE_RECEIPT.json');verify_files(HIST/'frozen',historical_receipt['file_bindings'])
    old=read(HIST/'frozen/report.json');oldmap={r['source_id']:r for r in old['decisions']}
    matches=[]
    for d in candidate['decisions']:
        previous=oldmap[d['source_id']]
        previous_path=HIST/'frozen'/previous['geometry']['dynamic'];blob=store.get(d['candidate_ref'],kind='geometry')
        matches.append(dict(key=d['key'],source_id=d['source_id'],aliases=d['aliases'],expected_sha256=sha(previous_path),actual_sha256=digest(blob),bytes_equal=blob==previous_path.read_bytes(),expected_radius_mm=previous['proposed_radius_mm'],actual_radius_mm=d['proposed_radius_mm'],decision_equal=d['decision']==previous['decision'],priority_equal=d['priority']==previous['priority']))
    write(out/'C01_SOURCE_MATCHES.json',matches)
    if len(matches)!=51 or any(not all(r[k] for k in ('bytes_equal','decision_equal','priority_equal')) or r['expected_radius_mm']!=r['actual_radius_mm'] for r in matches):
        raise ValueError('C01_SAVED_SOURCE_REPRODUCTION_MISMATCH')
    if candidate['allocation']['groups']!=old['groups']:raise ValueError('C01_GROUP_ALLOCATION_MISMATCH')
    protected_after=[frozen_fingerprint(ROOT,r) for r in freezes]
    preserved_after={p:sha(ROOT/p) for p in baseline}
    if protected_after!=protected_before or preserved_after!=preserved_before:raise ValueError('PROTECTED_BASELINE_CHANGED')
    receipt=dict(status='PASS_COMPLETE_C01_ENGLISH_CONTRACT_ABI_REPRODUCTION',branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),source_sha256=case['source_sha256'],english_sha256=policy['english_sha256'],binding_ref=binding_ref,policy_ref=policy_ref,scene_ref=scene_ref,plan_ref=plan_ref,candidate_ref=executed['candidate_ref'],verification_ref=verified['verification_ref'],output_scene_ref=candidate['output_scene_ref'],before_ref=candidate['before_ref'],after_ref=candidate['after_ref'],comparison_ref=comparison['comparison_ref'],source_cache_objects=len(objects),matched_canonical_sites=len(matches),matched_alias_occurrences=candidate['source_occurrences'],all_51_candidate_bytes_equal=True,all_decisions_priorities_radii_equal=True,counts=candidate['counts'],neighbor_response_sites=candidate['neighbor_response_sites'],neighbor_response_controls=len(candidate['events']),evolving_companion_response_sites=candidate['evolving_companion_response_sites'],square_disabled_controls=candidate['square_disabled_controls'],negative_wire_controls=negatives,construction_path='All discovery, target allocation and geometry construction through tools/t01_agent_abi.py JSON subprocess requests; host imports source/registers authority only; saved target opened afterward',idempotent_run_reused=True,assets=assets,protected_before=protected_before,protected_after=protected_after,non_T01_baseline_files_unchanged=len(baseline),T02_T03_T04_T05='UNCHANGED_AND_NOT_EXECUTED',owner='NOT_GRANTED_FOR_NEW_CANDIDATE',independent='NOT_RUN: CHANNEL_UNAVAILABLE',native_electrical_manufacturing='NOT_ESTABLISHED',verification=verified['verification'],geometry_comparison='Per-site byte equality; cumulative union comparison/visuals generated separately')
    write(out/'RECEIPT.json',receipt)
    for p in [*sorted((ROOT/'src/t01_abi').glob('*.py')),ROOT/'tools/t01_agent_abi.py',Path(__file__),*sorted((ROOT/'contracts/t01').glob('*'))]:
        dest=out/'code_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    print(json.dumps({k:receipt[k] for k in ('status','matched_canonical_sites','matched_alias_occurrences','counts','neighbor_response_sites','neighbor_response_controls','evolving_companion_response_sites','non_T01_baseline_files_unchanged')}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
