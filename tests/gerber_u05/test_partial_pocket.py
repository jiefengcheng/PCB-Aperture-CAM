import hashlib,json,copy
from pathlib import Path
import pytest
from shapely import from_wkb,to_wkb
from shapely.geometry import box
from src.partial_pocket_remedy import construct,propose,validate,STRATEGY
from src.component_voids import RemedyContract,plan,holes
from src import component_clearance as cc
from src.gerber_u05.native_component_checks_final import final_inventory

def actual():
    root=Path(__file__).parent/'fixtures/partial_rim';values={}
    for name,expected in json.loads((root/'MANIFEST.json').read_bytes()).items():
        raw=(root/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==expected;values[name]=from_wkb(raw)
    return values['pocket.wkb'],values['carrier.wkb'],json.loads((root/'full_check.json').read_bytes())

def test_actual_approved_pocket_has_smooth_connected_remainder_and_strict_cap():
    pocket,carrier,full=actual();contract=RemedyContract()
    ring,check,spec=propose(pocket,carrier,contract,full)
    assert check['passed']and check['full_pocket_check']['reasons']==['SHORTAGE_ABOVE_20_PERCENT']
    assert .199<check['shortage']<=.20
    initial,remaining,_,_=validate(spec,contract)
    assert remaining.geom_type=='Polygon'and remaining.area>pocket.area*.5
    assert ring.intersection(remaining).area<=contract.area_epsilon_mm2
    assert initial.symmetric_difference(ring.union(remaining)).area<=contract.area_epsilon_mm2
    assert spec['decision']['smoothing_radius_mm']>0

def test_other_failed_predicates_cannot_be_overridden_by_partial_fill():
    pocket,carrier,full=actual();full['reasons'].append('FOREIGN_CLEARANCE_FAILED')
    with pytest.raises(ValueError,match='ONLY_THE_SIZE_LIMIT'):propose(pocket,carrier,RemedyContract(),full)

def test_forged_budget_is_rejected():
    pocket,carrier,full=actual();_,_,spec=propose(pocket,carrier,RemedyContract(),full)
    spec['decision']['maximum_added_area_mm2']*=2
    with pytest.raises(ValueError,match='BUDGET_INVALID'):validate(spec,RemedyContract())

def test_existing_small_pocket_keeps_the_whole_fill_path():
    with pytest.raises(ValueError,match='WHOLE_POCKET_ALREADY_WITHIN_CAP'):construct(box(0,0,1,1),box(1,0,11,10),RemedyContract())

def source_case():
    pocket=box(3,2,7,8);current=box(0,0,10,10).difference(pocket)
    source=current.difference(box(4.5,8,5.5,10.1))
    return source,current,pocket

def test_later_radii_never_restart_the_twenty_percent_allowance():
    source,current,pocket=source_case();specs=[];first=None
    for radius in(.04,.08,.16,.32):
        contract=RemedyContract(notch_radius_mm=radius)
        report,fills,current=plan(source,current,contract,partial_strategy=STRATEGY,approved_partials=specs)
        specs=report['approved_partial_pockets']
        assert len(specs)==1
        if first is None:first=specs[0]['pocket_id']
        assert specs[0]['pocket_id']==first
        assert current.intersection(pocket).area<=specs[0]['decision']['maximum_added_area_mm2']
        assert len(holes(current))==1
        if radius>.04:assert not any(f['kind']=='partial_rim'for f in fills)

def registered(tmp_path):
    from src.gerber_u05 import pipeline as p
    from src.gerber_u05.component_policy import capture_job
    source,current,pocket=source_case();report,_,result=plan(source,current,partial_strategy=STRATEGY);spec=copy.deepcopy(report['approved_partial_pockets'][0]);store=p.Store(tmp_path/'runtime');capture_job(tmp_path)
    ctx=cc.Context(source,'a'*64,{'source':source});own=ctx.owner('source');spec.update(original_owner_id=own,original_source_sha256=ctx.source_hash)
    row=dict(source_id='component-completion:'+own,kind='component_remedy',geometry_ref=p.geomref(store,result.difference(current)),original_ref=p.geomref(store,ctx.cores[own]),metadata=dict(original_owner_id=own,original_source_sha256=ctx.source_hash,approved_partial_pockets=[spec]))
    ctx.register_scene(store,dict(objects=[row]));return ctx,own,source,current,pocket,result,spec

def test_next_stage_cannot_fill_the_protected_opening_or_exceed_budget(tmp_path):
    ctx,own,source,current,pocket,result,spec=registered(tmp_path)
    assert not ctx.partial_pocket_failures({own:result})
    assert ctx.partial_pocket_failures({own:result.union(pocket)})

def test_native_inventory_accepts_only_the_declared_opening(tmp_path,monkeypatch):
    ctx,own,source,current,pocket,result,spec=registered(tmp_path);monkeypatch.setattr(cc,'ACTIVE',ctx)
    report=final_inventory(source,{own:result})
    assert report['new_resolvable_empty_pockets']==0
    assert len(report['approved_partial_pocket_remainders'])==1
    assert report['remaining_cavities'][0]['status']=='APPROVED_SMOOTH_RIM_RETAINED_OPENING'
    ctx.approved_partial_pockets.clear()
    with pytest.raises(ValueError,match='UNREPAIRED_GROWTH_CREATED_EMPTY_POCKET'):final_inventory(source,{own:result})

def test_native_inventory_rejects_missing_retained_void(tmp_path,monkeypatch):
    ctx,own,source,current,pocket,result,spec=registered(tmp_path);monkeypatch.setattr(cc,'ACTIVE',ctx)
    with pytest.raises(ValueError,match='CUMULATIVE_CAP_OR_OPENING_CHANGED'):final_inventory(source,{own:result.union(pocket)})

def test_prior_positive_copper_is_retained_inside_the_partial_budget():
    pocket,carrier,_=actual();mandatory=pocket.intersection(box(15.6,-9.5,15.7,-9.2))
    ring,remaining,_=construct(pocket,carrier,RemedyContract(),mandatory=mandatory)
    assert mandatory.difference(ring).area<=1e-12
    assert remaining.intersection(mandatory).area<=1e-12

def test_prior_positive_requirement_cannot_waive_the_cap():
    pocket,carrier,_=actual()
    with pytest.raises(ValueError,match='PRIOR_COPPER_EXCEEDS'):construct(pocket,carrier,RemedyContract(),mandatory=pocket)

def test_t05_prior_floor_keeps_the_frozen_pocket_metadata(tmp_path,monkeypatch):
    from src.gerber_u05 import pipeline as p,prior_copper
    ctx,own,source,current,pocket,result,spec=registered(tmp_path);monkeypatch.setattr(cc,'ACTIVE',ctx);store=p.Store(tmp_path/'runtime')
    ctx.reserved={own:result.union(box(-.01,0,0,1))};ctx.reservation_sha256='b'*64
    growth=current.difference(source);ctx.assign('closure',growth,[own]);sid='component-completion:'+own
    rows=[dict(source_id='source',kind='region',geometry_ref=p.geomref(store,source),original_ref=p.geomref(store,source),metadata={}),dict(source_id='closure',kind='component_remedy',geometry_ref=p.geomref(store,growth),original_ref=p.geomref(store,ctx.cores[own]),metadata=dict(original_owner_id=own,original_source_sha256=ctx.source_hash)),dict(source_id=sid,kind='component_remedy',geometry_ref=p.geomref(store,result.difference(current)),original_ref=p.geomref(store,ctx.cores[own]),metadata=dict(original_owner_id=own,original_source_sha256=ctx.source_hash,approved_partial_pockets=[spec]))]
    # Only the established owner surface is a prior-floor update target.
    rows[1]['kind']='junction_addition';rows[1]['metadata']=dict(owner_trace='source')
    scene=dict(objects=rows,lineage=[])
    output,receipt=prior_copper.prepare(store,scene)
    row=next(r for r in output['objects']if r['source_id']==sid)
    assert receipt['records']and row['metadata']['approved_partial_pockets']==[spec]
    assert len(ctx.approved_partial_pockets)==1
    _,material,_=p.operands(store,output)
    assert not ctx.partial_pocket_failures(ctx.project(material))
