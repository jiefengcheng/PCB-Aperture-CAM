"""U05 retained custody, source admission, alias/contact and actual native guards."""
import copy,json,os,subprocess
from pathlib import Path
import pytest
from shapely import to_wkb,from_wkb
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.u05_board.store import ReadOnlyStore,OverlayStore
from src.u05_board.junctions import NativeSpindleAdapter,JunctionGates,parameters
from src.u05_board.scene import admit


def scene_fixture(tmp_path,aliases=False,inclusive=False):
    store=ArtifactStore(tmp_path/'runtime');objects=[]
    def row(sid,kind,g,**md):
        ref=store.put('geometry',to_wkb(g));r=dict(source_id=sid,kind=kind,original_ref=ref,geometry_ref=ref,metadata=dict(native_source_ids=[sid],**md));objects.append(r);return r
    row('route','trace',LineString([(-.6,0),(.6,0)]).buffer(.025,quad_segs=64),native_route_ref={'qualified':'unit-fixture'},land_ids=[])
    row('left','circle',Point(-.6,0).buffer(.2,quad_segs=64),qualified_land=True,alias_source_ids=['left','left_alias'] if aliases else ['left'])
    row('right','circle',Point(.6,0).buffer(.2,quad_segs=64),qualified_land=True,alias_source_ids=['right'])
    if aliases:row('left_alias','circle',Point(-.6,0).buffer(.2,quad_segs=64),qualified_land=True,alias_source_ids=['left','left_alias'])
    scene=dict(source_sha256='a'*64,frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=[-3,-3,3,3],objects=objects,findings=[],lineage=[],acceptance=dict(owner='PENDING_USER'))
    scene,report=admit(store,scene,None);return store,scene,report


def plan_fixture(tmp_path,aliases=False):
    store,scene,report=scene_fixture(tmp_path,aliases);adapter=NativeSpindleAdapter();scene_ref=store.put_json('scene',scene);policy=dict(stage='t05',parameters=parameters());bounds=dict(max_source_objects=len(scene['objects']),max_targets=1,max_evaluations=4,max_output_bytes=10000000,max_seconds=300)
    details=adapter.plan(store,scene,policy,dict(stage='t05',scene_ref=scene_ref,source_ids=report['target_ids']),bounds);plan=dict(stage='t05',profile_id='unit-u05-spindle',scene_ref=scene_ref,policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details)
    return store,scene,policy,plan,adapter


def test_overlay_never_writes_retained_store_and_detects_corruption(tmp_path):
    old=ArtifactStore(tmp_path/'old');ref=old.put('geometry',b'bound');before={p:p.stat().st_mtime_ns for p in (tmp_path/'old').rglob('*') if p.is_file()};new=OverlayStore(tmp_path/'new',tmp_path/'old')
    assert new.get(ref)==b'bound' and new.put('geometry',b'bound')==ref
    assert not (tmp_path/'new/artifacts'/ref['artifact_id']).exists()
    assert before=={p:p.stat().st_mtime_ns for p in (tmp_path/'old').rglob('*') if p.is_file()}
    with pytest.raises(ValueError,match='WRITE_FORBIDDEN'):new.predecessor.put('geometry',b'bad')
    (tmp_path/'old/artifacts'/ref['artifact_id']).write_bytes(b'corrupt')
    with pytest.raises(ValueError):new.get(ref)


def test_verified_alias_does_not_falsely_hide_its_own_land(tmp_path):
    store,scene,policy,plan,adapter=plan_fixture(tmp_path,True)
    assert plan['details']['routes'][0]['land_ids']==['left','right']
    candidate=adapter.run(store,scene,policy,plan,lambda _:None)
    assert candidate['coverage']['grown']==1
    check=adapter.verify(store,scene,policy,plan,candidate,{'scope':'complete-source-and-all-patches'},lambda _:None)
    assert check['passed'] and check['removed_area_mm2']<=1e-12
    assert candidate['protected_source_refs']=={r['source_id']:r['geometry_ref'] for r in scene['objects']}


def test_alias_conflict_rejects_even_if_broad_owner_would_cover_it(tmp_path):
    store,scene,policy,plan,adapter=plan_fixture(tmp_path,True)
    row=next(r for r in scene['objects'] if r['source_id']=='left_alias');row['geometry_ref']=store.put('geometry',to_wkb(Point(-.6,0).buffer(.21,quad_segs=64)))
    with pytest.raises(ValueError,match='ALIAS'):adapter.plan(store,scene,policy,dict(stage='t05',scene_ref=plan['scene_ref'],source_ids=['route']),plan['details']['bounds'])


