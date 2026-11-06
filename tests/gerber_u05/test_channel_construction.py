import pytest
from shapely import to_wkb,from_wkb
from shapely.geometry import box
from src import component_clearance as cc,source_channel_scope as functional
from src.source_common_frame import discover
from src.source_channel_guard import SourceChannels
from src.prepared_width_scene import PreparedWidthScene
from tests.gerber_u05.test_source_channels import frame_scene

def fixture(tmp_path,monkeypatch):
 store,scene,source=frame_scene(tmp_path);frame,cert=discover(source,'a'*64,scene,store);channels=SourceChannels(source,'a'*64,frame,cert,store=store);originals={r['source_id']:from_wkb(store.get(r['original_ref'],kind='geometry'))for r in scene['objects']};scope=functional.Scope(channels,cert,originals);physical=cc.Context(source,'a'*64,originals);physical.functional=scope;monkeypatch.setattr(cc,'ACTIVE',physical);monkeypatch.setattr(functional,'ACTIVE',scope);return store,scene,source,scope,originals

def width_fixture(tmp_path,monkeypatch):
 store,scene,source,scope,originals=fixture(tmp_path,monkeypatch);traces=[dict(id=s,original=g,candidate=g,verified_original_width_mm=.08)for s,g in originals.items()if s.startswith('trace:')];fixed=[dict(id=s,geometry=g,trace_width_mm=.1)for s,g in originals.items()if s.startswith('frame:')];parent=PreparedWidthScene(traces,fixed);return parent,traces,scope,originals

def test_counterfactual_rejects_merge_that_the_common_physical_owner_allows(tmp_path,monkeypatch):
 parent,traces,scope,originals=width_fixture(tmp_path,monkeypatch);bad=[dict(r)for r in traces];bad[0]['candidate']=bad[0]['original'].union(box(2,6,8.1,6.1))
 physical=parent._physical_check(bad,materialize_scene=True)
 assert physical['passed']
 actual=parent.check(bad,materialize_scene=True)
 assert not actual['passed']and not actual['functional_channels']['passed']
 assert any(r.get('clearance_scope')=='FUNCTIONAL_SOURCE_CHANNEL'for r in actual['failures'])

def test_all_selected_route_checks_keep_source_identities_and_cache_bounds(tmp_path,monkeypatch):
 parent,traces,scope,originals=width_fixture(tmp_path,monkeypatch)
 for flag in(False,True):
  result=parent.check(traces,materialize_scene=flag)
  assert result['passed']and result['functional_channels']['checked_trace_count']==len(traces)
  assert result['functional_channels']['evaluation_complete']
  assert parent._functional_check.weight<=parent._functional_check.limit

def test_local_growth_uses_the_same_frozen_channel_and_keeps_the_frame(tmp_path,monkeypatch):
 parent,traces,scope,originals=width_fixture(tmp_path,monkeypatch);candidate=[dict(r)for r in traces];candidate[0]['candidate']=candidate[0]['original'].union(box(1.9,4,2.2,4.2));before={s:to_wkb(g)for s,g in originals.items()if s in scope.frame_ids}
 assert parent.check(candidate,materialize_scene=True)['passed']
 assert before=={s:to_wkb(originals[s])for s in scope.frame_ids}

def test_frame_geometry_cannot_grow_under_the_functional_context(tmp_path,monkeypatch):
 store,scene,source,scope,originals=fixture(tmp_path,monkeypatch);changed=dict(originals);sid=next(iter(scope.frame_ids));changed[sid]=changed[sid].buffer(.01)
 with pytest.raises(ValueError,match='TEMPORARY_FRAME_GROWTH_NOT_ALLOWED'):scope.project(changed)

def test_changed_functional_context_cannot_reuse_counterfactual_verdicts(tmp_path,monkeypatch):
 parent,traces,scope,originals=width_fixture(tmp_path,monkeypatch);assert parent.check(traces)['passed'];scope.binding='different'
 with pytest.raises(ValueError,match='ORIGINAL_OWNER_CONTEXT_CHANGED'):parent.check(traces)

def test_route_assignment_uses_frozen_source_members_and_not_new_contact(tmp_path,monkeypatch):
 store,scene,source,scope,originals=fixture(tmp_path,monkeypatch);ref=store.put('geometry',to_wkb(originals['trace:0'].union(originals['trace:1'])));row=dict(source_id='route:forged',kind='trace',original_ref=ref,geometry_ref=ref,metadata=dict(reference_source_ids=['trace:0','trace:1']))
 with pytest.raises(ValueError,match='CROSSES_FUNCTIONAL_CHANNELS'):scope.register_scene(store,dict(objects=[row]))

