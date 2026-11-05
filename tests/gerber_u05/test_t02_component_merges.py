from types import SimpleNamespace
import copy
import pytest
from shapely.geometry import box
from shapely.ops import unary_union
from src.gerber_u05 import pipeline as p
from src import component_clearance as cc
from src.gerber_u05.component_rectangles import ComponentRectangleAdapter

def fixture(store,*,bridge=True,foreign=False):
 original=dict(a=box(0,0,1,1),b=box(1.1,0,2.1,1))
 if bridge:original['stroke']=box(.9,.45,1.2,.55)
 if foreign:original['foreign']=box(1.035,1.02,1.065,1.04)
 ctx=cc.bind(unary_union(list(original.values())),'0'*64,original);ctx.reserved=dict(ctx.cores);rows={}
 for sid,g in original.items():
  ref=p.geomref(store,g);rows[sid]=dict(source_id=sid,kind='rectangle'if sid in('a','b')else'stroke',original_ref=ref,geometry_ref=ref,metadata=dict(original_width_mm=.1,nominal_width_mm=.1))
 scene=dict(viewport_mm=[-1,-1,4,3],objects=list(rows.values()),lineage=[dict(stage='source')]);plan=dict(details=dict(targets=['a','b'],containment={s:dict(contained=False)for s in('a','b')}));budget=SimpleNamespace(evaluation=lambda:None,output=lambda x:None)
 return ctx,rows,original,scene,plan,budget

def test_trace_pad_component_is_not_its_own_inclusive_clearance_obstacle(tmp_path):
 store=p.Store(tmp_path/'store');ctx,rows,current,scene,plan,budget=fixture(store);records,additions=ComponentRectangleAdapter('t02')._merges(store,scene,plan,rows,current,budget)
 assert records[0]['status']=='MERGED'and len(additions)==1 and not records[0]['foreign_component_pairs']
 derived=dict(scene,objects=scene['objects']+additions);ctx.register_scene(store,derived)
 assert ctx.owner(additions[0]['source_id'])==ctx.owner('a')==ctx.owner('b')
 changed=copy.deepcopy(derived);changed['objects'][-1]['metadata']['original_component_owner_id']='0'*64
 with pytest.raises(ValueError,match='INCLUSIVE_ORIGINAL_OWNER_CHANGED'):ctx.register_scene(store,changed)

def test_inclusive_merge_cannot_connect_distinct_original_owners(tmp_path):
 store=p.Store(tmp_path/'store');ctx,rows,current,scene,plan,budget=fixture(store,bridge=False);records,additions=ComponentRectangleAdapter('t02')._merges(store,scene,plan,rows,current,budget)
 assert not additions and 'MIXED_ORIGINAL_COPPER_OWNERS'in records[0]['reasons']

def test_true_foreign_clearance_remains_enforced_for_inclusive_delta(tmp_path):
 store=p.Store(tmp_path/'store');ctx,rows,current,scene,plan,budget=fixture(store,foreign=True);records,additions=ComponentRectangleAdapter('t02')._merges(store,scene,plan,rows,current,budget)
 assert not additions and 'FOREIGN_COMPONENT_CLEARANCE_FAILED'in records[0]['reasons']
 assert any(not r['passed']for r in records[0]['foreign_component_pairs'])
