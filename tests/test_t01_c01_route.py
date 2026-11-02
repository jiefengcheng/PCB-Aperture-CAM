"""Plan authority and slice gates over actual successful response fixtures.

Native CLI outcomes are injected here; the separate live Local Code trial must
establish execution. No constructor is executed; these are response fixtures.
"""
import copy
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import pytest
from tools import t01_c01_route as workflow
from tools import t01_operator_host as host
from tools.t01_native_route import RouteError, native_identity
from tools.t01_route_client import Client
from tools.t01_macos_adapter import MacOSAdapter

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'out/crop_dynamic_tasks/t01_local_code_c01_ref_20261031_300'
FIXTURES=['slice_1/compile_response.json','slice_2a/discover_response.json','slice_2b/inspect_response.json','slice_3/plan_response.json','slice_4/run_response.json','slice_5/verify_response.json','slice_6a/compare_response.json','slice_6b/review_response.json','slice_7/negative_compile_response.json']

@pytest.fixture
def route(tmp_path,monkeypatch):
    monkeypatch.setattr(workflow,'check',lambda session:None)
    monkeypatch.setattr(host,'local',lambda p:p)
    r=workflow.C01Route.__new__(workflow.C01Route)
    r.session=tmp_path;r.identity=native_identity();r.route_id='test-route'
    r.lock=threading.RLock();r.receipt_hashes={};r.audit_hashes={}
    r.cap=json.loads((OLD/'capsule_00.json').read_bytes())
    r.contract=json.loads((ROOT/'contracts/t01/c01_route.json').read_bytes())
    r.operations=r.contract['operations'];r.position=0;r.pending=None;r.responses={};r.accepted=[]
    r.negative=dict(artifact_id='english-spec:'+'1'*64,sha256='1'*64)
    (tmp_path/'attempts').mkdir();(tmp_path/'audits').mkdir();(tmp_path/'START.json').write_text('{}')
    fixtures={name:json.loads((OLD/path).read_bytes()) for name,path in zip(r.operations,FIXTURES)}
    r.grants=[]
    def register(session,path):
        return dict(r.cap,capsule_revision=1,policy_ref=fixtures['t01_compile']['result']['policy_ref'])
    def grant(session,path):
        r.grants.append(path)
        return json.loads((OLD/'capsule_02.json').read_bytes())
    monkeypatch.setattr(workflow,'register',register);monkeypatch.setattr(workflow,'grant',grant)
    def runner(argv,**kwargs):
        req=json.loads(Path(argv[argv.index('--input')+1]).read_bytes())
        name=req['operation']
        if name=='t01_compile' and req['payload']['english_ref']==r.negative:name='t01_negative_compile'
        response=copy.deepcopy(fixtures[name]);response.update(request_id=req['request_id'],operation=req['operation'])
        return SimpleNamespace(stdout=json.dumps(response).encode(),stderr=b'',returncode=2 if name=='t01_negative_compile' else 0)
    r.runner=runner
    return r


def call(r,op,attempt=None):
    return r.call(op,dict(route_id=r.route_id,attempt_id=attempt or op),dict(name='LocalCode'))


def audit(r,**changes):
    p=r.pending
    a=dict(p['result']['audit_required']);a['note']='Observed actual response and scope.';a.update(changes)
    return r.call('native_route.audit',dict(route_id=r.route_id,attempt_id=p['attempt_id'],audit=a),dict(name='LocalCode'))


def through(r,op):
    while r.position<=r.operations.index(op):
        step=r.operations[r.position]
        result=call(r,step)
        assert result['error'] is None,result
        audit(r)


def test_all_nine_steps_need_separate_actual_response_audits(route):
    through(route,'t01_negative_compile')
    assert route.info()['status']=='COMPLETE_AUDITED_SEQUENCE_ORACLE_PENDING'
    assert len(route.accepted)==9 and len(route.grants)==1
    assert len(list((route.session/'attempts').glob('*/abi/execution.json')))==9
    facts=json.loads((route.session/'attempts/t01_compare/result.json').read_bytes())['result']['facts']
    assert facts['selected_records']==51 and facts['changed_sources']==42 and facts['unchanged_sources']==9


