#!/usr/bin/env python3
"""Publish selected read-only Gerbers to the viewer ABI. No engineering operations."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.pcb_workspace import prepare, WORK
from src.viewer_abi.publisher import publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--gerber', action='append', required=True)
    parser.add_argument('--slice', default='Gerber import')
    parser.add_argument('--job', default='manual-import')
    args = parser.parse_args()
    prepare()
    root = Path(args.workspace).resolve()
    if not root.is_relative_to(WORK.resolve()) or root == WORK.resolve():
        raise ValueError('VIEWER_WORKSPACE_MUST_BE_UNDER_LACIE_WORK')
    manifest, scene = publish(root, args.gerber, slice_name=args.slice, job=args.job)
    print(json.dumps(dict(status='PUBLISHED_PREVIEW', workspace=str(root), revision=scene['revision'],
                          objects=len(scene['objects']), manifest=manifest), indent=2))


if __name__ == '__main__':
    main()
