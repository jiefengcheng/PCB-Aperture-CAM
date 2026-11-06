import pytest
from shapely.geometry import Polygon,box
from src.component_voids import RemedyContract
from src.gerber_u05.joint_smoothing import propose


def body():
 return Polygon([(0,0),(.12,0),(.12,.1),(.10,.15),(.12,.2),(.12,.3),(0,.3)])


def test_additive_local_joint_rounds_without_source_loss():
 owner=body();window=box(.07,.05,.13,.25)
 value,proof=propose(owner,owner,window,[],RemedyContract(),allowed=window)
 assert proof['status']=='GROWN'
 assert value['addition'].area>1e-8
 assert value['region'].difference(window).area<1e-12
 assert owner.union(value['region']).covers(owner)


def test_foreign_clearance_rejects_complete_profile():
 owner=body();window=box(.07,.05,.13,.25)
 value,proof=propose(owner,owner,window,[('other',box(.14,0,.2,.3))],RemedyContract(),allowed=window)
 assert value is None and 'FOREIGN_CLEARANCE_FAILED'in proof['reasons']


def test_source_contact_window_is_required():
 value,proof=propose(body(),body(),box(.07,.05,.13,.25),[],RemedyContract(),allowed=box(0,0,.05,.05))
 assert value is None and proof['reasons']==['OUTSIDE_SOURCE_CONTACT_WINDOW']


def test_pin_rejection_is_whole_not_trimmed():
 class Rule:
  def remedy(self,logical,predecessor):
   assert logical.area>0
   return dict(passed=False,status='REJECT_ENTIRE_LOGICAL_FILL')
 value,proof=propose(body(),body(),box(.07,.05,.13,.25),[],RemedyContract(),pin_rule=Rule())
 assert value is None and proof['reasons']==['PROTECTED_PIN_SEPARATION']


@pytest.mark.parametrize('functional',[False,True])
def test_stage_application_stores_one_checked_local_profile(tmp_path,monkeypatch,functional):
 from shapely.geometry import Point
 from src.gerber_u05 import pipeline as p,component_policy
 from src.gerber_u05.joint_smoothing import apply
 from src import component_clearance as cc
 store=p.Store(tmp_path/'runtime');core=body();circle=Point(.04,.15).buffer(.04);land=Point(.04,.15).buffer(.06);owner=core.union(land);ref=lambda g:p.geomref(store,g)
 rows=[dict(source_id='body',kind='fixed_source',original_ref=ref(core),geometry_ref=ref(core),metadata={}),dict(source_id='land',kind='circle',original_ref=ref(circle),geometry_ref=ref(land),metadata=dict(center_mm=[.04,.15])),dict(source_id='route',kind='trace',original_ref=ref(box(.03,.14,.07,.16)),geometry_ref=ref(box(.03,.14,.07,.16)),metadata={})]
 scene=dict(source_sha256='fixture',frame='mm',units='mm',layer='F.Cu',viewport_mm=[-1,-1,1,1],objects=rows,lineage=[],findings=[]);scene_ref=store.put_json('scene',scene)
 class Index:
  def membership(self,g):return ['own']
 class Context:
  index=Index();cores={'own':core};reserved={};source_hash='fixture'
  def owner(self,sid):return 'own'
  def assign(self,*args):return ('own',)
 context=Context();physical_source=core
 if functional:
  from types import SimpleNamespace
  other=box(-.25,.05,-.21,.25)
  frame=box(-.25,-.05,.05,-.01).union(box(-.02,-.05,.02,.02)).union(box(-.25,-.05,-.21,.06))
  physical_source=core.union(other).union(frame)
  context.index=SimpleNamespace(source=physical_source)
  context.functional=Context();context.functional.cores={'own':core,'other':other}
 monkeypatch.setattr(cc,'ACTIVE',context)
 config=dict(radius_fraction=.25,sources={'fixture':[dict(id='joint',center_mm=[.04,.15],source_geometry_sha256=ref(circle)['sha256'],window_mm=[.07,.05,.13,.25])]})
 monkeypatch.setattr(component_policy,'read_job',lambda _:({'t05_joint_profiles':config},[RemedyContract()]))
 before=dict(output_scene_ref=scene_ref,after_native_ref=ref(owner),before_native_ref=ref(owner),fills=[],feature_counts={},summary={'fills':0})
 if functional:
  before.update(after_native_ref=ref(physical_source.union(owner)),before_native_ref=ref(physical_source.union(owner)),native_channel_refs={'own':ref(owner),'other':ref(other)})
 t05=dict(plan={'scene_ref':scene_ref},candidate={'decisions':[dict(source_id='route',land_ids=['land'])]})
 after=apply(store,scene,{'source_ref':{'sha256':'fixture'}},before,'t05',t05)
 assert after['summary']['joint_profiles_grown']==1
 assert len(after['fills'])==1
 assert len(store.get_json(after['output_scene_ref'])['objects'])==4
 assert p.geometry(store,after['after_native_ref']).difference(owner).area>1e-8
 if functional:
  material=p.geometry(store,after['after_native_ref'])
  assert physical_source.difference(material).area<1e-12
  assert p.geometry(store,after['native_channel_refs']['other']).equals(other)
  assert p.geometry(store,after['native_channel_refs']['own']).intersection(frame).area==owner.intersection(frame).area
