"""Shared-neighbor geometry, exact KEEP anchors and complete-fill vetoes."""
import copy
import pytest
from shapely.geometry import box
from shapely.affinity import scale,rotate
from shapely.ops import unary_union
from shapely import to_wkb
from src import t02_shared_gaps as gaps,component_clearance as cc,pin_separation as pin,source_channel_scope,t04_width_fence
from src.stage_abi.store import ArtifactStore
from src.stage_abi.lands import LandAdapter,land_parameters
from src.u04_board.search import FastRectangleAdapter
from src.gerber_u05.component_rectangles import ComponentRectangleAdapter

@pytest.fixture(autouse=True)
def contexts(monkeypatch):
 for module in (gaps,cc,pin,source_channel_scope,t04_width_fence):monkeypatch.setattr(module,'ACTIVE',None)

def fixture(tmp_path,*,rotation=False):
 source=dict(a=box(0,0,1,1),b=box(0,2,1,3),wall=box(2,-1,3,4))
 if rotation:source={s:rotate(g,90,origin=(0,0))for s,g in source.items()}
 store=ArtifactStore(tmp_path/'runtime');ref=lambda g:store.put('geometry',to_wkb(g))
 rows=[dict(source_id=s,kind='rectangle'if s!='wall'else'fixed',original_ref=ref(g),geometry_ref=ref(g),metadata={})for s,g in source.items()]
 scene=dict(source_sha256='a'*64,frame='test',units='mm',layer='F.Cu',viewport_mm=[-6,-6,6,6],objects=rows,lineage=[],findings=[],acceptance={})
 return source,scene,store

@pytest.mark.parametrize('rotation',[False,True])
def test_shared_wall_projects_only_optional_axis_growth_and_preserves_normal_axis(tmp_path,rotation):
 original,scene,store=fixture(tmp_path,rotation=rotation);spec=gaps.records(scene,original,original)
 assert len(spec['groups'])==1
 proposed=dict(a=scale(original['a'],1.2,1.2,origin=original['a'].centroid),b=scale(original['b'],1.1,1.1,origin=original['b'].centroid))
 result,proof=gaps.project(spec,original,original,proposed)
 axis=1 if rotation else 0
 for sid in result:
  assert result[sid].covers(original[sid])and result[sid].difference(proposed[sid]).area<1e-12
  assert result[sid].bounds[axis+2]-result[sid].bounds[axis]==pytest.approx(1.1)
 other=1-axis
 assert result['a'].bounds[other+2]-result['a'].bounds[other]==pytest.approx(1.2)
 whole=unary_union([result['a'],result['b'],original['wall']]);assert gaps.complete(proof,whole)['passed']
 assert {round(r['gap_mm'],10)for r in proof['zones']}=={.95}

@pytest.mark.parametrize('held',['unselected','exposure_keep'])
def test_held_peer_anchors_shared_bank_without_blocking_other_axis(tmp_path,held):
 original,scene,store=fixture(tmp_path);spec=gaps.records(scene,original,original)
 proposed=dict(a=scale(original['a'],1.2,1.2,origin=original['a'].centroid))
 if held=='exposure_keep':proposed['b']=original['b']
 result,proof=gaps.project(spec,original,original,proposed)
 assert result['a'].bounds[0::2]==original['a'].bounds[0::2]
 assert result['a'].area>original['a'].area and all(r['gap_mm']==1 for r in proof['zones'])

