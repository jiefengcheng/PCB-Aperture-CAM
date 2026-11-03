"""Whole-board admission, sparse execution equivalence and closed U03 routes."""
import copy,json,random
from pathlib import Path
import pytest
from shapely.geometry import LineString,box,Point
from shapely import to_wkb
from src.native_inventory import inventory
from src.stage_abi.store import canonical,digest
from src.u03_board.source import qualify,require_admitted
from src.u03_board.solver import solve
from src.u03_board.checker import IncrementalWidthScene
from src.prepared_width_scene import PreparedWidthScene
from src.bounded_width_solver import solve_width_scales
from src.source_offset_width import FAMILY


def source_case(nodes):
    raw=('(kicad_pcb (version 20241229) (layers (0 "F.Cu" signal) (31 "B.Cu" signal)) '+' '.join(nodes)+')').encode()
    inv=inventory(raw);rows=inv['objects']
    import sexpdata
    from src.native_reference import one
    for r in rows:
        a,b=r['source_span'];node=sexpdata.loads(raw[a:b].decode());r['trace_width_mm']=float(one(node,'width',[0])[0])
    blobs={r['id']:inv['payloads'][r['geometry_sha256']] for r in rows}
    return raw,rows,blobs


def test_mixed_width_and_branch_boundaries_keep_every_native_part():
    raw,rows,blobs=source_case(['(segment (start 0 0) (end 1 0) (width .1) (layer "F.Cu"))',
        '(segment (start 1 0) (end 2 0) (width .1) (layer "F.Cu"))',
        '(segment (start 1 0) (end 1 1) (width .1) (layer "F.Cu"))',
        '(segment (start 2 0) (end 3 0) (width .2) (layer "F.Cu"))'])
    q=qualify(raw,rows,blobs,blobs);require_admitted(q)
    assert q['trace_occurrences']==4 and len(q['admitted_paths'])==3
    assert sorted(s for p in q['admitted_paths'] for s in p['source_ids'])==sorted(blobs)
    assert all(p['original_native_source_members_retained'] for p in q['admitted_paths'])
    assert any(p['original_width_transition_ports'] for p in q['admitted_paths'])
    # Exercise the actual evidence boundary, including paired junction tuples.
    assert json.loads(canonical(q))==q


def test_source_evidence_conversion_does_not_relax_shared_artifact_contract():
    from src.u03_board.source import route_evidence
    from src.stage_abi.contracts import StageABIError
    original={'paired_continuations':[('source-a','source-b')]}
    with pytest.raises(StageABIError):canonical(original)
    assert route_evidence(original)=={'paired_continuations':[['source-a','source-b']]}
    for value in ({'unsupported':{1,2}}, {'unsupported':object()}, {'number':float('nan')}):
        with pytest.raises(StageABIError):route_evidence(value)


def test_native_rejection_retains_actual_stderr_traceback(tmp_path):
    import subprocess,sys
    root=Path(__file__).resolve().parents[1];session=tmp_path/'native';session.mkdir()
    request=tmp_path/'request.json';request.write_bytes(canonical(dict(abi_version='pcb-u03-board/1',request_id='negative',operation='unexposed')))
    p=subprocess.run([sys.executable,'-B',str(root/'tools/pcb_u03_board_abi.py'),'--session',str(session),'--input',str(request)],cwd=root,capture_output=True)
    response=json.loads(p.stdout)
    assert p.returncode==2 and response['status']=='REJECTED' and response['result'] is None
    assert 'U03_OPERATION_NOT_EXPOSED' in response['error']['message']
    assert b'Traceback (most recent call last)' in p.stderr and b'U03_OPERATION_NOT_EXPOSED' in p.stderr