def test_filled_inclusive_gap_cannot_invent_original_contact(tmp_path):
    store,scene,_=scene_fixture(tmp_path);route=scene['objects'][0];trace=box(-.05,-.05,.05,.05);route['original_ref']=route['geometry_ref']=store.put('geometry',to_wkb(trace))
    support=box(-.3,-.1,-.15,.1).union(box(.15,-.1,.3,.1));ref=store.put('geometry',to_wkb(support));current=store.put('geometry',to_wkb(box(-.3,-.1,.3,.1)));scene['objects']= [route,dict(source_id='inclusive',kind='inclusive_rectangle',original_ref=ref,geometry_ref=current,metadata=dict(native_source_ids=[],qualified_land=True,alias_source_ids=['inclusive']))]
    _,report=admit(store,scene,None);assert report['target_ids']==[] and report['routes'][0]['land_ids']==[]


def test_complete_window_crossing_stays_whole_and_fixed(tmp_path):
    store,scene,_=scene_fixture(tmp_path);scene['viewport_mm']=[-.85,-.3,.85,.3]
    _,report=admit(store,scene,None);assert report['target_ids']==[] and report['routes'][0]['disposition']=='KEEP_COMPLETE_WINDOW_BOUNDARY'


def test_new_current_contact_without_original_contact_is_not_selected(tmp_path):
    store,scene,_=scene_fixture(tmp_path);land=next(r for r in scene['objects'] if r['source_id']=='left');land['original_ref']=store.put('geometry',to_wkb(Point(-2,0).buffer(.1,quad_segs=64)))
    _,report=admit(store,scene,None);assert 'left' not in report['routes'][0]['land_ids']


def test_fixed_spindle_policy_cannot_be_relaxed(tmp_path):
    store,scene,policy,plan,adapter=plan_fixture(tmp_path);policy['parameters']['hard_gap_mm']=.001
    with pytest.raises(ValueError):adapter.plan(store,scene,policy,dict(stage='t05',scene_ref=plan['scene_ref'],source_ids=['route']),plan['details']['bounds'])


def test_operation_local_replay_cannot_forge_KEEP_or_drop_source(tmp_path):
    store,scene,policy,plan,adapter=plan_fixture(tmp_path);g=JunctionGates.__new__(JunctionGates);g.store=store;g.adapter=adapter;ref=store.put_json('plan',plan);g.context=lambda:(scene,policy,plan,ref)
    c=g.reconstruct();assert g.check_candidate(c)['passed']
    for change in ('keep','missing','source','policy'):
        bad=copy.deepcopy(c)
        if change=='keep':bad['decisions'][0]['status']='KEEP'
        elif change=='missing':bad['decisions']=[]
        elif change=='source':bad['protected_source_refs']={}
        else:bad['policy_ref']=dict(c['policy_ref'],sha256='0'*64)
        with pytest.raises(ValueError,match='FULL_RECONSTRUCTION_FAILED'):g.check_candidate(bad)
    path=store.root/'artifacts'/g._replay_ref['artifact_id'];path.write_bytes(b'corrupt')
    with pytest.raises(ValueError):g.reconstruct()


def test_native_append_preserves_every_predecessor_node_and_checks_actual_contours(tmp_path):
    from src.u05_board.export import U05DataService
    from src.pcb_data_abi import board_native as native
    s=U05DataService.__new__(U05DataService);s.raw=b'(kicad_pcb (version 20241229) (generator pcbnew) (gr_poly (pts (xy 0 0) (xy 1 0) (xy 1 1) (xy 0 1)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu")))';s.targets={'patch':box(1,0,1.2,.2)}
    body=s.native_body();assert s.native_check(body)['all_U04_nodes_equal']
    import sexpdata
    root=sexpdata.loads(body.decode());root[1].append([sexpdata.Symbol('corruption'),'1'])
    with pytest.raises(ValueError,match='U04_NATIVE_NODE_CHANGED'):s.native_check(native.board_bytes(root))


def test_operation_order_rejects_a_skipped_gate(tmp_path):
    from src.u05_board.custody import require_operation,STEPS
    (tmp_path/'U05_SEQUENCE.json').write_bytes(canonical(dict(operations=list(STEPS),accepted=[])))
    require_operation(tmp_path,STEPS[0])
    with pytest.raises(ValueError,match='OPERATION_ORDER'):require_operation(tmp_path,'t05_run')


def test_original_historical_spindle_contract_is_unchanged():
    from src.junction_spindle_stage import CONTRACT
    assert (CONTRACT.barrier_gap_mm,CONTRACT.construction_gap_mm,CONTRACT.hard_gap_mm)==(.02011,.02010,.02000)
    assert CONTRACT.radius_scales==(1.,.75,.5,.25) and CONTRACT.buffer_quad_segs==64


