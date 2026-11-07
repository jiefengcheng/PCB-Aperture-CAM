"""One source-bound stage assignment shared by Gerber growth consumers.

Native plotting syntax and growth authority are separate. In particular a
compact rectangular draw is a T02 land, never a T04 widening target. The
catalogue changes no copper and grants no clearance or pin-slot exemption.
"""
from collections import Counter
from src.stage_abi.store import canonical,digest

SCHEMA='gerber-source-growth-catalogue/1'


def assignment(row):
    kind=row['kind'];md=row['metadata'];terminal=md.get('rectangle_terminal')
    if terminal and(kind!='rectangle'or not md.get('qualified_land')):
        raise ValueError('T02_TERMINAL_EXCLUSIVE_AUTHORITY_CHANGED')
    owner={'circle':'T01','rectangle':'T02','stroke':'T04'}.get(kind,'FIXED')
    return dict(schema=SCHEMA,source_id=row['source_id'],original_geometry_sha256=row['original_ref']['sha256'],
                source_kind=md.get('source_kind'),geometry_family=kind,growth_owner=owner,
                family=terminal['family']if terminal else'original-'+kind,
                t03='VERIFY_NATIVE_DRAW'if md.get('source_kind')in('Line','Arc')else'FIXED_CONTEXT',
                t04='ELIGIBLE_TRACE'if owner=='T04'else'EXCLUDED_OTHER_SOURCE_FAMILY',
                t02='ELIGIBLE_RECTANGLE'if owner=='T02'else'FIXED_CONTEXT',
                t05='SOURCE_LAND_ATTACHMENT'if md.get('qualified_land')else'SOURCE_ROUTE_ATTACHMENT'if owner=='T04'else'FIXED_CONTEXT')


def record(row):
    value=assignment(row)
    row['metadata']['growth_authority']=dict(value,binding_sha256=digest(canonical(value)))
    return row['metadata']['growth_authority']


def authority(row):
    value=row['metadata'].get('growth_authority')
    if value is None:
        # Existing scenes/ABI fixtures retain their original family contract.
        # Newly recognized native terminals require the explicit catalogue.
        if row['metadata'].get('rectangle_terminal'):raise ValueError('T02_TERMINAL_CATALOGUE_REQUIRED')
        return assignment(row)
    expected=assignment(row)
    if value!=dict(expected,binding_sha256=digest(canonical(expected))):
        raise ValueError('SOURCE_GROWTH_AUTHORITY_CHANGED:'+row['source_id'])
    return expected


def native_draw(row):
    value=authority(row)
    return value['t03']=='VERIFY_NATIVE_DRAW'or row['kind']=='stroke'


def t04_trace(row):
    return authority(row)['growth_owner']=='T04'


def t02_land(row):
    return authority(row)['growth_owner']=='T02'


def t05_land(row):
    if row['kind']=='inclusive_rectangle':return True
    return authority(row)['t05']=='SOURCE_LAND_ATTACHMENT'


def catalogue(scene):
    records=[authority(row)for row in scene['objects']]
    return dict(schema=SCHEMA,source_sha256=scene['source_sha256'],records=records,
                owner_counts=dict(sorted(Counter(r['growth_owner']for r in records).items())),
                policy='EXCLUSIVE_SOURCE_GROWTH_OWNER; original drawing and attachment provenance retained')