def test_whole_board_ABI_inspection_exhausts_more_than_1000_targets(tmp_path):
    from src.stage_abi.store import ArtifactStore
    from src.stage_abi.service import StageService
    from src.stage_abi.registry import TrustedRegistry
    from src.u03_board.inspection import inspect_all,validate,aggregate
    from src.stage_abi.width import WidthAdapter,width_parameters
    from src.stage_abi import ABI_VERSION
    store=ArtifactStore(tmp_path/'runtime');g=store.put('geometry',to_wkb(box(0,0,1,1)))
    ids=[f'source-{i:04d}' for i in range(2371)]
    scene=store.put_json('scene',dict(source_sha256='a'*64,frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=[-1,-1,2,2],
        objects=[dict(source_id=s,kind='fixed_source',original_ref=g,geometry_ref=g,metadata={}) for s in ids],findings=[],lineage=[],acceptance={}))
    policy=store.put_json('policy',dict(stage='t04',parameters=width_parameters()));bounds=store.put_json('bounds',dict(max_source_objects=len(ids),max_targets=len(ids),max_evaluations=1,max_output_bytes=100000,max_seconds=10));verifier=store.put_json('verifier',{})
    registry=dict(schema='stage-agent-registry/1',profiles={'fixture':dict(stage='t04',adapter='native-width-v1',policy_ref=policy,scene_refs=[scene],bounds_ref=bounds,verifier_ref=verifier)},authorization_refs=[],decision_refs=[])
    service=StageService(store,TrustedRegistry(store,registry),{'native-width-v1':WidthAdapter()});calls=[]
    def call(verb,payload):
        calls.append(payload)
        response=service.dispatch(dict(abi_version=ABI_VERSION,request_id='inspect-fixture',operation='t04_inspect',profile_id='fixture',scene_ref=scene,policy_ref=policy,plan_ref=None,authorization_ref=None,idempotency_key=None,payload=payload))
        assert response['status']=='OK',response
        return response['result']
    ref,count=inspect_all(store,ids,call);report=validate(store,ref)
    assert count==24 and {len(p['source_ids']) for p in calls}=={1000,371}
    assert len(report['records'])==2371 and report['selected_source_ids']==ids
    with pytest.raises(ValueError,match='INCOMPLETE|COVERAGE'):
        aggregate(store,ids,report['u03_complete_inspection_pages'][:-1])
    with pytest.raises(ValueError):aggregate(store,ids,report['u03_complete_inspection_pages']*2)


def test_geometric_parallel_membership_requires_clear_cross_section():
    nodes=['(segment (start 0 0) (end 1 0) (width .1) (layer "F.Cu"))','(segment (start 0 .3) (end 1 .3) (width .1) (layer "F.Cu"))']
    raw,rows,b=source_case(nodes);q=qualify(raw,rows,b,b)
    assert len(q['groups'])==1 and len(q['groups'][0]['members'])==2 and len(q['relations'])==1
    raw,rows,b=source_case(nodes+['(gr_poly (pts (xy .45 .12) (xy .55 .12) (xy .55 .18) (xy .45 .18)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))'])
    q=qualify(raw,rows,b,b)
    assert len(q['groups'])==2 and len(q['blocked_relations'])==1 and not q['relations']


def test_partial_coverage_never_suppresses_complete_trace():
    raw,rows,b=source_case(['(segment (start 0 0) (end 1 0) (width .1) (layer "F.Cu"))',
        '(gr_poly (pts (xy -.2 -.2) (xy .5 -.2) (xy .5 .2) (xy -.2 .2)) (stroke (width 0) (type solid)) (fill yes) (layer "F.Cu"))'])
    q=qualify(raw,rows,b,b);assert len(q['admitted_paths'])==1
    changed=dict(b);changed[rows[1]['id']]=to_wkb(box(-.2,-.2,1.2,.2))
    q=qualify(raw,rows,b,changed);assert not q['admitted_paths'] and q['classifications']=={'KEEP_FULLY_COVERED':1}


def test_changed_T03_trace_and_missing_source_cannot_be_admitted():
    raw,rows,b=source_case(['(segment (start 0 0) (end 1 0) (width .1) (layer "F.Cu"))'])
    with pytest.raises(ValueError,match='COMPLETE_CURRENT_SCENE'):qualify(raw,rows,b,{})
    with pytest.raises(ValueError,match='CHANGED_T03_ROUTES'):qualify(raw,rows,b,{rows[0]['id']:to_wkb(box(0,0,1,1))})


