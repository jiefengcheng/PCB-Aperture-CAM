#!/usr/bin/env python3
"""Actual source binding preflight at factor 1.0; no width-growth execution."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hashlib,json,subprocess
from shapely import STRtree,from_wkb,to_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.uniform_trace_width import construct_uniform_width
from tools.run_c02_four_attachment_diagnostic_v2 import compute
from tools.run_c02_growth_coverage import render


def main(constructor=construct_uniform_width):
    pre,inventory,qualification,out=map(Path,sys.argv[1:])
    assert not out.exists()
    stage,g=compute(pre)
    source=g['base']['source']
    bank=json.loads((pre/'inputs/source_manifest.json').read_text())
    manifest={r['id']:r for r in bank['objects']}
    inv=json.loads((inventory/'TRACE_ENDPOINT_INVENTORY.json').read_text())
    q=json.loads((qualification/'CHAIN_CONTACT_QUALIFICATION.json').read_text())
    qualified={r['component_id'] for r in q['chains'] if r['status']=='SOURCE_CHAIN_GEOMETRICALLY_QUALIFIED_FOR_WIDTH_FEASIBILITY'}
    chains={r['component_id']:dict(r,source_sha256=bank['source_sha256']) for r in inv['components'] if r['component_id'] in qualified}
    records=[];unions={}
    for cid,chain in sorted(chains.items()):
        blobs={sid:(pre/f'inputs/source_wkb/{manifest[sid]["geometry_sha256"]}.wkb').read_bytes() for sid in chain['source_ids']}
        record,parts,original,candidate=constructor(source,chain,manifest,blobs,1.)
        assert candidate.equals(original) and record['added_area_mm2']==0 and record['core_removed_mm2']==0
        assert all(to_wkb(parts[sid])==blobs[sid] for sid in chain['source_ids'])
        records.append(dict(**record,preflight='PASS_EXACT_NO_CHANGE',outside_crop_members=chain['outside_crop_source_ids']))
        unions[cid]=original
    out.mkdir(parents=True);(out/'visuals').mkdir()
    receipt=dict(schema='c02-uniform-width-source-preflight/1',source_sha256=bank['source_sha256'],
        source_manifest_sha256=hashlib.sha256((pre/'inputs/source_manifest.json').read_bytes()).hexdigest(),
        qualification_sha256=hashlib.sha256((qualification/'CHAIN_CONTACT_QUALIFICATION.json').read_bytes()).hexdigest(),
        trace_chain_count=len(records),source_primitive_count=sum(len(r['primitives']) for r in records),
        factor=1.,width_growth_execution='NOT_RUN',stage_acceptance='NONE',T02='PENDING_BATCH_AUDIT_NOT_FROZEN',
        records=records)
    (out/'SOURCE_PREFLIGHT.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    notes=[f'{len(records)} complete qualified source chains, all at factor 1.0; every original primitive WKB retained exactly.',
        'Teal = unchanged source trace footprints; red = cumulative predecessor. No trace widening or routing.',
        'The constructor enforces one uniform nominal width on each complete trace; groups share one scale.',
        'Remote source sections are included. Missing members, mixed widths, local exceptions and >1.5 factors reject.',
        'Source binding preflight only. Positive-width tests are synthetic controls; actual T04 growth has NOT_RUN.',
        'T02 remains pending batched audit; no native-board export, electrical or manufacturing acceptance.']
    render(out/'visuals/full_c02.svg','C02 / uniform-width constructor — exact source preflight',g['after'],unary_union(list(unions.values())),g['base']['bounds'],[],{},notes)
    # Show an entire source chain with remote sections, never crop it to imply full-route coverage.
    chosen=max(records,key=lambda r:(len(r['outside_crop_members']),len(r['primitives']),r['component_id']))
    core=unions[chosen['component_id']];x0,y0,x1,y1=core.bounds
    bounds=[x0-.2,y0-.2,x1+.2,y1+.2]
    scene=g['scene'];ids=sorted(scene.objects)
    geometry=[scene.replacements.get(sid,scene.objects[sid]['geometry']) for sid in ids]
    tree=STRtree(geometry);copper=unary_union([geometry[int(i)] for i in tree.query(box(*bounds),predicate='intersects')])
    (out/'remote_route_copper.wkb').write_bytes(to_wkb(copper))
    (out/'remote_route_trace.wkb').write_bytes(to_wkb(core))
    (out/'REMOTE_ROUTE_FRAME.json').write_text(json.dumps(dict(component_id=chosen['component_id'],
        source_ids=chosen['complete_source_ids'],outside_crop_source_ids=chosen['outside_crop_members'],viewport_mm=bounds,
        source_trace_wkb_sha256=hashlib.sha256(to_wkb(core)).hexdigest(),
        copper_wkb_sha256=hashlib.sha256(to_wkb(copper)).hexdigest(),factor=1.),indent=2)+'\n')
    render(out/'visuals/complete_remote_route.svg','C02 trace / complete source route including remote sections',copper,core,bounds,[],{},
        [f'Actual full source chain: {chosen["component_id"]}; {len(chosen["primitives"])} primitives, {len(chosen["outside_crop_members"])} outside C02.',
         f'Uniform original width {chosen["verified_original_width_mm"]:.8f} mm; factor 1.0. No width growth.',
         'Same source route terminals and intermediate coordinates; original primitive WKBs exact.',
         'Red = current source/cumulative copper in this full-route frame; teal = unchanged complete selected trace.',
         'This expanded frame demonstrates whole-route scope; it is not a new accepted land baseline.',
         'T02 pending batched audit; T04 width construction NOT_RUN.'])
    for name in ('full_c02','complete_remote_route'):
        subprocess.run(['sips','-s','format','png',str(out/f'visuals/{name}.svg'),'--out',str(out/f'visuals/{name}.png')],check=True,capture_output=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 width source preflight</title><style>body{font:18px system-ui;color:#142a3f;margin:24px}img{width:100%}</style><h1>C02 uniform-width source preflight — no growth</h1><img src="visuals/full_c02.png"><h2>Complete route including remote sections</h2><img src="visuals/complete_remote_route.png">')
    print(json.dumps({k:v for k,v in receipt.items() if k!='records'}))


if __name__=='__main__':main()
