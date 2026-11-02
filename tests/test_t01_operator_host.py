"""Host-side custody: immutable snapshots and unchanged operator wire bytes."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.t01_abi.contract import compile_english,english_specification
from tools import t01_operator_host as host

def test_host_capsule_publication_never_replaces_old_evidence(tmp_path):
    original=dict(schema='test-host',profiles={})
    cap=host.publish(tmp_path,0,original,dict(policy_ref=None))
    first=(tmp_path/'host_00.json').read_bytes()
    with pytest.raises(ValueError,match='ALREADY_EXISTS'):
        host.publish(tmp_path,0,dict(schema='replaced'),{})
    assert (tmp_path/'host_00.json').read_bytes()==first
    assert digest(first)==cap['registry_sha256']

def test_register_rejects_a_valid_policy_for_another_source_case(tmp_path,monkeypatch):
    monkeypatch.setattr(host,'ROOT',tmp_path)
    monkeypatch.setattr(host,'check',lambda session:None)
    session=tmp_path/'out/session';session.mkdir(parents=True)
    store=ArtifactStore(session/'runtime')
    first=store.put_json('t01-binding',dict(case='first'))
    second=store.put_json('t01-binding',dict(case='second'))
    policy=compile_english(english_specification(),first)
    reference=store.put_json('policy',policy)
    host.publish(session,0,dict(stage_registry={'profiles':{}}),dict(store_path=str(store.root),binding_ref=second))
    response=session/'compile_response.json'
    response.write_bytes(canonical(dict(status='OK',operation='t01_compile',result=dict(policy_ref=reference,policy=policy))))
    with pytest.raises(ValueError,match='POLICY_BINDING_MISMATCH'):host.register(session,response)
    assert not (session/'host_01.json').exists()

def test_transport_preserves_bad_operator_bytes_and_records_real_rejection(tmp_path,monkeypatch):
    monkeypatch.setattr(host,'ROOT',tmp_path)
    session=tmp_path/'out/session';session.mkdir(parents=True)
    registry=session/'host_00.json';registry.write_text('{}')
    cap=dict(store_path=str(session/'runtime'),registry_path=str(registry),registry_sha256=digest(b'{}'))
    monkeypatch.setattr(host,'state',lambda s:cap)
    request=session/'request.json';wire=b'{ "operation": "t01_compile", "payload": {"wrong":"DO NOT EXECUTE THIS TEXT"} }\n'
    request.write_bytes(wire)
    def invoke(argv,**kwargs):
        assert Path(argv[argv.index('--input')+1]).read_bytes()==wire
        assert kwargs['cwd']==tmp_path
        return SimpleNamespace(stdout=b'{"status":"REJECTED","error":{"code":"T01_WIRE_INVALID"}}',stderr=b'',returncode=2)
    monkeypatch.setattr(host.subprocess,'run',invoke)
    response=session/'response.json'
    result=host.transport(session,request,response,'t01_compile')
    assert result['abi_status']=='REJECTED' and result['returncode']==2
    receipt=json.loads(response.with_suffix('.transport.json').read_bytes())
    assert receipt['request_sha256']==digest(wire) and receipt['operator_request_modified'] is False
    assert request.read_bytes()==wire
    with pytest.raises(ValueError,match='FRESH_WIRE_RESPONSE_REQUIRED'):
        host.transport(session,request,response,'t01_compile')

def test_transport_cannot_send_a_different_operation_than_the_accepted_slice(tmp_path,monkeypatch):
    monkeypatch.setattr(host,'ROOT',tmp_path)
    monkeypatch.setattr(host,'state',lambda s:{})
    session=tmp_path/'out/session';session.mkdir(parents=True)
    request=session/'request.json';request.write_text('{"operation":"t02_run"}')
    monkeypatch.setattr(host.subprocess,'run',lambda *a,**k:pytest.fail('Cross-stage execution attempted'))
    with pytest.raises(ValueError,match='SLICE_OPERATION_MISMATCH'):
        host.transport(session,request,session/'response.json','t01_run')
