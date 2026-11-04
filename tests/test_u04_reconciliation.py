"""U04 reconciliation and predicate-preserving performance checks."""
import copy,json
from pathlib import Path
import pytest
from shapely import to_wkb,STRtree
from shapely.geometry import box
from shapely.ops import unary_union
from src.stage_abi.store import canonical,digest
from src.u04_board.search import FastRectangleAdapter
from src.u04_board.rectangles import NativeRectangleAdapter,parameters
from tests.test_u04_board import native_scene,rect,fixture

@pytest.mark.parametrize('foreign',[
 [],[box(-1,-1,2,2)],[box(-1,-1,.499,.4),box(.501,-1,2,2)],
 [box(-1,-1,.25,2)],[box(-1,-1,.24999999,2),box(.25000001,-1,2,2)],
 [box(10,10,11,11)],
])
def test_uncovered_witness_matches_complete_foreign_union(foreign):
 core=box(0,0,.5,.4);current={'owner':core,**{str(i):g for i,g in enumerate(foreign)}};ids=list(current);tree=STRtree(list(current.values()))
 assert FastRectangleAdapter.covered(core,'owner',current,ids,tree,{'owner'})==(core.difference(unary_union(foreign)).area<=1e-12)


def test_optimized_search_matches_full_materialization_reference(tmp_path):
 store,scene,_,_=native_scene(tmp_path,[rect(),rect(.55),rect(3), '(segment (start .3 .45) (end 1 .45) (width .05) (layer "F.Cu"))'])
 ids=[r['source_id'] for r in scene['objects'] if r['kind']=='rectangle'];ref=store.put_json('scene',scene);policy=dict(stage='t02',parameters=parameters());a=NativeRectangleAdapter();bounds=dict(max_source_objects=4,max_targets=3,max_evaluations=10000,max_output_bytes=10000000,max_seconds=300)
 details=a.plan(store,scene,policy,dict(stage='t02',scene_ref=ref,source_ids=ids),bounds);plan=dict(stage='t02',scene_ref=ref,policy_ref=store.put_json('policy',policy),implementation=a.describe()['implementation'],details=details)
 actual=a.run(store,scene,policy,plan,lambda _:None)
 class Reference(NativeRectangleAdapter):
  def _trial_check(self,*args):return self._check(*args)
  @staticmethod
  def covered(core,sid,current,ids,tree,aliases):return core.difference(unary_union([g for s,g in current.items() if s not in aliases])).area<=1e-12
 expected=Reference().run(store,scene,policy,plan,lambda _:None)
 assert actual==expected and actual['checks']['scene_union_materialized']
 assert a.verify(store,scene,policy,plan,actual,{'scope':'complete-source-land-and-inclusive'},lambda _:None)['passed']


def test_role_protection_holds_complete_parallel_group_and_validates_source(tmp_path,monkeypatch):
 import src.u04_board.roles as roles
 from src.source_bulk_components import bind_bulk_regions
 from tests.test_u03_board import source_case
 from shapely import from_wkb
 nodes=['(segment (start 0 0) (end 1 0) (width .1) (layer "F.Cu"))','(segment (start 0 .3) (end 1 .3) (width .1) (layer "F.Cu"))','(segment (start 3 0) (end 4 0) (width .1) (layer "F.Cu"))']
 raw,rows,blobs=source_case(nodes);seeds=[dict(name='fixed',point_mm=[.5,0])];scope=[-1,-1,5,1];_,bindings=bind_bulk_regions([from_wkb(blobs[s]) for s in sorted(blobs)],seeds,scope=box(*scope));receipt=tmp_path/'review.json';receipt.write_bytes(canonical(dict(status='FROZEN_C03_FINAL_SO_FAR_OWNER_ACCEPTED',source_sha256=digest(raw))))
 contract=tmp_path/'roles.json';contract.write_bytes(canonical(dict(profiles=[dict(source_sha256=digest(raw),review_receipt=str(receipt),review_receipt_sha256=digest(receipt.read_bytes()),scope_mm=scope,seeds=seeds,expected_regions=bindings,reviewed_fixed_sources=[])])));monkeypatch.setattr(roles,'CONTRACT',contract)
 report=roles.qualify(raw,rows,blobs,blobs)
 assert len(report['admitted_paths'])==1 and len(report['groups'])==1
 assert set(report['classifications'])=={'KEEP_REVIEWED_BULK','KEEP_GROUP_WITH_REVIEWED_BULK','ADMIT_COMPLETE_NATIVE_ROUTE'}
 changed=dict(blobs);changed[rows[0]['id']]=to_wkb(box(10,10,11,11))
 with pytest.raises(ValueError,match='RECONSTRUCTION_CHANGED|BULK_REGION'):roles.reviewed_roles(raw,rows,changed)
 receipt.write_bytes(b'changed')
 with pytest.raises(ValueError,match='REVIEW_CHANGED'):roles.reviewed_roles(raw,rows,blobs)
 assert roles.reviewed_roles(raw+b' ',rows,blobs)['profiles']==[]


