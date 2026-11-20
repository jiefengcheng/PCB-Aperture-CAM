"""Bounded reuse must preserve geometric witnesses and fresh policy decisions."""
from dataclasses import replace
import gc
import weakref

import pytest
from shapely import set_precision, to_wkb
from shapely.geometry import box, Point, LineString, Polygon

from src.stage_abi.loaded_geometry import GeometryMemo, GeometrySnapshot
from src.stage_abi.store import ArtifactStore
from src.junction_spindle_blend import spindle_addition, spindle_blend, check_spindle


def test_constructed_geometry_is_exact_and_operand_order_is_preserved():
    memo = GeometryMemo('source/policy/frame/precision')
    a, b = box(0, 0, 2, 2), box(1, 1, 3, 3)
    for name in ('union', 'intersection', 'difference', 'symmetric_difference'):
        expected = getattr(a, name)(b)
        assert to_wkb(getattr(memo, name)(a, b)) == to_wkb(expected)
        assert to_wkb(getattr(memo, name)(a, b)) == to_wkb(expected)
    assert not memo.difference(a, b).equals(memo.difference(b, a))
    assert memo.stats['hits'] >= 4


def test_spindle_geometry_all_witnesses_and_policy_failure_match_reference():
    owner = Point(0, 0).buffer(.2, quad_segs=64).union(LineString([(0, 0), (1, 0)]).buffer(.025, quad_segs=64))
    window = box(-1, -1, 2, 1)
    memo = GeometryMemo('case')
    actual = spindle_blend(owner, .15, window, geometry=memo)
    expected = spindle_blend(owner, .15, window)
    assert [to_wkb(g) for g in actual] == [to_wkb(g) for g in expected]
    foreign = [('covered', box(-.01, -.01, .01, .01)), ('nearby', box(.5, .055, .6, .1))]
    for gap in (.02, .05):
        assert check_spindle(owner, *actual, window, foreign, gap=gap, geometry=memo) == check_spindle(owner, *expected, window, foreign, gap=gap)
    low = check_spindle(owner, *actual, window, foreign, gap=.02, geometry=memo)
    stricter_gap = low['pairs'][-1]['gap_mm'] + .01
    high = check_spindle(owner, *actual, window, foreign, gap=stricter_gap, geometry=memo)
    assert low['passed'] and not high['passed']
    assert memo.stats['measurement_hits'] > 0


def test_measurement_uses_both_current_operands_and_is_not_a_permission():
    memo = GeometryMemo('same policy')
    a, b = box(0, 0, 1, 1), box(-1, -1, 2, 2)
    assert memo.difference_empty(a, b)
    assert not memo.difference_empty(a, box(0, 0, .5, .5))
    assert not memo.difference_empty(b, a)


def test_disjoint_bounds_measurement_keeps_touching_and_fixed_grid_overlay():
    memo = GeometryMemo('floating and fixed copper')
    left = Point(0, 0).buffer(1, quad_segs=128)
    right = box(1.000001, -1, 2, 1)
    touching = box(1, -1, 2, 1)
    fixed = set_precision(right, .0000001)
    rest = [touching, fixed, Polygon(), box(-1, -1, 1, 1)]
    assert memo.difference_empty(left, right) is False
    assert memo.difference_empty(left, right) is False
    assert memo.stats['measurement_hits'] == 1
    for a, b in [(left, g) for g in rest] + [(Polygon(), left)]:
        assert memo.difference_empty(a, b) == a.difference(b).is_empty
    assert memo.stats['measurement_disjoint_bounds'] == 1


def test_spindle_addition_reuse_rechecks_changed_window_and_radius():
    owner = Point(0, 0).buffer(.2).union(LineString([(0, 0), (1, 0)]).buffer(.025))
    window = box(-1, -1, 2, 1)
    smaller_window = box(.15, 0, .23, .3)
    memo = GeometryMemo('spindle')
    cases = [(owner, .15, window), (owner, .15, window),
             (owner, .10, window), (owner, .15, smaller_window),
             (owner.buffer(.001), .15, window)]
    for copper, radius, scope in cases:
        expected = (copper.buffer(radius, quad_segs=64)
                    .buffer(-radius, quad_segs=64).difference(copper).intersection(scope))
        actual = spindle_addition(copper, radius, scope, geometry=memo)
        assert to_wkb(actual) == to_wkb(expected)
    assert memo.stats['hits_spindle-addition'] == 1


def test_geometry_and_scalar_cache_corruption_reject_without_recomputation():
    a, b = box(0, 0, 1, 1), box(.5, .5, 2, 2)
    memo = GeometryMemo('case');memo.difference(a, b)
    key = next(iter(memo.values));entry = memo.values[key]
    memo.values[key] = replace(entry, value=box(10, 10, 11, 11))
    with pytest.raises(ValueError, match='CACHE_CORRUPTED'):memo.difference(a, b)
    memo = GeometryMemo('case');memo.difference_empty(a, b)
    key = next(iter(memo.values));entry = memo.values[key]
    memo.values[key] = replace(entry, value=not entry.value)
    with pytest.raises(ValueError, match='MEASUREMENT_CORRUPTED'):memo.difference_empty(a, b)


