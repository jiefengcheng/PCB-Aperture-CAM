#!/usr/bin/env python3
"""Prepare gray/green T04 growth presentation from the current saved construction."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.pcb_workspace import prepare, WORK
from src.viewer_abi.board_growth import publish_board_growth

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection', required=True)
    args = parser.parse_args(); prepare()
    root = Path(args.connection).resolve()
    if not root.is_relative_to(WORK.resolve()):
        raise ValueError('BOARD_GROWTH_REQUIRES_LACIE_WORKSPACE')
    print(json.dumps(publish_board_growth(root)))
