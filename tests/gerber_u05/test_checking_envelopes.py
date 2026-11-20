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


def test_obstacle_reuse_preserves_exact_union_and_recreated_operands(monkeypatch):
 from shapely import from_wkb,to_wkb,get_precision
 material=box(0,0,1,.1);reserved=box(.9,0,2,.1);guard=material.buffer(.000014)
 context=SimpleNamespace(reserved={'a':reserved},checking_envelopes={'a':guard})
 expected=cc.joined([material,reserved,guard]);join=cc.joined;calls=[]
 def counted(values):calls.append(1);return join(values)
 monkeypatch.setattr(cc,'joined',counted)
 assert to_wkb(constraint(context,'a',material))==to_wkb(expected)
 context.reserved['a']=from_wkb(to_wkb(reserved))
 context.checking_envelopes['a']=from_wkb(to_wkb(guard))
 result=constraint(context,'a',from_wkb(to_wkb(material)))
 assert to_wkb(result)==to_wkb(expected) and get_precision(result)==get_precision(expected)
 assert len(calls)==1
 assert context._checking_constraint_memo.stats['hits']==1


@pytest.mark.parametrize('change',['material','reservation','checking','remove_reservation','precision','owner'])
def test_obstacle_reuse_invalidates_every_changed_input(change):
 from shapely import to_wkb,set_precision,from_wkb,get_precision
 material=set_precision(box(0,0,1,.1),.0001);reserved=box(.9,0,2,.1);guard=box(-.01,-.01,1.01,.11)
 context=SimpleNamespace(reserved={'a':reserved},checking_envelopes={'a':guard});owner='a'
 constraint(context,owner,material)
 if change=='material':material=box(0,0,1,.2)
 if change=='reservation':context.reserved['a']=box(.9,0,2,.2)
 if change=='checking':context.checking_envelopes['a']=box(-.01,-.01,1.01,.21)
 if change=='remove_reservation':context.reserved.clear()
 if change=='precision':material=from_wkb(to_wkb(material))
 if change=='owner':
  owner='b';context.reserved['b']=reserved;context.checking_envelopes['b']=guard
 operands=[material]
 if owner in context.reserved:operands.append(context.reserved[owner])
 if owner in context.checking_envelopes:operands.append(context.checking_envelopes[owner])
 expected=cc.joined(operands);actual=constraint(context,owner,material)
 assert to_wkb(actual)==to_wkb(expected) and get_precision(actual)==get_precision(expected)
 assert context._checking_constraint_memo.stats['builds']==2


def test_warmed_obstacle_cannot_hide_a_new_foreign_reservation():
 material=box(0,0,1,.1);proposal=box(0,.16,1,.3)
 context=SimpleNamespace(reserved={},checking_envelopes={'a':box(0,0,1,.11)})
 assert proposal.distance(constraint(context,'a',material))>=.0401
 context.reserved['a']=box(0,0,1,.13)
 assert proposal.distance(constraint(context,'a',material))<.0401
 context.reserved.clear();context.checking_envelopes.clear()
 assert constraint(context,'a',material) is material


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


def preparation_fixture(tmp_path):
 from test_gerber_source import source_circle
 store=p.Store(tmp_path/'runtime');binding=p.build_source(store,source_circle())
 scene=store.get_json(binding['scene_ref'],kind='scene');sid=scene['objects'][0]['source_id']
 scene['objects'][0]['metadata']['minimum_caliper_mm']=.1
 binding=dict(binding,scene_ref=store.put_json('scene',scene));p.save(tmp_path/'source.json',binding)
 raw=dict(solution=dict(schema='source-route-ten-step-width-ladder/1'),part_factors={sid:1.3})
 def write_checkpoint(raw):
  import json
  final=dict(raw,t04_width_fence={'fixture':True},pin_separation={'fixture':True})
  (tmp_path/'RAW_WIDTH_CHECKPOINT.json').write_text(json.dumps(raw));(tmp_path/'t04.json').write_text(json.dumps(final))
  for mode in ('construct','1','2'):
   path=tmp_path/'audits/t04'/(mode+'.json');path.parent.mkdir(parents=True,exist_ok=True)
   path.write_text(json.dumps(dict(status='PASS',candidate_sha256=p.digest(p.canonical(final)))))
 write_checkpoint(raw)
 def context():
  _,current,_=p.operands(store,scene)
  return Context(p.unary_union(list(current.values())),binding['source_ref']['sha256'],current)
 return store,binding,scene,sid,raw,write_checkpoint,context


def test_envelope_preparation_reuses_geometry_with_identical_receipt(tmp_path):
 from shapely import to_wkb
 store,binding,scene,sid,raw,write_checkpoint,context=preparation_fixture(tmp_path)
 first=context();expected=install(first,store,binding);memo=first._checking_preparation_memo;builds=memo.stats['builds']
 second=context();actual=install(second,store,binding,reuse_from=first)
 assert actual==expected and second.binding==first.binding
 assert second._checking_preparation_memo is memo and memo.stats['builds']==builds and memo.stats['hits']==4
 for attr in ('checking_envelopes','checking_replay_envelopes'):
  assert {k:to_wkb(g)for k,g in getattr(first,attr).items()}=={k:to_wkb(g)for k,g in getattr(second,attr).items()}
 assert first.checking_envelopes is not second.checking_envelopes


@pytest.mark.parametrize('mutation',['factor','width','geometry','headroom'])
def test_envelope_reuse_matches_cold_build_after_input_changes(tmp_path,monkeypatch,mutation):
 import json
 from shapely import to_wkb
 from src.gerber_u05 import checking_envelopes as ce
 store,binding,scene,sid,raw,write_checkpoint,context=preparation_fixture(tmp_path)
 donor=context();install(donor,store,binding)
 if mutation=='factor':raw['part_factors'][sid]=1.4;write_checkpoint(raw)
 if mutation=='width':scene['objects'][0]['metadata']['minimum_caliper_mm']=.2
 if mutation=='geometry':
  ref=p.geomref(store,box(0,0,.1,.1));scene['objects'][0].update(original_ref=ref,geometry_ref=ref)
 if mutation in ('width','geometry'):
  binding=dict(binding,scene_ref=store.put_json('scene',scene));(tmp_path/'source.json').write_text(json.dumps(binding))
 if mutation=='headroom':monkeypatch.setattr(ce,'NATIVE_HEADROOM_MM',0.)
 cold=context();warm=context();expected=install(cold,store,binding);actual=install(warm,store,binding,reuse_from=donor)
 assert actual==expected
 for attr in ('checking_envelopes','checking_replay_envelopes'):
  assert {k:to_wkb(g)for k,g in getattr(cold,attr).items()}=={k:to_wkb(g)for k,g in getattr(warm,attr).items()}


def test_warm_envelope_memo_does_not_skip_audits_or_scalar_validation(tmp_path):
 import json
 store,binding,scene,sid,raw,write_checkpoint,context=preparation_fixture(tmp_path)
 donor=context();install(donor,store,binding)
 path=tmp_path/'audits/t04/2.json';value=json.loads(path.read_text());value['status']='FAIL';path.write_text(json.dumps(value))
 with pytest.raises(ValueError,match='CHECKING_ENVELOPE_T04_AUDIT_CHANGED'):install(context(),store,binding,reuse_from=donor)
 with pytest.raises(ValueError,match='SCALAR_OR_WIDTH_INVALID'):p.offset_part(box(0,0,1,1),.1,1.6,True,memo=donor._checking_preparation_memo)
