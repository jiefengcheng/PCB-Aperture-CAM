#!/usr/bin/env python3
"""Inventory whole-source trace adjacency before any T04 width construction."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hashlib
import json
import re
from collections import Counter
from shapely.geometry import box
from shapely import from_wkb
from src.trace_endpoint_inventory import endpoint_components


def main():
    pre, out = map(Path, sys.argv[1:])
    assert not out.exists()
    raw = (pre/'inputs/ORG_source.kicad_pcb').read_bytes()
    bank = json.loads((pre/'inputs/source_manifest.json').read_text())
    assert hashlib.sha256(raw).hexdigest() == bank['source_sha256']
    bounds = json.loads((pre/'result.json').read_text())['viewport_mm']
    crop = box(*bounds)
    rows, seeds = [], []
    for r in bank['objects']:
        if r['kind'] not in ('segment','arc'):
            continue
        if r['coverage'] != 'GEOMETRY_AVAILABLE' or r['layers'] != ['F.Cu']:
            continue
        start, end = r['source_span']
        fragment = raw[start:end]
        ends = []
        for field in ('start', 'end'):
            m = re.search(rb'\('+field.encode()+rb'\s+([^\s()]+)\s+([^\s()]+)\)', fragment)
            if m is None:
                raise ValueError('TRACE_ENDPOINT_NOT_ESTABLISHED')
            ends.append([v.decode('ascii') for v in m.groups()])
        width = re.search(rb'\(width\s+([^\s()]+)\)', fragment)
        assert width and float(width[1]) == r['trace_width_mm']
        rows.append(dict(source_id=r['id'], kind=r['kind'], endpoints_decimal_mm=ends,
                         width_mm=r['trace_width_mm'], bounds_mm=r['bounds_mm'],
                         source_fragment_sha256=hashlib.sha256(fragment).hexdigest(),
                         source_wkb_sha256=r['geometry_sha256']))
        if box(*r['bounds_mm']).intersects(crop):
            blob = (pre/f'inputs/source_wkb/{r["geometry_sha256"]}.wkb').read_bytes()
            assert hashlib.sha256(blob).hexdigest() == r['geometry_sha256']
            if from_wkb(blob).intersects(crop):
                seeds.append(r['id'])
    components = endpoint_components(rows, seeds)
    by_id = {r['source_id']:r for r in rows}
    for c in components:
        c['component_id'] = 'EC-'+hashlib.sha256('\n'.join(c['source_ids']).encode()).hexdigest()[:16]
        c['outside_crop_source_ids'] = [sid for sid in c['source_ids'] if sid not in seeds]
        c['original_full_source_members'] = [by_id[sid] for sid in c['source_ids']]
        c['candidate_width_ceiling_factor'] = 1.5
        c['width_geometry_constructed'] = False
    out.mkdir(parents=True)
    result = dict(schema='c02-whole-source-trace-endpoint-inventory/1', source_sha256=bank['source_sha256'],
        source_manifest_sha256=hashlib.sha256((pre/'inputs/source_manifest.json').read_bytes()).hexdigest(),
        viewport_mm=bounds, whole_source_trace_primitive_count=len(rows), crop_seed_count=len(seeds),
        endpoint_components=len(components), source_members_after_full_endpoint_expansion=sum(len(c['source_ids']) for c in components),
        classifications=dict(Counter(c['status'] for c in components)), components=components,
        limitations=['Read-only preparation; no T04 width edits or stage acceptance.',
                     'Endpoint adjacency is geometric source evidence, not electrical intent.',
                     'Interior contacts, land terminals, full-route membership and parallel-group scope still require checks.',
                     'Other trace-like polygons lack this native segment/arc route representation and remain unqualified.'])
    (out/'TRACE_ENDPOINT_INVENTORY.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    (out/'README.md').write_text('# C02 complete-source trace preparation\n\nExact original segment/arc endpoint adjacency expands every crop-intersecting source primitive through the whole source bank. Remote members remain included. Branched or mixed-width definitions remain unresolved. No width geometry, land edits, route edits, electrical acceptance or T04 execution.\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('components','limitations')}))


if __name__ == '__main__':
    main()
