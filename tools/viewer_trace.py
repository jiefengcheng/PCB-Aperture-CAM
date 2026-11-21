#!/usr/bin/env python3
"""Generate one local source-growth comparison from a frozen viewer selection."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.pcb_workspace import prepare, WORK
from src.viewer_abi.trace_selection import write_trace_response
from src.viewer_abi.route_presentation import bind_catalogue


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', required=True)
    p.add_argument('--request')
    p.add_argument('--response')
    p.add_argument('--catalogue-preparation', help='Bind existing source-role preparation for route picking; no stage execution')
    args = p.parse_args(); prepare()
    if args.catalogue_preparation:
        workspace=Path(args.workspace).resolve();preparation=Path(args.catalogue_preparation).resolve()
        if args.request or args.response or not workspace.is_relative_to(WORK.resolve())or not preparation.is_relative_to(WORK.resolve()):
            raise ValueError('CATALOGUE_BINDING_REQUIRES_VIEWER_LACIE_WORKSPACE')
        print(json.dumps(bind_catalogue(workspace.parent,preparation)))
        return
    if not args.request or not args.response:p.error('--request and --response are required for a selection')
    workspace, request, response = (Path(v).resolve() for v in (args.workspace, args.request, args.response))
    if (not workspace.is_relative_to(WORK.resolve()) or
            not request.is_relative_to(workspace) or not response.is_relative_to(workspace)):
        raise ValueError('TRACE_REQUIRES_VIEWER_LACIE_WORKSPACE')
    value = write_trace_response(workspace.parent, json.loads(request.read_bytes()), response)
    print(json.dumps(dict(status='TRACE_COMPARISON_READY', objectID=value['objectID'], revision=value['revision'])))


if __name__ == '__main__': main()
