"""Bounded geometry reuse over immutable, byte-revalidated scene operands.

Geometric constructions and separately typed measurements are memoized. Callers still evaluate every policy
predicate and perform complete ordered final assembly. Cache estimates bound
retained objects, not transient GEOS allocations or the process allocator.
"""
from collections import Counter, OrderedDict
from dataclasses import dataclass
import weakref

from shapely import from_wkb, to_wkb
from shapely.geometry import box
from shapely.ops import unary_union

from .contracts import fail
from .store import digest

SNAPSHOT_BYTES = 192 * 1024**2
MEMO_BYTES = 32 * 1024**2
MEMO_ENTRIES = 8192
SIGNATURE_ENTRIES = 32768


def budget(value, name):
    if type(value) is not int or value < 0:
        raise ValueError('LOADED_GEOMETRY_INVALID_BUDGET:' + name)
    return value


def valid(shape):
    if shape.is_empty or not shape.is_valid or shape.geom_type not in ('Polygon', 'MultiPolygon'):
        fail('GEOMETRY_INVALID', 'finite valid filled copper required')
    return shape


class GeometrySnapshot:
    """One versioned source snapshot with deduplicated immutable decoded shapes.

    Every geometry access still reads and hashes its actual artifact bytes via
    the store. Original/current maps preserve source order and separate identity.
    No artifact-byte cache or identity-only validity shortcut is introduced.
    """
    def __init__(self, store, scene, *, limit=SNAPSHOT_BYTES):
        self.limit = budget(limit, 'snapshot')
        self.shapes = {}
        self.weight = 0
        self.peak = 0
        self.stats = Counter()
        self.objects = {r['source_id']: r for r in scene['objects']}
        self._charge(256 * len(self.objects))
        try:
            self.current = {s: self.geometry(store, r['geometry_ref']) for s, r in self.objects.items()}
            self.original = {s: self.geometry(store, r['original_ref']) for s, r in self.objects.items()}
            self.crop = box(*scene['viewport_mm'])
        except BaseException:
            self.close()
            raise

    def _charge(self, amount):
        if self.weight + amount > self.limit:
            raise ValueError('LOADED_GEOMETRY_SNAPSHOT_BUDGET')
        self.weight += amount
        self.peak = max(self.peak, self.weight)

    def geometry(self, store, reference):
        body = store.get(reference, kind='geometry')
        key = reference['sha256']
        self.stats['artifact_accesses'] += 1
        if key not in self.shapes:
            self._charge(2 * len(body) + 512)
            try:
                shape = valid(from_wkb(body))
                self.shapes[key] = (shape, digest(to_wkb(shape)))
            except (TypeError, ValueError) as error:
                fail('GEOMETRY_INVALID', str(error))
            self.stats['decodes'] += 1
        else:
            self.stats['decode_reuses'] += 1
        shape, expected = self.shapes[key]
        if digest(to_wkb(shape)) != expected:
            raise ValueError('LOADED_GEOMETRY_SNAPSHOT_CORRUPTED')
        # Preserve the original geometry validation even on a decoded-shape hit.
        return valid(shape)

    def retain_derived(self, shape):
        self._charge(2 * len(to_wkb(shape)) + 512)
        return shape

    def composed(self, store, scene):
        # Identical full operand order and clipping; no source/view pruning.
        return unary_union([self.geometry(store, r['geometry_ref']) for r in scene['objects']]).intersection(box(*scene['viewport_mm']))

    def diagnostics(self):
        return dict(self.stats, resident_estimated_bytes=self.weight,
                    peak_estimated_bytes=self.peak, limit_bytes=self.limit,
                    resident_geometry_entries=len(self.shapes))

    def validate_bindings(self):
        if self.current.keys() != self.objects.keys() or self.original.keys() != self.objects.keys():
            raise ValueError('LOADED_GEOMETRY_SNAPSHOT_BINDING_CHANGED')
        checked = set()
        for sid, row in self.objects.items():
            for name, view in (('geometry_ref', self.current), ('original_ref', self.original)):
                key = row[name]['sha256']
                entry = self.shapes.get(key)
                if entry is None or view[sid] is not entry[0]:
                    raise ValueError('LOADED_GEOMETRY_SNAPSHOT_BINDING_CHANGED')
                if key not in checked:
                    if digest(to_wkb(entry[0])) != entry[1]:
                        raise ValueError('LOADED_GEOMETRY_SNAPSHOT_CORRUPTED')
                    checked.add(key)

    def close(self):
        self.shapes.clear()
        self.current = {}
        self.original = {}
        self.objects = {}
        self.weight = 0


@dataclass(frozen=True)
class GeometryEntry:
    value: object
    sha256: str
    weight: int


@dataclass(frozen=True)
class MeasurementEntry:
    value: bool
    sha256: str
    weight: int


