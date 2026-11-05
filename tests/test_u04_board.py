"""Corrected U04: exact U03 predecessor, T02 rectangle/inclusive and native exports."""
import copy,json
from pathlib import Path
import pytest
from shapely import to_wkb,from_wkb
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.u04_board.rectangles import RectangleGates,admit_rectangles,NativeRectangleAdapter,parameters


def fixture(tmp_path):
    from tests.test_u03_board import gates_fixture
    from src.u03_board.custody import T04
    gates_fixture(tmp_path)
    from src.u04_board.width import WidthGates
    width=WidthGates(tmp_path)
    for op in T04:width.dispatch(op)
    return RectangleGates(tmp_path)


def native_scene(tmp_path,nodes):
    from tests.test_u03_board import source_case
    from src.stage_abi.native_import import import_width_scene
    raw,rows,blobs=source_case(nodes);manifest=dict(source_sha256=digest(raw),objects=rows)
    store=ArtifactStore(tmp_path/'runtime')
    imported=import_width_scene(store,source=raw,manifest=manifest,original_blobs=blobs,current_blobs={},chains=[],viewport_mm=[-3,-3,1000,1000],qualification={'scope':'Source-admission unit fixture'})
    scene=store.get_json(imported['scene_ref'],kind='scene')
    return store,scene,manifest,raw


def rect(x=0,y=0):
    return f'(gr_poly (pts (xy {x} {y}) (xy {x+.5} {y}) (xy {x+.5} {y+.4}) (xy {x} {y+.4})) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))'


def test_no_applicable_feature_still_completes_all_native_gates(tmp_path):
    from src.u04_board.custody import T02
    gates=fixture(tmp_path);results=[gates.dispatch(op) for op in T02]
    assert all(r['facts']['passed'] for r in results)
    assert results[3]['facts']['disposition']=='NO_APPLICABLE_FEATURE'
    assert results[4]['facts']['reconstructed_rectangles']==0
    assert len(results[-1]['controls'])==6


def test_source_admission_is_complete_beyond_one_page_and_keeps_original_ids(tmp_path):
    store,scene,manifest,raw=native_scene(tmp_path,[rect(i*2) for i in range(121)])
    report=admit_rectangles(store,scene,manifest,raw)
    assert len(report['sources'])==len(report['target_ids'])==121
    assert report['native_source_ids']==sorted(r['id'] for r in manifest['objects'])
    from src.u03_board.paging import put,get
    ref=put(store,report['sources'],binding={'source':digest(raw)},kind='u04-rectangle-sources')
    rows,index=get(store,ref,binding={'source':digest(raw)},kind='u04-rectangle-sources',identity=lambda r:r['source_id'])
    assert len(index['pages'])==2 and rows==report['sources']


def test_generated_T01_polygon_is_not_a_new_rectangle_target(tmp_path):
    node='(gr_circle (center 0 0) (end .2 0) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))'
    store,scene,manifest,raw=native_scene(tmp_path,[node]);scene['objects'][0]['geometry_ref']=store.put('geometry',to_wkb(box(-.2,-.2,.2,.2)))
    report=admit_rectangles(store,scene,manifest,raw)
    assert report['target_ids']==[] and report['sources'][0]['disposition']=='KEEP_PROTECTED_PREDECESSOR'


def test_changed_source_or_duplicate_native_members_halt(tmp_path):
    store,scene,manifest,raw=native_scene(tmp_path,[rect()])
    with pytest.raises(ValueError,match='SOURCE_CHANGED'):admit_rectangles(store,scene,manifest,raw+b' ')
    scene['objects'][0]['metadata']['native_source_ids']*=2
    with pytest.raises(ValueError,match='PARTITION'):admit_rectangles(store,scene,manifest,raw)


def test_oriented_rectangle_is_explicitly_unsupported(tmp_path):
    node='(gr_poly (pts (xy 0 0) (xy 1 1) (xy .5 1.5) (xy -.5 .5)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))'
    store,scene,manifest,raw=native_scene(tmp_path,[node]);report=admit_rectangles(store,scene,manifest,raw)
    assert len(report['unsupported'])==1 and not report['target_ids']


