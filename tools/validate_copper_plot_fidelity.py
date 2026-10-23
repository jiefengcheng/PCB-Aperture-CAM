#!/usr/bin/env python3
"""Validate source-derived F.Cu geometry against fresh KiCad Gerber plots.

This is an exploratory geometry-fidelity measurement, not board acceptance.
Outputs are written only under out/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from shapely import affinity
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.copper_fidelity import (board_copper_inventory, comparison_metrics,
                                 local_scope)
from src.gerber_image import read_image
from src.native_inventory import inventory


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_package(package: Path) -> dict:
    manifest = package / 'SHA256SUMS'
    rows = []
    errors = []
    for line in manifest.read_text().splitlines():
        digest, relative = line.split('  ', 1)
        path = package / relative
        actual = sha(path) if path.is_file() else None
        rows.append({'path': relative, 'expected_sha256': digest, 'actual_sha256': actual,
                     'status': 'PASS' if actual == digest else 'FAIL'})
        if actual != digest:
            errors.append(relative)
    if errors:
        raise SystemExit(f'intake package hash mismatch: {errors}')
    return {'manifest': str(manifest.relative_to(ROOT)), 'entry_count': len(rows),
            'verified_count': len(rows), 'status': 'PASS', 'entries': rows}


def full_board_metrics(expected, plotted):
    intersection = expected.intersection(plotted)
    difference = expected.symmetric_difference(plotted)
    return {
        'status': 'MEASURED',
        'native_supported_union_area_mm2': expected.area,
        'kiCad_plot_union_area_mm2': plotted.area,
        'intersection_area_mm2': intersection.area,
        'native_covered_fraction': intersection.area / expected.area if expected.area else None,
        'plot_covered_fraction': intersection.area / plotted.area if plotted.area else None,
        'signed_area_delta_mm2': plotted.area - expected.area,
        'symmetric_difference_area_mm2': difference.area,
        'symmetric_difference_fraction_of_plot': difference.area / plotted.area if plotted.area else None,
        'scope': 'complete F.Cu plot compared with source records whose native_inventory geometry is available; no board-wide ORG-to-EDIT change conclusion',
    }


def load_board(source: Path):
    raw = source.read_bytes()
    result = inventory(raw)
    supported, unsupported, fallbacks, unresolved = board_copper_inventory(raw, result)
    union = unary_union([shape for _, shape in supported])
    return raw, result, supported, unsupported, fallbacks, unresolved, union


def run(args):
    package = (ROOT / args.package).resolve()
    export_run = (ROOT / args.export_run).resolve()
    correspondence = (ROOT / args.correspondence).resolve()
    output = (ROOT / args.output).resolve()
    if not package.is_relative_to(ROOT) or not export_run.is_relative_to(ROOT / 'out'):
        raise SystemExit('package and export run must stay inside this checkout; exports must be under out/')
    if not correspondence.is_relative_to(ROOT / 'out') or not output.is_relative_to(ROOT / 'out'):
        raise SystemExit('correspondence and report paths must stay under out/')
    if output.exists():
        raise SystemExit(f'refusing to overwrite existing output: {output}')
    package_hashes = verify_package(package)
    intake = json.loads((package / 'metadata/manifest.json').read_text())
    graph = json.loads(correspondence.read_text())
    registration = graph['registration']
    source_specs = {
        'ORG': ('raw/ORG/top.kicad_pcb', 'ORG/gerbers/top-F_Cu.gbr'),
        'EDIT': ('raw/EDIT/top_layer.kicad_pcb', 'EDIT/gerbers/top_layer-F_Cu.gbr'),
    }
    groups = graph['groups']
    report = {
        'schema': 'pcb-copper-plot-fidelity/1',
        'status': 'MEASURED_NOT_QUALIFIED',
        'dataset_id': graph['dataset_id'],
        'input_package': str(package.relative_to(ROOT)),
        'input_manifest_verification': package_hashes,
        'registration': {
            'source_layer': registration.get('source_layer'),
            'translation_mm': registration.get('translation_mm_after_minus_before'),
            'rotation_radians': registration.get('fitted_after_to_before', {}).get('rotation_radians'),
            'scale': registration.get('transform_model'),
            'inlier_count': registration.get('inlier_count'),
            'maximum_residual_mm': registration.get('max_inlier_residual_mm'),
            'qualification': 'candidate frame only; global uniqueness not established',
        },
        'measurement_scope': {
            'full_board': 'source-native F.Cu geometry union versus each board own fresh F.Cu plot; fidelity only',
            'local_regions': '12 review-group centers; each is a 3.6 mm square centered in the candidate common board frame',
            'region_radius_mm': args.region_radius_mm,
            'metrics_are_not_summed': True,
            'local_source_closure': 'all supported F.Cu source geometries intersecting each region are enumerated by source identity; unsupported F.Cu records and explicit diagnostic fallbacks are separate',
            'overlapping_region_union_attribution': 'regions may overlap; each is an independent diagnostic and results are not added together',
        },
        'cases': {},
        'region_overlap': [],
        'limitations': [
            'No predeclared engineering tolerance is applied; these are measurements, not PASS/FAIL geometry acceptance.',
            'The 84 EDIT degenerate arcs remain UNSUPPORTED by native_inventory. Collinear-line buffering is an explicitly separate diagnostic hypothesis, not a source parser promotion.',
            'The Gerber geometry decoder and source reconstruction both use Shapely/GEOS; KiCad plotting is the independent native export path, but this is not a separately implemented geometry kernel.',
            'Global registration uniqueness, candidate correspondence accuracy, electrical connectivity, design intent, board-wide enhancement attribution, and engineering/manufacturing acceptance are not established.',
            'The intake raw-tree hash is recorded by its manifest; this run verifies each listed input file but does not reconstruct the profile-generation raw-tree hashing algorithm.',
        ],
    }
    for side, (source_rel, gerber_rel) in source_specs.items():
        native_path = package / source_rel
        gerber_path = export_run / gerber_rel
        receipt_path = export_run / 'run_receipt.json'
        export_receipt = json.loads(receipt_path.read_text())
        case_receipt = export_receipt['cases'][side]
        native_hash = sha(native_path)
        gerber_hash = sha(gerber_path)
        if native_hash != graph['source_files']['before' if side == 'ORG' else 'after']['sha256']:
            raise SystemExit(f'{side} native file hash differs from correspondence binding')
        if native_hash != case_receipt['source_sha256'] or gerber_hash != case_receipt['outputs'][gerber_path.name]:
            raise SystemExit(f'{side} export receipt does not bind current source and Gerber bytes')
        raw, inv, supported, unsupported, fallbacks, unresolved, native_union = load_board(native_path)
        parsed = read_image(gerber_path)
        # KiCad's X2 SameCoordinates=Original output is Y-up; native coordinates use Y-down.
        plotted_union = affinity.scale(parsed['geometry'], xfact=1, yfact=-1, origin=(0, 0))
        fallback_union = unary_union([native_union, *[entry['geometry'] for _, entry in fallbacks]])
        case = {
            'source': {'path': source_rel, 'sha256': native_hash, 'size_bytes': len(raw)},
            'gerber': {'path': str(gerber_path.relative_to(ROOT)), 'sha256': gerber_hash,
                       'size_bytes': gerber_path.stat().st_size,
                       'file_function': parsed['file_attrs'].get('.FileFunction'),
                       'file_polarity': parsed['file_attrs'].get('.FilePolarity'),
                       'same_coordinates': parsed['file_attrs'].get('.SameCoordinates'),
                       'gerber_object_count': len(parsed['objects']),
                       'gerber_object_types': parsed['object_types'],
                       'unit_mm_absolute_profile': 'PASS: read_image strict profile'},
            'native_inventory': {
                'version': inv['version'],
                'source_object_count': inv['source_objects'],
                'fcu_source_record_count': sum('F.Cu' in row.get('layers', []) for row in inv['objects']),
                'fcu_supported_geometry_count': len(supported),
                'fcu_unsupported_geometry_count': len(unsupported),
                'unsupported_reasons': {reason: sum(row.get('unsupported_reason') == reason for row in unsupported)
                                        for reason in sorted({row.get('unsupported_reason') for row in unsupported})},
                'unsupported_identities': sorted(row['id'] for row in unsupported),
                'explicit_collinear_fallback_count': len(fallbacks),
                'fallback_identities': sorted(entry['source_identity'] for _, entry in fallbacks),
                'unresolved_after_diagnostic_fallback_count': len(unresolved),
                'geometry_error_mm': inv['geometry_error_mm'],
                'per_curve_approximation_error_mm': inv['per_curve_approximation_error_mm'],
            },
            'whole_board_fidelity_measurement': full_board_metrics(native_union, plotted_union),
            'whole_board_fallback_diagnostic': full_board_metrics(fallback_union, plotted_union),
            'local_regions': [],
        }
        for group in groups:
            scope = local_scope(supported, unsupported, fallbacks, unresolved,
                                group['center_mm'], args.region_radius_mm)
            plotted_region = plotted_union.intersection(scope['region'])
            strict_metrics = comparison_metrics(scope['expected_supported_geometry'], plotted_region)
            fallback_metrics = comparison_metrics(scope['expected_with_fallback_geometry'], plotted_region)
            case['local_regions'].append({
                'group_id': group['group_id'],
                'group_center_mm': group['center_mm'],
                'region_bounds_mm': scope['region_bounds_mm'],
                'region_shape': 'square',
                'source_scope_counts': {
                    'supported_fcu_records_intersecting_roi': scope['supported_source_count'],
                    'unsupported_fcu_records_in_roi': scope['unsupported_source_count'],
                    'unresolved_unsupported_fcu_records_in_roi': scope['unresolved_unsupported_source_count'],
                },
                'supported_source_identities': scope['supported_source_identities'],
                'unsupported_source_identities': scope['unsupported_source_identities'],
                'unresolved_unsupported_source_identities': scope['unresolved_unsupported_source_identities'],
                'fallback_diagnostics': scope['fallback_diagnostics'],
                'strict_native_inventory_vs_kicad_plot': strict_metrics,
                'diagnostic_fallback_vs_kicad_plot': fallback_metrics,
            })
        report['cases'][side] = case
    for i, left in enumerate(groups):
        for right in groups[i + 1:]:
            ax, ay = left['center_mm']; bx, by = right['center_mm']
            overlap_x = max(0.0, min(ax + args.region_radius_mm, bx + args.region_radius_mm)
                            - max(ax - args.region_radius_mm, bx - args.region_radius_mm))
            overlap_y = max(0.0, min(ay + args.region_radius_mm, by + args.region_radius_mm)
                            - max(ay - args.region_radius_mm, by - args.region_radius_mm))
            if overlap_x * overlap_y:
                report['region_overlap'].append({'left': left['group_id'], 'right': right['group_id'],
                                                 'overlap_area_mm2': overlap_x * overlap_y})
    output.mkdir(parents=True)
    json_path = output / 'fidelity_report.json'
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    summary = [
        '# ORG/EDIT F.Cu source-to-KiCad-plot fidelity measurements', '',
        '**Status: MEASURED_NOT_QUALIFIED.** This verifies local plot fidelity evidence only; it is not an area-growth, connectivity, design-intent, or manufacturing result.', '',
        f"Intake package manifest: {package_hashes['verified_count']} / {package_hashes['entry_count']} listed files verified. Source board hashes: ORG `{report['cases']['ORG']['source']['sha256']}`, EDIT `{report['cases']['EDIT']['source']['sha256']}`.", '',
        '| Board | Supported F.Cu source geometries | Unsupported F.Cu records | Native union mm² | KiCad plot mm² | Symmetric difference mm² | Relative difference |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for side in ('ORG', 'EDIT'):
        c = report['cases'][side]
        m = c['whole_board_fidelity_measurement']
        summary.append(f"| {side} | {c['native_inventory']['fcu_supported_geometry_count']} | {c['native_inventory']['fcu_unsupported_geometry_count']} | {m['native_supported_union_area_mm2']:.9f} | {m['kiCad_plot_union_area_mm2']:.9f} | {m['symmetric_difference_area_mm2']:.9f} | {m['symmetric_difference_fraction_of_plot']:.8g} |")
    summary += ['', '## Local review-group neighborhoods', '',
                'Each row compares all source-supported F.Cu objects intersecting the fixed 3.6 mm square with the corresponding clipped KiCad Gerber image. The strict inventory metric excludes records marked unsupported. A second, diagnostic-only metric adds collinear degenerate arcs as round strokes; their source IDs and midline deviations remain listed in the JSON. Area/boundary numbers are per region and must not be summed across overlapping ROIs.', '',
                '| Board | Region | Supported objects | Unsupported records | Strict symmetric diff mm² | Strict boundary Hausdorff mm | Diagnostic symmetric diff mm² | Diagnostic boundary Hausdorff mm |',
                '|---|---|---:|---:|---:|---:|---:|---:|']
    for side in ('ORG', 'EDIT'):
        for row in report['cases'][side]['local_regions']:
            a = row['strict_native_inventory_vs_kicad_plot']; b = row['diagnostic_fallback_vs_kicad_plot']
            summary.append(f"| {side} | {row['group_id']} | {row['source_scope_counts']['supported_fcu_records_intersecting_roi']} | {row['source_scope_counts']['unsupported_fcu_records_in_roi']} | {a['symmetric_difference_area_mm2']:.9f} | {a['boundary_hausdorff_distance_mm']:.9f} | {b['symmetric_difference_area_mm2']:.9f} | {b['boundary_hausdorff_distance_mm']:.9f} |")
    summary += ['', '## Interpretation limits', '',
                '- Full-board rows compare each board with its own plot. They are not ORG-versus-EDIT growth metrics.',
                '- Local regions are source-closed for every geometry-available F.Cu identity intersecting the declared region; unsupported identities and diagnostic approximations are explicit.',
                '- The 84 EDIT degenerate arcs remain unsupported by the main inventory. Their exact collinearity and agreement under a round-stroke diagnostic are evidence for review, not parser promotion.',
                '- No numerical engineering acceptance tolerance was predeclared, so no fidelity PASS/FAIL is issued.',
                '- KiCad provides an independent plotting path, but both geometry reconstructions use the same GEOS/Shapely kernel; no second geometry engine is claimed.',
                '- Registration alternatives, correspondence accuracy, electrical connectivity, global copper-growth attribution, and engineering/manufacturing acceptance remain unestablished.',
                '', f"Detailed identities, exact hashes and all per-region metrics: `{json_path.relative_to(ROOT)}`."]
    (output / 'fidelity_report.md').write_text('\n'.join(summary) + '\n')
    (output / 'SHA256SUMS').write_text(''.join(
        f'{sha(path)}  {path.name}\n' for path in sorted(output.iterdir()) if path.is_file() and path.name != 'SHA256SUMS'))
    print(json.dumps({'status': report['status'], 'output': str(output.relative_to(ROOT)),
                      'intake_hash_entries_verified': package_hashes['verified_count'],
                      'groups': len(groups),
                      'ORG': report['cases']['ORG']['whole_board_fidelity_measurement'],
                      'EDIT': report['cases']['EDIT']['whole_board_fidelity_measurement']}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', default='dataset/szu-comm_3020301113B_intake_ready_20261021_v2')
    parser.add_argument('--correspondence', default='out/ingestion/trace_polygon_correspondence_20261024/groups.json')
    parser.add_argument('--export-run', default='out/ingestion/gerber_fidelity/run-20261022T182946Z')
    parser.add_argument('--output', default='out/ingestion/gerber_fidelity/qualification_20261024')
    parser.add_argument('--region-radius-mm', type=float, default=1.8)
    args = parser.parse_args()
    run(args)


if __name__ == '__main__':
    main()
