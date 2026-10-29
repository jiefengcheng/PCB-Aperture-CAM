#!/usr/bin/env python3
"""Render one source-bound, unioned added-copper image per T04 operation."""
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from shapely import from_wkb
from shapely.geometry import box
from tools.run_c02_growth_coverage import render


def main(proposal,out):
    if out.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
    operations=json.loads((proposal/'GROWTH_OPERATIONS.json').read_text())
    result=json.loads((proposal/'RESULT.json').read_text())
    after=from_wkb((proposal/'after.wkb').read_bytes())
    if hashlib.sha256((proposal/'after.wkb').read_bytes()).hexdigest()!=result['after_sha256']:
        raise ValueError('CUMULATIVE_GEOMETRY_BINDING_MISMATCH')
    out.mkdir(parents=True)
    figures=[];records=[]
    for op in operations:
        blob=(proposal/'growth_operations'/f"{op['operation_id']}.wkb").read_bytes()
        if hashlib.sha256(blob).hexdigest()!=op['added_copper_sha256']:
            raise ValueError('OPERATION_GEOMETRY_BINDING_MISMATCH')
        added=from_wkb(blob)
        if added.is_empty:
            records.append(dict(op,visual='KEEP_ZERO_ADDED_COPPER'));continue
        x0,y0,x1,y1=added.bounds
        pad=max(.1,.08*max(x1-x0,y1-y0));bounds=[x0-pad,y0-pad,x1+pad,y1+pad]
        svg=out/f"{op['operation_id']}.svg"
        render(svg,f"C02 / one merged expansion / {op['operation_id']}",after.intersection(box(*bounds)),added,bounds,[],{},[
            f"Shared width scale {op['scale']:.9f}; {len(op['members'])} native runs, {len(op['source_ids'])} source identities.",
            'Teal = unioned added copper counted once; red = cumulative copper. Fully covered objects remain fixed.',
            f"Source board {result['source_sha256']}; exact operation WKB {op['added_copper_sha256']}.",
            'Source-bound model proposal; fixed routes and frozen lands. No native or manufacturing acceptance.'])
        subprocess.run(['sips','-s','format','png',str(svg),'--out',str(svg.with_suffix('.png'))],check=True,capture_output=True)
        records.append(dict(op,viewport_mm=bounds,visual=svg.with_suffix('.png').name))
        figures.append(f'<h2>{html.escape(op["operation_id"])} · {op["scale"]:.6f}×</h2><img src="{svg.stem}.png">')
    (out/'VISUAL_BINDINGS.json').write_text(json.dumps(records,indent=2,sort_keys=True)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 merged growth operations</title><style>body{font:18px system-ui;margin:24px}img{max-width:100%}</style><h1>One expansion per common-scale operation</h1><p>Unchanged KEEP operations are recorded with zero added copper in VISUAL_BINDINGS.json.</p>'+''.join(figures))
    print(json.dumps(dict(operations=len(records),positive_visuals=len(figures))))

if __name__=='__main__':main(*map(Path,sys.argv[1:]))