def test_complete_cap_crossing_viewport_and_fixed_bulk_stay_protected(tmp_path):
    store,scene,manifest,raw=native_scene(tmp_path,[rect()]);scene['viewport_mm']=[0,0,.5,.4]
    report=admit_rectangles(store,scene,manifest,raw)
    assert report['sources'][0]['disposition']=='KEEP_VIEWPORT_BOUNDARY'
    scene['objects'][0]['metadata']['fixed_bulk']=True
    assert admit_rectangles(store,scene,manifest,raw)['sources'][0]['disposition']=='KEEP_FIXED_BULK'


def test_actual_native_rectangle_growth_and_original_cap_replay(tmp_path):
    store,scene,manifest,raw=native_scene(tmp_path,[rect()]);report=admit_rectangles(store,scene,manifest,raw)
    adapter=NativeRectangleAdapter();ref=store.put_json('scene',scene);policy=dict(stage='t02',parameters=parameters())
    bounds=dict(max_source_objects=1,max_targets=1,max_evaluations=1000,max_output_bytes=1000000,max_seconds=120)
    details=adapter.plan(store,scene,policy,dict(stage='t02',scene_ref=ref,source_ids=report['target_ids']),bounds)
    plan=dict(stage='t02',scene_ref=ref,policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details)
    candidate=adapter.run(store,scene,policy,plan,lambda v:None)
    assert candidate['decisions'][0]['shape']['factors']==[1.25,1.25]
    assert adapter.verify(store,scene,policy,plan,candidate,dict(scope='complete-source-land-and-inclusive'),lambda v:None)['passed']
    changed=copy.deepcopy(candidate);changed['decisions'][0]['shape']['factors'][0]=1.26
    from src.stage_abi.contracts import StageABIError
    with pytest.raises(StageABIError) as error:adapter.verify(store,scene,policy,plan,changed,dict(scope='complete-source-land-and-inclusive'),lambda v:None)
    assert error.value.code=='RECTANGLE_SCALE_OUT_OF_SCOPE'


def test_sequences_preserve_U03_and_reserve_T05_for_U05():
    from src.u03_board.custody import STEPS as old
    from src.u04_board.custody import STEPS,T02,operation_steps
    assert len(old)==33 and len(STEPS)==41 and len(operation_steps(cropped=True))==43
    assert tuple(op for op in STEPS if op not in T02)==old
    assert not any(op.startswith(('render_','t05_')) for op in STEPS)


def test_old_launcher_rejects_U04_before_input_scan(tmp_path,monkeypatch):
    from tools import t01_crop_jobs as jobs,u04_board_jobs
    monkeypatch.setattr(u04_board_jobs,'configure',lambda:None)
    monkeypatch.setattr(jobs,'launcher_ready',lambda:dict(u03_board='native-u03/1'))
    with pytest.raises(ValueError,match='NATIVE_LAUNCHER_UPDATE_REQUIRED'):u04_board_jobs.intake('/not-read')


def test_final_route_requires_actual_rectangle_and_inclusive_controls(tmp_path):
    from src.u04_board.export import required_export_controls
    from tools.u04_board_route import U04Route
    measured=dict(changed_native_trace_parts=1,targets=[],rectangle_parts=2,inclusive_parts=1)
    expected=required_export_controls(measured)
    assert len(expected)==5
    folder=tmp_path/'data_output';folder.mkdir();(folder/'pcb_gerber_verify.json').write_bytes(canonical(dict(verification=measured)))
    controls=[dict(name=name,expected=prefix,error=prefix+':actual fault',status='PASS_EXPECTED_REJECTION') for name,prefix in expected.items()]
    facts=dict(passed=True,deliberate_controls=5,all_rejected_for_expected_reason=True)
    response=dict(status='OK',error=None,result=dict(facts=facts,controls=controls))
    route=U04Route.__new__(U04Route);route.session=tmp_path;route._bind=lambda path:None
    assert route._facts('pcb_export_controls',response,0,tmp_path)==facts
    for mutation in ('missing_control','false_prefix','duplicate'):
        bad=copy.deepcopy(response)
        if mutation=='missing_control':bad['result']['controls'].pop()
        elif mutation=='false_prefix':bad['result']['controls'][0]['expected']=''
        else:bad['result']['controls'][-1]=bad['result']['controls'][0]
        with pytest.raises(ValueError,match='REQUIRED_EXPORT_CONTROLS_MISMATCH'):route._facts('pcb_export_controls',bad,0,tmp_path)


