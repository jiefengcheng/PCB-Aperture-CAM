"""Durable board preparation, not a treatment policy or acceptance cache.

One context owns immutable source and revision snapshots. Native trees stay in
their worker; exact ordered boundary runs survive reopening in checked files.
"""
from collections import Counter
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from types import MappingProxyType
import uuid

import shapely
from shapely import STRtree, from_wkb, to_wkb, get_precision, set_precision
from shapely.geometry import Polygon
from shapely.ops import unary_union

from src.original_copper_owners import OriginalOwners
from src.stage_abi.loaded_geometry import SNAPSHOT_BYTES

FORMAT = 'shared-copper-context/2'
LIMIT = 128 * 1024**2
ACTIVE = ContextVar('shared_copper_context', default=None)
ROOT = Path(__file__).resolve().parents[1]


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def geometry_key(g):
    return digest(encoded([digest(to_wkb(g, include_srid=True)), float(get_precision(g))]))


def polygon(g):
    if g.geom_type not in ('Polygon', 'MultiPolygon') or not g.is_valid:
        raise ValueError('SHARED_COPPER_VALID_ORDERED_MATERIAL_REQUIRED')
    return g


class LazyOwners(Mapping):
    """Exact alternate plotting views do not duplicate inactive owner geometry."""
    def __init__(self,context,entries):self.context=context;self.entries=dict(entries)
    def __len__(self):return len(self.entries)
    def __iter__(self):return iter(self.entries)
    def __getitem__(self,key):return self.context._load_geometry(self.entries[key])


class Revision:
    def __init__(self, context, key, values, owners, membership, parent=None, changes=None):
        self.context, self.key, self.parent = context, key, parent
        self.values = MappingProxyType(values)
        self.owners = owners if isinstance(owners,LazyOwners) else MappingProxyType(owners)
        self.membership = MappingProxyType({s: tuple(v) for s, v in membership.items()})
        self.changes = MappingProxyType(changes or {})
        grouped = {o: [] for o in owners}
        for s in values:
            for o in membership[s]: grouped[o].append(s)
        self.owner_sources = MappingProxyType({o: tuple(v) for o, v in grouped.items()})
        self._image = None
        self._stored_image = None
        self._tree = None

    def image(self):
        self.context._check()
        if self._image is None:
            if self._stored_image is not None:self._image=self.context._load_geometry(self._stored_image)
            else:
                self._image = polygon(unary_union(list(self.values.values())))
                self.context.stats['assembled_board_unions'] += 1
        return self._image

    def sources(self, window, *, predicate='intersects'):
        return self.context.sources(self, window, predicate=predicate)

    def owner(self, source_id):
        own = self.membership[source_id]
        if len(own) != 1:
            raise ValueError('ONE_PHYSICAL_BOUNDARY_OWNER_REQUIRED')
        return own[0], self.owners[own[0]]


