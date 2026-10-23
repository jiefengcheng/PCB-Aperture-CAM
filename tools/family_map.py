#!/usr/bin/env python3
"""Read-only verification entry point for derived ORG family-map bundles."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.family_map_storage import verify_bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('verify',))
    parser.add_argument('--bundle', required=True, type=Path)
    args = parser.parse_args(argv)
    bundle = args.bundle if args.bundle.is_absolute() else ROOT / args.bundle
    print(json.dumps(verify_bundle(ROOT, bundle), sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)}, allow_nan=False))
        raise SystemExit(1)
