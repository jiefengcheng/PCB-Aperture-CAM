#!/usr/bin/env python3
"""Render representative G10 expected-vs-plotted increment comparisons."""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shapely.geometry import GeometryCollection
from shapely.ops import unary_union
from tools.evaluate_arc_attribution_sweep import geom_for_case, stroke
from tools.render_arc_attribution_coupon import path_data


def svg_for(root: Path, case: dict):
    baseline = geom_for_case(root, case, 6, 'without_target')
    treated = geom_for_case(root, case, 6, 'with_target')
    observed = treated.difference(baseline)
    contexts = [stroke(x) for x in case['scenario']['context_segments']]
    context = unary_union(contexts) if contexts else GeometryCollection()
    target = case['scenario']['target']
    target_geometry = stroke({'start':target['start'],'end':target['end'],'width':target['width']})
    expected = context.union(target_geometry).difference(context)
    width = target['width']; length = target['centerline_length_mm']
    margin = max(width * 0.9, 0.002)
    xmin = min(target['start'][0], target['end'][0]) - margin
    xmax = max(target['start'][0], target['end'][0]) + margin
    ymin = min(target['start'][1], target['end'][1]) - margin
    ymax = max(target['start'][1], target['end'][1]) + margin
    if not context.is_empty:
        b = context.bounds
        xmin=min(xmin,b[0]-margin); xmax=max(xmax,b[2]+margin)
        ymin=min(ymin,b[1]-margin); ymax=max(ymax,b[3]+margin)
    panel_w, height, full_w = 350, 245, 740
    scale = min((panel_w-40)/max(xmax-xmin,1e-9),(height-84)/max(ymax-ymin,1e-9))
    left_x, right_x, top_y = 20, panel_w+20, 78
    c1=path_data(context,xmin,ymax,scale,left_x,top_y)
    e1=path_data(expected,xmin,ymax,scale,left_x,top_y)
    c2=path_data(context,xmin,ymax,scale,right_x,top_y)
    m2=path_data(observed,xmin,ymax,scale,right_x,top_y)
    sid=html.escape(case['scenario']['id'])
    note=('Target is fully covered in the baseline; paired plots show no distinguishable increment.'
          if expected.is_empty else 'Blue is expected unique target area; orange is KiCad plot difference (with − without).')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{full_w}" height="{height}" viewBox="0 0 {full_w} {height}">
<rect width="100%" height="100%" fill="#f6f8fa"/>
<text x="20" y="20" font-family="system-ui,sans-serif" font-size="14" font-weight="700">{sid}</text>
<text x="20" y="40" font-family="system-ui,sans-serif" font-size="10" fill="#445">{html.escape(note)}</text>
<text x="20" y="63" font-family="system-ui,sans-serif" font-size="12">Expected unique target increment</text>
<text x="{panel_w+20}" y="63" font-family="system-ui,sans-serif" font-size="12">Measured plot increment</text>
<path d="{c1}" fill="#9aa4b2" fill-opacity="0.7" stroke="#667085" stroke-width="0.7" fill-rule="evenodd"/>
<path d="{e1}" fill="#3b82f6" fill-opacity="0.78" stroke="#1d4ed8" stroke-width="0.7" fill-rule="evenodd"/>
<path d="{c2}" fill="#9aa4b2" fill-opacity="0.7" stroke="#667085" stroke-width="0.7" fill-rule="evenodd"/>
<path d="{m2}" fill="#f97316" fill-opacity="0.78" stroke="#c2410c" stroke-width="0.7" fill-rule="evenodd"/>
<text x="20" y="{height-8}" font-family="system-ui,sans-serif" font-size="10" fill="#667085">Gray: context copper. Shared scale. Source dimensions length={length:.9g} mm, width={width:.9g} mm.</text>
</svg>'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default='out/ingestion/gerber_fidelity/g10_arc_attribution_sweep_v2')
    parser.add_argument('--output',default='out/ingestion/gerber_fidelity/g10_arc_attribution_sweep_v2/visuals_v2')
    args=parser.parse_args(); root=(ROOT/args.input).resolve(); output=(ROOT/args.output).resolve()
    if not root.is_relative_to(ROOT/'out') or not output.is_relative_to(ROOT/'out'):
        raise SystemExit('input/output must stay under out/')
    spec=json.loads((root/'scenario_spec.json').read_text())
    chosen={'shortest_horizontal_isolated','widest_horizontal_isolated',
            'widest_horizontal_partial_overlap','narrowest_horizontal_full_occlusion'}
    output.mkdir(parents=True,exist_ok=False)
    count=0
    for case in spec['cases']:
        if case['scenario']['id'] not in chosen: continue
        (output/f"{case['scenario']['id']}.svg").write_text(svg_for(root,case)); count+=1
    if count!=len(chosen): raise SystemExit(f'expected {len(chosen)} representative SVGs, got {count}')
    print(json.dumps({'visual_count':count,'output':str(output.relative_to(ROOT))},indent=2))


if __name__=='__main__': main()
