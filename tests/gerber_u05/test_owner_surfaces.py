import gc
import pytest
from shapely import to_wkb
from shapely.geometry import box,Point
from src import component_clearance as cc
from src.stage_abi.store import ArtifactStore
from src.u05_board.owner_surfaces import OwnerSurfaces

def case(tmp_path,limit):
 a=box(0,0,1,1);b=box(3,0,4,1);c=Point(7,0).buffer(.5,quad_segs=128)
 ctx=cc.Context(a.union(b).union(c),'a'*64,{'a':a,'b':b,'c':c});material={'a':a.buffer(.1),'b':b,'c':c};store=ArtifactStore(tmp_path/'runtime');return ctx,material,store,OwnerSurfaces(ctx,material,store,limit=limit)

@pytest.mark.parametrize('limit',[0,1000,20000])
def test_spilled_owner_surfaces_match_complete_original_projection(tmp_path,limit):
 ctx,material,store,view=case(tmp_path,limit);expected=ctx.project(material)
 assert list(view)==list(expected)
 for _ in range(3):
  for own,g in expected.items():assert to_wkb(view[own])==to_wkb(g)
  assert view.weight<=limit
 view.validate_bindings();assert view.diagnostics()['peak_estimated_bytes']<=limit
 view.close();assert view.weight==0 and not view.cache and not view.live

def test_zero_cache_still_shares_shapes_kept_alive_by_the_current_execution(tmp_path):
 ctx,material,store,view=case(tmp_path,0);own=ctx.owner('a');one=view[own]
 assert view[own]is one and not view.cache
 del one;gc.collect();assert not view.live
 assert to_wkb(view[own])==to_wkb(ctx.project(material)[own])

def test_owner_queries_are_conservative_and_keep_original_order(tmp_path):
 ctx,material,store,view=case(tmp_path,1000)
 for window in [box(-1,-1,2,2),box(-10,-10,10,10),box(9,9,10,10)]:
  full=[o for o,g in ctx.project(material).items()if g.intersects(window)]
  reduced=[o for o in view.query(window)if view[o].intersects(window)]
  assert full==reduced

def test_owner_artifact_corruption_is_checked_even_for_a_live_shape(tmp_path):
 ctx,material,store,view=case(tmp_path,20000);own=ctx.owner('a');shape=view[own];ref=view.refs[own]
 (store.root/'artifacts'/ref['artifact_id']).write_bytes(b'corrupt')
 with pytest.raises(ValueError)as exc:view[own]
 assert exc.value.code=='ARTIFACT_CORRUPTED'

def test_corrupted_cached_owner_is_rejected(tmp_path):
 ctx,material,store,view=case(tmp_path,20000);own=ctx.owner('a');wrong=box(9,9,10,10);view.live[own]=wrong
 with pytest.raises(ValueError,match='OWNER_SURFACE_CACHE_CORRUPTED'):view[own]
 with pytest.raises(ValueError,match='OWNER_SURFACE_CACHE_CORRUPTED'):view.validate_bindings()

def test_multi_owner_occurrence_guard_is_retained(tmp_path):
 ctx,material,store,view=case(tmp_path,0);both=ctx.originals['a'].union(ctx.originals['b']);ctx.originals['multi']=both;ctx.ids['multi']=ctx.index.membership(both)
 material['multi']=both.buffer(.001)
 with pytest.raises(ValueError,match='MULTI_OWNER_OCCURRENCE_CHANGED'):OwnerSurfaces(ctx,material,store,limit=1000)

def test_canonical_leaf_assembly_is_checked_for_legacy_and_connected_modes(tmp_path):
 from src.u05_board.coverage import verify_assembled_output
 from src.stage_abi.loaded_geometry import GeometrySnapshot
 store=ArtifactStore(tmp_path/'runtime');rows=[]
 for i,g in enumerate([box(0,0,1,1),box(.5,.5,2,2),box(-1,-1,.5,.5)]):
  ref=store.put('geometry',to_wkb(g));rows.append(dict(source_id=str(i),geometry_ref=ref,original_ref=ref))
 scene=dict(objects=rows,viewport_mm=[-3,-3,3,3]);snapshot=GeometrySnapshot(store,scene);after=snapshot.composed(store,scene);ref=store.put('geometry',to_wkb(after))
 assert to_wkb(verify_assembled_output(snapshot,store,scene,rows,scene,ref))==to_wkb(after)
 bad=store.put('geometry',to_wkb(box(20,20,21,21)))
 with pytest.raises(ValueError,match='U05_ATTACHMENT_AFTER_CHANGED'):verify_assembled_output(snapshot,store,scene,rows,scene,bad)
 with pytest.raises(ValueError,match='U05_ATTACHMENT_ASSEMBLY_CHANGED'):verify_assembled_output(snapshot,store,scene,rows,dict(scene,objects=rows[:-1]),ref)
