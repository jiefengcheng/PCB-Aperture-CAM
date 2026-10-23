"""Extract and freshly reopen source-located records from a sealed intake profile."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.profile_materialization import accept_materialization, reopen_materialization, _read_materialization


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('acceptance', 'reopen', 'verify'))
    parser.add_argument('--package-root', type=Path)
    parser.add_argument('--dataset-id')
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.action == 'acceptance':
        if not args.package_root or not args.dataset_id or not args.output:
            parser.error('acceptance requires --package-root, --dataset-id, and --output')
        result = accept_materialization(ROOT, args.package_root, args.dataset_id, args.output)
    else:
        if not args.bundle:
            parser.error(args.action + ' requires --bundle')
        bundle = args.bundle if args.bundle.is_absolute() else ROOT / args.bundle
        if args.action == 'verify':
            receipt, materialization, _ = _read_materialization(ROOT, bundle)
            reopened = reopen_materialization(ROOT, bundle, require_acceptance=True)
            if reopened['total_records_returned'] != receipt['query_records']:
                raise ValueError('Fresh-process retrieval count differs from acceptance')
            result = {'status': 'PASS', 'dataset_id': materialization['dataset_id'],
                      'source_records': receipt['source_records'], 'query_records': reopened['total_records_returned'],
                      'package_seal_sha256': materialization['package_seal']['sha256'],
                      'reader_pid': reopened['reader_pid']}
        else:
            result = reopen_materialization(ROOT, bundle)
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)}))
        sys.exit(1)