def test_arc_source_is_retained_without_fitting():
    raw,rows,b=source_case(['(arc (start 0 0) (mid .5 .5) (end 1 0) (width .1) (layer "F.Cu"))'])
    q=qualify(raw,rows,b,b);require_admitted(q)
    assert q['native_rows'][0]['kind']=='arc' and len(q['native_rows'][0]['route_points_mm'])>2
    assert q['admitted_paths'][0]['primitive_trimming']=='NONE'


def test_native_arc_plot_identity_allows_only_bounded_grid_endpoint_rounding(tmp_path):
    from gerbonara import graphic_objects as go
    from gerbonara.apertures import CircleAperture
    from gerbonara.utils import MM
    from src.stage_abi.store import ArtifactStore
    from src.u03_board.export import U03DataService
    raw,rows,blobs=source_case(['(arc (start 48.034 69.439) (mid 48.05556 69.49203) (end 48.108 69.515) (width .0508) (layer "F.Cu"))'])
    sid=rows[0]['id'];store=ArtifactStore(tmp_path/'runtime');geometry=store.put('geometry',blobs[sid]);scene=store.put_json('scene',dict(objects=[dict(source_id=sid,geometry_ref=geometry)]))
    (tmp_path/'RECEIPT.json').write_bytes(canonical(dict(scene_ref=scene)))
    service=U03DataService.__new__(U03DataService);service.store=store;service.previous=tmp_path
    service.width_primitives={sid:dict(kind='arc',original_width_mm=.0508,start_mm=[48.034,69.439],end_mm=[48.108,69.515],fragment_sha256=digest(raw))}
    obj=go.Arc(x1=48.034,y1=-69.439,x2=48.108,y2=-69.514999,cx=.076048,cy=.000021,clockwise=False,aperture=CircleAperture(diameter=.0508,unit=MM),unit=MM)
    indices,proofs=service.source_trace_indices([obj]);assert indices=={0} and proofs[0]['endpoint_tolerance_mm']==.000002
    from dataclasses import replace
    with pytest.raises(ValueError,match='PLOT_MEMBERSHIP_FAILED'):service.source_trace_indices([replace(obj,y2=-69.514990)])


def test_nearly_straight_arc_requires_exact_isolated_native_plot_evidence(tmp_path):
    from gerbonara import graphic_objects as go
    from gerbonara.apertures import CircleAperture
    from gerbonara.utils import MM
    from src.stage_abi.store import ArtifactStore
    from src.u03_board.export import U03DataService
    from src.crop_circle_sources import verify_assets
    verify_assets()
    raw,rows,blobs=source_case(['(arc (start 42.126 69.82) (mid 42.13253 69.746) (end 42.139 69.672) (width .10008) (layer "F.Cu"))'])
    sid=rows[0]['id'];store=ArtifactStore(tmp_path/'runtime');geometry=store.put('geometry',blobs[sid]);scene=store.put_json('scene',dict(objects=[dict(source_id=sid,geometry_ref=geometry)]))
    (tmp_path/'RECEIPT.json').write_bytes(canonical(dict(scene_ref=scene)))
    service=U03DataService.__new__(U03DataService);service.store=store;service.previous=tmp_path;service.raw=raw;service.out=tmp_path/'data_output';service.out.mkdir();service.board=tmp_path/'custody.kicad_pcb';service.board.write_bytes(raw)
    a,b=rows[0]['source_span'];service.width_primitives={sid:dict(kind='arc',original_width_mm=.10008,start_mm=[42.126,69.82],end_mm=[42.139,69.672],fragment_sha256=digest(raw[a:b]))}
    obj=go.Line(x1=42.139,y1=-69.672,x2=42.126,y2=-69.82,aperture=CircleAperture(diameter=.10008,unit=MM,attrs=()),unit=MM,attrs={'.N':()})
    with pytest.raises(ValueError,match='ISOLATED_ARC_EVIDENCE_MISSING'):service.source_trace_indices([obj])
    service.allow_source_plot_probes=True
    indices,proofs=service.source_trace_indices([obj]);assert indices=={0}
    service.allow_source_plot_probes=False
    receipt=Path(proofs[0]['isolated_native_plot']);value=json.loads(receipt.read_bytes())
    assert value['execution']=='ACTUAL_PINNED_NATIVE_SOURCE_PLOT'
    assert proofs[0]['source_kind']=='arc' and proofs[0]['plot_kind']=='Line'
    assert proofs[0]['source_plot_hausdorff_mm']>.000025
    from dataclasses import replace
    with pytest.raises(ValueError,match='PLOT_MEMBERSHIP_FAILED'):service.source_trace_indices([replace(obj,attrs={'.N':('wrong',)})])
    # A replay must check exact retained bytes; altered probes cannot be
    # replaced, re-exported or accepted through a loose geometry tolerance.
    plot=receipt.parent/'gerbers/board-F_Cu.gbr';plot.write_bytes(plot.read_bytes()+b'G04 corrupt*\n')
    with pytest.raises(ValueError,match='ISOLATED_ARC_EVIDENCE_CHANGED'):service.source_trace_indices([obj])


