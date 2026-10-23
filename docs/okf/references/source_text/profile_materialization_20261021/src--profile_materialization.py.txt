"""Materialize source-located KiCad/Gerber records from a sealed intake profile.

This is a read-only extraction path: parser warnings and unsupported geometry
remain attached to source revisions; no cross-source qualification is inferred.
"""
from __future__ import annotations

from collections import defaultdict
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import warnings

from gerbonara.rs274x import GerberFile, GerberParser
from shapely import affinity

from .dataset_profiler import verify_profile
from .gerber_image import object_geometry
from .ingestion_files import local, sha, verify, write_json
from .native_inventory import inventory as native_inventory
from .revision_catalog import RevisionCatalog, canonical, digest

SCHEMA = 'pcb-profile-record-materialization/1'
RUN_SCHEMA = 'pcb-profile-materialization-acceptance/1'
GERBER_COMMAND_RE = re.compile(r'G04.*?\*\s*|%.*?%\s*|[^*%]*\*\s*', re.DOTALL)


def _json_value(value):
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class _LocatedGerberParser(GerberParser):
    """Keep byte spans for every plotting command emitted by Gerbonara."""
    def __init__(self, target):
        super().__init__(target)
        self.current_span = None
        self.feature_spans = {}

    def _split_commands(self, data):
        self.lineno = 1
        for match in GERBER_COMMAND_RE.finditer(data):
            raw = match[0]
            command = raw.strip().strip('%').rstrip('*')
            if command:
                leading = len(raw) - len(raw.lstrip())
                self.current_span = [match.start() + leading, match.start() + leading + len(command)]
                self.line = command
                yield command
            self.lineno += raw.count('\n')
        self.lineno = 0
        self.line = ''

    def _parse_coord(self, match):
        before = len(self.target.objects)
        super()._parse_coord(match)
        for index in range(before, len(self.target.objects)):
            self.feature_spans[index] = list(self.current_span) if self.current_span else None


def _warning_span(text, line_number):
    if not isinstance(line_number, int) or line_number < 1:
        return None
    start = 0
    for _ in range(line_number - 1):
        found = text.find('\n', start)
        if found < 0:
            return None
        start = found + 1
    end = text.find('\n', start)
    if end < 0:
        end = len(text)
    return [start, end]


