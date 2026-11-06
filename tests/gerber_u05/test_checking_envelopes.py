"""Guard geometry is an obstacle, never a copper floor or fill entitlement."""
from types import SimpleNamespace
import pytest
from shapely.geometry import box
from src.gerber_u05 import pipeline as p
from src.gerber_u05.checking_envelopes import constraint,check_native,install,NATIVE_HEADROOM_MM
from src.component_clearance import Context
from src import component_clearance as cc,source_channel_scope as functional,pin_separation as pin
from src.prepared_land_scene import PreparedLandScene
from src.component_voids import parts


@pytest.fixture(autouse=True)
def isolated_contexts(monkeypatch):
 monkeypatch.setattr(cc,'ACTIVE',None);monkeypatch.setattr(functional,'ACTIVE',None);monkeypatch.setattr(pin,'ACTIVE',None)


def test_envelope_is_rebuilt_from_source_and_cannot_inflate_nominal_copper():
 core=box(0,0,1,.1)
 nominal=p.offset_part(core,.1,1.3,False)
 envelope=p.offset_part(core,.1,1.3,True,extra_envelope_mm=NATIVE_HEADROOM_MM)
 assert nominal.bounds[3]==pytest.approx(.115)
 assert envelope.bounds[3]==pytest.approx(.115014)
 assert nominal.difference(envelope).is_empty
 with pytest.raises(ValueError,match='CHECKING_ONLY'):
  p.offset_part(core,.1,1.3,False,extra_envelope_mm=NATIVE_HEADROOM_MM)
 with pytest.raises(ValueError,match='CHECKING_ONLY'):
  p.offset_part(core,.1,1.3,True,extra_envelope_mm=.001)


def test_constraint_does_not_change_minimum_copper_or_source_ownership():
 material=box(0,0,1,.1);guard=material.buffer(.000014)
 context=SimpleNamespace(reserved={},checking_envelopes={'a':guard})
 assert constraint(context,'a',material).covers(guard)
 assert context.reserved=={}
 assert material.area==.1


def land(s,g,candidate):
 return dict(id=s,original=g,candidate=candidate,native_source_kind='gr_poly',native_stroke_width_mm=0.)


def test_foreign_pad_cannot_consume_route_envelope_but_joint_stays_integral(monkeypatch):
 route=box(0,0,1,.1);pad=box(0,.16009,1,.3)
 context=Context(route.union(pad),'source',{'route':route,'pad':pad})
 owner=context.owner('route');context.checking_envelopes={owner:box(0,0,1,.115014)}
 monkeypatch.setattr(cc,'ACTIVE',context)
 # 40.1 um from nominal T04 copper, but only 40.086 um from its guard.
 candidate=box(0,.1551,1,.3)
 baseline=[land('pad',pad,pad)]
 checker=PreparedLandScene(baseline,[dict(id='route',geometry=route,trace_width_mm=.1)])
 result=checker.check([land('pad',pad,candidate)])
 assert not result['passed']
 assert any(r['reason']=='NEW_COPPER_BELOW_FOREIGN_COMPONENT_GAP'for r in result['failures'])
 # The same source-connected pad/trace has one owner: no artificial joint gap.
 joint=box(.9,.05,1.2,.2);integral=Context(route.union(joint),'joint',{'route':route,'pad':joint})
 integral.checking_envelopes={integral.owner('route'):route.buffer(.015014)}
 monkeypatch.setattr(cc,'ACTIVE',integral)
 checker=PreparedLandScene([land('pad',joint,joint)],[dict(id='route',geometry=route,trace_width_mm=.1)])
 assert checker.check([land('pad',joint,joint.buffer(.01))])['passed']