class GeometryMemo:
    """Operation-local LRU of exact ordered geometric constructions.

    Keys bind the operation's complete context plus operand WKB and parameters.
    Weak signature records never retain an otherwise dead operand. Their entry
    count is bounded independently. Eviction means recomputation, never a waiver.
    """
    def __init__(self, binding, *, limit=MEMO_BYTES, entries=MEMO_ENTRIES,
                 signatures=SIGNATURE_ENTRIES):
        self.binding = binding
        self.limit = budget(limit, 'memo')
        self.max_entries = budget(entries, 'entries')
        self.max_signatures = budget(signatures, 'signatures')
        self.values = OrderedDict()
        self.signatures = OrderedDict()
        self.weight = 0
        self.peak = 0
        self.stats = Counter()

    def token(self, shape):
        sid = id(shape)
        old = self.signatures.get(sid)
        if old is not None and old[0]() is shape:
            self.signatures.move_to_end(sid)
            return old[1]
        h = digest(to_wkb(shape))
        if self.max_signatures:
            def expired(ref, key=sid):
                current = self.signatures.get(key)
                if current is not None and current[0] is ref:
                    self.signatures.pop(key, None)
            self.signatures[sid] = (weakref.ref(shape, expired), h)
            self.signatures.move_to_end(sid)
            while len(self.signatures) > self.max_signatures:
                self.signatures.popitem(last=False)
        return h

    def construct(self, name, operands, parameters, fn):
        key = (self.binding, name, tuple(self.token(g) for g in operands), parameters)
        old = self.values.get(key)
        self.stats['requests'] += 1
        if old is not None:
            if digest(to_wkb(old.value)) != old.sha256:
                raise ValueError('LOADED_GEOMETRY_CACHE_CORRUPTED')
            self.values.move_to_end(key)
            self.stats['hits'] += 1
            self.stats['hits_' + name] += 1
            return old.value
        value = fn()
        self.stats['builds'] += 1
        self.stats['builds_' + name] += 1
        blob = to_wkb(value)
        weight = 2 * len(blob) + 512 + len(repr(key))
        if weight <= self.limit and self.max_entries:
            while self.values and (self.weight + weight > self.limit or
                                   len(self.values) >= self.max_entries):
                _, entry = self.values.popitem(last=False)
                self.weight -= entry.weight
                self.stats['evictions'] += 1
            self.values[key] = GeometryEntry(value, digest(blob), weight)
            self.weight += weight
            self.peak = max(self.peak, self.weight)
        else:
            self.stats['not_retained'] += 1
        return value

    def difference_empty(self, left, right):
        # This is a geometry measurement, not an owner/permission or stage verdict.
        # Retain its scalar witness instead of a large, otherwise unused polygon.
        key = (self.binding, 'measurement:difference_empty',
               (self.token(left), self.token(right)), ())
        old = self.values.get(key)
        self.stats['measurement_requests'] += 1
        if old is not None:
            if not isinstance(old, MeasurementEntry) or type(old.value) is not bool or digest(str(old.value).encode()) != old.sha256:
                raise ValueError('LOADED_GEOMETRY_MEASUREMENT_CORRUPTED')
            self.values.move_to_end(key)
            self.stats['measurement_hits'] += 1
            return old.value
        value = bool(left.difference(right).is_empty)
        self.stats['measurement_builds'] += 1
        weight = 512 + len(repr(key))
        if weight <= self.limit and self.max_entries:
            while self.values and (self.weight + weight > self.limit or len(self.values) >= self.max_entries):
                _, entry = self.values.popitem(last=False)
                self.weight -= entry.weight
                self.stats['evictions'] += 1
            self.values[key] = MeasurementEntry(value, digest(str(value).encode()), weight)
            self.weight += weight
            self.peak = max(self.peak, self.weight)
        else:
            self.stats['not_retained'] += 1
        return value

    def buffer(self, shape, radius, *, quad_segs=64):
        return self.construct('buffer', [shape], (radius, quad_segs),
                              lambda: shape.buffer(radius, quad_segs=quad_segs))

    def difference(self, left, right):
        return self.construct('difference', [left, right], (), lambda: left.difference(right))

    def intersection(self, left, right):
        return self.construct('intersection', [left, right], (), lambda: left.intersection(right))

    def union(self, left, right):
        return self.construct('union', [left, right], (), lambda: left.union(right))

    def symmetric_difference(self, left, right):
        return self.construct('symmetric_difference', [left, right], (), lambda: left.symmetric_difference(right))

    def diagnostics(self):
        return dict(self.stats, resident_estimated_bytes=self.weight,
                    peak_estimated_bytes=self.peak, limit_bytes=self.limit,
                    resident_entries=len(self.values), entry_limit=self.max_entries,
                    signature_entries=len(self.signatures), signature_limit=self.max_signatures)

    def close(self):
        self.values.clear()
        self.signatures.clear()
        self.weight = 0
