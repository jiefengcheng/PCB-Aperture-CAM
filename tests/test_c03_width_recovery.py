"""Independent source-partition, explicit-selection and inherited-policy guards."""
import copy,json
from pathlib import Path
from unittest.mock import patch
import pytest
from shapely import STRtree
from shapely.geometry import box
from src.c03_width_recovery import exposed_runs,primary_groups
from src.c03_width_profile import marker,selected
from src.c03_input_family import specification
from src.trace_width_clearance import TraceWidthContract
from src.stage_abi.store import canonical,digest
ROOT=Path(__file__).resolve().parents[1]


def parent():
    edges=[dict(source_alias_ids=[f's{i}'],start_decimal_mm=[str(i),'0'],end_decimal_mm=[str(i+1),'0']) for i in range(3)]
    return dict(path_id='P',source_ids=['s0','s1','s2'],ordered_source_edges=edges,uniform_original_width_mm=.1,route_type='OPEN_UNIFORM_SOURCE_ROUTE')


def test_fixed_source_is_a_native_endpoint_not_a_cut():
    runs=exposed_runs([parent()],{'s1'},'source')
    assert [r['source_ids'] for r in runs]==[['s0'],['s2']]
    assert [r['terminal_points_decimal_mm'] for r in runs]==[[['0','0'],['1','0']],[['2','0'],['3','0']]]
    assert all(r['primitive_trimming']=='NONE' for r in runs)
    assert all(r['original_fixed_source_ports'][0]['fixed_source_id']=='s1' for r in runs)


def test_alias_fixed_disposition_cannot_be_split():
    p=parent();p['source_ids'].append('alias');p['ordered_source_edges'][1]['source_alias_ids'].append('alias')
    with pytest.raises(ValueError,match='ALIAS_ELIGIBILITY_CONFLICT'):exposed_runs([p],{'s1'},'source')


def test_runs_of_one_parent_share_a_hard_unit_even_when_remote():
    runs=exposed_runs([parent()],{'s1'},'source');paths={r['path_id']:r for r in runs};cores={runs[0]['path_id']:box(0,0,1,.1),runs[1]['path_id']:box(10,0,11,.1)};ids=['a','b'];byid=dict(zip(ids,cores.values()))
    groups,proof=primary_groups(paths,[],byid,STRtree(list(byid.values())),ids,cores,{})
    assert len(groups)==1 and len(groups[0]['members'])==2
    assert proof['hard_links'][0]['reason']=='ORIGINAL_TRACE_COMMON_SCALE'


@pytest.mark.parametrize('branch_contact',[False,True])
def test_only_native_longitudinal_overlap_couples_factors(branch_contact):
    from shapely.geometry import LineString
    paths={'A':dict(parent_route_id='P',source_ids=['a']),'B':dict(parent_route_id='Q',source_ids=['b'])}
    a=[[0.,0.],[2.,0.]];b=[[2.,0.],[3.,0.]] if branch_contact else [[0.,.06],[2.,.06]]
    byid={'a':LineString(a).buffer(.05),'b':LineString(b).buffer(.05)};cores=dict(A=byid['a'],B=byid['b'])
    native={'a':dict(kind='segment',route_points_mm=a,width_mm=.1),'b':dict(kind='segment',route_points_mm=b,width_mm=.1)}
    groups,proof=primary_groups(paths,[],byid,STRtree(list(byid.values())),['a','b'],cores,native)
    assert len(groups)==(2 if branch_contact else 1)
    assert len(proof['hard_links'])==(0 if branch_contact else 1)
    assert len(proof['unqualified_overlap_scale_links'])==(1 if branch_contact else 0)
    if not branch_contact:assert proof['hard_links'][0]['native_witnesses'][0]['longitudinal_overlap_mm']==2.


def test_source_matching_never_selects_width_family(tmp_path):
    assert selected(tmp_path) is False


def setup_job(tmp_path):
    root=tmp_path/'native';root.mkdir();spec,_,sha=specification()
    (tmp_path/'job.json').write_bytes(canonical(dict(inputs=dict(kicad=dict(sha256=spec['source_sha256'])),crop=dict(sha256=spec['crop_sha256']))))
    (root/'C03_INPUT_FAMILY.json').write_bytes(canonical(dict(schema='c03-input-family-selected/1',contract=spec,contract_sha256=sha)))
    (root/'C03_WIDTH_RECOVERY.json').write_bytes(canonical(marker()));return root


def test_explicit_marker_requires_exact_owner_source_crop_and_recipe(tmp_path):
    root=setup_job(tmp_path);assert selected(root)
    job=json.loads((tmp_path/'job.json').read_bytes());job['crop']['sha256']='0'*64;(tmp_path/'job.json').write_bytes(canonical(job))
    with pytest.raises(ValueError,match='JOB_SOURCE_OR_CROP_CHANGED'):selected(root)


