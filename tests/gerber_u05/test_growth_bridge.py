import math
import numpy as np
import pytest
from shapely.geometry import LineString,Polygon,box
from shapely.ops import unary_union
from src.gerber_u05.growth_bridge import run
from src.native_inventory import ERROR_MM


def case():
    points={'line':[[-1.,0.],[0.,0.]],'arc':[[float(math.cos(t)),float(1+math.sin(t))]
        for t in np.linspace(-math.pi/2,0.,121)]}
    rows={s:dict(metadata=dict(route_points_mm=p,route_kind='segment'if s=='line'else'arc',minimum_caliper_mm=.05))for s,p in points.items()}
    original={s:LineString(p).buffer(.025,quad_segs=128)for s,p in points.items()}
    naked=box(-.035,-.1,.035,.1)
    before={s:unary_union([original[s],LineString(p).buffer(.0375,quad_segs=128).difference(naked)])for s,p in points.items()}
    return rows,{'r':['line','arc']},before,original,{'line':.075,'arc':.075}


def prepared(plans,forbidden=None):
    return {i:dict(forbidden=Polygon()if forbidden is None else forbidden,context=Polygon(),neighbors=[])
            for i,p in enumerate(plans)if p['patch']is not None},dict(queries=0)


def test_bridge_covers_naked_seam_without_losing_previous_widening():
    rows,paths,before,original,caps=case()
    after,_,_,q=run(rows,paths,before,original,caps,prepare=prepared)
    from src.stage_abi.contracts import finite_json
    finite_json(q)
    assert q['smoothed']>=1 and q['unresolved']==0
    old=unary_union(list(before.values()));new=unary_union(list(after.values()))
    assert old.difference(new).area<1e-12 and new.difference(old).area>.0001
    missing=box(-.02,-.035,.02,.035).difference(new)
    assert missing.area<=ERROR_MM**2 and missing.difference(new.buffer(ERROR_MM)).is_empty
    assert all(r['net_growth_area_mm2']>=0 and r['profile']['maximum_materialized_alignment_angle_degrees']<=10 for r in q['reports'])


def test_blocked_gap_preserves_original_candidate_instead_of_withdrawing_it():
    rows,paths,before,original,caps=case()
    after,_,_,q=run(rows,paths,before,original,caps,prepare=lambda plans:prepared(plans,box(-.1,-.1,.1,.1)))
    assert q['smoothed']==0 and q['unresolved']>0
    assert all(after[s].wkb==g.wkb for s,g in before.items())
    assert q['removed_optional_copper_mm2']==0 and not q['withdrawn_growth']


def test_width_cap_does_not_turn_existing_widening_into_new_permission():
    rows,paths,before,original,caps=case();caps['arc']=.05
    after,_,_,q=run(rows,paths,before,original,caps,prepare=prepared)
    assert q['smoothed']==0 and q['unresolved']>0
    assert all(after[s].wkb==g.wkb for s,g in before.items())


def test_constructor_requires_prepared_allowance():
    with pytest.raises(ValueError,match='PREPARED_ALLOWANCE_REQUIRED'):run(*case())


def test_covered_chain_is_not_regrown():
    rows,paths,before,original,caps=case()
    after,_,_,q=run(rows,paths,before,original,caps,covered=set(before),prepare=prepared)
    assert not q['reports'] and all(after[s].wkb==g.wkb for s,g in before.items())


def test_reversed_source_occurrences_keep_gap_station_custody():
    rows,paths,before,original,caps=case();rows['arc']['metadata']['route_points_mm'].reverse()
    after,_,_,q=run(rows,paths,before,original,caps,prepare=prepared)
    assert q['smoothed']>=1 and q['unresolved']==0
    assert all(original[s].difference(g).area<1e-12 for s,g in after.items())


def test_local_recession_requires_real_gap_gain_and_cannot_borrow_distant_copper():
    from src.gerber_u05.growth_bridge import change_budget
    before=box(0,0,1,1);window=box(.8,-.1,1.2,1.1)
    cut=box(.9,0,1,.1);fill=box(1,.3,1.1,.5)
    after=before.difference(cut).union(fill)
    added,removed,reasons=change_budget(before,after,window)
    assert not reasons and added.area>removed.area>0
    _,_,reasons=change_budget(before,before.difference(box(.8,0,1,1)).union(fill),window)
    assert 'LOCAL_GROWTH_LOSS'in reasons
    _,_,reasons=change_budget(before,before.difference(box(0,0,.01,.01)).union(fill),window)
    assert 'RECESSION_OUTSIDE_BRIDGE_WINDOW'in reasons


def test_final_board_compares_with_previous_widening_and_rejects_new_steps_or_loss():
    from src.gerber_u05.boundary_finish import board_outline
    original={'s':box(0,0,1,1)};baseline={'s':box(0,-.1,1,1.1)}
    _,_,q=board_outline(original,baseline,10,baseline_sources=baseline)
    assert q['passed'] and q['bridge_net_growth_area_mm2']==0
    _,_,q=board_outline(original,{'s':box(0,-.1,.9,1.1)},10,baseline_sources=baseline)
    assert not q['passed'] and q['bridge_net_growth_area_mm2']<0
    _,_,q=board_outline(original,{'s':baseline['s'].union(box(.4,1, .6,1.2))},10,baseline_sources=baseline)
    assert not q['passed'] and q['additional_shoulders']>0


