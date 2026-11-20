from pathlib import Path
import pytest
from shapely.geometry import LineString,Point,Polygon
from shapely.affinity import translate
from src.gerber_u05.translated_profile import parameters,profile_body,SCHEMA

def test_bounded_only_and_parameter_validation():
 for v in (.10,.25):assert parameters(dict(schema=SCHEMA,scope='BOUNDED',width_variation_limit=v),['r'])==v
 with pytest.raises(ValueError):parameters(dict(schema=SCHEMA,scope='FULL_BOARD',width_variation_limit=.25),['r'])
 for v in (-.1,.26,float('nan')):
  with pytest.raises(ValueError):parameters(dict(schema=SCHEMA,scope='BOUNDED',width_variation_limit=v),['r'])

def test_complete_route_translation_retains_new_reference_and_explicitly_vacates_old_trace():
 line=LineString([(0,0),(1,0)]);core=line.buffer(.025,quad_segs=128);pose=(0.,.015)
 a=profile_body(core,.05,.06,.066,pose,line,Polygon());b=profile_body(core,.05,.06,.075,pose,line,Polygon())
 for g,high in [(a,.066),(b,.075)]:
  shifted=translate(core,yoff=.015);assert g.covers(shifted) and g.geom_type=='Polygon' and core.difference(g).area>0
  assert g.difference(shifted.buffer((high-.05)/2,quad_segs=128)).area<1e-12
 # In the corridor the parameter leaves the same 60 µm width.
 section=LineString([(.5,-.2),(.5,.2)])
 assert abs(a.intersection(section).length-.060)<1e-10
 assert abs(b.intersection(section).length-.060)<1e-10

def test_checking_envelope_covers_nominal():
 core=LineString([(0,0),(.5,0)]).buffer(.025,quad_segs=128);line=LineString([(0,0),(.5,0)])
 nominal=profile_body(core,.05,.06,.075,(.005,.01),line,Polygon());envelope=profile_body(core,.05,.06,.075,(.005,.01),line,Polygon(),envelope=True)
 assert envelope.covers(nominal)

def test_predecessor_void_is_not_reset_by_relocation(monkeypatch):
 import src.t04_topology as top
 from types import SimpleNamespace
 monkeypatch.setattr(top,'holes_required',lambda:True)
 full=Point(0,0).buffer(1);hole=Point(0,0).buffer(.2);old=full.difference(hole)
 d=SimpleNamespace(owners={'r':'o'},context=SimpleNamespace(cores={'o':full},source_void_reference={'o':old}),before={'o':full})
 with pytest.raises(ValueError,match='SOURCE_VOID_MISSING'):top.SourceVoids(d,1024**2)

def test_alias_binding_rejects_a_changed_original_and_missing_body(tmp_path):
 from src.gerber_u05.pipeline import Store,geomref
 from src.gerber_u05.translated_profile import resolve_operands,ALIAS
 store=Store(tmp_path/'runtime');shape=Point(0,0).buffer(.1);ref=geomref(store,shape);empty=geomref(store,Polygon());alias=dict(schema=ALIAS,source_id='s',route_id='r',original_ref=ref,body_ref=ref)
 source=dict(source_sha256='a'*64,objects=[dict(source_id='s',kind='stroke',original_ref=ref,geometry_ref=ref,metadata={'minimum_caliper_mm':.2})]);inputref=store.put_json('scene',source)
 ledger=dict(schema=SCHEMA,source_sha256='a'*64,input_scene_ref=inputref,maximum_translation_mm=.025,width_variation_limit=.25,growth_source_ids_by_route={'r':['s']},route_owners={'r':'owner'},route_plans={'r':dict(translation_mm=[0.,0.],source_width_mm=.2,corridor_width_mm=.2,outer_width_ceiling_mm=.2)},source_aliases={'s':alias},published_routes={'r':dict(translated_reference_ref=ref,input_route_ref=ref,source_refs={'s':ref},translation_mm=[0.,0.],selected_progress=1.)},removed_bulk_sources={},bulk_roles={})
 lr=store.put_json('t04-route-motion',ledger)
 scene=dict(source_sha256='a'*64,lineage=[dict(stage='t04-translated-profile-published',receipt_ref=lr)],objects=[dict(source_id='s',kind='stroke',original_ref=ref,geometry_ref=empty,metadata={'translated_route_alias':alias}),dict(source_id='r',kind='trace',original_ref=ref,geometry_ref=ref,metadata={'reference_source_ids':['s'],'original_channel_id':'owner'})])
 _,current,_=resolve_operands(store,scene);assert current['s'].is_empty and current['r'].equals(shape)
 scene['objects'][0]['original_ref']=geomref(store,shape.buffer(.01))
 with pytest.raises(ValueError,match='ALIAS_BINDING'):resolve_operands(store,scene)
 scene['objects'][0]['original_ref']=ref;scene['objects'].pop()
 with pytest.raises(ValueError,match='BODY_MISSING'):resolve_operands(store,scene)

