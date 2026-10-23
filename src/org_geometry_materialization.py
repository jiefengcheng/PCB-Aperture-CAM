"""Immutable, ORG-only native geometry materialization and fresh-process verifier."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

from .ingestion_files import sha, write_json
from .native_inventory import inventory
from .revision_catalog import RevisionCatalog, canonical, digest

SCHEMA = 'pcb-org-native-geometry-materialization/1'
RECEIPT_SCHEMA = 'pcb-org-native-geometry-acceptance/1'
SOURCE_RELATIVE = 'dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb'
EXPECTED_DATASET_ID = 'client:szu-comm:3020301113b:intake-20261021:v1'
EXPECTED_SOURCE_SHA256 = '850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0'


def _safe_out(root: Path, bundle: Path) -> Path:
    root = root.resolve()
    bundle = bundle.resolve()
    if not bundle.is_relative_to(root / 'out'):
        raise ValueError('ORG geometry bundle must be under checkout/out')
    return bundle


def _coverage(objects):
    rows = []
    for row in objects:
        for layer in row.get('layers', []):
            rows.append((row['kind'], layer, row['coverage']))
    counts = Counter(rows)
    return {f'{kind}|{layer}|{status}': counts[(kind, layer, status)]
            for kind, layer, status in sorted(counts)}


def build_org_geometry_materialization(root, *, source_relative=SOURCE_RELATIVE,
                                       dataset_id=EXPECTED_DATASET_ID,
                                       expected_source_sha256=EXPECTED_SOURCE_SHA256,
                                       output):
    """Read and persist one pinned ORG KiCad board; no EDIT path is accepted."""
    root = Path(root).resolve()
    if source_relative != SOURCE_RELATIVE or dataset_id != EXPECTED_DATASET_ID:
        raise ValueError('This bounded run is pinned to the sealed SZU-comm ORG board')
    if not re.fullmatch(r'[0-9a-f]{64}', expected_source_sha256 or ''):
        raise ValueError('Invalid expected ORG source hash')
    source_path = root / source_relative
    if source_path.is_symlink() or not source_path.resolve().is_relative_to(root / 'dataset'):
        raise ValueError('ORG source must be a regular file under checkout/dataset')
    if not source_path.is_file():
        raise ValueError('Pinned ORG source is unavailable')
    raw = source_path.read_bytes()
    source_hash = sha(source_path)
    if source_hash != expected_source_sha256:
        raise ValueError('Pinned ORG source hash mismatch')

    output = _safe_out(root, Path(output))
    if output.exists():
        raise ValueError('ORG geometry materialization is immutable; output already exists')
    parsed = inventory(raw)
    implementation_hash = sha(Path(__file__))
    config = {
        'kind': 'org-native-geometry-materialization/1',
        'dataset_id': dataset_id,
        'source_path': source_relative,
        'source_sha256': source_hash,
        'extractor': parsed.get('version', 'native-inventory/2'),
        'implementation_sha256': implementation_hash,
        'geometry_policy': 'native_inventory_geometry_v1; filled circles and polygons accept fill yes or solid',
        'coverage': 'Source-located ORG KiCad inventory only; no EDIT, Gerber, family recognition, or electrical inference',
    }
    output.mkdir(parents=True)
    try:
        with RevisionCatalog(output / 'store') as catalog:
            for key, payload in parsed.get('payloads', {}).items():
                if catalog.put_payload(payload) != key:
                    raise ValueError('ORG geometry payload hash mismatch')
            revision = catalog.import_revision(raw, parsed['objects'], [], config)
        manifest = {
            'schema': SCHEMA,
            'dataset_id': dataset_id,
            'source': {'path': source_relative, 'sha256': source_hash, 'bytes': len(raw)},
            'revision': revision,
            'extractor': config['extractor'],
            'implementation_sha256': implementation_hash,
            'object_count': len(parsed['objects']),
            'geometry_payload_count': len(parsed.get('payloads', {})),
            'geometry_available_count': sum(bool(row.get('geometry_sha256')) for row in parsed['objects']),
            'coverage_counts': _coverage(parsed['objects']),
            'unsupported_reasons': parsed.get('unsupported_reasons', {}),
            'warnings': parsed.get('warnings', []),
            'qualification': 'NOT_RUN',
            'engineering_acceptance': 'NOT_ESTABLISHED',
            'scope': 'ORG-only native geometry persistence and retrieval; not land recognition or family mapping',
        }
        write_json(output / 'materialization.json', manifest)
        return manifest
    except Exception:
        import shutil
        shutil.rmtree(output, ignore_errors=True)
        raise


def reopen_org_geometry_materialization(root, bundle):
    root = Path(root).resolve()
    bundle = _safe_out(root, Path(bundle))
    manifest = json.loads((bundle / 'materialization.json').read_text())
    if manifest.get('schema') != SCHEMA or manifest.get('dataset_id') != EXPECTED_DATASET_ID:
        raise ValueError('Invalid ORG geometry materialization identity')
    source = manifest.get('source') or {}
    if source.get('path') != SOURCE_RELATIVE or source.get('sha256') != EXPECTED_SOURCE_SHA256:
        raise ValueError('ORG geometry source binding mismatch')
    source_path = root / source['path']
    if source_path.is_symlink() or not source_path.is_file() or sha(source_path) != source['sha256']:
        raise ValueError('Pinned ORG source changed before reopen')

    with RevisionCatalog(bundle / 'store', read_only=True) as catalog:
        snapshot = catalog.snapshot(manifest['revision'])
        if snapshot['source_sha256'] != source['sha256'] or len(snapshot['objects']) != manifest['object_count']:
            raise ValueError('Reopened ORG revision differs from materialization manifest')
        if snapshot['relations']:
            raise ValueError('ORG geometry materialization unexpectedly contains relations')
        by_coverage = _coverage(snapshot['objects'])
        if by_coverage != manifest['coverage_counts']:
            raise ValueError('ORG geometry coverage differs after reopen')
        geometry_count = 0
        for row in snapshot['objects']:
            if row.get('geometry_sha256'):
                payload = catalog.read_payload(row['geometry_sha256'])
                if digest(payload) != row['geometry_sha256']:
                    raise ValueError('ORG geometry payload hash mismatch')
                geometry_count += 1
        if geometry_count != manifest['geometry_available_count']:
            raise ValueError('ORG geometry payload count differs after reopen')
        collected = []
        after = None
        while True:
            page = catalog.query(manifest['revision'], limit=1000, after_id=after,
                                 expected_snapshot=manifest['revision'], result_byte_limit=32*1024*1024)
            if page['status'] not in ('COMPLETE', 'TRUNCATED', 'TRUNCATED_BYTE_BUDGET'):
                raise ValueError('ORG catalogue query failed: ' + page['status'])
            collected.extend(page['records'])
            if page['status'] == 'COMPLETE':
                break
            next_after = page.get('next_after_id')
            if not next_after or next_after == after:
                raise ValueError('ORG catalogue pagination made no progress')
            after = next_after
        if collected != snapshot['objects']:
            raise ValueError('Fresh ORG query differs from stored revision')
        # Check the bounded shapes directly in the reopened object rows.
        expected_shapes = {
            'gr_circle|F.Cu': 1541,
            'gr_poly|F.Cu': 450,
            'gr_circle|F.Mask': 139,
            'gr_poly|F.Mask': 247,
            'gr_circle|F.Paste': 88,
            'gr_poly|F.Paste': 243,
        }
        recovered = Counter()
        for row in collected:
            if row.get('geometry_sha256'):
                for layer in row.get('layers', []):
                    if row['kind'] in ('gr_circle', 'gr_poly') and layer in ('F.Cu', 'F.Mask', 'F.Paste'):
                        recovered[f"{row['kind']}|{layer}"] += 1
        if dict(recovered) != expected_shapes:
            raise ValueError('Recovered filled-shape counts differ from expected ORG counts')
        return {
            'schema': SCHEMA,
            'status': 'PASS',
            'dataset_id': manifest['dataset_id'],
            'source_sha256': source['sha256'],
            'revision': manifest['revision'],
            'object_count': len(collected),
            'geometry_available_count': geometry_count,
            'filled_shape_geometry_counts': dict(sorted(recovered.items())),
            'coverage_counts_sha256': digest(canonical(by_coverage)),
            'reader_pid': os.getpid(),
            'fresh_read_only_process': True,
            'edit_input': 'NOT_PRESENT',
        }


def accept_org_geometry_materialization(root, *, output):
    root = Path(root).resolve()
    bundle = _safe_out(root, Path(output))
    manifest = build_org_geometry_materialization(root, output=bundle)
    command = [sys.executable, str(root / 'tools/materialize_org_geometry.py'),
               'reopen', '--bundle', str(bundle)]
    run = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False,
                         env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if run.returncode != 0:
        raise ValueError('Fresh-process ORG reopen failed: ' + (run.stderr or run.stdout)[-1600:])
    reopened = json.loads(run.stdout)
    if reopened.get('status') != 'PASS' or reopened.get('reader_pid') == os.getpid():
        raise ValueError('ORG geometry was not verified in a distinct fresh process')
    write_json(bundle / 'reopened.json', reopened)
    outputs = {'materialization.json': sha(bundle / 'materialization.json'),
               'reopened.json': sha(bundle / 'reopened.json'),
               'store/catalog.sqlite': sha(bundle / 'store/catalog.sqlite')}
    for path in sorted((bundle / 'store/payloads').iterdir()):
        if path.is_file():
            outputs[path.relative_to(bundle).as_posix()] = sha(path)
    receipt = {
        'schema': RECEIPT_SCHEMA,
        'status': 'PASS',
        'dataset_id': manifest['dataset_id'],
        'source_sha256': manifest['source']['sha256'],
        'revision': manifest['revision'],
        'object_count': manifest['object_count'],
        'geometry_available_count': manifest['geometry_available_count'],
        'reader_pid': reopened['reader_pid'],
        'outputs': outputs,
        'qualification': 'NOT_RUN',
        'engineering_acceptance': 'NOT_ESTABLISHED',
    }
    write_json(bundle / 'acceptance.json', receipt)
    verify_org_geometry_materialization(root, bundle, require_acceptance=True)
    return receipt


def verify_org_geometry_materialization(root, bundle, *, require_acceptance=True):
    root = Path(root).resolve()
    bundle = _safe_out(root, Path(bundle))
    receipt_path = bundle / 'acceptance.json'
    if require_acceptance and not receipt_path.is_file():
        raise ValueError('ORG geometry acceptance receipt missing')
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text())
        if receipt.get('schema') != RECEIPT_SCHEMA or receipt.get('status') != 'PASS':
            raise ValueError('ORG geometry acceptance receipt failed')
        for relative, expected in receipt.get('outputs', {}).items():
            output = (bundle / relative).resolve()
            if not output.is_relative_to(bundle) or not output.is_file() or sha(output) != expected:
                raise ValueError('ORG geometry output hash mismatch: ' + relative)
    return reopen_org_geometry_materialization(root, bundle)
