#!/usr/bin/env python3
"""Show exact source-surface witnesses used by preliminary width bounds."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import json,subprocess,html
from shapely.geometry import LineString,box
from shapely.ops import unary_union
from tools.run_c02_four_attachment_diagnostic_v2 import compute
from tools.run_c02_growth_coverage import render,svg_shape


def main():
    pre,inventory,bounds_packet=map(Path,sys.argv[1:])
    report,g=compute(pre)
    inv=json.loads((inventory/'TRACE_ENDPOINT_INVENTORY.json').read_text())
    chains={c['component_id']:c for c in inv['components']}
    d=json.loads((bounds_packet/'COLLECTIVE_WIDTH_BOUNDS.json').read_text())
    out=bounds_packet/'witnesses_v2';assert not out.exists();out.mkdir()
    scene=g['scene']
    geom=lambda sid:scene.replacements.get(sid,scene.objects[sid]['geometry'])
    cards=[];records=[]
    for group in d['groups']:
        for row in group['applicable_witnesses']:
            key=row['constraint_id'];line=LineString(row['witness_mm'])
            trace=unary_union([geom(sid) for sid in chains[row['member_a']]['source_ids']])
            other=(unary_union([geom(sid) for sid in chains[row['member_b']]['source_ids']])
                   if row['member_b'] else geom(row['fixed_neighbor_source_id']))
            center=line.centroid;side=max(.08,line.length*3)
            bounds=[center.x-side/2,center.y-side/2,center.x+side/2,center.y+side/2]
            notes=[f'Exact nearest copper-surface witness: {row["surface_gap_mm"]*1000:.9f} µm. Coordinates from retained geometry.',
                'Cyan = unchanged complete trace contour; gold = neighbor contour; white = measured nearest-surface segment.',
                'Construction guard 20.10 µm; hard minimum 20.00 µm. A trace already at the guard can remain unchanged.',
                'This is a width-growth bound, not a new T02 defect or a request to move existing copper.',
                f'Group {group["group_id"]}; common-factor upper bound {group["analytical_bound"]["common_factor_upper_bound"]:.12f}.',
                'No T04 width construction. Original attachment/occlusion and coupled-group checks remain separate.']
            svg=out/f'{key}.svg'
            render(svg,f'C02 / exact width-bound witness {key}',g['after'],line.buffer(.00012),bounds,[],{},notes)
            a,b=row['witness_mm']
            measured=f'<path d="M {a[0]} {a[1]} L {b[0]} {b[1]}" fill="none" stroke="#ffffff" stroke-width=".00035"/>'
            overlays=svg_shape(trace.intersection(box(*bounds)),'none','#36ddc7',.0004)+svg_shape(other.intersection(box(*bounds)),'none','#ffe463',.0004)+measured
            svg.write_text(svg.read_text().replace('</svg>',overlays+'</svg>',1))
            subprocess.run(['sips','-s','format','png',str(svg),'--out',str(out/f'{key}.png')],check=True,capture_output=True)
            records.append(dict(**row,group_id=group['group_id'],viewport_mm=bounds,
                                common_factor_upper_bound=group['analytical_bound']['common_factor_upper_bound']))
            cards.append('<h2>'+html.escape(key)+f' — {row["surface_gap_mm"]*1000:.9f} µm</h2><img src="{key}.png">')
    (out/'EXACT_WITNESSES.json').write_text(json.dumps(records,indent=2,sort_keys=True)+'\n')
    full=out/'full_crop_locator.svg'
    render(full,'C02 / exact width-bound witness locations',g['after'],g['exposed'],g['base']['bounds'],[],{},
        ['Crosshairs are at exact measured nearest-surface segment midpoints, not source-group centers.',
         'W01–W04 refer to the detail views and exact source-coordinate records below.',
         'Source geometry and widths unchanged. A limiting width bound is not a failed T02 proposal.'])
    markers=''
    for index,r in enumerate(records,1):
        a,b=r['witness_mm'];x,y=(a[0]+b[0])/2,(a[1]+b[1])/2
        markers+=f'<path d="M {x-.04} {y} L {x+.04} {y} M {x} {y-.04} L {x} {y+.04}" stroke="#ffffff" stroke-width=".006"/><text x="{x+.05}" y="{y-.04}" font-size=".08" font-family="Arial" fill="#ffffff">W{index:02d}</text>'
        cards[index-1]=f'<h2>W{index:02d} / '+cards[index-1][4:]
    full.write_text(full.read_text().replace('</svg>',markers+'</svg>',1))
    subprocess.run(['sips','-s','format','png',str(full),'--out',str(out/'full_crop_locator.png')],check=True,capture_output=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 width witnesses</title><style>body{font:18px system-ui;color:#142a3f;margin:24px}img{width:100%}</style><h1>C02 exact surface witnesses — no width growth</h1><p>These measured relationships limit possible growth. They are not failed T02 proposals.</p><img src="full_crop_locator.png">'+''.join(cards))
    p=bounds_packet/'index.html';p.write_text(p.read_text().replace('href="witnesses/index.html"','href="witnesses_v2/index.html"'))


if __name__=='__main__':main()