def _gerber_inventory(raw, relative_path):
    """Parse Gerber commands, grouping emitted objects by their exact trigger."""
    source_sha = digest(raw)
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError as error:
        return {'source_sha256': source_sha, 'source_objects': [], 'payloads': {},
                'status': 'PARSE_FAILED', 'warnings': [{'severity': 'ERROR', 'code': 'NON_ASCII_SOURCE',
                    'message': str(error), 'source_span': [error.start, error.end]}],
                'file_attributes': {}, 'unit': None, 'coordinate_format': None, 'eof_found': False}

    parsed = GerberFile()
    parser = _LocatedGerberParser(parsed)
    caught = []
    error_row = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:
            parser.parse(text, filename=relative_path)
        except Exception as error:
            span = parser.current_span
            error_row = {'severity': 'ERROR', 'code': type(error).__name__, 'message': str(error),
                         'source_span': span}

    issues = [{'severity': 'WARNING', 'code': item.category.__name__, 'message': str(item.message),
               'source_span': _warning_span(text, item.lineno)} for item in caught]
    if error_row:
        issues.append(error_row)

    grouped = defaultdict(list)
    unlocated = 0
    for index, obj in enumerate(parsed.objects):
        span = parser.feature_spans.get(index)
        if not span or not (0 <= span[0] < span[1] <= len(raw)):
            unlocated += 1
            continue
        grouped[tuple(span)].append(obj)

    records = []
    for (start, end), objects in sorted(grouped.items()):
        shapes = []
        shape_errors = []
        for obj in objects:
            try:
                shape = object_geometry(obj)
                shape = affinity.scale(shape, 1, -1, origin=(0, 0))
                if shape.is_empty or not shape.is_valid:
                    raise ValueError('INVALID_OR_EMPTY_GEOMETRY')
                shapes.append(shape)
            except Exception as error:
                shape_errors.append(type(error).__name__ + ': ' + str(error))
        bounds = None
        if shapes:
            bounds = [min(s.bounds[0] for s in shapes), min(s.bounds[1] for s in shapes),
                      max(s.bounds[2] for s in shapes), max(s.bounds[3] for s in shapes)]
        kinds = sorted({type(obj).__name__ for obj in objects})
        attrs = [_json_value(getattr(obj, 'attrs', {})) for obj in objects]
        dark = sorted({bool(getattr(obj, 'polarity_dark', True)) for obj in objects})
        row = {'id': f'{source_sha}:bytes:{start}:{end}', 'source_sha256': source_sha,
               'source_span': [start, end], 'parent_id': None, 'native_id': None,
               'representation': 'gerber', 'kind': 'gerber_command_features',
               'primitive_types': kinds, 'primitive_count': len(objects),
               'attributes': attrs, 'polarity_dark_values': dark,
               'layer_function': _json_value(parsed.file_attrs.get('.FileFunction')),
               'layer_role': 'UNRESOLVED_FROM_SOURCE_ATTRIBUTES',
               'position_mm': None, 'endpoints_mm': None, 'bounds_mm': bounds,
               'geometry_sha256': None, 'geometry_basis': 'Maintained Gerbonara primitive bounds; exact WKB not persisted',
               'coverage': 'BOUNDS_ONLY' if shapes else 'UNSUPPORTED',
               'unsupported_reason': sorted(set(shape_errors)) or None,
               'qualification_refs': [], 'match_refs': [],
               'source_label': relative_path}
        records.append(row)
    if unlocated:
        issues.append({'severity': 'WARNING', 'code': 'FEATURE_SOURCE_LOCATION_UNAVAILABLE',
                       'message': f'{unlocated} parsed primitives had no command byte span', 'source_span': None})
    if error_row:
        status = 'PARSED_PARTIAL'
    elif issues:
        status = 'PARSED_WITH_WARNINGS'
    else:
        status = 'PARSED'
    return {'source_sha256': source_sha, 'source_objects': records, 'payloads': {}, 'status': status,
            'warnings': issues, 'file_attributes': _json_value(parsed.file_attrs),
            'unit': str(parsed.unit) if parsed.unit is not None else None,
            'coordinate_format': _json_value(getattr(parsed.import_settings, 'number_format', None)),
            'eof_found': parser.eof_found, 'unlocated_primitives': unlocated}


def _native_result(raw):
    try:
        result = native_inventory(raw)
        issues = [{'severity': 'WARNING', 'code': code, 'count': count,
                   'message': 'Native geometry or layer coverage remains explicit on source records'}
                  for code, count in sorted(result['unsupported_reasons'].items() if 'unsupported_reasons' in result else [])]
        return result, issues, 'PARSED_WITH_WARNINGS' if issues else 'PARSED'
    except Exception as error:
        return {'source_sha256': digest(raw), 'objects': [], 'payloads': {}, 'counts': {},
                'geometry_available': 0, 'unsupported_reasons': {}}, [
                    {'severity': 'ERROR', 'code': type(error).__name__, 'message': str(error),
                     'source_span': None}], 'PARSE_FAILED'


def _artifact_paths(bundle):
    result = [p for p in Path(bundle).rglob('*') if p.is_file()]
    return sorted(result, key=lambda p: p.relative_to(bundle).as_posix())


def _revision_side(relative_path):
    parts = PurePosixPath(relative_path).parts
    return {'ORG': 'before', 'EDIT': 'after'}.get(parts[0].upper()) if len(parts) > 1 else None


