"""Preserve and profile a received directory without interpreting or qualifying it."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dataset_profiler import profile_directory, verify_profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Directory received for intake")
    parser.add_argument("--dataset-id", help="Stable identity, e.g. client:acme-board:20261021:v1")
    parser.add_argument("--output", type=Path, help="New profile directory under checkout/out/ or checkout/dataset/")
    parser.add_argument("--verify", type=Path, help="Verify an existing staged profile")
    args = parser.parse_args(argv)
    if args.verify:
        result = verify_profile(args.verify)
    else:
        if not args.source or not args.dataset_id or not args.output:
            parser.error("--source, --dataset-id and --output are required unless --verify is used")
        result = profile_directory(ROOT, args.source, args.dataset_id, args.output)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}))
        sys.exit(1)
