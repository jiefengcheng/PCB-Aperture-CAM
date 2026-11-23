import fcntl
import gzip
import json
from pathlib import Path

import pytest

from src.large_copper_runner import run, authenticate, publish_saved, status, ROOT, digest


def gerber(y=2):
    return ('''G04 independent cleanup fixture*
%FSLAX46Y46*%
%MOMM*%
%IPPOS*%
%ADD10R,4X4*%
%ADD11C,0.0508*%
%LPD*%
D10*
X2000000Y2000000D03*
D11*
X10000Y'''+str(round(y*1000000))+'''D02*
X2000000Y'''+str(round(y*1000000))+'''D01*
M02*
''').encode()


def source(tmp_path,raw=None):
    path=tmp_path/'input.gbr';path.write_bytes(raw or gerber())
    return path


@pytest.fixture(autouse=True)
def isolated_identity(monkeypatch,tmp_path):
    # Keep real parser, native geometry, storage checks and publication. A
    # per-test implementation salt isolates durable duplicate-job receipts.
    from src import large_copper_runner as runner
    actual=runner.implementation
    monkeypatch.setattr(runner,'implementation',lambda:dict(actual(),test_identity=str(tmp_path)))


def test_explicit_source_complete_trim_saved_custody_and_display(tmp_path):
    path=source(tmp_path)
    result=run(path,output=tmp_path/'job')
    assert result['counts']==dict(corrected=1,unresolved=0,ignored=0)
    value,stage,rows,original=authenticate(result['job'])
    assert stage['trim_only_phase']['positive_copper_mm2']==0
    assert stage['batch_proof']['actual_removed_mm2']>0
    assert len(rows)==2 and path.read_bytes()==gerber()
    display=publish_saved(result['job'])
    assert display['status']=='PENDING_NATIVE_ACK'
    assert status(result['job'])['display']['status']=='PENDING_NATIVE_ACK'
    from src.viewer_abi.publisher import read_current
    _,snapshot=read_current(Path(display['workspace']))
    assert snapshot['revision']==display['revision']
    assert all(o['kind'] in ('source','removed') for o in snapshot['objects'])
    assert run(path)['status']=='DUPLICATE_JOB_RETAINED'


def test_unsupported_source_retains_failure_and_cannot_rerun(tmp_path):
    path=source(tmp_path,b'unsupported source')
    with pytest.raises(ValueError):run(path,output=tmp_path/'failed')
    failure=json.loads((tmp_path/'failed/FAILED.json').read_bytes())
    assert failure['remaining']=='NOT_RUN'
    again=run(path)
    assert again['status']=='DUPLICATE_JOB_RETAINED' and again['retained']['status']=='FAILED_RETAINED'


def test_source_duplicate_lock_covers_other_outputs(tmp_path):
    path=source(tmp_path)
    lock=ROOT/'out/lacie_work/large_copper_jobs/locks'/(digest(path.read_bytes())+'.lock')
    lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('a+b') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError,match='DUPLICATE_SOURCE_JOB_ACTIVE'):
            run(path,output=tmp_path/'different')
    assert not (tmp_path/'different').exists()


@pytest.mark.parametrize('target',['construction.json.gz','source.gbr','source.json'])
def test_corruption_cannot_publish_and_remains_retained(tmp_path,target):
    result=run(source(tmp_path),output=tmp_path/'job')
    path=tmp_path/'job'/target;path.write_bytes(b'corrupt')
    with pytest.raises((ValueError,json.JSONDecodeError),match='CHANGED|Expecting'):
        publish_saved(result['job'])
    assert path.read_bytes()==b'corrupt' and not (tmp_path/'job/viewer/current.json').exists()


def test_native_artifact_corruption_rejects_publication(tmp_path):
    result=run(source(tmp_path),output=tmp_path/'job')
    _,stage,rows,_=authenticate(result['job'])
    reference=next(iter(rows.values()))['original_ref']
    path=tmp_path/'job/runtime/artifacts'/reference['artifact_id']
    path.write_bytes(b'bad')
    with pytest.raises(Exception):publish_saved(result['job'])
    assert not (tmp_path/'job/viewer/current.json').exists()


def test_no_change_broad_source_has_grey_inspectable_saved_objects(tmp_path):
    raw=gerber().replace(b'X10000Y2000000',b'X1000000Y2000000')
    result=run(source(tmp_path,raw),output=tmp_path/'job')
    assert not any(result['counts'].values())
    display=publish_saved(result['job'])
    from src.viewer_abi.publisher import read_current
    _,snapshot=read_current(Path(display['workspace']))
    assert snapshot['objects'] and all(o['kind']=='source' for o in snapshot['objects'])


