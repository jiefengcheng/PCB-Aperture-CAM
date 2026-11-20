"""Exact, bounded visibility operands carried by T04 pass checkpoints.

Visibility is a function of the frozen original scene, its query ordering,
the checker policy, and this neighbor's geometry version. Other trial routes
never hide its boundary. The record supplies geometry only; pair checks,
attachment ports, clearance predicates and pin checks still execute.
"""
from pathlib import Path
import zlib

import shapely
from shapely import from_wkb, get_precision, to_wkb

from src.stage_abi.store import canonical, digest

LIMIT = 4 * 1024 * 1024
MAX_RAW = 64 * 1024 * 1024
SCHEMA = 't04-exact-visibility/1'


def binding(checker):
    directory = Path(__file__).parent
    files = [directory / name for name in ('checker.py', 'dependency.py', 'visibility_records.py')]
    return digest(canonical(dict(
        scene=checker.binding, shapely=shapely.__version__, geos=shapely.geos_version_string,
        union_cache_enabled=bool(checker.original_union_cache_limit),
        code=[digest(path.read_bytes()) for path in files])))


def decode(row):
    """Bound decompression and check exact bytes before exposing an operand."""
    try:
        packed = bytes.fromhex(row['compressed'])
        decoder = zlib.decompressobj()
        raw = decoder.decompress(packed, MAX_RAW + 1)
        if (len(raw) > MAX_RAW or not decoder.eof or decoder.unused_data
                or decoder.unconsumed_tail or digest(raw) != row['sha256']):
            raise ValueError('Invalid visibility payload')
        shape = from_wkb(raw)
        if get_precision(shape) != 0 or to_wkb(shape, include_srid=True) != raw:
            raise ValueError('Visibility encoding changed')
        return shape
    except (KeyError, TypeError, ValueError, zlib.error, shapely.errors.GEOSException) as error:
        raise ValueError('T04_VISIBILITY_RECORD_CHANGED') from error


class VisibilityRecords:
    def __init__(self, checker):
        self.checker = checker
        self.records = {}
        self.window_mode = None
        self.hits = 0
        self.misses = 0

    def get(self, sid, version):
        # The checker selects its union-window mode when a check begins.
        # A restored packet can load before that transition, but is reusable
        # only in the exact mode in which it was captured.
        if self.window_mode != self.checker.use_width_union_window:
            self.misses += 1
            return None
        row = self.records.get((sid, version))
        if row is None:
            self.misses += 1
            return None
        value = decode(row)
        self.hits += 1
        return value

    def snapshot(self):
        # Favor the latest visible versions, then prior versions still held
        # by the existing bounded geometry cache. Persist exact WKB, including
        # empties. Non-default precision models remain on the original path.
        candidates = dict(self.checker.visible_cache)
        values = {(sid, version): shape for sid, (version, shape) in candidates.items()}
        for key, (shape, _) in self.checker.geometries.items():
            if key[0] == 'visible':
                values.setdefault((key[1], key[2]), shape)
        records = []
        weight = 0
        # Restored records belong to their captured query mode. Re-saving
        # after a mode transition must not silently relabel those operands.
        carried = self.records if self.window_mode == self.checker.use_width_union_window else {}
        keys = list(values) + [key for key in carried if key not in values]
        for sid, version in keys:
            if (sid, version) in values:
                shape = values[sid, version]
                if get_precision(shape) != 0:
                    continue
                raw = to_wkb(shape, include_srid=True)
                if len(raw) > MAX_RAW:
                    continue
                row = dict(sid=sid, version=version, sha256=digest(raw),
                           compressed=zlib.compress(raw, 1).hex())
            else:
                row = carried[sid, version]
            size = len(canonical(row)) + 256
            if weight + size > LIMIT:
                continue
            records.append(row)
            weight += size
        return dict(schema=SCHEMA, binding=binding(self.checker),
                    window_mode=self.checker.use_width_union_window, records=records)

    def restore(self, packet):
        if packet['schema'] != SCHEMA or packet['binding'] != binding(self.checker):
            raise ValueError('T04_VISIBILITY_BINDING_CHANGED')
        if type(packet.get('window_mode')) is not bool:
            raise ValueError('T04_VISIBILITY_RECORD_CHANGED')
        restored = {}
        weight = 0
        for row in packet['records']:
            sid, version = row['sid'], row['version']
            key = sid, version
            weight += len(canonical(row)) + 256
            if (sid not in self.checker.original or key in restored or weight > LIMIT
                    or len(version) != 64 or any(c not in '0123456789abcdef' for c in version)):
                raise ValueError('T04_VISIBILITY_RECORD_CHANGED')
            decode(row)
            restored[key] = row
        # Publish only after every record has been checked. Old checkpoints
        # omit this packet and naturally start with an empty record cache.
        self.records = restored
        self.window_mode = packet['window_mode']
