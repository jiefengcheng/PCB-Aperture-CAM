import json
from pathlib import Path

import pytest
from src import copper_pipeline as pipeline,copper_phase_seal as seals
from src.large_copper_runner import run as cleanup
from src.viewer_abi.publisher import digest


def source(tmp_path):
    # The narrow pad-to-pad trace is outside a separate broad copper owner.
    raw=('G04 joined fixture '+digest(str(tmp_path).encode())+'*\n'+'''%FSLAX46Y46*%
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
''').encode()
    path=tmp_path/'source.gbr';path.write_bytes(raw);return path


def test_real_joined_workers_separate_jobs_and_exact_sealed_t04_entry(tmp_path,monkeypatch):
    path=source(tmp_path);before=path.read_bytes();job=tmp_path/'joined'
    result=pipeline.run(source=path,output=job)
    assert result['status']=='COMPLETED'and path.read_bytes()==before
    assert result['workspaces']['large_copper']!=result['workspaces']['t04']
    assert pipeline.status(job)['custody'].startswith('AUTHENTICATED_SAVED_PHASES')
    parent=seals.verify(**result['outputs']['large_copper'],phase='large_copper')
    child=seals.verify(**result['outputs']['t04'],phase='t04')
    assert child['parent']==result['outputs']['large_copper']
    assert child['shared_preparation_key']==parent['shared_preparation_key']
    assert parent['summary']['counts']['corrected']>0
    assert child['output_geometry_sha256']!=parent['output_geometry_sha256']
    saved=json.loads((job/'t04/RESULT.json').read_bytes())
    assert saved['inputs']['cleanup']['seal']==result['outputs']['large_copper']
    assert saved['checks']['native_connections']>0
    assert saved['settings']['maximum_factor']==1.5
    assert not result['export']
    # Saved viewer preparation owns two heads and invokes neither stage.
    from src.viewer_abi.copper_pipeline import prepare
    from src.viewer_abi.publisher import read_current
    import base64
    monkeypatch.setattr('src.large_copper_runner.run',lambda *a,**k:pytest.fail('viewer ran cleanup'))
    monkeypatch.setattr('tools.run_t04_after_cleanup.execute',lambda *a,**k:pytest.fail('viewer ran T04'))
    viewers=prepare(job)
    assert viewers['workspaces']['large_copper']!=viewers['workspaces']['t04']
    assert viewers['copper_color']=='GREY'and not viewers['geometry_treatment_executed']
    assert viewers['native_display']=='PENDING_NATIVE_ACK'
    links=[json.loads((Path(path)/'phase-navigation.json').read_bytes())for path in viewers['workspaces'].values()]
    assert links[0]==links[1]and links[0]['sourceSHA256']==result['source_sha256']
    assert links[0]['pipelineResultSHA256']==digest((job/'RESULT.json').read_bytes())
    for name,destination in links[0]['workspaces'].items():
        assert destination['path']==viewers['workspaces'][name]
        assert destination['snapshotSHA256']==viewers['snapshot_sha256'][name]
        presentation=Path(destination['path'])/'presentations'/(destination['snapshotSHA256']+'.json')
        assert destination['presentationSHA256']==digest(presentation.read_bytes())
    for name in('large_copper','t04'):
        root=Path(viewers['workspaces'][name]);manifest,snapshot=read_current(root)
        envelope=json.loads((root/'presentations'/(manifest['sha256']+'.json')).read_bytes())
        presentation=json.loads(base64.b64decode(envelope['payloadBase64']))
        assert ('t04'in presentation)==(name=='t04')
        assert not (root/'outbox/display.json').exists()
    assert prepare(job)==viewers
    assert pipeline.status(job)['status']=='COMPLETED'
    monkeypatch.setattr(pipeline,'_worker',lambda *a:pytest.fail('duplicate ran a worker'))
    again=pipeline.run(source=path,output=tmp_path/'different')
    assert again['status']=='DUPLICATE_JOB_RETAINED'and not (tmp_path/'different').exists()
    again=pipeline.run(cleanup_job=parent['job'],output=tmp_path/'alternate-entry')
    assert again['status']=='DUPLICATE_JOB_RETAINED'and not (tmp_path/'alternate-entry').exists()
    alias=seals.publish(parent['job'],tmp_path/'same-bytes-other-pin.json')
    with pytest.raises(ValueError,match='PARENT_CHANGED'):
        seals.publish(job/'t04',tmp_path/'wrong-parent.output.json',phase='t04',parent_ref=alias)
    # Altering T04 output cannot contaminate or silently rerun the cleanup.
    (job/'t04/construction.json.gz').write_bytes(b'corrupted output')
    with pytest.raises(ValueError,match='DEPENDENCY_CHANGED'):pipeline.status(job)
    assert seals.verify(**result['outputs']['large_copper'])['phase']=='large_copper'