def test_allowance_batch_reserves_growth_outside_original_bounds_and_protects_same_owner_pin():
    from src.gerber_u05.boundary_prepare import bridge_allowances
    class Context:
        def __init__(self):self.stats={};self.bounds=None
        def query_view(self,bounds):self.bounds=bounds;self.stats['revision_overlay_index_builds']=1;return self
        def sources(self,window):self.stats['source_queries']=self.stats.get('source_queries',0)+1;return ['a','b']
    class Revision:
        context=Context();membership={'a':{'owner-a'},'b':{'owner-b'}}
    material={'a':box(0,0,.1,.1),'b':box(2,0,2.1,.1)}
    plans=[dict(chain={'source_ids':['a']},patch=box(.1,0,1,.1)),
           dict(chain={'source_ids':['b']},patch=box(.9,0,2,.1))]
    pin=box(.4,-.01,.5,.11)
    allowances,receipt=bridge_allowances(plans,material,Revision(),protected_voids=[pin])
    assert Revision.context.bounds['a'].covers(plans[0]['patch'])
    assert allowances[0]['forbidden'].covers(pin)
    assert allowances[0]['forbidden'].intersects(plans[1]['patch'])
    assert receipt['queries']==2 and receipt['overlay_index_builds']==1
    assert receipt['source_index_builds']==receipt['private_indexes']==receipt['owner_reconstructions']==0


def test_outline_noise_filter_does_not_excuse_a_real_width_step():
    from src.gerber_u05.boundary_finish import sharp_points
    from src.gerber_u05.growth_bridge import meaningful_shoulders
    floor=box(0,0,1,1);stepped=floor.union(box(.4,1,.6,1.1))
    points=sharp_points(stepped,floor,10)
    assert points and meaningful_shoulders(stepped,points)==points


def test_actual_tangent_angle_includes_trajectory_shift_not_just_radius_slope():
    from src.gerber_u05.growth_bridge import cone_alignment
    axis=np.array([math.cos(math.radians(6)),math.sin(math.radians(6))])
    # A nominal 6-degree radius taper on a trajectory already tilted 6 degrees
    # exceeds the 10-degree source alignment limit; both effects count.
    assert cone_alignment(axis,np.array([1.,0.]),math.sin(math.radians(6)))==pytest.approx(12.)
    assert cone_alignment(np.array([1.,0.]),np.array([1.,0.]),0.)==0


def test_visible_steep_tangent_rejects_but_a_fully_buried_one_is_not_an_edge():
    from src.gerber_u05.growth_bridge import exposed_alignment
    positions=np.array([[0.,0.],[1.,.3]]);native=np.array([[0.,0.],[1.,0.]])
    radii=np.array([.1,.1]);shape=LineString(positions).buffer(.1,quad_segs=128)
    with pytest.raises(ValueError,match='EDGE_ALIGNMENT'):exposed_alignment(shape,positions,native,radii,10)
    maximum,hidden,internal=exposed_alignment(box(-1,-1,2,2),positions,native,radii,10)
    assert maximum==0 and hidden==1 and internal>10


def test_failed_floor_preservation_rejects_candidate_and_keeps_previous_widening(monkeypatch):
    import src.gerber_u05.source_trace_floor as floor
    def reject(*args):raise ValueError('SOURCE_FLOOR_POSITIVE_COPPER_STILL_MISSING')
    monkeypatch.setattr(floor,'preserve',reject)
    rows,paths,before,original,caps=case();after,_,_,q=run(rows,paths,before,original,caps,prepare=prepared)
    assert not q['smoothed'] and q['unresolved']
    assert all(after[s].wkb==g.wkb for s,g in before.items())
    attempts=q['reports'][0]['attempts']
    assert attempts and all(r['reasons']==['SOURCE_FLOOR_POSITIVE_COPPER_STILL_MISSING']for r in attempts)
    assert all(r['source_floor_rejection']['carrier_wkb_hex']for r in attempts)


def test_unexpected_floor_errors_still_stop_execution(monkeypatch):
    import src.gerber_u05.source_trace_floor as floor
    def broken(*args):raise ValueError('UNEXPECTED_KERNEL_FAILURE')
    monkeypatch.setattr(floor,'preserve',broken)
    with pytest.raises(ValueError,match='UNEXPECTED_KERNEL_FAILURE'):run(*case(),prepare=prepared)


