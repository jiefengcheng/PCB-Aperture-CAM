"""One-request/one-response local JSON entry point."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .service import dispatch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local CAM Agent ABI v0.1; no network or execution adapter.")
    parser.add_argument("--input", type=Path, help="Read one JSON request from this file; otherwise read stdin.")
    args = parser.parse_args(argv)
    try:
        raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
        request = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        response = {"abi_version": "0.1", "operation": "", "status": "REJECTED", "result": None, "error": {"code": "INPUT_JSON_INVALID", "message": str(exc)}}
        print(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 2
    response = dispatch(request)
    print(json.dumps(response, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0 if response["status"] in {"OK", "NOT_RUN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
