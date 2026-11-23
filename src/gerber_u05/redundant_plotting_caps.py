"""Explicit bulk-trim exception for duplicated, covered source endpoint flashes.

This never changes source family/land metadata or grants another stage authority.
Declared contacts and protected pins remain protected regardless of redundancy.
"""
from math import hypot
from shapely.ops import unary_union
from shapely import to_wkb
from src.native_inventory import ERROR_MM
from src.gerber_image import disk as source_disk


def qualify(rows, original, revision, sid, *, protected=()):
    row=rows[sid];meta=row['metadata'];g=original[sid]
    if (row['kind']!='circle' or sid in protected or
            any(meta.get(k) for k in ('rectangle_terminal','declared_terminal','declared_pin','protected_pin','terminal_intent_declared'))):
        return None
    center=meta.get('center_mm');radius=meta.get('radius_mm');aliases=meta.get('alias_source_ids',[])
    if center is None or radius is None or radius<=0 or sid not in aliases:return None
    if any(s not in original or not original[s].equals_exact(g,0) for s in aliases):return None
    if set(aliases)&set(protected):return None
    if any(rows[s]['metadata'].get(k) for s in aliases for k in
           ('rectangle_terminal','declared_terminal','declared_pin','protected_pin','terminal_intent_declared')):return None
    near=revision.sources(g.buffer(ERROR_MM))
    incident=[];supports=[]
    for other in near:
        if other==sid or rows[other]['kind']!='stroke':continue
        md=rows[other]['metadata'];points=md.get('route_points_mm',[])
        if not points:continue
        supports.append(other)
        width=md.get('original_width_mm',md.get('minimum_caliper_mm'))
        if width is None or abs(width-2*radius)>ERROR_MM:continue
        if min(hypot(p[0]-center[0],p[1]-center[1]) for p in (points[0],points[-1]))<=ERROR_MM:
            incident.append(other)
    if not incident or not supports:return None
    paired=len({to_wkb(original[s]) for s in incident})>=2
    if len(set(aliases))<2 and not paired:return None
    support=unary_union([original[s] for s in supports])
    residual=g.difference(support)
    # Arc buffers and separately plotted disks can have different chord phase.
    # Bind the actual flash to the existing Gerber source disk constructor, rather than
    # increasing the area epsilon to call these two tessellations identical.
    disk=source_disk(center,radius)
    if g.symmetric_difference(disk).area>1e-12:return None
    if not support.buffer(ERROR_MM,quad_segs=128).covers(g):return None
    return dict(schema='covered-duplicate-endpoint-flash/1',source_id=sid,aliases=sorted(aliases),
                center_mm=center,radius_mm=radius,matching_aperture_endpoint_sources=incident,
                original_stroke_support_sources=supports,uncovered_original_area_mm2=residual.area,
                endpoint_support='TWO_DISTINCT_MATCHING_APERTURE_STROKES' if paired else 'DUPLICATE_FLASH_AT_MATCHING_APERTURE_ENDPOINT',
                coverage_proof='CANONICAL_MATCHING_APERTURE_ENDPOINT_DISK_AND_EXISTING_COORDINATE_ENVELOPE',
                coordinate_error_mm=ERROR_MM,canonical_disk_residual_mm2=g.symmetric_difference(disk).area,
                source_family_reclassified=False,authority='OWNER_AUTHORIZED_BULK_NOISE_TRIM_ONLY')
