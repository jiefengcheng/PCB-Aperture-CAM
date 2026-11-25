"""Explicit T04 preservation floor after authenticated subtractive cleanup.

Raw original refs remain immutable provenance. Only the constructor's geometric
floor changes to the verified stage entry; no T03 acceptance is synthesized.
"""
import gzip
import json
from pathlib import Path
from shapely import from_wkb, to_wkb
from . import pipeline as p
from .group_board_job import file_sha


def load_cleanup(result_path, source_sha):
    result_path = Path(result_path).resolve()
    result = json.loads(result_path.read_bytes())
    ref = result['stage']
    if file_sha(ref['path']) != ref['sha256']:
        raise ValueError('T04_CLEANUP_CONSTRUCTION_CHANGED')
    raw = gzip.decompress(Path(ref['path']).read_bytes())
    if p.digest(raw) != ref['stage_sha256']:
        raise ValueError('T04_CLEANUP_CANONICAL_BYTES_CHANGED')
    stage = json.loads(raw)
    if (result['source']['sha256'] != source_sha or
            stage['operation'] != 'TRIM_ONLY' or
            stage['trim_only_phase']['positive_copper_mm2'] > p.EPS or
            not stage['trim_only_phase']['passed']):
        raise ValueError('T04_VERIFIED_SUBTRACTIVE_PREDECESSOR_REQUIRED')
    mapping = dict(stage['hybrid_components']['continuous_source_bodies'])
    mapping.update(stage['hybrid_components']['changed_bulk_copper'])
    return stage, {s: from_wkb(bytes.fromhex(v['wkb_hex'])) for s,v in mapping.items()}, dict(
        report=dict(path=str(result_path), sha256=file_sha(result_path)), construction=ref,
        source_sha256=source_sha, counts=result['counts'])


def bind_floor(rows, current, original, custody):
    if tuple(current) != tuple(original) or set(rows) != set(current):
        raise ValueError('T04_TRIMMED_ENTRY_INVENTORY_CHANGED')
    for sid in current:
        if current[sid].difference(original[sid]).area > p.EPS:
            raise ValueError('T04_TRIMMED_ENTRY_HAS_ADDITIONS')
    return dict(custody, schema='t04-verified-trimmed-entry/1',
        original_fingerprints={s:p.digest(to_wkb(g)) for s,g in original.items()},
        entry_fingerprints={s:p.digest(to_wkb(g)) for s,g in current.items()})


def constructor_operands(loaded, receipt):
    rows, current, original = loaded
    if receipt.get('schema') != 't04-verified-trimmed-entry/1':
        raise ValueError('T04_TRIMMED_ENTRY_RECEIPT_REQUIRED')
    for shapes, field in ((original,'original_fingerprints'),(current,'entry_fingerprints')):
        if {s:p.digest(to_wkb(g)) for s,g in shapes.items()} != receipt[field]:
            raise ValueError('T04_TRIMMED_ENTRY_OPERANDS_CHANGED')
    return rows, current, current


def sealed_subtractive_entry(store,scene):
    """Identify the exact sealed trim output, without inventing prior growth.

    The runner authenticates the complete pinned file closure before/after
    execution. Here the phase type and ordered entry identities determine
    whether a prior additive-reference reservation is applicable at all.
    """
    if scene is None or [v.get('stage')for v in scene.get('lineage',[])]!=[
            'gerber-source-intake','verified-large-copper-trim-entry']:return False
    receipt=store.get_json(scene['lineage'][-1]['receipt_ref'],kind='t04-trimmed-entry')
    ref=receipt.get('seal')
    if ref is None:return False
    from src.copper_phase_seal import SCHEMA,read_file
    raw=read_file(ref['path'])
    if p.digest(raw)!=ref['sha256']:raise ValueError('T04_SUBTRACTIVE_ENTRY_SEAL_CHANGED')
    seal=json.loads(raw)
    ledger=[[r['source_id'],r['geometry_ref']['sha256']]for r in scene['objects']]
    if (seal['schema']!=SCHEMA or seal['phase']!='large_copper'or seal['parent']is not None or
            receipt.get('schema')!='t04-verified-trimmed-entry/1'or
            seal['source_sha256']!=scene['source_sha256']or receipt['source_sha256']!=scene['source_sha256']or
            seal['output_geometry_sha256']!=p.digest(p.canonical(ledger))):
        raise ValueError('T04_SUBTRACTIVE_ENTRY_BINDING_CHANGED')
    return True


def operands(store, scene):
    """Read exact cleanup tombstones without weakening positive-only geometry.

    Growing positive contributions use the ordinary reader. A zero contribution
    must match the authenticated entry bytes and may never restore raw copper.
    """
    entries=[v for v in scene['lineage']if v.get('stage')=='verified-large-copper-trim-entry']
    receipt=store.get_json(entries[-1]['receipt_ref'],kind='t04-trimmed-entry')
    if receipt.get('schema')!='t04-verified-trimmed-entry/1' or receipt['source_sha256']!=scene['source_sha256']:
        raise ValueError('T04_TRIMMED_ENTRY_RECEIPT_REQUIRED')
    rows={r['source_id']:r for r in scene['objects']}; current={}; original={}
    if set(rows)!=set(receipt['entry_fingerprints']):raise ValueError('T04_TRIMMED_ENTRY_INVENTORY_CHANGED')
    for sid,row in rows.items():
        original[sid]=p.geometry(store,row['original_ref'])
        if p.digest(to_wkb(original[sid]))!=receipt['original_fingerprints'][sid]:
            raise ValueError('T04_TRIMMED_ENTRY_ORIGINAL_CHANGED')
        raw=store.get(row['geometry_ref'],kind='geometry'); g=from_wkb(raw)
        if g.is_empty:
            if not g.is_valid or g.geom_type not in ('Polygon','MultiPolygon') or p.digest(raw)!=receipt['entry_fingerprints'][sid]:
                raise ValueError('T04_UNAUTHORIZED_EMPTY_CONTRIBUTION')
            current[sid]=g
        else:current[sid]=p.geometry(store,row['geometry_ref'])
    return rows,current,original
