"""Local broad phase with canonical full-obstacle subtraction on contact.

Clipping an obstacle before buffering is cheap, but intersecting that clipped
buffer can perturb GEOS overlay coordinates and therefore audit measurements.
The local mask here is only a no-contact test. A touching proposal uses the
original ordered, uncut buffer union, including duplicates. No verdict, area,
candidate-supplied patch or retained decision selects this fallback.
"""
from math import isfinite, ulp

from shapely import get_precision
from shapely.geometry import box
from shapely.ops import unary_union


class LocalObstacles:
    """One junction's immutable obstacles, shared across its radius attempts.

    The caller supplies already owner-filtered operands in their original order.
    Keep references to those immutable Shapely objects, not caller-owned lists.
    A new junction/execution constructs a new instance; no scene acceptance or
    cache survives a copper change. The optional buffer callback uses the
    adapter's existing bounded execution memo without changing its budget.
    """

    def __init__(self, domain, obstacles, gap, buffer):
        if not isfinite(gap) or gap <= 0:
            raise ValueError('T05_LOCAL_BARRIER_POSITIVE_GAP_REQUIRED')
        self.obstacles = tuple(obstacles)
        self.gap = gap
        self.buffer = buffer
        self.reference = None
        self.local = None
        self.bounds = domain.bounds
        self.statistics = dict(local_builds=0, disjoint_trims=0,
                               reference_builds=0, reference_trims=0)
        # Precision-grid overlays and unsupported/invalid operands retain the
        # original path. The fast path is for valid floating polygon surfaces.
        shapes = (domain, *self.obstacles)
        if any(g.is_empty or not g.is_valid or get_precision(g) != 0 or
               g.geom_type not in ('Polygon', 'MultiPolygon') for g in shapes):
            return
        if not all(isfinite(v) for g in shapes for v in g.bounds):
            return
        # This is a conservative fast-path guard, not a new clearance tolerance.
        # A near contact falls back to the original operation and unchanged rules.
        self.margin = max(1e-9, 64 * max(ulp(v) for v in self.bounds))
        halo = 2 * gap + self.margin
        xmin, ymin, xmax, ymax = self.bounds
        capture = box(xmin-halo, ymin-halo, xmax+halo, ymax+halo)
        cx0, cy0, cx1, cy1 = capture.bounds
        parts = []
        for shape in self.obstacles:
            x0, y0, x1, y1 = shape.bounds
            if x1 < cx0 or x0 > cx1 or y1 < cy0 or y0 > cy1:
                continue
            # Artificial cut edges are farther than one buffer radius from
            # the proposal's allowed bounding box. Preserve holes and all faces.
            local = shape.intersection(capture)
            if not local.is_empty:
                parts.append(local.buffer(gap, quad_segs=64))
        self.local = unary_union(parts)
        self.statistics['local_builds'] += 1

    def _full(self):
        if self.reference is None:
            # Exactly the legacy flat union: no grouping, deduplication, clipping,
            # sorting, simplification or rounding. Reuse only within this object.
            self.reference = unary_union([self.buffer(g, self.gap)
                                          for g in self.obstacles])
            self.statistics['reference_builds'] += 1
        return self.reference

    def trim(self, proposal):
        # Once contact requires the full mask, reuse it for subsequent attempts.
        if self.reference is None and self.local is not None:
            bounds = proposal.bounds
            contained = (not proposal.is_empty and len(bounds) == 4 and
                         self.bounds[0] <= bounds[0] <= bounds[2] <= self.bounds[2] and
                         self.bounds[1] <= bounds[1] <= bounds[3] <= self.bounds[3])
            if (contained and proposal.is_valid and get_precision(proposal) == 0 and
                    proposal.geom_type in ('Polygon', 'MultiPolygon') and
                    (self.local.is_empty or proposal.distance(self.local) > self.margin)):
                self.statistics['disjoint_trims'] += 1
                # Keep GEOS difference even for disjoint operands: returning the
                # proposal directly can change ring ordering and hence WKB.
                return proposal.difference(self.local)
        self.statistics['reference_trims'] += 1
        return proposal.difference(self._full())
