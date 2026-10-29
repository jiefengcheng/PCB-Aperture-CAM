"""Construct nominal uniform width on unchanged, source-bound native routes.

Construction is not clearance verification or stage acceptance. Original cached
copper must be contained exactly; failure is rejected rather than patched by a
neck-down or by changing a route. Curves retain the inventory's stated kernel.
"""
import hashlib
import math
from shapely import from_wkb,to_wkb
from shapely.geometry import LineString
from shapely.ops import unary_union
from .crop_attachment_diagnostic import _decode
from .native_inventory import arc_points,steps,ERROR_MM


def construct_uniform_width(source, chain, manifest_rows, cached_blobs, factor):
    if type(factor) not in (float,int) or not math.isfinite(factor) or not 1<=factor<=1.5:
        raise ValueError('ONE_FINITE_COMMON_SCALE_REQUIRED_WITHIN_1_TO_1P5')
    ids=chain['source_ids']
    if not ids or len(set(ids))!=len(ids):raise ValueError('INVALID_COMPLETE_CHAIN_IDENTITIES')
    if not all(sid in manifest_rows and sid in cached_blobs for sid in ids):
        raise ValueError('COMPLETE_CHAIN_MEMBER_MISSING')
    source_sha,records=_decode(source,ids)
    if chain.get('source_sha256',source_sha)!=source_sha:
        raise ValueError('CHAIN_SOURCE_HASH_MISMATCH')
    widths=[];primitives=[];candidates={};originals=[]
    for sid,record in zip(ids,records,strict=True):
        kind,attrs,_,fragment_sha=record
        if kind not in ('segment','arc'):raise ValueError('UNSUPPORTED_NATIVE_ROUTE_PRIMITIVE')
        row=manifest_rows[sid];blob=cached_blobs[sid]
        if row['id']!=sid or hashlib.sha256(blob).hexdigest()!=row['geometry_sha256']:
            raise ValueError('ORIGINAL_SOURCE_CACHE_MISMATCH')
        width=float(attrs['width'][0])
        if not math.isfinite(width) or width<=0 or width!=row['trace_width_mm']:
            raise ValueError('ORIGINAL_WIDTH_NOT_VERIFIED')
        widths.append(width)
        if len(set(widths))!=1:raise ValueError('FULL_TRACE_HAS_MIXED_ORIGINAL_WIDTHS')
        start,end=(tuple(map(float,attrs[k])) for k in ('start','end'))
        points=arc_points(start,tuple(map(float,attrs['mid'])),end) if kind=='arc' else [start,end]
        original=from_wkb(blob);originals.append(original)
        nominal=width*factor
        proposed=original if factor==1 else LineString(points).buffer(nominal/2,quad_segs=steps(nominal/2))
        if not proposed.is_valid or proposed.is_empty:raise ValueError('INVALID_WIDTH_GEOMETRY')
        if not proposed.covers(original):raise ValueError('ORIGINAL_PRIMITIVE_CORE_NOT_RETAINED')
        candidates[sid]=proposed
        primitives.append(dict(source_id=sid,kind=kind,fragment_sha256=fragment_sha,
            original_wkb_sha256=hashlib.sha256(blob).hexdigest(),candidate_wkb_sha256=hashlib.sha256(to_wkb(proposed)).hexdigest(),
            original_width_mm=width,nominal_candidate_width_mm=nominal,factor=factor,
            fixed_source_route_points_mm=[list(p) for p in points],start_mm=list(start),end_mm=list(end),
            source_mid_mm=list(map(float,attrs['mid'])) if kind=='arc' else None))
    original=unary_union(originals);candidate=unary_union(list(candidates.values()))
    if not candidate.covers(original):raise ValueError('FULL_TRACE_CORE_NOT_RETAINED')
    return dict(source_sha256=source_sha,component_id=chain['component_id'],factor=factor,
        verified_original_width_mm=widths[0],uniform_nominal_width_mm=widths[0]*factor,
        complete_source_ids=list(ids),primitives=primitives,
        source_route_change='NONE',per_curve_approximation_error_mm=ERROR_MM,
        core_removed_mm2=original.difference(candidate).area,
        added_area_mm2=candidate.difference(original).area,
        status='WIDTH_CONSTRUCTION_ONLY_CLEARANCE_NOT_CHECKED'),candidates,original,candidate


def construct_group_width(source, group, chains, manifest_rows, cached_blobs, factor):
    """One factor across the declared complete group, including singleton groups."""
    members=group['members']
    if not members or len(set(members))!=len(members) or any(cid not in chains for cid in members):
        raise ValueError('COMPLETE_GROUP_MEMBER_MISSING_OR_DUPLICATED')
    used=set();records=[];parts={};originals=[];candidates=[]
    for cid in sorted(members):
        chain=chains[cid]
        if used.intersection(chain['source_ids']):raise ValueError('SOURCE_PRIMITIVE_SHARED_BY_MULTIPLE_TRACES')
        used.update(chain['source_ids'])
        record,primitives,original,candidate=construct_uniform_width(source,chain,manifest_rows,cached_blobs,factor)
        records.append(record);parts.update(primitives);originals.append(original);candidates.append(candidate)
    return dict(group_id=group['group_id'],common_factor=factor,trace_members=records,
        status='GROUP_WIDTH_CONSTRUCTION_ONLY_CLEARANCE_NOT_CHECKED'),parts,unary_union(originals),unary_union(candidates)
