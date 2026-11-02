"""Whole-board source coverage, authority, pagination and unchanged T01 behavior."""
import copy,json
from pathlib import Path
import pytest
from shapely import from_wkb
from src.native_inventory import inventory
from src.stage_abi.store import ArtifactStore,digest
from src.stage_abi.contracts import StageABIError
from src.pcb_data_abi.board_scope import derive_scope,assess_scope
from src.t01_board import PROFILE
from src.t01_board.policy import english,compile_policy,validate_binding
from src.t01_board.source import context
from src.t01_board.service import BoardService
from src.t01_crop.paging import store_pages


def environment(tmp_path,count=3):
    circles=[(0,0,.12497),(0,0,.06),(2,0,.14999)]if count==3 else[(i*2,0,.12497)for i in range(count)]
    circles.append(circles[0]) # exact native alias, not a second canonical target
    body=' '.join(f'(gr_circle (center {x} {y}) (end {x+r} {y}) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))'for x,y,r in circles)
    if count==3:body+=' (segment (start 0 0) (end -.5 0) (width .02) (layer "F.Cu") (net 0))'
    raw=('(kicad_pcb (version 20241229) (generator pcbnew) (layers (0 "F.Cu" signal) (31 "B.Cu" signal)) '+body+')').encode()
    inv=inventory(raw);rows=[r for r in inv['objects']if'F.Cu'in r['layers']]
    for row in rows:row['trace_width_mm']=0.
    manifest=dict(source_sha256=digest(raw),objects=rows);shapes=[from_wkb(inv['payloads'][r['geometry_sha256']])for r in rows];store=ArtifactStore(tmp_path/'runtime');mref=store.put_json('native-manifest',manifest)
    scope=derive_scope(raw,manifest,shapes);scope.update(schema='pcb-board-scope-verified/1',manifest_sha256=mref['sha256'],facts=dict(complete_source_coverage=True))
    sref=store.put_json('board-binding',scope);objects=[]
    for row in rows:
        g=store.put('geometry',inv['payloads'][row['geometry_sha256']]);objects.append(dict(source_id=row['id'],kind='circle'if row['kind']=='gr_circle'else'fixed_source',original_ref=g,geometry_ref=g,metadata={}))
    bref=store.put_json('t01-binding',dict(schema='t01-board-binding/1',source_ref=store.put('native-source',raw),manifest_ref=mref,source_sha256=digest(raw),manifest_sha256=mref['sha256'],source_objects=len(rows),source_inventory_ref=store_pages(store,objects,binding=dict(source_sha256=digest(raw),manifest_sha256=mref['sha256']),kind='t01-source-inventory'),viewport_mm=scope['bounds_mm'],scope_ref=sref,scope_sha256=sref['sha256'],reviewed_pairs=[],recess_source_ids=[]))
    scene=dict(source_sha256=digest(raw),frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=scope['bounds_mm'],objects=objects,findings=[],lineage=[],acceptance={});scene_ref=store.put_json('scene',scene)
    bounds=store.put_json('bounds',dict(max_source_objects=len(rows),max_targets=len(rows),max_evaluations=10000,max_output_bytes=200000000,max_seconds=120));verifier=store.put_json('verifier',{})
    host=dict(schema='t01-board-host/1',compiler_binding_refs=[bref],stage_registry=dict(schema='stage-agent-registry/1',profiles={},authorization_refs=[],decision_refs=[]));service=BoardService(store,host)
    def req(verb,payload,**extra):return dict(abi_version='stage-agent-abi/1.0',request_id='board-'+verb,operation='t01_'+verb,profile_id=PROFILE,scene_ref=scene_ref,policy_ref=pref,plan_ref=None,authorization_ref=None,idempotency_key=None,payload=payload,**extra)
    compile_req=dict(abi_version='stage-agent-abi/1.0',request_id='board-compile',operation='t01_compile',profile_id=None,scene_ref=None,policy_ref=None,plan_ref=None,authorization_ref=None,idempotency_key=None,payload=dict(english=english(),binding_ref=bref))
    result=service.dispatch(compile_req);assert result['status']=='OK',result;pref=result['result']['policy_ref'];host['stage_registry']['profiles'][PROFILE]=dict(stage='t01',adapter=PROFILE,policy_ref=pref,scene_refs=[scene_ref],bounds_ref=bounds,verifier_ref=verifier);service=BoardService(store,host)
    return store,service,req,host,scene,bref,bounds,scope