def test_native_transport_retains_raw_stdout_and_stderr_bytes(tmp_path,monkeypatch):
    from tools import pcb_u05_board_run as runner
    (tmp_path/'attempts').mkdir()
    class FakeProcess:
        returncode=0
        def __init__(self,argv,**kwargs):self.request=json.loads(Path(argv[-1]).read_bytes())
        def communicate(self,timeout):return canonical(dict(self.request,status='OK',result=dict(facts=dict(passed=True)),error=None)),b'raw diagnostic bytes\n'
    monkeypatch.setattr(runner.subprocess,'Popen',FakeProcess)
    attempt,result=runner.native(tmp_path,0,'u04_predecessor_verify',30)
    assert result['facts']['passed']
    assert (tmp_path/'attempts'/attempt/'abi/stderr.log').read_bytes()==b'raw diagnostic bytes\n'
    from tools.t01_native_route import verify_attempt
    assert verify_attempt(tmp_path/'attempts'/attempt)['status']=='PASS_RECEIPT_INTEGRITY'


def test_native_support_is_existing_owner_only_and_does_not_change_union(tmp_path):
    from src.u05_board.export import export_region,NATIVE_OWNER_OVERLAP_MM
    from src.junction_spindle_stage import prepare_spindle_context,fit_spindle_blend
    trace=LineString([(-.5,0),(.1,0)]).buffer(.02,quad_segs=64);land=Point(0,0).buffer(.15,quad_segs=64);owner,r,domain=prepare_spindle_context(trace,[land],box(-2,-2,2,2));best,_=fit_spindle_blend(owner,r,domain,[]);assert best
    region,support=export_region(best['addition'],owner,domain)
    assert support.area>0 and support.difference(owner).area<=1e-12
    assert owner.union(region).symmetric_difference(owner.union(best['addition'])).area<=1e-12
    from src.pcb_data_abi.geometry import CIRCLE_TOLERANCE_MM,POLYGON_TOLERANCE_MM
    assert region.difference(domain).area<=1e-12 and NATIVE_OWNER_OVERLAP_MM==2*max(CIRCLE_TOLERANCE_MM,POLYGON_TOLERANCE_MM)


def test_native_export_constructor_accounts_for_support_and_all_contour_parts(tmp_path,monkeypatch):
    import src.u05_board.export as export
    from types import SimpleNamespace
    store,scene,policy,plan,adapter=plan_fixture(tmp_path);candidate=adapter.run(store,scene,policy,plan,lambda _:None);base=tmp_path/'before.kicad_pcb';base.write_bytes(b'(kicad_pcb (version 20241229) (generator pcbnew))')
    gates=SimpleNamespace(root=tmp_path,store=store,predecessor=dict(kicad=str(base)),adapter=adapter,validate_verification=lambda:candidate,context=lambda:(scene,policy,plan,store.put_json('plan',plan)))
    monkeypatch.setattr(export,'JunctionGates',lambda root:gates)
    service=export.U05DataService(tmp_path)
    assert service.targets and service.normalization
    assert all(not n['physical_union_changed'] and n['existing_owner_support_area_mm2']>0 for n in service.normalization)
    assert service.native_check(service.native_body())['junction_parts']==len(service.targets)


def test_completion_event_can_carry_a_receipt_status_without_conflict(capsys):
    from tools.pcb_u05_board_run import progress
    progress('COMPLETE_MACHINE_AUDITED_U05_EXPORT',status='PASS_U05_RETAINED_CONTINUATION_EXPORT',owner='PENDING_USER')
    value=json.loads(capsys.readouterr().out)
    assert value['status']=='COMPLETE_MACHINE_AUDITED_U05_EXPORT' and value['owner']=='PENDING_USER'


def test_actual_topology_uses_direct_physical_union_not_subtracted_roundoff():
    from src.u05_board.export import actual_spindle_check
    from src.junction_spindle_blend import check_spindle
    owner=box(0,0,.1,1);region=box(.09,.4,.2,.6);exact=region.difference(owner)
    # Mimic a floating intersection leaving a microscopic disconnected sliver
    # in the derived delta while the actual exported contour remains connected.
    delta=box(.1000000000000001,.4,.100001,.6).union(box(.100001,.4,.2,.6))
    assert exact.symmetric_difference(delta).area<1e-12
    assert 'DISCONNECTED_OR_INVALID_CANDIDATE' in check_spindle(owner,owner.union(delta),delta,box(-1,-1,2,2),[])['failures']
    assert actual_spindle_check(owner,[region],delta,box(-1,-1,2,2),[])['passed']


