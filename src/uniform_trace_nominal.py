"""Nominal copper separate from its conservative width-verification envelope.

Each original finite source stroke receives the same radial increase implied by
its verified width and common factor. Dilation preserves the exact source core;
the separately constructed conservative envelope must contain all nominal copper.
"""
import hashlib
from shapely import from_wkb,to_wkb
from shapely.ops import unary_union
from .native_inventory import steps
from .uniform_trace_width_v2 import construct_uniform_width,FAMILY as VERIFICATION_FAMILY

FAMILY='source-core-uniform-offset-nominal/1'


def construct_nominal_width(source,chain,manifest_rows,cached_blobs,factor):
    record,envelopes,original,envelope=construct_uniform_width(source,chain,manifest_rows,cached_blobs,factor)
    nominal_parts={}
    for p in record['primitives']:
        sid=p['source_id'];core=from_wkb(cached_blobs[sid]);width=p['original_width_mm']
        increment=width*(factor-1)/2
        quadrants=2*steps(width*.5/2)
        nominal=core if factor==1 else core.buffer(increment,quad_segs=quadrants)
        if not nominal.covers(core):raise ValueError('NOMINAL_SOURCE_CORE_NOT_RETAINED')
        if not envelopes[sid].covers(nominal):raise ValueError('NOMINAL_COPPER_OUTSIDE_VERIFIED_ENVELOPE')
        nominal_parts[sid]=nominal
        p['verification_envelope_wkb_sha256']=p['candidate_wkb_sha256']
        p['candidate_wkb_sha256']=hashlib.sha256(to_wkb(nominal)).hexdigest()
        p['verification_outward_margin_mm']=p.pop('outward_validation_margin_mm')
        p.update(geometry_role='NOMINAL_COPPER_UNIFORM_SOURCE_BOUNDARY_OFFSET',nominal_outward_margin_mm=0.,
            uniform_radial_increase_mm=increment,nominal_offset_quadrant_segments=quadrants)
    nominal=unary_union(list(nominal_parts.values()))
    if not nominal.covers(original):raise ValueError('NOMINAL_COMPLETE_TRACE_CORE_NOT_RETAINED')
    if not envelope.covers(nominal):raise ValueError('NOMINAL_TRACE_OUTSIDE_VERIFIED_ENVELOPE')
    record.update(geometry_family=FAMILY,verification_geometry_family=VERIFICATION_FAMILY,
        geometry_role='NOMINAL_COPPER_SEPARATE_FROM_CONSERVATIVE_VERIFICATION',
        verification_added_area_mm2=record['added_area_mm2'],added_area_mm2=nominal.difference(original).area,
        nominal_copper_wkb_sha256=hashlib.sha256(to_wkb(nominal)).hexdigest(),
        verification_envelope_wkb_sha256=hashlib.sha256(to_wkb(envelope)).hexdigest(),
        source_route_change='NONE',nominal_width_ceiling_factor=1.5)
    return record,nominal_parts,envelopes,original,nominal,envelope