@pytest.mark.parametrize('seed',range(6))
def test_sparse_solver_same_scales_and_final_upper_proofs_as_existing_solver(seed):
    rng=random.Random(seed);limits={str(i):rng.uniform(1.,1.5) for i in range(4)}
    def evaluate(v):return dict(passed=all(x<=limits[k] for k,x in v.items()) and sum(v.values())<5.3,failures=[])
    dense=solve_width_scales(limits,evaluate,geometry_family=FAMILY);sparse=solve(limits,evaluate)
    assert sparse['selected_scales']==dense['selected_scales']
    assert sparse['maximum_established']==dense['maximum_established']
    vector=dict(sparse['ledger_initial_scales'])
    for r in sparse['evaluations']:
        vector.update(r['changes']);assert digest(canonical(vector))==r['scales_sha256']


def test_sparse_vector_encoding_is_byte_equivalent_to_strict_canonical_json():
    from src.u03_board.solver import ScaleVectorEncoding
    from src.stage_abi.contracts import StageABIError
    vector={**{str(i):1. for i in range(371)},'路径':1.,'quote"\n':1.}
    encoded=ScaleVectorEncoding(vector);rng=random.Random(29)
    for i in range(120):
        changes={rng.choice(list(vector)):rng.choice([1.,1.5,1.000001,-0.,{'nested':[None,True,1,'λ']}])}
        vector.update(changes);encoded.update(changes)
        assert encoded.sha256()==digest(canonical(vector))
    with pytest.raises(StageABIError):encoded.update({'路径':float('nan')})


@pytest.mark.parametrize('token',['NaN','Infinity','-Infinity','1e309','-1e309'])
def test_width_report_decoder_preserves_strict_nonfinite_rejection(tmp_path,token):
    from src.stage_abi.store import ArtifactStore
    from src.stage_abi.contracts import StageABIError
    from src.u03_board.solver import read_width_check
    store=ArtifactStore(tmp_path/'runtime')
    ref=store.put('width-check',('{"passed":true,"nested":[{"number":'+token+'}]}').encode())
    for reader in (lambda:store.get_json(ref,kind='width-check'),lambda:read_width_check(store,ref)):
        with pytest.raises(StageABIError) as error:reader()
        assert error.value.code=='NONFINITE_NUMBER'


def test_width_report_decoder_and_ledger_still_check_actual_report_bytes(tmp_path):
    from src.stage_abi.store import ArtifactStore
    from src.stage_abi.contracts import StageABIError
    from src.u03_board.solver import read_width_check,validate_ledger
    store=ArtifactStore(tmp_path/'runtime');refs=[]
    def evaluate(scales):
        report=dict(passed=sum(scales.values())<2.4,nested=[None,True,'λ',{'n':1e308}])
        refs.append(store.put_json('width-check',report));return report
    solution=solve(['a','b'],evaluate);candidate=dict(solution=solution,check_refs=refs)
    assert validate_ledger(store,candidate)==len(refs)==solution['evaluation_count']
    assert read_width_check(store,refs[0])==store.get_json(refs[0],kind='width-check')
    bad=copy.deepcopy(candidate);bad['solution']['evaluations'][1]['scales_sha256']='0'*64
    with pytest.raises(ValueError,match='LEDGER_BINDING_CHANGED'):validate_ledger(store,bad)
    bad=copy.deepcopy(candidate);bad['check_refs'].pop()
    with pytest.raises(ValueError,match='LEDGER_COVERAGE_CHANGED'):validate_ledger(store,bad)
    (store.root/'artifacts'/refs[-1]['artifact_id']).write_bytes(b'{}')
    with pytest.raises(StageABIError) as error:validate_ledger(store,candidate)
    assert error.value.code=='ARTIFACT_CORRUPTED'