def test_eviction_signature_budget_and_disabled_cache_keep_exact_results():
    memo = GeometryMemo('case', limit=4096, entries=3, signatures=4)
    off = GeometryMemo('case', limit=0, entries=0, signatures=0)
    for i in range(100):
        a, b = box(i, 0, i+1, 1), box(i+.5, 0, i+1.5, 1)
        assert to_wkb(memo.difference(a, b)) == to_wkb(off.difference(a, b))
        assert memo.difference_empty(a, b) == off.difference_empty(a, b)
        assert memo.weight <= 4096 and len(memo.values) <= 3 and len(memo.signatures) <= 4
    assert memo.stats['evictions'] > 0 and not off.values and not off.signatures
    memo.close()
    assert memo.weight == 0 and not memo.values and not memo.signatures


def test_signature_records_do_not_keep_dead_operands_alive():
    memo = GeometryMemo('case')
    a = box(0, 0, 1, 1);ref = weakref.ref(a);memo.token(a)
    del a;gc.collect()
    assert ref() is None and not memo.signatures


@pytest.mark.parametrize('value', [-1, 1.5, True, None])
def test_invalid_budgets_reject(value):
    with pytest.raises(ValueError, match='INVALID_BUDGET'):GeometryMemo('case', limit=value)


def snapshot_fixture(tmp_path):
    store = ArtifactStore(tmp_path / 'runtime')
    ref = store.put('geometry', to_wkb(box(0, 0, 1, 1)))
    scene = dict(objects=[dict(source_id='first', geometry_ref=ref, original_ref=ref),
                          dict(source_id='alias', geometry_ref=ref, original_ref=ref)], viewport_mm=[-1, -1, 2, 2])
    return store, ref, scene


def test_snapshot_deduplicates_shapes_but_reads_each_occurrence_and_composes_all(tmp_path):
    store, ref, scene = snapshot_fixture(tmp_path)
    snapshot = GeometrySnapshot(store, scene)
    assert snapshot.stats['decodes'] == 1 and snapshot.stats['artifact_accesses'] == 4
    assert snapshot.current['first'] is snapshot.original['alias']
    from src.stage_abi.scene import composed
    assert to_wkb(snapshot.composed(store, scene)) == to_wkb(composed(store, scene))
    assert snapshot.stats['artifact_accesses'] == 6
    snapshot.close();assert snapshot.weight == 0 and not snapshot.shapes and not snapshot.current


def test_snapshot_detects_changed_bytes_and_changed_cached_shape(tmp_path):
    store, ref, scene = snapshot_fixture(tmp_path)
    snapshot = GeometrySnapshot(store, scene)
    (store.root / 'artifacts' / ref['artifact_id']).write_bytes(b'corrupt')
    with pytest.raises(ValueError) as error:snapshot.geometry(store, ref)
    assert error.value.code == 'ARTIFACT_CORRUPTED'
    store, ref, scene = snapshot_fixture(tmp_path / 'other');snapshot = GeometrySnapshot(store, scene)
    _, h = snapshot.shapes[ref['sha256']]
    snapshot.shapes[ref['sha256']] = (box(10, 10, 11, 11), h)
    with pytest.raises(ValueError, match='SNAPSHOT_CORRUPTED'):snapshot.geometry(store, ref)


def test_loaded_current_or_original_view_cannot_diverge_from_its_artifact(tmp_path):
    store, _, scene = snapshot_fixture(tmp_path)
    for view in ('current', 'original'):
        snapshot = GeometrySnapshot(store, scene)
        snapshot.validate_bindings()
        getattr(snapshot, view)['first'] = box(10, 10, 11, 11)
        with pytest.raises(ValueError, match='SNAPSHOT_BINDING_CHANGED'):snapshot.validate_bindings()


def test_snapshot_budget_rejects_instead_of_falling_back(tmp_path):
    store, _, scene = snapshot_fixture(tmp_path)
    with pytest.raises(ValueError, match='SNAPSHOT_BUDGET'):GeometrySnapshot(store, scene, limit=1)


@pytest.mark.parametrize('change', ['write_mask', 'budget', 'metadata'])
def test_operation_rejects_mutation_and_releases_its_memo(tmp_path, change):
    from tests.test_u05_attachments import fixture
    store, scene, policy, plan, adapter = fixture(tmp_path)
    def mutate(_):
        if change == 'write_mask':adapter.write = box(-4, -4, 4, 4)
        elif change == 'budget':adapter.geometry_budgets['memo_bytes'] += 1
        else:scene['objects'][-1]['metadata']['land_ids'] = []
    with pytest.raises(ValueError, match='EXECUTION_INPUT_CHANGED'):
        adapter.run(store, scene, policy, plan, mutate)
    assert adapter._geometry is None
    adapter.close();assert adapter._snapshot is None


def test_operation_failure_and_small_eviction_cache_do_not_change_treatment(tmp_path):
    from tests.test_u05_attachments import fixture
    store, scene, policy, plan, adapter = fixture(tmp_path)
    first = adapter.run(store, scene, policy, plan, lambda _:None)
    adapter.geometry_budgets.update(memo_bytes=1024, memo_entries=1, signature_entries=1)
    second = adapter.run(store, scene, policy, plan, lambda _:None)
    assert first == second
    assert adapter.verify(store, scene, policy, plan, second, {'scope':'complete-source-and-all-patches'}, lambda _:None)['passed']
    def stop(_):raise RuntimeError('diagnostic stop')
    with pytest.raises(RuntimeError, match='diagnostic stop'):adapter.run(store, scene, policy, plan, stop)
    assert adapter._geometry is None
    adapter.close();assert adapter._snapshot is None
