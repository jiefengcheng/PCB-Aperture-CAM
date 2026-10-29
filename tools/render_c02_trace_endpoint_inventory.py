#!/usr/bin/env python3
"""Actual source trace footprints, classified for read-only T04 preparation."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hashlib
import html
import json
import subprocess
from shapely import from_wkb
from shapely.ops import unary_union
from tools.run_c02_growth_coverage import render


def main():
    pre, scene_path, inventory = map(Path,sys.argv[1:])
    d=json.loads((inventory/'TRACE_ENDPOINT_INVENTORY.json').read_text())
    scene=from_wkb(scene_path.read_bytes())
    names=[('simple_source_chains','SOURCE_ENDPOINT_CHAIN_REQUIRES_LAND_AND_CONTACT_CHECKS'),
           ('unresolved_source_components','UNRESOLVED_TRACE_DEFINITION')]
    out=inventory/'visuals'
    assert not out.exists()
    out.mkdir()
    for name,status in names:
        components=[c for c in d['components'] if c['status']==status]
        selected={r['source_id']:r for c in components for r in c['original_full_source_members']}
        parts=[]
        for r in selected.values():
            blob=(pre/f'inputs/source_wkb/{r["source_wkb_sha256"]}.wkb').read_bytes()
            assert hashlib.sha256(blob).hexdigest()==r['source_wkb_sha256']
            parts.append(from_wkb(blob))
        footprints=unary_union(parts)
        notes=[f'{len(components)} exact-source endpoint components; {len(selected)} full-source primitives retained, including remote members.',
               'Teal = unchanged original trace footprints of this classification. Red = retained cumulative land/copper scene.',
               'No trace widening, rerouting or source edit. These colors indicate inventory membership, not added copper.',
               'Simple chains still need land-terminal/interior-contact qualification before T04 eligibility.',
               'Branched/mixed-width definitions are retained unresolved; no artificial splitting or width normalization.',
               'Cumulative T02 remains proposed pending batched audit. Electrical intent and native export not established.']
        render(out/f'{name}.svg',f'C02 / trace preparation — {name.replace("_"," ")}',
               scene,footprints,d['viewport_mm'],[],{},notes)
        subprocess.run(['sips','-s','format','png',str(out/f'{name}.svg'),'--out',str(out/f'{name}.png')],check=True,capture_output=True)
    rows=''.join('<tr><td>'+html.escape(c['component_id'])+'</td><td>'+str(len(c['source_ids']))+'</td><td>'+str(len(c['outside_crop_source_ids']))+'</td><td>'+html.escape(str(c['original_widths_mm']))+'</td><td>'+html.escape(', '.join(c['unresolved_reasons']) or 'land/contact checks pending')+'</td></tr>' for c in d['components'])
    (inventory/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 trace preparation</title><style>body{font:18px system-ui;margin:28px;color:#142a3f}img{width:100%}td,th{padding:7px;border-bottom:1px solid #ddd}</style><h1>C02 trace inventory — no width growth yet</h1><p>Exact native endpoint graph; remote members included. Source primitives are not inferred electrical nets.</p>'+''.join(f'<h2>{name.replace("_"," ")}</h2><img src="visuals/{name}.png">' for name,_ in names)+'<table><tr><th>Source endpoint component</th><th>Full primitives</th><th>Outside crop</th><th>Original widths mm</th><th>Remaining definition checks</th></tr>'+rows+'</table>')


if __name__=='__main__':
    main()
