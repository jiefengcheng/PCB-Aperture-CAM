import json
from pathlib import Path

import pytest

from src.large_copper_runner import run,authenticate
from src import copper_pipeline,copper_phase_seal
from src.gerber_u05 import pipeline as p
from test_source_assembly import RAW,outer_rectangle


def framed(tmp_path,nested=False):
    raw=RAW.replace(b'%ADD12C,0.300000*%',b'%ADD12C,0.300000*%\n%ADD13R,1X1*%')
    raw=raw.replace(b'M02*',b'D13*\nX0005000000Y0005000000D03*\nM02*')
    if nested:raw=raw.replace(b'M02*',outer_rectangle(-1000000,11000000)+b'M02*')
    raw=b'G04 '+str(tmp_path).encode()+b'*\n'+raw
    path=tmp_path/'framed.gbr';path.write_bytes(raw);return path,raw


@pytest.mark.parametrize('nested,removed',[(False,4),(True,8)])
def test_existing_enclosure_removal_precedes_copper_discovery(tmp_path,monkeypatch,nested,removed):
    from src import large_copper_runner as runner
    path,raw=framed(tmp_path,nested);real=runner.discover;seen=[]
    def inspect(rows,material,revision,*args):
        assert len(rows)==5
        assert all(r['metadata'].get('aperture_family')!=['C',.1]for r in rows.values())
        seen.append(True);return real(rows,material,revision,*args)
    monkeypatch.setattr(runner,'discover',inspect)
    result=run(path,output=tmp_path/'cleanup');job=Path(result['job'])
    saved,stage,rows,_=authenticate(job)
    assert seen==[True]and path.read_bytes()==(job/'original.gbr').read_bytes()==raw
    binding=json.loads((job/'source.json').read_text());store=p.Store(job/'runtime')
    proof=store.get_json(binding['input_assembly']['proof_ref'],kind='source-assembly-proof')
    assert proof['removed_objects']==removed and proof['retained_objects']==5
    assert proof['raw_source_sha256']==saved['execution_binding']['source_sha256']==p.digest(raw)
    assert proof['assembled_source_sha256']==stage['input_binding']['source_sha256']==saved['source']['sha256']
    assert saved['source']['sha256']!=p.digest(raw)
    assert stage['trim_only_phase']['positive_copper_mm2']==0
    seal=copper_phase_seal.publish(job,tmp_path/'cleanup.output.json')
    assert copper_phase_seal.verify(**seal)['summary']['input_assembly']['removed_objects']==removed
    (job/'original.gbr').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='ASSEMBLY_BINDING_CHANGED'):authenticate(job)
    with pytest.raises(ValueError,match='DEPENDENCY_CHANGED'):copper_phase_seal.verify(**seal)


def test_inner_loop_with_outside_copper_is_retained(tmp_path):
    path,raw=framed(tmp_path)
    raw=raw.replace(b'M02*',b'D12*\nX0020000000Y0020000000D03*\nM02*');path.write_bytes(raw)
    result=run(path,output=tmp_path/'no-confirmed-frame');job=Path(result['job'])
    binding=json.loads((job/'source.json').read_text());proof=p.Store(job/'runtime').get_json(
        binding['input_assembly']['proof_ref'],kind='source-assembly-proof')
    assert proof['removed_objects']==0 and (job/'source.gbr').read_bytes()==raw


def test_joined_t04_and_saved_views_use_assembled_source_and_keep_original_identity(tmp_path):
    path,raw=framed(tmp_path);job=tmp_path/'joined'
    result=copper_pipeline.run(source=path,output=job)
    assert result['status']=='COMPLETED'and result['input_source_sha256']==p.digest(raw)
    assert result['source_sha256']!=result['input_source_sha256']
    assert copper_pipeline.status(job)['status']=='COMPLETED'
    parent=copper_phase_seal.verify(**result['outputs']['large_copper'])
    child=copper_phase_seal.verify(**result['outputs']['t04'])
    assert parent['source_sha256']==child['source_sha256']==result['source_sha256']
    assert parent['occurrence_count']==child['occurrence_count']==5
    assert parent['summary']['input_assembly']['removed_objects']==4
    assert child['summary']['checks']['native_connections']==2
    from src.viewer_abi.copper_pipeline import prepare
    saved=prepare(job)
    assert not saved['geometry_treatment_executed']and saved['copper_color']=='GREY'
    for folder in saved['workspaces'].values():
        assert json.loads((Path(folder)/'phase-navigation.json').read_text())['sourceSHA256']==result['source_sha256']
    assert copper_pipeline.run(source=path)['status']=='DUPLICATE_JOB_RETAINED'
    assert copper_pipeline.run(cleanup_job=parent['job'])['status']=='DUPLICATE_JOB_RETAINED'
