"""Immutable planning recipes and a geometry-only, byte-bounded LRU.

Recipes remain eligible independently of cache residency. Active source and
chosen-route geometry belongs to the planner; this budget covers reuse only.
"""
from collections import OrderedDict
from dataclasses import dataclass
import hashlib

from shapely import get_precision, to_wkb

DEFAULT_CACHE_BYTES = 512 * 1024**2


@dataclass(frozen=True)
class GeometryRecipe:
    key: tuple
    bounds: tuple
    estimated_bytes: int


@dataclass(frozen=True)
class CandidateRecipe:
    pose: tuple
    low: float
    high: float
    score: tuple
    geometry: GeometryRecipe
    identity: bool = False

    def selected(self, shapes):
        body, delta = shapes
        return dict(pose=self.pose, low=self.low, high=self.high,
                    score=self.score, body=body, delta=delta)


def describe_geometry(body, delta):
    raw = [to_wkb(g, include_srid=True) for g in (body, delta)]
    key = tuple((hashlib.sha256(wkb).hexdigest(), get_precision(g))
                for wkb, g in zip(raw, (body, delta)))
    boxes = [g.bounds for g in (body, delta) if not g.is_empty]
    bounds = (() if not boxes else
              (min(b[0] for b in boxes), min(b[1] for b in boxes),
               max(b[2] for b in boxes), max(b[3] for b in boxes)))
    return GeometryRecipe(key, bounds, 3 * sum(map(len, raw)) + 1024)


class CandidateCache:
    def __init__(self, limit=DEFAULT_CACHE_BYTES):
        if type(limit) is not int or limit < 0:
            raise ValueError('T04_CANDIDATE_CACHE_NONNEGATIVE_BYTES_REQUIRED')
        self.limit = limit
        self.entries = OrderedDict()
        self.bytes = self.peak_bytes = 0
        self.records = self.requests = self.hits = self.rebuilds = 0
        self.evictions = self.bypasses = 0

    def _remember(self, recipe, shapes):
        if recipe.key in self.entries:
            if self.entries[recipe.key][1] != recipe:
                raise ValueError('T04_CANDIDATE_RECIPE_CHANGED')
            self.entries.move_to_end(recipe.key)
            return
        if recipe.estimated_bytes > self.limit:
            self.bypasses += 1
            return
        while self.entries and self.bytes + recipe.estimated_bytes > self.limit:
            _, (_, old) = self.entries.popitem(last=False)
            self.bytes -= old.estimated_bytes
            self.evictions += 1
        self.entries[recipe.key] = (shapes, recipe)
        self.bytes += recipe.estimated_bytes
        self.peak_bytes = max(self.peak_bytes, self.bytes)

    def record(self, body, delta):
        self.records += 1
        recipe = describe_geometry(body, delta)
        self._remember(recipe, (body, delta))
        return recipe

    def get(self, recipe, build):
        self.requests += 1
        if recipe.key in self.entries:
            if self.entries[recipe.key][1] != recipe:
                raise ValueError('T04_CANDIDATE_RECIPE_CHANGED')
            self.hits += 1
            self.entries.move_to_end(recipe.key)
            return self.entries[recipe.key][0]
        self.rebuilds += 1
        shapes = build()
        if describe_geometry(*shapes) != recipe:
            raise ValueError('T04_CANDIDATE_RECONSTRUCTION_CHANGED')
        self._remember(recipe, shapes)
        return shapes

    def diagnostics(self):
        return dict(limit_bytes=self.limit, retained_estimated_bytes=self.bytes,
                    peak_estimated_bytes=self.peak_bytes, records=self.records,
                    requests=self.requests, hits=self.hits, rebuilds=self.rebuilds,
                    evictions=self.evictions, oversized_bypasses=self.bypasses)

    def clear(self):
        self.entries.clear()
        self.bytes = 0
