"""Crop scope, full-scene obstacles and fresh T01/T03/T04 reconstruction."""
import copy,json,sys
from pathlib import Path
import pytest
from shapely.geometry import Point
from src.stage_abi.store import canonical,digest
from src.u03_board import selection
from src.u03_board.source import qualify,require_admitted
from tests.test_u03_board import source_case


def verified_window(tmp_path,source_sha,bounds,uncertainty=0.):
    """Scope-unit fixture; the separate native tests execute actual location."""
    from PIL import Image
    crop=tmp_path/'crop input.png';Image.new('RGB',(32,32),'red').save(crop)
    location=tmp_path/'location.json';location.write_bytes(canonical(dict(source_sha256=source_sha,crop_sha256=digest(crop.read_bytes()))))
    witness=tmp_path/'crop_landmark_witness.json';witness.write_bytes(canonical(dict(scope='Scope-unit fixture only; native command tests perform full source reconstruction')))
    verification=tmp_path/'verified.json';verification.write_bytes(canonical(dict(bounds_mm=bounds,uncertainty_mm=uncertainty,location_sha256=digest(location.read_bytes()),landmark_witness_sha256=digest(witness.read_bytes()),facts=dict(location_verified=True))))
    return dict(schema='pcb-u03-image-crop/1',crop_path=str(crop),crop_sha256=digest(crop.read_bytes()),source_sha256=source_sha,bounds_mm=bounds,edge_uncertainty_mm=uncertainty,location_status='PASS_NATIVE_ROI_LOCATION',location_path=str(location),location_sha256=digest(location.read_bytes()),verification_path=str(verification),verification_sha256=digest(verification.read_bytes()))


def test_crop_scope_is_bound_to_actual_files_source_and_verified_location(tmp_path):
    value=verified_window(tmp_path,'a'*64,[-1,-1,1,1]);assert selection.validate(value,'a'*64)==value
    with pytest.raises(ValueError,match='SOURCE_MISMATCH'):selection.validate(value,'0'*64)
    with pytest.raises(ValueError,match='SELECTION_CHANGED'):selection.validate(dict(value,bounds_mm=[0,0,1,1]))
    with pytest.raises(ValueError,match='LOCATION_NOT_VERIFIED'):selection.validate(dict(value,location_status='PENDING'))
    Path(value['crop_path']).write_bytes(b'changed image')
    with pytest.raises(ValueError,match='EVIDENCE_CHANGED'):selection.validate(value)


def test_whole_growth_envelope_and_uncertain_edge_are_protected(tmp_path,monkeypatch):
    chosen=verified_window(tmp_path,'a'*64,[-1,-1,1,1])
    sites=[dict(source_id=str(i),aliases=[str(i)],core=Point(x,0).buffer(.1,quad_segs=128),radius=.1) for i,x in enumerate([0,.88,2])]
    selected,rows=selection.select_sites(sites,chosen)
    assert [r['source_id'] for r in selected]==['0']
    assert [r['disposition'] for r in rows]==['SELECT_COMPLETE_GROWTH_ENVELOPE','KEEP_CROP_BOUNDARY','KEEP_OUTSIDE_CROP']
    narrow=verified_window(tmp_path,'a'*64,[-1,-1,1,1],.9)
    with pytest.raises(ValueError,match='NO_COMPLETE_CIRCLE'):selection.select_sites(sites,narrow)


def test_whole_native_path_crossing_edge_is_not_trimmed(tmp_path,monkeypatch):
    raw,rows,blobs=source_case(['(segment (start 0 0) (end 2 0) (width .1) (layer "F.Cu"))',
                              '(segment (start 0 .8) (end 1 .8) (width .1) (layer "F.Cu"))'])
    chosen=verified_window(tmp_path,digest(raw),[-.2,-.2,1.2,1.1])
    before=copy.deepcopy(blobs);q=qualify(raw,rows,blobs,blobs,selection=chosen);require_admitted(q)
    assert q['classifications']=={'KEEP_CROP_BOUNDARY':1,'ADMIT_COMPLETE_NATIVE_ROUTE':1}
    assert q['admitted_paths'][0]['source_ids']==[rows[1]['id']]
    assert rows[0]['id'] in q['protected_source_ids'] and blobs==before
    assert q['complete_trace_coverage'] and q['trace_occurrences']==2


