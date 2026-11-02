"""Report completion retains FAIL/NOT_RUN and never calls a renderer or runner."""
import json,sys
from pathlib import Path
import pytest
from tools import t01_board_completion as c
from tools.t01_route_client import encode


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value if isinstance(value,bytes)else encode(value));return c.sha(path.read_bytes())


@pytest.fixture
def job(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'ROOT',tmp_path);j=tmp_path/'out/job';r=j/'native';out=r/'render_output';board=r/'data_output/candidate/board.kicad_pcb';gerber=r/'data_output/candidate/gerbers/board-F_Cu.gbr'
    bh=put(board,b'verified native candidate');gh=put(gerber,b'verified F.Cu');put(j/'inputs/kicad',b'source');put(j/'inputs/gerber',b'source gerber')
    put(j/'job.json',dict(task_scope='full-board',job=str(j),inputs=dict(kicad=dict(sha256=c.sha(b'source')),gerber=dict(sha256=c.sha(b'source gerber'))),staged=dict(kicad=str(j/'inputs/kicad'),gerber=str(j/'inputs/gerber'))))
    put(j/'halted.json',dict(status='HALTED'));put(r/'adapter_stopped.json',dict(status='STOPPED'));put(r/'START.json',dict(historical_producer='preserved'));put(r/'DECISION_POLICY.json',dict(operations=c.STEPS))
    put(r/'T01_CHECKPOINT.json',{});scope_hash=put(r/'data_board/verified.json',dict(facts=dict(complete_source_coverage=True)));put(r/'RECEIPT.json',dict(status='PASS_BOARD_T01_VERIFIED',scope_sha256=scope_hash))
    for name in ['pcb_gerber_export','pcb_gerber_verify','pcb_export_controls']:put(r/f'data_output/{name}.json',{})
    required=['RECEIPT.json','data_board/verified.json','T01_CHECKPOINT.json','data_output/pcb_gerber_export.json','data_output/pcb_gerber_verify.json','data_output/pcb_export_controls.json','data_output/candidate/board.kicad_pcb','data_output/candidate/gerbers/board-F_Cu.gbr']
    checkpoint=put(r/'EXPORT_CHECKPOINT.json',dict(operations=c.STEPS[:18],files={name:c.sha((r/name).read_bytes())for name in required}))
    tiles=[dict(id='tile-'+str(i),bounds_mm=[i,0,i+1,1],pixels=[2,2])for i in range(3)];plan=dict(tiles=tiles);put(out/'tile_plan.json',plan)
    for tile in tiles:
        for name in ['kicad','gerber']:put(out/'tiles'/tile['id']/(name+'.png'),b'retained native image')
    put(out/'comparison.png',b'retained overview')
    contract=put(r/'pipeline_render_contract.json',dict(tiles=plan,raster_boundary_error_mm=dict(kicad=.001,gerber=.005)))
    host=put(r/'pipeline_render_host.json',dict(schema='pcb-board-render-host/1',checkpoint=str(r/'EXPORT_CHECKPOINT.json'),checkpoint_sha256=checkpoint,contract_path=str(r/'pipeline_render_contract.json'),contract_sha256=contract,output=str(out)))
    render=dict(facts=dict(passed=True,complete_board_coverage=True,geometry_edited=False),input_files=dict(kicad=dict(path=str(board),sha256=bh),gerber=dict(path=str(gerber),sha256=gh)),files={str(p.relative_to(out)):c.sha(p.read_bytes())for p in out.rglob('*')if p.is_file()});put(out/'render.json',render)
    for i,op in enumerate(c.STEPS[:20],1):
        folder=r/'attempts'/str(i);facts=dict(passed=True);response=dict(facts=facts)
        if op=='board_candidate_check':facts.update(complete_source_coverage=True,full_reconstruction_passed=True,protected_sources_unchanged=True,canonical_sites=2,aliases=3)
        if op=='pcb_kicad_write':response.update(board=str(board),board_sha256=bh)
        if op=='pcb_gerber_export':response.update(output_sha256={str(gerber):gh})
        if op=='pcb_gerber_verify':facts.update(protected_fcu_atoms_equal=True,protected_other_layers=8)
        if op=='render_compare':response=render;facts=render['facts']
        if i<20:
            raw=dict(result=response,status='OK',error=None);put(folder/'result.json',dict(error=None,result=dict(facts=facts)));rh=put(folder/'abi/stdout.json',raw)
            observation='Observed distinct gate '+str(i);note_hash=c.sha(observation.encode());audit=dict(verdict='PASS',observed=facts,response_sha256=rh,note=note_hash)
            put(r/f'audits/{i}/request.json',dict(arguments=dict(attempt_id=str(i),audit=audit)));put(r/f'audits/{i}/decision.json',dict(status='PASS_SLICE_OBSERVATION_AUDIT',accepted_operation=op))
            summary=put(r/f'operator_ui/summary-{i}.json',dict(facts=facts));put(r/f'operator_ui/review-{i}.json',dict(attempt_id=str(i),audit=audit,summary_sha256=summary,agent_observation=observation,agent_observation_sha256=note_hash))
        else:
            put(folder/'result.json',dict(result=None,error=dict(code='BOARD_OPERATION_CHECK_FAILED')))
            put(folder/'abi/stdout.json',dict(status='REJECTED',operation=op,error=dict(code='RENDER_REJECTED',message='RASTER_FIDELITY_EXCEEDED:sample:0.001089077')))
            put(folder/'abi/execution.json',dict(registry_sha256=host))
        put(folder/'receipt.json',dict(attempt_id=str(i),tool=op,completed_at=f'{i:02d}',status='FAIL'if i==20 else'PASS_BOARD_OPERATION_CHECKS',files={str(p.relative_to(folder)):c.sha(p.read_bytes())for p in folder.rglob('*')if p.is_file()}))
    put(out/'tiles/tile-0/audit.json',dict(tile=tiles[0],audits={name:dict(passed=True,mismatches_outside_band=0,pixels_checked=4,allowed_boundary_error_mm=band)for name,band in [('kicad',.001),('gerber',.005)]}))
    return j


