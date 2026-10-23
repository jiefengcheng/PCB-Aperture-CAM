#!/usr/bin/env python3
"""Publish bounded ORG-only candidate-member and family hypotheses."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.family_map_storage import publish
from src.ingestion_files import sha
from src.org_family_recognition import recognize_catalogue
from src.org_geometry_materialization import verify_org_geometry_materialization
from src.revision_catalog import RevisionCatalog

DEFAULT_ORG_BUNDLE = ROOT / 'out/ingestion/org_geometry_materializations/szu-comm_before_after_20261022_org_only_v1'
DEFAULT_OUTPUT = ROOT / 'out/ingestion/org_family_map_materializations/szu-comm_20261022_org_recognition_v1'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--org-bundle', type=Path, default=DEFAULT_ORG_BUNDLE)
    parser.add_argument('--output-root', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    org_bundle = args.org_bundle if args.org_bundle.is_absolute() else ROOT / args.org_bundle
    output_root = args.output_root if args.output_root.is_absolute() else ROOT / args.output_root
    org_bundle = org_bundle.resolve()
    output_root = output_root.resolve()
    if not org_bundle.is_relative_to(ROOT / 'out'):
        raise ValueError('ORG geometry bundle must be under checkout/out')
    verify_org_geometry_materialization(ROOT, org_bundle, require_acceptance=True)
    materialization_path = org_bundle / 'materialization.json'
    manifest = json.loads(materialization_path.read_text())
    with RevisionCatalog(org_bundle / 'store', read_only=True) as catalog:
        recognized = recognize_catalogue(
            catalog, manifest['revision'],
            geometry_materialization_sha256=sha(materialization_path))
    bundle, receipt = publish(
        ROOT, base_store=org_bundle / 'store', org_revision=manifest['revision'],
        output_root=output_root, dataset_id=manifest['dataset_id'],
        input_spec=recognized['input_spec'], entities=recognized['entities'],
        relations=recognized['relations'], coverage=recognized['coverage'])
    print(json.dumps({
        'status': 'PASS', 'bundle': str(bundle.relative_to(ROOT)),
        'dataset_id': manifest['dataset_id'],
        'org_revision': manifest['revision'],
        'org_source_sha256': manifest['source']['sha256'],
        'candidate_members': recognized['coverage']['candidate_members'],
        'family_hypotheses': recognized['coverage']['family_hypotheses'],
        'uncertain_trace_associations': recognized['coverage']['trace_associations'].get(
            'uncertain_trace_associations', 0),
        'content_sha256': json.loads((bundle / 'materialization.json').read_text())[
            'derived_map']['content_sha256'],
        'writer_pid': receipt['writer_pid'], 'reader_pid': receipt['reader_pid'],
        'engineering_acceptance': 'NOT_ESTABLISHED',
        'manufacturing_acceptance': 'NOT_ESTABLISHED',
    }, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)}, allow_nan=False))
        raise SystemExit(1)