def test_marker_boundary_or_blocked_target_tamper_rejects(tmp_path):
    root=setup_job(tmp_path);m=json.loads((root/'C03_WIDTH_RECOVERY.json').read_bytes());m['contract']['blocked']=[];(root/'C03_WIDTH_RECOVERY.json').write_bytes(canonical(m))
    with pytest.raises(ValueError,match='C03_WIDTH_SELECTION_CHANGED'):selected(root)


def test_marker_symlink_rejects(tmp_path):
    root=setup_job(tmp_path);p=root/'C03_WIDTH_RECOVERY.json';blob=p.read_bytes();p.unlink();t=tmp_path/'marker.json';t.write_bytes(blob);p.symlink_to(t)
    with pytest.raises(ValueError,match='C03_WIDTH_MARKER_UNSAFE'):selected(root)


def test_numeric_policy_and_all_original_blocked_targets_remain_fixed():
    c=TraceWidthContract();m=marker()['contract']
    assert (c.hard_gap_mm,c.construction_gap_mm,c.original_port_buffer_gap_mm,c.comparison_epsilon_mm,c.port_quad_segs)==(.02000,.02010,.02002,1e-12,128)
    assert m['width_scale']==[1,1.5] and m['blocked']==['T01:C028','T02:R304','T02:R305']
    assert m['boundary_policy']=='UNCHANGED_COMPLETE_MAXIMUM_ENVELOPE_AND_COMPLETE_COHORT'


@pytest.fixture(scope='module')
def native_case():
    from src.c03_width_recovery import qualify
    n=ROOT/'out/lacie_work/operator_routes/u04_board/managed/jobs/20261104T085910Z-114c2085c2584f278b4800f1c99f056c/native'
    def read(p):return json.loads(p.read_bytes())
    def artifact(r):
        b=(n/'runtime/artifacts'/r['artifact_id']).read_bytes();assert digest(b)==r['sha256'];return b
    binding=json.loads(artifact(read(n/'RECEIPT.json')['binding_ref']));raw=artifact(binding['source_ref']);manifest=read(n/'data_board/source_manifest.json');original={r['id']:(n/'data_board/source_wkb'/(r['geometry_sha256']+'.wkb')).read_bytes() for r in manifest['objects']};scene=json.loads(artifact(read(n/'u02_t03/t03_search.json')['candidate']['output_scene_ref']));current={r['source_id']:artifact(r['geometry_ref']) for r in scene['objects']};selection=read(n/'U03_SELECTION.json')
    report=qualify(raw,manifest['objects'],original,current,selection=selection)
    return raw,manifest,original,current,selection,report


def test_all_94_original_positive_identities_rederive_without_fixed_overlap(native_case):
    *_,report=native_case
    references=json.loads((ROOT/'out/crop_dynamic_tasks/c03_final_so_far_freeze_20261030_270/frozen/T04/CONSTRUCTION.json').read_bytes())
    runs={r['path']['path_id']:r['path'] for r in report['paths'] if r.get('path')}
    positive=[r for r in references if r['factor']>1]
    assert len(positive)==94
    fixed=set(report['reviewed_source_roles']['protected'])
    for r in positive:
        assert runs[r['component_id']]['source_ids']==sorted(r['complete_source_ids'])
        assert not fixed.intersection(r['complete_source_ids'])


def test_full_native_occurrence_partition_and_cohort_partition(native_case):
    *_,report=native_case
    members=[s for r in report['paths'] for s in (r['path']['source_ids'] if r.get('path') else r['source_ids'])]
    assert len(members)==len(set(members))==15858
    assert set(members)=={r['source_id'] for r in report['native_rows']}
    selected=['route:'+p['path_id'] for p in report['admitted_paths']]
    grouped=[s for g in report['groups'] for s in g['members']]
    assert len(grouped)==len(set(grouped)) and set(grouped)==set(selected)


def test_all_admitted_actual_1p5_envelopes_are_inside_unchanged_window(native_case):
    from src.source_offset_width import construct_source_offset_width
    from src.u03_board.selection import window
    raw,manifest,original,current,selection,report=native_case;region=window(selection);meta={r['id']:r for r in manifest['objects']}
    for p in report['admitted_paths']:
        record,_,_,core,g,envelope=construct_source_offset_width(raw,dict(component_id=p['path_id'],source_ids=p['source_ids']),meta,original,1.5)
        assert region.covers(envelope)
        assert g.covers(core) and envelope.covers(g)


def test_boundary_crossing_bottom_bundle_stays_held_as_a_complete_group(native_case):
    *_,report=native_case
    byid={r['path']['path_id']:r for r in report['paths'] if r.get('path')}
    assert byid['ER-4cd376d1f8699384']['disposition']=='KEEP_CROP_BOUNDARY'
    assert byid['ER-53f99f8f80927fa8']['disposition']=='KEEP_CROP_BOUNDARY'
    assert byid['ER-12cc490efa25a7c7']['disposition']=='KEEP_CROP_GROUP_BOUNDARY'
    assert byid['ER-a35532b6aa33a960']['disposition']=='KEEP_CROP_GROUP_BOUNDARY'
    assert not any('route:ER-12cc490efa25a7c7' in g['members'] for g in report['groups'])
    # The two auxiliary branches are not fused by end-cap contact. They retain
    # full-scene clearance obligations as separate source-native operations.
    assert byid['ER-3d072b34a242639f']['disposition']=='ADMIT_COMPLETE_NATIVE_ROUTE'
    assert byid['ER-3a78ddc887404085']['disposition']=='ADMIT_COMPLETE_NATIVE_ROUTE'
    assert all(r['native_witnesses'] for r in report['cohort_proof']['hard_links'] if r['reason']=='SOURCE_VERIFIED_LONGITUDINAL_OVERLAP_ONE_OPERATION')