def test_operation_local_replay_is_content_bound_and_corruption_rejects(tmp_path,monkeypatch):
 gates=fixture(tmp_path)
 for op in ('t02_inspect','t02_admit','t02_plan'):gates.dispatch(op)
 actual=gates.reconstruct();calls=[]
 monkeypatch.setattr(gates.adapter,'run',lambda *a: calls.append(1))
 assert gates.reconstruct()==actual and calls==[]
 path=gates.store.root/'artifacts'/gates._replay_ref['artifact_id'];path.write_bytes(b'corrupt')
 with pytest.raises(ValueError):gates.reconstruct()


def test_original_width_limits_ports_after_predecessor_widening(tmp_path):
 from shapely.affinity import scale
 store,scene,_,_=native_scene(tmp_path,[rect(), '(segment (start .25 .2) (end .8 .2) (width .1) (layer "F.Cu"))'])
 trace=next(r for r in scene['objects'] if r['metadata']['native_source_kind']=='segment');trace['metadata'].update(original_width_mm=.1,nominal_width_mm=.15)
 from shapely import from_wkb
 trace['geometry_ref']=store.put('geometry',to_wkb(scale(from_wkb(store.get(trace['geometry_ref'],kind='geometry')),1,1.5,origin='centroid')))
 sid=next(r['source_id'] for r in scene['objects'] if r['kind']=='rectangle');a=NativeRectangleAdapter();_,current,original,checker,_=a._context(store,scene,dict(stage='t02',parameters=parameters()),dict(targets=[sid]))
 assert checker.widths[trace['source_id']]==.1
 expected=original[sid].intersection(original[trace['source_id']]).buffer(.1+checker.contract.original_port_buffer_gap_mm,quad_segs=checker.contract.port_quad_segs)
 assert checker.ports[(sid,trace['source_id'])][0].equals_exact(expected,0)


def test_prepared_context_reuses_only_identical_hash_validated_source(tmp_path,monkeypatch):
 from src.stage_abi.lands import LandAdapter
 store,scene,_,_=native_scene(tmp_path,[rect()]);sid=scene['objects'][0]['source_id'];policy=dict(stage='t02',parameters=parameters());details=dict(targets=[sid]);a=NativeRectangleAdapter();calls=[];base=LandAdapter._context
 def tracked(*args):calls.append(1);return base(*args)
 monkeypatch.setattr(LandAdapter,'_context',tracked)
 first=a._context(store,scene,policy,details)
 assert a._context(store,scene,policy,details) is first and len(calls)==1
 bad=copy.deepcopy(policy);bad['parameters']['ceiling']=2
 with pytest.raises(ValueError):a._context(store,scene,bad,details)
 reference=scene['objects'][0]['geometry_ref'];(store.root/'artifacts'/reference['artifact_id']).write_bytes(b'corrupt')
 with pytest.raises(ValueError):a._context(store,scene,policy,details)