def test_t01_priority_groups_ignore_only_the_source_frame_tie(tmp_path,monkeypatch):
 from shapely.geometry import Point
 from src.gerber_u05.pipeline import t01_sites
 store,scene,source=frame_scene(tmp_path)
 for label,x in [('left',2),('right',8)]:
  g=Point(x,7).buffer(.2,quad_segs=64);source=source.union(g);sid='pad:'+label;ref=store.put('geometry',to_wkb(g));scene['objects'].append(dict(source_id=sid,kind='circle',original_ref=ref,geometry_ref=ref,metadata=dict(alias_source_ids=[sid])))
 frame,cert=discover(source,'a'*64,scene,store);channels=SourceChannels(source,'a'*64,frame,cert,store=store);objects={r['source_id']:from_wkb(store.get(r['original_ref'],kind='geometry'))for r in scene['objects']};scope=functional.Scope(channels,cert,objects);monkeypatch.setattr(functional,'ACTIVE',scope)
 sites=t01_sites(store,scene)
 assert len(sites)==2 and len({r['physical_contact_group']for r in sites})==2
 assert all(r['physical_contact_group'].startswith('FUNCTIONAL-SOURCE-')for r in sites)

def rectangle_merge_fixture(tmp_path,monkeypatch,connected):
 from shapely.geometry import LineString
 from src.gerber_u05.component_rectangles import ComponentRectangleAdapter
 from src.stage_abi.runtime import Budget
 store,scene,source=frame_scene(tmp_path)
 def add(sid,kind,g):
  nonlocal source
  ref=store.put('geometry',to_wkb(g));scene['objects'].append(dict(source_id=sid,kind=kind,original_ref=ref,geometry_ref=ref,metadata=dict(original_width_mm=0.)));source=source.union(g)
 add('rect:left','rectangle',box(2,4,5.9,5));add('rect:right','rectangle',box(6,4,8.1,5))
 if connected:
  add('local-joint','fixed_source',LineString([(5.8,4.5),(6.1,4.5)]).buffer(.04,quad_segs=64))
  add('third-channel','fixed_source',LineString([(9,0),(9,8)]).buffer(.04,quad_segs=64))
 frame,cert=discover(source,'a'*64,scene,store);channels=SourceChannels(source,'a'*64,frame,cert,store=store);objects={r['source_id']:from_wkb(store.get(r['original_ref'],kind='geometry'))for r in scene['objects']};scope=functional.Scope(channels,cert,objects);physical=cc.Context(source,'a'*64,objects);monkeypatch.setattr(cc,'ACTIVE',physical);monkeypatch.setattr(functional,'ACTIVE',scope);scene['viewport_mm']=[-1,-1,11,11]
 adapter=ComponentRectangleAdapter('t02');rows={r['source_id']:r for r in scene['objects']};plan=dict(details=dict(targets=['rect:left','rect:right'],containment={s:dict(contained=False)for s in('rect:left','rect:right')}));budget=Budget(dict(max_source_objects=100,max_targets=10,max_evaluations=100,max_output_bytes=1000000,max_seconds=60));return adapter,store,scene,plan,rows,objects,budget,scope

def test_t02_inclusive_merge_cannot_use_the_remote_frame_as_local_connectivity(tmp_path,monkeypatch):
 args=rectangle_merge_fixture(tmp_path,monkeypatch,False);adapter,store,scene,plan,rows,current,budget,scope=args;records,additions=adapter._merges(store,scene,plan,rows,current,budget)
 assert records and not additions
 assert any('MIXED_FUNCTIONAL_SOURCE_CHANNELS'in r['reasons']for r in records)

def test_t02_local_integral_copper_fill_is_not_blocked_by_the_outer_frame_hole(tmp_path,monkeypatch):
 args=rectangle_merge_fixture(tmp_path,monkeypatch,True);adapter,store,scene,plan,rows,current,budget,scope=args;records,additions=adapter._merges(store,scene,plan,rows,current,budget)
 assert records and additions and any(r['status']=='MERGED'for r in records)
 assert additions[0]['metadata']['original_channel_id']==scope.owner('rect:left')==scope.owner('rect:right')
 assert any(r.get('functional_shortage',1)<=.2 for r in records if r['status']=='MERGED')
 scope.register_scene(store,dict(objects=additions))
