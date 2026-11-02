"""U02 finite-copper policy, complete pagination and closed native orchestration."""
import copy,json,threading
from pathlib import Path
from types import SimpleNamespace
import pytest
from shapely.geometry import Point,box
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.u02_board.adapter import pair_check,require_supported,verify_candidate,RetainPathsAdapter,FAMILY
from src.u02_board.custody import STEPS,T03,PREFIX,THROUGH_T03,CONTRACT
from src.t01_crop.paging import store_pages,read_pages
from tools.t01_route_client import encode,publish

POLICY=json.loads(CONTRACT.read_bytes())['policy']


def test_same_t01_clearance_and_no_later_stage_or_renderer():
    from tools.pcb_u02_board_operator import U02Operator
    from src.pcb_data_abi.board_custody import ROI,T01,CHECK,FILES
    assert PREFIX==(*ROI,*T01,CHECK) and STEPS==(*PREFIX,*T03,*FILES)
    assert len(STEPS)==25 and len(set(STEPS))==25 and U02Operator.steps==STEPS
    assert POLICY['hard_gap_mm']==.020 and POLICY['area_epsilon_mm2']==1e-10
    assert not any(s.startswith(('t02_','t04_','t05_','render_')) for s in STEPS)


def test_finite_copper_near_miss_requires_movement_despite_disjoint_centerline():
    core=Point(0,0).buffer(.1);grown=Point(0,0).buffer(.2);trace=box(.21,-.03,.4,.03)
    q=pair_check(core,grown,trace,None,POLICY)
    assert not grown.intersects(trace) and not q['passed'] and q['forbidden_intrusion_mm2']>0
    with pytest.raises(ValueError,match='MOVEMENT_NOT_QUALIFIED'):require_supported([dict(source_id='trace',pairs=[q])])


def test_exact_source_port_exemption_retains_attachment_without_permission_expansion():
    core=Point(0,0).buffer(.1);grown=core.buffer(.02);trace=box(-.3,-.015,0,.015)
    assert not pair_check(core,grown,trace,None,POLICY)['passed']
    port=trace.buffer(.04).intersection(core.buffer(.05))
    q=pair_check(core,grown,trace,port,POLICY)
    assert q['passed'] and q['original_contact_preserved'] and q['port_sha256']


@pytest.mark.parametrize('field,value',[('output_scene_ref',{}),('predecessor_scene_ref',{}),('changed_trace_count',1),('replacement_refs',{'hidden':'route'}),('disposition','CONSTRUCTED')])
def test_no_change_candidate_must_reconstruct_exactly(field,value):
    ref=dict(artifact_id='scene:'+'a'*64,sha256='a'*64);plan=dict(trace_inventory_ref={'bound':'inventory'})
    candidate=dict(family=FAMILY,plan_sha256=digest(canonical(plan)),predecessor_scene_ref=ref,output_scene_ref=ref,disposition='NO_CHANGE_REQUIRED',changed_trace_count=0,replacement_refs={},trace_inventory_ref=plan['trace_inventory_ref'])
    verify_candidate(candidate,plan,ref);candidate[field]=value
    with pytest.raises(ValueError,match='RECONSTRUCTION_MISMATCH'):verify_candidate(candidate,plan,ref)


def adapter_fixture(tmp_path,count=237):
    adapter=RetainPathsAdapter.__new__(RetainPathsAdapter);adapter.root=tmp_path;adapter.out=tmp_path/'u02_t03';adapter.store=ArtifactStore(tmp_path/'runtime');adapter.policy=POLICY
    adapter.scene_ref=adapter.store.put_json('scene',{'fixture':'predecessor'});adapter.binding=dict(predecessor_scene_ref=adapter.scene_ref)
    records=[dict(source_id=str(i),pairs=[],geometry_sha256=digest(str(i).encode())) for i in range(count)]
    coverage=dict(source_objects=count,canonical_sites=2,site_occurrences=3,source_pages=3,port_pages=1,source_sha256='a'*64)
    adapter.assess=lambda:(records,coverage)
    return adapter,records