def test_whole_board_complete_discovery_aliases_and_covered_circle(tmp_path):
    store,service,req,host,scene,bref,bounds,scope=environment(tmp_path)
    r=service.dispatch(req('discover',dict(bounds_ref=bounds)))
    assert r['status']=='OK',r
    assert r['result']['discovery']['unique_sites']==3 and r['result']['discovery']['occurrences']==4
    _,_,_,_,sites=context(store,scene,compile_policy(english(),bref));assert sorted(len(s['aliases'])for s in sites)==[1,1,2]
    assert scope['image_used']is False

@pytest.mark.parametrize('mutation',['bounds','alias','source','count'])
def test_scope_omission_or_shortened_view_cannot_authorize_t01(tmp_path,mutation):
    store,service,req,host,scene,bref,bounds,scope=environment(tmp_path);binding=store.get_json(bref,kind='t01-binding');value=copy.deepcopy(scope)
    if mutation=='bounds':value['bounds_mm'][2]-=.1
    elif mutation=='alias':value['eligible_occurrence_ids'].pop()
    elif mutation=='source':value['all_source_ids'].pop()
    else:value['canonical_sites']-=1
    ref=store.put_json('board-binding',value);binding.update(scope_ref=ref,scope_sha256=ref['sha256']);bad=store.put_json('t01-binding',binding)
    with pytest.raises(StageABIError):context(store,scene,compile_policy(english(),bad))


def test_more_than_1000_board_sites_have_complete_inspection_and_comparison(tmp_path):
    store,service,req,host,scene,bref,bounds,scope=environment(tmp_path,1001)
    d=service.dispatch(req('discover',dict(bounds_ref=bounds)));assert d['status']=='OK',d
    selection=d['result']['selection_ref'];inspection=service.dispatch(req('inspect_all',dict(selection_ref=selection,page_size=100)))
    assert inspection['status']=='OK'and inspection['result']['total_records']==1001 and inspection['result']['page_count']==11
    viewport=store.put_json('viewport',dict(frame=scene['frame'],bounds_mm=scene['viewport_mm']));evidence=store.put_json('evidence-selection',dict(source_ids=d['result']['discovery']['source_ids']))
    r=service.dispatch(req('compare_all',dict(left_ref=req('x',{})['scene_ref'],right_ref=req('x',{})['scene_ref'],viewport_ref=viewport,evidence_selection_ref=evidence,page_size=100)))
    assert r['status']=='OK'and len(r['result']['source_changes'])==1001 and r['result']['page_count']==11

@pytest.mark.parametrize('stage',['t02','t03','t04','t05'])
def test_whole_board_service_cannot_run_later_stages(tmp_path,stage):
    _,service,req,*_=environment(tmp_path);r=req('run',{});r['operation']=stage+'_run';result=service.dispatch(r)
    assert result['status']=='REJECTED'and result['result']is None


def test_policy_preserves_all_numeric_settings_and_concentric_interaction():
    from src.t01_crop.policy import compile_policy as crop,english as crop_english
    ref=dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64);p=compile_policy(english(),ref);old=crop(crop_english(),ref)
    assert p['settings']==old['settings']and p['diameter_classes_mm']==old['diameter_classes_mm']
    assert p['rules']['pair_interaction']==old['rules']['pair_interaction']
    with pytest.raises(StageABIError):compile_policy(english().replace('hard gap 0.020 mm','hard gap 0.019 mm'),ref)


def test_board_plan_requires_data_gates_and_distinct_observation(tmp_path):
    from tools.t01_board_route import BoardRoute,STEPS
    route=BoardRoute.__new__(BoardRoute);route.submitted=True;route.halted=False;route.pending=None;route.position=0;route.operations=list(STEPS);route.route_id='test';route.session=tmp_path
    with pytest.raises(ValueError,match='Audit current result'):route._step('t01_run',dict(route_id='test',attempt_id='forbidden'),{})
    assert not list(tmp_path.iterdir())