@pytest.mark.parametrize('implementation',[LandAdapter,FastRectangleAdapter,ComponentRectangleAdapter])
def test_all_public_adapters_reconstruct_partial_selection_and_reject_stale_plan(tmp_path,implementation):
 original,scene,store=fixture(tmp_path);adapter=implementation('t02');ref=store.put_json('scene',scene);policy=dict(stage='t02',parameters=land_parameters('t02'));bounds=dict(max_source_objects=100,max_targets=100,max_evaluations=10000,max_output_bytes=10**7,max_seconds=60)
 details=adapter.plan(store,scene,policy,dict(stage='t02',scene_ref=ref,source_ids=['a']),bounds);plan=dict(stage='t02',scene_ref=ref,policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details)
 candidate=adapter.run(store,scene,policy,plan,lambda _:None)
 d=candidate['decisions'][0];assert d['shape']['factors'][0]==1 and d['shape']['factors'][1]>1
 assert adapter.verify(store,scene,policy,plan,candidate,{'scope':'complete-source-land-and-inclusive'},lambda _:None)['passed']
 bad=copy.deepcopy(candidate);bad['shared_neighbor_gaps']['zones'][0]['gap_mm']-=.01
 with pytest.raises(Exception)as error:adapter.verify(store,scene,policy,plan,bad,{'scope':'complete-source-land-and-inclusive'},lambda _:None)
 assert error.value.code=='SHARED_GAP_RECONSTRUCTION_CHANGED'
 details['shared_neighbor_gaps']['groups']=[]
 with pytest.raises(Exception)as error:adapter.run(store,scene,policy,plan,lambda _:None)
 assert error.value.code=='SHARED_GAP_PLAN_CHANGED'

def test_fills_reject_entire_logical_proposal_and_encoded_bypass(tmp_path,monkeypatch):
 original,scene,store=fixture(tmp_path);spec=gaps.records(scene,original,original);_,proof=gaps.project(spec,original,original,dict(a=original['a']))
 before=unary_union(list(original.values()));bad=box(.5,.2,2.2,.8);good=box(-.1,.1,.2,.8)
 details=dict(shared_neighbor_gaps=spec,targets=['a'])
 assert not gaps.fill_check(details,original,bad)['passed']
 assert gaps.fill_check(details,original,good)['passed']
 monkeypatch.setattr(gaps,'ACTIVE',proof)
 from src.growth_remedy_constraints import remedy,encoded_remedy,require_remedy
 assert not remedy(bad.union(good),before)['passed']
 assert remedy(good,before)['passed']
 assert not encoded_remedy(good,bad.union(good),before)['passed']
 with pytest.raises(ValueError,match='SHARED_GAP_REMEDY'):require_remedy(bad,before)

def test_actual_material_intrusion_and_missing_face_fail_even_when_min_clearance_safe(tmp_path):
 original,scene,store=fixture(tmp_path);spec=gaps.records(scene,original,original);_,proof=gaps.project(spec,original,original,dict(a=original['a'],b=original['b']))
 whole=unary_union(list(original.values()))
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.complete(proof,whole.union(box(1,.2,1.001,.8)),tolerance_mm=.000002)
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.complete(proof,whole.difference(box(.99,.2,1.01,.8)))
 with pytest.raises(ValueError,match='STAGE_ENTRY_INTRUSION'):gaps.records(scene,original,dict(original,a=scale(original['a'],1.1,1.,origin=original['a'].centroid)))

def test_nonshared_or_obstructed_and_integral_joint_faces_are_not_grouped(tmp_path):
 original,scene,store=fixture(tmp_path)
 # Separate wall fragments are different source components, not a shared wall.
 original['wall']=box(2,-.1,3,1.1).union(box(2,1.9,3,3.1))
 assert not gaps.records(scene,original,original)['groups']
 original,scene,store=fixture(tmp_path/'two');original['joint']=box(.5,-1,1.5,4)
 scene['objects'].append(dict(source_id='joint',kind='trace',metadata={}))
 assert not gaps.records(scene,original,original)['groups']

