"""English/ABI conformance and fail-closed source/semantic regressions."""
import copy
import json
from pathlib import Path
import pytest
from src.native_inventory import inventory
from src.stage_abi import ABI_VERSION
from src.stage_abi.store import ArtifactStore, digest, canonical
from src.t01_abi import STRATEGY
from src.t01_abi.contract import CLAUSES, compile_english, english_specification, validate_policy
from src.t01_abi.protocol import request_schema, response_schema
from src.t01_abi.service import InteractionService, ADAPTER
from src.stage_abi.contracts import StageABIError

def setup(tmp_path,duplicate=False):
    xs=[0,.8,0 if duplicate else 1.6]
    circles='\n'.join(f'(gr_circle (center {x} 0) (end {x+.12497} 0) (stroke (width 0) (type default)) (fill yes) (layer "F.Cu"))' for x in xs)
    raw=('(kicad_pcb (version 20240108) (generator pcbnew) (layers (0 "F.Cu" signal)) '+circles+')').encode()
    inv=inventory(raw);rows=[r for r in inv['objects'] if 'F.Cu' in r['layers']]
    store=ArtifactStore(tmp_path/'store');objects=[]
    for row in rows:
        g=store.put('geometry',inv['payloads'][row['geometry_sha256']])
        objects.append(dict(source_id=row['id'],kind='circle',original_ref=g,geometry_ref=g,metadata={}))
    manifest=dict(source_sha256=digest(raw),objects=rows);manifest_raw=canonical(manifest)
    # Exact aliases are canonicalized by minimum source identity.
    grouped={}
    for r in rows:grouped.setdefault(r['geometry_sha256'],[]).append(r['id'])
    ids=[min(v) for v in grouped.values()]
    binding=dict(schema='t01-source-binding/1',case_id='synthetic-native-test',source_ref=store.put('native-source',raw),manifest_ref=store.put('native-manifest',manifest_raw),source_sha256=digest(raw),manifest_sha256=digest(manifest_raw),source_objects=len(rows),viewport_mm=[-1,-1,3,1],unique_sites=len(ids),occurrences=len(rows),reviewed_pair=ids[:2],recess_source_ids=[])
    binding_ref=store.put_json('t01-binding',binding)
    scene=dict(source_sha256=digest(raw),frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=binding['viewport_mm'],objects=objects,findings=[],lineage=[],acceptance={})
    scene_ref=store.put_json('scene',scene);bounds=store.put_json('bounds',dict(max_source_objects=100,max_targets=10,max_evaluations=1000,max_output_bytes=10000000,max_seconds=120))
    host=dict(schema='t01-interaction-host/1',compiler_binding_refs=[binding_ref],stage_registry=dict(schema='stage-agent-registry/1',profiles={},authorization_refs=[],decision_refs=[]))
    def request(verb,payload,plan=None,auth=None,key=None):
        return dict(abi_version=ABI_VERSION,request_id='test',operation='t01_'+verb,profile_id=None if verb=='compile' else 'test-profile',scene_ref=None if verb in ('compile','describe') else scene_ref,policy_ref=None if verb in ('compile','describe') else policy_ref,plan_ref=plan,authorization_ref=auth,idempotency_key=key,payload=payload)
    service=InteractionService(store,host)
    compiled=service.dispatch(request('compile',dict(english=english_specification(),binding_ref=binding_ref)))
    assert compiled['status']=='OK',compiled
    policy_ref=compiled['result']['policy_ref']
    verifier=store.put_json('verifier',dict(family='t01-priority-companion/1'))
    host['stage_registry']['profiles']['test-profile']=dict(stage='t01',adapter=ADAPTER,policy_ref=policy_ref,scene_refs=[scene_ref],bounds_ref=bounds,verifier_ref=verifier)
    return store,host,service,request,bounds,verifier,binding_ref,scene

def plan(env):
    store,host,service,request,bounds,verifier,binding_ref,scene=env
    d=service.dispatch(request('discover',dict(bounds_ref=bounds)));assert d['status']=='OK',d
    d=d['result'];ids=d['discovery']['source_ids']
    i=service.dispatch(request('inspect',dict(source_ids=ids,finding_ids=[],page_size=100,cursor=None)));assert i['status']=='OK',i
    q=store.put_json('verification',dict(scene_ref=request('inspect',{})['scene_ref'],geometric_status='PASS'))
    p=service.dispatch(request('plan',dict(inspection_ref=i['result']['inspection_ref'],selection_ref=d['selection_ref'],predecessor_qualification_ref=q,bounds_ref=bounds,strategy=STRATEGY)))
    assert p['status']=='OK',p
    pref=p['result']['plan_ref'];out=store.put_json('output-scope',dict(kind='immutable-local-artifacts'))
    r=request('run',{},pref)
    auth=store.put_json('authorization',dict(profile_id=r['profile_id'],scene_ref=r['scene_ref'],policy_ref=r['policy_ref'],plan_ref=pref,operations=['t01_run','t01_verify'],authority='unit-test-host',output_scope_ref=out))
    host['stage_registry']['authorization_refs'].append(auth)
    return pref,auth,out,d

