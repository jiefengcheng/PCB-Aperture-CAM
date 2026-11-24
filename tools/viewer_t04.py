#!/usr/bin/env python3
"""Prepare the dedicated T04 workspace from an already saved result."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.pcb_workspace import prepare,WORK
from src.viewer_abi.t04_workspace import publish
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--connection',required=True);args=p.parse_args();prepare()
    root=Path(args.connection).resolve()
    if not root.is_relative_to(WORK.resolve()):raise ValueError('T04_VIEW_REQUIRES_LACIE')
    print(json.dumps(publish(root)))