def build_materialization(root, package_root, dataset_id, output):
    root = Path(root).resolve()
    package = local(root, package_root)
    output = Path(output).resolve()
    if not output.is_relative_to(root / 'out') or output.exists():
        raise ValueError('Materialization output must be a new directory under checkout/out')
    profile_result = verify_profile(package)
    profile = json.loads((package / 'metadata/profile.json').read_text())
    recipe = json.loads((package / 'metadata/registration_recipe.json').read_text())
    if profile.get('dataset_id') != dataset_id or recipe.get('dataset', {}).get('id') != dataset_id:
        raise ValueError('Selected dataset does not match the sealed profile identity')
    if recipe.get('package_root') != package.relative_to(root).as_posix():
        raise ValueError('Sealed package root differs from the registered profile location')
    file_rows = profile.get('files')
    if not isinstance(file_rows, list):
        raise ValueError('Sealed profile has no source file inventory')
    raw_sources = []
    for row in file_rows:
        package_path = package / 'raw' / PurePosixPath(row['path'])
        if not package_path.is_file() or sha(package_path) != row['sha256'] or package_path.stat().st_size != row['bytes']:
            raise ValueError('Sealed source changed: ' + row['path'])
        suffix = PurePosixPath(row['path']).suffix.lower()
        if suffix in ('.kicad_pcb', '.gbr'):
            raw_sources.append((row, package_path.read_bytes(), suffix))
    if not raw_sources:
        raise ValueError('No supported KiCad board or Gerber source files are present in this profile')

    output.mkdir(parents=True)
    catalog_root = output / 'store'
    artifacts = []
    native_pair = {}
    side_by_path = {row['path']: _revision_side(row['path']) for row, _, _ in raw_sources}
    try:
        with RevisionCatalog(catalog_root) as catalog:
            for row, raw, suffix in raw_sources:
                relative = row['path']
                if suffix == '.kicad_pcb':
                    parsed, issues, status = _native_result(raw)
                    objects = parsed['objects']
                    side = side_by_path.get(relative)
                    native_pair[side or relative] = {
                        'path': relative, 'sha256': row['sha256'], 'status': status,
                        'object_count': len(objects), 'counts': parsed.get('counts', {}),
                        'layer_instance_counts': parsed.get('layer_instance_counts', {}),
                        'unsupported_reasons': parsed.get('unsupported_reasons', {}),
                        'pad_records': sum(obj.get('kind') == 'pad' for obj in objects),
                        'footprint_references': sorted({obj['reference'] for obj in objects if obj.get('reference')}),
                        'net_names': sorted({obj['net_name'] for obj in objects if obj.get('net_name')}),
                    }
                    for key, payload in parsed.get('payloads', {}).items():
                        if catalog.put_payload(payload) != key:
                            raise ValueError('Native geometry content hash mismatch')
                    config = {'kind': 'sealed-native-board-inventory/1', 'source_path': relative,
                              'source_sha256': row['sha256'], 'profile_sha256': profile_result['seal_sha256'],
                              'extractor': parsed.get('version', 'native-inventory/2'),
                              'coverage': 'All recognized source-located native inventory records; unsupported geometry retained per record',
                              'unsupported_reasons': parsed.get('unsupported_reasons', {}),
                              'counts': parsed.get('counts', {})}
                else:
                    parsed = _gerber_inventory(raw, relative)
                    issues = parsed['warnings'];status = parsed['status']
                    objects = parsed['source_objects']
                    config = {'kind': 'sealed-gerber-command-inventory/1', 'source_path': relative,
                              'source_sha256': row['sha256'], 'profile_sha256': profile_result['seal_sha256'],
                              'extractor': 'Gerbonara ' + importlib.metadata.version('gerbonara'),
                              'coverage': 'Source-located plotting-command records with primitive bounds only; layer role and feature geometry not qualified',
                              'parse_status': status, 'warnings': issues,
                              'file_attributes': parsed.get('file_attributes', {}),
                              'unit': parsed.get('unit'), 'coordinate_format': parsed.get('coordinate_format'),
                              'eof_found': parsed.get('eof_found')}
                revision = catalog.import_revision(raw, objects, [], config)
                snapshot = catalog.snapshot(revision)
                artifacts.append({'path': relative, 'side': side_by_path.get(relative),
                                  'sha256': row['sha256'], 'bytes': row['bytes'],
                                  'format': 'KiCad' if suffix == '.kicad_pcb' else 'Gerber',
                                  'revision': revision, 'source_objects': len(objects),
                                  'geometry_available': sum(bool(obj.get('geometry_sha256')) for obj in objects),
                                  'bounds_available': sum(bool(obj.get('bounds_mm')) for obj in objects),
                                  'status': status, 'warnings': issues,
                                  'queryable_objects': len(snapshot['objects'])})
        paired = {'before': native_pair.get('before'), 'after': native_pair.get('after')}
        pair_status = 'PAIR_PRESENT' if paired['before'] and paired['after'] else 'PAIR_INCOMPLETE'
        result = {'schema': SCHEMA, 'dataset_id': dataset_id,
                  'package_root': package.relative_to(root).as_posix(),
                  'package_seal': {'path': (package / 'SHA256SUMS').relative_to(root).as_posix(),
                                   'sha256': profile_result['seal_sha256']},
                  'profile': {'path': (package / 'metadata/profile.json').relative_to(root).as_posix(),
                              'sha256': sha(package / 'metadata/profile.json'),
                              'tree_sha256': profile['intake']['tree_sha256']},
                  'comparison_intent': {
                      'objective': 'Compare one before revision with one after revision; inspect copper-area expansion and retain terminal, pad, and connection context.',
                      'pairing': {'before': 'ORG', 'after': 'EDIT',
                                  'basis': 'sealed source directory names; no source bytes relabelled'},
                      'status': pair_status,
                      'native_revision_summaries': paired,
                      'copper_delta_status': 'NOT_ESTABLISHED: source layer identities and a qualified same-coordinate copper image are required',
                      'terminal_pad_connection_status': 'NOT_FOUND_IN_NATIVE_INVENTORY' if paired['before'] and paired['after'] and not any(x.get('pad_records') or x.get('footprint_references') or x.get('net_names') for x in native_pair.values()) else 'PARTIAL_OR_PRESENT',
                      'warning': 'Native source inventory records board primitives but does not infer terminal identity or electrical connectivity from absent pad/reference/net records.'},
                  'artifacts': artifacts, 'artifact_count': len(artifacts),
                  'source_objects': sum(row['source_objects'] for row in artifacts),
                  'geometry_available': sum(row['geometry_available'] for row in artifacts),
                  'warning_count': sum(len(row['warnings']) for row in artifacts),
                  'correspondence_status': 'NOT_RUN: no cross-source layer/coordinate mapping was inferred; before/after pairing uses sealed ORG and EDIT directory names only',
                  'qualification': 'NOT_RUN', 'engineering_acceptance': 'NOT_ESTABLISHED',
                  'parser_runtime': {'gerbonara': importlib.metadata.version('gerbonara'),
                                     'shapely': importlib.metadata.version('shapely')},
                  'scope': 'Read-only source inventory and persisted, source-located records; unsupported geometry and parser warnings remain explicit'}
        write_json(output / 'materialization.json', result)
        return output
    except Exception:
        import shutil
        shutil.rmtree(output, ignore_errors=True)
        raise


