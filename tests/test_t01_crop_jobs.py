"""Job lifecycle: preserve old evidence, allocate fresh inputs, never bypass a gate."""
import hashlib
import os
from pathlib import Path
import pytest
from tools import t01_crop_jobs as jobs
from tools.t01_route_client import encode, publish
REAL_LAUNCHER_READY=jobs.launcher_ready


@pytest.fixture
def registry(tmp_path,monkeypatch):
    monkeypatch.setattr(jobs,'ROOT',tmp_path)
    monkeypatch.setattr(jobs,'MANAGED',tmp_path/'out/managed')
    monkeypatch.setattr(jobs,'implementation',lambda:'code-v1')
    monkeypatch.setattr(jobs,'LAUNCHER',tmp_path/'out/launcher')
    monkeypatch.setattr(jobs,'launcher_ready',lambda:dict(launcher_id='test-host'))
    jobs.MANAGED.mkdir(parents=True)
    return tmp_path


def payload(crop=b'crop'):
    blobs=dict(crop=crop,kicad=b'original native source',gerber=b'original supplied Gerber')
    rows={k:dict(path='/explicit/'+k,sha256=jobs.digest(v),bytes=len(v)) for k,v in blobs.items()}
    return rows,blobs


def complete(job):
    ui=job/'native/operator_ui';ui.mkdir(parents=True)
    publish(ui/'current.json',encode(dict(status='COMPLETE')))


