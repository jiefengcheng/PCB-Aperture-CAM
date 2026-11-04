"""Conservative candidate completeness and dependency invalidation controls."""
from dataclasses import replace
import random

import pytest
from shapely import STRtree
from shapely.geometry import box, Point, Polygon

from src.stage_abi.spatial_queries import SpatialQueries


def oracle(shapes, query):
    ids = sorted(shapes)
    return tuple(ids[int(i)] for i in sorted(STRtree([shapes[s] for s in ids]).query(query)))


def test_new_interaction_invalidates_previously_empty_query_and_old_location():
    source = {'far': box(20, 20, 21, 21)}
    service = SpatialQueries(source, context='native-mm')
    near, far = box(0, 0, 1, 1), box(19, 19, 22, 22)
    assert service.query(near) == ()
    assert service.query(far) == ('far',)
    assert service.update('far', near) == 2
    assert service.query(near) == ('far',)
    assert service.query(far) == ()
    # Rejected trial rollback rediscovers the previous state via normal updates.
    service.update('far', source['far'])
    assert service.query(near) == () and service.query(far) == ('far',)


def test_same_bounds_new_version_insertion_deletion_and_owner_identity():
    a = box(0, 0, 2, 2)
    service = SpatialQueries({'whole-path': a}, context='one')
    assert service.query(a) == ('whole-path',)
    triangle = Polygon([(0, 0), (2, 2), (2, 0)])
    assert service.update('whole-path', triangle) == 1
    service.update('another-complete-group', a)
    assert service.query(a) == ('another-complete-group', 'whole-path')
    service.update('whole-path', None)
    assert service.query(a) == ('another-complete-group',)


def test_disjoint_neighborhood_survives_while_touching_bounds_invalidate():
    service = SpatialQueries({'a': box(0, 0, 1, 1)}, context='one')
    q = box(10, 10, 11, 11)
    service.query(q)
    assert service.update('a', box(2, 2, 3, 3)) == 0
    service.query(q)
    assert service.stats['query_hits'] == 1
    assert service.update('a', box(9, 9, 10, 10)) == 1
    assert service.query(q) == ('a',)


@pytest.mark.parametrize('cache_entries,overlay_entries', [(0, 0), (1, 1), (16, 7)])
def test_randomized_transitions_match_full_rebuild_including_rollback(cache_entries, overlay_entries):
    rng = random.Random(3304)
    shapes = {str(i): Point(rng.uniform(-20, 20), rng.uniform(-20, 20)).buffer(.3) for i in range(30)}
    service = SpatialQueries(shapes, context='complete', query_entries=cache_entries,
                             query_bytes=6000, overlay_entries=overlay_entries)
    for step in range(90):
        sid = str(rng.randrange(40))
        old = shapes.get(sid)
        g = Point(rng.uniform(-20, 20), rng.uniform(-20, 20)).buffer(rng.uniform(.1, 4))
        for value in (g, old):
            if value is None:shapes.pop(sid, None)
            else:shapes[sid] = value
            service.update(sid, value)
            for q in (box(-30, -30, 30, 30), box(-2, -2, 2, 2), g.envelope):
                assert service.query(q) == oracle(shapes, q)
            assert service.weight <= 6000 and len(service.cache) <= cache_entries
            assert len(service.overlay) <= overlay_entries
    service.close()
    assert not service.current and not service.cache and not service.reverse and service.weight == 0


def test_corrupt_cached_candidate_omission_rejects():
    g = box(0, 0, 1, 1)
    service = SpatialQueries({'a': g}, context='one')
    service.query(g)
    key = next(iter(service.cache))
    service.cache[key] = replace(service.cache[key], members=())
    with pytest.raises(ValueError, match='NEIGHBORHOOD_CORRUPTED'):service.query(g)


def test_context_geometry_and_version_binding_changes_reject():
    g = box(0, 0, 1, 1)
    service = SpatialQueries({'a': g}, context='one')
    service.validate_bindings({'a': g}, service.versions, context='one')
    for geometries, versions, context in [({'a':g}, service.versions, 'two'),
            ({'a':box(0, 0, 1, 1)}, service.versions, 'one'), ({'a':g}, {'a':'changed'}, 'one')]:
        with pytest.raises(ValueError, match='INPUT_BINDING_CHANGED'):
            service.validate_bindings(geometries, versions, context=context)


def test_compact_member_token_corruption_rejects_at_hit_and_verdict_boundary():
    g = box(0, 0, 1, 1)
    service = SpatialQueries({'a':g}, context='one')
    service.query(g)
    service.tokens['a'] = b'x' * 32
    with pytest.raises(ValueError, match='NEIGHBORHOOD_CORRUPTED'):service.query(g)
    with pytest.raises(ValueError, match='TOKEN_BINDING_CHANGED'):
        service.validate_bindings({'a':g}, service.versions, context='one')


def test_empty_nonfinite_and_budget_failure_leave_state_unchanged():
    g = box(0, 0, 1, 1)
    service = SpatialQueries({'a': g}, context='one', index_bytes=1024)
    with pytest.raises(ValueError, match='INDEX_BUDGET'):service.update('b', g)
    with pytest.raises(ValueError, match='NONFINITE_OR_EMPTY'):service.update('a', Polygon())
    assert service.query(g) == ('a',) and service.current['a'] is g


def test_broadphase_never_becomes_exact_contact_or_permission():
    ring = Point(0, 0).buffer(3).difference(Point(0, 0).buffer(2))
    q = Point(0, 0).buffer(.1)
    service = SpatialQueries({'protected-source': ring}, context='one')
    assert service.query(q) == ('protected-source',)
    assert not ring.intersects(q)  # Caller must perform its existing predicate.


def test_adapter_reuses_candidates_but_reconstructs_complete_witnesses(tmp_path):
    from tests.test_u05_attachments import fixture
    store, scene, policy, plan, adapter = fixture(tmp_path)
    first = adapter.run(store, scene, policy, plan, lambda _:None)
    assert adapter.verify(store, scene, policy, plan, first,
                          {'scope':'complete-source-and-all-patches'}, lambda _:None)['passed']
    assert adapter._spatial.stats['query_hits'] > 0
    assert adapter.run(store, scene, policy, plan, lambda _:None) == first
    adapter.close()
    assert not hasattr(adapter, '_spatial')