def test_translated_output_is_blocked_from_unqualified_downstream():
 from src.gerber_u05.t04_edge_entry import reject_unqualified_predecessor
 with pytest.raises(ValueError,match='PROFILE_DOWNSTREAM'):
  reject_unqualified_predecessor(dict(lineage=[dict(stage='t04-translated-profile-published')]))

def test_translation_only_candidate_still_has_checking_envelope():
 line=LineString([(0,0),(.5,0)]);core=line.buffer(.025,quad_segs=128)
 nominal=profile_body(core,.05,.05,.05,(0,.01),line,Polygon());envelope=profile_body(core,.05,.05,.05,(0,.01),line,Polygon(),envelope=True)
 assert envelope.covers(nominal) and not envelope.equals(nominal)

def test_actual_caller_requires_motion_gate_and_restores_context_on_rejection(monkeypatch):
 from contextlib import contextmanager
 from types import SimpleNamespace
 from src.gerber_u05 import ladder_width,constructed_width,translated_profile,motion_final_validation
 events=[];inputscene={'lineage':[]};preparedscene={'lineage':[{'stage':'test-prepared'}]};obj=SimpleNamespace(relocation=True,mutable_route_ids=['r'])
 @contextmanager
 def prepared(*args,**kw):
  events.append('prepare')
  try:yield preparedscene,obj
  finally:events.append('restore')
 def run(store,scene,**kw):
  assert scene is preparedscene and kw['construction'] is obj
  events.append('native-final-checks');return {'output':'unpublished'}
 def reject(store,result,construction):
  assert events==['prepare','native-final-checks'] and construction is obj
  events.append('motion-gate');raise ValueError('T04_TRANSLATED_FULL_SCENE_REJECTED')
 monkeypatch.setattr(translated_profile,'prepared',prepared);monkeypatch.setattr(constructed_width,'checked',run);monkeypatch.setattr(motion_final_validation,'verify',reject)
 with pytest.raises(ValueError,match='TRANSLATED_FULL_SCENE_REJECTED'):
  ladder_width.run(None,inputscene,route_ids=['r'],settings=object(),limiting_rule={'schema':SCHEMA})
 assert events==['prepare','native-final-checks','motion-gate','restore']

def test_final_void_check_does_not_skip_changed_envelope_at_factor_one(monkeypatch):
 from types import SimpleNamespace
 import src.t04_topology as top
 monkeypatch.setattr(top,'holes_required',lambda:True)
 solid=Point(0,0).buffer(1);old=solid.difference(Point(0,0).buffer(.1))
 d=SimpleNamespace(owners={'r':'o'},context=SimpleNamespace(cores={'o':old}),before={'o':old},route_ids=['r'],route_tree=top.STRtree([solid]),original_route_geometries={'r':old})
 voids=top.SourceVoids(d,1024**2)
 q=voids.complete({'r':solid},{'r':1.})
 assert not q['passed'] and q['failures'][0]['reason']=='ORIGINAL_SOURCE_ROUTE_VOID_REMOVED'

@pytest.mark.parametrize('dx,passes',[(.020,False),(-.020,True)])
def test_complete_gate_checks_motion_against_old_owner_surface_not_new_reference(tmp_path,monkeypatch,dx,passes):
 from types import SimpleNamespace
 from shapely.geometry import box
 from src.gerber_u05.pipeline import Store
 import src.gerber_u05.motion_final_validation as gate
 old=box(0,0,.010,1);foreign=box(.060,0,.070,1);moved=translate(old,xoff=dx)
 ctx=SimpleNamespace(cores={'A':moved,'B':foreign},ids={'r':('A',),'fixed':('B',)},frame_ids=())
 monkeypatch.setattr(gate.sc,'ACTIVE',ctx)
 material={'r':moved,'fixed':foreign}
 monkeypatch.setattr(gate.p,'operands',lambda store,scene:({},material,{}))
 obj=SimpleNamespace(before_owners={'A':old,'B':foreign},paths={'r':['member']},receipt={'route_owners':{'r':'A'}},chosen={'r':{'pose':(dx,0.)}},oldcores={'r':old},route=lambda r,f,envelope:moved.buffer(.000014) if envelope else moved,rows={},input_current={},original={},source_owner_ids={})
 store=Store(tmp_path/'runtime');scene=store.put_json('scene',{})
 result=dict(output_scene_ref=scene,solution={'selected_scales':{'r':1.5}},limiting_construction={'source_sha256':'a'*64})
 if passes:assert gate.verify(store,result,obj)['passed']
 else:
  with pytest.raises(ValueError,match='TRANSLATED_FULL_SCENE_REJECTED'):gate.verify(store,result,obj)
