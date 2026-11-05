"""Scope, complete source custody, reconstruction and cap corruption controls."""
import copy
from unittest.mock import patch
import pytest
from shapely.geometry import box
from shapely import to_wkb
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.stage_abi.contracts import StageABIError
from src.scoped_land_recovery import construct_rectangles,verify_recovery,permission,validate_machine_prefix,check_export_surfaces


def scene(tmp_path):
    store=ArtifactStore(tmp_path/'runtime');objects=[]
    for sid,g,kind in [('r1',box(0,0,1,1),'rectangle'),('r2',box(0,2,1,3),'rectangle'),
                       ('protected',box(4,0,5,1),'fixed_source')]:
        ref=store.put('geometry',to_wkb(g))
        objects.append(dict(source_id=sid,kind=kind,original_ref=ref,geometry_ref=ref,metadata={}))
    s=dict(source_sha256='a'*64,frame='native-kicad-mm',units='mm',layer='F.Cu',
           viewport_mm=[-1,-1,6,4],objects=objects,findings=[],lineage=[],acceptance={})
    return store,store.put_json('scene',s),s


def test_ordinary_two_rectangle_recovery_preserves_protected_source_and_reconstructs(tmp_path):
    store,ref,s=scene(tmp_path)
    with patch('src.scoped_land_recovery.permission',return_value={'ordinary_t02_recovery_source_ids':['r1','r2']}):
        recovery=construct_rectangles(store,ref,s)
        assert verify_recovery(store,recovery)['passed']
    candidate=recovery['candidate']
    assert all(d['status']=='GROWN'and d['shape']['factors']==[1.25,1.25]for d in candidate['decisions'])
    assert candidate['protected_source_refs']=={'protected':s['objects'][2]['geometry_ref']}
    assert recovery['verification']['inclusive_fills']==0


@pytest.mark.parametrize('fault',['cap','missing_target','protected','proof','plan','fill'])
def test_corruption_rejects_without_weakening_normal_t02_checks(tmp_path,fault):
    store,ref,s=scene(tmp_path)
    with patch('src.scoped_land_recovery.permission',return_value={'ordinary_t02_recovery_source_ids':['r1','r2']}):
        recovery=construct_rectangles(store,ref,s);bad=copy.deepcopy(recovery)
        if fault=='cap':bad['candidate']['decisions'][0]['shape']['factors'][0]=1.25001
        elif fault=='missing_target':bad['candidate']['decisions'].pop()
        elif fault=='protected':bad['candidate']['protected_source_refs']={}
        elif fault=='proof':bad['verification']['reconstructed_targets']=1
        elif fault=='plan':bad['plan']['details']['targets'].pop()
        else:bad['candidate']['inclusive_candidates'].append({'status':'MERGED'})
        with pytest.raises((StageABIError,ValueError)):verify_recovery(store,bad)


def test_unbound_source_cannot_use_scoped_permission():
    with pytest.raises(ValueError,match='SOURCE_AUTHORITY_REQUIRED'):permission('a'*64)


def test_authority_bytes_are_rechecked_before_scoped_execution(tmp_path):
    from src.t01_canonical import specification
    spec=copy.deepcopy(specification());p=tmp_path/'authority.json'
    p.write_bytes(b'{}');spec['permission_revision']['authority_path']=str(p)
    with patch('src.scoped_land_recovery.specification',return_value=spec):
        with pytest.raises(ValueError,match='AUTHORITY_CHANGED'):permission('a'*64)


@pytest.mark.parametrize('fault',['missing_proof','altered_proof','failed_predicate'])
def test_machine_prefix_missing_altered_or_failed_proof_rejects(tmp_path,fault):
    from pathlib import Path
    import json
    expected=json.loads((Path(__file__).resolve().parents[1]/'contracts/operator/t01_board_auto.json').read_text())['sequence']
    proofs={}
    for i in range(18):
        p=tmp_path/(str(i)+'.json');p.write_bytes(canonical(dict(status='PASS',checks=[dict(passed=True)])))
        proofs[p.name]=digest(p.read_bytes())
    if fault=='missing_proof':proofs.pop('0.json')
    elif fault=='altered_proof':(tmp_path/'0.json').write_bytes(b'{}')
    else:
        p=tmp_path/'0.json';p.write_bytes(canonical(dict(status='PASS',checks=[dict(passed=False)])));proofs[p.name]=digest(p.read_bytes())
    (tmp_path/'MACHINE_RECEIPT.json').write_bytes(canonical(dict(operations=expected,proofs=proofs)))
    with pytest.raises(ValueError):validate_machine_prefix(tmp_path)


