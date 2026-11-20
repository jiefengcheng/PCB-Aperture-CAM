#!/usr/bin/env python3
"""Deliver a chat explanation to its exact viewer selection; never writes geometry."""
from pathlib import Path
import argparse
import base64
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.pcb_workspace import prepare, WORK
from src.viewer_abi.publisher import encode, digest, atomic_write, read_current


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True)
    parser.add_argument('--selection',required=True)
    parser.add_argument('--text-file',required=True)
    parser.add_argument('--author',required=True)
    parser.add_argument('--evidence',action='append',required=True)
    args=parser.parse_args();prepare()
    root=Path(args.workspace).resolve()
    if root==WORK.resolve() or not root.is_relative_to(WORK.resolve()):raise ValueError('EXPLANATION_REQUIRES_LACIE')
    selected=json.loads(Path(args.selection).read_bytes());selected=selected.get('selection',selected)
    manifest,current=read_current(root)
    scene=current
    if selected['revision']!=current['revision'] and manifest.get('previousPayload'):
        raw=(root/'snapshots'/manifest['previousPayload']).read_bytes()
        if digest(raw)!=manifest['previousSHA256']:raise ValueError('EXPLANATION_PARENT_CHANGED')
        scene=json.loads(raw)
    obj=selected['object']
    if scene['job']!=selected['job'] or scene['revision']!=selected['revision'] or obj not in scene['objects']:
        raise ValueError('EXPLANATION_SELECTION_NOT_IN_REVISION')
    text=Path(args.text_file).read_text()
    payload=encode(dict(schema=1,job=scene['job'],revision=scene['revision'],objectID=obj['id'],sourceID=obj['sourceID'],author=args.author,text=text,evidence=args.evidence))
    if not text.strip() or len(payload)>64*1024:raise ValueError('EXPLANATION_TEXT_RESOURCE_LIMIT')
    envelope=encode(dict(schema=1,sha256=digest(payload),payloadBase64=base64.b64encode(payload).decode()))
    folder=root/'inbox';folder.mkdir(exist_ok=True)
    atomic_write(folder/'explanation.json',envelope)
    print(json.dumps(dict(status='EXPLANATION_DELIVERED',revision=scene['revision'],objectID=obj['id'],sha256=digest(payload)),indent=2))


if __name__=='__main__':main()
