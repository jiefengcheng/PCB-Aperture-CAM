"""Opt-in exact boundary-section screening for prior-clearance fallbacks.

Retain original copper, every original edge and all clearance policies. A new
actual-copper indexed measurement supplies a conservative search bound; it is
never the returned numeric proof. Nearby original right-hand boundary sections
are measured against the unchanged left polygon in the original orientation.
Unsupported, intersecting and numerically inconclusive cases keep the original
full distance. Qualification is separate from production enablement.
"""
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
import math
import time
import shapely
from shapely.geometry import MultiLineString


class Screen:
    """Reuse the existing bounded exact-edge index; no additional shape cache.

    `distance_module.boundary_index` retains ordered runs of 32 original edges,
    including hole boundaries. Its signature, SRID/precision, geometry checksum
    and tree-container checks remain mandatory. Changed copper misses. All
    construction/index retention stays inside its existing 128 MiB budget;
    this does not change the independent 512 MiB completion memo.
    """
    def __init__(self, distance_module):
        self.module = distance_module
        self.stats = Counter()

    def measure(self, left, right, fallback):
        start = time.perf_counter()
        self.stats['calls'] += 1
        try:
            # Only right-side screening is admitted: swapping operands or
            # replacing the left polygon with a different boundary traversal
            # can change legacy floating witnesses. Small inputs gain little.
            if (left.geom_type not in ('Polygon', 'MultiPolygon') or
                right.geom_type not in ('Polygon', 'MultiPolygon') or
                left.is_empty or right.is_empty or
                not 1024 <= int(shapely.get_num_coordinates(right)) <= 1000000 or
                shapely.get_precision(left) != 0 or shapely.get_precision(right) != 0):
                self.stats['unsupported'] += 1
                return fallback(left, right)
            # Polygon distance has interior/containment semantics. Boundary-only
            # reduction is valid only after proving the full polygons disjoint.
            # This also protects polygons inside holes and touching/overlap cases.
            if not left.is_valid or not right.is_valid or left.intersects(right):
                self.stats['invalid_or_intersecting'] += 1
                return fallback(left, right)
            with self.module.CONTROL:
                if self.module.ENGINE is None:
                    self.module.ENGINE = self.module.Engine()
                upper = float(self.module.ENGINE.measure(left, right))
                if not math.isfinite(upper) or upper <= 4e-12:
                    self.stats['near_zero_or_invalid_bound'] += 1
                    return fallback(left, right)
                tree, parts = self.module.boundary_index(right)
                magnitude = max(1., *(abs(v) for v in (*left.bounds, *right.bounds)))
                padding = max(512*math.ulp(magnitude), 512*math.ulp(upper))
                # GEOS dwithin enumerates a superset around actual left copper,
                # including its complete boundary. Padding enlarges candidates
                # only; it is not applied to copper or a clearance comparison.
                indices = sorted(map(int, tree.query(
                    left, predicate='dwithin', distance=upper+padding)))
                self.stats['sections_considered'] += len(parts)
                self.stats['sections_selected'] += len(indices)
                if not indices or len(indices) == len(parts):
                    self.stats['inconclusive'] += 1
                    return fallback(left, right)
                # A section shares endpoint vertices with its neighbours but
                # contains only original edges, in original direction/order.
                # Never clip at the search window, interpolate a vertex, close
                # the section into a polygon, simplify, union, or reverse it.
                selected = MultiLineString([parts[i] for i in indices])
                selected = shapely.set_srid(selected, shapely.get_srid(right))
                value = float(left.distance(selected))
                if not math.isfinite(value) or value <= 4e-12 or abs(value-upper) > padding:
                    self.stats['witness_fallback'] += 1
                    return fallback(left, right)
                self.stats['screened'] += 1
                return value
        finally:
            self.stats['seconds'] += time.perf_counter()-start

    def diagnostics(self):
        return dict(self.stats, additional_geometry_cache_bytes=0,
                    shared_distance_cache_limit_bytes=self.module.LIMIT)



# The screen is bounded to prior preparation during the saved comparison.
# Context-local selection avoids replacing the distance function globally.
ACTIVE = ContextVar('t05_prior_boundary_screen', default=None)


@contextmanager
def bounded_prior_screen():
    from src import indexed_polygon_distance

    screen = Screen(indexed_polygon_distance)
    token = ACTIVE.set(screen)
    try:
        yield screen
    finally:
        ACTIVE.reset(token)