def test_actual_terminal_route_closes_all_41_gates_and_exports(tmp_path):
    """Exercise checkpoint production and consumption through the real facade."""
    import os,signal,subprocess
    from src.crop_circle_sources import verify_assets
    from src.pcb_data_abi.service import CLI,CLI_SHA
    from src.u04_board.custody import STEPS,THROUGH_T02
    root=Path(__file__).resolve().parents[1]
    verify_assets();assert digest(CLI.read_bytes())==CLI_SHA
    raw=tmp_path/'synthetic_raw';raw.mkdir()
    construction=tmp_path/'construction';construction.mkdir()
    board=construction/'board.kicad_pcb'
    board.write_bytes(b'''(kicad_pcb (version 20241229) (generator pcbnew)
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
      (gr_line (start 0 3) (end 1 3) (stroke (width .1) (type solid)) (layer "B.Cu")))''')
    (raw/'board.kicad_pcb').write_bytes(board.read_bytes())
    plots=construction/'gerbers';plots.mkdir()
    argv=list(map(str,[CLI,'pcb','export','gerbers','--layers','F.Cu','--precision','6','--no-protel-ext','-o',str(plots)+'/',board]))
    plotted=subprocess.run(argv,capture_output=True,timeout=120,env=dict(os.environ,KICAD_RUN_FROM_BUILD_DIR='1'))
    (tmp_path/'source_plot.stdout').write_bytes(plotted.stdout);(tmp_path/'source_plot.stderr').write_bytes(plotted.stderr)
    (tmp_path/'source_plot.command.json').write_bytes(canonical(dict(argv=argv,returncode=plotted.returncode,cli_sha256=CLI_SHA)))
    assert plotted.returncode==0,plotted.stderr.decode()
    (raw/'board-F_Cu.gbr').write_bytes((plots/'board-F_Cu.gbr').read_bytes())
    log=tmp_path/'terminal.log'
    with log.open('wb') as stream:
        process=subprocess.Popen([str(root/'tools/Run_U04_Board.command'),'--input-dir',str(raw)],cwd=root,stdout=stream,stderr=subprocess.STDOUT)
        try:code=process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            process.send_signal(signal.SIGINT);process.wait(timeout=30)
            pytest.fail('Native synthetic U04 timed out; retained '+str(log))
    events=[]
    for line in log.read_text().splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    assert code==0,log.read_text()[-10000:]
    complete=next(e for e in events if e.get('status')=='COMPLETE_MACHINE_AUDITED_U04_EXPORT')
    job=Path(complete['job']);native=job/'native'
    journal=Path(json.loads((job/'TERMINAL_RUN.json').read_bytes())['journal'])
    result=json.loads((journal/'result.json').read_bytes())
    assert result['machine_audits']==len(STEPS)==41 and result['observation_audits']==0
    assert result['render_operations']==0 and result['owner']=='PENDING_USER'
    checkpoint=json.loads((native/'U04_CHECKPOINT.json').read_bytes())
    assert checkpoint['operations']==list(THROUGH_T02)
    assert {'u02_t03/t03_inspect.json','u02_t03/t03_search.json','u02_t03/t03_verify.json','u02_t03/t03_controls.json'}<=checkpoint['files'].keys()
    assert len(json.loads((native/'MACHINE_RECEIPT.json').read_bytes())['proofs'])==41
    exports=json.loads((native/'data_output/pcb_gerber_export.json').read_bytes())
    assert exports['facts']['layers']==9 and len(exports['output_sha256'])==18
    rectangle=json.loads((native/'u04_t02/t02_run.json').read_bytes())['facts']
    assert rectangle['grown']>0 and rectangle['inclusive_fills']>0
    assert json.loads((native/'data_output/pcb_export_controls.json').read_bytes())['facts']['deliberate_controls']==5
    actual=json.loads((native/'data_output/pcb_gerber_verify.json').read_bytes())['verification']
    assert actual['rectangle_parts']>0 and actual['inclusive_parts']>0
    assert json.loads((native/'adapter_stopped.json').read_bytes())['status']=='STOPPED'