def test_board_public_abi_constructs_and_reconstructs_entire_selection(tmp_path):
    store,service,req,host,scene,bref,bounds,scope=environment(tmp_path)
    def ok(r):
        value=service.dispatch(r);assert value['status']=='OK',value;return value['result']
    discovered=ok(req('discover',dict(bounds_ref=bounds)));inspected=ok(req('inspect_all',dict(selection_ref=discovered['selection_ref'],page_size=100)))
    qualified=store.put_json('verification',dict(scene_ref=req('x',{})['scene_ref'],geometric_status='PASS'))
    planned=ok(req('plan',dict(inspection_ref=inspected['inspection_ref'],selection_ref=discovered['selection_ref'],predecessor_qualification_ref=qualified,bounds_ref=bounds,strategy='priority_companion_growth')))
    allocation=planned['plan']['details']['allocation'];assert len(allocation['priority_pool_source_ids'])==3 and allocation['boundary_keep_source_ids']==[]
    assert sum('concentric_source_proof'in g for g in allocation['groups'])==1
    output=store.put_json('output-scope',dict(kind='immutable-local-artifacts'));plan_ref=planned['plan_ref'];authorization=store.put_json('authorization',dict(profile_id=PROFILE,scene_ref=req('x',{})['scene_ref'],policy_ref=req('x',{})['policy_ref'],plan_ref=plan_ref,operations=['t01_run','t01_verify'],authority='Whole-board unit fixture',output_scope_ref=output));host['stage_registry']['authorization_refs'].append(authorization);service=BoardService(store,host)
    r=dict(req('run',dict(output_scope_ref=output)),plan_ref=plan_ref,authorization_ref=authorization,idempotency_key='board-test-run');ran=ok(r)['result'];candidate=ran['candidate']
    assert candidate['unique_sites']==3 and candidate['source_occurrences']==4 and len(candidate['final_checks'])==3
    proof=store.put_json('proof-scope',dict(scope='complete-board-t01-source-reconstruction'));verifier=host['stage_registry']['profiles'][PROFILE]['verifier_ref']
    r=dict(req('verify',dict(candidate_ref=ran['candidate_ref'],verifier_ref=verifier,proof_scope_ref=proof)),plan_ref=plan_ref,authorization_ref=authorization,idempotency_key='board-test-verify');verified=ok(r)['result']['verification'];assert verified['geometric_status']=='PASS'and verified['check']['reconstructed_alias_occurrences']==4


def test_port_pages_preserve_exact_bytes_and_tampering_blocks_construction(tmp_path):
    from src.t01_crop.paging import read_pages
    from src.t01_board.adapter import BoardAdapter
    from src.t01_crop.adapter import CropAdapter
    store,service,req,host,scene,bref,bounds,scope=environment(tmp_path)
    d=service.dispatch(req('discover',dict(bounds_ref=bounds)))['result'];i=service.dispatch(req('inspect_all',dict(selection_ref=d['selection_ref'],page_size=100)))['result'];qualified=store.put_json('verification',dict(scene_ref=req('x',{})['scene_ref'],geometric_status='PASS'))
    r=service.dispatch(req('plan',dict(inspection_ref=i['inspection_ref'],selection_ref=d['selection_ref'],predecessor_qualification_ref=qualified,bounds_ref=bounds,strategy='priority_companion_growth')));assert r['status']=='OK',r
    plan=r['result']['plan'];ports=plan['details']['allocation']['ports'];assert ports['zones']>0;index=store.get_json(ports['index_ref'],kind='t01-board-ports-index')
    records,_=read_pages(store,ports['index_ref'],binding=index['binding'],kind='t01-board-ports',identity=lambda r:r['source_id'])
    policy=store.get_json(req('x',{})['policy_ref'],kind='policy');binding,raw,rows,shapes,sites=context(store,scene,policy)
    original=CropAdapter()._allocate(raw,rows,shapes,sites,policy,dict(binding,location_uncertainty_mm=0))[1]['ports']
    assert {row['source_id']:{oid:store.get(ref,kind='t01-port-geometry').hex()for oid,ref in row['ports'].items()}for row in records}==original
    altered=copy.deepcopy(plan);altered['details']['allocation']['ports']['zones']+=1
    with pytest.raises(StageABIError,match='source-computed allocation'):BoardAdapter()._compute(store,scene,policy,altered,lambda value:None)