@pytest.mark.parametrize('clause',[r[0] for r in CLAUSES])
def test_every_english_clause_is_mandatory_and_has_a_typed_meaning(clause):
    ref=dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64)
    text=english_specification();policy=compile_english(text,ref)
    trace=next(r for r in policy['clause_trace'] if r['clause']==clause)
    assert policy['rules'][trace['contract_field']]==trace['value']
    changed='\n'.join(line for line in text.splitlines() if not line.startswith(clause+':'))
    with pytest.raises(StageABIError,match='complete ordered'):compile_english(changed,ref)
    bad=copy.deepcopy(policy);bad['rules'][trace['contract_field']]='different'
    with pytest.raises(StageABIError,match='English derivation'):validate_policy(bad)

def test_no_paraphrase_or_clearance_change_can_silently_compile():
    ref=dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64)
    for old,new in [('0.020 mm','0.001 mm'),('current scene','original scene'),('R09:','R08:'),('1.5 growth cap','2.0 growth cap')]:
        with pytest.raises(StageABIError):compile_english(english_specification().replace(old,new),ref)

def test_full_abi_construction_verification_and_idempotence(tmp_path):
    env=setup(tmp_path);store,host,service,request,_,verifier,_,_=env
    pref,auth,out,d=plan(env)
    r=request('run',dict(output_scope_ref=out),pref,auth,'construct')
    run=service.dispatch(r);assert run['status']=='OK',run
    candidate=run['result']['result'];assert candidate['candidate']['unique_sites']==3
    proof=store.put_json('proof-scope',dict(scope='complete-c01-priority-companion-source-reconstruction'))
    v=service.dispatch(request('verify',dict(candidate_ref=candidate['candidate_ref'],verifier_ref=verifier,proof_scope_ref=proof),pref,auth,'verify'))
    assert v['status']=='OK',v
    assert v['result']['result']['verification']['geometric_status']=='PASS'
    assert service.dispatch(r)['result']['reused'] is True

def test_aliases_are_updated_together_and_not_counted_as_independent_sites(tmp_path):
    env=setup(tmp_path,duplicate=True);store,host,service,request,*_=env
    pref,auth,out,d=plan(env)
    assert d['discovery']['unique_sites']==2 and d['discovery']['occurrences']==3
    r=service.dispatch(request('run',dict(output_scope_ref=out),pref,auth,'construct'))
    assert r['status']=='OK',r
    c=r['result']['result']['candidate'];assert len(c['replacements'])==3
    site=next(x for x in c['decisions'] if len(x['aliases'])==2)
    assert len({json.dumps(c['replacements'][a],sort_keys=True) for a in site['aliases']})==1

def test_wrong_stage_old_strategy_and_extra_authority_are_rejected(tmp_path):
    env=setup(tmp_path);_,_,service,request,_,_,_,_=env
    bad=request('describe',dict(requested_contract_version=ABI_VERSION));bad['operation']='t02_describe'
    assert service.dispatch(bad)['status']=='REJECTED'
    bad=request('discover',dict(bounds_ref=env[4]));bad['payload']['grant_authority']=True
    assert service.dispatch(bad)['status']=='REJECTED'
    bad=request('plan',dict(inspection_ref=env[4],selection_ref=env[4],predecessor_qualification_ref=env[4],bounds_ref=env[4],strategy='round_class_growth'))
    assert service.dispatch(bad)['error']['code']=='T01_WIRE_INVALID'

def test_reconstruction_rejects_tampered_priority_and_geometry(tmp_path):
    env=setup(tmp_path);store,_,service,request,_,verifier,_,_=env
    pref,auth,out,_=plan(env);run=service.dispatch(request('run',dict(output_scope_ref=out),pref,auth,'construct'))
    assert run['status']=='OK',run
    c=run['result']['result']['candidate'];proof=store.put_json('proof-scope',dict(scope='complete-c01-priority-companion-source-reconstruction'))
    for ordinal in range(2):
        bad=copy.deepcopy(c)
        if ordinal==0:bad['decisions'][0]['priority']=not bad['decisions'][0]['priority']
        else:bad['decisions'][0]['candidate_ref']=env[7]['objects'][0]['geometry_ref']
        badref=store.put_json('candidate',bad)
        r=service.dispatch(request('verify',dict(candidate_ref=badref,verifier_ref=verifier,proof_scope_ref=proof),pref,auth,'bad-'+str(ordinal)))
        assert r['status']=='REJECTED' and r['error']['code']=='T01_SEMANTIC_RECONSTRUCTION_MISMATCH',r