def test_absolute_image_command_completes_43_native_gates_and_protects_outside(tmp_path):
    import os,signal,subprocess
    from src.pcb_data_abi.service import CLI,CLI_SHA
    from src.u04_board.custody import CROP,STEPS
    from src.native_inventory import inventory
    from tests.test_u03_crops import image_fixture
    raw,inv,image=image_fixture(tmp_path)
    source=tmp_path/'raw';source.mkdir();board=source/'board.kicad_pcb';board.write_bytes(raw)
    plots=tmp_path/'plots';plots.mkdir()
    argv=list(map(str,[CLI,'pcb','export','gerbers','--layers','F.Cu','--precision','6','--no-protel-ext','-o',str(plots)+'/',board]))
    native=subprocess.run(argv,capture_output=True,timeout=120,env=dict(os.environ,KICAD_RUN_FROM_BUILD_DIR='1'))
    (tmp_path/'source_plot.stdout').write_bytes(native.stdout);(tmp_path/'source_plot.stderr').write_bytes(native.stderr)
    (tmp_path/'source_plot.command.json').write_bytes(canonical(dict(argv=argv,cli_sha256=CLI_SHA,returncode=native.returncode)))
    assert native.returncode==0,native.stderr.decode()
    # A native exporter may create project metadata beside its working copy.
    for p in source.iterdir():
        if p!=board:p.rename(tmp_path/('source_metadata_'+p.name))
    (source/'board-F_Cu.gbr').write_bytes((plots/'board-F_Cu.gbr').read_bytes())
    root=Path(__file__).resolve().parents[1];log=tmp_path/'terminal.log'
    with log.open('wb') as stream:
        process=subprocess.Popen([str(root/'tools/Run_U04_Board.command'),'--input-dir',str(source),'--crop',str(image)],cwd=root,stdout=stream,stderr=subprocess.STDOUT)
        try:code=process.wait(timeout=360)
        except subprocess.TimeoutExpired:
            process.send_signal(signal.SIGINT);process.wait(timeout=30);pytest.fail('Image U04 timed out; retained '+str(log))
    assert code==0,log.read_text()[-14000:]
    events=[]
    for line in log.read_text().splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    event=next(r for r in events if r.get('status')=='COMPLETE_MACHINE_AUDITED_U04_EXPORT');job=Path(event['job']);session=job/'native'
    receipt=json.loads((session/'U04_RECEIPT.json').read_bytes());expected=[*STEPS[:3],*CROP,*STEPS[3:]]
    assert receipt['operations']==expected and len(expected)==43
    assert len(json.loads((session/'MACHINE_RECEIPT.json').read_bytes())['proofs'])==43
    assert receipt['selection']['crop_sha256']==digest(image.read_bytes())
    assert (Path(json.loads((job/'job.json').read_bytes())['crop']['path'])).read_bytes()==image.read_bytes()
    candidate=Path(json.loads((session/'data_output/pcb_kicad_write.json').read_bytes())['board'])
    changed=inventory(candidate.read_bytes())
    # Locate the original outside circle by its immutable native bytes.
    fragment=b'(gr_circle (center 30 30) (end 30.12497 30) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))'
    before_circle=next(r for r in inv['objects'] if raw[slice(*r['source_span'])]==fragment)
    # T01 is source-wide even for a view. Its complete decision map proves
    # this original source is retained or grown under the same canonical policy.
    cap=json.loads(sorted(session.glob('capsule_*.json'))[-1].read_bytes())
    store=ArtifactStore(Path(cap['store_path']))
    run=next(json.loads((p/'abi/stdout.json').read_bytes())['result'] for p in (session/'attempts').iterdir() if (p/'receipt.json').exists() and json.loads((p/'receipt.json').read_bytes())['tool']=='t01_run')
    result=store.get_json(run['result']['candidate_ref'],kind='candidate')
    assert before_circle['id'] in result['replacements']
    from shapely import from_wkb
    original=from_wkb((session/'data_board/source_wkb'/f'{before_circle["geometry_sha256"]}.wkb').read_bytes())
    replacement=from_wkb(store.get(result['replacements'][before_circle['id']],kind='geometry'))
    assert original.difference(replacement).area<=1e-10
    report=(session/'U04_REPORT.md').read_text()
    assert str(image) in report and '--crop' in report and '43 native gates' in report
    assert json.loads((session/'adapter_stopped.json').read_bytes())['status']=='STOPPED'