def test_all_seven_t03_gates_exhaust_pages_and_reconstruct_with_real_negative_geometry(tmp_path):
    adapter,records=adapter_fixture(tmp_path)
    results=[adapter.dispatch(op) for op in T03]
    assert results[0]['facts']['trace_occurrences']==237 and results[0]['facts']['trace_pages']==3
    assert results[2]['candidate']['disposition']=='NO_CHANGE_REQUIRED'
    assert results[3]['facts']['fresh_reconstruction'] is True
    assert results[4]['facts']['comparison_pages']==3
    assert len(results[-1]['controls'])==3 and all(r['status']=='PASS_EXPECTED_REJECTION' for r in results[-1]['controls'])


def test_missing_page_and_changed_predecessor_cannot_plan(tmp_path):
    from src.stage_abi.contracts import StageABIError
    adapter,records=adapter_fixture(tmp_path);result=adapter.inspect();ref=result['trace_inventory_ref'];index=adapter.store.get_json(ref,kind='u02-traces-index');page=index['pages'][1]['page_ref'];path=adapter.store.root/'artifacts'/page['artifact_id'];path.write_bytes(b'{}')
    with pytest.raises(StageABIError) as error:adapter.plan()
    assert error.value.code=='ARTIFACT_CORRUPTED'


def test_verification_reassesses_instead_of_trusting_inspection(tmp_path):
    adapter,records=adapter_fixture(tmp_path,2);adapter.inspect();adapter.plan();adapter.search()
    records[0]['geometry_sha256']='changed-after-inspection'
    with pytest.raises(ValueError,match='TRACE_RECONSTRUCTION_MISMATCH'):adapter.verify()


def test_movement_findings_are_retained_before_plan_halts(tmp_path):
    adapter,records=adapter_fixture(tmp_path,2);records[1]['pairs']=[dict(passed=False,original_contact_preserved=True)]
    adapter.inspect()
    with pytest.raises(ValueError,match='MOVEMENT_NOT_QUALIFIED'):adapter.plan()
    assert (adapter.out/'t03_inspect.json').is_file() and not(adapter.out/'t03_plan.json').exists()


def test_u02_route_exposes_only_own_sequence_and_rejects_skipping_audit(tmp_path):
    from tools.u02_board_route import U02Route
    from tools.t01_native_route import RouteError
    route=U02Route.__new__(U02Route);route.operations=list(STEPS);route.position=0;route.pending=None;route.submitted=True;route.halted=False;route.route_id='fixture';route.session=tmp_path;route.lock=threading.RLock()
    assert {t['name'] for t in route.tools()}=={*STEPS,'board.submit','native_route.info','native_route.verify_receipt','native_route.audit'}
    with pytest.raises(RouteError):route._step('t03_search',dict(route_id='fixture',attempt_id='forbidden'),{})
    for op in ('render_compare','t04_run','t05_run','t02_run'):
        with pytest.raises(RouteError):route.call(op,{}, {})
    assert not list(tmp_path.iterdir())


def test_machine_route_rejects_forged_proof_before_advancement(tmp_path):
    from tools.u02_board_route import MachineRoute
    root=tmp_path;folder=root/'audits/machine-001';folder.mkdir(parents=True);publish(folder/'proof.json',encode(dict(status='PASS')))
    route=MachineRoute.__new__(MachineRoute);route.session=root;route.position=0;route.pending=dict(attempt_id='attempt');route.halted=False;route.audit_hashes={}
    with pytest.raises((ValueError,FileNotFoundError,KeyError)):route._audit(dict(attempt_id='attempt',audit={'note':'generic success'}),{})
    assert route.halted and route.position==0


def test_local_code_missing_directory_and_old_launcher_do_not_read_input(tmp_path,monkeypatch,capsys):
    import sys
    from tools import pcb_u02_board_operator as cli,u02_board_jobs as jobs
    monkeypatch.setattr(jobs,'configure',lambda:None)
    monkeypatch.setattr(sys,'argv',['pcb_u02_board_operator.py','start'])
    assert cli.main()==2
    assert 'EXPLICIT_ABSOLUTE_INPUT_DIRECTORY_REQUIRED' in json.loads(capsys.readouterr().out)['error']
    monkeypatch.setattr(jobs.jobs,'launcher_ready',lambda:{})
    monkeypatch.setattr(jobs.directory,'native_intake',lambda *a,**kw:pytest.fail('Old launcher must reject before intake'))
    with pytest.raises(ValueError,match='UPDATE_REQUIRED'):jobs.intake('/not-read')