@pytest.mark.parametrize('module_name',['src.component_voids','src.growth_void_remedy_v09'])
def test_complete_notch_is_rejected_without_fragments_while_unrelated_repair_proceeds(module_name):
 import importlib
 module=importlib.import_module(module_name)
 # Shallow growth-created notches. The guard is foreign and blocks only one.
 original=box(0,0,1,.1).union(box(3,0,4,.1))
 first=box(0,0,1,.2).difference(box(.48,.18,.52,.21))
 second=box(3,0,4,.2).difference(box(3.48,.18,3.52,.21))
 current=first.union(second);source_parts=parts(original)
 blocked_source=next(i for i,g in enumerate(source_parts)if g.centroid.x<2)
 foreign_index=1-blocked_source
 guard=box(.48,.22,.52,.23)
 report,fills,result=module.plan(original,current,clearance_only={foreign_index:guard})
 rejected=[r for r in report['records']if r['status']=='KEEP_ENTIRE_FILL_CHECKING_ENVELOPE']
 assert rejected
 assert any(r['geometry'].centroid.x>2 for r in fills)
 assert not any(r['geometry'].centroid.x<2 for r in fills)
 assert result.intersection(box(.48,.18,.52,.21)).area==0


def test_actual_native_addition_rechecks_standard_envelope_without_plotting_guard():
 route=box(0,0,1,.1);pad=box(0,.2,1,.3)
 context=Context(route.union(pad),'source',{'route':route,'pad':pad})
 own=context.owner('route');other=context.owner('pad')
 context.checking_replay_envelopes={own:box(0,0,1,.11501)}
 assert check_native(context,{own:route,other:box(0,.155114,1,.3)},.0401)['passed']
 with pytest.raises(ValueError,match='NATIVE_REFERENCE_OCCUPIES'):
  check_native(context,{own:route,other:box(0,.1551,1,.3)},.0401)


@pytest.mark.parametrize('mutation',[None,'raw','audit'])
def test_prepared_envelopes_bind_original_width_ladder_and_all_three_t04_audits(tmp_path,mutation):
 from test_gerber_source import source_circle
 store=p.Store(tmp_path/'runtime');binding=p.build_source(store,source_circle())
 p.save(tmp_path/'source.json',binding)
 scene=store.get_json(binding['scene_ref'],kind='scene');rows,current,_=p.operands(store,scene)
 sid=next(iter(rows));rows[sid]['metadata']['minimum_caliper_mm']=.1
 scene_ref=store.put_json('scene',scene);binding=dict(binding,scene_ref=scene_ref)
 # Replace the source scene metadata only in this authored unit fixture.
 (tmp_path/'source.json').unlink();p.save(tmp_path/'source.json',binding)
 raw=dict(solution=dict(schema='source-route-ten-step-width-ladder/1'),part_factors={sid:1.3})
 final=dict(raw,t04_width_fence={'fixture':True},pin_separation={'fixture':True})
 p.save(tmp_path/'t04.json',final)
 for mode in('construct','1','2'):
  p.save(tmp_path/'audits/t04'/(mode+'.json'),dict(status='FAIL'if mutation=='audit'and mode=='2'else'PASS',candidate_sha256=p.digest(p.canonical(final))))
 if mutation=='raw':raw=dict(raw,part_factors={sid:1.2})
 p.save(tmp_path/'RAW_WIDTH_CHECKPOINT.json',raw)
 source=p.unary_union(list(current.values()));ctx=Context(source,binding['source_ref']['sha256'],current)
 if mutation:
  with pytest.raises(ValueError,match='CHECKING_ENVELOPE_'):install(ctx,store,binding)
 else:
  receipt=install(ctx,store,binding)
  assert receipt['role']=='CLEARANCE_ONLY_NOT_COPPER_NOT_MINIMUM_FLOOR'
  assert receipt['records'][0]['original_width_mm']==.1
  assert receipt['records'][0]['factor']==1.3
  assert ctx.reserved=={}
  assert ctx.project(current)=={ctx.owner(sid):source}
  assert not ctx.checking_envelopes[ctx.owner(sid)].difference(source).is_empty