def test_U04_rejects_forged_machine_proof_before_advancement(tmp_path):
    from tools.u04_board_route import MachineRoute
    folder=tmp_path/'audits/machine-001';folder.mkdir(parents=True);(folder/'proof.json').write_bytes(canonical(dict(status='PASS')))
    route=MachineRoute.__new__(MachineRoute);route.session=tmp_path;route.position=0;route.pending=dict(attempt_id='attempt');route.halted=False;route.audit_hashes={}
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):route._audit(dict(attempt_id='attempt',audit={'note':'generic success'}),{})
    assert route.halted and route.position==0


def test_U04_old_launcher_and_missing_mount_do_not_scan_input(tmp_path,monkeypatch):
    from tools import u04_board_jobs as jobs
    configure=jobs.configure
    monkeypatch.setattr(jobs,'configure',lambda:None);monkeypatch.setattr(jobs.jobs,'launcher_ready',lambda:{})
    monkeypatch.setattr(jobs.directory,'native_intake',lambda *a,**k:pytest.fail('Old launcher must not intake'))
    with pytest.raises(ValueError,match='UPDATE_REQUIRED'):jobs.intake('/not-scanned-by-client')
    def missing():raise RuntimeError('LACIE_WORKSPACE_UNAVAILABLE')
    monkeypatch.setattr(jobs,'require_storage',missing)
    with pytest.raises(RuntimeError,match='UNAVAILABLE'):configure()


def test_U04_runner_keeps_supervision_and_no_false_observations():
    root=Path(__file__).resolve().parents[1];text=(root/'tools/pcb_u04_board_run.py').read_text()
    assert 'adapter_health(thread,thread_error)' in text and 'traceback.format_exc()' in text
    assert 'owned.cancel()' in text and 'HALT_RECORD_WRITE_FAILED' in text
    assert "action='u04_directory_intake'" in text and 'len(operator.steps)' in text




def test_launcher_accepts_u04_intake_only_into_its_separate_namespace(tmp_path,monkeypatch):
    from tools import t01_crop_jobs as jobs,t01_crop_launcher as module,u04_board_jobs as u04
    from tools.t01_route_client import publish,encode
    monkeypatch.setattr(jobs,'ROOT',tmp_path);monkeypatch.setattr(jobs,'MANAGED',tmp_path/'out/t01-managed');monkeypatch.setattr(u04,'MANAGED',tmp_path/'out/u04-managed')
    class Process:
        pid=987
        def poll(self):return 0
    calls=[];monkeypatch.setattr(module.subprocess,'Popen',lambda argv,**kw:calls.append(argv)or Process())
    launcher=module.Launcher(tmp_path/'out/launcher')
    try:
        req=dict(action='u04_directory_intake',launcher_id=launcher.id,input_directory='/not-read-by-client',companion_policy='PRESERVE_EXCLUDED');publish(launcher.registry/'inbox/u04.json',encode(req));launcher.tick()
        assert len(calls)==1 and calls[0][-1]==str(u04.MANAGED)
        assert jobs.MANAGED==tmp_path/'out/t01-managed'
        assert json.loads((launcher.registry/'current.json').read_bytes())['u04_board']=='native-u04/1'
        launcher.tick();assert len(calls)==1
    finally:launcher.close()


