"""The export-only profile stops at eighteen audited operations and exposes no renderer."""
from pathlib import Path
from types import SimpleNamespace
import json,threading,pytest
from tools import t01_board_export_route as module
from tools.pcb_t01_board_export_operator import ExportOperator
from tools.t01_native_route import RouteError
from src.pcb_data_abi.board_custody import STEPS as ALL_STEPS


def route():
    r=module.ExportOnlyRoute.__new__(module.ExportOnlyRoute);r.operations=list(module.STEPS);r.route_id='test';r.lock=threading.RLock();r.position=0;r.pending=None;r.accepted=[];r.identity={};r.session=Path('/not-read');r.halted=False;r.submitted=False;return r


def test_profile_is_exact_eighteen_slice_export_prefix_without_image_work():
    r=route();assert list(module.STEPS)==list(ALL_STEPS[:18])==list(ExportOperator.steps)
    names={x['name']for x in r.tools()};assert names=={*module.STEPS,'board.submit','native_route.info','native_route.verify_receipt','native_route.audit'}
    for name in['render_compare','render_verify','render_controls','t02_run','t03_run','t04_run','t05_run']:
        with pytest.raises(RouteError)as error:r.call(name,{}, {})
        assert error.value.code=='TOOL_NOT_EXPOSED'


def test_argv_never_selects_renderer():
    r=route();r.cap=dict(registry_path='/explicit/host',registry_sha256='a'*64)
    for i,op in enumerate(module.STEPS):
        if op in module.T01:continue
        r.position=i;argv=r._argv(Path('/explicit/request'))
        assert all('render'not in str(part)for part in argv)
        assert any(name in str(argv)for name in['pcb_directory_data_abi.py','pcb_board_candidate_check.py','pcb_board_data_abi.py'])


def test_submit_has_no_optional_project_input_default():
    r=route()
    with pytest.raises((ValueError,RouteError)):r.submit({}, {})


def test_last_observation_makes_export_checkpoint_and_finishes_without_render_host(tmp_path,monkeypatch):
    r=route();r.session=tmp_path;r.position=17;r.pending=SimpleNamespace();r.responses={};r.accepted=list(module.STEPS[:17]);r.audit_hashes={};r.identity={'test':'native'}
    (tmp_path/'audits').mkdir();(tmp_path/'data_output').mkdir();facts=dict(passed=True);audit=dict(verdict='PASS',response_sha256='a'*64,observed=facts,note='actual observation')
    r.pending=dict(attempt_id='last',operation='pcb_export_controls',result=dict(raw_response_sha256='a'*64,facts=facts),response=dict(result=facts),path=tmp_path/'attempts/last')
    r._valid_args=lambda *a,**k:None;r._prior_integrity=lambda:None;monkeypatch.setattr(module,'check',lambda p:None)
    seen=[];monkeypatch.setattr(module,'checkpoint',lambda root,name,ops,extras:seen.append((name,tuple(ops)))or dict(checkpoint=str(root/name),checkpoint_sha256='b'*64))
    def forbidden(*a,**k):pytest.fail('Export-only completion may not allocate any renderer')
    r._set_host=forbidden
    result=r._audit(dict(route_id=r.route_id,attempt_id='last',audit=audit),{})
    assert result['next_operation']is None and r.position==18 and seen==[('EXPORT_CHECKPOINT.json',module.STEPS)]
    assert json.loads((tmp_path/'EXPORT_ONLY_RECEIPT.json').read_bytes())['rendering']=='NOT_REQUESTED'
    assert not(tmp_path/'pipeline_render_host.json').exists()and not(tmp_path/'render_output').exists()
    # The route's native info is terminal at 18, rather than indexing a 21-step list.
    (tmp_path/'START.json').write_text('{}');assert r.info()['status']=='COMPLETE_AUDITED_BOARD_EXPORT_SEQUENCE'


def test_existing_mac_launcher_dispatches_explicit_new_scope(tmp_path,monkeypatch):
    from tools import start_t01_crop_operator as entry,start_t01_board_export_operator as worker
    job=tmp_path/'job';job.mkdir();(job/'job.json').write_text(json.dumps(dict(task_scope='full-board-export-only')));seen=[]
    monkeypatch.setattr(worker,'managed_worker',lambda path:seen.append(path)or 0)
    assert entry.managed_worker(job/'native')==0 and seen==[job/'native']