def test_source_with_contacting_and_foreign_owners_is_not_fully_exempted():
    from src.gerber_u05.boundary_prepare import bridge_allowances
    class Context:
        stats={}
        def query_view(self,bounds):return self
        def sources(self,window):return ['a','split']
    class Revision:
        context=Context();membership={'a':{'own'},'split':{'own','foreign'}}
    material={'a':box(0,0,.1,.1),'split':box(.2,0,.3,.1)}
    allowances,_=bridge_allowances([dict(chain={'source_ids':['a']},patch=box(.1,0,.25,.1))],material,Revision())
    assert not allowances[0]['forbidden'].is_empty
    assert allowances[0]['foreign_operands']==1


def test_unexpected_aperture_constructor_error_is_not_a_kept_finding(monkeypatch):
    import src.gerber_u05.growth_bridge as bridge
    def broken(*args):raise ValueError('UNEXPECTED_CONSTRUCTOR_FAILURE')
    monkeypatch.setattr(bridge,'ribbon',broken)
    with pytest.raises(ValueError,match='UNEXPECTED_CONSTRUCTOR_FAILURE'):run(*case(),prepare=prepared)


def test_affected_interior_section_is_witnessed_by_its_own_emitted_source():
    from src.gerber_u05.growth_bridge import affected_sections
    from src.gerber_u05.endpoint_sections import audit
    points={'a':[[-1.,0.],[0.,0.]],'b':[[0.,0.],[1.,0.]]}
    rows={s:dict(metadata=dict(route_points_mm=p))for s,p in points.items()}
    before={s:LineString(p).buffer(.0375,quad_segs=128)for s,p in points.items()}
    after={s:LineString(p).buffer(.035,quad_segs=128)for s,p in points.items()}
    chain=dict(line=LineString([[-1,0],[0,0],[1,0]]),width=.05,source_intervals=[(0.,1.,'a'),(1.,2.,'b')])
    sections=affected_sections(rows,chain,before,after)
    assert set(sections)=={('a',(0.,0.)),('b',(0.,0.))}
    obligations=[dict(route_id='r',source_id=s,endpoint_mm=[0,0],section=section,native_frame_transition_admitted=True)for(s,_),section in sections.items()]
    assert audit({'r':unary_union(list(after.values()))},obligations)['passed']


def test_retained_real_overlay_rejects_for_the_original_floor_reason():
    import json,hashlib
    from pathlib import Path
    from shapely import from_wkb
    from src.gerber_u05.source_trace_floor import preserve
    path=Path(__file__).resolve().parents[2]/'out/lacie_work/t04_gap_bridge_20261125_23/REJECTED_FLOOR.json'
    if not path.exists():pytest.skip('Retained LaCie overlay fixture unavailable')
    raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='cea37bba6605762eb2b1aed1b3129ca8401466a3748499f189e72e7be6736d6a'
    q=json.loads(raw)
    with pytest.raises(ValueError,match='SOURCE_FLOOR_POSITIVE_COPPER_STILL_MISSING'):
        preserve(from_wkb(bytes.fromhex(q['carrier_wkb_hex'])),from_wkb(bytes.fromhex(q['proposed_wkb_hex'])))


def test_long_edge_retrace_uses_native_coordinate_depth_without_editing_copper():
    from src.gerber_u05.growth_bridge import meaningful_shoulders
    from src.native_inventory import ERROR_MM
    for depth,expected in ((ERROR_MM/2,[]),(ERROR_MM*2,[(1.,0.)])):
        body=Polygon([(0,0),(1,0),(.9,depth),(1,1),(0,1)])
        raw=body.wkb
        assert body.is_valid
        assert meaningful_shoulders(body,[(1.,0.)])==expected
        assert body.wkb==raw


def test_round_cap_corner_outside_flat_window_cannot_escape_outline_check(monkeypatch):
    import src.gerber_u05.growth_bridge as module
    raw=module.proposals
    def capped(rows,chain,caps,angle):
        proposals=raw(rows,chain,caps,angle)
        if not proposals:return []
        record=dict(proposals[0][0]);patch=box(-.02,.02,-.01,.033)
        record.update(domain_wkb_hex=box(.01,-.05,.02,.05).wkb_hex,
            source_domains_wkb_hex={chain['source_ids'][0]:patch.wkb_hex})
        return [(record,patch)]
    monkeypatch.setattr(module,'proposals',capped)
    monkeypatch.setattr(module,'constrained_reference',lambda *a:None)
    rows,paths,before,original,caps=case()
    after,_,_,report=module.run(rows,paths,before,original,caps,prepare=prepared)
    assert not report['smoothed'] and report['unresolved']
    assert all(after[s].wkb==before[s].wkb for s in before)
    assert any('BRIDGE_OUTLINE_HAS_SHOULDER'in a['reasons']for r in report['reports']for a in r.get('attempts',[]))


def test_accepted_first_bridge_does_not_construct_or_verify_unused_alternative(monkeypatch):
    import src.gerber_u05.growth_bridge as module
    def unused(*args):raise AssertionError('UNUSED_ALTERNATIVE_EXECUTED')
    monkeypatch.setattr(module,'constrained_reference',unused)
    _,_,_,report=module.run(*case(),prepare=prepared)
    assert report['smoothed'] and all(r['mode']=='ADD_ONLY'for r in report['reports']if r['status']=='BRIDGED')
