#!/usr/bin/env python3
"""Same-source-set historical/rebuilt comparison, without new construction."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import argparse
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from shapely import from_wkb
from shapely.ops import unary_union
from tools.run_c02_growth_coverage import render, HISTORICAL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('packet', type=Path)
    args = ap.parse_args()
    p = args.packet
    out = p/'additive_same_candidate_comparison'
    out.mkdir(exist_ok=True)
    coverage = json.loads((p/'coverage.json').read_text())
    bank = {r['id']:r for r in json.loads((p/'inputs/source_manifest.json').read_text())['objects']}
    cores = {r['source_id']:from_wkb((p/'inputs/source_wkb'/f'{bank[r["source_id"]]["geometry_sha256"]}.wkb').read_bytes()) for r in coverage}
    selected = [r for r in coverage if r['selected']]
    historical = {r['source_id']:r for r in json.loads((HISTORICAL/'t02_decisions.json').read_text())['decisions']}
    parts = []
    for row in selected:
        sid = row['source_id']
        blob = (HISTORICAL/'t02_candidates'/(hashlib.sha256(sid.encode()).hexdigest()+'.wkb')).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == historical[sid]['candidate_geometry_sha256']
        parts.append(from_wkb(blob).difference(cores[sid]))
    t01 = from_wkb((p/'t01/cumulative.wkb').read_bytes())
    old_delta = unary_union(parts).difference(t01)
    old = t01.union(old_delta)
    new_delta = from_wkb((p/'t02/cumulative.wkb').read_bytes()).difference(t01)
    bounds = json.loads((p/'result.json').read_text())['viewport_mm']
    notes = ['Same 74 rectangle source IDs and same focused T01 in both panels; six context rectangles unchanged.',
             'Left: historical v69 rectangle proposals, retained as comparison only. Right: rebuilt own-stage checked growth.',
             'New additions are constrained within T02; no corner-clearance shortfall is delegated to T03.',
             'NOT FROZEN: five unchanged growth objectives and local attachment classification remain unresolved.']
    render(out/'historical.svg', 'C02 / historical proposals — same 74 selected rectangles', old,old_delta,bounds,coverage,cores,notes)
    q = out/'historical.svg'
    q.write_text(q.read_text().replace('#21bda8','#ffb34b'))
    tag = '{http://www.w3.org/2000/svg}'
    svgs = [ET.parse(q).getroot(),ET.parse(p/'t02/full_crop.svg').getroot()]
    height = int(float(svgs[0].attrib['height']))
    root = ET.Element(tag+'svg',{'width':'3680','height':str(height+250),'viewBox':f'0 0 3680 {height+250}'})
    ET.SubElement(root,tag+'rect',{'width':'3680','height':str(height+250),'fill':'#edf3f7'})
    for i,svg in enumerate(svgs):
        svg.set('x',str(40+i*1840)); svg.set('y','100');root.append(svg)
    lines = [('C02 / complete focused coverage — same 74 candidates; 69 positive-growth outcomes',48,32),
             (f'Exact exposed rectangle additions: historical {old_delta.area:.6f} mm² → revised {new_delta.area:.6f} mm² ({new_delta.area/old_delta.area*100:.2f}% retained).',height+155,26),
             ('Historical geometry is comparison evidence only. No source, trace, acceptance or old-ledger record is changed.',height+195,24)]
    for text,y,size in lines:
        e = ET.SubElement(root,tag+'text',{'x':'40','y':str(y),'font-size':str(size),'font-family':'Arial','fill':'#142a3f'})
        e.text = text
    ET.ElementTree(root).write(out/'same_74_before_after.svg',encoding='unicode')
    subprocess.run(['sips','-s','format','png',str(out/'same_74_before_after.svg'),'--out',str(out/'same_74_before_after.png')],check=True,capture_output=True)
    (out/'comparison.json').write_text(json.dumps({'historical_selected_count':len(selected),'revised_selected_count':len(selected),
        'historical_exact_exposed_added_area_mm2':old_delta.area,'revised_exact_exposed_added_area_mm2':new_delta.area,
        'retained_fraction':new_delta.area/old_delta.area,'status':'ADDITIVE_READ_ONLY_COMPARISON_NOT_IN_SUBMITTED_REV05_ZIP'},indent=2)+'\n')


if __name__ == '__main__':
    main()