def test_omitted_source_object_or_changed_source_cache_cannot_be_discovered(tmp_path):
    env=setup(tmp_path);store,_,service,request,_,_,_,scene=env
    for remove in (True,False):
        altered=copy.deepcopy(scene)
        if remove:altered['objects'].pop()
        else:altered['objects'][0]['geometry_ref']=altered['objects'][1]['geometry_ref']
        r=request('discover',dict(bounds_ref=env[4]));r['scene_ref']=store.put_json('scene',altered)
        profile=env[1]['stage_registry']['profiles']['test-profile'];profile['scene_refs'].append(r['scene_ref'])
        response=service.dispatch(r)
        assert response['status']=='REJECTED',response
        assert response['error']['code']==('T01_SOURCE_COVERAGE_MISMATCH' if remove else 'T01_ORIGINAL_SOURCE_REQUIRED')

def test_wire_schemas_match_delivered_contracts():
    root=Path(__file__).resolve().parents[1]
    assert json.loads((root/'contracts/t01/request.schema.json').read_text())==request_schema()
    assert json.loads((root/'contracts/t01/response.schema.json').read_text())==response_schema()
    assert (root/'contracts/t01/c01.english.txt').read_text()==english_specification()

def test_compiled_policy_matches_closed_machine_contract():
    from jsonschema import Draft202012Validator
    root=Path(__file__).resolve().parents[1]
    schema=json.loads((root/'contracts/t01/policy.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    v=Draft202012Validator(schema)
    p=compile_english(english_specification(),dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64))
    assert not list(v.iter_errors(p))
    p['settings']['hard_gap']=.001
    assert list(v.iter_errors(p))

@pytest.mark.parametrize('bad',[None,[],{}, {'request_id':3,'operation':False}])
def test_malformed_wire_returns_closed_rejection_instead_of_throwing(tmp_path,bad):
    service=setup(tmp_path)[2]
    assert service.dispatch(bad)['status']=='REJECTED'

def test_small_discovery_budget_rejects_before_source_discovery(tmp_path,monkeypatch):
    env=setup(tmp_path);store,host,service,request,*_=env
    import src.t01_abi.adapter as module
    monkeypatch.setattr(module,'discover',lambda *a:pytest.fail('Unbounded discovery was attempted'))
    tiny=store.put_json('bounds',dict(max_source_objects=1,max_targets=10,max_evaluations=1,max_output_bytes=1,max_seconds=1))
    host['stage_registry']['profiles']['test-profile']['bounds_ref']=tiny
    r=service.dispatch(request('discover',dict(bounds_ref=tiny)))
    assert r['error']['code']=='SCOPE_LIMIT_REACHED'

def test_english_reference_compiles_to_identical_policy_without_transcription(tmp_path):
    env=setup(tmp_path);store,_,service,request,_,_,binding,_=env
    reference=store.put('english-spec',english_specification().encode())
    response=service.dispatch(request('compile',dict(english_ref=reference,binding_ref=binding)))
    literal=service.dispatch(request('compile',dict(english=english_specification(),binding_ref=binding)))
    assert response['status']=='OK',response
    assert response['result']==literal['result']

@pytest.mark.parametrize('wrong_kind',[False,True])
def test_english_reference_cannot_bypass_rules_or_artifact_kind(tmp_path,wrong_kind):
    env=setup(tmp_path);store,_,service,request,_,_,binding,_=env
    reference=store.put('geometry' if wrong_kind else 'english-spec',english_specification().replace('0.020 mm','0.001 mm').encode())
    response=service.dispatch(request('compile',dict(english_ref=reference,binding_ref=binding)))
    assert response['status']=='REJECTED'
    assert response['error']['code']==('ARTIFACT_KIND_MISMATCH' if wrong_kind else 'T01_ENGLISH_UNSUPPORTED')

def test_reference_and_literal_english_cannot_be_mixed(tmp_path):
    env=setup(tmp_path);store,_,service,request,_,_,binding,_=env
    reference=store.put('english-spec',english_specification().encode())
    r=service.dispatch(request('compile',dict(english=english_specification(),english_ref=reference,binding_ref=binding)))
    assert r['error']['code']=='T01_WIRE_INVALID'

def test_selection_reference_inspection_matches_explicit_ids_exactly(tmp_path):
    env=setup(tmp_path);store,_,service,request,bounds,*_=env
    d=service.dispatch(request('discover',dict(bounds_ref=bounds)))['result']
    byref=service.dispatch(request('inspect',dict(selection_ref=d['selection_ref'],page_size=100,cursor=None)))
    literal=service.dispatch(request('inspect',dict(source_ids=d['discovery']['source_ids'],finding_ids=[],page_size=100,cursor=None)))
    assert byref['status']=='OK'
    assert byref['result']==literal['result']

def test_selection_reference_is_bound_to_its_source_scene_and_stage(tmp_path):
    env=setup(tmp_path);store,_,service,request,*_=env
    for stage,scene in [('t02',request('inspect',{})['scene_ref']),('t01',dict(artifact_id='scene:'+'a'*64,sha256='a'*64))]:
        wrong=store.put_json('selection',dict(stage=stage,scene_ref=scene,source_ids=[]))
        r=service.dispatch(request('inspect',dict(selection_ref=wrong,page_size=100,cursor=None)))
        assert r['error']['code']=='T01_SELECTION_BINDING_MISMATCH'
