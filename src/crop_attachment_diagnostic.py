"""Source-bound REV09 diagnostics; not an enabled production growth policy.

Original finite ports and clearance thresholds are unchanged. Only the four
declared source relationships are eligible in the calling diagnostic packet.
"""
from src.clearance_policy import HARD_GAP_MM, CONSTRUCTION_GAP_MM, CONTACT_BUFFER_MM, LEGACY_CONSTRUCTION_MM, BARRIER_GAP_MM
from dataclasses import dataclass
import hashlib
from shapely import from_wkb, to_wkb
from shapely.geometry import LineString
from shapely.ops import nearest_points
from .crop_stage_growth import check_proposal, original_attachment_port


@dataclass(frozen=True)
class AttachmentDiagnostic:
    mode: str
    target_id: str
    obstacle_id: str
    target_wkb: bytes
    obstacle_wkb: bytes
    source_sha256: str
    fragments_sha256: tuple
    feed_id: str | None = None
    feed_wkb: bytes | None = None
    width_mm: float = 0.0


def _decode(source, ids):
    from sexpdata import loads
    from .native_inventory import geometry
    digest = hashlib.sha256(source).hexdigest()
    records = []
    for sid in ids:
        prefix, start, end = sid.rsplit(':', 2)
        if prefix != digest+':bytes':
            raise ValueError('SOURCE_HASH_OR_ID_MISMATCH')
        a, b = int(start), int(end)
        if not 0 <= a < b <= len(source):
            raise ValueError('INVALID_NATIVE_SOURCE_SPAN')
        blob = source[a:b]
        node = loads(blob.decode())
        kind = str(node[0])
        attrs = {str(v[0]):v[1:] for v in node[1:] if isinstance(v,list) and v}
        if list(map(str,attrs.get('layer',[]))) != ['F.Cu']:
            raise ValueError('ATTACHMENT_NOT_FCU')
        records.append((kind, attrs, geometry(node,kind), hashlib.sha256(blob).hexdigest()))
    return digest, records


def bind_circle_attachment(source, target_id, obstacle_id):
    digest, (target, circle) = _decode(source, (target_id, obstacle_id))
    if target[0] != 'gr_poly' or circle[0] != 'gr_circle':
        raise ValueError('UNSUPPORTED_CIRCLE_ATTACHMENT_SOURCE')
    if list(map(str,circle[1].get('fill',[]))) != ['yes']:
        raise ValueError('CIRCLE_NOT_FILLED')
    core, obstacle = target[2], circle[2]
    if not core.equals(core.envelope) or core.intersection(obstacle).area <= 0:
        raise ValueError('NO_ORIGINAL_RECTANGLE_CIRCLE_OVERLAP')
    if obstacle.difference(core).is_empty:
        raise ValueError('FULLY_COVERED_CIRCLE_NOT_INDEPENDENT_TARGET')
    return AttachmentDiagnostic('DIRECT_ORIGINAL_CIRCLE_ATTACHMENT',target_id,obstacle_id,
        to_wkb(core),to_wkb(obstacle),digest,(target[3],circle[3]))


def bind_overlapping_feed_attachment(source, target_id, obstacle_id, feed_id):
    digest, (target, obstacle, feed) = _decode(source,(target_id,obstacle_id,feed_id))
    if target[0] != 'gr_poly' or obstacle[0] != 'segment' or feed[0] != 'segment':
        raise ValueError('UNSUPPORTED_OVERLAPPING_FEED_SOURCE')
    ow, fw = float(obstacle[1]['width'][0]), float(feed[1]['width'][0])
    if ow <= 0 or ow != fw:
        raise ValueError('ORIGINAL_WIDTH_MISMATCH')
    core, ob, fg = target[2], obstacle[2], feed[2]
    if not core.equals(core.envelope) or core.intersects(ob) or core.intersection(fg).area <= 0:
        raise ValueError('INVALID_ORIGINAL_FEED_TARGET_RELATIONSHIP')
    witness = LineString(nearest_points(core,ob))
    junction = fg.intersection(ob)
    if junction.area <= 0 or not fg.covers(witness) or junction.distance(witness) > 1e-12:
        raise ValueError('NO_SOURCE_BOUND_LOCAL_OVERLAP_SUPPORT')
    return AttachmentDiagnostic('LOCAL_ORIGINAL_FINITE_COPPER_OVERLAP',target_id,obstacle_id,
        to_wkb(core),to_wkb(ob),digest,(target[3],obstacle[3],feed[3]),feed_id,to_wkb(fg),ow)


