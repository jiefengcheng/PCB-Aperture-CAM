"""Fixed-source uniform normal offsets with separate checking envelopes.

This is a versioned alternative to rebuffering a sampled route. The original
finite stroke is the nominal geometry authority; every primitive receives the
same width-derived radial increase. No route fitting or corner adjustment occurs.
"""
import hashlib
from shapely import from_wkb,to_wkb
from shapely.ops import unary_union
from .uniform_trace_width import construct_uniform_width as source_binding
from .native_inventory import steps,ERROR_MM

FAMILY='fixed-source-uniform-offset-verification-envelope/1'


def construct_source_offset_width(source,chain,manifest_rows,cached_blobs,factor):
    # The source binder validates scalar bounds, native widths, fragment hashes,
    # cache identities and original route envelopes without positive buffering.
    if type(factor) not in (float,int) or not 1<=factor<=1.5:
        raise ValueError('ONE_FINITE_COMMON_SCALE_REQUIRED_WITHIN_1_TO_1P5')
    record,_,original,_=source_binding(source,chain,manifest_rows,cached_blobs,1.)
    nominal_parts={};envelope_parts={}
    for p in record['primitives']:
        sid=p['source_id'];core=from_wkb(cached_blobs[sid]);width=p['original_width_mm']
        delta=width*(factor-1)/2;q=2*steps(width*.5/2)
        nominal=core if factor==1 else core.buffer(delta,quad_segs=q)
        envelope=core if factor==1 else core.buffer(delta+ERROR_MM,quad_segs=q)
        if not nominal.is_valid or not envelope.is_valid:raise ValueError('INVALID_OFFSET_COPPER')
        if not nominal.covers(core):raise ValueError('OFFSET_SOURCE_CORE_NOT_RETAINED')
        if not envelope.covers(nominal):raise ValueError('OFFSET_NOMINAL_OUTSIDE_ENVELOPE')
        nominal_parts[sid]=nominal;envelope_parts[sid]=envelope
        p.update(factor=factor,nominal_candidate_width_mm=width*factor,uniform_radial_increase_mm=delta,
            nominal_candidate_wkb_sha256=hashlib.sha256(to_wkb(nominal)).hexdigest(),
            verification_envelope_wkb_sha256=hashlib.sha256(to_wkb(envelope)).hexdigest(),
            fixed_offset_quadrant_segments=q,nominal_outward_margin_mm=0.,
            verification_outward_margin_mm=0. if factor==1 else ERROR_MM)
    nominal=unary_union(list(nominal_parts.values()));envelope=unary_union(list(envelope_parts.values()))
    if not nominal.covers(original):raise ValueError('OFFSET_COMPLETE_SOURCE_CORE_NOT_RETAINED')
    if not envelope.covers(nominal):raise ValueError('OFFSET_COMPLETE_NOMINAL_OUTSIDE_ENVELOPE')
    record.update(factor=factor,uniform_nominal_width_mm=record['verified_original_width_mm']*factor,
        geometry_family=FAMILY,geometry_role='NOMINAL_SOURCE_OFFSET_WITH_SEPARATE_CHECKING_ENVELOPE',
        added_area_mm2=nominal.difference(original).area,core_removed_mm2=original.difference(nominal).area,
        nominal_copper_wkb_sha256=hashlib.sha256(to_wkb(nominal)).hexdigest(),
        verification_envelope_wkb_sha256=hashlib.sha256(to_wkb(envelope)).hexdigest(),
        nominal_width_ceiling_factor=1.5,route_change='NONE',
        approximation='Fixed polygonal source offset; checking margin excluded from nominal copper')
    return record,nominal_parts,envelope_parts,original,nominal,envelope
