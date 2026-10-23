#!/usr/bin/env python3
"""Build and plot a deterministic synthetic KiCad arc coupon under out/."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path('assets/starter/fixtures/before/kicad/coupon.kicad_pcb')
CLI = Path('/Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'pcb-aperture-cam-g7-coupon-v1:{name}'))


def verify_assets():
    manifest = ROOT / 'contracts/asset_manifest.sha256'
    rows = []
    errors = []
    for line in manifest.read_text().splitlines():
        expected, rel = line.split('  ', 1)
        path = ROOT / rel
        actual = sha(path) if path.is_file() else None
        rows.append({'path': rel, 'expected_sha256': expected,
                     'actual_sha256': actual, 'status': 'PASS' if actual == expected else 'FAIL'})
        if actual != expected:
            errors.append(rel)
    if errors:
        raise SystemExit(f'asset manifest mismatch: {errors}')
    return rows


def run(args):
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / 'out'):
        raise SystemExit('coupon output must stay under out/')
    if output.exists():
        raise SystemExit(f'refusing to overwrite existing output: {output}')
    asset_rows = verify_assets()
    template = ROOT / TEMPLATE
    text = template.read_text()
    if text.rstrip()[-1] != ')':
        raise SystemExit('unexpected coupon template shape')
    text = text.replace('(gr_rect locked (start 17.0 17.0) (end 26.0 29.0)',
                        '(gr_rect locked (start 17.0 17.0) (end 43.0 33.0)')
    text = text.rstrip()[:-1]
    features = [
        {'id': 'exact_forward_isolated', 'start': [28.0, 20.0], 'mid': [29.0, 20.0], 'end': [30.0, 20.0], 'width': 0.2, 'expected': 'round_stroke'},
        {'id': 'exact_reversed_isolated', 'start': [33.0, 20.0], 'mid': [32.0, 20.0], 'end': [31.0, 20.0], 'width': 0.2, 'expected': 'round_stroke'},
        {'id': 'exact_overlap_with_segment', 'start': [35.0, 20.0], 'mid': [36.0, 20.0], 'end': [37.0, 20.0], 'width': 0.2, 'expected': 'round_stroke'},
        {'id': 'near_collinear_control', 'start': [28.0, 26.0], 'mid': [29.0, 26.001], 'end': [30.0, 26.0], 'width': 0.2, 'expected': 'native_arc'},
        {'id': 'curved_arc_control', 'start': [33.0, 26.0], 'mid': [34.0, 27.0], 'end': [35.0, 26.0], 'width': 0.2, 'expected': 'native_arc'},
        {'id': 'exact_shared_roi_a', 'start': [38.0, 20.0], 'mid': [38.5, 20.0], 'end': [39.0, 20.0], 'width': 0.16, 'expected': 'round_stroke'},
        {'id': 'exact_shared_roi_b', 'start': [39.0, 20.0], 'mid': [39.5, 20.0], 'end': [40.0, 20.0], 'width': 0.16, 'expected': 'round_stroke'},
    ]
    context_segment = {'start': [34.8, 20.0], 'end': [36.4, 20.0], 'width': 0.1}
    text += f'\n (segment (start {context_segment["start"][0]:.6f} {context_segment["start"][1]:.6f}) (end {context_segment["end"][0]:.6f} {context_segment["end"][1]:.6f}) (width {context_segment["width"]:.6f}) (layer "F.Cu") (net 1) (tstamp {stable_uuid("overlap_context_segment")}))\n'
    for feature in features:
        points = ' '.join(f'({key} {point[0]:.6f} {point[1]:.6f})'
                          for key, point in (('start', feature['start']),
                                             ('mid', feature['mid']),
                                             ('end', feature['end'])))
        text += (f' (arc {points} (width {feature["width"]:.6f}) '
                 f'(layer "F.Cu") (net 1) (tstamp {stable_uuid(feature["id"])}))\n')
    text += ')\n'
    output.mkdir(parents=True)
    board = output / 'coupon.kicad_pcb'
    board.write_text(text)
    cases = [
        {**features[0], 'roi_bounds_mm': [27.5, 19.5, 30.5, 20.5]},
        {**features[1], 'roi_bounds_mm': [30.5, 19.5, 33.5, 20.5]},
        {**features[2], 'expected': 'round_stroke_plus_segment',
         'context_segment': context_segment, 'roi_bounds_mm': [34.2, 19.5, 37.5, 20.5]},
        {**features[3], 'roi_bounds_mm': [27.5, 25.5, 30.5, 26.5]},
        {**features[4], 'roi_bounds_mm': [32.5, 25.5, 35.5, 27.5]},
        {'id': 'exact_shared_roi_pair', 'features': [features[5], features[6]],
         'expected': 'union_of_round_strokes', 'roi_bounds_mm': [37.5, 19.5, 40.5, 20.5]},
    ]
    spec = {
        'schema': 'g7-collinear-arc-coupon/1',
        'status': 'SYNTHETIC_NOT_FOR_FABRICATION',
        'source_template': TEMPLATE.as_posix(),
        'source_template_sha256': sha(template),
        'asset_manifest_path': 'contracts/asset_manifest.sha256',
        'asset_manifest_verified_count': len(asset_rows),
        'asset_manifest_status': 'PASS',
        'generated_source_sha256': sha(board),
        'authored_features': features,
        'context_segment': context_segment,
        'cases': cases,
        'case_semantics': 'Exact-collinear cases assert a round-capped straight stroke; near-collinear and curved controls assert the analytic circle through start/mid/end. Fixed case ROIs are disjoint. The shared-context and overlapping-track cases are evaluated as unions.',
    }
    (output / 'expected_spec.json').write_text(json.dumps(spec, indent=2) + '\n')
    policy = {
        'schema': 'g7-geometry-accuracy-policy/1',
        'status': 'FROZEN_BEFORE_METRIC_EVALUATION',
        'scope': 'Synthetic KiCad F.Cu coupon geometry fidelity only; not manufacturing acceptance.',
        'coordinate_profile': {'units': 'millimetres', 'gerber_format': 'absolute coordinates, six decimal places',
                               'maximum_source_coordinate_decimal_places': 6,
                               'minimum_coordinate_quantum_mm': 0.000001},
        'acceptance_by_feature': {
            'maximum_symmetric_difference_area_mm2': 0.0001,
            'maximum_boundary_hausdorff_distance_mm': 0.00002,
            'topology': 'Expected and plotted clipped geometry must have equal connected-component and hole counts; empty/nonempty status must agree.',
            'measurement': 'Each authored case is evaluated in a fixed, non-overlapping context ROI. Shared-context cases are assessed as a union, with each authored source arc identity retained.',
            'unsupported_semantics': 'A feature class without a unique expected geometric interpretation is NOT_ESTABLISHED; it cannot pass by choosing the closest fallback after observing the plot.'},
        'basis': 'The envelope bounds this comparison using native_inventory geometry error 2e-5 mm, curve approximation 1e-5 mm, and 1e-6 mm Gerber coordinate quantum. This is an experiment threshold, not a fabrication or product specification.'}
    (output / 'accuracy_policy.json').write_text(json.dumps(policy, indent=2) + '\n')
    cli_version = subprocess.run([str(CLI), 'version'], capture_output=True, text=True, check=False)
    if cli_version.returncode != 0:
        raise SystemExit('pinned KiCad CLI version command failed')
    out_dir = output / 'gerbers'
    argv = [str(CLI), 'pcb', 'export', 'gerbers', '--layers', 'F.Cu',
            '--precision', '6', '--no-protel-ext', '--check-zones',
            '-o', str(out_dir.resolve()) + '/', str(board.resolve())]
    exported = subprocess.run(argv, capture_output=True, text=True, check=False)
    out_dir.mkdir(exist_ok=True)
    (output / 'export.stdout.txt').write_text(exported.stdout)
    (output / 'export.stderr.txt').write_text(exported.stderr)
    receipt = {
        'argv': argv, 'exit_code': exported.returncode,
        'tool': str(CLI), 'tool_sha256': sha(CLI),
        'tool_version_stdout': cli_version.stdout.strip(),
        'tool_version_stderr': cli_version.stderr.strip(),
        'source_sha256': sha(board), 'source_template_sha256': sha(template),
        'asset_manifest_verified_count': len(asset_rows),
        'outputs': {p.name: sha(p) for p in sorted(out_dir.iterdir()) if p.is_file()},
        'stdout': exported.stdout, 'stderr': exported.stderr,
    }
    (output / 'export_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': 'PASS' if exported.returncode == 0 else 'FAIL',
                      'asset_manifest_entries_verified': len(asset_rows),
                      'source_sha256': receipt['source_sha256'],
                      'outputs': receipt['outputs'], 'exit_code': exported.returncode}, indent=2))
    if exported.returncode != 0:
        raise SystemExit(exported.returncode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='out/ingestion/gerber_fidelity/g7_coupon_20261024_v3')
    run(parser.parse_args())


if __name__ == '__main__':
    main()
