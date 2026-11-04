"""Fresh source derivation of preserved owner-reviewed bulk protections.

These annotations classify original source roles only. They never select a
crop, supply candidate geometry, infer nets or exempt copper from clearance.
"""
from collections import Counter
from shapely import from_wkb
from shapely.geometry import box
from src.stage_abi.store import digest
from src.source_bulk_components import bind_bulk_regions,source_bulk_role
from src.u03_board.source import qualify as base_qualify,require_admitted
from tools.t01_operator_host import ROOT,read

CONTRACT=ROOT/'contracts/operator/u04_source_roles.json'


def reviewed_roles(raw,manifest,original_blobs):
    spec=read(CONTRACT);source=digest(raw);found=[];protected={}
    for profile in spec['profiles']:
        if profile['source_sha256']!=source:continue
        receipt=ROOT/profile['review_receipt']
        if digest(receipt.read_bytes())!=profile['review_receipt_sha256']:raise ValueError('U04_SOURCE_ROLE_REVIEW_CHANGED')
        accepted=read(receipt)
        if accepted['status']!='FROZEN_C03_FINAL_SO_FAR_OWNER_ACCEPTED' or accepted['source_sha256']!=source:
            raise ValueError('U04_SOURCE_ROLE_AUTHORITY_INVALID')
        region=box(*profile['scope_mm'])
        regions,bindings=bind_bulk_regions([from_wkb(original_blobs[s]) for s in sorted(original_blobs)],profile['seeds'],scope=region)
        expected={r['name']:(r['original_component_wkb_sha256'],r['area_mm2']) for r in profile['expected_regions']}
        actual={r['name']:(r['original_component_wkb_sha256'],r['area_mm2']) for r in bindings}
        if actual!=expected:raise ValueError('U04_REVIEWED_BULK_SOURCE_RECONSTRUCTION_CHANGED')
        for row in manifest:
            if row['kind'] not in ('segment','arc','gr_line','gr_arc'):continue
            sid=row['id'];witness=source_bulk_role(sid,from_wkb(original_blobs[sid]),regions,scope=region)
            if witness is not None:protected[sid]=witness
        for annotation in profile['reviewed_fixed_sources']:
            sid=annotation['source_id']
            if sid not in original_blobs or digest(original_blobs[sid])!=annotation['source_geometry_sha256']:raise ValueError('U04_REVIEWED_SOURCE_IDENTITY_CHANGED')
            protected[sid]=dict(annotation,authority='Preserved reviewed original-source fixed disposition',clearance_exemption='NONE')
        found.append(dict(source_sha256=source,scope_mm=profile['scope_mm'],regions=bindings,review_receipt_sha256=profile['review_receipt_sha256']))
    return dict(contract_sha256=digest(CONTRACT.read_bytes()),profiles=found,protected=protected,authority='Original reviewed source roles; no geometry or clearance exemption')


def qualify(raw,manifest,original_blobs,current_blobs,*,selection=None):
    report=base_qualify(raw,manifest,original_blobs,current_blobs,selection=selection)
    roles=reviewed_roles(raw,manifest,original_blobs);fixed=set(roles['protected'])
    paths={('route:'+p['path_id']):p for p in report['admitted_paths']}
    blocked={sid for sid,p in paths.items() if fixed.intersection(p['source_ids'])}
    # Preserve the complete parallel-group constraint. A fixed member keeps its
    # entire group at original width; no primitive/path/group is shortened.
    groups=[];held=set(blocked)
    for group in report['groups']:
        if set(group['members'])&blocked:held.update(group['members'])
        else:groups.append(group)
    for row in report['paths']:
        p=row.get('path')
        if p and 'route:'+p['path_id'] in held:
            row['disposition']='KEEP_REVIEWED_BULK' if 'route:'+p['path_id'] in blocked else 'KEEP_GROUP_WITH_REVIEWED_BULK'
            row['reason']='Owner-reviewed original bulk contributor remains fixed; no group splitting or clearance exemption'
            row['reviewed_bulk_source_ids']=sorted(fixed.intersection(p['source_ids']))
    admitted=[p for p in report['admitted_paths'] if 'route:'+p['path_id'] not in held]
    members={s for p in admitted for s in p['source_ids']}
    report.update(admitted_paths=admitted,groups=groups,protected_source_ids=sorted(set(original_blobs)-members),
                  classifications=dict(Counter(r['disposition'] for r in report['paths'])),reviewed_source_roles=roles)
    if members&fixed:raise ValueError('U04_FIXED_BULK_ADMITTED')
    return report
