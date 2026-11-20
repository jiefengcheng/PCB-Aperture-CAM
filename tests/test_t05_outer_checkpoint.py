"""Actual source-kernel CLI qualification; historical receipts below are fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.stage_abi.store import canonical
from tools import t05_certified_checkpoint as checkpoint


def prefix_fixture(tmp_path,monkeypatch):
    # build() executes the genuine tiny source parser/constructor/checker. Only
    # the synthetic predecessor-custody records are authored in this fixture.
    from tests.test_t05_outer_acceptance import build
    run,store,value,packet,signer,expected,capture,timing=build(tmp_path/'prior',monkeypatch)
    for stage in('t01','t03'):
        (run/(stage+'.json')).write_bytes(canonical(dict(output_scene_ref=value['plan']['scene_ref'])))
    from src.gerber_u05.pin_policy import capture as capture_pin
    capture_pin(run,dict(selected='top.art.gbr',files={'top.art.gbr':expected['source_sha256']}))
    # These are synthetic custody records, not a second live producer seal.
    producer_path=run/'PRODUCER_BINDING.json';record=json.loads(producer_path.read_bytes())
    record['job_inputs'][str(run/'PIN_SEPARATION_POLICY.json')]=checkpoint.sha((run/'PIN_SEPARATION_POLICY.json').read_bytes())
    producer_path.write_bytes(canonical(record))
    producer=checkpoint.sha((run/'PRODUCER_BINDING.json').read_bytes());named={}
    for stage in checkpoint.STAGES:
        named[stage]=producer
        for mode in checkpoint.MODES:
            path=run/'audits'/stage/(mode+'.json');path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(canonical(dict(status='PASS',stage=stage,
                candidate_sha256=checkpoint.sha((run/(stage+'.json')).read_bytes()),
                producer_binding_sha256=producer,source_sha256=expected['source_sha256'])))
    plan=dict(producer_binding_sha256=producer,custody=dict(retained_stage_producers={s:named[s]for s in('t01','t03','t04')},source_sha256=expected['source_sha256']))
    job=run.parent;checkpoint.save(job/'RUN_PLAN.json',plan)
    (job/'RUN_PLAN.sha256').write_text(checkpoint.sha((job/'RUN_PLAN.json').read_bytes())+'\n')
    checkpoint.save(job/'EXECUTION_STARTED.json',dict(plan_sha256=checkpoint.sha((job/'RUN_PLAN.json').read_bytes())))
    checkpoint.save(job/'RESULT.json',dict(status='PASS',proofs_match=True))
    checkpoint.save(job/'OUTER_TIMING.json',dict(returncode=0))
    return run,checkpoint.sha((run/'t04.json').read_bytes())


def test_prepare_binds_old_receipts_without_starting_or_copying_old_t05(tmp_path,monkeypatch):
    from tools import pcb_workspace
    monkeypatch.setattr(pcb_workspace,'require_storage',lambda:tmp_path)
    prefix,h=prefix_fixture(tmp_path,monkeypatch)
    from src.gerber_u05 import worker
    monkeypatch.setattr(worker,'compute',lambda *_:pytest.fail('prepare ran a stage'))
    plan=checkpoint.prepare(prefix,h,parent=tmp_path/'fresh')
    job=Path(plan['job']);run=Path(plan['run'])
    assert not(run/'t05.json').exists()and not(job/'EXECUTION_STARTED.json').exists()
    assert plan['profile']['reconstruction_workers']==0 and plan['profile']['reference_arms']==0
    assert checkpoint.check_job(job)[0]==plan
    (run/'t02.json').write_bytes(b'changed')
    with pytest.raises(ValueError):checkpoint.check_job(job)


@pytest.mark.parametrize('change',['receipt','plan','source','assembly_option'])
def test_prefix_corruptions_stop_before_new_run(tmp_path,monkeypatch,change):
    from tools import pcb_workspace
    monkeypatch.setattr(pcb_workspace,'require_storage',lambda:tmp_path)
    prefix,h=prefix_fixture(tmp_path,monkeypatch)
    path={'receipt':prefix/'audits/t02/2.json','plan':prefix.parent/'RUN_PLAN.json',
        'source':prefix/'source_snapshot/top.art.gbr','assembly_option':prefix/'PIN_SEPARATION_POLICY.json'}[change]
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises((ValueError,AssertionError)):checkpoint.retained_custody(prefix,h)


def test_full_cli_one_actual_source_constructor_two_public_only_readers(tmp_path,monkeypatch):
    # No client-board/reference arm. Uses the same real public-only CLI that the
    # full-board job launches; both readers forbid construction via cProfile.
    from tools import pcb_workspace
    monkeypatch.setattr(pcb_workspace,'require_storage',lambda:tmp_path)
    prefix,h=prefix_fixture(tmp_path,monkeypatch)
    plan=checkpoint.prepare(prefix,h,parent=tmp_path/'fresh');job=Path(plan['job'])
    code=checkpoint.measure(job)
    assert code==0,(job/'RUN.log').read_text()
    result=checkpoint.read(job/'RESULT.json');outer=checkpoint.read(job/'OUTER_TIMING.json')
    assert result['status']=='PASS'and result['full_rebuilds']==0 and result['reference_arms']==0
    assert outer['returncode']==0 and result['summary']['grown']>0
    for proof in result['public_readers']:
        assert proof['counts']['local_containments']==result['summary']['grown']
        assert not proof['forbidden_call_records']and proof['physical_checks_repeated']==0
    before=checkpoint.read(job/'OUTER_CERTIFICATE.json')
    second=subprocess.run([sys.executable,'-B',str(Path(checkpoint.__file__)),'--execute',str(job)],capture_output=True,text=True)
    assert second.returncode and 'FileExistsError'in second.stderr
    assert checkpoint.read(job/'OUTER_CERTIFICATE.json')==before
