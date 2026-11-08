"""Conservative spatial candidates with bounded, versioned dependencies.

This service knows geometry identities, never clearance, permission or verdicts.
Queries return the same sorted AABB candidates as a rebuilt STRtree. Callers
must still run their exact predicates and retain complete engineering owners.
"""
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
import math
import struct

from shapely import STRtree, to_wkb
from shapely.geometry import box

from .loaded_geometry import budget, geometry_checksum
from .store import canonical, digest

INDEX_BYTES = 32 * 1024**2
QUERY_BYTES = 4 * 1024**2
QUERY_ENTRIES = 1024
OVERLAY_ENTRIES = 128


def overlaps(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def bounds(shape):
    value = tuple(shape.bounds)
    if len(value) != 4 or not all(math.isfinite(x) for x in value):
        raise ValueError('SPATIAL_NONFINITE_OR_EMPTY_GEOMETRY')
    return value


@dataclass(frozen=True)
class Neighborhood:
    envelope: tuple
    members: tuple
    checksum: str
    weight: int


class SpatialQueries:
    """Fixed base plus small changed overlay; stable IDs survive rebuilding.

The caller owns immutable geometry and its byte validation. The index retains
references, bounded metadata, and conservative candidate lists only. Updating
an ID invalidates both reverse dependencies and query footprints intersecting
old OR new bounds, including previously empty neighborhoods. Rejected trial
rollback uses the same update path, never a special validity shortcut.
"""
    def __init__(self, geometries, *, context, versions=None, index_bytes=INDEX_BYTES,
                 query_bytes=QUERY_BYTES, query_entries=QUERY_ENTRIES,
                 overlay_entries=OVERLAY_ENTRIES, envelopes_only=False):
        self.context = context
        self.limits = tuple(budget(v, n) for v, n in (
            (index_bytes, 'index'), (query_bytes, 'queries'),
            (query_entries, 'query_entries'), (overlay_entries, 'overlay_entries')))
        self.envelopes_only = envelopes_only
        self.current = dict(geometries)
        self._check_capacity(len(self.current))
        self.boxes = {sid: bounds(g) for sid, g in self.current.items()}
        self.versions = ({sid: digest(to_wkb(g)) for sid, g in self.current.items()}
                         if versions is None else dict(versions))
        self.fingerprints = ({sid: geometry_checksum(g) for sid, g in self.current.items()}
                             if envelopes_only else {})
        if envelopes_only:
            self.current = {sid: box(*self.boxes[sid]) for sid in self.current}
        if self.versions.keys() != self.current.keys():
            raise ValueError('SPATIAL_VERSION_COVERAGE')
        self.tokens = {s: self._token(s, v) for s, v in self.versions.items()}
        self.context_token = bytes.fromhex(digest(canonical(context)))
        self.cache = OrderedDict()
        self.reverse = defaultdict(set)
        self.overlay = set()
        self.weight = 0
        self.peak = 0
        self.stats = Counter()
        self._rebuild()

    def _check_capacity(self, count):
        # Metadata + tree allowance; shared caller geometry is not duplicated.
        if count * 1024 > self.limits[0]:
            raise ValueError('SPATIAL_INDEX_BUDGET')

    def _rebuild(self):
        self.ids = tuple(sorted(self.current))
        self.tree = STRtree([self.current[s] for s in self.ids])
        self.overlay.clear()
        self.stats['index_builds'] += 1

    @staticmethod
    def _token(sid, version):
        return bytes.fromhex(digest(canonical([sid, version])))

    def _checksum(self, envelope, members):
        # Fixed-width SHA-256 member tokens bind full IDs and geometry versions.
        # Rehash the entire ordered membership on every hit. This avoids repeated
        # general JSON traversal of long source IDs without weakening the digest.
        if any(self.versions.get(s) != v for s, v in members):
            raise ValueError('SPATIAL_NEIGHBORHOOD_CORRUPTED')
        return digest(self.context_token + struct.pack('!4d', *envelope) +
                      b''.join(self.tokens[s] for s, _ in members))

    def _drop(self, key):
        item = self.cache.pop(key)
        self.weight -= item.weight
        for sid, _ in item.members:
            self.reverse[sid].discard(key)
            if not self.reverse[sid]:
                del self.reverse[sid]

    def query(self, shape):
        envelope = bounds(shape)
        self.stats['queries'] += 1
        item = self.cache.get(envelope)
        if item is not None:
            if (item.envelope != envelope or
                    self._checksum(envelope, item.members) != item.checksum):
                raise ValueError('SPATIAL_NEIGHBORHOOD_CORRUPTED')
            self.cache.move_to_end(envelope)
            self.stats['query_hits'] += 1
            return tuple(s for s, _ in item.members)
        # Changed/deleted base records are masked. New geometry can lie anywhere;
        # no maximum-growth assumption is used for overlay discovery.
        found = {self.ids[int(i)] for i in self.tree.query(shape)
                 if self.ids[int(i)] not in self.overlay}
        found.update(s for s in self.overlay if s in self.current and overlaps(envelope, self.boxes[s]))
        members = tuple((s, self.versions[s]) for s in sorted(found))
        self.stats['tree_queries'] += 1
        weight = 512 + sum(256 + len(s.encode()) + len(v.encode()) for s, v in members)
        if weight <= self.limits[1] and self.limits[2]:
            while self.cache and (self.weight + weight > self.limits[1] or len(self.cache) >= self.limits[2]):
                self._drop(next(iter(self.cache)))
                self.stats['evictions'] += 1
            self.cache[envelope] = Neighborhood(envelope, members, self._checksum(envelope, members), weight)
            self.weight += weight
            self.peak = max(self.peak, self.weight)
            for sid, _ in members:
                self.reverse[sid].add(envelope)
        return tuple(s for s, _ in members)

    def update(self, sid, shape):
        """Set or delete one source-bound geometry; validation precedes mutation."""
        old = self.boxes.get(sid)
        new = None if shape is None else bounds(shape)
        version = None if shape is None else digest(to_wkb(shape))
        self._check_capacity(len(self.current) + int(sid not in self.current and shape is not None))
        affected = set(self.reverse.get(sid, ()))
        for key in self.cache:
            if (old is not None and overlaps(key, old)) or (new is not None and overlaps(key, new)):
                affected.add(key)
        for key in affected:
            self._drop(key)
        self.stats['invalidated_queries'] += len(affected)
        self.stats['updates'] += 1
        if shape is None:
            self.current.pop(sid, None)
            self.boxes.pop(sid, None)
            self.versions.pop(sid, None)
            self.tokens.pop(sid, None)
            self.fingerprints.pop(sid, None)
        else:
            self.current[sid] = box(*new) if self.envelopes_only else shape
            self.boxes[sid] = new
            self.versions[sid] = version
            self.tokens[sid] = self._token(sid, version)
            if self.envelopes_only: self.fingerprints[sid] = geometry_checksum(shape)
        self.overlay.add(sid)
        if len(self.overlay) > self.limits[3]:
            self._rebuild()
        return len(affected)

    def validate_bindings(self, geometries, versions, *, context):
        """Pair with the caller's full byte validation at each verdict boundary."""
        if (context != self.context or self.current.keys() != geometries.keys() or
                self.versions != versions):
            raise ValueError('SPATIAL_INPUT_BINDING_CHANGED')
        if self.envelopes_only:
            if self.fingerprints != {s: geometry_checksum(g) for s, g in geometries.items()}:
                raise ValueError('SPATIAL_INPUT_BINDING_CHANGED')
            if any(bounds(g) != self.boxes[s] or
                   geometry_checksum(self.current[s]) != geometry_checksum(box(*self.boxes[s]))
                   for s, g in geometries.items()):
                raise ValueError('SPATIAL_INPUT_BINDING_CHANGED')
        elif any(self.current[s] is not g for s, g in geometries.items()):
            raise ValueError('SPATIAL_INPUT_BINDING_CHANGED')
        if (self.context_token != bytes.fromhex(digest(canonical(context))) or
                self.tokens != {s:self._token(s,v) for s,v in versions.items()}):
            raise ValueError('SPATIAL_TOKEN_BINDING_CHANGED')
        for i, sid in enumerate(self.ids):
            if sid not in self.overlay and self.tree.geometries[i] is not self.current.get(sid):
                raise ValueError('SPATIAL_INDEX_BINDING_CHANGED')

    def diagnostics(self):
        return dict(self.stats, query_estimated_bytes=self.weight, peak_query_estimated_bytes=self.peak,
                    query_entries=len(self.cache), dependency_edges=sum(map(len, self.reverse.values())),
                    overlay_entries=len(self.overlay), index_estimated_bytes=len(self.ids) * 1024,
                    limits=list(self.limits))

    def close(self):
        self.cache.clear()
        self.reverse.clear()
        self.current.clear()
        self.versions.clear()
        self.tokens.clear()
        self.boxes.clear()
        self.fingerprints.clear()
        self.overlay.clear()
        self.ids = ()
        self.tree = STRtree([])
        self.weight = 0
