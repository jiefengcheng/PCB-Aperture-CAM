#!/usr/bin/env python3
"""Produce a non-mutating, multi-reason decomposition of G8 arc triage."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = Path('out/ingestion/gerber_fidelity/real_arc_compatibility_20261024_v1/real_arc_compatibility.json')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decompose(report):
    rows = []
    status_counts = Counter()
    reason_counts = Counter()
    unresolved_combinations = Counter()
    for record in report['records']:
        metrics = record['target_only_plot_metrics']
        flags = {
            'source_geometry_outside_coupon_class': not record['coupon_geometry_class_match'],
            'width_outside_coupon_envelope': not record['coupon_width_range_match'],
            'length_outside_coupon_envelope': not record['coupon_length_range_match'],
            'multiple_unsupported_arcs_in_roi': record['unsupported_arc_count_in_roi'] > 1,
            'no_unique_target_area': record['target_unique_area_mm2'] <= 1e-15,
            'absolute_area_reference_miss': not metrics['area_reference_pass'],
            'relative_area_reference_miss': not metrics['relative_area_reference_pass'],
            'boundary_reference_miss': not metrics['boundary_reference_pass'],
        }
        active = sorted(key for key, value in flags.items() if value)
        status_counts[record['status']] += 1
        reason_counts.update(active)
        if record['status'] == 'UNRESOLVED':
            unresolved_combinations[' + '.join(active) or 'none'] += 1
        rows.append({
            'source_identity': record['source_identity'],
            'status_unchanged': record['status'],
            'original_primary_reason': record['reason'],
            'reason_flags': flags,
            'unsupported_arc_count_in_roi': record['unsupported_arc_count_in_roi'],
            'supported_source_count_in_roi': record['supported_neighbor_count'],
            'target_unique_area_mm2': record['target_unique_area_mm2'],
            'reported_metric_scope': 'strict supported-local copper union plus this target fallback, compared to the clipped KiCad F.Cu copper union',
            'metrics': metrics,
        })
    return {
        'status_counts_unchanged': dict(status_counts),
        'multi_label_reason_counts': dict(reason_counts),
        'unresolved_reason_combinations': dict(unresolved_combinations),
        'records': rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default=DEFAULT_INPUT.as_posix())
    parser.add_argument('--output', default='out/ingestion/gerber_fidelity/g9_arc_attribution_current_v1/reason_decomposition_v2.json')
    args = parser.parse_args()
    source = (ROOT / args.input).resolve()
    output = (ROOT / args.output).resolve()
    if not source.is_relative_to(ROOT / 'out') or not output.is_relative_to(ROOT / 'out'):
        raise SystemExit('input and output must remain under out/')
    if not source.is_file() or output.exists():
        raise SystemExit('input missing or output already exists')
    report = json.loads(source.read_text())
    if report.get('schema') != 'real-degenerate-arc-coupon-compatibility/1' or len(report.get('records', [])) != 84:
        raise SystemExit('G8 compatibility report identity/count mismatch')
    decomposed = decompose(report)
    decomposed['status_counts_unchanged'] = {
        key: decomposed['status_counts_unchanged'].get(key, 0)
        for key in ('COMPATIBLE', 'INCOMPATIBLE', 'UNRESOLVED')
    }
    result = {
        'schema': 'g9-real-arc-reason-decomposition/1',
        'status': 'DIAGNOSTIC_ONLY_CLASSIFICATIONS_UNCHANGED',
        'input_path': str(source.relative_to(ROOT)),
        'input_sha256': sha(source),
        'source_sha256': report['source']['sha256'],
        'gerber_sha256': report['gerber']['sha256'],
        **decomposed,
        'interpretation': [
            'Flags are multi-label predicates computed from the frozen G8 rows; they do not alter any G8 status.',
            'The legacy target_arc_only_diagnostic_vs_plot field is not an isolated target-vs-plot comparison: the expected side includes the entire supported local F.Cu geometry union plus the target fallback, and the observed side is the local KiCad Gerber union.',
            'Only the paired synthetic KiCad coupon experiment can directly measure an incremental target contribution by subtracting a same-context no-target plot from a with-target plot.',
            'No parser support, ORG-to-EDIT enhancement attribution, connectivity, or manufacturing claim follows.',
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'status': result['status'],
        'status_counts_unchanged': result['status_counts_unchanged'],
        'multi_label_reason_counts': result['multi_label_reason_counts'],
        'unresolved_reason_combinations': result['unresolved_reason_combinations'],
        'input_sha256': result['input_sha256'],
        'output': str(output.relative_to(ROOT)),
    }, indent=2))


if __name__ == '__main__':
    main()
