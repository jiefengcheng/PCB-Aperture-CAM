"""Mandatory saved-place qualification for the owner's T04 shoulder examples.

This is an engineering check, not a viewer callback. It audits final copper at
fixed source-bound locations, so moving a shoulder cannot count as repairing it.
"""
import hashlib
import json
from pathlib import Path
from shapely import to_wkb
from shapely.geometry import Point, box
from shapely.ops import unary_union
from src.native_inventory import ERROR_MM
from .growth_bridge import meaningful_shoulders
from .shoulder_bridge import sharp_points,steps

CONTRACT=Path(__file__).resolve().parents[2]/'contracts/t04/marked_shoulders.json'


def contract():
    raw=CONTRACT.read_bytes();value=json.loads(raw)
    if value['schema']!='t04-marked-shoulder-review/1' or len(value['cases'])!=9:
        raise ValueError('T04_MARKED_CASE_CONTRACT_CHANGED')
    return value,hashlib.sha256(raw).hexdigest()


def audit(before,after,floor,*,local_images=None,terminals=()):
    """Audit local images, or reuse already assembled board images.

    local_images maps case IDs to (before, after, immutable floor) prepared by
    the caller's shared source-query batch. No board search or union lives here.
    """
    policy,sha=contract();angle=policy['maximum_transition_angle_degrees'];records=[]
    for case in policy['cases']:
        region=unary_union([box(*b)for b in case['regions_mm']]);window=region.envelope.buffer(.1)
        target=unary_union([Point(p).buffer(case['target_radius_mm'])for p in case['target_points_mm']])if 'target_points_mm'in case else region
        a,b,f=local_images[case['id']]if local_images is not None else(before.intersection(window),after.intersection(window),floor.intersection(window))
        def corners(image):
            return [p for p in meaningful_shoulders(image,sharp_points(image,f,angle))if target.covers(Point(p))]
        previous=corners(a);remaining=corners(b)
        from .terminal_handoff import interior_t04
        qualified=[r for r in terminals if r.get('attachment_scope_wkb_hex')and r.get('attachment_dependencies')]
        interior_remaining=interior_t04(remaining,qualified)
        interior_keys={tuple(p)for p in interior_remaining}
        pending=[p for p in remaining if tuple(p)not in interior_keys]
        new=[p for p in meaningful_shoulders(b,sharp_points(b,a,angle))if region.covers(Point(p))]
        added=b.difference(a).area;removed=a.difference(b).area
        control=case['disposition']=='UNCHANGED_COVERAGE_CONTROL'
        passed=(a.symmetric_difference(b).intersection(region).area<=ERROR_MM**2 if control else not interior_remaining and not new and added+1e-12>=removed)
        bounds=region.bounds
        records.append(dict(id=case['id'],image=case['image'],passed=passed,
            disposition='UNCHANGED_COVERAGE_CONTROL'if control else
                'INTERIOR_REPAIRED; SOURCE_ATTACHMENTS_PENDING_T05'if passed and pending else'REPAIRED'if passed else'UNRESOLVED',
            bounds=dict(x=bounds[0]-.08,y=bounds[1]-.08,width=bounds[2]-bounds[0]+.16,height=bounds[3]-bounds[1]+.16),
            before_corners_mm=previous,remaining_corners_mm=remaining,new_corners_mm=new,
            unresolved_interior_corners_mm=interior_remaining,deferred_terminal_corners_mm=pending,
            target_points_mm=case.get('target_points_mm',[]),
            before_steps_mm=[s['point_mm']for s in steps(a,f,angle)if region.covers(Point(s['point_mm']))],
            after_steps_mm=[s['point_mm']for s in steps(b,f,angle)if region.covers(Point(s['point_mm']))],
            added_area_mm2=added,removed_area_mm2=removed,net_area_mm2=added-removed,
            before_wkb_sha256=hashlib.sha256(to_wkb(a)).hexdigest(),after_wkb_sha256=hashlib.sha256(to_wkb(b)).hexdigest(),
            floor_wkb_sha256=hashlib.sha256(to_wkb(f)).hexdigest()))
    return dict(schema='t04-marked-shoulder-checks/1',contract_sha256=sha,source_sha256=policy['source_sha256'],
        passed=all(r['passed']for r in records),cases=records,maximum_transition_angle_degrees=angle,
        geometry_scope='FINAL_SERIALIZED_PHYSICAL_COPPER; FIXED_MARKED_PLACES; NO_RELOCATED_SHOULDER_PASS')
