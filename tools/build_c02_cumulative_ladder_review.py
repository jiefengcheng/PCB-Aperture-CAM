#!/usr/bin/env python3
"""Same-frame presentation of exact saved cumulative copper stages."""
import sys,json,hashlib,subprocess,shutil,html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb
from src.crop_circle_sources import verify_assets
from tools.run_c02_growth_coverage import render


def sha(b):return hashlib.sha256(b).hexdigest()


def main():
    freeze,proposal,out=map(Path,sys.argv[1:]);assert not out.exists();integrity=verify_assets()
    receipt=json.loads((freeze/'FREEZE_RECEIPT.json').read_text());result=json.loads((proposal/'RESULT.json').read_text())
    constructions=json.loads((proposal/'CONSTRUCTION.json').read_text())
    route_count=len(constructions)
    positive_routes=sum(r['factor']>1 for r in constructions)
    keep_routes=route_count-positive_routes
    assert route_count==result['visible_complete_routes']
    assert receipt['status']=='FROZEN_GEOMETRIC_PREDECESSOR' and result['land_predecessor_sha256']==receipt['cumulative_sha256']
    files=[('ORG',freeze/'ORG_crop.wkb','Original source copper; no growth.'),
        ('T01',freeze/'T01_cumulative.wkb','Frozen focused circle stage; original trace routes and widths retained.'),
        ('T02',freeze/'cumulative.wkb','Frozen cumulative T01+T02:74positive rectangle witnesses; rejected cap trials remain separate.'),
        ('T04_proposed',proposal/'after.wkb',f'Proposed cumulative nominal T04: {route_count} routes, {positive_routes} positive, {keep_routes} KEEP; not frozen.')]
    out.mkdir();records=[];previous=None
    for label,path,description in files:
        blob=path.read_bytes();geometry=from_wkb(blob)
        if label=='T02':assert sha(blob)==receipt['cumulative_sha256']
        if label=='T04_proposed':assert sha(blob)==result['after_sha256']
        addition=geometry.difference(geometry) if previous is None else geometry.difference(previous)
        removal=0. if previous is None else previous.difference(geometry).area
        assert removal<=1e-12,'PREDECESSOR_REMOVAL'
        shutil.copyfile(path,out/f'{label}.wkb')
        notes=[description,'Red = complete cumulative nominal copper. Teal = exact copper added since the preceding displayed stage.',
            'Identical viewport and image scale across every panel. Source-bound finite copper; no generated illustration.',
            'T03 is deferred; no route changes. T04 checking envelopes are not included in displayed nominal copper.',
            f'Geometry SHA-256: {sha(blob)}',
            f'Added area relative to preceding panel: {addition.area:.12g} mm2; removed area: {removal:.12g} mm2.',
            'Geometry-only scope. T04 not frozen; source eligibility qualification remains separate. No native/electrical/manufacturing acceptance.']
        svg=out/f'{label}.svg';render(svg,f'C02 / cumulative ladder / {label}',geometry,addition,receipt['viewport_mm'],[],{},notes)
        subprocess.run(['sips','-s','format','png',str(svg),'--out',str(out/f'{label}.png')],check=True,capture_output=True)
        records.append(dict(stage=label,source_path=str(path),wkb_sha256=sha(blob),added_area_mm2=addition.area,removed_area_mm2=removal,description=description))
        previous=geometry
    (out/'STAGES.json').write_text(json.dumps(dict(asset_integrity=integrity,source_sha256=receipt['source_sha256'],viewport_mm=receipt['viewport_mm'],stages=records,T03='DEFERRED',T04='PROPOSED_NOT_FROZEN',visible_routes=route_count,positive_routes=positive_routes,keep_routes=keep_routes),indent=2)+'\n')
    panels=''.join('<section><h2>'+r['stage']+'</h2><p>'+html.escape(r['description'])+'</p><img src="'+r['stage']+'.png"></section>' for r in records)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 cumulative copper ladder</title><style>body{font:18px system-ui;max-width:1800px;margin:28px auto;color:#142a3f}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}img{width:100%}@media(max-width:900px){.grid{grid-template-columns:1fr}}</style><h1>C02 cumulative copper ladder</h1><p>Same source, viewport and scale. Frozen T01/T02 remain unchanged. T03 is deferred. T04 is proposed, not frozen; qualification of its source eligibility remains separate.</p><div class="grid">'+panels+'</div><p><a href="STAGES.json">Exact stage bindings and differences</a> · <a href="../'+html.escape(proposal.name)+'/index.html">Current proposal and source scope</a> · <a href="../'+html.escape(proposal.name)+'/SOLVER.json">Current retained rejected T04 upper trials</a></p>')
    manifest={p.name:sha(p.read_bytes()) for p in out.iterdir() if p.is_file()};(out/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(records))


if __name__=='__main__':main()
