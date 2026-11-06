import pytest
from types import SimpleNamespace
from shapely.geometry import box,Polygon
from src import pin_separation as pin,component_clearance as cc,source_channel_scope
from src.component_voids import RemedyContract,joined
from src.gerber_u05 import pipeline as p

@pytest.fixture
def pins(monkeypatch):
 left=box(.2,0,.3,2);right=box(.4,0,.5,2);source=left.union(right).union(box(.2,1.9,.5,2.1));slot=pin.Slot('a'*64,'pair',('left','right'),box(.25,-.1,.45,1.8),source,(left,right));rule=pin.Rule([slot],construction_gap=.0401,finished_gap=.04);monkeypatch.setattr(pin,'ACTIVE',rule);monkeypatch.setattr(source_channel_scope,'ACTIVE',None)
 return rule,slot,source,left,right

@pytest.mark.parametrize('module',['src.component_voids','src.growth_void_remedy_v09'])
def test_raw_notch_fill_is_rejected_before_clipping_or_partial_rim(pins,module):
 import importlib
 rule,slot,source,left,right=pins;planner=importlib.import_module(module).plan;current=source.union(left.buffer(.024)).union(right.buffer(.024));report,fills,after=planner(source,current)
 assert any(r['status']=='KEEP_PROTECTED_PIN_SEPARATION'for r in report['records'])
 assert rule.require(after)['passed']
 assert all(r['geometry'].difference(current).intersection(slot.void).is_empty for r in fills)


def test_microscopic_absorption_keeps_protected_slot(pins):
 from src.component_absorption import absorb
 rule,slot,source,left,right=pins;hole=box(.35,1,.3500001,1.0000001);region=Polygon(box(.25,.9,.45,1.1).exterior,[hole.exterior]);after,report=absorb(region,source,source,[],RemedyContract())
 assert hole.difference(after).area>0
 assert report['holes_absorbed']==0
 assert any(r['status']=='KEEP_PROTECTED_PIN_SEPARATION'for r in report['records'])


def test_smooth_rim_rejects_complete_pocket_before_budget_or_mandatory_clipping(pins):
 from src.partial_pocket_remedy import construct
 rule,slot,source,left,right=pins;pocket=box(.29,.7,.41,.71).union(box(.7,.7,.8,.8))
 with pytest.raises(ValueError,match='COMPLETE_POCKET_REJECTED'):construct(pocket,source,RemedyContract(),mandatory=box(2,2,3,3))
 assert not rule.remedy(box(.72,.72,.78,.78),source)['passed']

@pytest.mark.parametrize('which',['general','fast','component'])
def test_every_inclusive_rectangle_adapter_rejects_same_owner_pin_slot(tmp_path,monkeypatch,which):
 from src.stage_abi.lands import LandAdapter
 from src.u04_board.search import FastRectangleAdapter
 from src.gerber_u05.component_rectangles import ComponentRectangleAdapter
 monkeypatch.setattr(source_channel_scope,'ACTIVE',None)
 left=box(0,0,1,2);right=box(1.1,0,2.1,2);joint=box(0,1.9,2.1,2.1);source=left.union(right).union(joint);domain=box(.5,-.1,1.6,1.8);slot=pin.Slot('a'*64,'pair',('left','right'),domain,source,(left,right));rule=pin.Rule([slot],construction_gap=.0401,finished_gap=.04);monkeypatch.setattr(pin,'ACTIVE',rule)
 current=dict(left=left,right=right,joint=joint);ctx=cc.bind(source,'a'*64,current)if which=='component'else None;monkeypatch.setattr(cc,'ACTIVE',ctx);store=p.Store(tmp_path/'runtime');rows={}
 for sid,g in current.items():
  ref=p.geomref(store,g);rows[sid]=dict(source_id=sid,kind='rectangle'if sid!='joint'else'trace',original_ref=ref,geometry_ref=ref,metadata=dict(original_width_mm=.1,nominal_width_mm=.1))
 scene=dict(viewport_mm=[-1,-1,4,3],objects=list(rows.values()),lineage=[dict(stage='source')]);plan=dict(details=dict(targets=['left','right'],containment={s:dict(contained=False)for s in('left','right')}));budget=SimpleNamespace(evaluation=lambda:None,output=lambda x:None)
 adapter={'general':LandAdapter,'fast':FastRectangleAdapter,'component':ComponentRectangleAdapter}[which]('t02');records,additions=adapter._merges(store,scene,plan,rows,current,budget)
 assert records and records[0]['shortage']<.20 and not additions
 assert 'PROTECTED_PIN_SEPARATION_ENTIRE_FILL'in records[0]['reasons']


