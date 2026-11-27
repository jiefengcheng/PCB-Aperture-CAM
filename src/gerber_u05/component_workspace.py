"""Operation-local operands for bulk reservations and residual candidates.

No clearance verdicts or constructed-group audits live here. Immutable strip
buffers keep their original order; the mutable scene reuses the existing
versioned spatial service and falls back to a full index on a budget miss.
"""
from collections.abc import MutableMapping
from shapely import STRtree
from shapely.geometry import box,Polygon
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

    def __init__(self, material, *, index_bytes=INDEX_BYTES, source_floors=None):
        self.material = dict(material)
        self.source_floors = dict(source_floors or {})
        self._floor_fragments = {}
        for key in self.source_floors:self.material.setdefault(key,Polygon())
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
        self._floor_fragments.pop(key,None)
        if self._index is not None:
            try:
                self._index.update(key, self._indexed_shape(key,shape))
            except ValueError as error:
                if str(error) != 'SPATIAL_INDEX_BUDGET':
                    raise
                if self.source_floors:raise ValueError('T04_SOURCE_FLOOR_RESERVATION_CAPACITY')from error
                self.close()

    def __delitem__(self, key):
        if key in self.source_floors:
            self[key]=Polygon();return
        del self.material[key]
        self._floor_fragments.pop(key,None)
        if self._index is not None:
            self._index.update(key, None)

    def _indexed_shape(self,key,shape):
        floor=self.source_floors.get(key)
        if floor is None or floor.is_empty:return None if shape.is_empty else shape
        if shape.is_empty:return floor
        a,b,c,d=shape.bounds;x,y,z,w=floor.bounds
        return shape if a<=x and b<=y and c>=z and d>=w else box(min(a,x),min(b,y),max(c,z),max(d,w))

    def reservation_rows(self,key,shape=None):
        """Borrow current copper plus only its missing immutable source floor.

        The fragment is prepared once per accepted material object, never per
        candidate. No union, ownership reconstruction or clearance result is
        cached. Geometry used to construct the profile remains unchanged.
        """
        if shape is None:shape=self.material[key]
        floor=self.source_floors.get(key)
        rows=[]if shape.is_empty else[(key,shape)]
        if floor is None or floor.is_empty or shape is floor:return rows
        cached=self._floor_fragments.get(key)
        if cached is None or cached[0]is not shape or cached[1]is not floor:
            from .finite_profile_union import polygonal
            missing=floor if shape.is_empty else polygonal(floor.difference(shape))
            if not missing.is_valid:raise ValueError('T04_SOURCE_FLOOR_RESERVATION_INVALID')
            cached=(shape,floor,missing);self._floor_fragments[key]=cached
        if not cached[2].is_empty:rows.append((key+':retained-source-floor',cached[2]))
        return rows

    def query(self, window):
        if window.is_empty:
            return ()
        if self._index is None and self._index_available:
            try:
                self._index = SpatialQueries(
                    {s:shape for s,g in self.material.items() if (shape:=self._indexed_shape(s,g))is not None},
                    context={'schema': 't04-residual-material-workspace/1'},
                    index_bytes=self.index_bytes, query_bytes=0, query_entries=0)
            except ValueError as error:
                if str(error) != 'SPATIAL_INDEX_BUDGET':
                    raise
                if self.source_floors:raise ValueError('T04_SOURCE_FLOOR_RESERVATION_CAPACITY')from error
                self._index_available = False
        if self._index is not None:
            return self._index.query(window)
        if self.source_floors:raise ValueError('T04_SOURCE_FLOOR_RESERVATION_CAPACITY')
        shapes={s:shape for s,g in self.material.items()if(shape:=self._indexed_shape(s,g))is not None}
        ids = sorted(shapes)
        tree = STRtree([shapes[s] for s in ids])
        return tuple(ids[int(i)] for i in sorted(map(int, tree.query(window))))

    def close(self):
        if self._index is not None:
            self._index.close()
        self._index = None
        self._index_available = False
