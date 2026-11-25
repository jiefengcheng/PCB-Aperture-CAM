import copy
import math
import pytest
from shapely.geometry import LineString,Point,box
from shapely.ops import unary_union
from shapely import to_wkb
from src.stage_abi.store import digest
from src.gerber_u05.terminal_handoff import prepare,seal,authenticate,finish,interior
from src.gerber_u05.boundary_finish import run,board_outline


def fixture():
    path=[[-1.,0.],[0.,0.]];trace=LineString(path).buffer(.025,quad_segs=128)
    pad=Point(0,0).buffer(.2,quad_segs=128);grown=LineString(path).buffer(.0375,quad_segs=128)
    entry=dict(trace=trace,pad=pad)
    rows={s:dict(source_id=s,kind='circle'if s=='pad'else'stroke',
        original_ref=dict(sha256=digest(to_wkb(g))),metadata=dict(qualified_land=s=='pad',
        route_points_mm=path,minimum_caliper_mm=.05))for s,g in entry.items()}
    paths={'r':['trace']};bodies=dict(trace=grown)
    records=prepare(rows,paths,entry,{'r':{'pad':pad}},bodies)
    return rows,paths,entry,bodies,records


def test_terminal_deferral_preserves_whole_trace_growth_and_records_obligations():
    rows,paths,entry,bodies,records=fixture()
    after,cuts,sections,q=run(rows,paths,bodies,entry,{'trace':.075},supports={'r':{'pad':entry['pad']}},
        terminals=records,local_controls=True)
    assert after['trace'].wkb==bodies['trace'].wkb and not cuts and not q['withdrawn_growth']
    assert q['deferred_terminals'] and q['deferred_terminals'][0]['points_mm']
    before=dict(entry);result=dict(entry,**after)
    _,_,proof=board_outline(before,result,10,q['deferred_terminals'])
    assert proof['passed']and proof['deferred_terminal_shoulders']>0
    assert not board_outline(before,result,10)[2]['passed']


def test_t05_cannot_clear_pending_terminals_with_a_keep_or_remove_predecessor():
    rows,paths,entry,bodies,records=fixture()
    after,_,_,q=run(rows,paths,bodies,entry,{'trace':.075},supports={'r':{'pad':entry['pad']}},terminals=records,local_controls=True)
    ledger=seal(q['deferred_terminals'],dict(entry,**after),'source',10)
    current=unary_union([*after.values(),entry['pad']])
    assert not finish(ledger,current)['passed']
    with pytest.raises(ValueError,match='COPPER_REMOVED'):finish(ledger,unary_union(list(entry.values())))
    from shapely import from_wkb
    # Completion check only: this synthetic fill grants no clearance acceptance.
    completed=unary_union([current,from_wkb(bytes.fromhex(records[0]['window_wkb_hex']))])
    assert finish(ledger,completed)['passed']
    assert authenticate(ledger,'source',dict(entry,**after))==ledger
    changed=copy.deepcopy(ledger);changed['records'][0]['points_mm']=[]
    with pytest.raises(ValueError,match='BINDING_CHANGED'):authenticate(changed,'source',dict(entry,**after))
    with pytest.raises(ValueError,match='PREDECESSOR_CHANGED'):authenticate(ledger,'source',entry)


def test_pad_proximity_and_foreign_geometry_do_not_grant_terminal_deferral():
    rows,paths,entry,bodies,records=fixture()
    rows['pad']['metadata']['qualified_land']=False
    assert not prepare(rows,paths,entry,{'r':{'pad':entry['pad']}},bodies)
    outside=[[-.9,.0375]]
    assert interior(outside,records)==outside
    # A different source's shoulder inside the window but outside the named
    # trace's optional copper remains T04 work.
    assert interior([[-.1,.25]],records)==[[-.1,.25]]


def test_t04_interior_is_not_frozen_by_the_larger_t05_search_window():
    from src.gerber_u05.terminal_handoff import attachment_scopes,interior_t04
    rows,paths,entry,bodies,records=fixture()
    records=attachment_scopes(records,rows,entry,{'trace':.075})
    bend=[[-.35,.0375]]
    assert interior(bend,records)==[]
    assert interior_t04(bend,records)==bend
    terminal=[[-math.sqrt(.2**2-.0375**2)-1e-6,.0375]]
    assert interior_t04(terminal,records)==[]
    assert records[0]['attachment_dependencies'][0]['land_sha256']==digest(to_wkb(entry['pad']))


def test_tight_native_miter_is_locally_suppressed_without_rejecting_long_chain():
    points=[[-1.,0.],[-.03,0.],[-.01,.01],[0.,0.],[.01,.01],[.03,0.],[1.,0.]]
    floor=LineString(points).buffer(.025,quad_segs=128);grown=LineString(points).buffer(.0375,quad_segs=128)
    rows={'s':dict(metadata=dict(route_points_mm=points,minimum_caliper_mm=.05))}
    after,_,_,q=run(rows,{'r':['s']},{'s':grown},{'s':floor},{'s':.075},local_controls=True)
    assert q['unresolved']==0 and not q['withdrawn_growth']
    assert after['s'].difference(floor).area>.4*grown.difference(floor).area
    assert floor.difference(after['s']).area<1e-12 and after['s'].difference(grown).area<1e-12
    assert any(c['recipe']for c in q['chains'])


