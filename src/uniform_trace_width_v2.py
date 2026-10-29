"""Nested conservative verification envelopes for fixed-route width search.

One cap-selected tessellation is held fixed across factors. Positive proposals use
a one-ERROR_MM outward validation margin, bounded by the inventory's existing
two-ERROR_MM geometry envelope. These are verification envelopes, not native
exports or a change to nominal widths. Scale 1 retains exact source geometry.
"""
import hashlib
import math
from shapely import from_wkb,to_wkb
from shapely.geometry import LineString
from shapely.ops import unary_union
from .native_inventory import steps,ERROR_MM
from .uniform_trace_width import construct_uniform_width as original_preflight

FAMILY = 'fixed-route-fixed-tessellation-verification-envelope/2'


def construct_uniform_width(source,chain,manifest_rows,cached_blobs,factor):
    if type(factor) not in (int,float) or not math.isfinite(factor) or not 1<=factor<=1.5:
        raise ValueError('ONE_FINITE_COMMON_SCALE_REQUIRED_WITHIN_1_TO_1P5')
    record,_,original,_=original_preflight(source,chain,manifest_rows,cached_blobs,1.)
    candidates={}
    for p in record['primitives']:
        sid=p['source_id'];width=p['original_width_mm'];radius=width*factor/2
        core=from_wkb(cached_blobs[sid]);route=LineString(p['fixed_source_route_points_mm'])
        quadrants=2*steps(width*1.5/2+2*ERROR_MM)
        envelope=route.buffer(radius+2*ERROR_MM,quad_segs=quadrants)
        if not envelope.covers(core):raise ValueError('SOURCE_CORE_OUTSIDE_DECLARED_ROUTE_ENVELOPE')
        candidate=core if factor==1 else route.buffer(radius+ERROR_MM,quad_segs=quadrants)
        if not candidate.covers(core) or not envelope.covers(candidate):
            raise ValueError('INVALID_NOMINAL_WIDTH_OR_SOURCE_RETENTION')
        candidates[sid]=candidate
        p.update(factor=factor,nominal_candidate_width_mm=width*factor,
                 candidate_wkb_sha256=hashlib.sha256(to_wkb(candidate)).hexdigest(),
                 fixed_buffer_quadrant_segments=quadrants,
                 nominal_route_envelope_error_mm=2*ERROR_MM,
                 outward_validation_margin_mm=0. if factor==1 else ERROR_MM,
                 geometry_role='EXACT_SOURCE' if factor==1 else 'CONSERVATIVE_WIDTH_VERIFICATION_ENVELOPE')
    candidate=unary_union(list(candidates.values()))
    if not candidate.covers(original):raise ValueError('FULL_TRACE_CORE_NOT_RETAINED')
    record.update(factor=factor,uniform_nominal_width_mm=record['verified_original_width_mm']*factor,
        geometry_family=FAMILY,core_removed_mm2=original.difference(candidate).area,
        added_area_mm2=candidate.difference(original).area,
        approximation='Fixed-tessellation conservative verification envelope within existing inventory error budget; nominal width unchanged')
    return record,candidates,original,candidate


def construct_group_width(source,group,chains,manifest_rows,cached_blobs,factor):
    members=group['members']
    if not members or len(set(members))!=len(members) or any(cid not in chains for cid in members):
        raise ValueError('COMPLETE_GROUP_MEMBER_MISSING_OR_DUPLICATED')
    used=set();records=[];parts={};originals=[];candidates=[]
    for cid in sorted(members):
        chain=chains[cid]
        if used.intersection(chain['source_ids']):raise ValueError('SOURCE_PRIMITIVE_SHARED_BY_MULTIPLE_TRACES')
        used.update(chain['source_ids'])
        r,p,o,c=construct_uniform_width(source,chain,manifest_rows,cached_blobs,factor)
        records.append(r);parts.update(p);originals.append(o);candidates.append(c)
    return dict(group_id=group['group_id'],common_factor=factor,geometry_family=FAMILY,trace_members=records,
        status='GROUP_WIDTH_CONSTRUCTION_ONLY_CLEARANCE_NOT_CHECKED'),parts,unary_union(originals),unary_union(candidates)