def check_attachment_diagnostic(core, candidate, neighbors, binding, *, crop, cap, contract):
    if (contract.hard_gap_mm != HARD_GAP_MM or contract.construction_gap_mm != CONSTRUCTION_GAP_MM
            or contract.attachment_buffer_gap_mm != CONTACT_BUFFER_MM or contract.quad_segs != 128
            or contract.comparison_epsilon_mm != 1e-12 or contract.area_epsilon_mm2 != 1e-12):
        raise ValueError('DIAGNOSTIC_REQUIRES_UNCHANGED_CONTRACT')
    expected = from_wkb(binding.target_wkb)
    original = from_wkb(binding.obstacle_wkb)
    rows = [n for n in neighbors if n['source_id'] == binding.obstacle_id]
    if (len(rows) != 1 or not core.equals(expected)
            or not rows[0]['original'].equals(original) or not rows[0]['geometry'].equals(original)):
        raise ValueError('STALE_OR_UNBOUND_DIAGNOSTIC_GEOMETRY')
    n = rows[0]
    ordinary = check_proposal(core,candidate,[q for q in neighbors if q['source_id'] != binding.obstacle_id],
                             crop=crop,cap=cap,contract=contract)
    added = candidate.difference(core)
    reasons = []
    row = dict(neighbor_id=binding.obstacle_id, original_surface_gap_mm=core.distance(original),
               candidate_surface_gap_mm=candidate.distance(original), original_source_contact=core.intersects(original),
               diagnostic_mode=binding.mode, source_sha256=binding.source_sha256,
               source_fragment_sha256=list(binding.fragments_sha256))
    if binding.mode == 'DIRECT_ORIGINAL_CIRCLE_ATTACHMENT':
        port = original_attachment_port(core,original,0.0,contract)
        if port is None or core.intersection(original).area <= 0:
            raise ValueError('ORIGINAL_CIRCLE_CONTACT_MISSING')
        visible = original.difference(core)
        protected = visible.difference(port)
        exposed = added.difference(original)
        checked = exposed.difference(port)
        gap = None if checked.is_empty else checked.distance(visible)
        covered = candidate.intersection(protected).area
        if covered > contract.area_epsilon_mm2:
            reasons.append('ORIGINAL_VISIBLE_CIRCLE_OUTSIDE_PORT_COVERED')
        if gap is not None and gap + contract.comparison_epsilon_mm < contract.construction_gap_mm:
            reasons.append('EXPOSED_ADDITION_BELOW_VISIBLE_CIRCLE_GUARD')
        row.update(original_visible_circle_area_mm2=visible.area,
                   protected_visible_circle_new_coverage_mm2=covered,
                   checked_exposed_to_visible_circle_gap_mm=gap,
                   checked_exposed_to_full_circle_diagnostic_mm=None if checked.is_empty else checked.distance(original),
                   inside_original_port_circle_coverage_extension_mm2=candidate.intersection(visible.intersection(port)).area,
                   exposed_target_addition_mm2=exposed.area,
                   original_circle_wkb_sha256=hashlib.sha256(binding.obstacle_wkb).hexdigest(),
                   interpretation='Only circle portions inside the unchanged original rectangle are internal boundaries. '
                      'Original visible circle outside the unchanged finite port is protected; no component exemption.')
    elif binding.mode == 'LOCAL_ORIGINAL_FINITE_COPPER_OVERLAP':
        feeds = [q for q in neighbors if q['source_id'] == binding.feed_id]
        feed = from_wkb(binding.feed_wkb)
        if (len(feeds) != 1 or not feeds[0]['original'].equals(feed) or not feeds[0]['geometry'].equals(feed)
                or feeds[0]['trace_width_mm'] != binding.width_mm or n['trace_width_mm'] != binding.width_mm):
            raise ValueError('STALE_OR_MISSING_ORIGINAL_FEED')
        port = original_attachment_port(core,feed,binding.width_mm,contract)
        witness = LineString(nearest_points(core,original))
        if port is None or not port.covers(witness) or not feed.covers(witness):
            raise ValueError('ORIGINAL_FEED_PORT_DOES_NOT_SUPPORT_WITNESS')
        exposed = added.difference(feed.intersection(port))
        checked = added.difference(port)
        outside_gap = candidate.distance(original.difference(port))
        gap = None if exposed.is_empty else exposed.distance(original)
        checked_gap = None if checked.is_empty else checked.distance(original)
        if candidate.intersects(original):
            reasons.append('NEW_SOURCE_CONTACT')
        if outside_gap + contract.comparison_epsilon_mm < contract.hard_gap_mm:
            reasons.append('OUTSIDE_ORIGINAL_ATTACHMENT_PORT_BELOW_FLOOR')
        if gap is not None and gap + contract.comparison_epsilon_mm < contract.construction_gap_mm:
            reasons.append('EXPOSED_ADDITION_BELOW_CONSTRUCTION_GAP')
        if checked_gap is not None and checked_gap + contract.comparison_epsilon_mm < contract.construction_gap_mm:
            reasons.append('ADDED_COPPER_BELOW_CONSTRUCTION_GAP_OUTSIDE_PORT')
        row.update(supporting_feed_source_id=binding.feed_id, original_trace_width_mm=binding.width_mm,
                   original_feed_obstacle_overlap_mm2=feed.intersection(original).area,
                   original_raw_gap_filled_by_feed=feed.covers(witness),
                   candidate_to_obstacle_outside_original_port_gap_mm=outside_gap,
                   exposed_added_copper_to_full_obstacle_gap_mm=gap,
                   added_copper_gap_outside_port_mm=checked_gap,
                   interpretation='Verified local finite-width source overlap; no shared endpoint or electrical-net proof claimed.')
    else:
        raise ValueError('UNKNOWN_DIAGNOSTIC_MODE')
    row.update(attachment_port_area_mm2=port.area,
               attachment_port_wkb_sha256=hashlib.sha256(to_wkb(port)).hexdigest(),failures=reasons)
    ordinary['pairs'].append(row)
    ordinary['failures'].extend(dict(neighbor_id=binding.obstacle_id,reason=r) for r in reasons)
    ordinary['passed'] = not ordinary['failures']
    ordinary['diagnostic_only'] = True
    return ordinary