def test_active_curved_sections_overlap_the_original_carrier_without_cracks():
    import numpy as np
    from src.gerber_u05.boundary_finish import compile_graph,reference,hole_regions
    points=[[-1.,0.],[0.,0.]]+[[.3*math.sin(t),.3*(1-math.cos(t))]
        for t in np.linspace(0,math.pi/2,45)[1:]]+[[.3,1.3]]
    floor=LineString(points).buffer(.05,quad_segs=128)
    body=LineString(points).buffer(.075,quad_segs=128)
    rows={'s':dict(metadata=dict(route_points_mm=points,minimum_caliper_mm=.1))}
    chain=compile_graph(rows,{'r':['s']},{'s':body},{'s':floor},set(),{})[0]['chains'][0]
    chain['local_controls']=True
    shape,recipe=reference(chain,{'s':.15},math.tan(math.radians(10)))
    assert recipe and shape.is_valid and not hole_regions(shape)
    assert floor.difference(shape).area<1e-12
    assert shape.difference(floor).area>.4*body.difference(floor).area


def test_admitted_growth_contact_uses_shared_batch_without_new_terminal_authority():
    from src.gerber_u05.boundary_prepare import supports
    rows,paths,entry,bodies,_=fixture()
    entry['pad']=box(-.6,.03,-.4,.2)
    class Revision:
        membership={'trace':{'owner'},'pad':{'owner'}}
        queries=0
        def sources(self,domain):
            self.queries+=1
            return set(entry)
    old=Revision();new=Revision()
    assert not supports(rows,paths,entry,old,with_sources=True)['r']
    contacts=supports(rows,paths,entry,new,with_sources=True,admitted=bodies)
    assert set(contacts['r'])=={'pad'} and old.queries==new.queries==1
    assert not prepare(rows,paths,entry,contacts,bodies)


def test_actual_t05_pipeline_consumes_saved_t04_terminal_obligation(tmp_path):
    from src.gerber_u05 import pipeline as p
    from src.t04_settings import capture_job
    from tests.gerber_u05.test_gerber_source import source_circle
    from src.gerber_u05.boundary_finish import sharp_points
    from shapely import from_wkb
    store=p.Store(tmp_path/'runtime');capture_job(tmp_path)
    source=p.build_source(store,source_circle());scene=store.get_json(source['scene_ref'],kind='scene')
    rows,original,_=p.operands(store,scene)
    t04=p.run_t04(store,scene);out=store.get_json(t04['output_scene_ref'],kind='scene')
    _,current,_=p.operands(store,out)
    paths={r['path']['path_id']:r['path']['source_ids']for r in t04['admission']['paths']}
    lands={s:g for s,g in original.items()if p.t05_land(rows[s])}
    records=prepare(rows,paths,original,{r:lands for r in paths},current)
    for r in records:
        domain=from_wkb(bytes.fromhex(r['window_wkb_hex']))
        image=unary_union([current[s]for s in r['source_ids']+r['land_ids']])
        floor=unary_union([original[s]for s in r['source_ids']+r['land_ids']])
        r['points_mm']=[pt for pt in sharp_points(image,floor,10)if domain.covers(Point(pt))]
    records=[r for r in records if r['points_mm']]
    assert records
    ledger=seal(records,current,scene['source_sha256'],10)
    out['lineage'].append(dict(stage='t04-terminal-obligations',terminal_handoff_ref=store.put_json('t04-terminal-handoff',ledger)))
    t02=p.run_t02(store,out)
    final=p.run_t05(store,store.get_json(t02['output_scene_ref'],kind='scene'),t04)
    assert final['verification']['passed']and final['terminal_completion']['passed']
    assert final['terminal_completion']['resolved']==len(records)


def test_exact_local_cut_handles_retained_nested_shell_without_geometry_repair():
    from pathlib import Path
    import json
    from shapely import from_wkb
    from src.gerber_u05.boundary_finish import subtract_optional
    root=Path(__file__).resolve().parents[2]
    path=root/'out/lacie_work/t04_t05_division_20261125_08/INVALID_SUBTRACTION.json'
    if not path.exists():pytest.skip('Retained LaCie numerical overlay fixture unavailable')
    value=json.loads(path.read_bytes())
    body,cut,floor=[from_wkb(bytes.fromhex(value[k+'_wkb_hex']))for k in('admitted','cut','floor')]
    assert body.is_valid and cut.is_valid and not body.difference(cut).is_valid
    result,method=subtract_optional(body,cut)
    assert result.is_valid and method=='EXACT_INTERSECTION_BEFORE_DIFFERENCE'
    assert result.difference(body).area<=1e-12 and floor.difference(result).area<=1e-12
    assert result.symmetric_difference(body.difference(cut.intersection(body))).area<=1e-12


def test_invalid_subtraction_operand_still_rejects():
    from shapely.geometry import Polygon
    from src.gerber_u05.boundary_finish import subtract_optional
    invalid=Polygon([(0,0),(1,1),(0,1),(1,0),(0,0)])
    with pytest.raises(ValueError,match='VALID_OPTIONAL_SUBTRACTION_OPERANDS'):
        subtract_optional(box(0,0,2,2),invalid)
