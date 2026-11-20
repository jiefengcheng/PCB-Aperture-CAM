"""Operation-local operands for bulk reservations and residual candidates.

No clearance verdicts or constructed-group audits live here. Immutable strip
buffers keep their original order; the mutable scene reuses the existing
versioned spatial service and falls back to a full index on a budget miss.
"""
from collections.abc import MutableMapping
from shapely import STRtree
from src.stage_abi.spatial_queries import SpatialQueries, INDEX_BYTES
from .limiting_math import GUARD, MARGIN


class StripReservations:
    """Compile each admitted strip's guard once, without merging operands."""

    def __init__(self, strips, owners):
        self.records = [(owners[lane['source_ids'][0]], shape,
                         shape.envelope.buffer(GUARD)) for lane, shape in strips]
        self.buffers = {}

    def foreign(self, owner, source):
        envelope = source.envelope
        found = []
        for index, (strip_owner, shape, window) in enumerate(self.records):
            if strip_owner == owner or not window.intersects(envelope):
                continue
            if index not in self.buffers:
                self.buffers[index] = shape.buffer(GUARD + 2*MARGIN, quad_segs=128)
            found.append(self.buffers[index])
        return found


class ResidualScene(MutableMapping):
    """Track every accepted material update, never cache a clearance result.

    The index covers all nonempty material. The caller filters owners and
    checks geometry after candidate discovery. No budget can remove a source
    from the mapping or its queries. This workspace ends before joint assembly.
    """

    def __init__(self, material, *, index_bytes=INDEX_BYTES):
        self.material = dict(material)
        self.index_bytes = index_bytes
        self._index = None
        self._index_available = True

    def __getitem__(self, key):
        return self.material[key]

    def __iter__(self):
        return iter(self.material)

    def __len__(self):
        return len(self.material)

    def items(self):
        return self.material.items()

    def values(self):
        return self.material.values()

    def __setitem__(self, key, shape):
        self.material[key] = shape
        if self._index is not None:
            try:
                self._index.update(key, None if shape.is_empty else shape)
            except ValueError as error:
                if str(error) != 'SPATIAL_INDEX_BUDGET':
                    raise
                self.close()

    def __delitem__(self, key):
        del self.material[key]
        if self._index is not None:
            self._index.update(key, None)

    def query(self, window):
        if window.is_empty:
            return ()
        if self._index is None and self._index_available:
            try:
                self._index = SpatialQueries(
                    {s:g for s,g in self.material.items() if not g.is_empty},
                    context={'schema': 't04-residual-material-workspace/1'},
                    index_bytes=self.index_bytes, query_bytes=0, query_entries=0)
            except ValueError as error:
                if str(error) != 'SPATIAL_INDEX_BUDGET':
                    raise
                self._index_available = False
        if self._index is not None:
            return self._index.query(window)
        ids = sorted(s for s,g in self.material.items() if not g.is_empty)
        tree = STRtree([self.material[s] for s in ids])
        return tuple(ids[int(i)] for i in sorted(map(int, tree.query(window))))

    def close(self):
        if self._index is not None:
            self._index.close()
        self._index = None
        self._index_available = False