def test_incremental_checks_match_full_policy_across_accept_reject_and_revert():
    sources=[LineString([(0,y),(1,y)]).buffer(.05) for y in (0,.16,.33)]
    baseline=[dict(id=str(i),original=g,candidate=g,verified_original_width_mm=.1) for i,g in enumerate(sources)]
    fixed=[dict(id='land',geometry=box(1.1,-.2,1.4,.5))]
    inc=IncrementalWidthScene(baseline,fixed);full=PreparedWidthScene(baseline,fixed)
    rng=random.Random(4)
    for factors in [(1.,1.,1.),(1.5,1.,1.),(1.5,1.5,1.5),(1.1,1.,1.),*(tuple(rng.uniform(1,1.5) for _ in sources) for i in range(20)),(1.,1.,1.)]:
        traces=[dict(row,candidate=row['original'].buffer(.05*(factor-1)) if factor>1 else row['original']) for row,factor in zip(baseline,factors)]
        q=inc.check(traces,fail_fast=True);expected=full.check(traces,fail_fast=True)
        assert q['passed']==expected['passed'],(factors,q,expected)
    assert inc.check(baseline,materialize_scene=True)['passed']


@pytest.mark.parametrize('budget',[1024,512*1024**2])
def test_original_union_cache_preserves_complete_reports_and_full_checks(budget):
    cores=[LineString(points).buffer(.05) for points in ([(0,0),(1,0)],[(0,0),(0,1)],[(0,.13),(1,.13)])]
    baseline=[dict(id=str(i),original=g,candidate=g,verified_original_width_mm=.1) for i,g in enumerate(cores)]
    ring=Point(.5,.5).buffer(1.5,quad_segs=512).difference(Point(.5,.5).buffer(.9,quad_segs=512))
    fixed=[dict(id='complex-ring',geometry=ring)]
    cached=IncrementalWidthScene(baseline,fixed,original_union_cache_bytes=budget)
    direct=IncrementalWidthScene(baseline,fixed,original_union_cache_bytes=0)
    for factors in [(1.,1.,1.),(1.1,1.1,1.1),(1.2,1.2,1.2),(1.5,1.5,1.5),(1.08,1.12,1.07),(1.,1.,1.)]:
        traces=[dict(r,candidate=r['original'] if f==1 else r['original'].buffer(.05*(f-1))) for r,f in zip(baseline,factors)]
        assert cached.check(traces,fail_fast=True)==direct.check(traces,fail_fast=True)
        assert cached.original_union_cache_weight<=budget
    widened=[dict(r,candidate=r['original'].buffer(.005)) for r in baseline]
    assert cached.check(widened,materialize_scene=True)==direct.check(widened,materialize_scene=True)
    if budget>1024:
        assert cached.original_union_hits>0
        assert cached.original_union_compressed_hits>0
        assert cached.original_union_misses<direct.original_union_misses


def test_compressed_original_union_corruption_halts_without_recomputation():
    core=LineString([(0,0),(1,0)]).buffer(.05)
    ring=Point(.5,.5).buffer(1.5,quad_segs=512).difference(Point(.5,.5).buffer(.9,quad_segs=512))
    checker=IncrementalWidthScene([dict(id='trace',original=core,candidate=core,verified_original_width_mm=.1)],[dict(id='ring',geometry=ring)])
    candidate=core.buffer(.005);checker.other_original_union('trace',candidate)
    key=next(iter(checker.original_union_cache));codec,blob,sha,weight=checker.original_union_cache[key]
    assert codec=='zlib'
    checker.original_union_cache[key]=(codec,b'corrupted',sha,weight)
    misses=checker.original_union_misses
    with pytest.raises(ValueError,match='U03_ORIGINAL_UNION_CACHE_CHANGED'):checker.other_original_union('trace',candidate)
    assert checker.original_union_misses==misses