def test_crop_cannot_split_a_complete_parallel_group(tmp_path,monkeypatch):
    raw,rows,blobs=source_case(['(segment (start 0 0) (end 1 0) (width .1) (layer "F.Cu"))',
                              '(segment (start 0 .3) (end 1 .3) (width .1) (layer "F.Cu"))'])
    full=qualify(raw,rows,blobs,blobs);assert len(full['groups'])==1
    chosen=verified_window(tmp_path,digest(raw),[-.2,-.2,1.2,.2])
    q=qualify(raw,rows,blobs,blobs,selection=chosen)
    assert q['admitted_paths']==q['groups']==[]
    assert q['classifications']=={'KEEP_CROP_GROUP_BOUNDARY':1,'KEEP_OUTSIDE_CROP':1}
    assert set(q['protected_source_ids'])==set(blobs)
    with pytest.raises(ValueError,match='NO_EXPOSED_COMPLETE_ROUTES'):require_admitted(q)
    assert qualify(raw,rows,blobs,blobs,selection=None)==full


def test_crop_command_arguments_and_whole_board_default(monkeypatch):
    from tools import pcb_u03_board_run as cli
    calls=[];monkeypatch.setattr(cli,'run',lambda value,**kw:calls.append((value,kw)) or 0)
    for args,expected in [([],None),(['--whole-board'],None),(['--crop','/explicit/crop image.png'],Path('/explicit/crop image.png'))]:
        monkeypatch.setattr(sys,'argv',['run','--input-dir','/explicit/raw',*args]);assert cli.main()==0
        assert calls[-1][1]['crop']==expected
    for args in (['--crop','C04'],['--crop','C01','--whole-board']):
        monkeypatch.setattr(sys,'argv',['run','--input-dir','/explicit/raw',*args])
        with pytest.raises(SystemExit):cli.main()


def test_crop_requires_updated_launcher_before_directory_intake(monkeypatch):
    from tools import u03_board_jobs as jobs
    monkeypatch.setattr(jobs,'configure',lambda:None)
    monkeypatch.setattr(jobs.jobs,'launcher_ready',lambda:dict(u03_board='native-u03/1'))
    monkeypatch.setattr(jobs,'crop_intake',lambda *a:pytest.fail('Old launcher must not intake'))
    with pytest.raises(ValueError,match='UPDATE_REQUIRED'):jobs.intake('/not-read',crop='/not-read/crop.png')


