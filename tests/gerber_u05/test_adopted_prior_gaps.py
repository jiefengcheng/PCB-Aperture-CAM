"""Native floor support is checked after selecting the actual adopted scene."""
import pytest
from shapely.geometry import box
from shapely.ops import unary_union
from src.gerber_u05 import pipeline as p,prior_copper,channel_prior
from src import component_clearance as cc,t02_shared_gaps as gaps
from src import pin_separation,source_channel_scope,t04_width_fence
from src.pcb_data_abi.geometry import GRID_MM


class Owners:
 def __init__(self,source,prior):
  self.cores=source;self.reserved=prior;self.source_hash='a'*64
  self.reservation_sha256='b'*64;self.owner={s:s for s in source};self.functional=None
 def project(self,material):
  return {own:unary_union([g for sid,g in material.items()if self.owner[sid]==own])for own in self.cores}
 def register_scene(self,*args):pass
 def assign(self,sid,geometry,owners):
  assert len(owners)==1
  self.owner[sid]=owners[0]
 def partial_pocket_failures(self,material):return []


def case(tmp_path,monkeypatch,prior_a,channel):
 for module in (gaps,cc,pin_separation,source_channel_scope,t04_width_fence):
  monkeypatch.setattr(module,'ACTIVE',None)
 source=dict(a=box(0,0,1,1),b=box(0,2,1,3),wall=box(2,-1,3,4))
 store=p.Store(tmp_path/'runtime');ref=lambda g:p.geomref(store,g)
 scene=dict(source_sha256='a'*64,frame='test',units='mm',layer='F.Cu',viewport_mm=[-6,-6,6,6],objects=[dict(source_id=s,kind='rectangle'if s!='wall'else'fixed',original_ref=ref(g),geometry_ref=ref(g),metadata={})for s,g in source.items()],lineage=[],findings=[],acceptance={})
 spec=gaps.records(scene,source,source);_,proof=gaps.project(spec,source,source,{s:source[s]for s in ('a','b')})
 assert len(proof['zones'])==2
 monkeypatch.setattr(gaps,'ACTIVE',proof)
 prior=dict(source,a=prior_a);context=Owners(source,prior);monkeypatch.setattr(cc,'ACTIVE',context)
 if channel:
  context.functional=Owners(source,prior)
  monkeypatch.setattr(channel_prior,'check_owned',lambda scope,material:dict(passed=True))
  monkeypatch.setattr(channel_prior,'physical_owner',lambda scope,identity,physical:identity)
 return source,scene,store,context


@pytest.mark.parametrize('channel',[False,True])
def test_unadopted_native_grid_support_cannot_cause_false_gap_failure(tmp_path,monkeypatch,channel):
 source,scene,store,context=case(tmp_path,monkeypatch,box(0,0,1+GRID_MM/2,1),channel)
 # This is the historical false failure: the entire reference is not the
 # material selected by the existing one-grid containment guard.
 with pytest.raises(ValueError,match='UNIFORMITY'):
  prior_copper.require_shared_prior(prior_copper.protected_owners(source,context.reserved))
 output,receipt=prior_copper.prepare(store,scene)
 _,actual,_=p.operands(store,output)
 assert receipt['records']==[]
 assert unary_union(list(actual.values())).equals(unary_union(list(source.values())))
 assert receipt['shared_neighbor_gaps']['passed']
 assert all(row['missing_boundary_mm']==0 for row in receipt['shared_neighbor_gaps']['boundaries'])


@pytest.mark.parametrize('channel',[False,True])
def test_real_required_floor_outside_gap_is_retained(tmp_path,monkeypatch,channel):
 source,scene,store,context=case(tmp_path,monkeypatch,box(-.2,0,1,1),channel)
 output,receipt=prior_copper.prepare(store,scene)
 _,actual,_=p.operands(store,output);whole=unary_union(list(actual.values()))
 assert len(receipt['records'])==1
 assert whole.covers(unary_union(list(source.values())))
 assert context.reserved['a'].difference(whole.buffer(2*GRID_MM)).area<=1e-12
 assert receipt['shared_neighbor_gaps']['passed']


@pytest.mark.parametrize('channel',[False,True])
def test_actually_adopted_intrusion_still_rejects_complete_floor(tmp_path,monkeypatch,channel):
 source,scene,store,context=case(tmp_path,monkeypatch,box(0,0,1.01,1),channel)
 # A real gap change remains forbidden, even when ordinary foreign clearance
 # is ample. Moving the check must not become a gap-tolerance exemption.
 with pytest.raises(ValueError,match='UNIFORMITY'):
  prior_copper.prepare(store,scene)