def test_native_worker_dispatch_and_namespace_are_distinct(tmp_path,monkeypatch):
    from tools import start_t01_crop_operator as dispatch,start_u02_board_operator as worker
    job=tmp_path/'job';job.mkdir();(job/'job.json').write_bytes(encode(dict(task_scope='u02-board')))
    seen=[];monkeypatch.setattr(worker,'managed_worker',lambda p:seen.append(p)or 0)
    assert dispatch.managed_worker(job/'native')==0 and seen==[job/'native']


def test_terminal_keeps_native_process_and_adapter_failure_protections():
    root=Path(__file__).resolve().parents[1];script=(root/'tools/pcb_u02_board_run.py').read_text()
    assert 'adapter_health(thread,thread_error)' in script and 'traceback.format_exc()' in script and 'retain_error' in script
    assert 'len(operator.steps)' in script and 'total=18' not in script
    assert "action='u02_directory_intake'" in script
    assert 'jobs.launcher_ready(' not in script


def native_session(tmp_path):
    """Fresh native-byte fixture with a real T01 construct and reconstruction."""
    from shapely import from_wkb
    from src.native_inventory import inventory
    from src.pcb_data_abi.board_scope import derive_scope
    from src.t01_board.policy import english
    from src.t01_board.service import BoardService
    from src.t01_board import PROFILE
    raw=b'(kicad_pcb (version 20241229) (generator pcbnew) (layers (0 "F.Cu" signal) (31 "B.Cu" signal)) (gr_circle (center 0 0) (end .12497 0) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu")) (gr_circle (center 2 0) (end 2.14999 0) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu")) (segment (start 0 0) (end -.5 0) (width .02) (layer "F.Cu") (net 0)))'
    inv=inventory(raw);rows=[r for r in inv['objects'] if 'F.Cu' in r['layers']]
    for r in rows:r['trace_width_mm']=.02 if r['kind']=='segment' else 0.
    store=ArtifactStore(tmp_path/'runtime');manifest=dict(source_sha256=digest(raw),objects=rows);mr=store.put_json('native-manifest',manifest)
    shapes=[from_wkb(inv['payloads'][r['geometry_sha256']]) for r in rows];scope=derive_scope(raw,manifest,shapes);scope.update(schema='pcb-board-scope-verified/1',manifest_sha256=mr['sha256'],facts=dict(complete_source_coverage=True));sr=store.put_json('board-binding',scope)
    objects=[]
    for row in rows:
        ref=store.put('geometry',inv['payloads'][row['geometry_sha256']]);objects.append(dict(source_id=row['id'],kind='circle'if row['kind']=='gr_circle'else'fixed_source',original_ref=ref,geometry_ref=ref,metadata={}))
    binding=dict(schema='t01-board-binding/1',source_ref=store.put('native-source',raw),manifest_ref=mr,source_sha256=digest(raw),manifest_sha256=mr['sha256'],source_objects=len(rows),source_inventory_ref=store_pages(store,objects,binding=dict(source_sha256=digest(raw),manifest_sha256=mr['sha256']),kind='t01-source-inventory'),viewport_mm=scope['bounds_mm'],scope_ref=sr,scope_sha256=sr['sha256'],reviewed_pairs=[],recess_source_ids=[]);br=store.put_json('t01-binding',binding)
    scene=store.put_json('scene',dict(source_sha256=digest(raw),frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=scope['bounds_mm'],objects=objects,findings=[],lineage=[],acceptance={}))
    bounds=store.put_json('bounds',dict(max_source_objects=len(rows),max_targets=len(rows),max_evaluations=10000,max_output_bytes=200000000,max_seconds=120));vr=store.put_json('verifier',{})
    host=dict(schema='t01-board-host/1',compiler_binding_refs=[br],stage_registry=dict(schema='stage-agent-registry/1',profiles={},authorization_refs=[],decision_refs=[]));pref=None
    def call(verb,payload,plan_ref=None,authorization_ref=None,idempotency_key=None):
        req=dict(abi_version='stage-agent-abi/1.0',request_id='fixture-'+verb,operation='t01_'+verb,profile_id=None if verb=='compile'else PROFILE,scene_ref=None if verb=='compile'else scene,policy_ref=pref,plan_ref=plan_ref,authorization_ref=authorization_ref,idempotency_key=idempotency_key,payload=payload)
        response=BoardService(store,host).dispatch(req);assert response['status']=='OK',response;return response['result']
    pref=call('compile',dict(english=english(),binding_ref=br))['policy_ref'];host['stage_registry']['profiles'][PROFILE]=dict(stage='t01',adapter=PROFILE,policy_ref=pref,scene_refs=[scene],bounds_ref=bounds,verifier_ref=vr)
    discovery=call('discover',dict(bounds_ref=bounds));inspection=call('inspect_all',dict(selection_ref=discovery['selection_ref'],page_size=100));qualification=store.put_json('verification',dict(scene_ref=scene,geometric_status='PASS'))
    planned=call('plan',dict(inspection_ref=inspection['inspection_ref'],selection_ref=discovery['selection_ref'],predecessor_qualification_ref=qualification,bounds_ref=bounds,strategy='priority_companion_growth'));pr=planned['plan_ref'];out=store.put_json('output-scope',dict(kind='immutable-local-artifacts'));auth=store.put_json('authorization',dict(profile_id=PROFILE,scene_ref=scene,policy_ref=pref,plan_ref=pr,operations=['t01_run','t01_verify'],authority='U02 synthetic fixture',output_scope_ref=out));host['stage_registry']['authorization_refs'].append(auth)
    ran=call('run',dict(output_scope_ref=out),pr,auth,'fresh-run')['result'];proof=store.put_json('proof-scope',dict(scope='complete-board-t01-source-reconstruction'))
    verified=call('verify',dict(candidate_ref=ran['candidate_ref'],verifier_ref=vr,proof_scope_ref=proof),pr,auth,'fresh-verify')['result']
    (tmp_path/'RECEIPT.json').write_bytes(encode(dict(status='PASS_BOARD_T01_VERIFIED',candidate_ref=ran['candidate_ref'],verification_ref=verified['verification_ref'],scene_ref=scene)))
    (tmp_path/'capsule_02.json').write_bytes(encode(dict(store_path=str(store.root),policy_ref=pref,plan_ref=pr)))
    return RetainPathsAdapter(tmp_path)


