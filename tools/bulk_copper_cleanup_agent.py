#!/usr/bin/env python3
"""Inspect the committed big-copper cleanup and continuation contract read-only."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.agent_abi.bulk_copper_cleanup import execute,request


def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--describe',action='store_true');g.add_argument('--status',action='store_true')
    g.add_argument('--list',nargs='?',const='all',choices=['all','corrected','unresolved','ignored','reviewed','circular'])
    g.add_argument('--inspect',metavar='CASE_ID');p.add_argument('--revision')
    g.add_argument('--check-saved',action='store_true');g.add_argument('--input',metavar='JSON_FILE_OR_DASH')
    a=p.parse_args()
    try:
        if a.input:
            if a.revision:raise ValueError('REVISION_BELONGS_IN_JSON_REQUEST')
            if a.input=='-':raw=sys.stdin.read(65537)
            else:
                from src.agent_abi.bulk_copper_cleanup import ROOT
                path=Path(a.input).resolve(strict=True)
                if not path.is_relative_to(ROOT) and not path.is_relative_to((ROOT/'out/lacie_work').resolve()):
                    raise ValueError('REQUEST_FILE_MUST_BE_PROJECT_LOCAL')
                with path.open('rb')as stream:raw=stream.read(65537)
            if len(raw)>65536:raise ValueError('CLEANUP_REQUEST_RESOURCE_LIMIT')
            v=json.loads(raw)
        else:
            if a.revision and not a.inspect:raise ValueError('REVISION_ONLY_FOR_INSPECT')
            v=request('describe'if a.describe else 'status'if a.status else 'list_places'if a.list else 'inspect_place'if a.inspect else 'check_saved',
                      filter=a.list,place_id=a.inspect,revision=a.revision)
        result=execute(v)
    except (ValueError,OSError,RuntimeError,KeyError,TypeError)as exc:
        print(json.dumps(dict(abi_version='1',status='FAIL',error=str(exc),writes=False,geometry_execution=False)));return 1
    print(json.dumps(result,indent=2,allow_nan=False));return 0


if __name__=='__main__':raise SystemExit(main())
