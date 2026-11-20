from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace

import pytest
from shapely import from_wkb, get_srid, set_precision, set_srid, to_wkb
from shapely.geometry import LineString, Polygon, box

from src.gerber_u05.profile_candidates import CandidateCache, describe_geometry
from src.gerber_u05 import translated_profile as tp
from src.t04_settings import capture


@pytest.mark.parametrize('limit', [-1, 1.5, True, None])
def test_cache_rejects_invalid_byte_budget(limit):
    with pytest.raises(ValueError, match='NONNEGATIVE_BYTES'):
        CandidateCache(limit)


def rectangles(route, step):
    x = route * 2.
    original = box(x, 0., x + .05, 1.)
    radius = step * .005
    body = box(x - radius, -radius, x + .05 + radius, 1. + radius)
    return body, body.difference(original)


@pytest.mark.parametrize('routes', [1, 64, 1524])
@pytest.mark.parametrize('limit', [0, 1, 4096, 16 * 1024**2])
def test_route_counts_and_budgets_preserve_every_recipe_and_shape(routes, limit):
    # Synthetic records only: this does not invoke a board stage or planner.
    cache = CandidateCache(limit)
    recipes = {(r, step): cache.record(*rectangles(r, step))
               for r in range(routes) for step in (0, 1, 2)}
    assert len(recipes) == 3 * routes
    for key in reversed(recipes):
        recipe = recipes[key]
        body, delta = cache.get(recipe, lambda key=key: rectangles(*key))
        assert describe_geometry(body, delta) == recipe
    assert cache.peak_bytes <= limit
    if limit < 4096:
        assert cache.rebuilds == len(recipes)
    if limit == 4096 and routes > 1:
        assert cache.evictions > 0
    cache.clear()
    assert cache.bytes == 0 and not cache.entries
    assert len(recipes) == 3 * routes


def test_changed_geometry_on_a_miss_is_fatal_instead_of_dropping_candidate():
    cache = CandidateCache(0)
    recipe = cache.record(*rectangles(0, 1))
    with pytest.raises(ValueError, match='RECONSTRUCTION_CHANGED'):
        cache.get(recipe, lambda: rectangles(0, 2))


def test_recipe_is_immutable_and_tampered_cache_hit_is_rejected():
    cache = CandidateCache()
    recipe = cache.record(*rectangles(0, 1))
    with pytest.raises(FrozenInstanceError):
        recipe.bounds = (0., 0., 0., 0.)
    with pytest.raises(ValueError, match='RECIPE_CHANGED'):
        cache.get(replace(recipe, bounds=(0., 0., 0., 0.)), lambda: rectangles(0, 1))


def test_srid_and_precision_are_part_of_the_geometry_identity():
    cache = CandidateCache()
    grid_shape = set_precision(box(0., 0., 1., 1.), .001)
    original = from_wkb(to_wkb(grid_shape))
    assert to_wkb(original) == to_wkb(grid_shape)
    plain = cache.record(original, Polygon())
    srid = cache.record(set_srid(original, 4326), Polygon())
    grid = cache.record(grid_shape, Polygon())
    assert len({plain.key, srid.key, grid.key}) == 3
    assert get_srid(cache.get(srid, lambda: pytest.fail('unexpected miss'))[0]) == 4326


@pytest.mark.parametrize('limit', [0, 4096])
@pytest.mark.parametrize('band', [(.130075, .130075), (.11, .121)])
def test_saved_real_copper_rebuilds_exactly_without_cache_residency(limit, band):
    from test_profile_topology_regression import CORE_WKB
    core = from_wkb(CORE_WKB)
    line = LineString([(45.89, .846), (46.393, .343)])
    def build():
        body = tp.profile_body(core, .100075, *band, (0., 0.), line, Polygon())
        return body, body.difference(core)
    cache = CandidateCache(limit)
    recipe = cache.record(*build())
    assert recipe.estimated_bytes > limit
    shapes = cache.get(recipe, build)
    assert describe_geometry(*shapes) == recipe
    assert cache.rebuilds == 1 and cache.bytes == 0


def scene(count):
    rows, original, ids, owners, paths = {}, {}, {}, {}, {}
    for index in range(count):
        r = f'r{index:04d}'
        y = .09 if index == 1 else 0. if index == 0 else index * 4.
        line = LineString([(0., y), (1., y)])
        original[r] = line.buffer(.025, quad_segs=128)
        rows[r] = dict(metadata=dict(minimum_caliper_mm=.05,
                                    route_points_mm=list(line.coords), route_kind='segment'))
        ids[r] = (r,)
        owners[r] = original[r]
        paths[r] = [r]
    return rows, original, paths, SimpleNamespace(ids=ids, cores=owners)


@pytest.mark.parametrize('routes', [2, 8, 64])
def test_real_planner_budget_parity_and_unrelated_route_count_independence(routes):
    rows, original, paths, context = scene(routes)
    snapshots = []
    for budget in (0, 1, 16 * 1024, 512 * 1024**2):
        progress = []
        chosen, _, _, receipt = tp.plan(rows, original, original, paths, {}, context,
            capture(), dict.fromkeys(paths, .0125), .1, progress.append,
            candidate_cache_bytes=budget)
        stats = next(e for e in progress if e['event'] == 'motion_candidate_cache')
        assert stats['peak_estimated_bytes'] <= budget
        assert budget != 0 or stats['rebuilds'] > 0
        snapshots.append(({r: (c['pose'], c['low'], c['high'], to_wkb(c['body']), to_wkb(c['delta']))
                           for r, c in chosen.items()},
                          {k: v for k, v in receipt.items() if k != 'planning_seconds'}))
    assert all(s == snapshots[0] for s in snapshots)
    # Unrelated routes must not change either member of the nearby pair.
    small_rows, small_original, small_paths, small_context = scene(2)
    reference, _, _, _ = tp.plan(small_rows, small_original, small_original,
        small_paths, {}, small_context, capture(), dict.fromkeys(small_paths, .0125),
        .1, candidate_cache_bytes=0)
    for r in small_paths:
        c = reference[r]
        assert snapshots[0][0][r] == (c['pose'], c['low'], c['high'],
                                     to_wkb(c['body']), to_wkb(c['delta']))


def test_no_top_31_or_memory_filter_can_remove_eligible_corridor_candidates():
    rows, original, paths, context = scene(1)
    receipts = []
    for budget in (0, 512 * 1024**2):
        _, _, _, receipt = tp.plan(rows, original, original, paths, {}, context,
            capture(), dict.fromkeys(paths, .0125), .1, corridor_only=True,
            candidate_cache_bytes=budget)
        receipts.append(receipt)
    assert receipts[0]['route_plans']['r0000']['candidate_count'] > 31
    assert receipts[0]['route_plans'] == receipts[1]['route_plans']
