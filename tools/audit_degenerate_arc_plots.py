#!/usr/bin/env python3
"""Measure EDIT collinear-arc diagnostic geometry against the fresh F.Cu plot.

This is a source-bound diagnostic report, not parser qualification or board
acceptance. It writes only under out/ and does not alter source or parser data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from shapely import affinity
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.copper_fidelity import (board_copper_inventory, comparison_metrics,
                                 diagnostic_arc_roi, local_scope)
from src.gerber_image import read_image
from src.native_inventory import inventory
from tools.validate_copper_plot_fidelity import sha, verify_package


def run(args):
    package = (ROOT / args.package).resolve()
    export_run = (ROOT / args.export_run).resolve()
    output = (ROOT / args.output).resolve()
    if not package.is_relative_to(ROOT) or not export_run.is_relative_to(ROOT / 'out'):
        raise SystemExit('package must stay inside checkout and exports under out/')
    if not output.is_relative_to(ROOT / 'out'):
        raise SystemExit('output must stay under out/')
    if output.exists():
        raise SystemExit(f'refusing to overwrite existing output: {output}')

    package_hashes = verify_package(package)
    source_rel = 'raw/EDIT/top_layer.kicad_pcb'
    gerber_rel = 'EDIT/gerbers/top_layer-F_Cu.gbr'
    source = package / source_rel
    gerber = export_run / gerber_rel
    receipt = json.loads((export_run / 'run_receipt.json').read_text())['cases']['EDIT']
    source_hash, gerber_hash = sha(source), sha(gerber)
    if source_hash != receipt['source_sha256']:
        raise SystemExit('source hash does not match native export receipt')
    if receipt['outputs'].get(gerber.name) != gerber_hash:
        raise SystemExit('Gerber hash does not match native export receipt')

    raw = source.read_bytes()
    inv = inventory(raw)
    supported, unsupported, fallbacks, unresolved = board_copper_inventory(raw, inv)
    if len(unsupported) != len(fallbacks) or unresolved:
        raise SystemExit('not every unsupported EDIT F.Cu record has an exact-collinear diagnostic')
    plotted = affinity.scale(read_image(gerber)['geometry'], xfact=1, yfact=-1,
                             origin=(0, 0))

    rows = []
    rois = []
    fallback_by_id = {item['id']: fallback for item, fallback in fallbacks}
    for item, fallback in fallbacks:
        roi = diagnostic_arc_roi(fallback, args.context_widths,
                                 args.minimum_context_mm)
        center = (roi.centroid.x, roi.centroid.y)
        radius = (roi.bounds[2] - roi.bounds[0]) / 2
        scope = local_scope(supported, unsupported, fallbacks, unresolved,
                            center, radius)
        plotted_region = plotted.intersection(scope['region'])
        strict = scope['expected_supported_geometry']
        diagnostic = scope['expected_with_fallback_geometry']
        target_only = unary_union([
            strict,
            fallback['geometry'].intersection(scope['region']),
        ])
        strict_metrics = comparison_metrics(strict, plotted_region)
        diagnostic_metrics = comparison_metrics(diagnostic, plotted_region)
        target_metrics = comparison_metrics(target_only, plotted_region)
        local_fallback_ids = sorted(
            row['source_identity'] for row in scope['fallback_diagnostics'])
        rows.append({
            'source_identity': item['id'],
            'roi_bounds_mm': scope['region_bounds_mm'],
            'roi_rule': 'stroke-bounds square, half-size = max stroke half-extent + max(2 * width, 0.05 mm)',
            'width_mm': fallback['width_mm'],
            'centerline_length_mm': fallback['centerline_length_mm'],
            'midpoint_deviation_mm': fallback['midpoint_deviation_mm'],
            'supported_source_count': scope['supported_source_count'],
            'unsupported_source_count': scope['unsupported_source_count'],
            'unresolved_unsupported_source_count': scope['unresolved_unsupported_source_count'],
            'fallback_identities_in_roi': local_fallback_ids,
            'target_fallback_identity_in_roi': item['id'] in local_fallback_ids,
            'target_only_added_area_mm2': target_only.difference(strict).area,
            'all_fallbacks_added_area_mm2': diagnostic.difference(strict).area,
            'strict_native_vs_plot': strict_metrics,
            'target_arc_only_diagnostic_vs_plot': target_metrics,
            'all_local_fallbacks_diagnostic_vs_plot': diagnostic_metrics,
        })
        rois.append(scope['region'])

    overlaps = []
    for i, left in enumerate(rois):
        for j in range(i + 1, len(rois)):
            intersection_area = left.intersection(rois[j]).area
            if intersection_area > 0:
                overlaps.append({'left_row': i, 'right_row': j,
                                 'overlap_area_mm2': intersection_area})

    def count_improved(before_key, after_key, metric):
        return sum(row[after_key][metric] < row[before_key][metric]
                   for row in rows)

    summary = {
        'status': 'MEASURED_NOT_QUALIFIED',
        'interpretation': 'local comparison evidence only; no numerical acceptance tolerance applied',
        'source': {'path': source_rel, 'sha256': source_hash, 'size_bytes': len(raw)},
        'gerber': {'path': str(gerber.relative_to(ROOT)), 'sha256': gerber_hash},
        'intake_manifest': {'entry_count': package_hashes['entry_count'],
                            'verified_count': package_hashes['verified_count'],
                            'status': package_hashes['status']},
        'native_inventory': {'version': inv['version'],
                             'unsupported_fcu_count': len(unsupported),
                             'diagnostic_fallback_count': len(fallbacks),
                             'unresolved_count': len(unresolved),
                             'parser_classification_changed': False},
        'protocol': {
            'context_widths': args.context_widths,
            'minimum_context_mm': args.minimum_context_mm,
            'roi': 'axis-aligned square around each diagnostic stroke; all source-supported F.Cu shapes intersecting ROI included; same ROI clips the KiCad Gerber union',
            'overlapping_regions_are_nonadditive': True,
            'shared_geometry_kernel': 'source reconstruction and Gerber composition both use Shapely/GEOS',
        },
        'counts': {'arc_windows': len(rows), 'roi_overlap_pairs': len(overlaps),
                   'area_difference_reduced_by_all_local_fallbacks': count_improved('strict_native_vs_plot', 'all_local_fallbacks_diagnostic_vs_plot', 'symmetric_difference_area_mm2'),
                   'boundary_distance_reduced_by_all_local_fallbacks': count_improved('strict_native_vs_plot', 'all_local_fallbacks_diagnostic_vs_plot', 'boundary_hausdorff_distance_mm')},
        'roi_overlaps': overlaps,
        'arcs': rows,
        'limitations': [
            'This is not a prequalified tolerance-based pass/fail result.',
            'The local windows overlap and their areas must not be summed.',
            'A fallback may add no unique area when neighboring supported geometry already covers it.',
            'Agreement with the KiCad plot is diagnostic evidence, not proof of source-language semantics or parser completeness.',
            'ORG-to-EDIT attribution, correspondence accuracy, connectivity, and engineering/manufacturing acceptance remain outside scope.',
        ],
    }
    output.mkdir(parents=True)
    json_path = output / 'degenerate_arc_plot_evidence.json'
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    strict_areas = [row['strict_native_vs_plot']['symmetric_difference_area_mm2']
                    for row in rows]
    diagnostic_areas = [row['all_local_fallbacks_diagnostic_vs_plot']['symmetric_difference_area_mm2']
                        for row in rows]
    strict_distances = [row['strict_native_vs_plot']['boundary_hausdorff_distance_mm']
                        for row in rows]
    diagnostic_distances = [row['all_local_fallbacks_diagnostic_vs_plot']['boundary_hausdorff_distance_mm']
                            for row in rows]
    md = [
        '# EDIT degenerate-arc local plot evidence', '',
        '**Status: MEASURED_NOT_QUALIFIED.** Each of the 84 diagnostic arc identities was evaluated in a context ROI against EDIT’s own KiCad F.Cu plot. No tolerance-based acceptance is claimed.', '',
        f"Source SHA-256: `{source_hash}`; Gerber SHA-256: `{gerber_hash}`. Intake manifest entries verified: {package_hashes['verified_count']}/{package_hashes['entry_count']}.", '',
        f"The ROI rule is fixed at stroke bounds expanded to a square whose half-size adds `max({args.context_widths:g} × width, {args.minimum_context_mm:g} mm)`. Supported native F.Cu geometry and the plot are clipped to the same ROI. {len(overlaps)} ROI pairs overlap; measurements are per-window and non-additive.", '',
        f"Across {len(rows)} windows, adding all local collinear-arc diagnostics reduced symmetric-difference area in {summary['counts']['area_difference_reduced_by_all_local_fallbacks']} windows and boundary Hausdorff distance in {summary['counts']['boundary_distance_reduced_by_all_local_fallbacks']} windows. Area-difference ranges: strict {min(strict_areas):.9g}–{max(strict_areas):.9g} mm²; diagnostic {min(diagnostic_areas):.9g}–{max(diagnostic_areas):.9g} mm². Boundary-distance ranges: strict {min(strict_distances):.9g}–{max(strict_distances):.9g} mm; diagnostic {min(diagnostic_distances):.9g}–{max(diagnostic_distances):.9g} mm.", '',
        'All 84 records remain unsupported by the base inventory. Local plot agreement supports the diagnostic hypothesis but does not qualify native arc semantics or parser behavior. Some arcs may be covered by neighboring copper; per-arc unique added area is retained in the JSON. Full identities, bounds, counts, metrics, and overlap pairs are in `degenerate_arc_plot_evidence.json`.', '',
        'The geometries share Shapely/GEOS. No ORG-to-EDIT growth, correspondence, connectivity, or engineering/manufacturing conclusion follows.', '',
    ]
    (output / 'README.md').write_text('\n'.join(md))
    files = sorted(p for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS')
    (output / 'SHA256SUMS').write_text(''.join(
        f'{sha(path)}  {path.name}\n' for path in files))
    print(json.dumps({'status': summary['status'], 'output': str(output.relative_to(ROOT)),
                      'arc_windows': len(rows), 'overlap_pairs': len(overlaps),
                      'area_improved': summary['counts']['area_difference_reduced_by_all_local_fallbacks'],
                      'boundary_improved': summary['counts']['boundary_distance_reduced_by_all_local_fallbacks']}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', default='dataset/szu-comm_3020301113B_intake_ready_20261021_v2')
    parser.add_argument('--export-run', default='out/ingestion/gerber_fidelity/run-20261022T182946Z')
    parser.add_argument('--output', default='out/ingestion/gerber_fidelity/degenerate_arcs_20261024_v1')
    parser.add_argument('--context-widths', type=float, default=2.0)
    parser.add_argument('--minimum-context-mm', type=float, default=0.05)
    run(parser.parse_args())


if __name__ == '__main__':
    main()
