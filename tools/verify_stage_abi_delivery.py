#!/usr/bin/env python3
"""Validate the compact ABI delivery's bytes, actual wire records and scenes."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import re
import sys
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shapely import from_wkb
from src.stage_abi.contracts import validate_request
from src.stage_abi.responses import validate_response
from src.stage_abi.service import runtime_fingerprint


def check(package, *, require_current=False):
    read = lambda p: json.loads(p.read_text())
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = read(package / 'SHA256SUMS.json')
    for name, expected in manifest.items():
        path = (package / name).resolve()
        assert path.is_relative_to(package.resolve()) and path.is_file() and sha(path) == expected, name
    provenance = read(package / 'PROVENANCE.json')
    versions = set()
    operations = 0
    for stage, binding in provenance['qualifications'].items():
        folder = package / stage
        receipt = read(folder / 'RECEIPT.json')
        assert sha(folder / 'RECEIPT.json') == binding['receipt_sha256']
        assert sha(folder / 'LOCAL_EVIDENCE_MANIFEST.json') == binding['source_manifest_sha256']
        inventory=read(folder/'LOCAL_EVIDENCE_MANIFEST.json')
        archive=folder/inventory['full_manifest_ref']['path']
        assert sha(archive)==inventory['full_manifest_ref']['sha256']
        raw_inventory=gzip.decompress(archive.read_bytes())
        assert hashlib.sha256(raw_inventory).hexdigest()==inventory['uncompressed_manifest_sha256']
        assert len(json.loads(raw_inventory)['files'])==inventory['file_count']
        versions.add(receipt['runtime_fingerprint'])
        compressed = folder / ('RESULT.json.gz' if stage == 'bundle_model' else 'TRANSCRIPT.json.gz')
        raw = gzip.decompress(compressed.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == binding['transcript_sha256']
        result = json.loads(raw)
        rows = result['transcript'] if stage == 'bundle_model' else result
        for record in rows:
            validate_request(record['request'])
            validate_response(record['response'])
            assert record['response']['status'] == 'OK'
            operations += 1
        if stage == 'bundle_model':
            assert receipt['actual_board'] is False and result['status'] == 'PASS_LOCAL_MODULAR_COMPOSITION'
            assert [r['stage'] for r in result['steps']] == ['t03', 't04']
            continue
        verified = next(r['response']['result']['result']['verification'] for r in rows if r['request']['operation'] == stage + '_verify')
        assert verified['geometric_status'] == 'PASS' and verified['check']['passed'] is True
        candidate = next(r['response']['result']['result']['candidate'] for r in rows if r['request']['operation'] == stage + ('_search' if stage == 't03' else '_run'))
        for name in ('before', 'after'):
            assert sha(folder / (name + '.wkb')) == candidate[name + '_ref']['sha256']
        before, after = [from_wkb((folder / (name + '.wkb')).read_bytes()) for name in ('before', 'after')]
        assert before.is_valid and after.is_valid and before.difference(after).area <= 1e-12
        if stage == 't03':
            assert candidate['status'] == 'NO_CHANGE_REQUIRED' and before.equals(after)
        else:
            assert after.difference(before).area > 1e-12
        assert candidate['owner_status'] == 'PENDING' and verified['independent_status'] == 'NOT_RUN'
    assert len(versions) == 1
    current_matches = versions == {runtime_fingerprint()}
    if require_current:
        assert current_matches, 'RUNTIME_FINGERPRINT_DRIFT'
    links = 0
    for page in package.rglob('*.html'):
        for link in re.findall(r'(?:src|href)="([^"]+)"', page.read_text()):
            parsed = urlparse(link)
            if parsed.scheme or not parsed.path:
                continue
            target = (page.parent / unquote(parsed.path)).resolve()
            assert target.is_relative_to(ROOT) and target.is_file(), (page, link)
            links += 1
    return dict(status='PASS_STAGE_ABI_DELIVERY_INTEGRITY_WIRE_AND_SAVED_GEOMETRY', files=len(manifest), links=links, executed_operation_records=operations, current_runtime_matches=current_matches, scope='Delivery integrity and saved source-scene geometry. Same-assistant local checks; not independent/native/electrical/manufacturing acceptance.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--require-current-runtime', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.package.resolve(), require_current=args.require_current_runtime)))
