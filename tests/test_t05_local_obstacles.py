"""Exact legacy-overlay comparisons and conservative fallback controls."""
import random

import pytest
from shapely import set_precision, to_wkb
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from src.t05_local_obstacles import LocalObstacles


def buffer(g, r):
    return g.buffer(r, quad_segs=64)


def reference(proposal, obstacles, gap=.11):
    return proposal.difference(unary_union([buffer(g, gap) for g in obstacles]))


def test_disjoint_proposal_keeps_exact_difference_bytes_without_full_buffers():
    obstacles = [box(.8, -100, 1.2, 100), box(20, 20, 21, 21)]
    calls = []
    def counted(g, r):
        calls.append(g)
        return buffer(g, r)
    guard = LocalObstacles(box(-1, -1, 1, 1), obstacles, .11, counted)
    proposal = Point(0, 0).buffer(.2)
    assert to_wkb(guard.trim(proposal)) == to_wkb(reference(proposal, obstacles))
    assert guard.statistics['disjoint_trims'] == 1 and calls == []


def test_contact_preserves_order_duplicates_and_reuses_one_full_mask():
    obstacle = box(.2, -100, .4, 100)
    obstacles = [obstacle, Point(.6, 0).buffer(.1), obstacle]
    calls = []
    def counted(g, r):
        calls.append(to_wkb(g))
        return buffer(g, r)
    guard = LocalObstacles(box(-1, -1, 1, 1), obstacles, .11, counted)
    for radius in (.4, .3, .2, .05):
        proposal = Point(0, 0).buffer(radius)
        assert to_wkb(guard.trim(proposal)) == to_wkb(reference(proposal, obstacles))
    assert calls == [to_wkb(g) for g in obstacles]
    assert guard.statistics['reference_builds'] == 1
    assert guard.statistics['reference_trims'] == 4


def test_neighbor_just_outside_domain_still_clips_the_proposal():
    obstacles = [box(1.01, -.5, 5, .5)]
    proposal = box(.95, -.2, 1, .2)
    guard = LocalObstacles(box(-1, -1, 1, 1), obstacles, .11, buffer)
    assert guard.trim(proposal).is_empty
    assert guard.statistics['reference_builds'] == 1


@pytest.mark.parametrize('kind', ['outside', 'precision', 'empty'])
def test_unsupported_fast_path_uses_original_operation(kind):
    domain = box(-1, -1, 1, 1)
    obstacles = [box(1.5, -.2, 2, .2)]
    proposal = box(-.2, -.2, .2, .2)
    if kind == 'outside':
        proposal = box(1.4, -.2, 1.6, .2)
    elif kind == 'precision':
        proposal = set_precision(proposal, .01)
    else:
        proposal = Polygon()
    guard = LocalObstacles(domain, obstacles, .11, buffer)
    assert to_wkb(guard.trim(proposal)) == to_wkb(reference(proposal, obstacles))
    assert guard.statistics['reference_builds'] == 1


def test_hole_is_free_but_a_hidden_island_is_not():
    ring = box(-10, -10, 10, 10).difference(box(-.5, -.5, .5, .5))
    proposal = box(-.1, -.1, .1, .1)
    for obstacles, clipped in (([ring], False), ([ring, box(-.01, -.01, .01, .01)], True)):
        guard = LocalObstacles(box(-1, -1, 1, 1), obstacles, .11, buffer)
        actual = guard.trim(proposal)
        assert to_wkb(actual) == to_wkb(reference(proposal, obstacles))
        assert (actual.area < proposal.area) is clipped


def test_changed_copper_uses_a_new_guard_not_a_previous_acceptance():
    obstacles = [box(2, 2, 3, 3)]
    proposal = box(-.01, -.01, .01, .01)
    old = LocalObstacles(box(-1, -1, 1, 1), obstacles, .11, buffer)
    obstacles.append(box(-.1, -.1, .1, .1))
    new = LocalObstacles(box(-1, -1, 1, 1), obstacles, .11, buffer)
    assert not old.trim(proposal).is_empty
    assert new.trim(proposal).is_empty


def test_deterministic_varied_geometry_matches_full_overlay_bytes():
    rng = random.Random(17)
    for _ in range(80):
        obstacles = [Point(rng.uniform(-2, 2), rng.uniform(-2, 2)).buffer(
            rng.uniform(.02, .3), quad_segs=16) for _ in range(4)]
        # Include a long foreign surface whose remote ends should be irrelevant.
        x = rng.uniform(-2, 2)
        obstacles.append(box(x, -100, x+.1, 100))
        proposal = Point(rng.uniform(-.5, .5), rng.uniform(-.5, .5)).buffer(.1)
        guard = LocalObstacles(box(-1, -1, 1, 1), obstacles, .11, buffer)
        assert to_wkb(guard.trim(proposal)) == to_wkb(reference(proposal, obstacles))
