import copy
import gzip
import json
from pathlib import Path
import pytest
from src.gerber_u05 import group_stage, group_board_job as job


def test_board_selection_has_no_bounded_route_limit_and_accounts_for_keeps():
    admitted=[dict(path_id=f'r{i:04}')for i in range(1524)]
    native=dict(admitted=admitted,paths=[dict(path=p,disposition='ADMIT_COMPLETE_GERBER_ROUTE')for p in admitted]+
                [dict(path=dict(path_id='covered'),disposition='KEEP_FULLY_COVERED')])
    selected,ledger=group_stage.native_board_selection(native)
    assert selected==[p['path_id']for p in admitted]and len(ledger)==1525
    assert ledger[-1]==('covered','KEEP_FULLY_COVERED')


@pytest.mark.parametrize('change',['unknown','missing','duplicate','empty'])
def test_board_selection_never_silently_omits_native_paths(change):
    p=dict(path_id='r');native=dict(admitted=[p],paths=[dict(path=p,disposition='ADMIT_COMPLETE_GERBER_ROUTE')])
    if change=='unknown':native['paths'][0]['disposition']='NOT_QUALIFIED'
    elif change=='missing':native['admitted']=[]
    elif change=='duplicate':native['admitted'].append(p)
    else:native=dict(admitted=[],paths=[])
    with pytest.raises(ValueError,match='NATIVE_INVENTORY'):
        group_stage.native_board_selection(native)


def stage():
    return dict(publication_ready=False,output_scene_ref=None,
        hybrid_components=dict(reference_checks=dict(passed=True),functional_checks=dict(passed=True),
            bulk=dict(error=None),joint_connections=dict(reports=[dict(passed=True)]),
            corner_smoothing=dict(pocket_completion=dict(passed=True),unresolved=2),
            frozen_endpoint_obligations=dict(passed=False,failures=['retained obligation']),
            constructed_groups_audited=0,constructed_group_bytes_preserved=True,covered_trace_copper_preserved=True))


@pytest.mark.parametrize('field',['reference_checks','functional_checks','bulk','joint_connections','corner_smoothing',
                                 'constructed_groups_audited','constructed_group_bytes_preserved','covered_trace_copper_preserved'])
def test_existing_failure_dispositions_stop_board_diagnostic(field):
    q=stage();h=q['hybrid_components']
    if field in('reference_checks','functional_checks'):h[field]['passed']=False
    elif field=='bulk':h[field]['error']='reserved corridor conflict'
    elif field=='joint_connections':h[field]['reports'][0]['passed']=False
    elif field=='corner_smoothing':h[field]['pocket_completion']['passed']=False
    elif field=='constructed_groups_audited':h[field]=1
    else:h[field]=False
    with pytest.raises(ValueError,match='COMPONENT_FAILURE'):job.checked(q)


def test_pending_endpoint_work_stays_explicit_and_does_not_claim_completion():
    q=job.checked(stage())
    assert not q['frozen_endpoint_obligations']['passed']and q['constructed_groups_audited']==0


def test_streamed_stage_matches_exact_canonical_bytes_and_is_exclusive(tmp_path):
    q=stage();q['unicode']='铜';q['values']=[.25,-0.,1.5]
    receipt=job.write_stage(tmp_path/'stage.gz',q)
    raw=gzip.decompress((tmp_path/'stage.gz').read_bytes())
    assert raw==job.p.canonical(q)and job.p.digest(raw)==receipt['stage_sha256']
    with pytest.raises(FileExistsError):job.write_stage(tmp_path/'stage.gz',q)


def test_readiness_cannot_use_old_checked_profile_or_changed_code(tmp_path,monkeypatch):
    monkeypatch.setattr(job.intake,'source_inventory',lambda:{'src/current.py':'a'})
    path=tmp_path/'ready.json'
    path.write_text(json.dumps(dict(schema=job.SCHEMA,status='READY_FOR_BOARD_CONSTRUCTION_DIAGNOSTIC',source_files={},inputs={})))
    with pytest.raises(ValueError,match='CODE_OR_INPUT_CHANGED'):job.require(path,{})


def test_readiness_tests_must_bind_the_current_code_not_only_a_success_log(tmp_path,monkeypatch):
    code={'src/current.py':'a'};monkeypatch.setattr(job.intake,'source_inventory',lambda:code)
    log=tmp_path/'tests.log';log.write_text('passed')
    ready=dict(schema=job.SCHEMA,status='READY_FOR_BOARD_CONSTRUCTION_DIAGNOSTIC',source_files=code,inputs={},
               tests=dict(source_files={},exit_code=0,log=str(log),log_sha256=job.file_sha(log)))
    path=tmp_path/'ready.json';path.write_text(json.dumps(ready))
    with pytest.raises(ValueError,match='TESTS_CHANGED'):job.require(path,{})
    value=json.loads(path.read_bytes());value['source_files']={'src/current.py':'a'};value['status']='QUALIFIED_T04_SOURCE_BUILT_PROFILE_ENTRY'
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='CODE_OR_INPUT_CHANGED'):job.require(path,{})


def test_failure_inputs_are_retained_without_reexecuting_the_operation(tmp_path):
    from shapely import to_wkb
    from shapely.geometry import box
    from shapely.errors import GEOSException
    calls=[]
    def face_cut():
        support=box(0,0,1,1);window=box(.2,.2,.8,.8)
        calls.append(1);raise GEOSException('native overlay failure')
    try:face_cut()
    except GEOSException as error:receipt=job.failure_operands(error,tmp_path)
    saved=json.loads(Path(receipt['path']).read_bytes())
    operand=saved['frames'][0]['operands']['support']
    assert Path(operand['path']).read_bytes()==to_wkb(box(0,0,1,1),include_srid=True)
    assert job.file_sha(operand['path'])==operand['sha256']and calls==[1]
