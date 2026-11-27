import json
import sys
from pathlib import Path
import pytest

from src import copper_pipeline
from tools import run_copper_pipeline as cli


def fixture(tmp_path):
    path=tmp_path/'fresh.gbr'
    path.write_text('G04 viewer execution '+str(tmp_path)+'*\n'+'''%FSLAX46Y46*%
%MOMM*%
%IPPOS*%
%ADD10R,4X4*%
%ADD11C,0.0508*%
%ADD12C,0.2*%
%LPD*%
D10*
X2000000Y2000000D03*
D12*
X0Y6000000D03*
X1000000Y6000000D03*
D11*
X10000Y2000000D02*
X2000000Y2000000D01*
X0Y6000000D02*
X1000000Y6000000D01*
M02*
''')
    return path


def test_viewer_command_runs_both_workers_then_prepares_linked_views(tmp_path,monkeypatch,capsys):
    source=fixture(tmp_path);original=source.read_bytes();job=tmp_path/'joined'
    monkeypatch.setattr(sys,'argv',['run_copper_pipeline','run','--source',str(source),'--output',str(job),'--prepare-display'])
    assert cli.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='COMPLETED'and source.read_bytes()==original
    paths=result['display']['workspaces']
    assert paths['large_copper']!=paths['t04']
    assert result['display']['geometry_treatment_executed']is False
    assert result['display']['copper_color']=='GREY'
    assert copper_pipeline.status(job)['status']=='COMPLETED'
    # Reopening the same successfully completed execution does not rerun either worker.
    monkeypatch.setattr(copper_pipeline,'_worker',lambda *a:(_ for _ in ()).throw(AssertionError('duplicate treatment')))
    assert cli.main()==0
    reused=json.loads(capsys.readouterr().out)
    assert reused['status']=='DUPLICATE_JOB_RETAINED'
    assert reused['display']==result['display']


def test_failed_consumer_cannot_publish_a_linked_success_or_retry(tmp_path,monkeypatch,capsys):
    from src.large_copper_runner import run
    source=fixture(tmp_path);producer=tmp_path/'cleanup';run(source,output=producer)
    capsys.readouterr()
    job=tmp_path/'joined'
    monkeypatch.setattr(copper_pipeline,'_worker',lambda *a:(_ for _ in ()).throw(ValueError('deliberate consumer failure')))
    monkeypatch.setattr(sys,'argv',['run_copper_pipeline','run','--cleanup-job',str(producer),'--output',str(job),'--prepare-display'])
    assert cli.main()==1
    assert 'deliberate consumer failure'in capsys.readouterr().err
    assert (job/'handoffs/large_copper.output.json').exists()
    assert not (job/'VIEWERS.json').exists()
    assert cli.main()==1
    assert 'RETAINED_JOB_NOT_COMPLETED'in capsys.readouterr().err
    assert copper_pipeline.status(job)['status']=='FAILED_RETAINED'


def test_t04_durable_cache_uses_verified_work_folder_and_rejects_escape(tmp_path,monkeypatch):
    from src import cleanup_runtime
    from src.gerber_u05.durable_groups import retain
    work=tmp_path/'explicit-work';work.mkdir()
    monkeypatch.setattr(cleanup_runtime,'workspace_root',lambda:work)
    value,binding,hit=retain(work/'source_artifacts/eligibility',{'source':'fixed'},'DATA.json.gz',lambda:{'kept':['one']})
    assert value=={'kept':['one']}and not hit
    assert retain(work/'source_artifacts/eligibility',{'source':'fixed'},'DATA.json.gz',lambda:pytest.fail('rebuilt cache'))[2]
    outside=tmp_path/'outside';outside.mkdir();(work/'escape').symlink_to(outside,target_is_directory=True)
    for destination in [work,work/'escape/cache',outside/'cache']:
        with pytest.raises(ValueError,match='REQUIRES_LACIE'):
            retain(destination,{'source':'fixed'},'DATA.json.gz',lambda:pytest.fail('escaped construction'))


def test_failed_display_can_have_a_fresh_derivative_without_treatment(tmp_path,monkeypatch):
    from src.viewer_abi import copper_pipeline as display,t04_workspace
    source=fixture(tmp_path);job=tmp_path/'joined-display';copper_pipeline.run(source=source,output=job)
    result=(job/'RESULT.json').read_bytes();real=t04_workspace.publish
    def fail(*a,**k):raise ValueError('DELIBERATE_DISPLAY_FAILURE')
    monkeypatch.setattr(t04_workspace,'publish',fail)
    with pytest.raises(ValueError,match='DELIBERATE_DISPLAY_FAILURE'):display.prepare(job)
    failure=(job/'VIEWERS_FAILED.json').read_bytes()
    monkeypatch.setattr(t04_workspace,'publish',real)
    monkeypatch.setattr(copper_pipeline,'_worker',lambda *a,**k:pytest.fail('duplicate treatment'))
    with pytest.raises(ValueError,match='PIPELINE_VIEWER_FAILURE_RETAINED'):display.prepare(job)
    destination=tmp_path/'display-derivative';saved=display.prepare(job,output=destination)
    assert saved['separate_display_derivative']and not saved['geometry_treatment_executed']
    assert (destination/'VIEWERS.json').exists()
    assert (job/'RESULT.json').read_bytes()==result and (job/'VIEWERS_FAILED.json').read_bytes()==failure
    assert Path(saved['workspaces']['t04']).is_relative_to(destination)
    with pytest.raises(ValueError,match='FRESH_DISPLAY_DERIVATIVE_DIRECTORY_REQUIRED'):
        display.prepare(job,output=destination)
