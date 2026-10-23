#!/usr/bin/env python3
"""Triage the 84 EDIT degenerate arcs against the coupon and local plot data."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.copper_fidelity import board_copper_inventory
from src.native_inventory import inventory
from src.native_reference import one
from tools.validate_copper_plot_fidelity import sha, verify_package
import sexpdata


def arc_values(source: bytes, item: dict):
    start, end = item['source_span']
    node = sexpdata.loads(source[start:end].decode('utf-8'))
    a, m, b = (tuple(map(float, one(node, key))) for key in ('start', 'mid', 'end'))
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    deviation = abs(dx * (a[1] - m[1]) - (a[0] - m[0]) * dy) / length if length else None
    return {'start_mm': a, 'mid_mm': m, 'end_mm': b,
            'width_mm': float(one(node, 'width')[0]),
            'layer': str(one(node, 'layer')[0]),
            'centerline_length_mm': length,
            'midpoint_deviation_mm': deviation}


def run(args):
    package = (ROOT / args.package).resolve()
    source_path = package / 'raw/EDIT/top_layer.kicad_pcb'
    gerber_path = ROOT / args.export_run / 'EDIT/gerbers/top_layer-F_Cu.gbr'
    export_receipt_path = ROOT / args.export_run / 'run_receipt.json'
    per_arc_path = ROOT / args.per_arc_evidence
    coupon_results_path = ROOT / args.coupon_results
    coupon_spec_path = ROOT / args.coupon_spec
    output = ROOT / args.output
    for p in (package, source_path, gerber_path, export_receipt_path,
              per_arc_path, coupon_results_path, coupon_spec_path):
        if not p.resolve().is_relative_to(ROOT):
            raise SystemExit(f'input path outside checkout: {p}')
    if not output.resolve().is_relative_to(ROOT / 'out'):
        raise SystemExit('output must stay under out/')
    if output.exists():
        raise SystemExit(f'refusing to overwrite existing output: {output}')

    manifest = verify_package(package)
    source_hash, gerber_hash = sha(source_path), sha(gerber_path)
    export_receipt = json.loads(export_receipt_path.read_text())['cases']['EDIT']
    if source_hash != export_receipt['source_sha256'] or gerber_hash != export_receipt['outputs'].get(gerber_path.name):
        raise SystemExit('real EDIT source or Gerber differs from its export receipt')
    per_arc = json.loads(per_arc_path.read_text())
    if source_hash != per_arc['source']['sha256'] or gerber_hash != per_arc['gerber']['sha256']:
        raise SystemExit('per-arc evidence is not bound to current EDIT source/Gerber')
    coupon = json.loads(coupon_results_path.read_text())
    spec = json.loads(coupon_spec_path.read_text())
    policy = coupon['accuracy_policy']['content']['acceptance_by_feature']
    if spec['parameter_source_sha256'] != source_hash:
        raise SystemExit('scale coupon is not parameterized from this EDIT source')

    raw = source_path.read_bytes()
    inv = inventory(raw)
    supported, unsupported, fallbacks, unresolved = board_copper_inventory(raw, inv)
    if len(unsupported) != 84 or len(fallbacks) != 84 or unresolved:
        raise SystemExit('expected 84 explicitly diagnostic EDIT arcs; inventory changed')
    fallback_rows = {item['id']: (item, fb) for item, fb in fallbacks}
    local_rows = {row['source_identity']: row for row in per_arc['arcs']}
    if set(fallback_rows) != set(local_rows):
        raise SystemExit('per-arc evidence identities do not exactly match current inventory')

    env = spec['measured_parameter_envelope']
    records = []
    counts = {'COMPATIBLE': 0, 'INCOMPATIBLE': 0, 'UNRESOLVED': 0}
    for identity in sorted(fallback_rows):
        item, fallback = fallback_rows[identity]
        values = arc_values(raw, item)
        local = local_rows[identity]
        geometry_class = (values['layer'] == 'F.Cu' and values['width_mm'] > 0
                          and values['centerline_length_mm'] > 0
                          and values['midpoint_deviation_mm'] <= args.collinear_limit_mm)
        in_width_range = env['width_min_mm'] <= values['width_mm'] <= env['width_max_mm']
        in_length_range = env['length_min_mm'] <= values['centerline_length_mm'] <= env['length_max_mm']
        target_metrics = local['target_arc_only_diagnostic_vs_plot']
        expected_area = target_metrics['expected_area_mm2']
        relative_area = (target_metrics['symmetric_difference_area_mm2'] / expected_area
                         if expected_area else None)
        area_ok = target_metrics['symmetric_difference_area_mm2'] <= policy['maximum_symmetric_difference_area_mm2']
        relative_ok = (relative_area is not None and relative_area <= policy['maximum_relative_symmetric_difference_fraction'])
        boundary_ok = target_metrics['boundary_hausdorff_distance_mm'] <= policy['maximum_boundary_hausdorff_distance_mm']
        isolated_in_roi = len(local['fallback_identities_in_roi']) == 1
        unique_area = local['target_only_added_area_mm2'] > 1e-15
        if not geometry_class:
            status, reason = 'INCOMPATIBLE', 'source geometry is outside the exact-collinear round-stroke coupon class'
        elif not (in_width_range and in_length_range):
            status, reason = 'UNRESOLVED', 'outside coupon width/length envelope'
        elif not isolated_in_roi:
            status, reason = 'UNRESOLVED', 'local ROI contains multiple unsupported arcs; individual plot contribution is not isolated'
        elif not unique_area:
            status, reason = 'UNRESOLVED', 'diagnostic stroke adds no unique area beyond supported neighboring copper'
        elif area_ok and relative_ok and boundary_ok:
            status, reason = 'COMPATIBLE', 'isolated local comparison falls within the synthetic coupon reference envelope'
        else:
            status, reason = 'UNRESOLVED', 'isolated local comparison exceeds at least one coupon reference tolerance'
        counts[status] += 1
        records.append({
            'source_identity': identity,
            **values,
            'native_inventory_classification': item.get('unsupported_reason'),
            'diagnostic_kind': fallback['fallback_kind'],
            'coupon_geometry_class_match': geometry_class,
            'coupon_width_range_match': in_width_range,
            'coupon_length_range_match': in_length_range,
            'local_roi_bounds_mm': local['roi_bounds_mm'],
            'supported_neighbor_count': local['supported_source_count'],
            'unsupported_arc_count_in_roi': len(local['fallback_identities_in_roi']),
            'target_unique_area_mm2': local['target_only_added_area_mm2'],
            'target_only_plot_metrics': {
                'symmetric_difference_area_mm2': target_metrics['symmetric_difference_area_mm2'],
                'symmetric_difference_fraction_of_expected': relative_area,
                'boundary_hausdorff_distance_mm': target_metrics['boundary_hausdorff_distance_mm'],
                'area_reference_pass': area_ok,
                'relative_area_reference_pass': relative_ok,
                'boundary_reference_pass': boundary_ok,
            },
            'status': status,
            'reason': reason,
        })
    report = {
        'schema': 'real-degenerate-arc-coupon-compatibility/1',
        'status': 'TRIAGED_NOT_QUALIFIED',
        'compatibility_counts': counts,
        'source': {'path': str(source_path.relative_to(ROOT)), 'sha256': source_hash},
        'gerber': {'path': str(gerber_path.relative_to(ROOT)), 'sha256': gerber_hash},
        'input_integrity': {'entry_count': manifest['entry_count'],
                            'verified_count': manifest['verified_count'], 'status': manifest['status']},
        'coupon_reference': {
            'source_hash': spec['generated_source_sha256'],
            'accuracy_policy_hash': coupon['accuracy_policy']['sha256'],
            'width_length_envelope': env,
            'tolerances_are_reference_only': True,
        },
        'classification_policy': {
            'exact_collinear_max_deviation_mm': args.collinear_limit_mm,
            'compatible': 'exact-collinear class; width and length within coupon envelope; one unsupported arc in ROI; target adds unique area; target-only source-to-plot area, relative-area, and boundary metrics meet coupon reference limits',
            'incompatible': 'source object does not belong to exact-collinear F.Cu round-stroke test class',
            'unresolved': 'overlap, no unique contribution, parameter mismatch, or reference metric outside the experimental envelope',
            'coupon_limits_not_board_acceptance': True,
        },
        'records': records,
        'limitations': [
            'COMPATIBLE means only that the declared diagnostic class and local plot evidence meet a synthetic coupon reference; it does not qualify parser support or native semantics generally.',
            'UNRESOLVED cases preserve overlapping/occluded contributions and metric misses; none are force-matched.',
            'No parser status changed; every source remains DEGENERATE_ARC/unsupported.',
            'ORG-to-EDIT enhancement, correspondence correctness, electrical connectivity, and engineering/manufacturing acceptance remain unestablished.',
        ],
    }
    output.mkdir(parents=True)
    json_path = output / 'real_arc_compatibility.json'
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    md = [
        '# Real EDIT degenerate-arc compatibility triage', '',
        '**Status: TRIAGED_NOT_QUALIFIED.** All 84 arcs are evaluated by source identity. Coupon thresholds are reference criteria for this triage only; they are not board acceptance limits.', '',
        f"Source SHA-256 `{source_hash}`; own KiCad F.Cu plot SHA-256 `{gerber_hash}`; intake checks {manifest['verified_count']}/{manifest['entry_count']}.", '',
        f"The generated coupon spans widths {env['width_min_mm']:.6g}–{env['width_max_mm']:.6g} mm and lengths {env['length_min_mm']:.6g}–{env['length_max_mm']:.6g} mm from the real source. Results: {counts['COMPATIBLE']} compatible in isolated local ROIs; {counts['INCOMPATIBLE']} outside the tested geometry class; {counts['UNRESOLVED']} retained unresolved due to overlapping arcs, occlusion, or a local metric outside the reference envelope.", '',
        'Every source object remains `DEGENERATE_ARC`/unsupported. This is not parser promotion, whole-board enhancement attribution, connectivity, or manufacturing acceptance.', '',
        f"Per-record measurements and reasons: `{json_path.relative_to(ROOT)}`.", '',
    ]
    (output / 'README.md').write_text('\n'.join(md))
    files = sorted(p for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS')
    (output / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in files))
    print(json.dumps({'status':report['status'],'compatibility_counts':counts,
                      'output':str(output.relative_to(ROOT))},indent=2))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--package',default='dataset/szu-comm_3020301113B_intake_ready_20261021_v2')
    parser.add_argument('--export-run',default='out/ingestion/gerber_fidelity/run-20261022T182946Z')
    parser.add_argument('--per-arc-evidence',default='out/ingestion/gerber_fidelity/degenerate_arcs_20261024_v1/degenerate_arc_plot_evidence.json')
    parser.add_argument('--coupon-results',default='out/ingestion/gerber_fidelity/g8_real_scale_coupon_20261024_v1/results_v2/coupon_results.json')
    parser.add_argument('--coupon-spec',default='out/ingestion/gerber_fidelity/g8_real_scale_coupon_20261024_v1/expected_spec.json')
    parser.add_argument('--output',default='out/ingestion/gerber_fidelity/real_arc_compatibility_20261024_v1')
    parser.add_argument('--collinear-limit-mm',type=float,default=1e-12)
    run(parser.parse_args())


if __name__=='__main__': main()
