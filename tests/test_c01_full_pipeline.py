"""Handoff isolation and deliberate mutations; fake receipts are not native proof."""
import copy
import json
from pathlib import Path
import threading
import pytest
from src.c01_pipeline import bindings as b
from src.stage_abi.store import canonical, digest
from tools.t01_c01_full_route import C01FullRoute
from tools.t01_native_route import RouteError

def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(value))

def fake_sequence(root, operations):
    for n,operation in enumerate(operations):
        attempt=f'slice-{n+1}';p=root/'attempts'/attempt
        put(p/'abi/stdout.json',dict(status='OK',result=dict(facts=dict(passed=True))))
        facts=dict(passed=True,operation=operation)
        put(p/'result.json',dict(result=dict(facts=facts),error=None))
        put(p/'receipt.json',dict(tool=operation,attempt_id=attempt,status='PASS',
            completed_at=f'2026-11-01T00:00:{n:02d}+00:00',
            files={str(q.relative_to(p)):digest(q.read_bytes()) for q in p.rglob('*') if q.is_file() and q.name!='receipt.json'}))
        put(root/'audits'/attempt/'request.json',dict(arguments=dict(attempt_id=attempt,
            audit=dict(verdict='PASS',response_sha256=digest((p/'abi/stdout.json').read_bytes()),observed=facts,note='Test fixture only.'))))
        put(root/'audits'/attempt/'decision.json',dict(status='PASS_SLICE_OBSERVATION_AUDIT',accepted_operation=operation))

def data_host(root):
    fake_sequence(root,(*b.T01,b.ORACLE))
    put(root/'RECEIPT.json',dict(test_fixture_only=True))
    proof=b.checkpoint(root,'T01_CHECKPOINT.json',(*b.T01,b.ORACLE),[root/'RECEIPT.json'])
    c=b.read(b.ROOT/'contracts/t01/c01_files.json')
    return dict(schema='pcb-c01-file-host/2',predecessor=str(root),
        predecessor_receipt_sha256=digest((root/'RECEIPT.json').read_bytes()),
        source_sha256=c['source_sha256'],edit_sha256=c['edit_sha256'],
        edit_reference=str(b.ROOT/'dataset/szu-comm_3020301113B_intake_ready_20261021_v1/raw/EDIT/top_layer.kicad_pcb'),
        output=str(root/'data_output'),authority=c['authority'],**proof)

def render_host(root):
    fake_sequence(root,(*b.T01,b.ORACLE,*b.FILES))
    paths=dict(kicad=root/'data_output/candidate/board.kicad_pcb',gerber=root/'data_output/candidate/gerbers/board-F_Cu.gbr')
    for p in paths.values():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fake data, not geometry proof')
    proof=b.checkpoint(root,'EXPORT_CHECKPOINT.json',(*b.T01,b.ORACLE,*b.FILES),list(paths.values()))
    contract=b.read(b.ROOT/'contracts/render/c01.json')
    contract['inputs']={k:dict(path=str(p.relative_to(b.ROOT)),sha256=digest(p.read_bytes())) for k,p in paths.items()}
    put(root/'pipeline_render_contract.json',contract)
    return dict(schema='pcb-c01-render-host/2',contract_path=str(root/'pipeline_render_contract.json'),
        contract_sha256=digest((root/'pipeline_render_contract.json').read_bytes()),output=str(root/'render_output'),**proof)

@pytest.mark.parametrize('mutation',['missing_audit','changed_note_facts','changed_raw','missing_receipt','failed_decision'])
def test_handoff_rejects_broken_native_observation_chain(tmp_path,mutation):
    host=data_host(tmp_path)
    if mutation=='missing_audit':(tmp_path/'audits/slice-3/request.json').unlink()
    elif mutation=='changed_note_facts':
        p=tmp_path/'audits/slice-3/request.json';v=b.read(p);v['arguments']['audit']['observed']={};put(p,v)
    elif mutation=='changed_raw':(tmp_path/'attempts/slice-3/abi/stdout.json').write_bytes(b'changed')
    elif mutation=='missing_receipt':(tmp_path/'attempts/slice-3/receipt.json').unlink()
    else:put(tmp_path/'audits/slice-3/decision.json',dict(status='FAIL'))
    with pytest.raises((ValueError,FileNotFoundError)):b.validate_data_host(host)

@pytest.mark.parametrize('mutation',['old_predecessor','wrong_output','different_source','missing_receipt_binding'])
def test_data_handoff_cannot_reuse_historical_or_wrong_source(tmp_path,mutation):
    host=data_host(tmp_path)
    assert b.validate_data_host(host)==tmp_path
    if mutation=='old_predecessor':host['predecessor']=str(b.ROOT/'out/crop_dynamic_tasks/t01_c01_macos_recovery_20261031_305/run')
    elif mutation=='wrong_output':host['output']=str(tmp_path/'elsewhere')
    elif mutation=='different_source':host['source_sha256']='0'*64
    else:host['predecessor_receipt_sha256']='0'*64
    with pytest.raises(ValueError):b.validate_data_host(host)

def test_predecessor_checkpoint_survives_later_accepted_slices(tmp_path):
    host=data_host(tmp_path)
    # A later complete sequence must not make the earlier handoff stale.
    fake_sequence(tmp_path,(*b.T01,b.ORACLE,*b.FILES))
    assert b.validate_data_host(host)==tmp_path

