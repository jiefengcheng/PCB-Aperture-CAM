#!/usr/bin/env python3
"""Render paired expected-vs-KiCad incremental copper SVGs for G9."""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from shapely.geometry import GeometryCollection, LineString
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.evaluate_arc_attribution_coupon import plot_geometry, stroke


def polygons(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == 'Polygon':
        return [geom]
    if hasattr(geom, 'geoms'):
        return [p for item in geom.geoms for p in polygons(item)]
    return []


def path_data(geom, tx, ty, scale, ox, oy):
    chunks=[]
    for poly in polygons(geom):
        for ring in [poly.exterior, *poly.interiors]:
            coords=list(ring.coords)
            if not coords:
                continue
            x0=ox+(coords[0][0]-tx)*scale
            y0=oy-(coords[0][1]-ty)*scale
            chunks.append(f'M {x0:.3f},{y0:.3f}')
            for x,y in coords[1:]:
                chunks.append(f'L {ox+(x-tx)*scale:.3f},{oy-(y-ty)*scale:.3f}')
            chunks.append('Z')
    return ' '.join(chunks)


def svg_for(root: Path, scenario: dict):
    base=plot_geometry((ROOT/scenario['exports']['without_target']['gerber_path']).resolve())
    treated=plot_geometry((ROOT/scenario['exports']['with_target']['gerber_path']).resolve())
    measured=treated.difference(base)
    contexts=[stroke(row['start'],row['end'],row['width']) for row in scenario['context_segments']]
    context=unary_union(contexts) if contexts else GeometryCollection()
    target=scenario['target']
    expected=context.union(stroke(target['start'],target['end'],target['width'])).difference(context)
    bounds=[target['start'][0]-0.1,target['start'][1]-0.1,
            target['end'][0]+0.1,target['start'][1]+0.1]
    if not context.is_empty:
        b=context.bounds
        bounds=[min(bounds[0],b[0]-0.02),min(bounds[1],b[1]-0.02),
                max(bounds[2],b[2]+0.02),max(bounds[3],b[3]+0.02)]
    if not measured.is_empty:
        b=measured.bounds
        bounds=[min(bounds[0],b[0]-0.02),min(bounds[1],b[1]-0.02),
                max(bounds[2],b[2]+0.02),max(bounds[3],b[3]+0.02)]
    xmin,ymin,xmax,ymax=bounds
    width,height=680,250
    panel_w=320
    scale=min((panel_w-40)/max(xmax-xmin,1e-6),(height-70)/max(ymax-ymin,1e-6))
    ybase=height-32
    leftx=20-(xmin*scale)
    rightx=360-(xmin*scale)
    l_expected=path_data(expected,xmin,ymin,scale,leftx,ybase+ymin*scale)
    l_context=path_data(context,xmin,ymin,scale,leftx,ybase+ymin*scale)
    r_measured=path_data(measured,xmin,ymin,scale,rightx,ybase+ymin*scale)
    r_context=path_data(context,xmin,ymin,scale,rightx,ybase+ymin*scale)
    title=html.escape(scenario['scenario'])
    occluded='Expected target increment is empty. Plot cannot distinguish the target from its covering neighbor.' if expected.is_empty else 'Target increment is visible in the paired plot difference.'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#f6f8fa"/>
<text x="20" y="22" font-family="system-ui,sans-serif" font-size="15" font-weight="700">{title}</text>
<text x="20" y="46" font-family="system-ui,sans-serif" font-size="11" fill="#445">{html.escape(occluded)}</text>
<text x="20" y="66" font-family="system-ui,sans-serif" font-size="12">Authored expected target increment</text>
<text x="360" y="66" font-family="system-ui,sans-serif" font-size="12">KiCad plotted increment (with − without)</text>
<path d="{l_context}" fill="#9aa4b2" fill-opacity="0.65" stroke="#667085" stroke-width="0.8" fill-rule="evenodd"/>
<path d="{l_expected}" fill="#3b82f6" fill-opacity="0.7" stroke="#1d4ed8" stroke-width="0.8" fill-rule="evenodd"/>
<path d="{r_context}" fill="#9aa4b2" fill-opacity="0.65" stroke="#667085" stroke-width="0.8" fill-rule="evenodd"/>
<path d="{r_measured}" fill="#f97316" fill-opacity="0.65" stroke="#c2410c" stroke-width="0.8" fill-rule="evenodd"/>
<text x="20" y="{height-8}" font-family="system-ui,sans-serif" font-size="10" fill="#667085">Gray: unchanged neighbor context. Blue/orange: incremental copper. Shared scale per panel; dimensions in mm.</text>
</svg>'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default='out/ingestion/gerber_fidelity/g9_arc_attribution_current_v1')
    parser.add_argument('--output',default='out/ingestion/gerber_fidelity/g9_arc_attribution_current_v1/visuals')
    args=parser.parse_args()
    root=(ROOT/args.input).resolve(); output=(ROOT/args.output).resolve()
    if not root.is_relative_to(ROOT/'out') or not output.is_relative_to(ROOT/'out'):
        raise SystemExit('input/output must stay under out/')
    spec=json.loads((root/'scenario_spec.json').read_text())
    output.mkdir(parents=True,exist_ok=True)
    for scenario in spec['scenarios']:
        (output/f"{scenario['scenario']}.svg").write_text(svg_for(root,scenario))
    print(json.dumps({'visuals':len(spec['scenarios']),'output':str(output.relative_to(ROOT))},indent=2))


if __name__=='__main__':
    main()
