"""Deferred operands preserve complete geometry while decoded retention stays bounded."""
import gc
import weakref
import pytest
from shapely import to_wkb
from shapely.geometry import box, Point
from src.stage_abi.store import ArtifactStore
from src.stage_abi.scene import composed
from src.stage_abi.loaded_geometry import GeometrySnapshot


def fixture(tmp_path):
 store=ArtifactStore(tmp_path/'runtime');rows=[]
 for i in range(10):
  shape=box(i,0,i+1,1)if i<2 else Point(i,2).buffer(.2,quad_segs=32)
  ref=store.put('geometry',to_wkb(shape))
  rows.append(dict(source_id=str(i),kind='fixed'if i<2 else'trace',geometry_ref=ref,original_ref=ref))
 return store,dict(objects=rows,viewport_mm=[-1,-1,12,4])


def test_full_eager_snapshot_fails_but_bounded_operands_keep_all_originals_and_composition(tmp_path):
 store,scene=fixture(tmp_path)
 with pytest.raises(ValueError,match='SNAPSHOT_BUDGET'):GeometrySnapshot(store,scene,limit=18000)
 snapshot=GeometrySnapshot(store,scene,limit=18000,bounded_operands=True)
 assert list(snapshot.current)==list(snapshot.original)==[r['source_id']for r in scene['objects']]
 assert snapshot.stats['artifact_accesses']==2*len(scene['objects'])
 for row in scene['objects']:
  for name,view in [('geometry_ref',snapshot.current),('original_ref',snapshot.original)]:
   assert to_wkb(view[row['source_id']])==store.get(row[name],kind='geometry')
   assert snapshot.weight<=18000
 assert to_wkb(snapshot.composed(store,scene))==to_wkb(composed(store,scene))
 snapshot.validate_bindings()
 assert snapshot.stats['optional_evictions']>0 and snapshot.peak<=18000


def test_derived_union_and_owner_cache_share_the_same_unchanged_budget(tmp_path):
 store,scene=fixture(tmp_path);snapshot=GeometrySnapshot(store,scene,limit=18000,bounded_operands=True)
 snapshot.retain_derived(Point(-2,0).buffer(.5,quad_segs=32))
 snapshot.reserve_external(4000)
 for row in reversed(scene['objects']):
  snapshot.current[row['source_id']]
  assert snapshot.weight+snapshot.external_reserved<=snapshot.limit==18000
 assert snapshot.optional_capacity()>=snapshot.optional_weight
 with pytest.raises(ValueError,match='SNAPSHOT_BUDGET'):snapshot.reserve_external(18000)


def test_optional_operand_larger_than_cache_is_checked_and_not_retained(tmp_path):
 store,scene=fixture(tmp_path);snapshot=GeometrySnapshot(store,scene,limit=6000,bounded_operands=True)
 assert snapshot.stats['optional_not_retained']>0
 assert to_wkb(snapshot.original['9'])==store.get(scene['objects'][-1]['original_ref'],kind='geometry')
 snapshot.validate_bindings();assert snapshot.weight<=6000


@pytest.mark.parametrize('mutation',['bytes','reference','decoded'])
def test_lazy_reads_and_binding_checks_reject_corruption(tmp_path,mutation):
 store,scene=fixture(tmp_path);snapshot=GeometrySnapshot(store,scene,limit=18000,bounded_operands=True);row=scene['objects'][-1];ref=row['geometry_ref'];snapshot.current['9']
 if mutation=='bytes':
  (store.root/'artifacts'/ref['artifact_id']).write_bytes(b'corrupt')
  with pytest.raises(ValueError)as error:snapshot.current['9']
  assert error.value.code=='ARTIFACT_CORRUPTED'
 elif mutation=='reference':
  row['geometry_ref']=scene['objects'][0]['geometry_ref']
  with pytest.raises(ValueError,match='SNAPSHOT_BINDING_CHANGED'):snapshot.validate_bindings()
 else:
  _,checksum,size=snapshot.optional[ref['sha256']];snapshot.optional[ref['sha256']]=(box(50,50,51,51),checksum,size)
  with pytest.raises(ValueError,match='SNAPSHOT_CORRUPTED'):snapshot.current['9']


def test_close_releases_pinned_views_and_prevents_a_detached_view_from_reloading(tmp_path):
 store,scene=fixture(tmp_path);snapshot=GeometrySnapshot(store,scene,limit=18000,bounded_operands=True);view=snapshot.current;ref=weakref.ref(view['0']);snapshot.close();gc.collect()
 assert ref()is None and not snapshot.shapes and not snapshot.optional and snapshot.weight==0
 with pytest.raises(ValueError,match='SNAPSHOT_CLOSED'):view['0']


def test_all_operand_streaming_and_envelope_index_keep_exact_source_candidates(tmp_path):
 from src.stage_abi.spatial_queries import SpatialQueries
 store,scene=fixture(tmp_path);snapshot=GeometrySnapshot(store,scene,limit=6000,bounded_operands=True,pin_current=False)
 material={s:snapshot.current[s]for s in snapshot.current};versions={r['source_id']:r['geometry_ref']['sha256']for r in scene['objects']}
 full=SpatialQueries(material,context='test',versions=versions)
 index=SpatialQueries(material,context='test',versions=versions,envelopes_only=True)
 for query in [box(-1,-1,3,4),box(3.9,1.9,4.1,2.1),box(-9,-9,-8,-8)]:
  assert full.query(query)==index.query(query)
 index.validate_bindings({s:snapshot.current[s]for s in snapshot.current},versions,context='test')
 snapshot.validate_bindings();assert snapshot.weight<=6000 and not snapshot.shapes


def test_envelope_index_rejects_different_geometry_with_the_same_bounds():
 from src.stage_abi.spatial_queries import SpatialQueries
 a=box(0,0,2,2);b=a.difference(box(.5,.5,1.5,1.5));index=SpatialQueries({'a':a},context='test',envelopes_only=True)
 assert a.bounds==b.bounds
 with pytest.raises(ValueError,match='INPUT_BINDING_CHANGED'):
  index.validate_bindings({'a':b},dict(index.versions),context='test')


def test_envelope_overlay_updates_preserve_full_tree_queries_and_validation():
 from src.stage_abi.spatial_queries import SpatialQueries
 material={'a':box(0,0,1,1),'b':box(4,0,5,1)};index=SpatialQueries(material,context='test',envelopes_only=True,overlay_entries=1)
 for sid,shape in [('b',box(1.1,0,2.1,1)),('c',box(1.5,0,1.9,1))]:
  material[sid]=shape;index.update(sid,shape)
  fresh=SpatialQueries(material,context='test')
  assert index.query(box(.9,-1,2,2))==fresh.query(box(.9,-1,2,2))
  index.validate_bindings(material,dict(index.versions),context='test')