def test_explicit_absolute_source_and_external_output_required(tmp_path):
    with pytest.raises(ValueError,match='ABSOLUTE_SOURCE'):run(Path('input.gbr'))
    with pytest.raises(ValueError,match='LACIE_OUTPUT'):run(source(tmp_path),output=ROOT/'out/forbidden_cleanup')


def test_missing_source_retains_errno_and_stops(tmp_path):
    with pytest.raises(ValueError,match='SOURCE_INTAKE_FAILED'):
        run(tmp_path/'missing.gbr',output=tmp_path/'failed')
    failure=json.loads((tmp_path/'failed/FAILED.json').read_bytes())
    assert failure['errno']==2 and failure['remaining']=='NOT_RUN'


def test_mask_source_is_rejected_not_treated_as_copper(tmp_path):
    raw=gerber().replace(b'%IPPOS*%',b'%IPPOS*%\n%TF.FileFunction,Soldermask,Top*%\n%TF.FilePolarity,Negative*%')
    with pytest.raises(ValueError,match='POSITIVE_COPPER_SURFACE'):
        run(source(tmp_path,raw),output=tmp_path/'failed')
    assert (tmp_path/'failed/FAILED.json').exists()


def test_crashed_worker_is_retained_and_duplicate_does_not_restart(tmp_path):
    import subprocess,sys
    raw=gerber(y=2.137).replace(b'G04 independent cleanup fixture*',
        b'G04 crash test '+digest(str(tmp_path).encode()).encode()+b'*')
    path=source(tmp_path,raw)
    job=tmp_path/'crashed'
    code='''import os,sys
from src.large_copper_runner import run
def stop(**event):
 if event['phase']=='preparation':os._exit(73)
run(sys.argv[1],output=sys.argv[2],progress_callback=stop)
'''
    child=subprocess.run([sys.executable,'-B','-c',code,str(path),str(job)],cwd=ROOT)
    assert child.returncode==73
    assert status(job)['status']=='INTERRUPTED_RETAINED_NO_AUTOMATIC_RETRY'
    # A fresh process uses the same production implementation binding and must
    # return that interrupted receipt instead of starting another job.
    result=subprocess.run([sys.executable,'-B',str(ROOT/'tools/run_large_copper.py'),'run','--source',str(path)],
                          cwd=ROOT,capture_output=True,text=True,check=True)
    answer=json.loads(result.stdout)
    assert answer['status']=='DUPLICATE_JOB_RETAINED'
    assert answer['retained']['status']=='INTERRUPTED_RETAINED_NO_AUTOMATIC_RETRY'
    assert not (job/'RESULT.json').exists()


def test_interrupted_display_never_commits_and_cannot_be_retried(tmp_path,monkeypatch):
    from src import large_copper_runner as runner
    result=run(source(tmp_path),output=tmp_path/'job')
    write=runner.atomic_write
    def interrupted(path,raw):
        if Path(path).name=='current.json':raise OSError('simulated publication interruption')
        return write(path,raw)
    monkeypatch.setattr(runner,'atomic_write',interrupted)
    with pytest.raises(OSError):publish_saved(result['job'])
    assert not (tmp_path/'job/viewer/current.json').exists()
    assert (tmp_path/'job/DISPLAY_FAILED.json').exists()
    with pytest.raises(ValueError,match='DISPLAY_FAILURE_RETAINED'):publish_saved(result['job'])


def test_stale_native_ack_cannot_acknowledge_current_saved_result(tmp_path):
    result=run(source(tmp_path),output=tmp_path/'job')
    display=publish_saved(result['job'])
    out=Path(display['workspace'])/'outbox';out.mkdir()
    (out/'display.json').write_text(json.dumps(dict(status='DISPLAY_DOM_UPDATED',revision='stale',
        payloadSHA256=display['snapshot_sha256'],presentation='BULK_COPPER_CLEANUP')))
    assert status(result['job'])['display']['status']=='PENDING_NATIVE_ACK'


def test_new_display_revision_retains_previous_session_and_geometry(tmp_path):
    result=run(source(tmp_path),output=tmp_path/'job')
    first=publish_saved(result['job'])
    original_receipt=(tmp_path/'job/DISPLAY.json').read_bytes()
    stage=(tmp_path/'job/construction.json.gz').read_bytes()
    second=publish_saved(result['job'],new_revision=True)
    assert first['revision']!=second['revision'] and first['workspace']!=second['workspace']
    assert (Path(first['workspace'])/'current.json').exists()
    assert (tmp_path/'job/DISPLAY.json').read_bytes()==original_receipt
    assert (tmp_path/'job/construction.json.gz').read_bytes()==stage
    assert status(result['job'])['display']['revision']==second['revision']
