"""Spindle reports retain exact legacy distance witnesses and negative results."""
import pytest
from shapely import set_precision
from shapely.geometry import Point, box

from src import indexed_polygon_distance as distance
from src import junction_spindle_blend as spindle
from src.stage_abi.loaded_geometry import GeometryMemo


@pytest.mark.parametrize('gap', [.04, .0401, .0401 - 2e-13, .0401 + 2e-13, .2, -.01])
def test_complete_spindle_report_matches_direct_distance(monkeypatch, gap):
    owner = box(-2, -1, 0, 1)
    addition = Point(0, 0).buffer(.2, quad_segs=400)
    candidate = owner.union(addition)
    foreign = [('curved', Point(1.2 + gap, 0).buffer(1, quad_segs=9000)),
               ('covered', box(-1, -.5, -.5, .5)),
               ('duplicate', Point(1.2 + gap, 0).buffer(1, quad_segs=9000))]
    window = box(-3, -3, 4, 3)
    direct = lambda a, b: a.distance(b)
    distance.clear()
    with monkeypatch.context() as patch:
        patch.setattr(spindle, 'exact_distance', direct)
        expected = spindle.check_spindle(owner, candidate, addition, window, foreign,
                                         gap=.0401, geometry=GeometryMemo('direct'))
    for _ in range(2):
        actual = spindle.check_spindle(owner, candidate, addition, window, foreign,
                                       gap=.0401, geometry=GeometryMemo('indexed'))
        assert actual == expected
    # The same geometry cannot reuse the verdict after the required gap changes.
    strict = spindle.check_spindle(owner, candidate, addition, window, foreign, gap=1.)
    assert not strict['passed']
    assert len(strict['pairs']) == len(foreign)
    assert distance.diagnostics()['distance_value_hits'] > 0
    distance.clear()


def test_changed_foreign_geometry_precision_and_extra_copper_still_checked(monkeypatch):
    owner = box(-2, -1, 0, 1)
    addition = Point(0, 0).buffer(.2, quad_segs=400)
    window = box(-3, -3, 4, 3)
    good = owner.union(addition)
    forged = good.union(box(-.1, .3, .1, .4))
    distance.clear()
    for candidate in (good, forged):
        for neighbor in (Point(2, 0).buffer(1, quad_segs=9000),
                         Point(1, 0).buffer(1, quad_segs=9000),
                         set_precision(Point(2, 0).buffer(1, quad_segs=9000), 1e-6)):
            with monkeypatch.context() as patch:
                patch.setattr(spindle, 'exact_distance', lambda a, b: a.distance(b))
                expected = spindle.check_spindle(owner, candidate, addition, window,
                                                 [('foreign', neighbor)])
            actual = spindle.check_spindle(owner, candidate, addition, window,
                                           [('foreign', neighbor)])
            assert actual == expected
            if candidate is forged: assert 'DELTA_MISMATCH' in actual['failures']
    distance.clear()


def test_medium_foreign_surface_keeps_direct_measurement(monkeypatch):
    owner = box(-2, -1, 0, 1)
    addition = Point(0, 0).buffer(.2, quad_segs=400)
    foreign = Point(2, 0).buffer(1, quad_segs=400)
    def unexpected(*args): raise AssertionError('medium obstacle must use direct distance')
    monkeypatch.setattr(spindle, 'exact_distance', unexpected)
    proof = spindle.check_spindle(owner, owner.union(addition), addition,
                                  box(-3, -3, 4, 3), [('medium', foreign)])
    assert proof['passed']
    assert proof['pairs'][0]['gap_mm'].hex() == addition.distance(foreign).hex()
