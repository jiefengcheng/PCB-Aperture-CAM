#!/usr/bin/env python3
"""Build paired KiCad plots for controlled degenerate-arc attribution cases.

This diagnostic tests whether a source arc's incremental copper can be isolated
from a plotted copper union. It does not alter parser support or real-board data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, box

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path('assets/starter/fixtures/before/kicad/coupon.kicad_pcb')
G8_METRICS = Path('out/ingestion/gerber_fidelity/real_arc_compatibility_20261024_v1/real_arc_compatibility.json')
CLI = Path('/Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_uid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'pcb-aperture-cam-g9-attribution:{name}'))


def verify_assets():
    manifest = ROOT / 'contracts/asset_manifest.sha256'
    rows = []
    for line in manifest.read_text().splitlines():
        expected, rel = line.split('  ', 1)
        path = ROOT / rel
        actual = sha(path) if path.is_file() else None
        if actual != expected:
            raise SystemExit(f'immutable asset mismatch: {rel}')
        rows.append({'path': rel, 'sha256': actual})
    return rows


def seg_text(name, seg):
    return (f' (segment (start {seg["start"][0]:.6f} {seg["start"][1]:.6f}) '
            f'(end {seg["end"][0]:.6f} {seg["end"][1]:.6f}) '
            f'(width {seg["width"]:.6f}) (layer "F.Cu") (net 1) '
            f'(tstamp {stable_uid(name)}))\n')


def arc_text(name, arc):
    points = ' '.join(f'({key} {arc[key][0]:.6f} {arc[key][1]:.6f})'
                      for key in ('start', 'mid', 'end'))
    return (f' (arc {points} (width {arc["width"]:.6f}) (layer "F.Cu") '
            f'(net 1) (tstamp {stable_uid(name)}))\n')


def make_board(template_text, scenario, with_target, output):
    text = template_text.replace('(gr_rect locked (start 17.0 17.0) (end 26.0 29.0)',
                                 '(gr_rect locked (start 17.0 17.0) (end 62.0 29.0)')
    if text.rstrip()[-1] != ')':
        raise SystemExit('unexpected immutable coupon template shape')
    text = text.rstrip()[:-1]
    for i, seg in enumerate(scenario['context_segments']):
        text += seg_text(f'{scenario["id"]}:context:{i}', seg)
    if with_target:
        text += arc_text(f'{scenario["id"]}:target', scenario['target'])
    text += ')\n'
    output.write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='out/ingestion/gerber_fidelity/g9_arc_attribution_current_v1')
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / 'out'):
        raise SystemExit('output must stay under out/')
    if output.exists():
        raise SystemExit(f'refusing to overwrite existing output: {output}')
    assets = verify_assets()
    metrics_path = ROOT / G8_METRICS
    metrics = json.loads(metrics_path.read_text())
    candidate = min((r for r in metrics['records'] if r['coupon_geometry_class_match']),
                    key=lambda r: r['centerline_length_mm'])
    length = candidate['centerline_length_mm']
    width = candidate['width_mm']
    y = 20.0
    scenarios = [
        {'id': 'isolated', 'x': 30.0, 'context_segments': []},
        {'id': 'partial_occlusion', 'x': 38.0, 'context_segments': []},
        {'id': 'full_occlusion', 'x': 46.0, 'context_segments': []},
        {'id': 'remote_neighbor_same_roi', 'x': 54.0, 'context_segments': []},
    ]
    for s in scenarios:
        x = s['x']
        s['target'] = {'start': [x, y], 'mid': [x + length / 2, y],
                       'end': [x + length, y], 'width': width,
                       'source_example_identity': candidate['source_identity']}
    # A narrower segment covers the middle third of the target centerline.
    s = scenarios[1]
    x = s['x']
    s['context_segments'] = [{'start': [x + length / 3, y],
                              'end': [x + 2 * length / 3, y],
                              'width': width * 0.45}]
    # A wider, co-linear segment fully covers the target's round-stroke footprint.
    s = scenarios[2]
    x = s['x']
    s['context_segments'] = [{'start': [x, y], 'end': [x + length, y],
                              'width': width * 1.8}]
    # A separate feature inside the comparison ROI must cancel from the pair delta.
    s = scenarios[3]
    x = s['x']
    s['context_segments'] = [{'start': [x, y + width * 1.8],
                              'end': [x + length, y + width * 1.8],
                              'width': width * 0.3}]

    template = ROOT / TEMPLATE
    cli_version = subprocess.run([str(CLI), 'version'], text=True,
                                 capture_output=True, check=False)
    if cli_version.returncode or cli_version.stdout.strip() != '10.99.0':
        raise SystemExit('expected pinned KiCad CLI version 10.99.0')
    output.mkdir(parents=True)
    (output / 'sources').mkdir()
    (output / 'gerbers').mkdir()
    rows = []
    for scenario in scenarios:
        pair = {'scenario': scenario['id'], 'target': scenario['target'],
                'target_source_example_identity': candidate['source_identity'],
                'context_segments': scenario['context_segments'], 'exports': {}}
        for presence in ('without_target', 'with_target'):
            stem = f'{scenario["id"]}_{presence}'
            board = output / 'sources' / f'{stem}.kicad_pcb'
            make_board(template.read_text(), scenario, presence == 'with_target', board)
            gerber_dir = output / 'gerbers' / stem
            gerber_dir.mkdir()
            argv = [str(CLI), 'pcb', 'export', 'gerbers', '--layers', 'F.Cu',
                    '--precision', '6', '--no-protel-ext', '--check-zones',
                    '-o', str(gerber_dir.resolve()) + '/', str(board.resolve())]
            result = subprocess.run(argv, text=True, capture_output=True, check=False)
            (output / 'sources' / f'{stem}.stdout.txt').write_text(result.stdout)
            (output / 'sources' / f'{stem}.stderr.txt').write_text(result.stderr)
            if result.returncode:
                raise SystemExit(f'KiCad plot failed: {stem}: {result.stderr}')
            gerbers = sorted(p for p in gerber_dir.iterdir() if p.suffix.lower() == '.gbr')
            if len(gerbers) != 1 or not gerbers[0].name.endswith('-F_Cu.gbr'):
                raise SystemExit(f'unexpected Gerber output for {stem}: {[p.name for p in gerbers]}')
            pair['exports'][presence] = {
                'board_path': str(board.relative_to(ROOT)), 'board_sha256': sha(board),
                'gerber_path': str(gerbers[0].relative_to(ROOT)),
                'gerber_sha256': sha(gerbers[0]), 'argv': argv,
                'tool_sha256': sha(CLI), 'tool_version': cli_version.stdout.strip(),
                'exit_code': result.returncode,
            }
        rows.append(pair)

    spec = {
        'schema': 'g9-arc-incremental-copper-attribution/1',
        'status': 'SYNTHETIC_DIAGNOSTIC_NOT_PARSER_QUALIFICATION',
        'immutable_asset_manifest': {'path': 'contracts/asset_manifest.sha256',
                                     'verified_count': len(assets)},
        'source_template': {'path': TEMPLATE.as_posix(), 'sha256': sha(template)},
        'real_edit_source': {'sha256': metrics['source']['sha256'],
                             'gerber_sha256': metrics['gerber']['sha256']},
        'parameterized_from_real_arc': candidate,
        'target_centerline_length_mm': length,
        'target_width_mm': width,
        'policy': {
            'comparison': 'KiCad plotted treated copper minus KiCad plotted baseline copper is the measured incremental target contribution; compare against expected round-stroke geometry minus baseline context geometry.',
            'fully_occluded': 'Expected and measured target increment are both empty; report zero uniquely observable area and do not infer arc semantics.',
            'board_byte_determinism': 'source copies are generated deterministically; KiCad Gerbers may include timestamps.',
            'scope': 'Four authored micro-coupon contexts only; not real-board acceptance or parser support.'},
        'scenarios': rows,
    }
    (output / 'scenario_spec.json').write_text(json.dumps(spec, indent=2, sort_keys=True) + '\n')
    (output / 'runtime.json').write_text(json.dumps({
        'tool': str(CLI), 'tool_sha256': sha(CLI), 'tool_version': cli_version.stdout.strip(),
        'asset_manifest_verified_count': len(assets), 'parameter_evidence_sha256': sha(metrics_path),
    }, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'output': str(output.relative_to(ROOT)),
                      'scenarios': len(rows), 'source_example': candidate['source_identity'],
                      'width_mm': width, 'length_mm': length,
                      'asset_manifest_verified': len(assets)}, indent=2))


if __name__ == '__main__':
    main()