def test_next_step_rejected_until_operator_audits_actual_result(route):
    assert call(route,'t01_compile')['error'] is None
    with pytest.raises(RouteError,match='Audit current result'):
        call(route,'t01_discover')
    assert route.position==0 and route.grants==[]


@pytest.mark.parametrize('operation',['t01_run','t01_verify','t01_plan'])
def test_cannot_skip_to_construction_or_grant(route,operation):
    with pytest.raises(RouteError):call(route,operation)
    assert not list((route.session/'attempts').iterdir()) and route.grants==[]


@pytest.mark.parametrize('changes',[
    dict(verdict='FAIL'),dict(response_sha256='0'*64),dict(observed={}),dict(note=''),dict(owner_acceptance='PASS')])
def test_audit_mismatch_retained_and_cannot_advance(route,changes):
    call(route,'t01_compile')
    with pytest.raises((RouteError,ValueError)):audit(route,**changes)
    assert route.position==0 and route.cap['capsule_revision']==0
    decision=list((route.session/'audits').glob('*/decision.json'))
    assert len(decision)==1 and json.loads(decision[0].read_bytes())['status']=='FAIL'


def test_only_audited_exact_plan_gets_native_authority(route):
    through(route,'t01_inspect')
    call(route,'t01_plan')
    assert route.cap['capsule_revision']==1 and route.grants==[]
    audit(route)
    assert route.cap['capsule_revision']==2 and len(route.grants)==1
    request=json.loads((route.session/'attempts/t01_plan/abi/request.json').read_bytes())
    assert request['plan_ref'] is None and request['authorization_ref'] is None
    request=route._request_for('t01_run','run')
    assert request['plan_ref']==route.cap['plan_ref'] and request['authorization_ref']==route.cap['authorization_ref']


def test_tampered_plan_response_prevents_authority_even_with_original_observations(route):
    through(route,'t01_inspect');call(route,'t01_plan')
    (route.session/'attempts/t01_plan/abi/stdout.json').write_bytes(b'{}')
    with pytest.raises(RouteError):audit(route)
    assert route.grants==[] and route.position==3


def test_changed_accepted_audit_prevents_next_native_operation(route):
    through(route,'t01_compile')
    path=next((route.session/'audits').glob('*/decision.json'));path.write_bytes(b'{}')
    result=call(route,'t01_discover')
    assert result['error']['code']=='AUDIT_RECEIPT_CHANGED'
    assert not (route.session/'attempts/t01_discover/abi').exists()


def test_reused_attempt_cannot_overwrite_prior_evidence(route):
    result=call(route,'t01_compile','fixed');audit(route)
    before=Path(result['receipt_path']).read_bytes()
    with pytest.raises(RouteError,match='Never overwrite'):call(route,'t01_discover','fixed')
    assert Path(result['receipt_path']).read_bytes()==before


def test_machine_checks_do_not_accept_positive_job_with_failed_geometry(route):
    through(route,'t01_plan')
    original=route.runner
    def failed(argv,**kwargs):
        outcome=original(argv,**kwargs);r=json.loads(outcome.stdout)
        r['result']['result']['candidate']['final_checks'][0]['check']['passed']=False
        return SimpleNamespace(stdout=json.dumps(r).encode(),stderr=b'',returncode=0)
    route.runner=failed
    result=call(route,'t01_run')
    assert result['error']['code']=='C01_OPERATION_CHECK_FAILED' and route.pending is None


def test_wrong_response_identity_is_rejected(route):
    original=route.runner
    def wrong(argv,**kwargs):
        outcome=original(argv,**kwargs);r=json.loads(outcome.stdout);r['request_id']='different'
        return SimpleNamespace(stdout=json.dumps(r).encode(),stderr=b'',returncode=0)
    route.runner=wrong
    assert call(route,'t01_compile')['error']['code']=='ABI_RESPONSE_CORRELATION_FAILED'


def test_c01_operations_use_same_mac_adapter_and_stdlib_client(route):
    adapter=MacOSAdapter(route);client=Client(route.session/'agent_setup.json','LocalCode')
    rid=client.submit('t01_compile',dict(route_id=route.route_id,attempt_id='mac-compile'))
    adapter.drain();output=client.receive(rid)
    assert output['result']['facts']['clauses']==15 and route.pending['attempt_id']=='mac-compile'
    assert 't01_run' in {t['name'] for t in client.setup['tools']}