def inventory(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


def test_second_crop_allocates_without_preparing_launcher_and_preserves_completed_job(registry):
    first,row=jobs.allocate(*payload());complete(first);before=inventory(first)
    second,row2=jobs.allocate(*payload(b'new crop'))
    assert first!=second and jobs.current()[0]==second
    assert inventory(first)==before
    assert Path(row2['staged']['crop']).read_bytes()==b'new crop'
    assert not (jobs.MANAGED.parent/'current.json').exists()


def test_explicit_new_trial_after_success_can_use_same_input(registry):
    first,_=jobs.allocate(*payload());complete(first)
    second,_=jobs.allocate(*payload())
    assert first!=second


def test_unfinished_job_cannot_be_replaced(registry):
    job,_=jobs.allocate(*payload());before=inventory(jobs.MANAGED)
    with pytest.raises(ValueError,match='IN_PROGRESS'):jobs.allocate(*payload(b'other'))
    assert before==inventory(jobs.MANAGED)


def test_failure_is_retained_same_bytes_renamed_cannot_retry_other_crop_can_start(registry):
    job,_=jobs.allocate(*payload());jobs.halt(job,'location ambiguous');before=inventory(job)
    rows,blobs=payload();rows['crop']['path']='/renamed.png'
    with pytest.raises(ValueError,match='FAILED_CROP_INPUTS_RETAINED'):jobs.allocate(rows,blobs)
    other,_=jobs.allocate(*payload(b'other crop'))
    assert other!=job and inventory(job)==before


def test_corrected_implementation_gets_new_job_never_resumes_old(registry,monkeypatch):
    job,_=jobs.allocate(*payload());jobs.halt(job,'old implementation failed');before=inventory(job)
    monkeypatch.setattr(jobs,'implementation',lambda:'code-v2')
    newer,_=jobs.allocate(*payload())
    assert newer!=job and inventory(job)==before


def test_only_supplied_unicode_attachment_is_read_no_filename_guessing(registry):
    p=registry/'Screenshot at 10.05.46\u202fPM.png';p.write_bytes(b'actual attachment')
    row,blob=jobs.attachment(str(p))
    assert row['path']==str(p) and blob==b'actual attachment'
    with pytest.raises(FileNotFoundError):jobs.attachment(str(p).replace('\u202f',' '))
    link=registry/'link.png';link.symlink_to(p)
    with pytest.raises(ValueError,match='REGULAR_ATTACHMENT'):jobs.attachment(link)


def test_external_attachment_is_checked_then_staged_inside_output(registry,tmp_path_factory):
    p=tmp_path_factory.mktemp('external')/'actual.png';p.write_bytes(b'external explicit')
    row,blob=jobs.attachment(p);rows,blobs=payload();rows['crop']=row;blobs['crop']=blob
    job,result=jobs.allocate(rows,blobs)
    assert Path(result['staged']['crop']).is_relative_to(job)
    assert p.read_bytes()==Path(result['staged']['crop']).read_bytes()


def test_parallel_command_cannot_enter_registry(registry):
    with jobs.exclusive():
        with pytest.raises(ValueError,match='COMMAND_IN_PROGRESS'):
            with jobs.exclusive():pytest.fail('acquired second lock')


def test_pointer_mutation_and_output_symlink_fail_closed(registry):
    job,row=jobs.allocate(*payload());bad=dict(row,input_sha256='changed');jobs.replace(jobs.MANAGED/'current.json',bad)
    with pytest.raises(ValueError,match='POINTER_CHANGED'):jobs.current()
    link=registry/'out/link';link.symlink_to(job,target_is_directory=True)
    with pytest.raises(ValueError,match='Symlink'):jobs.output(link/'new')


def test_worker_binding_digest_and_stopped_worker_are_checked(registry):
    job,row=jobs.allocate(*payload());native=job/'native';native.mkdir()
    binding=native/'operator_binding.json';publish(binding,b'{}')
    publish(job/'ready.json',encode(dict(session=str(native),pid=os.getpid(),binding_sha256=jobs.digest(b'{}'))))
    publish(job/'launch.json',encode(dict(launcher_id='test-host')))
    publish(job/'worker_status.json',encode(dict(launcher_id='test-host',status='RUNNING',updated_at=jobs.time.time())))
    assert jobs.binding(job)==binding
    publish(native/'adapter_stopped.json',b'{}')
    with pytest.raises(ValueError,match='RUNNER_STOPPED'):jobs.binding(job)
    assert jobs.binding(job,require_live=False)==binding
    binding.write_bytes(b'changed')
    with pytest.raises(ValueError,match='BINDING_CHANGED'):jobs.binding(job,require_live=False)


def test_nonmac_startup_is_retained_failure_no_worker(registry,monkeypatch):
    job,_=jobs.allocate(*payload());monkeypatch.setattr(jobs,'launcher_ready',REAL_LAUNCHER_READY)
    with pytest.raises(ValueError,match='NATIVE_LAUNCHER_REQUIRED'):jobs.launch(job)
    jobs.halt(job,'platform')
    assert jobs.outcome(job)=='HALTED' and not (job/'launch.json').exists()


def test_facade_start_and_review_bootstrap_without_legacy_pointer(registry,monkeypatch,capsys):
    from tools import pcb_t01_operator as facade
    rows,blobs=payload();calls=[]
    monkeypatch.setattr(jobs,'inputs',lambda *args:(rows,blobs))
    def launch(job):
        calls.append(('launch',job));native=job/'native';native.mkdir()
        publish(native/'operator_binding.json',b'{}')
        publish(job/'ready.json',encode(dict(session=str(native),pid=os.getpid(),binding_sha256=jobs.digest(b'{}'))))
        publish(job/'launch.json',encode(dict(launcher_id='test-host')))
        publish(job/'worker_status.json',encode(dict(launcher_id='test-host',status='RUNNING',updated_at=jobs.time.time())))
        return native/'operator_binding.json'
    monkeypatch.setattr(jobs,'launch',launch)
    class Operator:
        def __init__(self,binding):
            self.client=type('Client',(),{'root':binding.parent})()
            self.ui=binding.parent/'operator_ui';self.ui.mkdir(exist_ok=True)
        def start_crop(self,**args):
            calls.append(('submit',args));publish(self.ui/'current.json',encode(dict(status='REVIEW_REQUIRED')))
            return dict(status='REVIEW_REQUIRED',slice=1)
        def review(self,note,reject):
            calls.append(('review',note,reject));return dict(status='REVIEW_REQUIRED',slice=2)
    monkeypatch.setattr(facade,'CropOperator',Operator)
    monkeypatch.setattr(facade.sys,'argv',['operator','start','--crop','actual-path'])
    assert facade.main()==0
    assert 'REVIEW_REQUIRED' in capsys.readouterr().out
    job,_=jobs.current();assert calls[1][1]['crop']==str(job/'inputs/crop.png')
    before=inventory(job)
    assert facade.main()==2 # duplicate start must not halt/mutate the pending job
    assert 'IN_PROGRESS' in capsys.readouterr().out and inventory(job)==before
    monkeypatch.setattr(facade.sys,'argv',['operator','review','a distinct observation'])
    assert facade.main()==0 and calls[-1]==('review','a distinct observation',False)
    assert not (job/'halted.json').exists()
    # Only after terminal completion does a new start launch another job.
    (job/'native/operator_ui/current.json').write_bytes(encode(dict(status='COMPLETE')))
    before=inventory(job)
    monkeypatch.setattr(facade.sys,'argv',['operator','start','--crop','actual-path'])
    assert facade.main()==0 and jobs.current()[0]!=job
    assert inventory(job)==before and len([c for c in calls if c[0]=='launch'])==2


def test_facade_attachment_uses_real_ingestion_before_worker_start(registry,monkeypatch,capsys):
    import json
    from tools import pcb_t01_operator as facade
    contract=registry/'contracts/operator';contract.mkdir(parents=True)
    (contract/'t01_project.json').write_text('{"inputs":{}}')
    for name,blob in [('Screenshot 10.05\u202fPM.png',b'current crop'),('board.kicad_pcb',b'source'),('board.gbr',b'gerber')]:
        (registry/name).write_bytes(blob)
    def launch(job):
        native=job/'native';native.mkdir();return native/'operator_binding.json'
    monkeypatch.setattr(jobs,'launch',launch)
    class Operator:
        def __init__(self,binding):
            self.client=type('Client',(),{'root':binding.parent})()
            self.ui=binding.parent/'operator_ui';self.ui.mkdir()
        def start_crop(self,**args):
            assert Path(args['crop']).read_bytes()==b'current crop'
            return dict(status='REVIEW_REQUIRED',slice=1)
    monkeypatch.setattr(facade,'CropOperator',Operator)
    monkeypatch.setattr(facade.sys,'argv',['operator','start','--attachment','/Desktop/Screenshot 10.05 PM.png','--kicad-attachment','board.kicad_pcb','--gerber-attachment','board.gbr'])
    assert facade.main()==0 and 'REVIEW_REQUIRED' in capsys.readouterr().out
    job,row=jobs.current()
    assert row['inputs']['crop']['ingestion']['original_path_opened'] is False
    assert row['inputs']['crop']['ingestion']['staged_name']=='Screenshot 10.05\u202fPM.png'
    assert not (registry/'Desktop').exists()
