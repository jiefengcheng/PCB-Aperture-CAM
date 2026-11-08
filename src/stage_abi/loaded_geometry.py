"""Bounded geometry reuse over immutable, byte-revalidated scene operands.

Geometric constructions and separately typed measurements are memoized. Callers still evaluate every policy
predicate and perform complete ordered final assembly. Cache estimates bound
retained objects, not transient GEOS allocations or the process allocator.
"""
from collections import Counter, OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
import weakref,struct

from shapely import from_wkb, to_wkb, get_precision
from shapely.geometry import box
from shapely.ops import unary_union

from .contracts import fail
from .store import digest

SNAPSHOT_BYTES = 192 * 1024**2
MEMO_BYTES = 32 * 1024**2
MEMO_ENTRIES = 8192
SIGNATURE_ENTRIES = 32768


def geometry_checksum(shape):
    return digest(to_wkb(shape,include_srid=True)+struct.pack('!d',get_precision(shape)))


def budget(value, name):
    if type(value) is not int or value < 0:
        raise ValueError('LOADED_GEOMETRY_INVALID_BUDGET:' + name)
    return value


def valid(shape):
    if shape.is_empty or not shape.is_valid or shape.geom_type not in ('Polygon', 'MultiPolygon'):
        fail('GEOMETRY_INVALID', 'finite valid filled copper required')
    return shape


class OperandView(Mapping):
    """Source-order operands; optional decoded shapes live only in the LRU."""
    def __init__(self, snapshot, store, field, pinned):
        self.snapshot, self.store, self.field = snapshot, store, field
        self.pinned = pinned
        self.ids = tuple(snapshot.objects)

    def __iter__(self): return iter(self.ids)
    def __len__(self): return len(self.ids)

    def __getitem__(self, sid):
        s = self.snapshot
        if s.closed: raise ValueError('LOADED_GEOMETRY_SNAPSHOT_CLOSED')
        aid, sha = s.bindings[sid, self.field]
        ref = dict(artifact_id=aid, sha256=sha)
        if s.objects[sid][self.field] != ref:
            raise ValueError('LOADED_GEOMETRY_SNAPSHOT_BINDING_CHANGED')
        if sid in self.pinned: return self.pinned[sid]
        return s.geometry(self.store, ref)