def test_cli_requires_input_directory_without_using_project_defaults(monkeypatch,capsys):
    from contextlib import nullcontext
    from tools import pcb_t01_board_export_operator as operator
    import sys
    monkeypatch.setattr(operator.jobs,'exclusive',nullcontext)
    monkeypatch.setattr(operator.jobs,'launcher_ready',lambda:pytest.fail('Missing directory must fail before native launcher'))
    monkeypatch.setattr(sys,'argv',['pcb_t01_board_export_operator.py','start'])
    assert operator.main()==2;result=json.loads(capsys.readouterr().out);assert result['error'].startswith('EXPLICIT_INPUT_DIRECTORY_REQUIRED')and result['evidence']is None


def test_wrong_facade_rejects_before_touching_an_export_only_job(monkeypatch,capsys):
    from contextlib import nullcontext
    from tools import pcb_t01_board_operator as old
    import sys
    monkeypatch.setattr(old.jobs,'exclusive',nullcontext);monkeypatch.setattr(old.jobs,'current',lambda:(Path('/not-opened'),dict(task_scope='full-board-export-only')))
    monkeypatch.setattr(old.jobs,'halt',lambda *a:pytest.fail('Wrong facade cannot halt another profile'))
    monkeypatch.setattr(sys,'argv',['pcb_t01_board_operator.py','review','do not advance'])
    assert old.main()==2;assert 'EXPORT_ONLY_JOB_USE_EXPORT_OPERATOR'in json.loads(capsys.readouterr().out)['error']


def test_first_gate_checks_every_layer_with_json_manifest_path(tmp_path,monkeypatch):
    from tools.t01_board_route import BoardRoute
    r=route();r.session=tmp_path/'native';r.session.mkdir();manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(dict(files=[dict(kind='kicad'),dict(kind='gerber'),dict(kind='gerber')])));(tmp_path/'job.json').write_text(json.dumps(dict(input_directory=str(manifest))))
    facts=dict(provided_gerber_files=2,all_supplied_layers_verified=True)
    monkeypatch.setattr(BoardRoute,'_facts',lambda *a:facts)
    assert r._facts('pcb_inputs_verify',{},0,tmp_path/'response')==facts
    facts['provided_gerber_files']=1
    with pytest.raises(ValueError,match='ALL_DIRECTORY_LAYERS'):r._facts('pcb_inputs_verify',{},0,tmp_path/'response')


def test_native_v2_intake_receipt_and_companions_are_bound_before_pipeline(tmp_path,monkeypatch):
    import hashlib,json
    from tools import t01_crop_jobs as jobs,t01_board_export_jobs as exports
    from tools.t01_route_client import encode,publish
    from src.pcb_data_abi.input_directory import digest
    monkeypatch.setattr(jobs,'ROOT',tmp_path);monkeypatch.setattr(jobs,'MANAGED',tmp_path/'out/managed');monkeypatch.setattr(jobs,'implementation',lambda:'test')
    blobs={'board.kicad_pcb':b'(kicad_pcb)','source.gbr':b'qualified raw bytes','companion.gbr':b'excluded raw bytes'}
    files=[dict(relative_path=n,kind='kicad'if n.endswith('.kicad_pcb')else'gerber'if n=='source.gbr'else'companion',layer='F.Cu'if n=='source.gbr'else None,sha256=digest(b),bytes=len(b))for n,b in blobs.items()]
    proof=dict(schema='pcb-directory-identification/1',companion_policy='PRESERVE_EXCLUDED',registration_fit_used=False,native_source_sha256=digest(blobs['board.kicad_pcb']),matches=[dict(relative_path='source.gbr',layer='F.Cu')],excluded_companions=['companion.gbr'])
    manifest=dict(schema='pcb-raw-input-directory/2',provided_directory='/explicit',files=files,ignored_metadata=[],identification=proof)
    job,row=exports.allocate(manifest,blobs);call=tmp_path/'out/native-call';call.mkdir();publish(call/'request.json',b'{}');publish(call/'IDENTIFICATION.json',encode(manifest))
    receipt=dict(schema='pcb-native-directory-intake/1',job=str(job),rendering='NOT_REQUESTED',request=str(call/'request.json'),request_sha256=digest(b'{}'),identification=str(call/'IDENTIFICATION.json'),identification_sha256=digest(encode(manifest)))
    publish(job/'INTAKE_RECEIPT.json',encode(receipt));monkeypatch.setattr(module,'local',lambda p,*a:Path(p));monkeypatch.setattr(module,'check',lambda p:None)
    r=route();r.session=job/'native';r.session.mkdir();r.bound_outputs={}
    assert r.submit(row['staged'],{})['status']=='BOARD_INPUTS_BOUND'
    assert str(job/'raw_inputs/companion.gbr')in r.bound_outputs
    assert str(call/'request.json')in r.bound_outputs and str(call/'IDENTIFICATION.json')in r.bound_outputs
