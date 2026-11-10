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

def test_fixed_t04_copper_holds_two_pad_gap_without_removing_width(tmp_path):
 original,scene,_=fixture(tmp_path)
 original.pop('wall');scene['objects'].pop()
 extra=dict(c=box(2,0,3,1),d=box(2,2,3,3),spine=box(2.9,0,3.1,3),
            trace=box(.9,-.2,1,0),unrelated=box(8,8,9,9))
 original.update(extra)
 scene['objects'].extend(dict(source_id=s,kind='fixed'if s in ('spine','trace')else'rectangle',metadata={})for s in extra)
 trace=box(.875,-.2,1.025,.025)
 current=dict(original,trace=trace)
 spec=gaps.records(scene,original,current)
 assert spec['fixed_entry_holds'] and len(spec['occupied_entry_slots'])==1
 proposed={s:scale(current[s],1.1,1.1,origin=current[s].centroid)for s in ('a','b','c','d','unrelated')}
 selected,proof=gaps.project(spec,original,current,proposed)
 assert all(selected[s].bounds[0::2]==original[s].bounds[0::2]for s in ('a','b','c','d'))
 assert all(selected[s].area>original[s].area for s in ('a','b','c','d'))
 assert selected['unrelated'].equals(proposed['unrelated'])
 assert proof['fixed_entry_holds']==spec['fixed_entry_holds']
 after=dict(current,**selected);material=unary_union(list(after.values()))
 assert gaps.complete(proof,material)['passed']
 from src.shared_gap_projection import complete_parts
 assert complete_parts(proof,after.values())['passed']
 with pytest.raises(ValueError,match='FIXED_STAGE_ENTRY_COPPER_REMOVED'):
  gaps.complete(proof,unary_union(list(dict(after,trace=original['trace']).values())))
 assert not gaps.check(proof,box(1.02,.03,1.03,.04))['passed']

def test_fixed_wall_slot_also_keeps_unaccounted_entry_trace(tmp_path):
 original,scene,_=fixture(tmp_path)
 original['trace']=box(.9,-.2,1,0)
 scene['objects'].append(dict(source_id='trace',kind='trace',metadata={}))
 current=dict(original,trace=box(.875,-.2,1.025,.025))
 spec=gaps.records(scene,original,current)
 assert spec['fixed_entry_holds'] and len(spec['occupied_entry_slots'])==1
 result,proof=gaps.project(spec,original,current,{'a':scale(original['a'],1.1,1.1)})
 assert proof['factors']['a']==pytest.approx([1.,1.1])
 assert gaps.complete(proof,unary_union(list(dict(current,**result).values())))['passed']

def test_t02_discovers_only_the_open_span_in_accepted_t04(tmp_path):
 original,scene,_=fixture(tmp_path)
 original['trace']=box(.8,.01,1.,.02)
 scene['objects'].append(dict(source_id='trace',kind='trace',metadata={}))
 current=dict(original,trace=box(.8,.01,1.03,.08))
 scene['lineage']=[dict(stage='t04')]
 spec=gaps.records(scene,original,current)
 assert spec['discovery_geometry']=='SOURCE_GROUPS_WITH_ACCEPTED_T04_OPENINGS'
 assert 'fixed_entry_holds' not in spec
 group,=spec['groups']
 source_group,=spec['source_groups']
 assert (group['group_id'],group['banks'])==(source_group['group_id'],source_group['banks'])
 assert any(slot['lo']==pytest.approx(.08)for slot in group['slots'])
 assert group['slots']!=source_group['slots']
 proposed={s:scale(current[s],1.1,1.1,origin=current[s].centroid)for s in ('a','b')}
 result,proof=gaps.project(spec,original,current,proposed)
 after=unary_union(list(dict(current,**result).values()))
 assert gaps.complete(proof,after)['passed']
 assert unary_union(list(current.values())).difference(after).is_empty

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