def test_changed_native_trace_cannot_enter_recovery(native_case):
    from src.c03_width_recovery import qualify
    raw,manifest,original,current,selection,report=native_case;bad=dict(current);bad[report['native_rows'][0]['source_id']]=b'changed'
    with pytest.raises(ValueError,match='CHANGED_SOURCE_PATH_UNSUPPORTED'):qualify(raw,manifest['objects'],original,bad,selection=selection)


def test_actual_export_floor_keeps_the_construction_report_and_its_failures():
    from src.c03_width_export import actual_hard_floor
    r=dict(traces=[dict(trace_id='t',failures=[],pairs=[dict(neighbor_id='n',new_exposed_to_visible_neighbor_gap_mm=.02005)])],passed=False,failures=[dict(reason='NEW_EXPOSED_COPPER_BELOW_CONSTRUCTION_GUARD')])
    q=actual_hard_floor(r)
    assert q['passed'] and q['hard_gap_mm']==.02000
    assert q['construction_guard_report']is r and not r['passed'] and r['failures']
    r['traces'][0]['pairs'][0]['new_exposed_to_visible_neighbor_gap_mm']=.01999
    assert not actual_hard_floor(r)['passed']


def test_actual_export_floor_never_waives_removed_source_core():
    from src.c03_width_export import actual_hard_floor
    r=dict(traces=[dict(trace_id='t',failures=['ORIGINAL_TRACE_CORE_REMOVED'],pairs=[])])
    assert not actual_hard_floor(r)['passed']


def test_native_append_preserves_every_prior_node_and_detects_mutation():
    import sexpdata
    from src.c03_width_export import WidthExport
    from src.pcb_data_abi import board_native
    e=object.__new__(WidthExport);e.raw=b'(kicad_pcb (version 20241229) (property "protected" "original"))';e.targets={'source':box(1,1,1.1,1.2)}
    body=e.native_body();q=e.native_check(body)
    assert q['passed']and q['all_U05_native_nodes_equal']and q['width_parts']==1
    tree=sexpdata.loads(body.decode());tree[2].append('changed')
    with pytest.raises(ValueError,match='PROTECTED_U05_NATIVE_NODE_CHANGED'):e.native_check(board_native.board_bytes(tree))


def test_append_model_preserves_prior_widths_in_independent_factor_ledger():
    from src.c03_width_continuation import WidthContinuation
    x=object.__new__(WidthContinuation);x.prior_factors={'prior':1.5}
    a=dict(reference_width_obligations=[dict(reference_id='old',required_factor=1.5,required_positive=True,source_ids=['prior']),dict(reference_id='new',required_factor=1.4,required_positive=True,source_ids=['next'])]);c=dict(construction=[dict(factor=1.4,complete_source_ids=['next'])])
    q=x.coverage(a,c)
    assert q['met']==2 and q['previous_width_factors_preserved']
    c['construction'].append(dict(factor=1.,complete_source_ids=['prior']))
    q=x.coverage(a,c)
    assert q['met']==2 and q['records'][0]['actual_factors']=={'prior':1.5}


def test_complete_page_families_keep_all_records_and_short_artifact_kinds(tmp_path):
    from src.c03_width_qualification import Gates
    from src.stage_abi.store import ArtifactStore
    from types import SimpleNamespace
    g=object.__new__(Gates);g.wc=SimpleNamespace(original_raw=b'original',raw=b'current',store=ArtifactStore(tmp_path/'store'))
    sets={'source_manifest':[{'source_id':str(i)}for i in range(205)],'current_scene_sources':[{'source_id':'current'}],'source_comparisons':[{'source_id':'comparison'}]}
    pages=g.pages(sets);g.check_pages(pages,sets)
    index=g.wc.store.get_json(pages['references']['source_manifest'],kind=pages['references']['source_manifest']['artifact_id'].split(':')[0]);assert len(index['pages'])==3
    broken=copy.deepcopy(pages);broken['references']['source_manifest']=pages['references']['source_comparisons']
    with pytest.raises(Exception):g.check_pages(broken,sets)


def test_native_worker_gate_order_cannot_skip_or_repeat(tmp_path):
    from src.c03_width_qualification import Gates
    g=object.__new__(Gates);g.root=tmp_path
    g.require_operation('retained_prefix_verify')
    with pytest.raises(ValueError,match='AUDITED_OPERATION_ORDER_REQUIRED'):g.require_operation('width_construct')