def test_union_window_rechecks_original_query_at_existing_clearance_boundary():
    from shapely.affinity import translate
    core=LineString([(0,0),(1,0)]).buffer(.05)
    neighbor=LineString([(0,.1251-1.2e-12),(1,.1251-1.2e-12)]).buffer(.05)
    baseline=[dict(id=str(i),original=g,candidate=g,verified_original_width_mm=.1) for i,g in enumerate((core,neighbor))]
    checker=IncrementalWidthScene(baseline,[])
    assert checker.check(baseline,fail_fast=True)['passed']
    # Model a sub-epsilon difference in the accelerated visibility result.
    checker.visible_cache['1']=(checker.cached_sha(neighbor),translate(neighbor,yoff=.4e-12))
    trial=[dict(baseline[0],candidate=core.buffer(.005)),baseline[1]]
    original=PreparedWidthScene(baseline,[]).check(trial,fail_fast=True)
    actual=checker.check(trial,fail_fast=True)
    assert actual['passed']==original['passed']==False
    assert checker.original_union_boundary_rechecks>0


def gates_fixture(tmp_path):
    from tests.test_u02_board import native_session
    adapter=native_session(tmp_path)
    for op in ('t03_inspect','t03_plan','t03_search','t03_verify','t03_compare','t03_review','t03_controls'):adapter.dispatch(op)
    policy=adapter.store.get_json(adapter.cap['policy_ref'],kind='policy');binding=adapter.store.get_json(policy['binding_ref'],kind='t01-binding')
    receipt=json.loads((tmp_path/'RECEIPT.json').read_bytes());receipt.update(binding_ref=policy['binding_ref'],source_sha256=binding['source_sha256'])
    (tmp_path/'RECEIPT.json').write_bytes(canonical(receipt))
    (tmp_path/'data_board').mkdir();manifest=adapter.store.get_json(binding['manifest_ref'],kind='native-manifest')
    (tmp_path/'data_board/source_manifest.json').write_bytes(canonical(manifest))
    from src.u03_board.adapter import WidthGates
    return WidthGates(tmp_path)


def test_complete_native_T01_T03_T04_ABI_pipeline_and_page_reconstruction(tmp_path):
    from src.u03_board.custody import T04
    gates=gates_fixture(tmp_path)
    results=[]
    for op in T04:results.append(gates.dispatch(op))
    assert results[3]['facts']['fresh_construction'] and results[4]['facts']['fresh_reconstruction']
    assert results[4]['facts']['groups']==1 and results[4]['facts']['changed_native_parts']==1
    assert len(results[-1]['controls'])==7


@pytest.mark.parametrize('machine',[False,True])
def test_U03_negative_compile_null_reaches_pending_audit(tmp_path,machine):
    from types import SimpleNamespace
    from tools.pcb_u03_board_operator import U03Operator
    from tools.u03_board_auto_operator import MachineOperator
    from tools.t01_board_route import BoardRoute
    cls=MachineOperator if machine else U03Operator
    raw=dict(abi_version='stage-agent-abi/1.0',request_id='negative',operation='t01_compile',status='REJECTED',result=None,error=dict(code='T01_ENGLISH_UNSUPPORTED',message='unsupported'))
    facts=BoardRoute.__new__(BoardRoute)._facts('t01_negative_compile',raw,2,tmp_path/'response.json')
    path=tmp_path/'response.json';path.write_bytes(canonical(raw));operator=cls.__new__(cls)
    operator.ui=tmp_path/'operator_ui';operator.ui.mkdir();operator.state_path=operator.ui/'current.json';operator.binding_blob=b'fixture'
    operator.info=lambda:dict(pending_audit=None,next_operation='t01_negative_compile')
    operator.client=SimpleNamespace(invoke=lambda *a:dict(error=None,result=dict(facts=facts,raw_response_path=str(path),raw_response_sha256=digest(path.read_bytes()))))
    result=operator.offer(operator.steps.index('t01_negative_compile'))
    assert result['status']==('MACHINE_AUDIT_REQUIRED' if machine else 'REVIEW_REQUIRED')
    assert result['total_slices']==len(cls.steps)==33 and operator.state()['status']=='REVIEW_REQUIRED'
    assert not list(operator.ui.glob('review-*.json'))


