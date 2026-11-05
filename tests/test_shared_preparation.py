import copy
from dataclasses import replace
import pytest
from shapely import to_wkb,STRtree
from shapely.geometry import box,Point
from src.stage_abi.preparation import worker_resources,decode_geometry,prepared_tree,PreparedAdapter,ACTIVE
from src.stage_abi.store import ArtifactStore
from src.native_preparation import native_view,native_loads,ACTIVE as NATIVE_ACTIVE


def test_geometry_hits_still_require_callers_actual_read_and_release():
    shape=box(0,0,1,1);blob=to_wkb(shape)
    with worker_resources('one') as resources:
        first=decode_geometry(blob);assert decode_geometry(blob) is first
        assert resources.diagnostics()['geometry_hits']==1
    assert not resources.decoded and resources.geometry_weight==0 and ACTIVE.get() is None and NATIVE_ACTIVE.get() is None


def test_native_owned_trees_remain_mutable_independent_projections():
    text='(board (version 1))'+' '*4200
    with worker_resources('one'):
        view=native_view(text);owned=native_loads(text);owned[1].append('edit')
        assert list(view[1])!=owned[1] and native_loads(text)[1]==[__import__('sexpdata').Symbol('version'),1]


def test_corrupt_decoded_or_memo_geometry_rejects_before_return():
    with pytest.raises(ValueError,match='PREPARATION_DECODED_GEOMETRY_CHANGED'):
        with worker_resources('one') as resources:
            decode_geometry(to_wkb(box(0,0,1,1)));key=next(iter(resources.decoded))
            resources.decoded[key]=replace(resources.decoded[key],shape=box(9,9,10,10))
    assert ACTIVE.get() is None
    with pytest.raises(ValueError,match='LOADED_GEOMETRY_CACHE_CORRUPTED'):
        with worker_resources('two') as resources:
            resources.memo.buffer(box(0,0,1,1),.1);key=next(iter(resources.memo.values));resources.memo.values[key]=replace(resources.memo.values[key],value=box(9,9,10,10))


def test_ordered_spatial_candidates_match_native_and_recheck_exact_predicates():
    shapes=[box(2,0,3,1),box(0,0,1,1),box(1,0,2,1)];query=box(.5,0,2.5,1)
    with worker_resources('one') as resources:
        tree=prepared_tree(shapes);native=STRtree(shapes)
        assert tree.query(query).tolist()==native.query(query).tolist()
        assert tree.query(query).tolist()==native.query(query).tolist()
        before=resources.stats['spatial_hits']
        assert tree.query(query,predicate='intersects').tolist()==native.query(query,predicate='intersects').tolist()
        assert resources.stats['spatial_hits']==before
        assert prepared_tree(shapes) is tree


def test_changed_index_vector_invalidates_old_neighborhood_and_rollback_reuses_correct_vector():
    a,b=box(0,0,1,1),box(4,0,5,1);q=box(1.5,0,2.5,1)
    with worker_resources('one'):
        old=prepared_tree([a,b]);assert old.query(q).tolist()==[]
        changed=prepared_tree([a,box(2,0,3,1)]);assert changed.query(q).tolist()==[1]
        assert prepared_tree([a,b]).query(q).tolist()==[]


def test_spatial_cache_and_index_mutation_reject():
    with pytest.raises(ValueError,match='PREPARATION_NEIGHBORHOOD_CHANGED'):
        with worker_resources('one') as resources:
            tree=prepared_tree([box(0,0,1,1)]);q=box(0,0,2,2);tree.query(q)
            key=next(iter(resources.queries));resources.queries[key]=replace(resources.queries[key],indices=())
            tree.query(q)
    with pytest.raises(ValueError,match='PREPARATION_SPATIAL_BINDING_CHANGED'):
        with worker_resources('two'):
            tree=prepared_tree([box(0,0,1,1)]);tree.geometries[0]=box(9,9,10,10)


def test_zero_budgets_keep_original_checked_execution_without_retention():
    with worker_resources('tiny',geometry_bytes=0,memo_bytes=0,index_bytes=0,query_bytes=0,query_entries=0) as resources:
        blob=to_wkb(box(0,0,1,1));assert to_wkb(decode_geometry(blob))==blob
        assert prepared_tree([box(0,0,1,1)]).query(box(0,0,2,2)).tolist()==[0]
        assert not resources.decoded and not resources.trees and not resources.queries


def test_adapter_policy_mutation_rejects_and_cleanup_runs(tmp_path):
    store=ArtifactStore(tmp_path);g=store.put('geometry',to_wkb(box(0,0,1,1)))
    scene={'objects':[dict(source_id='one',geometry_ref=g,original_ref=g)]};policy={'stage':'test'}
    class Adapter:
        def run(self,store,scene,policy,*a):policy['changed']=True;return {'passed':True}
    with pytest.raises(ValueError,match='PREPARATION_SCENE_OR_POLICY_CHANGED'):PreparedAdapter(Adapter()).run(store,scene,policy)
    assert ACTIVE.get() is None


def test_adapter_cache_views_are_bound_to_original_current_bytes(tmp_path):
    store=ArtifactStore(tmp_path);g=store.put('geometry',to_wkb(box(0,0,1,1)));row=dict(source_id='one',geometry_ref=g,original_ref=g)
    scene={'objects':[row]};policy={'stage':'test'}
    class Adapter:
        def run(self,store,scene,policy,*a):
            self._prepared_context=({'one':row},{'one':box(7,7,8,8)},{'one':box(0,0,1,1)});return {'passed':True}
    with pytest.raises(ValueError,match='PREPARATION_ADAPTER_GEOMETRY_CHANGED'):PreparedAdapter(Adapter()).run(store,scene,policy)


def test_geometry_precision_and_srid_are_part_of_memo_identity():
    from shapely import set_precision,set_srid,get_precision,get_srid
    base=box(0,0,1,1);cases=[base,set_precision(base,.1),set_srid(base,4326)]
    with worker_resources('metadata') as resources:
        for g in cases:
            actual=resources.memo.construct('identity',[g],(),lambda:g)
            assert get_precision(actual)==get_precision(g) and get_srid(actual)==get_srid(g)
        assert resources.memo.stats['builds']==3


def test_index_eviction_does_not_retain_dead_indexes():
    import gc,weakref
    from shapely.geometry import box
    from src.stage_abi.preparation import worker_resources,prepared_tree
    with worker_resources('bounded-index-registry',index_bytes=1600) as owner:
        first=prepared_tree([box(0,0,1,1)]);ref=weakref.ref(first)
        second=prepared_tree([box(2,0,3,1)])
        assert owner.index_weight<=owner.index_limit and len(owner.trees)==1
        del first;gc.collect()
        assert ref() is None and len(owner.used_trees)==1
        owner.validate()