def test_crop_T01_T03_T04_uses_full_native_context_and_protects_outside(tmp_path,monkeypatch):
    from tests.test_u02_board import native_session
    from src.u03_board.crop_t01 import ImageCropService,PROFILE,english
    from src.u03_board.crop_t03 import CropRetainPathsAdapter
    from src.u03_board.adapter import WidthGates
    from src.u03_board.custody import T03,T04
    from src.stage_abi.scene import validate_scene
    baseline=native_session(tmp_path);store=baseline.store
    old_policy=store.get_json(baseline.cap['policy_ref'],kind='policy');binding_ref=old_policy['binding_ref'];binding=store.get_json(binding_ref,kind='t01-binding')
    chosen=verified_window(tmp_path,binding['source_sha256'],[-1,-1,1,1]);(tmp_path/'U03_SELECTION.json').write_bytes(canonical(chosen))
    crop_ref=store.put_json('u03-crop-selection',chosen);scene=baseline.receipt['scene_ref']
    bounds=store.put_json('bounds',dict(max_source_objects=3,max_targets=3,max_evaluations=10000,max_output_bytes=200000000,max_seconds=120));vr=store.put_json('verifier',{})
    host=dict(schema='u03-image-crop-t01-host/1',compiler_binding_refs=[binding_ref],crop_selection_ref=crop_ref,stage_registry=dict(schema='stage-agent-registry/1',profiles={},authorization_refs=[],decision_refs=[]));pref=None
    def call(verb,payload,plan_ref=None,authorization_ref=None,key=None):
        request=dict(abi_version='stage-agent-abi/1.0',request_id='crop-'+verb,operation='t01_'+verb,profile_id=None if verb=='compile' else PROFILE,scene_ref=None if verb=='compile' else scene,policy_ref=pref,plan_ref=plan_ref,authorization_ref=authorization_ref,idempotency_key=key,payload=payload)
        response=ImageCropService(store,host).dispatch(request);assert response['status']=='OK',response
        return response['result']
    pref=call('compile',dict(english=english(),binding_ref=binding_ref))['policy_ref'];host['stage_registry']['profiles'][PROFILE]=dict(stage='t01',adapter=PROFILE,policy_ref=pref,scene_refs=[scene],bounds_ref=bounds,verifier_ref=vr)
    discovery=call('discover',dict(bounds_ref=bounds));assert discovery['discovery']['unique_sites']==1 and discovery['discovery']['source_objects']==3
    inspection=call('inspect_all',dict(selection_ref=discovery['selection_ref'],page_size=100));qualification=store.put_json('verification',dict(scene_ref=scene,geometric_status='PASS'))
    planned=call('plan',dict(inspection_ref=inspection['inspection_ref'],selection_ref=discovery['selection_ref'],predecessor_qualification_ref=qualification,bounds_ref=bounds,strategy='priority_companion_growth'));pr=planned['plan_ref']
    out=store.put_json('output-scope',dict(kind='immutable-local-artifacts'));auth=store.put_json('authorization',dict(profile_id=PROFILE,scene_ref=scene,policy_ref=pref,plan_ref=pr,operations=['t01_run','t01_verify'],authority='Synthetic crop regression',output_scope_ref=out));host['stage_registry']['authorization_refs'].append(auth)
    ran=call('run',dict(output_scope_ref=out),pr,auth,'crop-fresh-run')['result'];proof=store.put_json('proof-scope',dict(scope='complete-board-t01-source-reconstruction'))
    verified=call('verify',dict(candidate_ref=ran['candidate_ref'],verifier_ref=vr,proof_scope_ref=proof),pr,auth,'crop-fresh-verify')['result'];assert verified['verification']['geometric_status']=='PASS'
    candidate=ran['candidate'];assert candidate['unique_sites']==1 and len(candidate['replacements'])==1
    original=validate_scene(store,scene);after=validate_scene(store,candidate['output_scene_ref'])
    assert len(after['objects'])==3
    assert all(a['geometry_ref']==b['geometry_ref'] for a,b in zip(original['objects'],after['objects']) if a['source_id'] not in candidate['replacements'])
    (tmp_path/'RECEIPT.json').write_bytes(canonical(dict(status='PASS_BOARD_T01_VERIFIED',binding_ref=binding_ref,source_sha256=binding['source_sha256'],scene_ref=scene,candidate_ref=ran['candidate_ref'],verification_ref=verified['verification_ref'])))
    (tmp_path/'capsule_02.json').write_bytes(canonical(dict(store_path=str(store.root),policy_ref=pref,plan_ref=pr)))
    (tmp_path/'data_board').mkdir();(tmp_path/'data_board/source_manifest.json').write_bytes(store.get(binding['manifest_ref'],kind='native-manifest'))
    t03=CropRetainPathsAdapter(tmp_path)
    for op in T03:t03.dispatch(op)
    gates=WidthGates(tmp_path)
    for op in T04:gates.dispatch(op)
    width=json.loads((tmp_path/'u03_t04/t04_verify.json').read_bytes())
    assert width['facts']['fresh_reconstruction'] and width['facts']['changed_native_parts']==1
    inventory=json.loads((tmp_path/'u03_t04/t04_inspect.json').read_bytes())
    assert inventory['facts']['complete_source_coverage']


