#!/usr/bin/env python3
"""Build or verify the sealed SZU-comm ORG-only native geometry materialization."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.org_geometry_materialization import (
    accept_org_geometry_materialization,
    reopen_org_geometry_materialization,
    verify_org_geometry_materialization,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('acceptance', 'reopen', 'verify'))
    parser.add_argument('--bundle', required=True, type=Path)
    args = parser.parse_args(argv)
    bundle = args.bundle if args.bundle.is_absolute() else ROOT / args.bundle
    if args.action == 'acceptance':
        result = accept_org_geometry_materialization(ROOT, output=bundle)
    elif args.action == 'verify':
        result = verify_org_geometry_materialization(ROOT, bundle, require_acceptance=True)
    else:
        result = reopen_org_geometry_materialization(ROOT, bundle)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)}, allow_nan=False))
        raise SystemExit(1)
