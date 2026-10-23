#!/usr/bin/env python3
"""Build a deterministic arc coupon at measured EDIT widths and lengths."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path('assets/starter/fixtures/before/kicad/coupon.kicad_pcb')
REAL_ARC_EVIDENCE = Path('out/ingestion/gerber_fidelity/degenerate_arcs_20261024_v1/degenerate_arc_plot_evidence.json')
CLI = Path('/Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def uid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'pcb-aperture-cam-real-scale-g8:{name}'))


def verify_assets():
    manifest = ROOT / 'contracts/asset_manifest.sha256'
    rows = []
    errors = []
    for line in manifest.read_text().splitlines():
        expected, rel = line.split('  ', 1)
        p = ROOT / rel
        actual = sha(p) if p.is_file() else None
        rows.append({'path': rel, 'expected_sha256': expected, 'actual_sha256': actual,
                     'status': 'PASS' if expected == actual else 'FAIL'})
        if expected != actual:
            errors.append(rel)
    if errors:
        raise SystemExit(f'asset manifest mismatch: {errors}')
    return rows


def q6(value):
    return round(float(value), 6)


def build_features(evidence):
    arcs = evidence['arcs']
    shortest = min(arcs, key=lambda r: r['centerline_length_mm'])
    longest = max(arcs, key=lambda r: r['centerline_length_mm'])
    narrowest = min(arcs, key=lambda r: r['width_mm'])
    widest = max(arcs, key=lambda r: r['width_mm'])
    median_length = sorted(arcs, key=lambda r: r['centerline_length_mm'])[len(arcs) // 2]

    def straight(name, x, y, row, reverse=False):
        length, width = q6(row['centerline_length_mm']), q6(row['width_mm'])
        a, b = [x, y], [x + length, y]
        if reverse:
            a, b = b, a
        mid = [(a[0] + b[0]) / 2, y]
        return {'id': name, 'start': [q6(x) if not reverse else q6(x + length), q6(y)],
                'mid': [q6((x + x + length) / 2), q6(y)],
                'end': [q6(x + length) if not reverse else q6(x), q6(y)],
                'width': width, 'expected': 'round_stroke',
                'parameter_source_identity': row['source_identity'],
                'reported_length_mm': row['centerline_length_mm'],
                'reported_width_mm': row['width_mm']}

    short = straight('shortest_real_scale_isolated', 28.0, 20.0, shortest)
    reverse_short = straight('shortest_real_scale_reversed', 33.0, 20.0, shortest, True)
    narrow = straight('narrowest_real_width', 38.0, 20.0, narrowest)
    wide = straight('widest_real_width', 44.0, 20.0, widest)
    long = straight('longest_real_scale', 51.0, 20.0, longest)
    median = straight('median_length_reference', 58.0, 20.0, median_length)
    overlap = straight('micro_arc_with_partial_segment', 65.0, 20.0, shortest)
    shared_a = straight('shared_micro_arc_a', 72.0, 20.0, shortest)
    shared_b = straight('shared_micro_arc_b', 72.0 + q6(shortest['centerline_length_mm']), 20.0, shortest)

    # Near-collinear controls use the real median span/width and fixed sagitta.
    near_length, near_width = q6(median_length['centerline_length_mm']), q6(median_length['width_mm'])
    def curved(name, x, y, sagitta):
        return {'id': name, 'start': [q6(x), q6(y)],
                'mid': [q6(x + near_length / 2), q6(y + sagitta)],
                'end': [q6(x + near_length), q6(y)], 'width': near_width,
                'expected': 'native_arc', 'sagitta_mm': sagitta,
                'parameter_source_identity': median_length['source_identity']}
    near = curved('near_collinear_real_scale_10um', 28.0, 27.0, 0.00001)
    quantized = curved('near_collinear_real_scale_1um', 33.0, 27.0, 0.000001)

    cases = [
        {**short, 'roi_bounds_mm': [27.0, 18.8, 29.2, 21.2]},
        {**reverse_short, 'roi_bounds_mm': [32.0, 18.8, 34.2, 21.2]},
        {**narrow, 'roi_bounds_mm': [37.0, 18.8, 39.2, 21.2]},
        {**wide, 'roi_bounds_mm': [42.5, 18.0, 46.0, 22.0]},
        {**long, 'roi_bounds_mm': [50.0, 18.8, 52.2, 21.2]},
        {**median, 'roi_bounds_mm': [57.0, 18.8, 59.2, 21.2]},
        {**overlap, 'expected': 'round_stroke_plus_segment',
         'context_segment': {'start': [q6(65.0 + q6(shortest['centerline_length_mm']) / 3), 20.0],
                             'end': [q6(65.0 + 2 * q6(shortest['centerline_length_mm']) / 3), 20.0],
                             'width': 0.04},
         'roi_bounds_mm': [64.0, 18.8, 66.2, 21.2]},
        {'id': 'shared_shortest_micro_pair', 'features': [shared_a, shared_b],
         'expected': 'union_of_round_strokes', 'roi_bounds_mm': [71.0, 18.8, 74.0, 21.2]},
        {**near, 'roi_bounds_mm': [27.0, 25.8, 29.2, 28.2]},
        {**quantized, 'roi_bounds_mm': [32.0, 25.8, 34.2, 28.2]},
    ]
    return cases, {'shortest': shortest, 'longest': longest, 'narrowest': narrowest,
                   'widest': widest, 'median_length': median_length}


def run(args):
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / 'out'):
        raise SystemExit('coupon output must stay under out/')
    if output.exists():
        raise SystemExit(f'refusing to overwrite existing output: {output}')
    asset_rows = verify_assets()
    evidence_path = ROOT / REAL_ARC_EVIDENCE
    evidence = json.loads(evidence_path.read_text())
    cases, selected = build_features(evidence)
    template = ROOT / TEMPLATE
    text = template.read_text()
    text = text.replace('(gr_rect locked (start 17.0 17.0) (end 26.0 29.0)',
                        '(gr_rect locked (start 17.0 17.0) (end 76.0 33.0)')
    if text.rstrip()[-1] != ')':
        raise SystemExit('unexpected immutable coupon template shape')
    text = text.rstrip()[:-1]
    context_segments = []
    for case in cases:
        if case.get('context_segment'):
            context_segments.append(case['context_segment'])
            seg = case['context_segment']
            text += (f'\n (segment (start {seg["start"][0]:.6f} {seg["start"][1]:.6f}) '
                     f'(end {seg["end"][0]:.6f} {seg["end"][1]:.6f}) '
                     f'(width {seg["width"]:.6f}) (layer "F.Cu") (net 1) '
                     f'(tstamp {uid(case["id"]+":segment")}))\n')
        for feature in case.get('features', [case]):
            points = ' '.join(f'({key} {v[0]:.6f} {v[1]:.6f})' for key,v in (
                ('start',feature['start']),('mid',feature['mid']),('end',feature['end'])))
            text += (f' (arc {points} (width {feature["width"]:.6f}) (layer "F.Cu") '
                     f'(net 1) (tstamp {uid(feature["id"])}))\n')
    text += ')\n'
    output.mkdir(parents=True)
    board = output / 'coupon.kicad_pcb'
    board.write_text(text)
    spec = {
        'schema': 'g8-real-scale-arc-coupon/1',
        'status': 'SYNTHETIC_NOT_FOR_FABRICATION',
        'source_template': TEMPLATE.as_posix(), 'source_template_sha256': sha(template),
        'asset_manifest_path': 'contracts/asset_manifest.sha256',
        'asset_manifest_verified_count': len(asset_rows),
        'parameter_evidence_path': REAL_ARC_EVIDENCE.as_posix(),
        'parameter_evidence_sha256': sha(evidence_path),
        'parameter_source_sha256': evidence['source']['sha256'],
        'parameter_gerber_sha256': evidence['gerber']['sha256'],
        'generated_source_sha256': sha(board),
        'measured_parameter_envelope': {
            'length_min_mm': min(x['centerline_length_mm'] for x in evidence['arcs']),
            'length_max_mm': max(x['centerline_length_mm'] for x in evidence['arcs']),
            'width_min_mm': min(x['width_mm'] for x in evidence['arcs']),
            'width_max_mm': max(x['width_mm'] for x in evidence['arcs']),
        },
        'selected_source_examples': {k:{'identity':v['source_identity'],
              'length_mm':v['centerline_length_mm'],'width_mm':v['width_mm']} for k,v in selected.items()},
        'cases': cases,
        'case_semantics': 'Expected strokes and circular controls are independently authored from the measured parameter envelope; no native EDIT coordinates are copied into this synthetic board. Exact-collinear cases assert round-capped line strokes only for this coupon contract.',
    }
    (output/'expected_spec.json').write_text(json.dumps(spec,indent=2)+'\n')
    policy={
        'schema':'g8-real-scale-arc-accuracy-policy/1',
        'status':'FROZEN_BEFORE_METRIC_EVALUATION',
        'scope':'Synthetic KiCad F.Cu coupon at the measured EDIT length/width envelope; not manufacturing acceptance.',
        'coordinate_profile':{'units':'millimetres','gerber_format':'absolute coordinates, six decimal places','minimum_coordinate_quantum_mm':1e-6},
        'acceptance_by_feature':{
            'maximum_symmetric_difference_area_mm2':0.0001,
            'maximum_relative_symmetric_difference_fraction':0.01,
            'maximum_boundary_hausdorff_distance_mm':0.00002,
            'topology':'Expected and plotted clipped geometry must have equal connected-component and hole counts.',
            'unsupported_semantics':'No unsupported source case is promoted by this diagnostic coupon.'},
        'basis':'Frozen experiment envelope using inventory geometry error 2e-5 mm, 1e-5 mm curve approximation, 1e-6 mm Gerber quantum, plus a 1% relative symmetric-area guard for small stroke footprints. Not a product or fabrication requirement.'}
    (output/'accuracy_policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    version=subprocess.run([str(CLI),'version'],capture_output=True,text=True,check=False)
    out_dir=output/'gerbers'
    argv=[str(CLI),'pcb','export','gerbers','--layers','F.Cu','--precision','6','--no-protel-ext','--check-zones','-o',str(out_dir.resolve())+'/',str(board.resolve())]
    res=subprocess.run(argv,capture_output=True,text=True,check=False)
    out_dir.mkdir(exist_ok=True)
    (output/'export.stdout.txt').write_text(res.stdout)
    (output/'export.stderr.txt').write_text(res.stderr)
    receipt={'argv':argv,'exit_code':res.returncode,'tool':str(CLI),'tool_sha256':sha(CLI),
             'tool_version_stdout':version.stdout.strip(),'tool_version_stderr':version.stderr.strip(),
             'source_sha256':sha(board),'source_template_sha256':sha(template),
             'parameter_evidence_sha256':sha(evidence_path),'asset_manifest_verified_count':len(asset_rows),
             'outputs':{p.name:sha(p) for p in sorted(out_dir.iterdir()) if p.is_file()},
             'stdout':res.stdout,'stderr':res.stderr}
    (output/'export_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':'PASS' if res.returncode==0 else 'FAIL','source_sha256':receipt['source_sha256'],
                      'gerber_sha256':receipt['outputs'].get('coupon-F_Cu.gbr'),
                      'asset_manifest_entries_verified':len(asset_rows),'cases':len(cases),'exit_code':res.returncode},indent=2))
    if res.returncode: raise SystemExit(res.returncode)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='out/ingestion/gerber_fidelity/g8_real_scale_coupon_20261024_v1')
    run(parser.parse_args())


if __name__=='__main__': main()