def test_image_path_reader_never_resolves_crop_alias_or_relative_path(tmp_path):
    from PIL import Image
    from src.u03_board.crop_roi import read_crop
    with pytest.raises(ValueError,match='ABSOLUTE_CROP_PATH_REQUIRED'):read_crop('C01')
    path=tmp_path/'C01 crop image λ.png';Image.new('RGB',(80,60),'red').save(path)
    row,blob=read_crop(path);assert row['provided_path']==str(path) and row['sha256']==digest(blob)
    bad=tmp_path/'not-an-image';bad.write_bytes(b'nonimage')
    with pytest.raises(ValueError,match='IMAGE_UNSUPPORTED'):read_crop(bad)


def test_crop_sequence_adds_location_gates_without_replacing_original_checks():
    from src.u03_board.custody import STEPS,CROP,operation_steps
    actual=operation_steps(cropped=True)
    assert len(STEPS)==33 and len(actual)==35 and actual[:5]==(*STEPS[:3],*CROP)
    assert tuple(op for op in actual if op not in CROP)==STEPS


def test_bulk_copper_does_not_discard_small_round_landmarks():
    import numpy as np
    from src.u03_board.crop_match import round_peaks,seed_poses
    from src.pcb_data_abi import roi
    yy,xx=np.ogrid[:1200,:1800];mask=np.zeros((1200,1800),dtype=bool)
    points=[(140,150),(370,170),(690,140),(200,440),(610,500),(120,800),(420,760),(780,800)]
    for x,y in points:mask|=(xx-x)**2+(yy-y)**2<=20**2
    mask[445:555,1345:1455]=True
    original=roi.peaks(mask);cutoff=max(7,.6*original[0][2])
    assert cutoff>20
    actual=round_peaks(mask)
    assert len(actual)==len(points)
    assert all(min((x-a)**2+(y-b)**2 for a,b in points)<4 for x,y,_ in actual)
    features=[dict(source_id=str(i),aliases=[str(i)],center=[10+x/300,20+y/300],radius=20/300) for i,(x,y) in enumerate(points)]
    poses=seed_poses(mask,features)
    assert poses and poses[0]['seed_landmarks']==8


def test_source_landmark_census_proves_covered_and_subresolution_roles():
    from shapely.geometry import box
    from shapely import to_wkb
    from src.u03_board.crop_landmarks import observable
    features=[dict(source_id=s,aliases=[s],center=[x,y],radius=r) for s,x,y,r in
              [('visible',2,2,.3),('covered',5,5,.25),('partial',7,7,.3),('tiny',3,7,.04),('above-floor',8,3,.040001),('coincident-outline',8,8,.25)]]
    features[0]['aliases'].append('exact-alias')
    shapes=[Point(*f['center']).buffer(f['radius']) for f in features]
    rows=[dict(id=f['source_id']) for f in features]
    rows.extend([dict(id='exact-alias'),dict(id='cover'),dict(id='partial-cover'),dict(id='same-visible-outline')]);shapes.extend([shapes[0],box(4.5,4.5,5.5,5.5),box(6.5,6.5,7,7.5),shapes[5]])
    before=[to_wkb(g) for g in shapes]
    eligible,census=observable(features,dict(objects=rows),shapes,[0,0,10,10],(1000,1000))
    assert [r['source_id'] for r in eligible]==['visible','partial','above-floor','coincident-outline']
    byid={r['source_id']:r for r in census}
    assert byid['covered']['disposition']=='NOT_OBSERVABLE_FULLY_COVERED_SOURCE'
    assert byid['covered']['coverage_source_ids']==['cover']
    assert byid['tiny']['disposition']=='NOT_OBSERVABLE_BELOW_EXISTING_PEAK_FLOOR'
    assert byid['tiny']['predicted_radius_px']==4
    assert len(census)==len(features) and [to_wkb(g) for g in shapes]==before