@pytest.mark.parametrize('rotation',[False,True])
def test_qualified_t04_fixed_wall_shift_is_preserved_over_every_full_span(tmp_path,rotation):
 original,scene,store=fixture(tmp_path,rotation=rotation);axis=1 if rotation else 0
 factors=[1.,1.];factors[axis]=1.06
 current=dict(original,wall=scale(original['wall'],*factors,origin=original['wall'].centroid))
 spec=gaps.records(scene,original,current)
 assert len(spec['groups'])==1 and len(spec['entry_walls'])==2
 assert all(w['offset_mm']==pytest.approx(.03)for w in spec['entry_walls'])
 proposed={s:scale(original[s],1.1,1.1,origin=original[s].centroid)for s in('a','b')}
 result,proof=gaps.project(spec,original,current,proposed)
 whole=unary_union(list(dict(current,**result).values()))
 check=gaps.complete(proof,whole)
 assert len(check['checks'])==2 and len(check['boundaries'])==4
 assert all(v['gap_mm']==pytest.approx(.92)for v in proof['zones'])
 assert all(v['gap_mm']==pytest.approx(.92)for v in gaps.frozen(spec,dict(current,**result))['zones'])
 assert current['wall'].difference(whole).is_empty

def test_integral_prior_trace_corner_is_absorbed_by_ordinary_checked_rectangle(tmp_path):
 original,scene,store=fixture(tmp_path);original['joint']=box(.8,.01,1.,.02)
 scene['objects'].append(dict(source_id='joint',kind='stroke',metadata={}))
 current=dict(original,joint=box(.8,.01,1.03,.08));spec=gaps.records(scene,original,current)
 proposed={s:scale(original[s],1.1,1.1,origin=original[s].centroid)for s in('a','b')}
 result,proof=gaps.project(spec,original,current,proposed);after=unary_union(list(dict(current,**result).values()))
 assert gaps.complete(proof,after)['passed']
 assert unary_union(list(current.values())).difference(after).is_empty

def test_prior_local_bridge_is_not_authority_to_redefine_the_gap(tmp_path):
 original,scene,store=fixture(tmp_path);original['joint']=box(.8,.01,1.,.02)
 scene['objects'].append(dict(source_id='joint',kind='stroke',metadata={}))
 current=dict(original,joint=box(.8,.01,2.1,.08));spec=gaps.records(scene,original,current)
 proposed={s:scale(original[s],1.25,1.25,origin=original[s].centroid)for s in('a','b')}
 result,proof=gaps.project(spec,original,current,proposed)
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.complete(proof,unary_union(list(dict(current,**result).values())))

def test_fixed_wall_support_is_source_bound_and_cannot_disappear_or_lose_core(tmp_path):
 original,scene,store=fixture(tmp_path);spec=gaps.records(scene,original,original)
 assert all([v['source_id']for v in w['supports']]==['wall']for w in spec['entry_walls'])
 with pytest.raises(ValueError,match='SUPPORT_MISSING'):gaps.records(scene,original,{k:v for k,v in original.items()if k!='wall'})
 with pytest.raises(ValueError,match='SUPPORT_CORE_CHANGED'):gaps.records(scene,original,dict(original,wall=box(2,-1,3,2.9)))

def test_mixed_bank_is_anchored_at_qualified_wall_offset_and_never_exceeds_proposal(tmp_path):
 original,scene,store=fixture(tmp_path)
 original['wall']=box(2.5,-1,3,4).union(box(2,2,3,3));original['c']=box(2,0,3,1)
 scene['objects'].append(dict(source_id='c',kind='rectangle',metadata={}))
 current=dict(original,wall=original['wall'].union(box(1.95,2,2.5,3)))
 spec=gaps.records(scene,original,current);assert len(spec['groups'])==1
 proposed={s:scale(original[s],1.2,1.2,origin=original[s].centroid)for s in('a','b','c')}
 result,proof=gaps.project(spec,original,current,proposed)
 assert result['c'].bounds[0]==pytest.approx(1.95)
 assert gaps.complete(proof,unary_union(list(dict(current,**result).values())))['passed']
 proposed['c']=scale(original['c'],1.04,1.2,origin=original['c'].centroid)
 with pytest.raises(ValueError,match='ANCHOR_INFEASIBLE'):gaps.project(spec,original,current,proposed)

def test_inherited_subgrid_endpoint_is_preserved_exactly_and_native_fidelity_is_unchanged(tmp_path):
 from shapely import set_precision
 original,scene,store=fixture(tmp_path)
 wall=box(1.97,-1,3.03,4).union(box(1.97-1.65e-10,0.,2.,3.2e-8));current=dict(original,wall=wall)
 spec=gaps.records(scene,original,current);proposed={s:scale(original[s],1.1,1.1,origin=original[s].centroid)for s in('a','b')}
 result,proof=gaps.project(spec,original,current,proposed);whole=unary_union(list(dict(current,**result).values()))
 assert gaps.complete(proof,whole)['passed']
 assert gaps.complete(proof,set_precision(whole,1e-6),tolerance_mm=2e-6)['passed']
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.complete(proof,whole.union(box(1.969,.2,2.,.8)),tolerance_mm=2e-6)

