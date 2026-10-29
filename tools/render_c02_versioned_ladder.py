#!/usr/bin/env python3
"""Render exact retained stage geometry after a successful versioned replay."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from shapely import from_wkb
from tools.run_c02_growth_coverage import render


def main():
    pre, proposed, replay, out = map(Path, sys.argv[1:])
    assert not out.exists()
    receipt = json.loads((replay/'REPLAY_RECEIPT.json').read_text())
    assert receipt['status'] == 'PASS_VERSIONED_FIXED_DIAGNOSTIC_REPLAY_PENDING_ACCEPTANCE'
    assert receipt['checks'] == 75 and receipt['wkb_payloads_exact'] == 11
    out.mkdir(parents=True)
    rows = json.loads((pre/'coverage.json').read_text())
    bank = {r['id']:r for r in json.loads((pre/'inputs/source_manifest.json').read_text())['objects']}
    cores = {r['source_id']:from_wkb((pre/'inputs/source_wkb'/f'{bank[r["source_id"]]["geometry_sha256"]}.wkb').read_bytes()) for r in rows}
    paths = [pre/'source_baseline/copper.wkb', pre/'t01/cumulative.wkb', proposed/'geometry/after.wkb']
    stages = [from_wkb(p.read_bytes()) for p in paths]
    bounds = json.loads((pre/'result.json').read_text())['viewport_mm']
    titles = ['C02 / ORG source copper', 'C02 / cumulative focused T01',
              'C02 / cumulative T01 + T02 — versioned replay']
    names = ['01_org', '02_t01', '03_t01_t02']
    records = []
    for i, (name, title, scene, path) in enumerate(zip(names, titles, stages, paths, strict=True)):
        previous = stages[max(0, i-1)]
        delta = scene.difference(previous)
        removed = previous.difference(scene).area
        assert removed <= 1e-12
        notes = [f'Exact source frame: {bounds}; mm. Same viewport and scale in every stage.',
                 'Red = resulting copper union; teal = exact copper added by this stage; gold = source rectangles.',
                 f'Exact added copper: {delta.area:.12f} mm²; predecessor copper removed: {removed:.12f} mm².',
                 '74 selected rectangles / 6 unchanged context rectangles. Original trace paths and widths unchanged.',
                 'T02: 70 accepted witnesses + 4 locally passing proposals pending batched audit; NOT FROZEN.',
                 '75 cumulative checks / 11 exact geometry payloads passed versioned replay. No native/electrical acceptance.']
        render(out/f'{name}.svg', title, scene, delta, bounds, rows, cores, notes)
        subprocess.run(['sips', '-s', 'format', 'png', str(out/f'{name}.svg'), '--out', str(out/f'{name}.png')], check=True, capture_output=True)
        records.append(dict(stage=name, source_wkb=str(path.resolve()),
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            added_area_mm2=delta.area, removed_area_mm2=removed))
    tag = '{http://www.w3.org/2000/svg}'
    panels = [ET.parse(out/f'{name}.svg').getroot() for name in names]
    width = float(panels[0].attrib['width'])
    height = float(panels[0].attrib['height'])
    full = ET.Element(tag+'svg', width=str(width*3), height=str(height), viewBox=f'0 0 {width*3} {height}')
    for i, panel in enumerate(panels):
        panel.set('x', str(width*i)); panel.set('y', '0'); full.append(panel)
    ET.ElementTree(full).write(out/'ladder.svg', encoding='unicode')
    subprocess.run(['sips', '-s', 'format', 'png', str(out/'ladder.svg'), '--out', str(out/'ladder.png')], check=True, capture_output=True)
    (out/'STAGE_GEOMETRY.json').write_text(json.dumps(dict(viewport_mm=bounds, stages=records,
        replay_receipt=str((replay/'REPLAY_RECEIPT.json').resolve()), geometry_edits='NONE; retained WKB rendering only'), indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 cumulative ladder</title><style>body{font-family:system-ui;background:#edf3f7;color:#142a3f;margin:24px}img{width:100%;height:auto}article{background:white;padding:16px;margin:20px 0}</style><h1>C02 cumulative ladder — exact retained geometry</h1><p>Comparable source → T01 → cumulative T02. Four proposals remain pending batched audit; T02 is not frozen.</p>'+''.join(f'<article><h2>{title}</h2><a href="{name}.svg"><img src="{name}.png"></a></article>' for name,title in zip(names,titles,strict=True)))


if __name__ == '__main__':
    main()