@pytest.mark.parametrize('rotation,mirror',[(r,m) for r in range(4) for m in (False,True)])
def test_round_landmark_search_preserves_supported_image_transforms(rotation,mirror):
    import numpy as np
    from src.pcb_data_abi import roi
    from src.u03_board.crop_match import seed_poses
    points=[(.32,.28),(.76,.31),(1.34,.27),(.44,.72),(1.2,.81),(.28,1.18),(.84,1.12),(1.48,1.17)]
    features=[dict(source_id=str(i),aliases=[str(i)],center=[x+10,y+20],radius=.065) for i,(x,y) in enumerate(points)]
    from shapely.ops import unary_union
    geometry=unary_union([Point(*r['center']).buffer(r['radius'],quad_segs=64) for r in features])
    mask=roi.contains_xy(geometry,10+(np.arange(540)[None,:]+.5)/300,20+(np.arange(450)[:,None]+.5)/300)
    poses=seed_poses(roi.orient(mask,rotation,mirror),features)
    assert poses and poses[0]['seed_landmarks']==8


def image_fixture(tmp_path):
    from src.native_inventory import inventory
    from src.pcb_data_abi import roi
    from PIL import Image
    from shapely import from_wkb
    import numpy as np
    pts=[(.32,.28),(.76,.31),(1.34,.27),(.44,.72),(1.2,.81),(.28,1.18),(.84,1.12),(1.48,1.17)]
    circles=' '.join(f'(gr_circle (center {x+10:.6f} {y+20:.6f}) (end {x+10+.065:.6f} {y+20:.6f}) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))' for x,y in pts)
    raw=('''(kicad_pcb (version 20241229) (generator pcbnew)
    (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (34 "B.Paste" user) (35 "F.Paste" user) (36 "B.SilkS" user) (37 "F.SilkS" user) (38 "B.Mask" user) (39 "F.Mask" user) (44 "Edge.Cuts" user))
    '''+circles+'''
    (gr_poly (pts (xy 9.9875 19.9875) (xy 11.8125 19.9875) (xy 11.8125 20.0125) (xy 9.9875 20.0125)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))
    (gr_poly (pts (xy 9.9875 21.4875) (xy 11.8125 21.4875) (xy 11.8125 21.5125) (xy 9.9875 21.5125)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))
    (gr_poly (pts (xy 9.9875 20.0125) (xy 10.0125 20.0125) (xy 10.0125 21.4875) (xy 9.9875 21.4875)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))
    (gr_poly (pts (xy 11.7875 20.0125) (xy 11.8125 20.0125) (xy 11.8125 21.4875) (xy 11.7875 21.4875)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))
    (segment (start 10.32 20.28) (end 10.12 20.28) (width .02) (layer "F.Cu") (net 0))
    (gr_circle (center 30 30) (end 30.12497 30) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))
    )''').encode()
    inv=inventory(raw);shapes=[from_wkb(inv['payloads'][r['geometry_sha256']]) for r in inv['objects'] if 'F.Cu' in r['layers']]
    mask=roi.raster(shapes,[9.97,19.97,11.83,21.53],300);pixels=np.zeros((*mask.shape,3),dtype=np.uint8);pixels[mask]=[255,0,0]
    image=tmp_path/'C01 input image λ.png';Image.fromarray(pixels).save(image)
    return raw,inv,image


