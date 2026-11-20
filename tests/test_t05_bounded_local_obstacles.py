"""Local trim proof boundaries; all physical acceptance remains downstream."""
from shapely import set_precision
from shapely.geometry import box
from shapely.ops import unary_union

from src.t05_bounded_local_obstacles import BoundedLocalObstacles
from src.junction_spindle_blend import check_spindle


def buffer(shape, gap):
    return shape.buffer(gap, quad_segs=64)


def test_contacting_local_trim_avoids_full_buffer_and_matches_complete_mask():
    domain = box(0, 0, 1, 1)
    obstacles = [box(.4, -100, .6, 100), box(50, 50, 60, 60)]
    guard = BoundedLocalObstacles(domain, obstacles, .04, buffer)
    proposal = box(.2, .2, .8, .8)
    reference = proposal.difference(unary_union([buffer(g, .04) for g in obstacles]))
    actual = guard.trim(proposal)
    assert actual.equals(reference)
    assert guard.reference is None
    assert guard.statistics['bounded_local_trims'] == 1
    assert guard.statistics['reference_builds'] == 0
    # A second radius proposal reuses the same local mask.
    guard.trim(box(.25, .25, .75, .75))
    assert guard.statistics['local_builds'] == 1
    assert guard.statistics['bounded_local_trims'] == 2


def test_outside_domain_and_nonzero_precision_keep_full_fallback():
    domain, obstacle = box(0, 0, 1, 1), box(.4, -100, .6, 100)
    outside = box(-.5, .2, .8, .8)
    guard = BoundedLocalObstacles(domain, [obstacle], .04, buffer)
    assert guard.trim(outside).equals(outside.difference(buffer(obstacle, .04)))
    assert guard.statistics['reference_builds'] == 1
    guard.trim(box(.2, .2, .8, .8))
    assert guard.statistics.get('bounded_local_trims', 0) == 0
    fixed = BoundedLocalObstacles(domain, [obstacle], .04, buffer)
    fixed.trim(set_precision(box(.2, .2, .8, .8), 1e-6))
    assert fixed.statistics['reference_builds'] == 1


def test_changed_copper_gets_new_local_mask():
    domain, proposal = box(0, 0, 1, 1), box(.2, .2, .8, .8)
    left = BoundedLocalObstacles(domain, [box(.4, -100, .5, 100)], .04, buffer)
    right = BoundedLocalObstacles(domain, [box(.6, -100, .7, 100)], .04, buffer)
    assert not left.trim(proposal).equals(right.trim(proposal))


def test_local_geometry_is_not_a_clearance_or_connectivity_verdict():
    owner, window = box(-1, 0, 0, 1), box(-2, -2, 2, 2)
    addition = box(-.1, .4, .2, .6)
    foreign = [('nearby', box(.21, .4, .3, .6))]
    # Even a caller-supplied incorrectly empty mask cannot waive the checker.
    guard = BoundedLocalObstacles(window, [], .04011, buffer)
    actual = guard.trim(addition)
    checked = check_spindle(owner, owner.union(actual), actual, window, foreign, gap=.0401)
    assert 'FOREIGN_CLEARANCE:nearby' in checked['failures']
    disconnected = guard.trim(box(.5, .5, .6, .6))
    checked = check_spindle(owner, owner.union(disconnected), disconnected, window, [])
    assert 'DISCONNECTED_OR_INVALID_CANDIDATE' in checked['failures']