class CopperContext:
    """A single explicitly owned, bounded context per loaded board.

    Callers pass composed, ordered positive contributions AFTER Gerber polarity
    evaluation. The frame and ordered-source binding are mandatory; this module
    never guesses a layer, merges boards or interprets Gerber operations.
    """
    def __init__(self, original, *, source_binding, frame, root=None, limit=LIMIT, geometry_limit=SNAPSHOT_BYTES, role='cleanup'):
        if not original or not source_binding or not frame or frame.get('units') != 'mm':
            raise ValueError('SHARED_COPPER_SOURCE_AND_FRAME_REQUIRED')
        if type(limit) is not int or limit <= 0 or limit > LIMIT:
            raise ValueError('SHARED_COPPER_MEMORY_BUDGET_INVALID')
        if type(geometry_limit) is not int or geometry_limit <= 0 or geometry_limit > SNAPSHOT_BYTES:
            raise ValueError('SHARED_COPPER_GEOMETRY_BUDGET_INVALID')
        if role not in ('cleanup','native-stage'):raise ValueError('SHARED_COPPER_ROLE_INVALID')
        from src.cleanup_runtime import workspace_root
        workspace = workspace_root()
        self.root = Path(root or workspace / 'shared_copper_context').resolve()
        if not self.root.is_relative_to(workspace):
            raise ValueError('SHARED_COPPER_LACIE_WORKSPACE_REQUIRED')
        self.limit, self.weight, self.closed = limit, 0, False
        self.geometry_limit,self.geometry_weight=geometry_limit,0
        self.stats = Counter()
        self.lock = threading.RLock()
        self.shapes, self.revisions = {}, {}
        from src.indexed_polygon_distance import BoundaryPreparation
        self.boundary_preparation = BoundaryPreparation(self)
        self.native_engine = None
        self.ids = tuple(original)
        self.ordinal = {s: i for i, s in enumerate(self.ids)}
        for g in original.values(): polygon(g)
        self.binding = dict(format=FORMAT, source=source_binding, frame=frame,
                            kernel=dict(shapely=shapely.__version__, geos=shapely.geos_version_string),
                            ordered_sources=[[s, geometry_key(g)] for s, g in original.items()])
        self.key = digest(encoded(self.binding))
        self.directory = self.root / self.key
        self.directory.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        cold_owner_index=None
        with self._publication_lock():
            path = self.directory / 'source.json.gz'
            if path.exists():
                record = self._read(path)
                if record['binding'] != self.binding:
                    raise ValueError('SHARED_COPPER_SOURCE_BINDING_CHANGED')
                revision = self._restore(record, original,lazy_owners=role=='native-stage')
                self.stats['source_warm_loads'] += 1
            else:
                # Source GEOS geometry is already owned by the stage snapshot.
                # Borrow it; do not allocate a second native copy or charge an
                # unrelated WKB-handle estimate as extra index memory.
                values = {s: self._retain(g, borrowed=True) for s, g in original.items()}
                image = polygon(unary_union(list(values.values())))
                self.stats['source_board_unions'] += 1
                own = OriginalOwners(image)
                cold_owner_index=own
                self.stats['owner_preparations'] += 1
                revision = Revision(self, self.key, values,
                                    {o: self._retain(g) for o, g in zip(own.ids, own.owners)},
                                    own.memberships(values))
                revision._image = image
                # The context already stores authenticated source identities;
                # do not retain a second full WKB batch solely for a donor memo.
                del own._source_memberships
                self._write(path, self._record(revision, binding=self.binding))
                self.stats['source_cold_preparations'] += 1
        self.source = revision
        if role=='native-stage':
            record=self._read(self.directory/'source.json.gz')
            revision.owners=LazyOwners(self,record['owners']);revision._image=None;revision._stored_image=record['image']
            borrowed={k for _,k in self.binding['ordered_sources']}
            self.shapes={k:g for k,g in self.shapes.items() if k in borrowed}
            self.geometry_weight=128*len(self.shapes)
            self.owner_index=None;self.owner_partitions={};self.partition_memberships={}
        else:
            self.owner_index=cold_owner_index or OriginalOwners.from_prepared(revision.image(),list(revision.owners.values()),list(revision.owners))
            self.owner_partitions={geometry_key(self.owner_index.source):self.owner_index}
            self.partition_memberships={geometry_key(self.owner_index.source):dict(revision.membership)}
        self.revisions[revision.key] = revision
        self._charge(len(self.ids) * 1024 + 512)
        self.source_tree = STRtree(list(revision.values.values()))
        self.stats['source_index_builds'] += 1
        self.stats['preparation_microseconds'] += round((time.perf_counter() - started) * 1e6)

    def _check(self):
        if self.closed: raise ValueError('SHARED_COPPER_CONTEXT_CLOSED')

    def _charge(self, weight):
        if self.weight + weight > self.limit:
            raise ValueError('SHARED_COPPER_RESIDENT_CAPACITY_EXCEEDED')
        self.weight += weight
        self.stats['peak_retained_bytes'] = max(self.stats['peak_retained_bytes'], self.weight)

    def _charge_geometry(self, weight):
        # Preserve the existing geometry-snapshot and indexed-distance budgets
        # separately. Original stage geometry is borrowed, never copied here.
        if self.geometry_weight+weight>self.geometry_limit:
            raise ValueError('SHARED_COPPER_GEOMETRY_CAPACITY_EXCEEDED')
        self.geometry_weight+=weight
        self.stats['peak_geometry_bytes']=max(self.stats['peak_geometry_bytes'],self.geometry_weight)

    @contextmanager
    def _publication_lock(self):
        with (self.directory / '.publication.lock').open('a+b') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(stream, fcntl.LOCK_UN)

    def _read(self, path):
        try:
            envelope = json.loads(gzip.decompress(path.read_bytes()))
            value = envelope['value']
            if envelope['sha256'] != digest(encoded(value)) or value['format'] != FORMAT:
                raise ValueError('checksum')
            return value
        except Exception as exc:
            raise ValueError('SHARED_COPPER_CORRUPT_ENTRY:' + str(path)) from exc

    def _write(self, path, value):
        value = dict(value, format=FORMAT)
        data = gzip.compress(encoded(dict(sha256=digest(encoded(value)), value=value)), mtime=0)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.pending')
        with temporary.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)

    def _retain(self, g, *, borrowed=False):
        key = geometry_key(g)
        if key not in self.shapes:
            self._charge_geometry(128 if borrowed else 3 * len(to_wkb(g, include_srid=True)) + int(shapely.get_num_coordinates(g))*24 + 1024)
            self.shapes[key] = g
        return self.shapes[key]

    def _geometry(self, g):
        self._retain(g)
        key = geometry_key(g)
        path = self.directory / 'geometry' / (key + '.json.gz')
        if path.exists(): self._load_geometry(key,g)
        else: self._write(path, dict(key=key, wkb=to_wkb(g, include_srid=True).hex(), precision=float(get_precision(g))))
        return key

    def _load_geometry(self, key, known=None):
        r = self._read(self.directory / 'geometry' / (key + '.json.gz'))
        if known is not None:
            if (r['key'] != key or geometry_key(known) != key or
                    r['wkb'] != to_wkb(known,include_srid=True).hex() or r['precision'] != float(get_precision(known))):
                raise ValueError('SHARED_COPPER_GEOMETRY_BINDING_CHANGED')
            return self._retain(known,borrowed=True)
        g = from_wkb(bytes.fromhex(r['wkb']))
        if r['precision']: g = set_precision(g, r['precision'], mode='pointwise')
        if r['key'] != key or geometry_key(g) != key:
            raise ValueError('SHARED_COPPER_GEOMETRY_BINDING_CHANGED')
        return self._retain(g)

    def _record(self, revision, **extra):
        return dict(key=revision.key, parent=revision.parent,
                    sources=[[s, self._geometry(g)] for s, g in revision.values.items()],
                    owners=[[o, self._geometry(g)] for o, g in revision.owners.items()],
                    membership=dict(revision.membership), changes=dict(revision.changes),
                    image=self._geometry(revision._image) if revision._image is not None else None, **extra)

    def _restore(self, record, values=None,*,lazy_owners=False):
        sources = {s: self._load_geometry(k,None if values is None else values[s]) for s, k in record['sources']}
        if tuple(sources) != self.ids:
            raise ValueError('SHARED_COPPER_ORDER_CHANGED')
        if values is not None and any(geometry_key(values[s]) != geometry_key(g) for s, g in sources.items()):
            raise ValueError('SHARED_COPPER_REVISION_BINDING_CHANGED')
        revision=Revision(self, record['key'], sources,
                        LazyOwners(self,record['owners']) if lazy_owners else {o: self._load_geometry(k) for o, k in record['owners']},
                        record['membership'], record['parent'], record['changes'])
        if record.get('image'):
            if lazy_owners:revision._stored_image=record['image']
            else:revision._image=self._load_geometry(record['image'])
        return revision

    def original_owner_index(self,source):
        key=geometry_key(source)
        if key in self.owner_partitions:
            self.stats['original_owner_index_hits']+=1
            return self.owner_partitions[key]
        # The native stage's raw-source plotting and an admitted source scene
        # can use different exact boundary tessellations. Reuse the existing
        # OriginalOwners construct per exact operand, never equate them by an
        # area/coordinate tolerance or substitute the cleanup representation.
        with self.lock,self._publication_lock():
            path=self.directory/'owner_partitions'/(key+'.json.gz')
            if path.exists():
                record=self._read(path)
                if record['source']!=key:raise ValueError('SHARED_COPPER_OWNER_PARTITION_CHANGED')
                index=OriginalOwners.from_prepared(source,
                    [self._load_geometry(k) for _,k in record['owners']],
                    [o for o,_ in record['owners']])
                membership=record['membership']
                if tuple(membership)!=tuple(sorted(self.ids)) or any(o not in index.ids for v in membership.values() for o in v):
                    raise ValueError('SHARED_COPPER_OWNER_MEMBERSHIP_CHANGED')
                if not unary_union(index.owners).equals(source):
                    raise ValueError('SHARED_COPPER_OWNER_MATERIAL_CHANGED')
                self.stats['owner_partition_validation_unions']+=1
                for g in index.owners:
                    if len(index.tree.query(g,predicate='intersects'))!=1:
                        raise ValueError('SHARED_COPPER_OWNER_PARTITION_OVERLAP')
                    if g.geom_type=='MultiPolygon' and len(OriginalOwners(g).owners)!=1:
                        raise ValueError('SHARED_COPPER_DISCONNECTED_OWNER')
                if any(index.membership(g)!=membership[s] for s,g in self.source.values.items()):
                    raise ValueError('SHARED_COPPER_OWNER_MEMBERSHIP_CHANGED')
                self.stats['owner_partition_membership_checks']+=len(self.ids)
                self.stats['owner_partition_warm_loads']+=1
            else:
                index=OriginalOwners(source)
                membership=index.memberships(self.source.values)
                del index._source_memberships
                self._write(path,dict(source=key,owners=[[o,self._geometry(g)]for o,g in zip(index.ids,index.owners)],
                                      membership=membership))
                self.stats['owner_partition_cold_preparations']+=1
            self.owner_partitions[key]=index
            self.partition_memberships[key]=membership
            return index

    def original_memberships(self,originals,partition=None):
        if (tuple(originals)!=self.ids or any(geometry_key(g)!=geometry_key(self.source.values[s]) for s,g in originals.items())):
            return None
        if partition is None and self.owner_index is None:
            self.owner_index=OriginalOwners.from_prepared(self.source.image(),list(self.source.owners.values()),list(self.source.owners))
            key=geometry_key(self.owner_index.source);self.partition_memberships[key]=dict(self.source.membership)
            self.owner_partitions[key]=self.owner_index
        partition=self.owner_index if partition is None else partition
        membership=self.partition_memberships.get(geometry_key(partition.source))
        if membership is None:return None
        self.stats['original_membership_batch_hits']+=1
        return {s:list(membership[s]) for s in originals}

    def acquire(self, changes=None, *, parent=None):
        """Publish a batch; unchanged owners and source index remain shared."""
        self._check()
        parent = self.source if parent is None else parent
        if parent.context is not self: raise ValueError('SHARED_COPPER_FOREIGN_REVISION')
        changes = dict(changes or {})
        if not changes.keys() <= parent.values.keys():
            raise ValueError('SHARED_COPPER_SOURCE_INVENTORY_CHANGED')
        changes = {s: polygon(g) for s, g in changes.items() if geometry_key(g) != geometry_key(parent.values[s])}
        if not changes: return parent
        values = dict(parent.values); values.update(changes)
        key = digest(encoded([self.key, [[s, geometry_key(g)] for s, g in values.items()]]))
        if key in self.revisions: return self.revisions[key]
        with self.lock, self._publication_lock():
            path = self.directory / 'revisions' / (key + '.json.gz')
            if path.exists():
                record = self._read(path)
                if record['key'] != key: raise ValueError('SHARED_COPPER_REVISION_KEY_CHANGED')
                result = self._restore(record, values)
                self.stats['revision_warm_loads'] += 1
            else:
                affected = set(o for s in changes for o in parent.membership[s])
                # Complete owners touching new copper are included: growth can
                # cross an old envelope or merge previously separate owners.
                for g in changes.values():
                    for o, body in parent.owners.items():
                        if body.intersects(g): affected.add(o)
                affected_sources = set(changes)
                pending=list(affected)
                while pending:
                    for s in parent.owner_sources[pending.pop()]:
                        affected_sources.add(s)
                        for o in parent.membership[s]:
                            if o not in affected:affected.add(o);pending.append(o)
                local = {s: values[s] for s in self.ids if s in affected_sources}
                image = polygon(unary_union(list(local.values())))
                self.stats['affected_owner_unions'] += 1
                owners = {o: g for o, g in parent.owners.items() if o not in affected}
                membership = dict(parent.membership)
                if image.is_empty:
                    membership.update({s: () for s in local})
                else:
                    partition = OriginalOwners(image)
                    self.stats['owner_preparations'] += 1
                    owners.update({o: self._retain(g) for o, g in zip(partition.ids, partition.owners)})
                    membership.update(partition.memberships(local))
                delta = {s: dict(before=geometry_key(parent.values[s]), after=geometry_key(g),
                                 removed=self._geometry(parent.values[s].difference(g)),
                                 added=self._geometry(g.difference(parent.values[s]))) for s, g in changes.items()}
                result = Revision(self, key, {s: self._retain(g,borrowed=True) for s, g in values.items()}, owners, membership, parent.key, delta)
                self._write(path, self._record(result))
                self.stats['revision_cold_preparations'] += 1
            self.revisions[key] = result
            return result

    def sources(self, revision, window, *, predicate='intersects'):
        self._check()
        if revision.context is not self: raise ValueError('SHARED_COPPER_FOREIGN_REVISION')
        if predicate not in (None, 'intersects'):
            raise ValueError('SHARED_COPPER_UNSUPPORTED_SOURCE_QUERY')
        if revision._tree is None:
            changed = tuple(s for s in self.ids if revision.values[s] is not self.source.values[s])
            tree = None
            if changed:
                self._charge(len(changed)*1024+512)
                tree = STRtree([revision.values[s] for s in changed])
                self.stats['revision_overlay_index_builds'] += 1
            revision._tree = (changed, set(changed), tree)
        changed, tombstones, tree = revision._tree
        hits = {self.ids[int(i)] for i in self.source_tree.query(window, predicate=predicate)} - tombstones
        if tree is not None: hits.update(changed[int(i)] for i in tree.query(window, predicate=predicate))
        self.stats['source_queries'] += 1
        return tuple(sorted(hits, key=self.ordinal.__getitem__))

    def boundary_index(self, shape):
        """Delegate to the EXISTING shared T02/T05 boundary implementation."""
        self._check()
        return self.boundary_preparation.index(shape)

    def boundary_sections(self, shape, window):
        """Ordered complete runs; never clip, simplify or reverse source edges."""
        tree,parts=self.boundary_index(shape)
        indices=tuple(sorted(map(int,tree.query(window))))
        return tuple((i,parts[i]) for i in indices)

    def boundary_adjacency(self,shape):
        from src.indexed_polygon_distance import boundary_rings
        return {first+i:dict(previous=first+(i-1)%count,next=first+(i+1)%count,
                             polygon=r['polygon'],ring=r['ring'])
                for r in boundary_rings(shape) for first,count in [(r['first'],r['count'])] for i in range(count)}

    def validate(self):
        """Integrity at a batch/stage boundary, not a full rehash per query."""
        self._check()
        self.boundary_preparation.validate()

    def engine(self):
        self._check()
        if self.native_engine is None:
            from src.indexed_polygon_distance import Engine
            self.native_engine=Engine(owner=self)
        return self.native_engine

    @contextmanager
    def activate(self):
        self._check()
        token = ACTIVE.set(self)
        try:
            yield self
            self.validate()
        finally: ACTIVE.reset(token)

    def diagnostics(self):
        return dict(self.stats, context=self.key, retained_bytes=self.weight, limit_bytes=self.limit,
                    geometry_retained_bytes=self.geometry_weight,geometry_limit_bytes=self.geometry_limit,
                    borrowed_source_coordinates=sum(int(shapely.get_num_coordinates(g)) for g in self.source.values.values()),
                    revisions=len(self.revisions), native_indexes_process_local=True)

    def close(self):
        for revision in self.revisions.values(): revision._tree=None;revision._image=None
        if hasattr(self,'pad_fill_preparation'):self.pad_fill_preparation.clear()
        self.boundary_preparation.close(); self.shapes.clear(); self.revisions.clear()
        if self.native_engine is not None:self.native_engine.close();self.native_engine=None
        self.source_tree = None
        self.owner_index=None
        self.owner_partitions.clear();self.partition_memberships.clear()
        self.source = None
        self.closed = True

    def __enter__(self): return self
    def __exit__(self, *args): self.close()


def for_board(original, **kwargs):
    """Match source-bound stage and cleanup contexts without filename identity."""
    sources={s.split(':',1)[0] for s in original}
    if len(sources)==1 and len(next(iter(sources)))==64:
        binding=dict(source_sha256=next(iter(sources)))
        frame=dict(units='mm',axes='X_RIGHT_Y_DOWN',layer='SOURCE_BOUND_COPPER')
    else:
        binding=dict(kind='ORDERED_SOURCE_CONTRIBUTIONS')
        frame=dict(units='mm',axes='SOURCE_NATIVE')
    return CopperContext(original,source_binding=binding,frame=frame,**kwargs)
