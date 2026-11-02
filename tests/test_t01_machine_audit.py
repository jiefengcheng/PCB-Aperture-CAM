"""Automatic audits derive their verdict from retained native evidence."""
from pathlib import Path
import json,copy,pytest
from tools.t01_route_client import encode,publish
from src.stage_abi.store import digest
from src.pcb_data_abi.machine_audit import evaluate,proof_note,MODE,STEPS


def negative_attempt(tmp_path,*,code=2,error='T01_ENGLISH_UNSUPPORTED',request_id='attempt-one'):
    root=tmp_path/'native';p=root/'attempts/attempt-one';(p/'abi').mkdir(parents=True)
    request=dict(abi_version='stage-agent-abi/1.0',request_id='attempt-one',operation='t01_compile')
    response=dict(request,request_id=request_id,status='REJECTED',result=None,error=dict(code=error))
    data={'abi/request.json':request,'abi/stdout.json':response,'abi/completed.json':dict(returncode=code),'result.json':dict(error=None,result=dict(operation='t01_negative_compile',raw_response_sha256=digest(encode(response))))}
    for name,value in data.items():publish(p/name,encode(value))
    publish(p/'receipt.json',encode(dict(tool='t01_negative_compile',attempt_id='attempt-one',files={name:digest((p/name).read_bytes())for name in data})))
    return root,p


def test_actual_negative_response_is_verified_without_any_observation(tmp_path):
    root,p=negative_attempt(tmp_path);proof=evaluate(root,'attempt-one')
    assert proof['status']=='PASS'and proof['mode']==MODE and len(proof['checks'])>=9
    assert proof['human_or_agent_observation']=='NOT_RUN'and proof['owner']=='PENDING_USER'
    assert not list(root.rglob('review-*.json'))
    assert 'Agent observation'not in proof_note(digest(encode(proof)))

@pytest.mark.parametrize('field,value',[('code',0),('error','UNRELATED_ERROR'),('request_id','another-request')])
def test_success_text_cannot_hide_wrong_native_exit_error_or_correlation(tmp_path,field,value):
    root,p=negative_attempt(tmp_path,**{field:value});proof=evaluate(root,'attempt-one')
    assert proof['status']=='FAIL'and any(not q['passed']for q in proof['checks'])


def test_receipt_tampering_rejects_before_audit(tmp_path):
    root,p=negative_attempt(tmp_path);(p/'abi/stdout.json').write_bytes(b'{}')
    with pytest.raises(Exception)as error:evaluate(root,'attempt-one')
    assert error.value.code=='RECEIPT_HASH_MISMATCH'


def test_automatic_contract_retains_exact_export_only_sequence():
    root=Path(__file__).resolve().parents[1];auto=json.loads((root/'contracts/operator/t01_board_auto.json').read_bytes());manual=json.loads((root/'contracts/operator/t01_board_export.json').read_bytes())
    assert auto['sequence']==manual['operations']==list(STEPS)and len(STEPS)==18
    assert all(not name.startswith(('render','t02','t03','t04','t05'))for name in STEPS)


def test_route_recomputes_proof_and_rejects_forged_pass(tmp_path,monkeypatch):
    from tools import t01_board_auto_route as module
    root=tmp_path/'native';folder=root/'audits/machine-001';folder.mkdir(parents=True)
    actual=dict(status='FAIL',checks=[dict(passed=False)])
    forged=dict(status='PASS',checks=[dict(passed=True)])
    publish(folder/'proof.json',encode(forged));route=module.MachineRoute.__new__(module.MachineRoute);route.session=root;route.position=0;route.pending=dict(attempt_id='one');route.halted=False
    route._valid_args=lambda *a,**k:None;monkeypatch.setattr(module,'evaluate',lambda *a:actual)
    def forbidden(*a,**k):pytest.fail('Rejected proof must never advance the native gate')
    monkeypatch.setattr(module.ExportOnlyRoute,'_audit',forbidden)
    with pytest.raises(ValueError,match='PROOF_INVALID'):route._audit(dict(attempt_id='one',audit=dict(note=proof_note(digest(encode(forged))))),{})
    assert route.halted


def test_generic_success_note_cannot_replace_a_valid_proof_reference(tmp_path,monkeypatch):
    from tools import t01_board_auto_route as module
    root=tmp_path/'native';folder=root/'audits/machine-001';folder.mkdir(parents=True);proof=dict(status='PASS',checks=[dict(passed=True)]);publish(folder/'proof.json',encode(proof))
    route=module.MachineRoute.__new__(module.MachineRoute);route.session=root;route.position=0;route.pending=dict(attempt_id='one');route.halted=False;route._valid_args=lambda *a,**k:None;monkeypatch.setattr(module,'evaluate',lambda *a:proof)
    with pytest.raises(ValueError,match='PROOF_REFERENCE_INVALID'):route._audit(dict(attempt_id='one',audit=dict(note='Everything passed. Continue.')),{})