def test_canonical_source_plane_rounding_keeps_original_support_identity(tmp_path):
 from shapely.affinity import translate
 original,scene,store=fixture(tmp_path)
 original={s:translate(g,5.599100000000002,-15.388565248402)for s,g in original.items()}
 current=dict(original,wall=scale(original['wall'],1.06,1.,origin=original['wall'].centroid))
 spec=gaps.records(scene,original,current)
 assert len(spec['groups'])==1 and len(spec['entry_walls'])==2
 assert all([q['source_id']for q in w['supports']]==['wall']for w in spec['entry_walls'])
 proposed={s:scale(original[s],1.1,1.1,origin=original[s].centroid)for s in('a','b')}
 result,proof=gaps.project(spec,original,current,proposed)
 assert gaps.complete(proof,unary_union(list(dict(current,**result).values())))['passed']

def test_original_joint_subgrid_lip_is_frozen_exactly_without_allowing_new_lips(tmp_path):
 from shapely.geometry import Polygon
 from shapely import set_precision
 original,scene,store=fixture(tmp_path);original['joint']=box(2.1,0,2.2,.1)
 scene['objects'].append(dict(source_id='joint',kind='stroke',metadata={}))
 lip=Polygon([(1.97,0),(1.97-1.65189291e-7,0),(1.97,3.213139e-5)])
 assert lip.area>gaps.EPS
 current=dict(original,wall=box(1.97,-1,3.03,4),joint=box(1.97,0,2.2,.1).union(lip))
 spec=gaps.records(scene,original,current)
 assert any('joint'in[w['source_id']for w in wall['original_attachments']]for wall in spec['entry_walls'])
 proposed={s:scale(original[s],1.1,1.1,origin=original[s].centroid)for s in('a','b')}
 result,proof=gaps.project(spec,original,current,proposed);whole=unary_union(list(dict(current,**result).values()))
 checked=gaps.complete(proof,whole)
 assert checked['passed']and any(r['retained_entry_material_mm2']>gaps.EPS for r in checked['checks'])
 assert gaps.complete(proof,set_precision(whole,1e-6),tolerance_mm=2e-6)['passed']
 # A new 0.1 nm lip is not part of the exact inherited footprint, even though
 # it is smaller than the wall-recognition/native fidelity tolerance.
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.complete(proof,whole.union(box(1.97-1e-7,.3,2.,.4)))

def test_fixed_wall_full_middle_boundary_cannot_disappear_between_endpoints(tmp_path):
 original,scene,store=fixture(tmp_path);current=dict(original,wall=box(1.97,-1,3.03,4));spec=gaps.records(scene,original,current)
 proposed={s:scale(original[s],1.1,1.1,origin=original[s].centroid)for s in('a','b')};result,proof=gaps.project(spec,original,current,proposed);whole=unary_union(list(dict(current,**result).values()))
 # Remove only preceding growth, not the original wall, to widen a local gap.
 bad=whole.difference(box(1.96,.2,1.971,.8))
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.complete(proof,bad)
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.complete(proof,bad,tolerance_mm=2e-6)

def test_native_inherited_attachment_rounding_uses_existing_fidelity_only(tmp_path):
 from shapely import set_precision
 from src.gerber_u05.exporter import native_shared_gap_complete
 from shapely.geometry import LineString
 lip=box(1.,.2,1.1000006,.4)
 wall=dict(bank=0,retained_material_wkb_hex=to_wkb(lip).hex(),contour_wkb_hex=to_wkb(LineString([(1.,0.),(1.,.2),(1.1000006,.2),(1.1000006,.4),(1.,.4),(1.,1.)])).hex(),supports=['original_joint'])
 proof=dict(policy=gaps.policy(),zones=[dict(axis=0,left=1.,right=2.,lo=0.,hi=1.,gap_mm=.8999994,group_id='fixture',entry_walls=[wall])])
 whole=unary_union([box(0,0,1,1),box(2,0,3,1),lip]);frozen=copy.deepcopy(proof)
 assert gaps.complete(proof,whole)['passed']
 from shapely import from_wkb
 native=from_wkb(to_wkb(set_precision(whole,1e-6)))
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.complete(proof,native,tolerance_mm=2e-6)
 assert native_shared_gap_complete(proof,native)['passed']
 assert proof==frozen
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.complete(proof,native)
 with pytest.raises(ValueError,match='UNIFORMITY'):native_shared_gap_complete(proof,native.union(box(1.,.25,1.10001,.35)))