def test_U03_sequence_has_actual_T04_gates_and_no_later_stages():
    from src.u03_board.custody import STEPS,PREFIX,THROUGH_T03,THROUGH_T04,T03,T04
    from src.pcb_data_abi.board_custody import FILES
    from tools.u03_board_route import U03Route
    assert STEPS==(*PREFIX,*T03,*T04,*FILES) and len(STEPS)==33
    assert len(THROUGH_T03)==20 and len(THROUGH_T04)==28 and U03Route.STEPS==STEPS
    assert not any(op.startswith(('render_','t02_','t05_')) for op in STEPS)


def test_actual_terminal_route_closes_all_33_gates_and_exports(tmp_path):
    """Exercise checkpoint production and consumption through the real facade."""
    import os,signal,subprocess
    from src.crop_circle_sources import verify_assets
    from src.pcb_data_abi.service import CLI,CLI_SHA
    from src.u03_board.custody import STEPS,THROUGH_T04
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
        process=subprocess.Popen([str(root/'tools/Run_U03_Board.command'),'--input-dir',str(raw)],cwd=root,stdout=stream,stderr=subprocess.STDOUT)
        try:code=process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            process.send_signal(signal.SIGINT);process.wait(timeout=30)
            pytest.fail('Native synthetic U03 timed out; retained '+str(log))
    events=[]
    for line in log.read_text().splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    assert code==0,log.read_text()[-10000:]
    complete=next(e for e in events if e.get('status')=='COMPLETE_MACHINE_AUDITED_U03_EXPORT')
    job=Path(complete['job']);native=job/'native'
    journal=Path(json.loads((job/'TERMINAL_RUN.json').read_bytes())['journal'])
    result=json.loads((journal/'result.json').read_bytes())
    assert result['machine_audits']==len(STEPS)==33 and result['observation_audits']==0
    assert result['render_operations']==0 and result['owner']=='PENDING_USER'
    checkpoint=json.loads((native/'U03_CHECKPOINT.json').read_bytes())
    assert checkpoint['operations']==list(THROUGH_T04)
    assert {'u02_t03/t03_inspect.json','u02_t03/t03_search.json','u02_t03/t03_verify.json','u02_t03/t03_controls.json'}<=checkpoint['files'].keys()
    assert len(json.loads((native/'MACHINE_RECEIPT.json').read_bytes())['proofs'])==33
    exports=json.loads((native/'data_output/pcb_gerber_export.json').read_bytes())
    assert exports['facts']['layers']==9 and len(exports['output_sha256'])==18
    assert json.loads((native/'data_output/pcb_export_controls.json').read_bytes())['facts']['deliberate_controls']==3
    assert json.loads((native/'adapter_stopped.json').read_bytes())['status']=='STOPPED'


def test_U03_every_source_page_and_corrupt_remote_page_reject(tmp_path):
    from src.u03_board.paging import put,get
    from src.stage_abi.store import ArtifactStore
    from src.stage_abi.contracts import StageABIError
    store=ArtifactStore(tmp_path/'runtime');rows=[dict(source_id=str(i)) for i in range(237)];binding=dict(source_sha256='a'*64)
    ref=put(store,rows,binding=binding,kind='u03-width-sources')
    actual,index=get(store,ref,binding=binding,kind='u03-width-sources',identity=lambda r:r['source_id'])
    assert actual==rows and len(index['pages'])==3
    page=index['pages'][2]['page_ref'];(store.root/'artifacts'/page['artifact_id']).write_bytes(b'{}')
    with pytest.raises(StageABIError):get(store,ref,binding=binding,kind='u03-width-sources',identity=lambda r:r['source_id'])


