"""Real native synthetic U04 receipt followed by all U05 continuation gates."""
import json,os,subprocess
from pathlib import Path
from src.stage_abi.store import canonical,digest

def events(path):
    values=[]
    for line in path.read_text().splitlines():
        try:values.append(json.loads(line))
        except ValueError:pass
    return values

def test_terminal_U05_follows_verified_U04_and_exports_real_spindles(tmp_path):
    from src.pcb_data_abi.service import CLI,CLI_SHA
    from src.crop_circle_sources import verify_assets
    root=Path(__file__).resolve().parents[1];verify_assets();assert digest(CLI.read_bytes())==CLI_SHA
    construction=tmp_path/'construction';construction.mkdir();board=construction/'board.kicad_pcb'
    body=b'''(kicad_pcb (version 20241229) (generator pcbnew)
      (layers (0 "F.Cu" signal) (31 "B.Cu" signal)
        (34 "B.Paste" user) (35 "F.Paste" user)
        (36 "B.SilkS" user) (37 "F.SilkS" user)
        (38 "B.Mask" user) (39 "F.Mask" user) (44 "Edge.Cuts" user))
      (gr_circle (center 0 0) (end .12497 0) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))
      (gr_circle (center 2 0) (end 2.14999 0) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))
      (segment (start 0 0) (end -.5 0) (width .02) (layer "F.Cu") (net 0))
      (gr_poly (pts (xy 4 0) (xy 5 0) (xy 5 1) (xy 4 1)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))
      (gr_poly (pts (xy 5.1 0) (xy 6.1 0) (xy 6.1 1) (xy 5.1 1)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))
      (segment (start 4.2 .5) (end 5.9 .5) (width .3) (layer "F.Cu") (net 0))
      (gr_poly (pts (xy 8 3) (xy 9 3) (xy 8 4)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))
      (gr_poly (pts (xy -3 -3) (xy -2.9 -3) (xy -3 -2.9)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))
      (gr_line (start 0 3) (end 1 3) (stroke (width .1) (type solid)) (layer "B.Cu")))'''
    board.write_bytes(body);plots=construction/'gerbers';plots.mkdir();argv=list(map(str,[CLI,'pcb','export','gerbers','--layers','F.Cu','--precision','6','--no-protel-ext','-o',str(plots)+'/',board]));p=subprocess.run(argv,capture_output=True,timeout=120,env=dict(os.environ,KICAD_RUN_FROM_BUILD_DIR='1'));(tmp_path/'source_plot.stdout').write_bytes(p.stdout);(tmp_path/'source_plot.stderr').write_bytes(p.stderr);(tmp_path/'source_plot.command.json').write_bytes(canonical(dict(argv=argv,cli_sha256=CLI_SHA,returncode=p.returncode)));assert p.returncode==0
    raw=tmp_path/'raw';raw.mkdir();(raw/'board.kicad_pcb').write_bytes(body);(raw/'board-F_Cu.gbr').write_bytes((plots/'board-F_Cu.gbr').read_bytes())
    from tools.pcb_workspace import WORK
    pointer=WORK/'operator_routes/u04_board/managed/current.json';saved_pointer=pointer.read_bytes() if pointer.exists() else None
    existing=os.environ.get('PCB_U05_TEST_U04_JOB')
    if existing:
        old=Path(existing)
        assert old.is_absolute()
    else:
        log=tmp_path/'U04.log'
        with log.open('wb') as stream:p=subprocess.run([str(root/'tools/Run_U04_Board.command'),'--input-dir',str(raw)],cwd=root,stdout=stream,stderr=subprocess.STDOUT,timeout=600)
        assert p.returncode==0,log.read_text()[-10000:]
        old=Path(next(e['job'] for e in events(log) if e.get('status')=='COMPLETE_MACHINE_AUDITED_U04_EXPORT'))
        if saved_pointer is not None and json.loads(pointer.read_bytes())['job']==str(old):
            temporary=pointer.with_name('restore-test-pointer.tmp');temporary.write_bytes(saved_pointer);os.replace(temporary,pointer)
    from src.u05_board.custody import inventory
    before=inventory(old);log=tmp_path/'U05.log'
    with log.open('wb') as stream:p=subprocess.run([str(root/'tools/Run_U05_Board.command'),'--u04-job',str(old),'--state-dir',str(tmp_path/'u05_managed')],cwd=root,stdout=stream,stderr=subprocess.STDOUT,timeout=600)
    assert p.returncode==0,log.read_text()[-16000:]
    result=next(e for e in events(log) if e.get('status')=='COMPLETE_MACHINE_AUDITED_U05_EXPORT');assert result['retained_U04_gates']==41 and result['new_native_gates']==result['machine_audits']==14;assert result['human_or_agent_observations']==0 and result['T05']['grown']>0
    assert inventory(old)==before and result['predecessor_preservation']['sha256_bytes_mtime_and_inventory_unchanged']
    job=Path(result['job']);proofs=list((job/'audits').glob('*/proof.json'));assert len(proofs)==14 and all(json.loads(q.read_bytes())['status']=='PASS' for q in proofs)
    for path in proofs:
        metadata=json.loads(path.with_name('evaluations.json').read_bytes());workers=metadata['workers'];assert len(workers)==2 and workers[0]['pid']!=workers[1]['pid']
        for i,worker in enumerate(workers,1):
            output=path.parent/'evaluations'/f'{i}.stdout.json';value=json.loads(output.read_bytes())
            assert worker['exit_code']==0 and digest(output.read_bytes())==worker['stdout_sha256'] and value['pid']==worker['pid'] and value['proof']==json.loads(path.read_bytes())
    exported=json.loads((job/'data_output/pcb_gerber_verify.json').read_bytes())['verification'];assert exported['actual_hard_gap_mm']==.04000 and exported['junction_parts']>0 and len(exported['protected_layers_equal'])==8
    controls=json.loads((job/'data_output/pcb_export_controls.json').read_bytes());assert {r['name'] for r in controls['controls']}=={'units','role','protected_U04','missing_spindle'}
    assert all(r['status']=='PASS_EXPECTED_REJECTION' for r in controls['controls']) and result['owner']=='PENDING_USER'
