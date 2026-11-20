"""Explicit zero contribution for an authorized, completely removed bulk source.

Original IDs, source kinds and immutable original refs remain present. Ordinary
geometry validation stays positive-only; only this T04 ledger-aware reader can
accept a zero current contribution. Downstream replay/export remains blocked.
"""
from shapely import from_wkb
from src.stage_abi.scene import geometry
from src.stage_abi.store import canonical,digest

SCHEMA='t04-source-role-limiting-growth/2'
STAGE='t04-limiting-entry-v2'


def operands(store,scene):
    entries=[v for v in scene['lineage'] if v.get('stage')==STAGE]
    if not entries:raise ValueError('T04_BULK_TOMBSTONE_AUTHORITY_MISSING')
    receipt=store.get_json(entries[-1]['receipt_ref'],kind='t04-source-projection-entry')
    if receipt['schema']!=SCHEMA or receipt['source_sha256']!=scene['source_sha256']:
        raise ValueError('T04_BULK_TOMBSTONE_SOURCE_CHANGED')
    rows={r['source_id']:r for r in scene['objects']};current={};original={}
    removed=receipt['removed_bulk_sources']
    for sid,row in rows.items():
        original[sid]=geometry(store,row['original_ref'])
        marker=row['metadata'].get('removed_bulk_source')
        if marker is None:
            if sid in removed:raise ValueError('T04_BULK_TOMBSTONE_RECORD_MISSING')
            current[sid]=geometry(store,row['geometry_ref']);continue
        if row['kind']!='stroke' or sid not in receipt['bulk_roles'] or marker!=removed.get(sid):
            raise ValueError('T04_BULK_TOMBSTONE_ROLE_CHANGED')
        if marker['schema']!=SCHEMA or marker['source_id']!=sid or marker['original_ref']!=row['original_ref'] or marker['after_ref']!=row['geometry_ref']:
            raise ValueError('T04_BULK_TOMBSTONE_GEOMETRY_BINDING_CHANGED')
        if marker['role_witness_sha256']!=digest(canonical(receipt['bulk_roles'][sid])):
            raise ValueError('T04_BULK_TOMBSTONE_WITNESS_CHANGED')
        g=from_wkb(store.get(row['geometry_ref'],kind='geometry'))
        if not g.is_empty or not g.is_valid or g.geom_type not in ('Polygon','MultiPolygon'):
            raise ValueError('T04_BULK_TOMBSTONE_MUST_BE_ZERO_CONTRIBUTION')
        current[sid]=g
    if not set(removed)<=set(rows):raise ValueError('T04_BULK_TOMBSTONE_SOURCE_ID_MISSING')
    return rows,current,original