def _read_materialization(root, bundle, *, require_acceptance=True):
    root = Path(root).resolve();bundle = Path(bundle).resolve()
    if not bundle.is_relative_to(root / 'out'):
        raise ValueError('Materialization bundle must remain under checkout/out')
    materialization_path = bundle / 'materialization.json'
    materialization = json.loads(materialization_path.read_text())
    receipt_path = bundle / 'acceptance.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else None
    if require_acceptance and (not receipt or receipt.get('schema') != RUN_SCHEMA or receipt.get('status') != 'PASS'):
        raise ValueError('Materialization acceptance receipt is missing or failed')
    if materialization.get('schema') != SCHEMA or (receipt and materialization.get('dataset_id') != receipt.get('dataset_id')):
        raise ValueError('Materialization manifest identity mismatch')
    if require_acceptance:
        verify(bundle, [{'path': key, 'sha256': value} for key, value in receipt.get('outputs', {}).items()])
        expected_files = set(receipt.get('outputs', {})) | {'acceptance.json'}
        payload_root = bundle / 'store/payloads'
        expected_files.update(path.relative_to(bundle).as_posix() for path in payload_root.iterdir() if path.is_file())
        if expected_files != {path.relative_to(bundle).as_posix() for path in _artifact_paths(bundle)}:
            raise ValueError('Materialization bundle file inventory mismatch')
    package = local(root, materialization['package_root'])
    profile_result = verify_profile(package)
    if profile_result['seal_sha256'] != materialization['package_seal']['sha256']:
        raise ValueError('Source package seal changed after materialization')
    for binding in materialization['artifacts']:
        source = package / 'raw' / PurePosixPath(binding['path'])
        if sha(source) != binding['sha256']:
            raise ValueError('Bound source changed after materialization: ' + binding['path'])
    return receipt, materialization, bundle


