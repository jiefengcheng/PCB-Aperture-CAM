#!/usr/bin/env python3
"""Actual source-bound operands behind final common-scale width limits."""
import sys,json,hashlib,subprocess,functools
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb
from shapely.geometry import LineString,box
from shapely.ops import nearest_points,unary_union
from src.crop_circle_sources import verify_assets
from src.source_offset_width import construct_source_offset_width
from tools.run_c02_four_attachment_diagnostic_v2 import compute
from tools.run_c02_growth_coverage import render,svg_shape


def main(pre,definitions,groups_dir,proposal,out):
    if out.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
    verify_assets();report,g=compute(pre);scene=g['scene'];raw=g['base']['source']
    result=json.loads((proposal/'RESULT.json').read_text());binding=json.loads((proposal/'INPUT_BINDING.json').read_text())
    for path,key in [(definitions/'UNIFORM_SOURCE_PATHS.json','definition_sha256'),(groups_dir/'PARALLEL_MEMBERSHIP.json','groups_sha256')]:
        if hashlib.sha256(path.read_bytes()).hexdigest()!=binding[key]:raise ValueError('INPUT_BINDING_MISMATCH')
    if report['cumulative_sha256']!=binding['land_predecessor_sha256']:raise ValueError('LAND_BINDING_MISMATCH')
    paths={r['path_id']:dict(r,component_id=r['path_id']) for r in json.loads((definitions/'UNIFORM_SOURCE_PATHS.json').read_text())['paths']}
    groups=json.loads((groups_dir/'PARALLEL_MEMBERSHIP.json').read_text())['groups'];assignment={cid:r['group_id'] for r in groups for cid in r['members']}
    meta={r['id']:r for r in json.loads((pre/'inputs/source_manifest.json').read_text())['objects']}
    blobs={sid:(pre/f'inputs/source_wkb/{meta[sid]["geometry_sha256"]}.wkb').read_bytes() for cid in assignment for sid in paths[cid]['source_ids']}
    @functools.lru_cache(maxsize=30)
    def construct(cid,scale):return construct_source_offset_width(raw,paths[cid],meta,blobs,scale)
    def geometry(identity,scales,original=False):
        if identity in assignment:return construct(identity,1. if original else scales[assignment[identity]])[3 if original else 5]
        return scene.objects[identity]['geometry'] if original else scene.replacements.get(identity,scene.objects[identity]['geometry'])
    out.mkdir();records=[];cards=[]
    solver=json.loads((proposal/'SOLVER.json').read_text())
    for proof in solver['maximum_proofs']:
        if proof.get('upper_factor') is None:continue
        check_path=proposal/f"checks/{proof['rejection_check_index']:05}.json";saved=json.loads(check_path.read_text())
        failure=saved['check']['failures'][0];a=failure['trace_id'];b=failure['neighbor_id'];scales=dict(result['selected_scales']);scales[proof['group_id']]=proof['upper_factor']
        ga,gb=geometry(a,scales),geometry(b,scales);oa,ob=geometry(a,scales,True),geometry(b,scales,True)
        points=nearest_points(ga,gb);line=LineString([points[0],points[1]]);center=line.centroid;side=max(.12,line.length*5);bounds=[center.x-side/2,center.y-side/2,center.x+side/2,center.y+side/2];clip=box(*bounds)
        index=len(records)+1;name=f'L{index:02d}';svg=out/f'{name}.svg'
        selected=result['selected_scales'][proof['group_id']]
        render(svg,f'C02 / final width limit {name}',g['after'].intersection(clip),line.buffer(.0001),bounds,[],{},[
            f'Selected common factor {selected:.9f}; rejected upper factor {proof["upper_factor"]:.9f}.',
            f'Original raw operand gap {oa.distance(ob)*1000:.9f} um; rejected checking-envelope raw gap {ga.distance(gb)*1000:.9f} um.',
            'Cyan/gold = rejected checking operands; white = exact nearest raw surface points. These are not committed copper.',
            'Governing visible-surface failure and operand identities saved in LIMITS.json; raw gap is diagnostic only.',
            'KEEP remains byte-identical and does not repair an inherited relationship. Frozen lands unchanged.'])
        x,y=points;overlay=svg_shape(ga.intersection(clip),'none','#36ddc7',.0004)+svg_shape(gb.intersection(clip),'none','#ffe463',.0004)+f'<path d="M {x.x} {x.y} L {y.x} {y.y}" stroke="white" stroke-width=".0003"/>'
        svg.write_text(svg.read_text().replace('</svg>',overlay+'</svg>'))
        subprocess.run(['sips','-s','format','png',str(svg),'--out',str(svg.with_suffix('.png'))],check=True,capture_output=True)
        row=next(r for r in saved['check']['traces'] if r['trace_id']==a);pair=next(r for r in row['pairs'] if r['neighbor_id']==b)
        records.append(dict(label=name,group_id=proof['group_id'],selected_factor=selected,rejected_factor=proof['upper_factor'],failure=failure,governing_pair=pair,source_ids_a=paths[a]['source_ids'],source_ids_b=paths[b]['source_ids'] if b in paths else [b],original_raw_gap_mm=oa.distance(ob),rejected_raw_gap_mm=ga.distance(gb),nearest_rejected_raw_points_mm=[list(x.coords)[0],list(y.coords)[0]],viewport_mm=bounds,saved_check=str(check_path),saved_check_sha256=hashlib.sha256(check_path.read_bytes()).hexdigest()))
        cards.append(f'<h2>{name} · selected {selected:.9f}×</h2><img src="{name}.png">')
    (out/'LIMITS.json').write_text(json.dumps(records,indent=2,sort_keys=True)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 final width limits</title><style>body{font:18px system-ui;margin:24px}img{max-width:100%}</style><h1>Why these common-scale groups stop growing</h1><p>Rejected trial envelopes shown separately; selected cumulative copper remains valid under the growth-only model.</p>'+''.join(cards))
    print(json.dumps(dict(limits=len(records),keep=sum(r['selected_factor']==1 for r in records))))

if __name__=='__main__':main(*map(Path,sys.argv[1:]))
