"""Prepared containment only proves owner preservation, never overall safety."""
import pytest
from shapely import is_prepared, prepare, set_precision, to_wkb
from shapely.geometry import Point, Polygon, box

from src.t05_owner_preservation import owner_is_covered
from src.junction_spindle_blend import check_spindle


@pytest.fixture
def owner():
    return Point(0, 0).buffer(1, quad_segs=9000)


def test_large_owner_coverage_preserves_bytes_and_releases_index(owner):
    candidate = owner.buffer(.01)
    before = to_wkb(candidate)
    assert owner_is_covered(owner, candidate, candidate.is_valid)
    assert owner.difference(candidate).is_empty
    assert not is_prepared(candidate)
    assert to_wkb(candidate) == before
    prepare(candidate)
    assert owner_is_covered(owner, candidate, candidate.is_valid)
    assert is_prepared(candidate)  # Never destroy the caller's index.


def test_actual_owner_removal_still_requires_original_cut(owner):
    candidate = owner.difference(box(.9, -2, 2, 2))
    assert not owner_is_covered(owner, candidate, candidate.is_valid)
    result = check_spindle(owner, candidate, Polygon(), box(-3, -3, 3, 3), [])
    assert 'OWNER_REMOVED' in result['failures']


def test_small_invalid_and_precision_inputs_take_original_path(owner):
    candidate = owner.buffer(.01)
    assert not owner_is_covered(box(0, 0, .1, .1), candidate, True)
    assert not owner_is_covered(owner, candidate, False)
    assert not owner_is_covered(owner, set_precision(candidate, 1e-9), True)
    assert not is_prepared(candidate)


def test_coverage_does_not_waive_connectivity_delta_or_clearance(owner):
    addition = box(.9, -.1, 1.1, .1)
    candidate = owner.union(addition)
    assert owner_is_covered(owner, candidate, candidate.is_valid)
    window = box(-3, -3, 3, 3)
    foreign = [('blocker', box(1.11, -.1, 1.2, .1))]
    clearance = check_spindle(owner, candidate, addition, window, foreign, gap=.0401)
    assert 'FOREIGN_CLEARANCE:blocker' in clearance['failures']
    extra = candidate.union(box(1.09, -.05, 1.3, .05))
    assert owner_is_covered(owner, extra, extra.is_valid)
    assert 'DELTA_MISMATCH' in check_spindle(owner, extra, addition, window, [])['failures']
    disconnected = candidate.union(box(2, 2, 2.1, 2.1))
    assert not owner_is_covered(owner, disconnected, disconnected.is_valid)
    assert 'DISCONNECTED_OR_INVALID_CANDIDATE' in check_spindle(owner, disconnected, addition, window, [])['failures']
