#!/usr/bin/env python3
"""Read-only full-chain contact qualification against the cumulative land scene."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hashlib,json,subprocess,html
from collections import Counter
from shapely import STRtree,to_wkb
from shapely.ops import unary_union
from src.trace_chain_contacts import qualify_chain
from tools.run_c02_four_attachment_diagnostic_v2 import compute
from tools.run_c02_growth_coverage import render


def main():
    pre,inventory,out=map(Path,sys.argv[1:])
    assert not out.exists()
    report,g=compute(pre)
    bank=json.loads((pre/'inputs/source_manifest.json').read_text())
    meta={r['id']:r for r in bank['objects']}
    scene=g['scene']
    ids=sorted(scene.objects)
    geometries={sid:scene.replacements.get(sid,scene.objects[sid]['geometry']) for sid in ids}
    tree=STRtree([geometries[sid] for sid in ids])
    d=json.loads((inventory/'TRACE_ENDPOINT_INVENTORY.json').read_text())
    assert d['source_sha256']==report['source_sha256']
    rows=[]
    for c in d['components']:
        core=unary_union([geometries[sid] for sid in c['source_ids']])
        neighbors=[dict(source_id=ids[int(i)],kind=meta[ids[int(i)]]['kind'],geometry=geometries[ids[int(i)]])
                   for i in tree.query(core,predicate='intersects')]
        q=qualify_chain(c,geometries,neighbors)
        rows.append(dict(component_id=c['component_id'],source_ids=c['source_ids'],
            original_widths_mm=c['original_widths_mm'],original_terminal_points_decimal_mm=c['terminal_points_decimal_mm'],
            outside_crop_source_ids=c['outside_crop_source_ids'],
            original_trace_union_wkb_sha256=hashlib.sha256(to_wkb(core)).hexdigest(),**q))
    out.mkdir(parents=True)
    result=dict(schema='c02-full-chain-contact-qualification/1',source_sha256=report['source_sha256'],
        proposed_cumulative_scene_sha256=report['cumulative_sha256'],predecessor_status='T02_PENDING_BATCH_AUDIT_NOT_FROZEN',
        endpoint_inventory_sha256=hashlib.sha256((inventory/'TRACE_ENDPOINT_INVENTORY.json').read_bytes()).hexdigest(),
        classifications=dict(Counter(r['status'] for r in rows)),chains=rows,
        width_construction='NOT_RUN',electrical_intent='NOT_ESTABLISHED',
        scope='Read-only whole-source endpoint-chain and original contact preparation; no blanket component exemption')
    (out/'CHAIN_CONTACT_QUALIFICATION.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    (out/'visuals').mkdir()
    for label,status in [('qualified','SOURCE_CHAIN_GEOMETRICALLY_QUALIFIED_FOR_WIDTH_FEASIBILITY'),
                         ('unresolved','UNRESOLVED_TRACE_DEFINITION'),
                         ('covered','COVERED_SOURCE_TRACE_NO_INDEPENDENT_EXPOSED_ROUTE')]:
        selected=[r for r in rows if r['status']==status]
        copper=unary_union([geometries[sid] for r in selected for sid in r['source_ids']])
        notes=[f'{len(selected)} source endpoint components: {status}.',
            'Teal = unchanged original source trace footprints; red = cumulative fixed copper/lands.',
            'The complete source chain, including sections outside this viewport, was checked for original contacts.',
            'Two land terminals and no exposed interior junction are required for the qualified classification.',
            'Covered source strokes receive no independent width-growth credit. Unresolved definitions are retained.',
            'No route/width changes; T02 pending batched audit. Parallel grouping and width feasibility remain to do.']
        render(out/f'visuals/{label}.svg',f'C02 / complete-chain contact qualification — {label}',
               g['after'],copper,g['base']['bounds'],[],{},notes)
        subprocess.run(['sips','-s','format','png',str(out/f'visuals/{label}.svg'),'--out',str(out/f'visuals/{label}.png')],check=True,capture_output=True)
    table=''.join('<tr><td>'+html.escape(r['component_id'])+'</td><td>'+html.escape(r['status'])+'</td><td>'+str(len(r['source_ids']))+'</td><td>'+html.escape(', '.join(r['unresolved_reasons']))+'</td></tr>' for r in rows)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 chain contacts</title><style>body{font:18px system-ui;color:#142a3f;margin:24px}img{width:100%}td{padding:8px;border-bottom:1px solid #ddd}</style><h1>C02 complete-chain contacts — read-only preparation</h1>'+''.join(f'<h2>{label}</h2><img src="visuals/{label}.png">' for label in ['qualified','unresolved','covered'])+'<table>'+table+'</table>')
    print(json.dumps(result['classifications']))


if __name__=='__main__':main()