def inventory(folder):return{str(p.relative_to(folder)):p.read_bytes()for p in folder.rglob('*')if p.is_file()}


def test_finishes_report_preserving_failure_and_originals_without_native_calls(job,monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:pytest.fail('No process or rendering is authorized'))
    before=inventory(job);r=c.finalize(job)
    assert r['status']==c.STATUS and r['render_qualification']=='FAIL'and r['new_native_operations']==0 and r['rerendered']is False
    assert [op['status']for op in r['operations']]==['PASS']*19+['FAIL','NOT_RUN']
    assert r['findings'][0]['observed_sample_mm']==.001089077 and r['findings'][0]['allowed_boundary_error_mm']==.001
    assert r['pixel_tiles_passed']==1 and r['pixel_tiles_not_run']==1 and r['render_controls']=='NOT_RUN'
    assert inventory(job)==before and 'failed findings'in r['ready_markdown']
    assert c.finalize(job)==r and inventory(job)==before
    for p in Path(r['evidence']).rglob('*.html'):
        import re
        for link in re.findall(r'(?:src|href)="([^"]+)"',p.read_text()):assert(p.parent/link).exists()


@pytest.mark.parametrize('mutation',['source','candidate','attempt','review','pixel','missing_target'])
def test_tampered_evidence_never_becomes_completed_with_findings(job,mutation):
    root=job/'native'
    target={'source':job/'inputs/kicad','candidate':root/'data_output/candidate/board.kicad_pcb','attempt':root/'attempts/20/abi/stdout.json','review':root/'operator_ui/review-1.json','pixel':root/'render_output/tiles/tile-0/audit.json','missing_target':root/'render_output/tiles/tile-2/gerber.png'}[mutation]
    if mutation=='missing_target':target.unlink()
    else:target.write_bytes(b'corrupted')
    with pytest.raises((ValueError,KeyError,OSError,TypeError)):c.finalize(job)
    assert not(c.ROOT/'out/operator_routes/t01_board/completions').exists()