def test_U03_rejects_forged_machine_proof_before_advancement(tmp_path):
    from tools.u03_board_route import MachineRoute
    folder=tmp_path/'audits/machine-001';folder.mkdir(parents=True);(folder/'proof.json').write_bytes(canonical(dict(status='PASS')))
    route=MachineRoute.__new__(MachineRoute);route.session=tmp_path;route.position=0;route.pending=dict(attempt_id='attempt');route.halted=False;route.audit_hashes={}
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):route._audit(dict(attempt_id='attempt',audit={'note':'generic success'}),{})
    assert route.halted and route.position==0


def test_U03_old_launcher_and_missing_mount_do_not_scan_input(tmp_path,monkeypatch):
    from tools import u03_board_jobs as jobs
    configure=jobs.configure
    monkeypatch.setattr(jobs,'configure',lambda:None);monkeypatch.setattr(jobs.jobs,'launcher_ready',lambda:{})
    monkeypatch.setattr(jobs.directory,'native_intake',lambda *a,**k:pytest.fail('Old launcher must not intake'))
    with pytest.raises(ValueError,match='UPDATE_REQUIRED'):jobs.intake('/not-scanned-by-client')
    def missing():raise RuntimeError('LACIE_WORKSPACE_UNAVAILABLE')
    monkeypatch.setattr(jobs,'require_storage',missing)
    with pytest.raises(RuntimeError,match='UNAVAILABLE'):configure()


def test_U03_runner_keeps_supervision_and_no_false_observations():
    root=Path(__file__).resolve().parents[1];text=(root/'tools/pcb_u03_board_run.py').read_text()
    assert 'adapter_health(thread,thread_error)' in text and 'traceback.format_exc()' in text
    assert 'owned.cancel()' in text and 'HALT_RECORD_WRITE_FAILED' in text
    assert "action='u03_directory_intake'" in text and 'len(operator.steps)' in text


def test_actual_native_width_write_reopen_export_and_corruption_controls(tmp_path,monkeypatch):
    from src.u03_board.custody import T04
    from src.u03_board.export import U03DataService
    from src.pcb_data_abi.crop import TEMPLATE
    from src.pcb_data_abi.board_geometry import export_reference
    from src.crop_circle_sources import verify_assets
    from shapely import from_wkb
    # This deliberately minimal synthetic board declares only two copper
    # layers. The production whole-board route still requires all nine layers.
    from src.pcb_data_abi import service as data_service
    from src.u03_board import export as width_export
    monkeypatch.setattr(data_service,'LAYERS',('F.Cu','B.Cu'))
    monkeypatch.setattr(width_export,'LAYERS',('F.Cu','B.Cu'))
    verify_assets();gates=gates_fixture(tmp_path)
    for op in T04:gates.dispatch(op)
    service=U03DataService.__new__(U03DataService);service.previous=tmp_path;service.out=tmp_path/'data_output';service.store=gates.store
    service.receipt=json.loads((tmp_path/'RECEIPT.json').read_bytes());service.raw=gates.raw;service.edit=TEMPLATE;service.versions={}
    t01=gates.store.get_json(service.receipt['candidate_ref'],kind='candidate');service.decisions=t01['decisions'];service.targets={d['source_id']:from_wkb(gates.store.get(d['candidate_ref'],kind='geometry')) for d in service.decisions}
    for d in service.decisions:
        if d['decision'] in ('GROW_COMPANION','ROUND_GROW_PRIORITY'):service.targets[d['source_id']]=export_reference(service.targets[d['source_id']])[0]
    service.before=service.out/'before/board.kicad_pcb';service.board=service.out/'candidate/board.kicad_pcb'
    service.width=json.loads((tmp_path/'u03_t04/t04_run.json').read_bytes())['result']['candidate'];service.width_targets={};service.width_primitives={}
    for c in service.width['construction']:
        if c['factor']>1:
            for p in c['primitives']:
                sid=p['source_id'];service.width_targets[sid]=from_wkb(gates.store.get(service.width['parts'][sid]['nominal_ref'],kind='geometry'));service.width_primitives[sid]=p
    assert service.write_kicad()['facts']['changed_native_trace_parts']==1
    assert service.verify_kicad()['facts']['passed']
    assert service.export_gerber()['facts']['native_export_exit']==0
    assert service.verify_gerber()['facts']['passed']
    assert len(service.controls()['controls'])==3
