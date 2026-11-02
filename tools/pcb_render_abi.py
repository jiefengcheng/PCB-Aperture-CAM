#!/usr/bin/env python3
"""Execute one source-bound read-only C01 render ABI operation."""

import argparse
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.stage_abi.store import digest
from src.render_abi import ABI_VERSION, OPERATIONS
from src.render_abi.service import RenderService, local
from tools.t01_route_client import decode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--registry-sha256', required=True)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    request = {}
    try:
        blob = args.input.read_bytes()
        if len(blob) > 65536:
            raise ValueError('RENDER_REQUEST_TOO_LARGE')
        request = decode(blob)
        if (type(request) is not dict or set(request) != {'abi_version', 'request_id', 'operation'}
                or request['abi_version'] != ABI_VERSION or type(request['operation']) is not str
                or request['operation'] not in (*OPERATIONS,'render_compare','render_verify','render_controls') or type(request['request_id']) is not str
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', request['request_id'])):
            raise ValueError('RENDER_REQUEST_INVALID')
        registry = local(args.registry)
        if not registry.is_relative_to(ROOT/'out'):
            raise ValueError('RENDER_REGISTRY_SCOPE_INVALID')
        raw = registry.read_bytes()
        if digest(raw) != args.registry_sha256:
            raise ValueError('RENDER_HOST_HASH_MISMATCH')
        host=decode(raw)
        if request['operation'] in ('render_compare','render_verify','render_controls'):
            from src.render_abi.crop import CropRenderService
            service=CropRenderService(host)
        else:service=RenderService(host)
        result = service.dispatch(request['operation'])
        response = dict(abi_version=ABI_VERSION, request_id=request['request_id'],
                        operation=request['operation'], status='OK', result=result, error=None)
        code = 0
    except Exception as error:
        safe = request if type(request) is dict else {}
        response = dict(abi_version=ABI_VERSION,
                        request_id=safe.get('request_id') if type(safe.get('request_id')) is str else None,
                        operation=safe.get('operation') if type(safe.get('operation')) is str else None,
                        status='REJECTED', result=None,
                        error=dict(code='RENDER_REJECTED', message=str(error)))
        code = 2
    print(json.dumps(response, sort_keys=True, allow_nan=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
