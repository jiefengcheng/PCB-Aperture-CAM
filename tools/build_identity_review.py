"""Build source-bound object-pair images for the local ingestion Findings view."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from xml.sax.saxutils import escape

import sexpdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ingestion_files import sha
from src.native_inventory import arc_points


def child(node, name):
    return next((item for item in node if isinstance(item, list) and item and str(item[0]) == name), None)


def xy(node):
    return float(node[1]), float(node[2])


def source_object(raw, row):
    start, end = row['source_span']
    node = sexpdata.loads(raw[start:end].decode('utf-8'))
    kind = row['kind']
    width_node = child(node, 'width')
    if width_node is None:
        stroke = child(node, 'stroke')
        width_node = child(stroke, 'width') if stroke else None
    width = float(width_node[1]) if width_node else 0.15
    if kind in ('segment', 'gr_line'):
        points = [xy(child(node, 'start')), xy(child(node, 'end'))]
        shape = 'line'
    elif kind in ('arc', 'gr_arc'):
        points = arc_points(xy(child(node, 'start')), xy(child(node, 'mid')), xy(child(node, 'end')))
        shape = 'line'
    elif kind == 'gr_circle':
        points = [xy(child(node, 'center')), xy(child(node, 'end'))]
        shape = 'circle'
    elif kind == 'gr_poly':
        pts = child(node, 'pts')
        points = [xy(item) for item in pts[1:] if isinstance(item, list) and item and str(item[0]) == 'xy']
        shape = 'polygon'
    else:
        points, shape = [], 'unsupported'
    fill_node = child(node, 'fill')
    fill = str(fill_node[1]) if fill_node and len(fill_node) > 1 else 'none'
    return {'shape': shape, 'points': points, 'width': width, 'kind': kind, 'fill': fill,
            'bounds': row.get('bounds_mm')}


def svg_for(entry, before, after, before_context, after_context):
    all_points = before['points'] + after['points']
    if not all_points:
        all_points = [(0, 0), (1, 1)]
    minx = min(point[0] for point in all_points); maxx = max(point[0] for point in all_points)
    miny = min(point[1] for point in all_points); maxy = max(point[1] for point in all_points)
    pad = max(0.02, max(maxx - minx, maxy - miny, before['width'], after['width']) * 0.15)
    minx -= pad; maxx += pad; miny -= pad; maxy += pad
    spanx = max(maxx - minx, 0.5); spany = max(maxy - miny, 0.5)
    pane_w, pane_h = 590, 520
    scale = min((pane_w - 48) / spanx, (pane_h - 104) / spany)
    y_offset = 122 + max(0, ((pane_h - 104) - spany * scale) / 2)

    def transform(point, pane_x):
        x, y = point
        return pane_x + 24 + (x - minx) * scale, y_offset + (y - miny) * scale

    def draw(shape, pane_x, color, opacity=1, selected=False):
        points = shape['points']
        if not points:
            return ''
        coords = [transform(point, pane_x) for point in points]
        sw = min(9, max(1.1 if selected else 0.8, shape['width'] * scale))
        if shape['shape'] == 'circle' and len(points) > 1:
            cx, cy = coords[0]; radius = math.dist(points[0], points[1]) * scale
            return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius:.2f}" fill="none" stroke="{color}" stroke-width="{sw:.2f}" opacity="{opacity}"/>'
        pts = ' '.join(f'{x:.2f},{y:.2f}' for x, y in coords)
        if shape['shape'] == 'polygon':
            return f'<polygon points="{pts}" fill="none" stroke="{color}" stroke-width="{sw:.2f}" opacity="{opacity}"/>'
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{sw:.2f}" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}"/>'

    title = escape(entry['kind'] + ' · ' + entry['layer'] + ' · ' + entry['review_class'])
    before_id = escape(entry['before_identity']); after_id = escape(entry['after_identity'])
    accent = '#ad5c45' if entry['review_class'] == 'exact' else '#a66a12'
    bits = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="700" viewBox="0 0 1280 700" role="img" aria-label="{title} ORG and EDIT pair comparison">',
            '<rect width="1280" height="700" fill="#f7fafb"/>',
            f'<text x="28" y="36" font-family="Arial,sans-serif" font-size="23" font-weight="700" fill="#20313d">{title}</text>',
            f'<text x="28" y="66" font-family="Arial,sans-serif" font-size="15" fill="{accent}">{escape(entry["review_label"])}</text>',
            '<rect x="20" y="86" width="610" height="570" rx="10" fill="#fff" stroke="#ccd8de"/>',
            '<rect x="650" y="86" width="610" height="570" rx="10" fill="#fff" stroke="#ccd8de"/>',
            '<text x="42" y="112" font-family="Arial,sans-serif" font-size="17" font-weight="700" fill="#20313d">ORG · before</text>',
            '<text x="672" y="112" font-family="Arial,sans-serif" font-size="17" font-weight="700" fill="#20313d">EDIT · enhanced</text>']
    for shape in before_context: bits.append(draw(shape, 20, '#b9c6cc', 0.6))
    for shape in after_context: bits.append(draw(shape, 650, '#b9c6cc', 0.6))
    bits.append(draw(before, 20, '#bf634a', 1, True)); bits.append(draw(after, 650, '#17818a', 1, True))
    bits.extend([
        f'<text x="42" y="674" font-family="Arial,sans-serif" font-size="10" fill="#526875">{before_id}</text>',
        f'<text x="672" y="674" font-family="Arial,sans-serif" font-size="10" fill="#526875">{after_id}</text>',
        '<text x="640" y="693" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" fill="#657985">Same source-coordinate crop · nearby same-layer objects muted · stroke display is illustrative</text>',
        '</svg>'])
    return ''.join(bits)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity-map', type=Path, default=ROOT / 'out/ingestion/profile_materializations/szu-comm_org_edit_identity_map_20261021_01')
    parser.add_argument('--package', type=Path, default=ROOT / 'dataset/szu-comm_3020301113B_intake_ready_20261021_v2')
    parser.add_argument('--registry', type=Path, default=ROOT / 'out/ingestion/manual_profile_add/workbench/run-36c679dc7fbc45c7b91d804c68608a2b/registry.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'out/ingestion/manual_identity_review_szucomm')
    parser.add_argument('--dataset-id', default='client:szu-comm:3020301113b:intake-20261021:v1')
    args = parser.parse_args(argv)
    for path in (args.identity_map, args.package, args.registry):
        if not path.exists(): raise SystemExit('Missing input: ' + str(path))
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / 'out'): raise SystemExit('Output must stay under checkout/out')
    out.mkdir(parents=True, exist_ok=True)
    image_dir = out / 'images'; image_dir.mkdir(exist_ok=True)
    package = args.package.resolve()
    profile = json.loads((package / 'metadata/profile.json').read_text())
    profile_rows = {row['path']: row for row in profile['files']}
    paths = {'before': 'ORG/top.kicad_pcb', 'after': 'EDIT/top_layer.kicad_pcb'}
    raws = {}
    for side, rel in paths.items():
        raw = (package / 'raw' / rel).read_bytes()
        if hashlib.sha256(raw).hexdigest() != profile_rows[rel]['sha256']:
            raise SystemExit('Sealed source hash mismatch: ' + rel)
        raws[side] = raw
    identities = [json.loads(line) for line in (args.identity_map / 'identities.jsonl').read_text().splitlines()]
    identity_by = {(row['side'], row['identity']): row for row in identities}
    native_rows = {}
    for side in paths:
        probe = json.loads((ROOT / f'out/ingestion/profile_materializations/{side}_identity_probe.json').read_text())
        native_rows.update({(side, row['id']): row for row in probe['rows']})
    # Decode drawable objects once; each card can then select concise local context.
    shapes = {}
    for key, identity in identity_by.items():
        native = native_rows.get(key)
        if native:
            try:
                shapes[key] = source_object(raws[key[0]], native)
            except (ValueError, TypeError, IndexError, KeyError):
                # Preserve unsupported/degenerate objects in the manifest; skip only their drawing.
                continue
    exact = [json.loads(line) for line in (args.identity_map / 'pairs.jsonl').read_text().splitlines()]
    candidates = [json.loads(line) for line in (args.identity_map / 'registered_near_candidates.jsonl').read_text().splitlines()]
    entries = []
    for index, pair in enumerate(exact, 1):
        entries.append({'review_class':'exact','review_label':'Unique coordinate-anchor match · stroke width compared separately','before_identity':pair['before_identity'],'after_identity':pair['after_identity'],'kind':pair['kind'],'layer':pair['layer'],'net_code':pair['net_code'],'before_width_mm':pair['before_width_mm'],'after_width_mm':pair['after_width_mm'],'stroke_width_changed':pair['stroke_width_changed'],'keypoint_displacement_mm':None,'before_geometry_sha256':pair['before_geometry_sha256'],'after_geometry_sha256':pair['after_geometry_sha256']})
    for pair in candidates:
        entries.append({'review_class':'candidate','review_label':'Mutual-unique near-geometry candidate · 5 µm tolerance','before_identity':pair['before_identity'],'after_identity':pair['after_identity'],'kind':pair['kind'],'layer':pair['layer'],'net_code':pair['net_code'],'before_width_mm':identity_by['before',pair['before_identity']]['stroke_width_mm'],'after_width_mm':identity_by['after',pair['after_identity']]['stroke_width_mm'],'stroke_width_changed':None,'keypoint_displacement_mm':pair['max_corresponding_keypoint_displacement_mm'],'before_geometry_sha256':identity_by['before',pair['before_identity']]['geometry_sha256'],'after_geometry_sha256':identity_by['after',pair['after_identity']]['geometry_sha256']})
    entries.sort(key=lambda item: (item['layer'] != 'F.Cu', item['review_class'] != 'exact', item['kind'],
                                   item['before_identity'], item['after_identity']))
    # Local context is restricted to the same source layer and a 1.2 mm crop.
    side_rows = {side: [row for row in identities if row['side'] == side] for side in paths}
    by_identity = {(row['side'], row['identity']): row for row in identities}
    for index, entry in enumerate(entries, 1):
        entry['review_id'] = f'{index:05d}'
        entry['image_file'] = f'{entry["review_class"]}-{index:05d}.svg'
        before_key=('before',entry['before_identity']); after_key=('after',entry['after_identity'])
        before_shape=shapes[before_key]; after_shape=shapes[after_key]
        coords=before_shape['points']+after_shape['points']
        if coords:
            cx=sum(x for x,y in coords)/len(coords);cy=sum(y for x,y in coords)/len(coords)
        else:cx=cy=0
        contexts={}
        for side,focus in (('before',before_shape),('after',after_shape)):
            selected=[]
            for row in side_rows[side]:
                if row['identity']==entry['before_identity' if side=='before' else 'after_identity'] or row['layer']!=entry['layer']:
                    continue
                bounds=row.get('bounds_mm')
                if not bounds or not (bounds[0]<=cx+1.2 and bounds[2]>=cx-1.2 and bounds[1]<=cy+1.2 and bounds[3]>=cy-1.2):
                    continue
                shape=shapes.get((side,row['identity']))
                if shape and shape['points']:
                    ox=sum(x for x,y in shape['points'])/len(shape['points']);oy=sum(y for x,y in shape['points'])/len(shape['points'])
                    selected.append((math.hypot(ox-cx,oy-cy),shape))
            contexts[side]=[shape for _,shape in sorted(selected,key=lambda x:x[0])[:12]]
        (image_dir/entry['image_file']).write_text(svg_for(entry,before_shape,after_shape,contexts['before'],contexts['after']))
    manifest={'schema':'pcb-native-object-manual-review-v1','dataset_id':args.dataset_id,'profile_seal_sha256':json.loads((package/'metadata/manifest.json').read_text()).get('seal_sha256'),'source_files':{side:{'path':paths[side],'sha256':profile_rows[paths[side]]['sha256']} for side in paths},'coordinate_basis':'Source coordinates used as recorded; no independent invariant-feature registration is claimed.','entries':entries}
    manifest_path=out/'manifest.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    config=json.loads(args.registry.read_text())
    dataset=next((row for row in config['datasets'] if row['id']==args.dataset_id),None)
    if dataset is None:raise SystemExit('Dataset is absent from selected registry: '+args.dataset_id)
    expected_images={entry['image_file'] for entry in entries}
    for stale in image_dir.glob('*.svg'):
        if stale.name not in expected_images:
            stale.unlink()
    file_bindings=[]
    for path in [manifest_path,*(image_dir/entry['image_file'] for entry in entries)]:
        binding={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)}
        file_bindings.append(binding)
    config.setdefault('identity_reviews',{})[args.dataset_id]={
        'manifest':file_bindings[0], 'images':file_bindings[1:],
        'summary':{'exact_pairs':len(exact),'near_geometry_candidates':len(candidates),'image_count':len(entries),
                   'source_hashes':{side:profile_rows[paths[side]]['sha256'] for side in paths}}}
    registry_out=out/'registry_identity_review.json';registry_out.write_text(json.dumps(config,indent=2)+'\n')
    print(json.dumps({'status':'PASS','output':out.relative_to(ROOT).as_posix(),'images':len(entries),'exact_pairs':len(exact),'near_geometry_candidates':len(candidates),'manifest':manifest_path.relative_to(ROOT).as_posix(),'registry':registry_out.relative_to(ROOT).as_posix()}))


if __name__ == '__main__':
    main()