def test_ordinary_t05_smoothing_preserves_the_frozen_gap_and_unrelated_treatment(tmp_path,monkeypatch):
 from src.u05_board.coverage import CoverageAdapter
 original,scene,store=fixture(tmp_path);spec=gaps.records(scene,original,original);_,proof=gaps.project(spec,original,original,{s:original[s]for s in('a','b')})
 monkeypatch.setattr(gaps,'ACTIVE',proof);adapter=CoverageAdapter(box(-2,-2,4,5));owner=original['a'];window=box(-1,-1,2,2)
 bad=box(.9,.2,1.001,.8);q=adapter._check(owner,owner.union(bad),bad,window,[])
 assert not q['passed']and 'FROZEN_SHARED_NEIGHBOR_GAP'in q['failures']
 good=box(-.01,.2,.2,.8);assert adapter._check(owner,owner.union(good),good,window,[])['passed']

def test_fresh_reference_worker_restores_shared_gaps_from_t02_lineage(tmp_path):
 from src.gerber_u05.reference_recipe import initialize_reference_constraints
 from src.stage_abi.store import digest,canonical
 original,scene,store=fixture(tmp_path);source=unary_union(list(original.values()));width=t04_width_fence.Rule(box(10,10,11,11),source,'frozen-width-fixture')
 scene['lineage']=[dict(stage='t04',t04_width_fence=width.state(store))]
 adapter=FastRectangleAdapter('t02');ref=store.put_json('scene',scene);policy=dict(stage='t02',parameters=land_parameters('t02'));bounds=dict(max_source_objects=100,max_targets=100,max_evaluations=10000,max_output_bytes=10**7,max_seconds=60)
 details=adapter.plan(store,scene,policy,dict(stage='t02',scene_ref=ref,source_ids=['a','b']),bounds);plan=dict(stage='t02',scene_ref=ref,policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details);result=adapter.run(store,scene,policy,plan,lambda _:None);after=store.get_json(result['output_scene_ref'],kind='scene')
 assert gaps.ACTIVE is None
 binding=dict(source_ref=dict(artifact_id='gerber-source:'+'a'*64,sha256='a'*64));receipt=initialize_reference_constraints(store,binding,source,scene,after)
 assert receipt['frozen_shared_gap_state_sha256']==digest(canonical(result['shared_neighbor_gaps']))
 from src.growth_remedy_constraints import remedy
 zone=result['shared_neighbor_gaps']['zones'][0];bad=box(zone['left']-.01,.2,zone['left']+.001,.8)
 assert not remedy(bad,source)['passed']

def test_retained_prior_cannot_bridge_or_narrow_an_accepted_shared_gap(tmp_path,monkeypatch):
 from src.gerber_u05.prior_copper import require_shared_prior
 original,scene,store=fixture(tmp_path);spec=gaps.records(scene,original,original);_,proof=gaps.project(spec,original,original,{s:original[s]for s in('a','b')});monkeypatch.setattr(gaps,'ACTIVE',proof)
 assert require_shared_prior(original)['passed']
 for patch in (box(.9,.2,1.001,.8),box(.9,.2,2.1,.8)):
  with pytest.raises(ValueError,match='UNIFORMITY'):require_shared_prior(dict(original,a=original['a'].union(patch)))


def test_native_straight_wall_endpoint_rounding_keeps_interior_coverage():
    from src.gerber_u05.exporter import native_shared_gap_complete

    proof = dict(policy=gaps.policy(), zones=[
        dict(axis=0, left=1., right=2., lo=0.0000004, hi=1.0000004,
             gap_mm=1., group_id='native-endpoint', entry_walls=[]),
    ])
    material = unary_union([box(0., 0.000001, 1., 1.), box(2., 0., 3., 1.1)])
    assert native_shared_gap_complete(proof, material)['passed']
    with pytest.raises(ValueError, match='UNIFORMITY'):
        gaps.complete(proof, material)
    with pytest.raises(ValueError, match='UNIFORMITY'):
        native_shared_gap_complete(proof, material.difference(box(.9, .5, 1.1, .500001)))
    with pytest.raises(ValueError, match='UNIFORMITY'):
        native_shared_gap_complete(proof, material.difference(box(.9, 0., 1.1, .000004)))
