#!/usr/bin/env python3
"""Measure paired KiCad plot deltas against authored target-arc increments."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gerber_image import read_image
from tools.qualify_collinear_arc_coupon import polygon_topology


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stroke(start, end, width):
    return LineString([tuple(start), tuple(end)]).buffer(float(width) / 2,
        quad_segs=32, cap_style='round', join_style='round')


def incremental_geometry(baseline, with_target):
    """Return only copper added by a target to the unchanged context union."""
    return with_target.difference(baseline)


def plot_geometry(path: Path):
    return affinity.scale(read_image(path)['geometry'], xfact=1, yfact=-1,
                          origin=(0, 0))


def evaluate_scenario(root: Path, scenario: dict):
    exports = scenario['exports']
    baseline_path = (ROOT / exports['without_target']['gerber_path']).resolve()
    treated_path = (ROOT / exports['with_target']['gerber_path']).resolve()
    for key, path in (('without_target', baseline_path), ('with_target', treated_path)):
        row = exports[key]
        if not path.is_file() or sha(path) != row['gerber_sha256']:
            raise SystemExit(f'Gerber hash mismatch: {path}')
    baseline_plot = plot_geometry(baseline_path)
    treated_plot = plot_geometry(treated_path)
    measured_delta = incremental_geometry(baseline_plot, treated_plot)

    context = [stroke(row['start'], row['end'], row['width'])
               for row in scenario['context_segments']]
    baseline_expected = context[0] if len(context) == 1 else None
    if len(context) > 1:
        from shapely.ops import unary_union
        baseline_expected = unary_union(context)
    if baseline_expected is None:
        from shapely.geometry import GeometryCollection
        baseline_expected = GeometryCollection()
    target = scenario['target']
    target_expected = stroke(target['start'], target['end'], target['width'])
    expected_delta = incremental_geometry(baseline_expected,
                                          baseline_expected.union(target_expected))
    symmetric = expected_delta.symmetric_difference(measured_delta).area
    hausdorff = (expected_delta.boundary.hausdorff_distance(measured_delta.boundary)
                 if not expected_delta.is_empty and not measured_delta.is_empty
                 else (0.0 if expected_delta.is_empty and measured_delta.is_empty else None))
    intersection = expected_delta.intersection(measured_delta).area
    expected_area = expected_delta.area
    relative_area = symmetric / expected_area if expected_area else (0.0 if measured_delta.is_empty else None)
    g8_area_limit = 0.0001
    g8_relative_limit = 0.01
    g8_boundary_limit = 0.00002
    area_ok = symmetric <= g8_area_limit
    relative_ok = relative_area is not None and relative_area <= g8_relative_limit
    boundary_ok = hausdorff is not None and hausdorff <= g8_boundary_limit
    topology_equal = polygon_topology(expected_delta) == polygon_topology(measured_delta)
    return {
        'scenario_id': scenario['scenario'],
        'target_source_example_identity': scenario['target_source_example_identity'],
        'target_expected_area_mm2': expected_delta.area,
        'target_plot_increment_area_mm2': measured_delta.area,
        'symmetric_difference_area_mm2': symmetric,
        'symmetric_difference_fraction_of_expected': relative_area,
        'boundary_hausdorff_distance_mm': hausdorff,
        'g8_diagnostic_reference_checks_only': {
            'absolute_area_limit_mm2': g8_area_limit,
            'relative_area_limit': g8_relative_limit,
            'boundary_hausdorff_limit_mm': g8_boundary_limit,
            'absolute_area_within_reference': area_ok,
            'relative_area_within_reference': relative_ok,
            'boundary_within_reference': boundary_ok,
            'topology_equal': topology_equal,
            'within_reference': area_ok and relative_ok and boundary_ok and topology_equal,
            'meaning': 'Reference comparison only; not a parser, board, or manufacturing acceptance limit.'
        },
        'expected_covered_fraction': (intersection / expected_delta.area
                                      if expected_delta.area else None),
        'measured_delta_topology': polygon_topology(measured_delta),
        'expected_delta_topology': polygon_topology(expected_delta),
        'observable_increment': not expected_delta.is_empty,
        'status': ('PLOT_DELTA_EMPTY_AS_EXPECTED' if expected_delta.is_empty and measured_delta.is_empty
                   else 'PLOT_DELTA_PRESENT_AS_EXPECTED' if not expected_delta.is_empty and not measured_delta.is_empty
                   else 'PLOT_DELTA_CONTRADICTS_AUTHORED_EXPECTATION'),
        'limitation': ('An empty incremental copper delta cannot establish the target primitive semantics; the neighbor alone fully covers its footprint.'
                       if expected_delta.is_empty else
                       'Controlled synthetic contrast only; it does not establish real-board source-to-plot attribution.'),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='out/ingestion/gerber_fidelity/g9_arc_attribution_current_v1')
    parser.add_argument('--output', default='out/ingestion/gerber_fidelity/g9_arc_attribution_current_v1/results_v2')
    args = parser.parse_args()
    input_root = (ROOT / args.input).resolve()
    output = (ROOT / args.output).resolve()
    if not input_root.is_relative_to(ROOT / 'out') or not output.is_relative_to(ROOT / 'out'):
        raise SystemExit('inputs and output must remain under out/')
    if output.exists():
        raise SystemExit(f'refusing to overwrite existing output: {output}')
    spec_path = input_root / 'scenario_spec.json'
    spec = json.loads(spec_path.read_text())
    rows = [evaluate_scenario(input_root, item) for item in spec['scenarios']]
    report = {
        'schema': 'g9-arc-incremental-copper-attribution-results/1',
        'status': 'BOUNDED_SYNTHETIC_DIAGNOSTIC',
        'scenario_spec_sha256': sha(spec_path),
        'source_template_sha256': spec['source_template']['sha256'],
        'real_edit_source_sha256': spec['real_edit_source']['sha256'],
        'accuracy_policy': 'No new acceptance limits are introduced. Results report paired plot increments and authored-geometry residuals; G8 coupon thresholds remain reference-only.',
        'results': rows,
        'counts': {status: sum(row['status'] == status for row in rows)
                   for status in sorted({row['status'] for row in rows})},
        'limitations': [
            'Only four synthetic cases at one real EDIT arc parameter point were measured.',
            'Expected swept shapes are authored round strokes for these diagnostic cases; this does not prove universal KiCad arc semantics.',
            'The source parser remains unchanged and exact-collinear arcs remain unsupported.',
            'This does not establish any ORG-to-EDIT enhancement, real-board attribution, connectivity, or manufacturing acceptance.',
        ],
    }
    output.mkdir(parents=True)
    result_path = output / 'attribution_results.json'
    result_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    table = ['| Scenario | Expected unique area (mm²) | Plotted increment (mm²) | Symmetric difference (mm²) | Relative difference | Hausdorff (mm) | G8 reference only | Result |',
             '|---|---:|---:|---:|---:|---:|---|---|']
    for row in rows:
        h = 'n/a' if row['boundary_hausdorff_distance_mm'] is None else f"{row['boundary_hausdorff_distance_mm']:.9g}"
        rel = 'n/a' if row['symmetric_difference_fraction_of_expected'] is None else f"{row['symmetric_difference_fraction_of_expected']:.6g}"
        reference = row['g8_diagnostic_reference_checks_only']['within_reference']
        table.append(f"| {row['scenario_id']} | {row['target_expected_area_mm2']:.9g} | {row['target_plot_increment_area_mm2']:.9g} | {row['symmetric_difference_area_mm2']:.9g} | {rel} | {h} | {'within reference' if reference else 'outside reference'} | {row['status']} |")
    (output / 'README.md').write_text('\n'.join([
        '# G9 paired-plot arc attribution diagnostic', '',
        '**Status: BOUNDED_SYNTHETIC_DIAGNOSTIC.** Each scenario is plotted twice with the same KiCad build and context: once without the target arc and once with it. The Gerber geometry difference is therefore a controlled plotted increment for that authored coupon pair.', '',
        f"Real EDIT parameter example: `{spec['parameterized_from_real_arc']['source_identity']}`, centerline length {spec['target_centerline_length_mm']:.9g} mm, width {spec['target_width_mm']:.9g} mm.", '',
        *table, '',
        'The fully occluded case is expected to produce no unique plotted increment; that outcome means the plot cannot reveal the hidden target primitive. This is an attribution limit, not proof of semantic equivalence. The synthetic results do not alter parser support or qualify any real-board correspondence.', '',
        f"Machine results: `{result_path.relative_to(ROOT)}`.", ''
    ]))
    lines=[]
    for path in sorted(output.rglob('*')):
        if path.is_file() and path.name != 'SHA256SUMS':
            lines.append(f'{sha(path)}  {path.relative_to(output).as_posix()}')
    (output / 'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status': report['status'], 'results': rows,
                      'output': str(output.relative_to(ROOT))}, indent=2))


if __name__ == '__main__':
    main()
