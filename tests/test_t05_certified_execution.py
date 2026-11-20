"""Actual adapter integration, deterministic worker projection and corruption."""
from copy import deepcopy
import pytest
from shapely import from_wkb, to_wkb
from shapely.geometry import box
from tests.test_u05_attachments import fixture
from src.stage_abi.loaded_geometry import GeometrySnapshot
from src.stage_abi.store import canonical
from src.t05_certified_execution import MEMO_BYTES


def prepared(tmp_path):
    store,scene,policy,plan,adapter=fixture(tmp_path)
    adapter.close()
    adapter.enable_certificate_consumption()
    plan['details']=adapter.plan(store,scene,policy,dict(stage='t05',scene_ref=plan['scene_ref'],source_ids=['view']),plan['details']['bounds'])
    plan['implementation']=adapter.describe()['implementation']
    return store,scene,policy,plan,adapter


def test_real_source_adapter_consumes_without_replaying_geometry(tmp_path,monkeypatch):
    store,scene,policy,plan,a=prepared(tmp_path)
    value=a.run(store,scene,policy,plan,lambda _:None)
    assert value['coverage']['grown']==1
    assert a.geometry_budgets['memo_bytes']==MEMO_BYTES
    for method in ('_operands','_blend_addition','needs','outcomes','_check','execution'):
        monkeypatch.setattr(a,method,lambda *_:pytest.fail('old verification path'))
    monkeypatch.setattr(GeometrySnapshot,'composed',lambda *_:pytest.fail('second composition'))
    proof=a.verify(store,scene,policy,plan,value,dict(scope='complete-source-and-all-patches'),lambda _:None)
    assert proof['passed'] and proof['reconstructed_patches']==1
    assert a._certificate_run.ledger.counts['complete_replays']==2
    assert a._certificate_run.ledger.counts['consumed']==2
    assert store.get_json(a._certificate_run.audit_ref)['stage']['counts']['verifications']==1


def test_two_fresh_authorities_produce_identical_canonical_stage_values(tmp_path):
    records=[];authorities=[]
    for name in ('construct','1','2'):
        store,scene,policy,plan,a=prepared(tmp_path/name)
        candidate=a.run(store,scene,policy,plan,lambda _:None)
        proof=a.verify(store,scene,policy,plan,candidate,dict(scope='complete-source-and-all-patches'),lambda _:None)
        records.append(canonical(dict(candidate=candidate,verification=proof)))
        authorities.append(a._certificate_run.seal_ref)
    assert records[0]==records[1]==records[2]
    assert len({r['sha256']for r in authorities})==3


@pytest.mark.parametrize('change',['scene','policy','plan','patch','output','scope','store'])
def test_actual_adapter_rejects_changed_inputs_and_extra_copper(tmp_path,change):
    store,scene,policy,plan,a=prepared(tmp_path)
    candidate=a.run(store,scene,policy,plan,lambda _:None)
    if change=='scene':scene['objects'][0]['metadata']['changed']=True
    elif change=='policy':policy['parameters']['hard_gap_mm']=.000001
    elif change=='plan':plan['implementation']='changed'
    elif change=='patch':candidate['decisions'][0]['patch_ref']=store.put('geometry',to_wkb(box(4,4,5,5)))
    elif change=='output':candidate['after_ref']=store.put('geometry',to_wkb(box(-3,-3,3,3)))
    elif change=='scope':a.write=box(-4,-4,4,4)
    elif change=='store':
        ref=candidate['after_ref'];(store.root/'artifacts'/ref['artifact_id']).write_bytes(b'corrupt')
    with pytest.raises(ValueError):a.verify(store,scene,policy,plan,candidate,dict(scope='complete-source-and-all-patches'),lambda _:None)


def test_geometry_matches_existing_source_constructor_and_checker(tmp_path):
    normal=fixture(tmp_path/'normal');cert=prepared(tmp_path/'certified');shapes=[]
    for store,scene,policy,plan,a in (normal,cert):
        candidate=a.run(store,scene,policy,plan,lambda _:None)
        proof=a.verify(store,scene,policy,plan,candidate,dict(scope='complete-source-and-all-patches'),lambda _:None)
        assert proof['passed']
        shapes.append((store.get(candidate['after_ref'],kind='geometry'),candidate['decisions']))
    assert shapes[0]==shapes[1]


def test_option_requires_planning_boundary_and_fresh_issuance(tmp_path):
    store,scene,policy,plan,a=fixture(tmp_path)
    with pytest.raises(ValueError,match='PRECEDE_PLANNING'):a.enable_certificate_consumption()
    a.close();a.enable_certificate_consumption()
    with pytest.raises(ValueError,match='FRESH_CERTIFIED'):a.verify(store,scene,policy,plan,{},dict(scope='complete-source-and-all-patches'),lambda _:None)


def test_independent_fresh_processes_agree_without_portable_hmac_keys(tmp_path):
    import json,subprocess,sys
    from pathlib import Path
    code='''
import hashlib,json,sys
from pathlib import Path
from tests.test_t05_certified_execution import prepared
from src.stage_abi.store import canonical
store,scene,policy,plan,a=prepared(Path(sys.argv[1]))
candidate=a.run(store,scene,policy,plan,lambda _:None)
proof=a.verify(store,scene,policy,plan,candidate,dict(scope='complete-source-and-all-patches'),lambda _:None)
print(json.dumps(dict(stage_sha256=hashlib.sha256(canonical(dict(candidate=candidate,verification=proof))).hexdigest(),seal=a._certificate_run.seal_ref)))
'''
    results=[]
    for mode in ('construct','1','2'):
        job=subprocess.run([sys.executable,'-B','-c',code,str(tmp_path/mode)],check=True,text=True,capture_output=True)
        results.append(json.loads(job.stdout))
    assert len({r['stage_sha256']for r in results})==1
    assert len({r['seal']['sha256']for r in results})==3


def test_owner_exempt_prior_copper_still_reaches_global_safety_issuer(tmp_path):
    from types import SimpleNamespace
    from src.gerber_u05.pipeline import Store
    from src.stage_abi.loaded_geometry import GeometryMemo
    from src.t05_certified_execution import CertifiedExecution
    from src.u05_board.junctions import parameters
    store=Store(tmp_path/'runtime');seen=[]
    def physical(owner,candidate,addition,window,foreign):
        seen.append([sid for sid,_ in foreign])
        blocked=any(addition.intersects(shape)for _,shape in foreign)
        return dict(passed=not blocked,failures=['GLOBAL_PIN_MATERIAL']if blocked else[])
    adapter=SimpleNamespace(describe=lambda:dict(implementation='test'),_scope_binding=lambda:'test',
        geometry_budgets={},_geometry=GeometryMemo('test',limit=1024**2),
        _foreign_for=lambda owner,foreign:[],_certificate_region=lambda addition:addition,_check=physical)
    execution=CertifiedExecution(adapter,store,{},dict(parameters=parameters()),{})
    owner=box(0,0,1,1);patch=box(1,.2,1.2,.8);window=box(-1,-1,3,3)
    assert execution.proposal(dict(source_id='A'),owner,patch,window,[])['passed']
    receipt,_=execution.pending['A'];reference=receipt['body']['patch_ref']
    execution.ledger.commit(receipt,'A',reference,owner,window)
    # Existing clearance owner policy excludes A. The physical issuer must
    # nevertheless receive it for global pin/other material predicates.
    assert not execution.proposal(dict(source_id='B'),owner,patch,window,[])['passed']
    assert seen==[[],['A']]
