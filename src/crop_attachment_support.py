"""A finite local attachment supported by exact original native trace records.

No net or physical-component label is consumed. The original port is recomputed
from the original intersection; callers cannot supply an enlarged permission area.
"""
from src.clearance_policy import HARD_GAP_MM, CONSTRUCTION_GAP_MM, CONTACT_BUFFER_MM, LEGACY_CONSTRUCTION_MM, BARRIER_GAP_MM
from dataclasses import dataclass
import hashlib
from shapely import from_wkb, to_wkb
from shapely.geometry import LineString
from shapely.ops import nearest_points


@dataclass(frozen=True)
class OriginalTraceAttachment:
    target_id: str
    obstacle_id: str
    feed_id: str
    target_wkb: bytes
    obstacle_wkb: bytes
    feed_wkb: bytes
    original_width_mm: float
    shared_endpoint_mm: tuple
    source_sha256: str
    fragment_sha256: tuple


def bind_original_trace_attachment(source, target_id, obstacle_id, feed_id):
    """Decode/reconstruct exactly three source-bound F.Cu native occurrences."""
    from sexpdata import loads
    from .native_inventory import geometry
    digest = hashlib.sha256(source).hexdigest()
    records = []
    for sid in (target_id, obstacle_id, feed_id):
        try:
            prefix, start, end = sid.rsplit(':', 2)
            if prefix != digest+':bytes':
                raise ValueError('SOURCE_HASH_OR_ID_MISMATCH')
            start,end = int(start),int(end)
            if not 0 <= start < end <= len(source):
                raise ValueError('INVALID_NATIVE_ATTACHMENT_SPAN')
            fragment = source[start:end]
            node = loads(fragment.decode())
        except (TypeError, IndexError, UnicodeError) as exc:
            raise ValueError('INVALID_NATIVE_ATTACHMENT_RECORD') from exc
        attrs = {str(v[0]):v[1:] for v in node[1:] if isinstance(v,list) and v}
        if list(map(str,attrs.get('layer',[]))) != ['F.Cu']:
            raise ValueError('ATTACHMENT_NOT_FCU')
        records.append((str(node[0]),attrs,geometry(node,str(node[0])),hashlib.sha256(fragment).hexdigest()))
    target, obstacle, feed = records
    if target[0] != 'gr_poly' or obstacle[0] not in ('arc','segment') or feed[0] != 'segment':
        raise ValueError('UNSUPPORTED_ATTACHMENT_SOURCE_KINDS')
    ow = float(obstacle[1]['width'][0]); fw = float(feed[1]['width'][0])
    if ow <= 0 or ow != fw:
        raise ValueError('ATTACHMENT_ORIGINAL_WIDTH_MISMATCH')
    endpoint_sets = [{tuple(r[1][k]) for k in ('start','end')} for r in (obstacle,feed)]
    shared = endpoint_sets[0] & endpoint_sets[1]
    if len(shared) != 1:
        raise ValueError('NO_UNIQUE_EXACT_NATIVE_SHARED_ENDPOINT')
    if not target[2].intersects(feed[2]) or target[2].intersection(feed[2]).area <= 0:
        raise ValueError('FEED_DOES_NOT_OVERLAP_ORIGINAL_TARGET')
    if target[2].intersects(obstacle[2]):
        raise ValueError('SUPPORT_EXPECTS_ORIGINAL_DISJOINT_PAIR')
    witness = LineString(nearest_points(target[2],obstacle[2]))
    if not feed[2].covers(witness):
        raise ValueError('ORIGINAL_FEED_DOES_NOT_FILL_RAW_GAP')
    return OriginalTraceAttachment(target_id,obstacle_id,feed_id,
        to_wkb(target[2]),to_wkb(obstacle[2]),to_wkb(feed[2]),ow,tuple(next(iter(shared))),
        digest,tuple(r[3] for r in records))


def qualify_original_support(core, neighbor, neighbors, support, contract):
    """Fail closed on stale geometry, unrelated neighbors or changed port policy."""
    if neighbor['source_id'] != support.obstacle_id:
        return None
    if contract.attachment_buffer_gap_mm != CONTACT_BUFFER_MM:
        raise ValueError('ATTACHMENT_PORT_POLICY_CHANGED')
    if contract.quad_segs != 128 or contract.comparison_epsilon_mm > 1e-12:
        raise ValueError('ATTACHMENT_NUMERICAL_POLICY_CHANGED')
    if contract.hard_gap_mm < HARD_GAP_MM or contract.construction_gap_mm < CONSTRUCTION_GAP_MM:
        raise ValueError('ATTACHMENT_CLEARANCE_POLICY_WEAKENED')
    target = from_wkb(support.target_wkb)
    obstacle = from_wkb(support.obstacle_wkb)
    feed = from_wkb(support.feed_wkb)
    feeds = [r for r in neighbors if r['source_id'] == support.feed_id]
    if len(feeds) != 1:
        return None
    f = feeds[0]
    if (not core.equals(target) or not neighbor['original'].equals(obstacle)
            or not neighbor['geometry'].equals(obstacle)
            or not f['original'].equals(feed) or not f['geometry'].equals(feed)
            or neighbor.get('trace_width_mm') != support.original_width_mm
            or f.get('trace_width_mm') != support.original_width_mm):
        return None
    witness = LineString(nearest_points(core,obstacle))
    overlap = core.intersection(feed)
    port = overlap.buffer(support.original_width_mm+contract.attachment_buffer_gap_mm,
                          quad_segs=contract.quad_segs)
    if overlap.area <= 0 or not feed.covers(witness) or not port.covers(witness):
        return None
    return {'port':port,'feed':feed,'evidence':{
        'target_source_id':support.target_id,'obstacle_source_id':support.obstacle_id,
        'supporting_feed_source_id':support.feed_id,'source_sha256':support.source_sha256,
        'source_fragment_sha256':list(support.fragment_sha256),
        'shared_native_endpoint_mm':list(support.shared_endpoint_mm),
        'original_trace_width_mm':support.original_width_mm,
        'port_sha256':hashlib.sha256(to_wkb(port)).hexdigest(),
        'original_raw_gap_filled_by_feed':True,
        'permission':'EXACT_ORIGINAL_LOCAL_ATTACHMENT_ONLY'}}