@pytest.mark.parametrize('mutation',['bounds','tolerance','old_input','changed_file','symlink','missing_export_audit'])
def test_render_handoff_keeps_policy_and_binds_current_verified_exports(tmp_path,mutation):
    host=render_host(tmp_path)
    assert b.validate_render_host(host)==tmp_path/'pipeline_render_contract.json'
    if mutation in ('bounds','tolerance','old_input'):
        p=tmp_path/'pipeline_render_contract.json';c=b.read(p)
        if mutation=='bounds':c['bounds_mm'][0]+=.01
        elif mutation=='tolerance':c['raster_boundary_error_mm']['gerber']=1
        else:c['inputs']=b.read(b.ROOT/'contracts/render/c01.json')['inputs']
        put(p,c);host['contract_sha256']=digest(p.read_bytes())
    elif mutation=='changed_file':(tmp_path/'data_output/candidate/board.kicad_pcb').write_bytes(b'changed')
    elif mutation=='symlink':
        p=tmp_path/'data_output/candidate/board.kicad_pcb';blob=p.read_bytes();p.unlink();(tmp_path/'copy').write_bytes(blob);p.symlink_to(tmp_path/'copy')
    else:(tmp_path/'audits/slice-15/request.json').unlink()
    with pytest.raises((ValueError,FileNotFoundError)):b.validate_render_host(host)

def test_incomplete_t01_cannot_create_export_checkpoint(tmp_path):
    fake_sequence(tmp_path,b.T01[:4])
    with pytest.raises(ValueError,match='SEQUENCE_INCOMPLETE'):
        b.checkpoint(tmp_path,'T01_CHECKPOINT.json',(*b.T01,b.ORACLE),[])
    assert not (tmp_path/'T01_CHECKPOINT.json').exists()

def test_full_profile_has_only_bound_operations_and_blocks_later_stages():
    route=C01FullRoute.__new__(C01FullRoute);route.operations=list(b.STEPS);route.lock=threading.RLock()
    assert {t['name'] for t in route.tools()}=={*b.STEPS,'native_route.info','native_route.verify_receipt','native_route.audit'}
    for name in ['t02_run','t03_run','t04_run','t05_run','native_route.conformance','t01_describe']:
        with pytest.raises(RouteError,match=name):route.call(name,{}, {})

def test_full_facade_rejects_render_only_descriptor():
    from tools.pcb_c01_full_operator import FullOperator
    op=FullOperator.__new__(FullOperator)
    with pytest.raises(ValueError,match='BOUND_FULL_C01_PROFILE_REQUIRED'):
        op.validate_tools({*b.RENDER,'native_route.info','native_route.audit','native_route.verify_receipt'})


@pytest.mark.parametrize('mutation',['priority','contour_bytes'])
def test_postconstruction_oracle_rejects_changed_semantics_or_contour(tmp_path,monkeypatch,mutation):
    from tools import pcb_c01_reproduction_check as oracle
    from src.stage_abi.store import ArtifactStore
    previous=b.ROOT/'out/crop_dynamic_tasks/t01_c01_macos_recovery_20261031_305/run'
    receipt=b.read(previous/'RECEIPT.json');store=ArtifactStore(previous/'runtime')
    candidate=copy.deepcopy(store.get_json(receipt['candidate_ref'],kind='candidate'))
    if mutation=='priority':candidate['decisions'][0]['priority']=not candidate['decisions'][0]['priority']
    class ChangedRead:
        def get_json(self,ref,*,kind):
            return candidate if kind=='candidate' else store.get_json(ref,kind=kind)
        def get(self,ref,*,kind):
            return b'changed contour' if mutation=='contour_bytes' and ref==candidate['decisions'][0]['candidate_ref'] else store.get(ref,kind=kind)
    put(tmp_path/'capsule_02.json',b.read(previous/'capsule_02.json'))
    monkeypatch.setattr(oracle,'ArtifactStore',lambda path:ChangedRead())
    monkeypatch.setattr(oracle,'check',lambda path:dict(status='TEST_STUB_CUSTODY'))
    monkeypatch.setattr(oracle,'accepted',lambda root,ops:dict(
        t01_run=dict(result=dict(result=dict(candidate_ref=receipt['candidate_ref']))),
        t01_verify=dict(result=dict(result=dict(verification_ref=receipt['verification_ref'])))))
    with pytest.raises(ValueError,match='C01_FROZEN_REPRODUCTION_MISMATCH'):
        oracle.reproduce_check(tmp_path)
    assert not (tmp_path/'RECEIPT.json').exists()


def test_oracle_does_not_read_frozen_contours_before_nine_observations(tmp_path,monkeypatch):
    from tools import pcb_c01_reproduction_check as oracle
    monkeypatch.setattr(oracle,'check',lambda root:None)
    def unavailable(*args):raise ValueError('C01_PIPELINE_SEQUENCE_INCOMPLETE')
    monkeypatch.setattr(oracle,'accepted',unavailable)
    monkeypatch.setattr(oracle,'read',lambda path:pytest.fail('Must not read frozen contours or capsule before accepted sequence'))
    with pytest.raises(ValueError,match='C01_PIPELINE_SEQUENCE_INCOMPLETE'):
        oracle.reproduce_check(tmp_path)