def test_actual_native_source_t01_predecessor_and_source_ports_complete_t03(tmp_path):
    adapter=native_session(tmp_path);result=adapter.inspect()
    assert result['facts']['trace_occurrences']==1 and result['facts']['complete_source_coverage'] is True
    assert result['facts']['affected_pairs']>=1 and result['facts']['movement_objectives']==0
    for op in T03[1:]:assert adapter.dispatch(op)['facts']['passed'] is True


def test_actual_native_predecessor_hidden_trace_change_is_rejected(tmp_path):
    adapter=native_session(tmp_path);trace=next(r for r in adapter.scene['objects'] if r['kind']=='fixed_source');trace['geometry_ref']=adapter.store.put('geometry',b'changed')
    with pytest.raises(ValueError,match='EXACT_T01_PREDECESSOR_REQUIRED'):adapter.inspect()


def test_launcher_accepts_u02_intake_only_into_its_separate_namespace(tmp_path,monkeypatch):
    from tools import t01_crop_jobs as jobs,t01_crop_launcher as module,u02_board_jobs as u02
    monkeypatch.setattr(jobs,'ROOT',tmp_path);monkeypatch.setattr(jobs,'MANAGED',tmp_path/'out/t01-managed');monkeypatch.setattr(u02,'MANAGED',tmp_path/'out/u02-managed')
    class Process:
        pid=987
        def poll(self):return 0
    calls=[];monkeypatch.setattr(module.subprocess,'Popen',lambda argv,**kw:calls.append(argv)or Process())
    launcher=module.Launcher(tmp_path/'out/launcher')
    try:
        req=dict(action='u02_directory_intake',launcher_id=launcher.id,input_directory='/not-read-by-client',companion_policy='PRESERVE_EXCLUDED');publish(launcher.registry/'inbox/u02.json',encode(req));launcher.tick()
        assert len(calls)==1 and calls[0][-1]==str(u02.MANAGED)
        assert jobs.MANAGED==tmp_path/'out/t01-managed'
        assert json.loads((launcher.registry/'current.json').read_bytes())['u02_board']=='native-u02/1'
        launcher.tick();assert len(calls)==1
    finally:launcher.close()


