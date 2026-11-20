"""Checkpoint preparation never invokes a board-growth computation."""
import json
from pathlib import Path
import pytest
from shapely import to_wkb
from shapely.geometry import box
from src.stage_abi.store import ArtifactStore,canonical,digest
from tools import t02_t05_checkpoint as checkpoint


def retained(tmp_path):
    prefix=tmp_path/'old'/'legacy';store=ArtifactStore(prefix/'runtime')
    raw=b'%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.1*%\n%LPD*%\nD10*\nX0Y0D03*\nM02*\n'
    source_ref=store.put('gerber-source',raw)
    geom=store.put('geometry',to_wkb(box(0,0,1,1)))
    scene=dict(source_sha256=source_ref['sha256'],frame='test',units='mm',layer='F.Cu',viewport_mm=[-1,-1,2,2],
        findings=[],lineage=[],acceptance={},objects=[dict(source_id='source',kind='fixed_source',geometry_ref=geom,original_ref=geom,metadata={})])
    def write(name,data):
        path=prefix/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(data));return digest(path.read_bytes())
    write('source.json',dict(source_ref=source_ref))
    (prefix/'source_snapshot').mkdir();(prefix/'source_snapshot/top.art.gbr').write_bytes(raw)
    write('LEGACY_REFERENCE_JOB.json',dict(schema='fresh-legacy-reservation-reference/1'))
    write('input_inventory.json',dict(input_directory='fixture'))
    write('PIN_SEPARATION_POLICY.json',dict(declaration=None,working_source_sha256=source_ref['sha256']))
    producer=write('PRODUCER_BINDING.json',dict(source_binding_sha256=checkpoint.sha(prefix/'source.json')))
    stage_ref=store.put_json('scene',scene)
    for stage in ['t01','t03','t04']:
        sha=write(stage+'.json',dict(output_scene_ref=stage_ref))
        for mode in checkpoint.MODES:
            write(f'audits/{stage}/{mode}.json',dict(status='PASS',stage=stage,candidate_sha256=sha,
                producer_binding_sha256=producer,source_sha256=source_ref['sha256']))
    return prefix,sha


def test_readonly_audit_binds_exact_stage_proofs_source_and_undeclared_pins(tmp_path):
    prefix,sha=retained(tmp_path)
    before={str(q):q.read_bytes()for q in prefix.rglob('*')if q.is_file()}
    result=checkpoint.audit_prefix(prefix,sha)
    assert result['pin_intent']=='UNDECLARED'and result['status']=='PASS_RETAINED_LEGACY_CUSTODY'
    assert before=={str(q):q.read_bytes()for q in prefix.rglob('*')if q.is_file()}
    with pytest.raises(ValueError,match='CHECKPOINT_HASH'):checkpoint.audit_prefix(prefix,'0'*64)
    q=prefix/'audits/t04/2.json';d=json.loads(q.read_bytes());d['producer_binding_sha256']='changed';q.write_bytes(canonical(d))
    with pytest.raises(ValueError,match='PROOF_CHANGED'):checkpoint.audit_prefix(prefix,sha)


def test_prepare_and_preflight_never_execute_stages(tmp_path,monkeypatch):
    from tools import pcb_workspace
    from src.gerber_u05 import worker
    monkeypatch.setattr(pcb_workspace,'require_storage',lambda:tmp_path)
    monkeypatch.setattr(worker,'compute',lambda *_:pytest.fail('growth executed during preparation'))
    prefix,sha=retained(tmp_path)
    plan=checkpoint.prepare(prefix,sha,parent=tmp_path/'prepared')
    assert plan['status']=='PREPARED_NOT_EXECUTED'and plan['full_board_execution']=='NOT_STARTED'
    assert plan['shared_performance']and plan['t05_certificates']
    run=checkpoint.check_job(plan)
    assert not(run/'t02.json').exists()and not(run/'t05.json').exists()
    assert not(Path(plan['job'])/'EXECUTION_STARTED.json').exists()
    assert checkpoint.audit_prefix(prefix,sha)['pin_intent']=='UNDECLARED'
    q=run/'t04.json';q.write_bytes(q.read_bytes()+b' ')
    with pytest.raises(ValueError,match='CUSTODY_CHANGED'):checkpoint.check_job(plan)
