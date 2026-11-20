"""Separate exact scalar witnesses without sharing eviction or weakening guards."""
from dataclasses import replace

import pytest
from shapely import set_precision, to_wkb
from shapely.geometry import box, Polygon

from src.stage_abi.loaded_geometry import GeometryMemo
from src.junction_spindle_blend import check_spindle


def memo(**kw):
    return GeometryMemo('unchanged-scene/policy', limit=16384,
                        measurement_bytes=8192, **kw)


def test_scalar_and_geometry_eviction_are_independent_and_share_total_budget():
    m = memo(entries=1, measurement_entries=1)
    a, owner = box(0, 0, 1, 1), box(-1, -1, 2, 2)
    assert m.difference_empty(a, owner)
    for i in range(8):
        m.buffer(box(i, 0, i+1, 1), .1, quad_segs=1)
    builds = m.stats['measurement_builds']
    assert m.difference_empty(a, owner)
    assert m.stats['measurement_builds'] == builds
    shape = box(20, 0, 21, 1)
    expected = to_wkb(m.buffer(shape, .1, quad_segs=1))
    for i in range(8):
        m.difference_empty(box(i, 0, i+1, 1), owner)
    assert to_wkb(m.buffer(shape, .1, quad_segs=1)) == expected
    assert m.stats['hits_buffer'] == 1
    assert m.stats['measurement_evictions'] > 0 and m.stats['evictions'] > 0
    d = m.diagnostics()
    assert d['resident_estimated_bytes'] <= d['limit_bytes'] == 16384
    assert m.weight <= 8192 and m.measurement_weight <= 8192
    assert d['peak_estimated_bytes'] <= 16384
    m.close()
    assert not m.values and not m.measurements and not m.signatures
    assert m.weight == m.measurement_weight == 0


def test_both_changed_operands_order_precision_and_empty_cases_match_overlay():
    m = memo()
    a, owner = box(0, 0, 1, 1), box(-1, -1, 2, 2)
    cases = [(a, owner), (a, owner), (owner, a),
             (a, box(0, 0, .5, .5)), (box(1.5, 0, 3, 1), owner),
             (set_precision(a, .1), owner), (Polygon(), owner),
             (a, Polygon()), (a, box(1, 0, 2, 1))]
    for left, right in cases:
        assert m.difference_empty(left, right) == left.difference(right).is_empty
    assert m.stats['measurement_hits'] == 1


def test_separate_measurement_corruption_is_rejected():
    m = memo()
    a, owner = box(0, 0, 1, 1), box(-1, -1, 2, 2)
    m.difference_empty(a, owner)
    key, old = next(iter(m.measurements.items()))
    m.measurements[key] = replace(old, value=not old.value)
    with pytest.raises(ValueError, match='MEASUREMENT_CORRUPTED'):
        m.difference_empty(a, owner)


def test_disabled_or_tiny_partitions_recompute_and_invalid_budgets_reject():
    a, b = box(0, 0, 1, 1), box(.5, 0, 2, 1)
    for entries in (0, 1):
        m = GeometryMemo('tiny', limit=1, measurement_bytes=1,
                         measurement_entries=entries)
        for _ in range(2):
            assert m.difference_empty(a, b) == a.difference(b).is_empty
        assert not m.measurements and not m.values
    with pytest.raises(ValueError, match='MEASUREMENT_BUDGET'):
        GeometryMemo('bad', limit=10, measurement_bytes=11)
    for value in (-1, True, 1.5):
        with pytest.raises(ValueError, match='INVALID_BUDGET'):
            GeometryMemo('bad', measurement_bytes=value)


def test_cached_measurement_still_rejects_changed_clearance_and_extra_copper():
    m = memo()
    owner, addition, window = box(0, 0, 1, 1), box(.9, .2, 1.1, .8), box(-1, -1, 2, 2)
    candidate = owner.union(addition)
    foreign = [('neighbor', box(1.3, .2, 1.4, .8))]
    for gap in (.1, .25):
        got = check_spindle(owner, candidate, addition, window, foreign, gap=gap, geometry=m)
        reference = check_spindle(owner, candidate, addition, window, foreign, gap=gap)
        assert got == reference
        assert got['passed'] == (gap == .1)
    extra = candidate.union(box(1, .4, 1.3, .6))
    bad = check_spindle(owner, extra, addition, window, foreign, gap=.1, geometry=m)
    assert not bad['passed'] and 'DELTA_MISMATCH' in bad['failures']


def test_t05_partition_preserves_full_candidate_and_verification(tmp_path):
    from tests.test_u05_attachments import fixture
    store, scene, policy, plan, a = fixture(tmp_path)
    reference = a.run(store, scene, policy, plan, lambda _: None)
    a.geometry_budgets.update(memo_bytes=512*1024**2,
                             measurement_bytes=64*1024**2)
    actual = a.run(store, scene, policy, plan, lambda _: None)
    assert actual == reference
    assert a.verify(store, scene, policy, plan, actual,
                    {'scope': 'complete-source-and-all-patches'}, lambda _: None)['passed']
    assert a.last_execution_statistics['memo']['measurement_limit_bytes'] == 64*1024**2
    a.close()