def test_actual_union_still_rejects_real_disconnection_delta_and_hard_gap():
    from src.u05_board.export import actual_spindle_check
    owner=box(0,0,.1,1);region=box(.09,.4,.2,.6);delta=region.difference(owner);domain=box(-1,-1,2,2)
    q=actual_spindle_check(owner,[box(.11,.4,.2,.6)],box(.11,.4,.2,.6),domain,[])
    assert 'DISCONNECTED_OR_INVALID_CANDIDATE' in q['failures']
    assert 'DELTA_MISMATCH' in actual_spindle_check(owner,[region],box(.12,.4,.2,.6),domain,[])['failures']
    assert any(f.startswith('FOREIGN_CLEARANCE') for f in actual_spindle_check(owner,[region],delta,domain,[('foreign',box(.21999,.4,.3,.6))])['failures'])


def context_fixture(tmp_path):
    old,scene,policy,plan,adapter=plan_fixture(tmp_path)
    g=JunctionGates.__new__(JunctionGates);g.store=OverlayStore(tmp_path/'new',old.root);g.scene=scene;g.selection=None;g.binding={'fixture':'bound'};g.adapter=adapter;g.out=tmp_path/'gates';g.out.mkdir()
    plan=dict(plan,binding=g.binding);saved=dict(plan_ref=g.store.put_json('plan',plan),plan=plan)
    for n,value in [('t05_inspect',{}),('t05_admit',{}),('t05_plan',saved)]: (g.out/(n+'.json')).write_bytes(canonical(value))
    g.inspection=lambda:(scene,{'target_ids':['route']})
    return g,scene


def test_context_reuses_only_operation_local_exact_plan_and_rehashes_operands(tmp_path,monkeypatch):
    g,scene=context_fixture(tmp_path);original=g.adapter.plan;calls=[]
    def counted(*a,**k):calls.append(1);return original(*a,**k)
    monkeypatch.setattr(g.adapter,'plan',counted)
    assert g.context()==g.context() and len(calls)==1
    ref=scene['objects'][0]['geometry_ref'];path=g.store.predecessor.root/'artifacts'/ref['artifact_id'];stat=path.stat();path.write_bytes(b'altered');os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
    with pytest.raises(ValueError):g.context()


def test_context_memo_rejects_receipt_changes_and_internal_mutation(tmp_path):
    g,_=context_fixture(tmp_path);g.context();g._context_value[0]['tampered']=True
    with pytest.raises(ValueError,match='CONTEXT_CACHE_MUTATED'):g.context()
    g,_=context_fixture(tmp_path/'other');g.context();p=g.out/'t05_plan.json';saved=json.loads(p.read_bytes());saved['plan']['profile_id']='changed';p.write_bytes(canonical(saved))
    with pytest.raises(ValueError,match='PLAN_CHANGED'):g.context()


def test_atomic_readonly_open_keeps_kind_hash_symlink_and_file_type_guards(tmp_path):
    old=ArtifactStore(tmp_path/'old');ref=old.put('geometry',b'qualified');view=ReadOnlyStore(old.root);path=old.root/'artifacts'/ref['artifact_id']
    assert view.get(ref,kind='geometry')==b'qualified'
    with pytest.raises(ValueError):view.get(ref,kind='scene')
    path.unlink();target=tmp_path/'elsewhere';target.write_bytes(b'qualified');path.symlink_to(target)
    with pytest.raises(ValueError,match='unsafe|'+ref['artifact_id']):view.get(ref)
    path.unlink();path.mkdir()
    with pytest.raises(ValueError):view.get(ref)


def test_prepared_spindle_context_rehashes_bytes_without_decoding_again(tmp_path,monkeypatch):
    store,scene,policy,plan,adapter=plan_fixture(tmp_path);adapter._context(store,scene,policy,plan['details'])
    import src.stage_abi.runtime as runtime
    monkeypatch.setattr(runtime,'operands',lambda *a:(_ for _ in ()).throw(AssertionError('duplicate decode')))
    adapter._context(store,scene,policy,plan['details'])
    ref=scene['objects'][0]['geometry_ref'];(store.root/'artifacts'/ref['artifact_id']).write_bytes(b'corrupt')
    with pytest.raises(ValueError):adapter._context(store,scene,policy,plan['details'])


def test_two_machine_evaluations_must_match_and_use_distinct_processes():
    from tools.pcb_u05_board_run import matching_audits
    proof={'status':'PASS','checks':[{'passed':True}]};rows=[dict(pid=101,proof=proof),dict(pid=102,proof=copy.deepcopy(proof))]
    assert matching_audits(rows)==proof
    for bad in ([rows[0],rows[0]],[rows[0],dict(pid=102,proof={'status':'FAIL'})],[rows[0]]):
        with pytest.raises(ValueError):matching_audits(bad)