@pytest.mark.parametrize('fault',[None,'export_changed','nominal_core_removed','rectangle_core_removed','actual_bridge'])
def test_model_and_quantized_export_have_separate_unchanged_strict_obligations(fault):
    from shapely.geometry import Point
    from shapely.affinity import scale,translate
    core=Point(0,0).buffer(.1,quad_segs=128)
    exported=scale(core,.999999999,.999999999,origin=core.centroid)
    assert not exported.covers(core)
    circles=[dict(id='c',original=core,nominal=core,actual=exported,predecessor_export_wkb=to_wkb(exported))]
    rect=box(1,0,2,1);actual=scale(rect,1.25,1.25,origin=rect.centroid)
    rectangles=[dict(id='r',original=rect,actual=actual)]
    if fault=='export_changed':circles[0]['actual']=translate(exported,xoff=.000001)
    elif fault=='nominal_core_removed':circles[0]['nominal']=exported
    elif fault=='rectangle_core_removed':rectangles[0]['actual']=scale(rect,.99,.99,origin=rect.centroid)
    elif fault=='actual_bridge':rectangles[0]['actual']=box(.08,-.125,2.125,1.125)
    if fault:
        with pytest.raises(ValueError):check_export_surfaces(circles,rectangles,[])
    else:
        q=check_export_surfaces(circles,rectangles,[])
        assert q['passed']and q['exact_model_surface']['checked_land_count']==2
        assert q['actual_rectangle_surface']['checked_land_count']==1


def test_native_scope_positions_enumerate_top_level_nodes_only():
    from src.scoped_land_recovery import native_positions
    from src.source_locators import locate
    raw=b'(kicad_pcb (version 1) (gr_poly (pts (xy 0 0) (xy 1 0) (xy 1 1)) (layer F.Cu)))'
    spans=locate(raw);top=[s for s in spans if s.parent_start==spans[0].start]
    positions=native_positions(raw)
    assert positions=={top[0].identity:1,top[1].identity:2}


@pytest.mark.parametrize('change',[None,'protected'])
def test_final_scope_audits_both_rectangles_and_rejects_protected_native_change(tmp_path,change):
    from types import SimpleNamespace
    from shapely.affinity import scale
    from src.native_preparation import native_loads
    from src.scoped_land_recovery import native_positions,verify_native_scope
    from src.pcb_data_abi import board_native
    from src.pcb_data_abi.crop import TEMPLATE
    raw=b'(kicad_pcb (version 1) (gr_poly (pts (xy 0 0) (xy 1 0) (xy 1 1) (xy 0 1)) (stroke (width 0) (type solid)) (fill yes) (layer F.Cu)) (gr_poly (pts (xy 0 2) (xy 1 2) (xy 1 3) (xy 0 3)) (stroke (width 0) (type solid)) (fill yes) (layer F.Cu)) (gr_circle (center 5 0) (end 5.1 0) (stroke (width 0) (type solid)) (fill yes) (layer F.Cu)))'
    positions=native_positions(raw);ids=[sid for sid,i in positions.items()if i in (2,3)];circle=next(sid for sid,i in positions.items()if i==4)
    store=ArtifactStore(tmp_path/'store');tree=native_loads(raw.decode());targets={};rows={}
    for sid,core in zip(ids,[box(0,0,1,1),box(0,2,1,3)]):
        target=scale(core,1.25,1.25,origin=core.centroid);targets[sid]=target
        rows[sid]=dict(original_ref=store.put('geometry',to_wkb(core)))
        tree[positions[sid]]=board_native.polygon_node(target,board_native.edit_template(TEMPLATE),sid,digest(to_wkb(target)))[0]
    if change:tree[1][1]=2
    board=tmp_path/'candidate.kicad_pcb';board.write_bytes(board_native.board_bytes(tree))
    prefix=tmp_path/'prefix';old=prefix/'data_output/candidate/board.kicad_pcb';old.parent.mkdir(parents=True);old.write_bytes(raw)
    service=SimpleNamespace(raw=raw,board=board,rectangle_targets=targets,rectangle_sources=rows)
    permit=dict(ordinary_t02_recovery_source_ids=ids,blocked_full_circle_obligation_source_ids=[circle])
    with patch('src.scoped_land_recovery.permission',return_value=permit):
        if change:
            with pytest.raises(ValueError,match='PREDECESSOR_NATIVE_NODE_CHANGED'):verify_native_scope(service,prefix,store,targets,{'source_sha256':digest(raw)})
        else:
            report=verify_native_scope(service,prefix,store,targets,{'source_sha256':digest(raw)})
            assert report['passed']and len(report['rectangles'])==2
            assert all(r['model_missing_area_mm2']==0 for r in report['rectangles'])