def test_t04_failure_retains_cleanup_seal_and_never_retries(tmp_path,monkeypatch):
    path=source(tmp_path);cleanup(path,output=tmp_path/'cleanup')
    def failed(*a):raise RuntimeError('deliberate T04 worker failure')
    monkeypatch.setattr(pipeline,'_worker',failed)
    with pytest.raises(RuntimeError,match='deliberate'):pipeline.run(cleanup_job=tmp_path/'cleanup',output=tmp_path/'joined')
    assert (tmp_path/'joined/handoffs/large_copper.output.json').exists()
    assert not (tmp_path/'joined/handoffs/t04.output.json').exists()
    assert pipeline.status(tmp_path/'joined')['status']=='FAILED_RETAINED'
    again=pipeline.run(cleanup_job=tmp_path/'cleanup',output=tmp_path/'other')
    assert again['status']=='DUPLICATE_JOB_RETAINED'
    assert again['retained']['status']=='FAILED_RETAINED'
    assert not (tmp_path/'other').exists()


def test_invalid_seal_prevents_t04_from_creating_a_job(tmp_path):
    from tools.run_t04_after_cleanup import execute
    path=source(tmp_path);cleanup(path,output=tmp_path/'cleanup');ref=seals.publish(tmp_path/'cleanup',tmp_path/'seal.json')
    with pytest.raises(ValueError,match='DIGEST_CHANGED'):
        execute(None,None,tmp_path/'t04',cleanup_seal=dict(ref,sha256='0'*64))
    assert not (tmp_path/'t04').exists()


def test_interrupted_allocation_and_input_workspace_remain_separate(tmp_path):
    interrupted=tmp_path/'interrupted';interrupted.mkdir()
    assert pipeline.status(interrupted)['status']=='INTERRUPTED_RETAINED_NO_AUTOMATIC_RETRY'
    path=source(tmp_path);cleanup(path,output=tmp_path/'cleanup')
    with pytest.raises(ValueError,match='PRODUCER_WORKSPACE_MUST_BE_SEPARATE'):
        pipeline.run(cleanup_job=tmp_path/'cleanup',output=tmp_path/'cleanup/consumer')
    assert not (tmp_path/'cleanup/consumer').exists()


def test_saved_shoulder_comparison_wkb_is_in_sealed_output_closure(tmp_path):
    result=pipeline.run(source=source(tmp_path),output=tmp_path/'joined')
    child=seals.verify(**result['outputs']['t04'],phase='t04')
    report=json.loads((tmp_path/'joined/t04/RESULT.json').read_bytes())
    ref=report['board_outline']['shoulder_baseline_ref']
    name='runtime/artifacts/'+ref['artifact_id']
    assert child['files'][name]==ref['sha256']
    (tmp_path/'joined/t04'/name).write_bytes(b'corrupted comparison image')
    with pytest.raises(ValueError,match='DEPENDENCY_CHANGED'):
        seals.verify(**result['outputs']['t04'],phase='t04')
    assert seals.verify(**result['outputs']['large_copper'])['phase']=='large_copper'