def test_frozen_state_restores_and_rejects_later_uniform_regrowth_or_state_loss(tmp_path):
 original,scene,store=fixture(tmp_path);adapter=FastRectangleAdapter('t02');ref=store.put_json('scene',scene);policy=dict(stage='t02',parameters=land_parameters('t02'));bounds=dict(max_source_objects=100,max_targets=100,max_evaluations=10000,max_output_bytes=10**7,max_seconds=60)
 details=adapter.plan(store,scene,policy,dict(stage='t02',scene_ref=ref,source_ids=['a','b']),bounds);plan=dict(stage='t02',scene_ref=ref,policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details)
 result=adapter.run(store,scene,policy,plan,lambda _:None);after=store.get_json(result['output_scene_ref'],kind='scene')
 gaps.restore(store,after);assert gaps.ACTIVE['zones']==result['shared_neighbor_gaps']['zones']
 # Recompute nothing from the later enlarged rectangles: the accepted gap is immutable.
 modified=copy.deepcopy(after)
 for row in modified['objects']:
  if row['source_id']in('a','b'):
   from src.stage_abi.scene import geometry
   widened=scale(geometry(store,row['geometry_ref']),1.01,1.,origin=original[row['source_id']].centroid)
   row['geometry_ref']=store.put('geometry',to_wkb(widened))
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.restore(store,modified)
 modified=copy.deepcopy(after);modified['lineage'][-1].pop('shared_gap_state_ref')
 with pytest.raises(ValueError,match='FROZEN_STATE_MISSING'):gaps.restore(store,modified)

def test_source_discovery_is_deterministic_and_ignores_unequal_original_gaps(tmp_path):
 original,scene,store=fixture(tmp_path);spec=gaps.records(scene,original,original)
 assert spec==gaps.records(dict(scene,objects=list(reversed(scene['objects']))),dict(reversed(list(original.items()))),original)
 original['b']=box(-.1,2,.9,3)
 assert not gaps.records(scene,original,original)['groups']

def test_small_integral_attachment_is_excluded_without_losing_shared_face(tmp_path):
 original,scene,store=fixture(tmp_path);original['joint']=box(.9,2,1.05,2.01)
 scene['objects'].append(dict(source_id='joint',kind='trace',metadata={}))
 spec=gaps.records(scene,original,original)
 assert len(spec['groups'])==1 and set(spec['groups'][0]['banks'][0])=={'a','b'}
 assert spec['groups'][0]['slots'][1]['lo']==pytest.approx(2.01)

def test_other_rectangle_approaching_slot_end_is_limited_without_clipping_or_copper_loss(tmp_path):
 original,scene,store=fixture(tmp_path);original['approach']=box(1.1,1.05,1.9,1.95)
 scene['objects'].append(dict(source_id='approach',kind='rectangle',metadata={}))
 spec=gaps.records(scene,original,original);proposed={s:scale(original[s],1.2,1.25,origin=original[s].centroid)for s in('a','b','approach')}
 result,proof=gaps.project(spec,original,original,proposed)
 assert proof['approaching_proposal_limits']
 assert result['approach'].covers(original['approach'])and result['approach'].equals(box(*result['approach'].bounds))
 assert result['approach'].bounds[1]>=1.-1e-12 and result['approach'].bounds[3]<=2.+1e-12
 assert gaps.complete(proof,unary_union([*result.values(),original['wall']]))['passed']

def test_off_origin_exact_straight_boundaries_use_intervals_not_tiny_buffers(tmp_path):
 original,scene,store=fixture(tmp_path)
 from shapely.affinity import translate
 original={s:translate(g,5.5991,-15.388565248402)for s,g in original.items()}
 spec=gaps.records(scene,original,original);_,proof=gaps.project(spec,original,original,dict(a=original['a'],b=original['b']))
 assert gaps.complete(proof,unary_union(list(original.values())))['passed']

def test_real_source_binary_bounds_cannot_round_past_original_factor_cap(tmp_path):
 original,scene,store=fixture(tmp_path)
 from shapely.affinity import translate
 original={s:scale(translate(g,5.8991,-15.3941),.65,.65,origin=(5.8991,-15.3941))for s,g in original.items()}
 spec=gaps.records(scene,original,original);proposed={s:scale(original[s],1.25,1.25,origin=original[s].centroid)for s in('a','b')}
 result,proof=gaps.project(spec,original,original,proposed,factor_rows={s:[1.25,1.25]for s in proposed})
 for sid,g in result.items():
  assert all(1<=f<=1.25 for f in proof['factors'][sid])and proposed[sid].covers(g)