class GeometrySnapshot:
    """One versioned source snapshot with deduplicated immutable decoded shapes.

    Every geometry access still reads and hashes its actual artifact bytes via
    the store. Original/current maps preserve source order and separate identity.
    No artifact-byte cache or identity-only validity shortcut is introduced.
    """
    def __init__(self, store, scene, *, limit=SNAPSHOT_BYTES, bounded_operands=False, pin_current=True):
        self.limit = budget(limit, 'snapshot')
        self.shapes = {}
        self.optional = OrderedDict()
        self.optional_weight = 0
        self.external_reserved = 0
        self.bounded_operands = bounded_operands
        self.closed = False
        self.weight = 0
        self.peak = 0
        self.stats = Counter()
        self.objects = {r['source_id']: r for r in scene['objects']}
        self.bindings = MappingProxyType({(s, field): (r[field]['artifact_id'], r[field]['sha256'])
            for s, r in self.objects.items() for field in ('geometry_ref', 'original_ref')})
        # Eager spatial callers may pin physical current surfaces. Envelope-only
        # callers can decode every operand on demand without losing any source
        # occurrence, artifact check, ordering or final composition operand.
        self.pinned_keys = ({r['geometry_ref']['sha256'] for r in scene['objects'] if r['kind'] != 'trace'} if pin_current else set()) if bounded_operands else None
        self._charge(256 * len(self.objects))
        try:
            if bounded_operands:
                pinned_current, pinned_original = {}, {}
                # Validate every input, even operands that no selected route
                # eventually uses. Optional entries may be evicted, never skipped.
                for s, r in self.objects.items():
                    shape = self.geometry(store, r['geometry_ref'])
                    if r['geometry_ref']['sha256'] in self.pinned_keys: pinned_current[s] = shape
                for s, r in self.objects.items():
                    shape = self.geometry(store, r['original_ref'])
                    if r['original_ref']['sha256'] in self.pinned_keys: pinned_original[s] = shape
                self.current = OperandView(self, store, 'geometry_ref', pinned_current)
                self.original = OperandView(self, store, 'original_ref', pinned_original)
                self.views = (self.current, self.original)
            else:
                self.current = {s: self.geometry(store, r['geometry_ref']) for s, r in self.objects.items()}
                self.original = {s: self.geometry(store, r['original_ref']) for s, r in self.objects.items()}
            self.crop = box(*scene['viewport_mm'])
        except BaseException:
            self.close()
            raise

    def _charge(self, amount):
        self._evict_for(amount)
        if self.weight + amount + self.external_reserved > self.limit:
            raise ValueError('LOADED_GEOMETRY_SNAPSHOT_BUDGET')
        self.weight += amount
        self.peak = max(self.peak, self.weight)

    def _evict_for(self, amount):
        while self.optional and self.weight + amount + self.external_reserved > self.limit:
            _, (_, _, size) = self.optional.popitem(last=False)
            self.weight -= size
            self.optional_weight -= size
            self.stats['optional_evictions'] += 1

    def reserve_external(self, amount):
        """Partition this same budget with the owner's decoded-surface LRU."""
        amount = budget(amount, 'external-reservation')
        base = self.weight - self.optional_weight
        if base + amount > self.limit:
            raise ValueError('LOADED_GEOMETRY_SNAPSHOT_BUDGET')
        self.external_reserved = amount
        self._evict_for(0)

    def optional_capacity(self):
        return self.limit - (self.weight - self.optional_weight) - self.external_reserved

    def geometry(self, store, reference):
        body = store.get(reference, kind='geometry')
        key = reference['sha256']
        self.stats['artifact_accesses'] += 1
        cached = self.shapes.get(key)
        if cached is None and key in self.optional:
            shape, expected, _ = self.optional[key]
            cached = (shape, expected)
            self.optional.move_to_end(key)
        if cached is None:
            size = 2 * len(body) + 512
            pinned = not self.bounded_operands or key in self.pinned_keys
            if pinned: self._charge(size)
            try:
                from .preparation import decode_geometry
                shape = valid(decode_geometry(body))
                cached = (shape, geometry_checksum(shape))
            except (TypeError, ValueError) as error:
                fail('GEOMETRY_INVALID', str(error))
            if pinned:
                self.shapes[key] = cached
            elif size <= self.optional_capacity():
                self._charge(size)
                self.optional[key] = (*cached, size)
                self.optional_weight += size
            else:
                self.stats['optional_not_retained'] += 1
            self.stats['decodes'] += 1
        else:
            self.stats['decode_reuses'] += 1
        shape, expected = cached
        if geometry_checksum(shape) != expected:
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
                    resident_geometry_entries=len(self.shapes) + len(self.optional),
                    optional_resident_estimated_bytes=self.optional_weight,
                    optional_entries=len(self.optional), external_reserved_bytes=self.external_reserved)

    def validate_bindings(self):
        if self.current.keys() != self.objects.keys() or self.original.keys() != self.objects.keys():
            raise ValueError('LOADED_GEOMETRY_SNAPSHOT_BINDING_CHANGED')
        if self.bounded_operands and (self.current is not self.views[0] or self.original is not self.views[1]):
            raise ValueError('LOADED_GEOMETRY_SNAPSHOT_BINDING_CHANGED')
        checked = set()
        for sid, row in self.objects.items():
            for name, view in (('geometry_ref', self.current), ('original_ref', self.original)):
                if (row[name]['artifact_id'], row[name]['sha256']) != self.bindings[sid, name]:
                    raise ValueError('LOADED_GEOMETRY_SNAPSHOT_BINDING_CHANGED')
                key = row[name]['sha256']
                if self.bounded_operands and key not in self.pinned_keys:
                    # The LRU may have evicted this input. Re-read its exact
                    # bytes and validate the decoded geometry independently.
                    self.geometry(view.store, row[name])
                    continue
                entry = self.shapes.get(key)
                if entry is None or view[sid] is not entry[0]:
                    raise ValueError('LOADED_GEOMETRY_SNAPSHOT_BINDING_CHANGED')
                if key not in checked:
                    if geometry_checksum(entry[0]) != entry[1]:
                        raise ValueError('LOADED_GEOMETRY_SNAPSHOT_CORRUPTED')
                    checked.add(key)

    def close(self):
        self.shapes.clear()
        self.optional.clear()
        self.optional_weight = 0
        self.external_reserved = 0
        self.closed = True
        for view in getattr(self, 'views', ()):
            view.pinned.clear()
        self.views = ()
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
        h = geometry_checksum(shape)
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
            if geometry_checksum(old.value) != old.sha256:
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
            self.values[key] = GeometryEntry(value, geometry_checksum(value), weight)
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
