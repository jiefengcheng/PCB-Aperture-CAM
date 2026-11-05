"""App protocol retains native authority, machine mode and terminal integrity."""
import json
from pathlib import Path
import pytest
from tools import u05_app as app
from tools.t01_route_client import encode,publish

@pytest.fixture
def registry(tmp_path,monkeypatch):
    root=tmp_path/'launcher';root.mkdir();(root/'inbox').mkdir();(root/'calls').mkdir();(root/'replies').mkdir()
    monkeypatch.setattr(app.jobs,'WORK',tmp_path);monkeypatch.setattr(app.jobs,'LAUNCHER',root);monkeypatch.setattr(app.jobs,'output',lambda p:Path(p))
    monkeypatch.setattr(app.jobs,'launcher_ready',lambda:dict(launcher_id='launcher-test',u05_board=app.CAPABILITY))
    return root

def test_old_launcher_does_not_submit_or_allocate(registry,monkeypatch):
    monkeypatch.setattr(app.jobs,'launcher_ready',lambda:dict(launcher_id='launcher-old'))
    with pytest.raises(ValueError,match='NATIVE_LAUNCHER_UPDATE_REQUIRED'):app.start('/explicit/U04')
    assert list((registry/'inbox').iterdir())==[]

@pytest.mark.parametrize('path',['relative','/absolute/../escape'])
def test_invalid_predecessor_never_submitted(registry,path):
    with pytest.raises(ValueError,match='ABSOLUTE_PATH'):app.start(path)
    assert list((registry/'inbox').iterdir())==[]

def test_client_is_file_only_and_request_bound(registry):
    result=app.start('/explicit/U04');rid=result['request_id'];value=json.loads((registry/'inbox'/f'{rid}.json').read_bytes())
    assert value==dict(action='u05_continuation',launcher_id='launcher-test',u04_job='/explicit/U04')
    assert result['human_or_agent_observations']==0 and result['audit_mode']=='TWO_FRESH_MACHINE_EVALUATIONS_PER_GATE'
    assert app.status(rid)['status']=='NATIVE_WORK_IN_PROGRESS'
    publish(registry/'replies'/f'{rid}.json',encode(dict(status='HALTED',launcher_id='other',request_id=rid)))
    with pytest.raises(ValueError,match='RESPONSE_CHANGED'):app.status(rid)

def test_launcher_runs_identical_terminal_entry_and_stops_gracefully(registry,monkeypatch):
    calls=[]
    class Process:
        pid=123
        def poll(self):return None
        def send_signal(self,signal):calls.append(('signal',signal))
        def wait(self,timeout):calls.append(('wait',timeout))
    def popen(argv,**kw):calls.append((argv,kw));return Process()
    monkeypatch.setattr(app.subprocess,'Popen',popen)
    host=app.Continuations(Path('/checkout'),registry,'launcher-test');rid='u05-test';folder=registry/'calls'/rid;folder.mkdir()
    request=dict(action='u05_continuation',launcher_id='launcher-test',u04_job='/explicit/U04');publish(folder/'request.json',encode(request));host.start(rid,folder,request)
    argv=calls[0][0]
    assert argv[:4]==['/checkout/.venv/bin/python','-B','/checkout/tools/pcb_u05_board_run.py','--u04-job']
    assert '--machine-evaluate' not in argv and '--reference' not in argv
    assert calls[0][1]['start_new_session']
    host.tick();assert json.loads((folder/'status.json').read_bytes())['status']=='NATIVE_WORK_IN_PROGRESS'
    monkeypatch.setattr(host,'tick',lambda:None);host.close();assert calls[-2][0]=='signal' and calls[-1]==('wait',30)

def complete_job(registry):
    job=registry.parent/'managed/jobs/native';job.mkdir(parents=True)
    operations=json.loads((Path(__file__).resolve().parents[1]/'contracts/operator/u05_board.json').read_bytes())['operations'];accepted=[]
    files={}
    for i,op in enumerate(operations,1):
        folder=job/'audits'/f'{i:03d}';folder.mkdir(parents=True)
        proof=encode(dict(status='PASS'));publish(folder/'proof.json',proof)
        publish(folder/'evaluations.json',encode(dict(workers=[dict(pid=100+i*2,exit_code=0),dict(pid=101+i*2,exit_code=0)])))
        accepted.append(dict(operation=op,proof=f'{i:03d}/proof.json',proof_sha256=app.jobs.digest(proof)))
    files={str(p.relative_to(job)):app.jobs.digest(p.read_bytes()) for p in job.rglob('*') if p.is_file()}
    cp=encode(dict(operations=operations,accepted=accepted,files=files));publish(job/'U05_CHECKPOINT.json',cp)
    publish(job/'U05_RECEIPT.json',encode(dict(status='PASS_U05_RETAINED_CONTINUATION_EXPORT',job=str(job),checkpoint_sha256=app.jobs.digest(cp),new_native_gates=len(operations),machine_audits=len(operations),human_or_agent_observations=0)))
    publish(job/'U05_REPORT.md',b'Owner PENDING_USER; no rendering.');return job

def test_delivery_requires_full_native_checkpoint_and_both_evaluations(registry):
    job=complete_job(registry);assert app.delivery(job)['ready_markdown']=='Owner PENDING_USER; no rendering.'
    (job/'audits/001/proof.json').write_bytes(b'{}')
    with pytest.raises(ValueError,match='ARTIFACT_CHANGED'):app.delivery(job)

def test_delivery_rejects_added_or_missing_evidence(registry):
    job=complete_job(registry);(job/'extra.json').write_bytes(b'{}')
    with pytest.raises(ValueError,match='FILE_SET_CHANGED'):app.delivery(job)

def test_launcher_capability_and_legacy_routes_remain_present():
    root=Path(__file__).resolve().parents[1]
    source=(root/'tools/t01_crop_launcher.py').read_text()
    assert "u05_board='native-u05/1'" in source and "u04_board='native-u04/1'" in source
    assert 'u04_directory_intake' in source and 'u03_directory_intake' in source
    # The embedded facade imports no kernel/process module.
    import ast
    tree=ast.parse((root/'tools/pcb_u05_board_operator.py').read_text())
    imports=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert not any(n.startswith('src.') for n in imports)