def test_combined_retained_prior_and_new_growth_cannot_close_each_others_gap(pins):
 rule,slot,source,left,right=pins;prior=source.union(right.buffer(.0299));rule.reserve([prior],'b'*64)
 assert rule.growth_parts([source],[source])['passed']
 # Each version alone has >= .0401 gap. The complete retained combination does not.
 candidate=source.union(left.buffer(.04));assert rule.check(candidate)['passed']
 assert not rule.growth_parts([source],[candidate])['passed']


def test_encoded_intrusion_is_rejected_even_when_finished_gap_remains_legal(pins):
 rule,slot,source,left,right=pins;encoded=box(.3,.7,.301,.8)
 assert rule.check(source.union(encoded),finished=True)['passed']
 with pytest.raises(ValueError,match='ACTUAL_ENCODED_REMEDY_FAILED'):pin.require_remedy(encoded,source,scope='actual_encoded_remedy')
 assert pin.require_remedy(left,source)['passed'] # Source overlap adds no forbidden copper.


def test_original_source_at_finished_floor_is_allowed_unchanged(monkeypatch):
 left=box(0,0,1,2);right=box(1.04005,0,2,2);source=left.union(right).union(box(0,1.9,2,2.1));slot=pin.Slot('a'*64,'pair',('left','right'),box(.5,-.1,1.5,1.8),source,(left,right));rule=pin.Rule([slot],construction_gap=.0401,finished_gap=.04)
 assert rule.growth_parts([source],[source])['passed']
 assert not rule.growth_parts([source],[source.union(box(1,.2,1.000001,1.7))])['passed']


def test_native_encoding_rejects_entire_logical_fill_and_keeps_other_repairs(pins):
 rule,slot,source,left,right=pins;outside=box(2,2,2.01,2.01);intrusion=box(.30,.7,.301,.8);encoded=outside.union(intrusion)
 proof=pin.encoded_remedy(outside,encoded,source)
 assert not proof['passed']and not proof['fragments_accepted']
 assert not rule.remedy(outside,source)['passed']
 assert rule.remedy(box(3,3,3.01,3.01),source)['passed']


def test_full_transition_keeps_original_taper_but_rejects_new_growth(monkeypatch):
 left=box(0,0,1,2);right=box(1.1,0,2.1,1.5).union(box(1.02,1.4,2.1,2));source=left.union(right).union(box(0,1.99,2.1,2.1));domain=box(.5,-.1,1.6,1.98);spacing=box(.5,-.1,1.6,1.3);slot=pin.Slot('a'*64,'transition',('left','right'),domain,source,(left,right),spacing_domain=spacing);rule=pin.Rule([slot],construction_gap=.0401,finished_gap=.04)
 assert rule.require(source)['passed']
 assert rule.require(source.union(box(1,.2,1.02,1.0)))['passed']
 assert not rule.check(source.union(box(1,1.6,1.001,1.7)),finished=True)['passed']
 assert not rule.check(source.union(box(1,1.97,1.03,1.975)),finished=True)['passed']


def test_native_parent_keeps_undeclared_source_path_and_coordinates(pins,monkeypatch):
 from shapely import set_precision,to_wkb,get_precision
 rule,slot,source,left,right=pins;ref=set_precision(box(0,0,1,1),.000001)
 plain=pin.native_parent(ref,grid_mm=.000001)
 assert get_precision(plain)==0 and plain.equals(ref)
 monkeypatch.setattr(pin,'ACTIVE',None)
 assert pin.native_parent(ref,grid_mm=.000001)is ref
