#!/usr/bin/env python3
"""Evaluate frozen synthetic KiCad arc expectations against fresh F.Cu plot."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gerber_image import read_image
from src.native_inventory import inventory, steps
from src.native_reference import one
from tools.validate_copper_plot_fidelity import sha
import sexpdata


def source_arc(source: bytes, item: dict) -> dict:
    start, end = item['source_span']
    node = sexpdata.loads(source[start:end].decode('utf-8'))
    return {
        'start': list(map(float, one(node, 'start'))),
        'mid': list(map(float, one(node, 'mid'))),
        'end': list(map(float, one(node, 'end'))),
        'width': float(one(node, 'width')[0]),
    }


def independent_centerline(points: dict, max_error_mm: float = 1e-5):
    """Sample the unique circle through non-collinear start/mid/end points."""
    a, m, b = points['start'], points['mid'], points['end']
    ax, ay = a; mx, my = m; bx, by = b
    determinant = 2 * (ax * (my - by) + mx * (by - ay) + bx * (ay - my))
    if abs(determinant) < 1e-12:
        raise ValueError('collinear points do not define a unique circular arc')
    aa, mm, bb = ax * ax + ay * ay, mx * mx + my * my, bx * bx + by * by
    cx = (aa * (my - by) + mm * (by - ay) + bb * (ay - my)) / determinant
    cy = (aa * (bx - mx) + mm * (ax - bx) + bb * (mx - ax)) / determinant
    angle = lambda p: math.atan2(p[1] - cy, p[0] - cx)
    start_angle, mid_angle, end_angle = angle(a), angle(m), angle(b)
    ccw_end = (end_angle - start_angle) % (2 * math.pi)
    ccw_mid = (mid_angle - start_angle) % (2 * math.pi)
    sweep = ccw_end if ccw_mid <= ccw_end else ccw_end - 2 * math.pi
    radius = math.hypot(ax - cx, ay - cy)
    max_angle = 2 * math.acos(max(-1.0, min(1.0, 1 - max_error_mm / radius)))
    count = max(1, math.ceil(abs(sweep) / max_angle))
    return LineString([a] + [
        (cx + radius * math.cos(start_angle + sweep * i / count),
         cy + radius * math.sin(start_angle + sweep * i / count))
        for i in range(1, count)
    ] + [b])


def stroke(points: dict):
    start, end = points['start'], points['end']
    mid = points['mid']
    dx, dy = end[0] - start[0], end[1] - start[1]
    det = abs(dx * (start[1] - mid[1]) - (start[0] - mid[0]) * dy)
    length = math.hypot(dx, dy)
    if length == 0:
        raise ValueError('zero-length endpoints in coupon spec')
    deviation = det / length
    radius = points['width'] / 2
    if deviation <= 1e-12:
        centerline = LineString([start, end])
    else:
        centerline = independent_centerline(points)
    return centerline.buffer(radius, quad_segs=steps(radius),
                             cap_style='round', join_style='round')


def polygon_topology(geom):
    if geom.is_empty:
        return {'components': 0, 'holes': 0, 'empty': True}
    polygons = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
    return {'components': len(polygons),
            'holes': sum(len(p.interiors) for p in polygons),
            'empty': False}


def metrics(expected, plotted):
    intersection = expected.intersection(plotted)
    return {
        'expected_area_mm2': expected.area,
        'plotted_area_mm2': plotted.area,
        'symmetric_difference_area_mm2': expected.symmetric_difference(plotted).area,
        'boundary_hausdorff_distance_mm': expected.boundary.hausdorff_distance(plotted.boundary),
        'symmetric_difference_fraction_of_expected': (expected.symmetric_difference(plotted).area / expected.area) if expected.area else None,
        'expected_topology': polygon_topology(expected),
        'plotted_topology': polygon_topology(plotted),
        'expected_covered_fraction': intersection.area / expected.area if expected.area else None,
    }


def within_accuracy_policy(measurement: dict, acceptance: dict) -> bool:
    if measurement['symmetric_difference_area_mm2'] > acceptance['maximum_symmetric_difference_area_mm2']:
        return False
    if measurement['boundary_hausdorff_distance_mm'] > acceptance['maximum_boundary_hausdorff_distance_mm']:
        return False
    relative = acceptance.get('maximum_relative_symmetric_difference_fraction')
    return relative is None or measurement['symmetric_difference_fraction_of_expected'] <= relative


def run(args):
    source_path = (ROOT / args.source).resolve()
    gerber_path = (ROOT / args.gerber).resolve()
    spec_path = (ROOT / args.spec).resolve()
    policy_path = (ROOT / args.policy).resolve()
    receipt_path = (ROOT / args.receipt).resolve()
    output = (ROOT / args.output).resolve()
    for path in (source_path, gerber_path, spec_path, policy_path, receipt_path):
        if not path.is_relative_to(ROOT):
            raise SystemExit(f'path outside checkout: {path}')
    if not output.is_relative_to(ROOT / 'out'):
        raise SystemExit('output must stay under out/')
    if output.exists():
        raise SystemExit(f'refusing to overwrite existing output: {output}')

    source = source_path.read_bytes()
    spec = json.loads(spec_path.read_text())
    policy = json.loads(policy_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    if policy.get('status') != 'FROZEN_BEFORE_METRIC_EVALUATION':
        raise SystemExit('accuracy policy is not frozen')
    source_hash, gerber_hash = sha(source_path), sha(gerber_path)
    if source_hash != spec['generated_source_sha256'] or source_hash != receipt['source_sha256']:
        raise SystemExit('coupon source hash does not match specification and export receipt')
    if receipt['outputs'].get(gerber_path.name) != gerber_hash:
        raise SystemExit('coupon Gerber hash does not match native export receipt')
    if receipt['exit_code'] != 0 or receipt['tool_version_stdout'] != '10.99.0':
        raise SystemExit('native KiCad export receipt is not successful/pinned')
    cli_path = Path(receipt['tool'])
    if not cli_path.is_file() or sha(cli_path) != receipt['tool_sha256']:
        raise SystemExit('native KiCad CLI bytes differ from the export receipt')
    asset_manifest = ROOT / spec['asset_manifest_path']
    asset_rows = []
    asset_errors = []
    for line in asset_manifest.read_text().splitlines():
        expected, rel = line.split('  ', 1)
        path = ROOT / rel
        actual = sha(path) if path.is_file() else None
        asset_rows.append({'path': rel, 'expected_sha256': expected,
                           'actual_sha256': actual,
                           'status': 'PASS' if expected == actual else 'FAIL'})
        if expected != actual:
            asset_errors.append(rel)
    if asset_errors or len(asset_rows) != spec['asset_manifest_verified_count']:
        raise SystemExit(f'asset manifest verification failed: {asset_errors}')
    template_path = ROOT / spec['source_template']
    if sha(template_path) != spec['source_template_sha256']:
        raise SystemExit('immutable source template hash differs from coupon spec')

    inv = inventory(source)
    objects = inv['objects']
    arc_rows = [row for row in objects if row.get('kind') == 'arc' and 'F.Cu' in row.get('layers', [])]
    parsed = read_image(gerber_path)
    plotted = affinity.scale(parsed['geometry'], xfact=1, yfact=-1, origin=(0, 0))
    bounds = [case['roi_bounds_mm'] for case in spec['cases']]
    for i, left in enumerate(bounds):
        for right in bounds[i + 1:]:
            if not (left[2] <= right[0] or right[2] <= left[0]
                    or left[3] <= right[1] or right[3] <= left[1]):
                raise SystemExit('coupon case ROIs overlap; revise fixed authored scope')

    rows = []
    for case in spec['cases']:
        feature_specs = case.get('features', [case])
        matched = []
        expected_parts = []
        for feature in feature_specs:
            found = []
            for item in arc_rows:
                arc = source_arc(source, item)
                if (arc['start'] == feature['start'] and arc['mid'] == feature['mid']
                        and arc['end'] == feature['end']
                        and abs(arc['width'] - feature['width']) < 1e-9):
                    found.append((item, arc))
            if len(found) != 1:
                raise SystemExit(f"coupon feature {feature['id']} resolved to {len(found)} source arcs")
            item, arc = found[0]
            matched.append(item)
            expected_parts.append(stroke(feature))
        roi = box(*case['roi_bounds_mm'])
        expected = unary_union(expected_parts)
        if 'context_segment' in case:
            seg = case['context_segment']
            expected = unary_union([expected, LineString([seg['start'], seg['end']]).buffer(
                seg['width'] / 2, quad_segs=steps(seg['width'] / 2),
                cap_style='round', join_style='round')])
        expected_clip = expected.intersection(roi)
        plot_clip = plotted.intersection(roi)
        measurement = metrics(expected_clip, plot_clip)
        parser_status = []
        for item in matched:
            parser_status.append({
                'identity': item['id'],
                'unsupported_reason': item.get('unsupported_reason'),
                'geometry_supported': bool(item.get('geometry_sha256')),
            })
        topology_match = measurement['expected_topology'] == measurement['plotted_topology']
        relative_limit = policy['acceptance_by_feature'].get('maximum_relative_symmetric_difference_fraction')
        numerical_match = within_accuracy_policy(measurement, policy['acceptance_by_feature'])
        expected_kind = case['expected']
        exact_semantics = expected_kind in ('round_stroke', 'round_stroke_plus_segment', 'union_of_round_strokes')
        parser_expectation_match = all(
            (row['unsupported_reason'] == 'DEGENERATE_ARC' and not row['geometry_supported'])
            if exact_semantics else (row['geometry_supported'] and row['unsupported_reason'] is None)
            for row in parser_status)
        rows.append({
            'case_id': case['id'], 'expected_kind': expected_kind,
            'roi_bounds_mm': case['roi_bounds_mm'],
            'source_arc_identities': [row['id'] for row in matched],
            'source_parser_classification': parser_status,
            'parser_classification_matches_contract': parser_expectation_match,
            'measurement': measurement,
            'tolerances_mm2_mm': {
                'symmetric_difference_area_mm2': policy['acceptance_by_feature']['maximum_symmetric_difference_area_mm2'],
                'boundary_hausdorff_distance_mm': policy['acceptance_by_feature']['maximum_boundary_hausdorff_distance_mm'],
                'maximum_relative_symmetric_difference_fraction': relative_limit,
            },
            'topology_matches': topology_match,
            'numerical_tolerances_pass': numerical_match,
            'status': 'PASS' if topology_match and numerical_match and parser_expectation_match else 'FAIL',
        })
    overall = 'PASS' if all(row['status'] == 'PASS' for row in rows) else 'FAIL'
    report = {
        'schema': 'native-collinear-arc-coupon-results/1',
        'status': overall,
        'scope': 'synthetic coupon geometry only; no production parser promotion or manufacturing acceptance',
        'source': {'path': str(source_path.relative_to(ROOT)), 'sha256': source_hash},
        'gerber': {'path': str(gerber_path.relative_to(ROOT)), 'sha256': gerber_hash,
                   'file_function': parsed['file_attrs'].get('.FileFunction'),
                   'unit_profile': 'strict mm absolute profile',
                   'gerber_object_count': len(parsed['objects'])},
        'template': {'path': spec['source_template'], 'sha256': spec['source_template_sha256']},
        'asset_manifest': {'path': spec['asset_manifest_path'],
                           'entry_count': len(asset_rows),
                           'verified_count': len(asset_rows), 'status': 'PASS'},
        'accuracy_policy': {'path': str(policy_path.relative_to(ROOT)),
                            'sha256': sha(policy_path), 'content': policy},
        'expected_specification': {'path': str(spec_path.relative_to(ROOT)),
                                   'sha256': sha(spec_path)},
        'implementation_hashes': {
            'qualifier_sha256': sha(Path(__file__).resolve()),
            'copper_fidelity_sha256': sha(ROOT / 'src/copper_fidelity.py'),
            'native_inventory_sha256': sha(ROOT / 'src/native_inventory.py'),
            'gerber_image_sha256': sha(ROOT / 'src/gerber_image.py'),
        },
        'export_receipt': {'path': str(receipt_path.relative_to(ROOT)),
                           'sha256': sha(receipt_path), 'tool_version': receipt['tool_version_stdout'],
                           'exit_code': receipt['exit_code']},
        'native_inventory': {'version': inv['version'],
                             'fcu_arc_count': len(arc_rows),
                             'unsupported_fcu_arc_count': sum(bool(x.get('unsupported_reason')) for x in arc_rows)},
        'cases': rows,
        'limitations': [
            'PASS applies only to the authored geometry classes, numerical policy, pinned tool, and coupon cases.',
            'The expected round-stroke result for exact-collinear records is an explicit test contract, not a claim about all KiCad versions or malformed native records.',
            'The measurement path shares Shapely/GEOS for expected buffer and Gerber composition; KiCad is the native plotting producer.',
            'This does not qualify the 84 real-board records; they require a separate compatibility check after this coupon.',
            'No production parser classification is changed and no fabrication or engineering acceptance is implied.',
        ],
    }
    output.mkdir(parents=True)
    (output / 'coupon_results.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    md=['# Native arc coupon result','',f"**Overall synthetic coupon result: {overall}.** This is restricted to the authored cases and frozen numeric envelope.",'',
        f"Source board SHA-256 `{source_hash}`; F.Cu Gerber SHA-256 `{gerber_hash}`; KiCad CLI {receipt['tool_version_stdout']}.",'',
        f"Frozen limits: symmetric difference ≤ {policy['acceptance_by_feature']['maximum_symmetric_difference_area_mm2']} mm²; boundary Hausdorff ≤ {policy['acceptance_by_feature']['maximum_boundary_hausdorff_distance_mm']} mm; topology must match exactly.",'',
        '| Case | Expected geometry | Parser classification | Symmetric difference mm² | Relative area | Hausdorff mm | Topology | Status |','|---|---|---|---:|---:|---:|---|---|']
    for row in rows:
        m=row['measurement']; cls=', '.join(x['unsupported_reason'] or ('supported' if x['geometry_supported'] else 'unknown') for x in row['source_parser_classification'])
        md.append(f"| {row['case_id']} | {row['expected_kind']} | {cls} | {m['symmetric_difference_area_mm2']:.9g} | {m['symmetric_difference_fraction_of_expected']:.6g} | {m['boundary_hausdorff_distance_mm']:.9g} | {'match' if row['topology_matches'] else 'mismatch'} | {row['status']} |")
    md += ['', 'Exact-collinear source arcs remain classified as `DEGENERATE_ARC`/unsupported by `native_inventory`; this coupon does not promote the production parser. A passing result establishes only that the pinned KiCad export matches the authored test geometry within the frozen envelope for these cases. The 84 real EDIT records still need a separate compatibility decision.', '', 'Full source identities, ROIs, topology counts, and measurement values are in `coupon_results.json`.', '']
    (output/'README.md').write_text('\n'.join(md))
    files=sorted(p for p in output.iterdir() if p.is_file() and p.name!='SHA256SUMS')
    (output/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in files))
    print(json.dumps({'status':overall,'cases':len(rows),'case_statuses':{x['case_id']:x['status'] for x in rows},'output':str(output.relative_to(ROOT))},indent=2))


def main():
    parser=argparse.ArgumentParser()
    base='out/ingestion/gerber_fidelity/g7_coupon_20261024_v3'
    parser.add_argument('--source',default=f'{base}/coupon.kicad_pcb')
    parser.add_argument('--gerber',default=f'{base}/gerbers/coupon-F_Cu.gbr')
    parser.add_argument('--spec',default=f'{base}/expected_spec.json')
    parser.add_argument('--policy',default=f'{base}/accuracy_policy.json')
    parser.add_argument('--receipt',default=f'{base}/export_receipt.json')
    parser.add_argument('--output',default=f'{base}/results_v2')
    run(parser.parse_args())


if __name__=='__main__':
    main()