def reopen_materialization(root, bundle, *, require_acceptance=False):
    receipt, materialization, bundle = _read_materialization(root, bundle, require_acceptance=require_acceptance)
    summaries = []
    expected_payloads = set()
    with RevisionCatalog(bundle / 'store', read_only=True) as catalog:
        for artifact in materialization['artifacts']:
            manifest = catalog.snapshot(artifact['revision'])
            if manifest['source_sha256'] != artifact['sha256'] or len(manifest['objects']) != artifact['source_objects']:
                raise ValueError('Reopened revision does not match its source and inventory: ' + artifact['path'])
            expected_payloads.add(manifest['source_sha256'])
            for row in manifest['objects']:
                if row.get('geometry_sha256'):
                    expected_payloads.add(row['geometry_sha256'])
                    payload = catalog.read_payload(row['geometry_sha256'])
                    if digest(payload) != row['geometry_sha256']:
                        raise ValueError('Stored geometry payload hash mismatch')
            collected = [];after = None
            while True:
                page = catalog.query(artifact['revision'], limit=1000, after_id=after,
                                     expected_snapshot=artifact['revision'], result_byte_limit=32*1024*1024)
                next_after = page.get('next_after_id')
                if page['status'] not in ('COMPLETE', 'TRUNCATED', 'TRUNCATED_BYTE_BUDGET'):
                    raise ValueError('Fresh-process query failed: ' + page['status'])
                if page['status'] != 'COMPLETE' and (not page['records'] or not next_after or next_after == after):
                    raise ValueError('Fresh-process pagination made no forward progress: ' + page['status'])
                collected.extend(page['records'])
                after = next_after
                if page['status'] == 'COMPLETE':
                    break
            if collected != manifest['objects'] or len(collected) != artifact['source_objects']:
                raise ValueError('Fresh-process query differs from persisted manifest: ' + artifact['path'])
            summaries.append({'path': artifact['path'], 'revision': artifact['revision'],
                              'records_returned': len(collected), 'result_sha256': digest(canonical(collected)),
                              'reader_pid': os.getpid(), 'complete': True})
    actual_payloads = {path.name for path in (bundle / 'store/payloads').iterdir() if path.is_file()}
    if actual_payloads != expected_payloads:
        raise ValueError('Content-addressed payload inventory differs from persisted revisions')
    return {'schema': SCHEMA, 'status': 'PASS', 'dataset_id': materialization['dataset_id'],
            'package_seal_sha256': materialization['package_seal']['sha256'],
            'source_revisions': summaries,
            'total_records_returned': sum(row['records_returned'] for row in summaries),
            'reader_pid': os.getpid(), 'backend': 'SQLite revision catalogue; fresh read-only process'}


def accept_materialization(root, package_root, dataset_id, output):
    output = Path(output).resolve()
    bundle = build_materialization(root, package_root, dataset_id, output)
    result_path = bundle / 'reopened.json'
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'tools/materialize_profile.py'),
               'reopen', '--bundle', str(bundle)]
    run = subprocess.run(command, cwd=Path(root), capture_output=True, text=True, check=False,
                         env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if run.returncode != 0:
        raise ValueError('Fresh-process reopen failed: ' + (run.stderr or run.stdout)[-1200:])
    reopened = json.loads(run.stdout)
    write_json(result_path, reopened)
    if reopened.get('status') != 'PASS' or reopened.get('total_records_returned') != json.loads((bundle / 'materialization.json').read_text())['source_objects']:
        raise ValueError('Fresh-process retrieval did not return the complete materialized record set')
    if reopened.get('reader_pid') == os.getpid():
        raise ValueError('Fresh-process reader did not use a distinct process')
    outputs = {name: sha(bundle / name) for name in
               ('materialization.json', 'reopened.json', 'store/catalog.sqlite')}
    materialization = json.loads((bundle / 'materialization.json').read_text())
    acceptance = {'schema': RUN_SCHEMA, 'status': 'PASS', 'dataset_id': dataset_id,
                  'package_seal_sha256': materialization['package_seal']['sha256'],
                  'materialization_status': 'MATERIALIZED_WITH_WARNINGS' if materialization['warning_count'] else 'MATERIALIZED',
                  'materialization_pid': os.getpid(), 'reader_pid': reopened['reader_pid'],
                  'source_records': materialization['source_objects'],
                  'warnings': materialization['warning_count'], 'query_records': reopened['total_records_returned'],
                  'query_result_sha256': digest(canonical(reopened['source_revisions'])),
                  'outputs': outputs,
                  'qualification': 'NOT_RUN', 'engineering_acceptance': 'NOT_ESTABLISHED'}
    write_json(bundle / 'acceptance.json', acceptance)
    _read_materialization(root, bundle)
    return acceptance


def run_acceptance(root, package_root, dataset_id, output):
    return accept_materialization(root, package_root, dataset_id, output)
