"""Opt-in, byte-bound reuse of admitted Gerber plotting objects.

This is a construction cache, never a clearance/connectivity verdict cache.
The caller still reads and validates its source binding on every invocation.
Only the complete, successful legacy_export.parse result can populate an entry.
Objects are decoded afresh on hits, so downstream mutation cannot poison reuse.
No pickle, dynamic class lookup, quantization or geometry composition is used.
"""
from array import array
from dataclasses import fields
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import stat
import struct
import sys
import time
import zlib

import gerbonara
from gerbonara import apertures as ap, graphic_objects as go
from gerbonara.utils import MM

SCHEMA = 'pcb-cam/parsed-gerber-objects/1'
MAX_BYTES = 128 * 1024**2
MAGIC = b'PCBPARSE1\0'
OBJECTS = {c.__name__: c for c in (go.Region, go.Line, go.Arc, go.Flash)}
APERTURES = {c.__name__: c for c in (
    ap.CircleAperture, ap.RectangleAperture, ap.ObroundAperture, ap.PolygonAperture)}


class NotCacheable(ValueError):
    """Supported parser output outside this deliberately narrower cache codec."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pack(value):
    """Preserve tuple/list distinctions, attribute keys and exact float values."""
    if value is MM:
        return ['mm']
    if value is None or type(value) in (str, int, bool):
        return ['atom', value]
    if type(value) is float and math.isfinite(value):
        return ['atom', value]
    if type(value) in (tuple, list):
        return [type(value).__name__, [pack(v) for v in value]]
    if type(value) is dict:
        return ['dict', [[pack(k), pack(v)] for k, v in value.items()]]
    if type(value) in APERTURES.values():
        return ['aperture', type(value).__name__,
                {f.name: pack(getattr(value, f.name)) for f in fields(value)}]
    raise NotCacheable('PARSED_VALUE_OUTSIDE_CACHE_CODEC:' + type(value).__name__)


def unpack(value):
    tag = value[0]
    if tag == 'mm':
        return MM
    if tag == 'atom':
        return value[1]
    if tag in ('list', 'tuple'):
        items = [unpack(v) for v in value[1]]
        return tuple(items) if tag == 'tuple' else items
    if tag == 'dict':
        return {unpack(k): unpack(v) for k, v in value[1]}
    if tag == 'aperture':
        return APERTURES[value[1]](**{k: unpack(v) for k, v in value[2].items()})
    raise ValueError('PARSED_CACHE_UNKNOWN_TAG')


def encode(objects):
    """Region points use lossless IEEE doubles; ordered arcs stay explicit.

    Region constructors can close/rewrite outlines. Decode restores the exact
    saved state instead, including an absent attrs field (Gerbonara's known
    Region default). Extra instance fields are preserved, not silently dropped.
    """
    rows, coordinates = [], array('d')
    for obj in objects:
        if type(obj) not in OBJECTS.values() or obj.unit is not MM:
            raise NotCacheable('PARSED_OBJECT_OUTSIDE_CACHE_CODEC')
        state = dict(vars(obj))
        row = {'type': type(obj).__name__}
        if type(obj) is go.Region:
            outline = state.pop('outline')
            arcs = state.pop('arc_centers')
            if type(outline) is not list or any(
                type(p) is not tuple or len(p) != 2 or
                any(type(v) is not float or not math.isfinite(v) for v in p)
                for p in outline
            ) or type(arcs) is not list:
                raise NotCacheable('PARSED_REGION_LAYOUT_OUTSIDE_CACHE_CODEC')
            row['points'] = [len(coordinates), len(outline)]
            coordinates.extend(v for point in outline for v in point)
            row['arcs'] = [len(arcs), [[i, pack(v)] for i, v in enumerate(arcs) if v is not None]]
        row['state'] = pack(state)
        rows.append(row)
    if sys.byteorder != 'little':
        coordinates.byteswap()
    header = canonical({'schema': SCHEMA, 'objects': rows})
    return struct.pack('<Q', len(header)) + header + coordinates.tobytes()


def decode(data):
    size, = struct.unpack('<Q', data[:8])
    if size > len(data) - 8:
        raise ValueError('PARSED_CACHE_HEADER_TRUNCATED')
    header = json.loads(data[8:8+size])
    if header['schema'] != SCHEMA:
        raise ValueError('PARSED_CACHE_SCHEMA_CHANGED')
    coordinates = array('d')
    coordinates.frombytes(data[8+size:])
    if sys.byteorder != 'little':
        coordinates.byteswap()
    objects, consumed = [], 0
    for row in header['objects']:
        cls = OBJECTS[row['type']]
        state = unpack(row['state'])
        if cls is go.Region:
            start, count = row['points']
            if start != consumed or count < 0 or start+2*count > len(coordinates):
                raise ValueError('PARSED_CACHE_POINT_RANGE')
            values = iter(coordinates[start:start+2*count])
            state['outline'] = list(zip(values, values))
            length, entries = row['arcs']
            if length < 0 or length > count:
                raise ValueError('PARSED_CACHE_ARC_RANGE')
            state['arc_centers'] = [None] * length
            seen = set()
            for index, value in entries:
                if index in seen or not 0 <= index < length:
                    raise ValueError('PARSED_CACHE_ARC_INDEX')
                seen.add(index)
                state['arc_centers'][index] = unpack(value)
            consumed += 2*count
        obj = cls.__new__(cls)
        obj.__dict__.update(state)
        if obj.unit is not MM or type(obj.polarity_dark) is not bool:
            raise ValueError('PARSED_CACHE_OBJECT_STATE')
        objects.append(obj)
    if consumed != len(coordinates):
        raise ValueError('PARSED_CACHE_UNUSED_COORDINATES')
    return objects


def implementation_binding(parser):
    """Rehash parser/adapter/codec sources and the installed Gerbonara package.

    The exact callback must be legacy_export.parse (profiling wrappers may be
    unwrapped). No configurable parser options exist at this boundary. Source
    edits, dependency edits and Python-version changes make different entries.
    Cache data is locally trusted like ArtifactStore: checksums detect damage,
    not an attacker able to replace code and all associated receipts together.
    """
    fn = inspect.unwrap(parser)
    if fn.__module__ != 'src.gerber_u05.legacy_export' or fn.__name__ != 'parse':
        raise ValueError('PARSED_CACHE_REQUIRES_QUALIFIED_PARSER')
    from src import gerber_image, validator
    package = Path(gerbonara.__file__).parent
    files = {str(p.relative_to(package)): sha(p.read_bytes()) for p in sorted(package.rglob('*.py'))}
    return dict(schema=SCHEMA, python=list(sys.version_info[:3]), gerbonara=files,
                adapter=sha(Path(inspect.getfile(fn)).read_bytes()),
                completion=sha(Path(gerber_image.__file__).read_bytes()),
                validator=sha(Path(validator.__file__).read_bytes()),
                codec=sha(Path(__file__).read_bytes()), options='legacy_export.parse:no-options')


class ParsedGerberCache:
    """Explicit local cache; caller chooses a prepared LaCie directory.

    Missing/changed keys parse afresh. Corrupt existing entries raise; they are
    never silently deleted or replaced. Unknown supported object families use
    the original parse without caching. File reads reject symlinks/nonfiles.
    A single-entry file is published atomically; no unbound in-memory hits.
    """
    def __init__(self, root):
        from tools.pcb_workspace import require_storage
        work = require_storage()
        self.root = Path(root)
        if self.root.is_symlink() or not self.root.resolve().is_relative_to(work.resolve()):
            raise ValueError('PARSED_CACHE_REQUIRES_LACIE_DIRECTORY')
        self.root.mkdir(parents=True, exist_ok=True)
        self.events = []

    def objects(self, raw, parser):
        start = time.perf_counter()
        binding = dict(source_sha256=sha(raw), source_bytes=len(raw), implementation=implementation_binding(parser))
        key = sha(canonical(binding))
        path = self.root / (key + '.cache')
        event = dict(key=key, binding=binding)
        event['binding_seconds'] = time.perf_counter() - start
        try:
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            except FileNotFoundError:
                fd = None
            if fd is not None:
                t = time.perf_counter()
                with os.fdopen(fd, 'rb') as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                        raise ValueError('PARSED_CACHE_FILE_UNSAFE')
                    entry = stream.read(MAX_BYTES+1)
                event['read_seconds'] = time.perf_counter() - t
                t = time.perf_counter()
                if not entry.startswith(MAGIC):
                    raise ValueError('PARSED_CACHE_MAGIC')
                size, = struct.unpack('<Q', entry[len(MAGIC):len(MAGIC)+8])
                offset = len(MAGIC)+8
                if size > len(entry)-offset:
                    raise ValueError('PARSED_CACHE_ENTRY_TRUNCATED')
                receipt = json.loads(entry[offset:offset+size])
                compressed = entry[offset+size:]
                if receipt['binding'] != binding or sha(compressed) != receipt['compressed_sha256']:
                    raise ValueError('PARSED_CACHE_BINDING_OR_CHECKSUM')
                decoder = zlib.decompressobj()
                data = decoder.decompress(compressed, MAX_BYTES+1)
                if len(data) > MAX_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise ValueError('PARSED_CACHE_PAYLOAD_LIMIT')
                if sha(data) != receipt['objects_sha256']:
                    raise ValueError('PARSED_CACHE_OBJECT_CHECKSUM')
                event['validate_decompress_seconds'] = time.perf_counter() - t
                t = time.perf_counter()
                result = decode(data)
                if len(result) != receipt['object_count']:
                    raise ValueError('PARSED_CACHE_OBJECT_COUNT')
                event.update(status='HIT', decode_seconds=time.perf_counter()-t,
                             objects_sha256=receipt['objects_sha256'], bytes=len(entry), objects=len(result))
                return result
            t = time.perf_counter()
            result = parser(raw).objects
            event['parse_seconds'] = time.perf_counter() - t
            t = time.perf_counter()
            try:
                data = encode(result)
            except NotCacheable:
                event['status'] = 'UNCACHEABLE'
                return result
            if len(data) > MAX_BYTES:
                event['status'] = 'OVERSIZE'
                return result
            # Construction must round-trip byte-exactly before publication.
            if encode(decode(data)) != data:
                raise ValueError('PARSED_CACHE_ROUNDTRIP_CHANGED')
            compressed = zlib.compress(data, 6)
            receipt = canonical(dict(binding=binding, compressed_sha256=sha(compressed),
                                     objects_sha256=sha(data), object_count=len(result)))
            entry = MAGIC + struct.pack('<Q', len(receipt)) + receipt + compressed
            event['encode_validate_seconds'] = time.perf_counter() - t
            from tools.pcb_workspace import require_storage
            import shutil
            require_storage()
            if shutil.disk_usage(self.root).free < 5*1024**3 + len(entry) + 1024**2:
                raise ValueError('PARSED_CACHE_INSUFFICIENT_RESERVE')
            # O_EXCL avoids following a stale/symlink temporary. Process IDs
            # separate concurrent publishers; identical bindings are immutable.
            temporary = path.with_suffix('.' + str(os.getpid()) + '.tmp')
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(entry)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)  # Never overwrite an existing entry.
            except FileExistsError:
                raise ValueError('PARSED_CACHE_CONCURRENT_PUBLICATION_RETRY_REQUIRED')
            finally:
                temporary.unlink()
            event.update(status='MISS', objects_sha256=sha(data), bytes=len(entry), objects=len(result))
            return result
        finally:
            event['seconds'] = time.perf_counter() - start
            self.events.append(event)