@pytest.mark.parametrize('error',['RENDER_INPUT_HASH_MISMATCH','RASTER_FIDELITY_EXCEEDED:sample:0.0001','RASTER_FIDELITY_EXCEEDED:sample:nan','BOARD_SEQUENCE_INCOMPLETE'])
def test_other_failures_and_inconsistent_measurements_cannot_be_report_completed(job,error):
    folder=job/'native/attempts/20';p=folder/'abi/stdout.json';raw=json.loads(p.read_bytes());raw['error']['message']=error;put(p,raw)
    receipt=json.loads((folder/'receipt.json').read_bytes());receipt['files']['abi/stdout.json']=c.sha(p.read_bytes());put(folder/'receipt.json',receipt)
    with pytest.raises(ValueError):c.retained(job)


def test_missing_observation_or_earlier_native_failure_still_halts(job):
    folder=job/'native/attempts/4';r=json.loads((folder/'receipt.json').read_bytes());r['status']='FAIL';put(folder/'receipt.json',r)
    with pytest.raises(ValueError,match='OBSERVATION_MISMATCH'):c.retained(job)


def test_output_cannot_modify_source_and_cached_report_cannot_be_corrupted(job):
    with pytest.raises(ValueError,match='ADDITIVE'):c.finalize(job,job/'new-report')
    r=c.finalize(job);Path(r['html']).write_text('changed')
    with pytest.raises(ValueError,match='HASH_MISMATCH'):c.finalize(job)


def test_does_not_allow_active_jobs_or_crop_jobs(job):
    (job/'native/adapter_stopped.json').unlink()
    with pytest.raises(OSError):c.finalize(job)


def test_finalizer_works_without_project_geometry_dependencies():
    import ast
    source=ast.parse(Path(c.__file__).read_text());imports=[n.module for n in ast.walk(source)if isinstance(n,ast.ImportFrom)]
    assert all(not(v or'').startswith(('src.','shapely','PIL'))for v in imports)


def test_cli_finalizes_retained_job_without_launcher_or_input_setup(job,monkeypatch,capsys):
    from tools import pcb_t01_board_operator as operator
    def forbidden(*a,**k):pytest.fail('No launcher or native tool may run')
    monkeypatch.setattr(operator.jobs,'launcher_ready',forbidden);monkeypatch.setattr(operator.BoardClient,'call',forbidden)
    monkeypatch.setattr(sys,'argv',['pcb_t01_board_operator.py','finalize','--job',str(job)])
    before=inventory(job);assert operator.main()==0;result=json.loads(capsys.readouterr().out)
    assert result['status']==c.STATUS and result['render_qualification']=='FAIL'and 'source_files'not in result
    assert inventory(job)==before


def test_review_of_halted_board_returns_additive_completion_without_worker(job,monkeypatch,capsys):
    from contextlib import nullcontext
    from tools import pcb_t01_board_operator as operator
    monkeypatch.setattr(operator.jobs,'exclusive',nullcontext);monkeypatch.setattr(operator.jobs,'current',lambda:(job,dict(task_scope='full-board')));monkeypatch.setattr(operator.jobs,'outcome',lambda j:'HALTED')
    monkeypatch.setattr(operator,'BoardOperator',lambda *a:pytest.fail('Stopped native worker must not be instantiated'))
    monkeypatch.setattr(sys,'argv',['pcb_t01_board_operator.py','review','Return retained findings'])
    before=inventory(job);assert operator.main()==0;assert json.loads(capsys.readouterr().out)['status']==c.STATUS;assert inventory(job)==before


def test_fresh_render_rejection_auto_finishes_report_without_retry(job,monkeypatch,capsys):
    from contextlib import nullcontext
    from tools import pcb_t01_board_operator as operator
    class FailedOperator:
        ui=job/'native/operator_ui'
        def review(self,*args):raise ValueError('retained pixel rejection')
    monkeypatch.setattr(operator.jobs,'exclusive',nullcontext);monkeypatch.setattr(operator.jobs,'current',lambda:(job,dict(task_scope='full-board')));monkeypatch.setattr(operator.jobs,'outcome',lambda j:'IN_PROGRESS');monkeypatch.setattr(operator.jobs,'binding',lambda *a,**k:None);monkeypatch.setattr(operator,'BoardOperator',lambda *a:FailedOperator())
    monkeypatch.setattr(sys,'argv',['pcb_t01_board_operator.py','review','Observed display production'])
    assert operator.main()==0;result=json.loads(capsys.readouterr().out)
    assert result['new_native_operations']==0 and result['render_qualification']=='FAIL'and result['operations'][-1]['status']=='NOT_RUN'
