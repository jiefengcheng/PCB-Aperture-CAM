#!/usr/bin/env python3
"""Evaluate G10 paired-plot attribution and precision/repeat diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from shapely import affinity
from shapely.geometry import GeometryCollection, LineString
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.gerber_image import CompletionParser, compose
from src.native_inventory import steps
from tools.qualify_collinear_arc_coupon import polygon_topology
from gerbonara.rs274x import GerberFile
from gerbonara.utils import MM


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def stroke(seg):
    return LineString([tuple(seg['start']),tuple(seg['end'])]).buffer(
        seg['width']/2,quad_segs=steps(seg['width']/2),cap_style='round',join_style='round')


def plot(path):
    # Measurement-only path: the production profile intentionally admits 4.6,
    # while this sweep compares KiCad's supported 4.5 and 4.6 exports. Keep
    # parser qualification unchanged; use the pinned strict adapter and verify
    # units/notation before composing diagnostic geometry.
    text=Path(path).read_text(); gerber=GerberFile(); parser=CompletionParser(gerber)
    parser.parse(text,filename=str(path))
    if parser.block_frame is not None or parser.current_region is not None:
        raise SystemExit(f'unclosed Gerber structure: {path}')
    if parser.inventory['MO']!=1 or parser.inventory['FS']!=1:
        raise SystemExit(f'expected explicit unit and coordinate format: {path}')
    if parser.file_settings.number_format not in ((2,5),(4,5),(2,6),(4,6)):
        raise SystemExit(f'unsupported measurement precision: {path}')
    if parser.file_settings.unit!=MM or not parser.file_settings.notation=='absolute':
        raise SystemExit(f'measurement requires absolute millimeter coordinates: {path}')
    geometry=compose(gerber.objects)
    if not geometry.is_valid: raise SystemExit(f'invalid composed Gerber image: {path}')
    return affinity.scale(geometry,xfact=1,yfact=-1,origin=(0,0))


def geom_for_case(root,case,precision,side):
    export=case['plots'][str(precision)][side]
    path=ROOT/export['gerber_path']
    if sha(path)!=export['gerber_sha256']: raise SystemExit(f'Gerber hash mismatch: {path}')
    return plot(path)


def measure(case,baseline,treated,limits):
    scenario=case['scenario']; target=scenario['target']
    contexts=[stroke(x) for x in scenario['context_segments']]
    base_expected=unary_union(contexts) if contexts else GeometryCollection()
    target_shape=LineString([tuple(target['start']),tuple(target['end'])]).buffer(
        target['width']/2,quad_segs=steps(target['width']/2),cap_style='round',join_style='round')
    expected=base_expected.union(target_shape).difference(base_expected)
    observed=treated.difference(baseline)
    delta=expected.symmetric_difference(observed).area
    rel=delta/expected.area if expected.area else (0.0 if observed.is_empty else None)
    hausdorff=(expected.boundary.hausdorff_distance(observed.boundary)
               if not expected.is_empty and not observed.is_empty else
               (0.0 if expected.is_empty and observed.is_empty else None))
    topology_equal=polygon_topology(expected)==polygon_topology(observed)
    checks={'absolute_area_within_reference':delta<=limits['maximum_symmetric_difference_area_mm2'],
            'relative_area_within_reference':rel is not None and rel<=limits['maximum_relative_symmetric_difference_fraction'],
            'boundary_within_reference':hausdorff is not None and hausdorff<=limits['maximum_boundary_hausdorff_distance_mm'],
            'topology_equal':topology_equal}
    if expected.is_empty and observed.is_empty:
        status='NO_OBSERVABLE_INCREMENT'
    elif expected.is_empty != observed.is_empty:
        status='UNRESOLVED'
    elif all(checks.values()):
        status='OBSERVABLE_INCREMENT'
    else:
        status='UNRESOLVED'
    return {'status':status,'expected_unique_area_mm2':expected.area,
            'measured_plot_increment_area_mm2':observed.area,
            'symmetric_difference_area_mm2':delta,
            'symmetric_difference_fraction_of_expected':rel,
            'boundary_hausdorff_distance_mm':hausdorff,
            'expected_covered_fraction':expected.intersection(observed).area/expected.area if expected.area else None,
            'expected_topology':polygon_topology(expected),'measured_topology':polygon_topology(observed),
            'reference_checks_only':checks}


def normalized_plot_hash(path):
    lines=path.read_text(errors='replace').splitlines()
    keep=[line for line in lines if not line.startswith('%TF.CreationDate,')
          and not line.startswith('G04 Created by KiCad (PCBNEW')]
    return hashlib.sha256(('\n'.join(keep)+'\n').encode()).hexdigest()


def verify_pair_source(root,case):
    pair=case['source_pair']; baseline=ROOT/pair['without_target']['path']; treated=ROOT/pair['with_target']['path']
    if sha(baseline)!=pair['without_target']['sha256'] or sha(treated)!=pair['with_target']['sha256']:
        raise SystemExit(f'source pair hash mismatch: {case["scenario"]["id"]}')
    target=case['scenario']['target']
    from tools.build_arc_attribution_sweep import serialize_target
    arc=serialize_target(f'{case["scenario"]["id"]}:target',target)
    expected=baseline.read_text()[:-2]+arc+')\n'
    if treated.read_text()!=expected:
        raise SystemExit(f'paired source differs beyond target arc: {case["scenario"]["id"]}')
    return {'verified':True,'baseline_sha256':sha(baseline),'treated_sha256':sha(treated),
            'target_only_byte_delta':True,'target_arc_serialized_sha256':hashlib.sha256(arc.encode()).hexdigest()}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',default='out/ingestion/gerber_fidelity/g10_arc_attribution_sweep_v2')
    ap.add_argument('--output',default='out/ingestion/gerber_fidelity/g10_arc_attribution_sweep_v2/results')
    args=ap.parse_args(); root=(ROOT/args.input).resolve(); out=(ROOT/args.output).resolve()
    if not root.is_relative_to(ROOT/'out') or not out.is_relative_to(ROOT/'out'): raise SystemExit('paths must stay under out/')
    if out.exists(): raise SystemExit(f'refusing to overwrite {out}')
    spec=json.loads((root/'scenario_spec.json').read_text())
    policy_path=ROOT/'out/ingestion/gerber_fidelity/g8_real_scale_coupon_20261024_v1/accuracy_policy.json'
    policy=json.loads(policy_path.read_text())['acceptance_by_feature']
    records=[]
    for case in spec['cases']:
        source_check=verify_pair_source(root,case)
        precision_results={}
        for precision in (6,5):
            if str(precision) not in case['plots']: continue
            b=geom_for_case(root,case,precision,'without_target')
            t=geom_for_case(root,case,precision,'with_target')
            precision_results[str(precision)]=measure(case,b,t,policy)
        repeat=None
        if '6_repeat' in case['plots']:
            b=geom_for_case(root,case,'6_repeat','without_target'); t=geom_for_case(root,case,'6_repeat','with_target')
            primary_b=geom_for_case(root,case,6,'without_target'); primary_t=geom_for_case(root,case,6,'with_target')
            repeat={'source_board_bytes_same':True,'without_target':{
                'primary_raw_sha256':case['plots']['6']['without_target']['gerber_sha256'],
                'repeat_raw_sha256':case['plots']['6_repeat']['without_target']['gerber_sha256'],
                'primary_body_sha256':normalized_plot_hash(ROOT/case['plots']['6']['without_target']['gerber_path']),
                'repeat_body_sha256':normalized_plot_hash(ROOT/case['plots']['6_repeat']['without_target']['gerber_path']),
                'plot_geometry_symmetric_difference_mm2':primary_b.symmetric_difference(b).area},
                'with_target':{
                'primary_raw_sha256':case['plots']['6']['with_target']['gerber_sha256'],
                'repeat_raw_sha256':case['plots']['6_repeat']['with_target']['gerber_sha256'],
                'primary_body_sha256':normalized_plot_hash(ROOT/case['plots']['6']['with_target']['gerber_path']),
                'repeat_body_sha256':normalized_plot_hash(ROOT/case['plots']['6_repeat']['with_target']['gerber_path']),
                'plot_geometry_symmetric_difference_mm2':primary_t.symmetric_difference(t).area},
                'increment_metrics':measure(case,b,t,policy)}
        records.append({'scenario_id':case['scenario']['id'],'parameter_label':case['scenario']['parameter_label'],
                        'orientation':case['scenario']['orientation'],'context_kind':case['scenario']['context_kind'],
                        'source_pair_verification':source_check,'precision_results':precision_results,
                        'fresh_plot_repeat':repeat})
    counts={}
    for precision in ('6','5'):
        rows=[r['precision_results'][precision]['status'] for r in records if precision in r['precision_results']]
        if rows: counts[precision]={k:rows.count(k) for k in ('OBSERVABLE_INCREMENT','NO_OBSERVABLE_INCREMENT','UNRESOLVED')}
    report={'schema':'g10-arc-attribution-sweep-results/1','status':'BOUNDED_SYNTHETIC_DIAGNOSTIC',
            'scenario_spec_sha256':sha(root/'scenario_spec.json'),'reference_policy_sha256':sha(policy_path),
            'g8_reference_limits_only':policy,'status_counts_by_precision':counts,
            'source_pair_exact_diff_checks_passed':all(r['source_pair_verification']['target_only_byte_delta'] for r in records),
            'results':records,
            'limitations':['Synthetic coupons only; no source object in real EDIT was removed.','G8 thresholds remain experiment references only.',
                           'The expanded sample does not qualify all 84 EDIT arcs or general KiCad arc semantics.',
                           'No parser, ORG/EDIT classification, connectivity, or manufacturing result changed.']}
    out.mkdir(parents=True); result_path=out/'attribution_sweep.json'; result_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    md=['# G10 attribution sweep results','','**Status: BOUNDED_SYNTHETIC_DIAGNOSTIC.** The three-way status vocabulary distinguishes observable increments, fully hidden increments, and unresolved metric outcomes. G8 thresholds are references only. KiCad CLI 10.99 accepts precision 5 and 6; precision 4 was rejected in the retained initial attempt and is recorded as `NOT_RUN_UNSUPPORTED_BY_KICAD_CLI`.','',
        '| Scenario | Parameter | Orientation | Context | p6 status | p5 status | Repeat |','|---|---|---|---|---|---|---|']
    for r in records:
        pr=r['precision_results']; rep=r['fresh_plot_repeat']
        repeat_status='not repeated'
        if rep:
            equal=(rep['without_target']['primary_body_sha256']==rep['without_target']['repeat_body_sha256'] and
                   rep['with_target']['primary_body_sha256']==rep['with_target']['repeat_body_sha256'] and
                   rep['without_target']['plot_geometry_symmetric_difference_mm2']==0 and
                   rep['with_target']['plot_geometry_symmetric_difference_mm2']==0)
            repeat_status='normalized plot matches' if equal else 'repeat differs'
        md.append(f"| {r['scenario_id']} | {r['parameter_label']} | {r['orientation']} | {r['context_kind']} | {pr.get('6',{}).get('status','n/a')} | {pr.get('5',{}).get('status','n/a')} | {repeat_status} |")
    (out/'README.md').write_text('\n'.join(md)+'\n')
    import hashlib as _hash
    lines=[]
    for p in sorted(out.rglob('*')):
        if p.is_file() and p.name!='SHA256SUMS': lines.append(f'{sha(p)}  {p.relative_to(out).as_posix()}')
    (out/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':report['status'],'scenario_count':len(records),'status_counts_by_precision':counts,
                      'source_pair_exact_diff_checks_passed':report['source_pair_exact_diff_checks_passed'],
                      'output':str(out.relative_to(ROOT))},indent=2))


if __name__=='__main__': main()