@pytest.mark.parametrize('corruption',['mask','landmark_census'])
def test_actual_image_locator_reconstructs_pixels_landmarks_and_controls(tmp_path,corruption):
    from src.u03_board.crop_roi import CropLocation
    raw,inv,image=image_fixture(tmp_path)
    root=tmp_path/'native';out=root/'data_board';out.mkdir(parents=True);cache=out/'source_wkb';cache.mkdir()
    rows=[r for r in inv['objects'] if 'F.Cu' in r['layers']];manifest=dict(source_sha256=digest(raw),objects=rows)
    (out/'source_manifest.json').write_bytes(canonical(manifest))
    for r in rows:(cache/(r['geometry_sha256']+'.wkb')).write_bytes(inv['payloads'][r['geometry_sha256']])
    (out/'inputs.json').write_bytes(canonical(dict(manifest_sha256=digest((out/'source_manifest.json').read_bytes()))))
    (tmp_path/'job.json').write_bytes(canonical(dict(crop=dict(path=str(image),sha256=digest(image.read_bytes())))))
    service=CropLocation(root);located=service.locate();verified=service.verify()
    assert located['facts']['located'] and verified['facts']['matched_landmarks']>=6
    assert len(verified['controls'])==3
    assert selection.for_root(root)['crop_sha256']==digest(image.read_bytes())
    assert service.audit('pcb_crop_locate')['mask_reconstructed_from_actual_input']
    assert service.audit('pcb_crop_verify')['metrics_recomputed']
    if corruption=='mask':
        altered=bytearray((out/'crop_mask.npy').read_bytes());altered[-1]^=1;(out/'crop_mask.npy').write_bytes(altered)
        with pytest.raises(ValueError,match='MASK_CHANGED'):service.audit('pcb_crop_verify')
    else:
        witness=json.loads((out/'crop_landmark_witness.json').read_bytes())
        required=next(r for r in witness['census'] if r['disposition']=='REQUIRED_VISIBLE_LANDMARK')
        required['disposition']='NOT_OBSERVABLE_FULLY_COVERED_SOURCE';required['coverage_source_ids']=['invented-cover']
        (out/'crop_landmark_witness.json').write_bytes(canonical(witness))
        sealed=json.loads((out/'crop_verified.json').read_bytes());sealed['landmark_witness_sha256']=digest((out/'crop_landmark_witness.json').read_bytes());(out/'crop_verified.json').write_bytes(canonical(sealed))
        with pytest.raises(ValueError,match='OBSERVABILITY_CHANGED'):service.audit('pcb_crop_verify')


def test_absolute_image_command_completes_35_native_gates_and_protects_outside(tmp_path):
    import os,signal,subprocess
    from src.pcb_data_abi.service import CLI,CLI_SHA
    from src.u03_board.custody import CROP,STEPS
    from src.native_inventory import inventory
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
        process=subprocess.Popen([str(root/'tools/Run_U03_Board.command'),'--input-dir',str(source),'--crop',str(image)],cwd=root,stdout=stream,stderr=subprocess.STDOUT)
        try:code=process.wait(timeout=360)
        except subprocess.TimeoutExpired:
            process.send_signal(signal.SIGINT);process.wait(timeout=30);pytest.fail('Image U03 timed out; retained '+str(log))
    assert code==0,log.read_text()[-14000:]
    events=[]
    for line in log.read_text().splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    event=next(r for r in events if r.get('status')=='COMPLETE_MACHINE_AUDITED_U03_EXPORT');job=Path(event['job']);session=job/'native'
    receipt=json.loads((session/'U03_RECEIPT.json').read_bytes());expected=[*STEPS[:3],*CROP,*STEPS[3:]]
    assert receipt['operations']==expected and len(expected)==35
    assert len(json.loads((session/'MACHINE_RECEIPT.json').read_bytes())['proofs'])==35
    assert receipt['selection']['crop_sha256']==digest(image.read_bytes())
    assert (Path(json.loads((job/'job.json').read_bytes())['crop']['path'])).read_bytes()==image.read_bytes()
    candidate=Path(json.loads((session/'data_output/pcb_kicad_write.json').read_bytes())['board'])
    changed=inventory(candidate.read_bytes())
    # Locate the original outside circle by its immutable native bytes.
    fragment=b'(gr_circle (center 30 30) (end 30.12497 30) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))'
    before_circle=next(r for r in inv['objects'] if raw[slice(*r['source_span'])]==fragment)
    assert before_circle['geometry_sha256'] in {r['geometry_sha256'] for r in changed['objects'] if r['kind']=='gr_circle'}
    report=(session/'U03_REPORT.md').read_text()
    assert str(image) in report and '--crop' in report and '35 native gates' in report
    assert json.loads((session/'adapter_stopped.json').read_bytes())['status']=='STOPPED'