def test_u02_output_requires_external_storage_and_missing_mount_has_no_fallback(tmp_path,monkeypatch):
    from tools import u02_board_jobs as module
    def missing():raise RuntimeError('LACIE_WORKSPACE_UNAVAILABLE')
    monkeypatch.setattr(module,'require_storage',missing);monkeypatch.setattr(module,'MANAGED',tmp_path/'absent')
    with pytest.raises(RuntimeError,match='UNAVAILABLE'):module.configure()
    assert not(tmp_path/'absent').exists()


@pytest.mark.parametrize('machine',[False,True])
def test_expected_negative_compile_null_result_reaches_pending_audit(tmp_path,machine):
    """Exercise offer(), not just the helper: a valid negative has no result body."""
    from tools.pcb_u02_board_operator import U02Operator
    from tools.u02_board_auto_operator import MachineOperator
    from tools.t01_board_route import BoardRoute
    from tools.pcb_c01_operator import sha
    raw=dict(abi_version='stage-agent-abi/1.0',request_id='negative-fixture',operation='t01_compile',
             status='REJECTED',result=None,error=dict(code='T01_ENGLISH_UNSUPPORTED',message='Complete whole-board normative wording required'))
    route=BoardRoute.__new__(BoardRoute)
    facts=route._facts('t01_negative_compile',raw,2,tmp_path/'response.json')
    response=tmp_path/'response.json';response.write_bytes(encode(raw))
    operator=(MachineOperator if machine else U02Operator).__new__(MachineOperator if machine else U02Operator)
    operator.ui=tmp_path/'operator_ui';operator.ui.mkdir();operator.state_path=operator.ui/'current.json';operator.binding_blob=b'fixture-binding'
    operator.info=lambda:dict(pending_audit=None,next_operation='t01_negative_compile')
    calls=[]
    result=dict(error=None,result=dict(facts=facts,raw_response_path=str(response),raw_response_sha256=sha(response.read_bytes())))
    def invoke(operation,attempt):calls.append(operation);return result
    operator.client=SimpleNamespace(invoke=invoke)
    summary=operator.offer(operator.steps.index('t01_negative_compile'))
    assert summary['status']==('MACHINE_AUDIT_REQUIRED' if machine else 'REVIEW_REQUIRED')
    assert summary['facts']==dict(negative_code='T01_ENGLISH_UNSUPPORTED',policy_emitted=False,construction_status='NOT_RUN')
    assert calls==['t01_negative_compile']
    assert operator.state()['status']=='REVIEW_REQUIRED'
    assert not list(operator.ui.glob('review-*.json'))
    assert not(operator.ui/'terminal.json').exists()


@pytest.mark.parametrize('machine',[False,True])
def test_u02_summary_preserves_control_details_for_successful_results(machine):
    from tools.pcb_u02_board_operator import U02Operator
    from tools.u02_board_auto_operator import MachineOperator
    cls=MachineOperator if machine else U02Operator;operator=cls.__new__(cls)
    controls=[dict(name='finite_copper_intrusion',status='PASS_EXPECTED_REJECTION')]
    summary=operator.summary_details(operator.steps.index('t03_controls'),dict(controls=controls))
    assert summary['controls']==controls and summary['total_slices']==25
