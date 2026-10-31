#!/usr/bin/env python3
"""Retain a labelled synthetic adaptive bundle → width composition example."""
from pathlib import Path
import argparse
import html
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.stage_abi.composition import execute_sequence
from src.stage_abi.scene import composed
from src.stage_abi.service import runtime_fingerprint
from src.stage_abi.visuals import comparison_svg
from src.stage_abi.width import WidthAdapter, width_parameters
from src.trace_first_pipeline import write
from tests.test_stage_abi_routes import case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output.resolve()
    if out.exists() or not out.is_relative_to(ROOT / 'out'):
        raise ValueError('FRESH_PROJECT_OUTPUT_REQUIRED')
    out.mkdir(parents=True)
    e = case(out)
    if 'plan_error' in e:
        raise ValueError(e['plan_error'])
    store, service, doc = e['store'], e['service'], e['doc']
    doc['profiles']['profile']['adapter'] = 'parallel-route-v1'
    service.adapters['parallel-route-v1'] = service.adapters.pop('test-adapter')
    plan = store.get_json(e['plan'], kind='plan')
    selection = store.get_json(plan['selection_ref'], kind='selection')
    template = store.put_json('selection-template', {k: v for k, v in selection.items() if k not in ('stage', 'scene_ref')})
    policy = store.put_json('policy', dict(stage='t04', parameters=width_parameters()))
    bounds = store.put_json('bounds', dict(max_source_objects=30, max_targets=5, max_evaluations=1000, max_output_bytes=10000000, max_seconds=120))
    doc['profiles']['width'] = dict(stage='t04', adapter='native-width-v1', policy_ref=policy, scene_refs=[e['scene']], bounds_ref=bounds, verifier_ref=store.put_json('verifier', dict(family=width_parameters()['family'])))
    service.adapters['native-width-v1'] = WidthAdapter()
    width_template = store.put_json('selection-template', dict(source_ids=['low', 'upper'], groups=[dict(group_id='parallel', members=['low', 'upper'])]))
    steps = [dict(stage='t03', profile_id='profile', selection_template_ref=template, proof_scope_ref=store.put_json('proof-scope', dict(scope='complete-source-parallel-route-and-attachments'))), dict(stage='t04', profile_id='width', selection_template_ref=width_template, proof_scope_ref=store.put_json('proof-scope', dict(scope='complete-source-nominal-envelope-and-upper-proofs')))]
    source = store.get_json(e['scene'], kind='scene')
    grant = store.put_json('composition-grant', dict(authority='User standing active goal: bounded explicitly synthetic ABI qualification, not a board repair or owner acceptance', initial_scene_ref=e['scene'], source_sha256=source['source_sha256'], steps=steps, output_scope_ref=e['scope'], max_steps=2))
    doc['composition_refs'] = [grant]
    result = execute_sequence(service, initial_scene_ref=e['scene'], qualification_ref=plan['qualification_ref'], steps=steps, grant_ref=grant, idempotency_prefix='retained-model')
    if result['status'] != 'PASS_LOCAL_MODULAR_COMPOSITION':
        raise ValueError(result)
    route = store.get_json(result['steps'][0]['candidate_ref'], kind='candidate')
    if route['status'] != 'CONSTRUCTED' or len(route['chosen']['moving']) != 2:
        raise ValueError('POSITIVE_ADAPTIVE_BUNDLE_REQUIRED')
    before = composed(store, source)
    after = composed(store, store.get_json(result['output_scene_ref'], kind='scene'))
    for name, copper in [('before', before), ('after', after)]:
        inner = comparison_svg(copper, after.difference(before) if name == 'after' else before.difference(after), source['viewport_mm'], title='Synthetic bundle ' + name).decode()
        inner = inner.replace('<svg ', '<svg x="20" y="120" ', 1)
        caption = 'SYNTHETIC MODEL / adaptive two-trace T03 + collective T04 / ' + name
        text = '<text x="20" y="38" font-size="26">' + html.escape(caption) + '</text><text x="20" y="76" font-size="17">Exact constructed model copper, not original-board geometry. Both local stage verifications PASS.</text><text x="20" y="105" font-size="17">Two members move through one reference; fixed widths in T03; one shared width scale in T04. No owner acceptance.</text>'
        path = out / (name + '.svg')
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1240" height="1060" viewBox="0 0 1240 1060"><rect width="1240" height="1060" fill="#edf4f7"/>' + text + inner + '</svg>')
        subprocess.run(['sips', '-s', 'format', 'png', str(path), '--out', str(path.with_suffix('.png'))], check=True, capture_output=True)
    write(out / 'RESULT.json', result)
    write(out / 'registry.json', doc)
    write(out / 'RECEIPT.json', dict(status='PASS_SYNTHETIC_ADAPTIVE_BUNDLE_AND_NATIVE_DERIVED_WIDTH_COMPOSITION', runtime_fingerprint=runtime_fingerprint(), fixture='tests.test_stage_abi_routes.case', actual_board=False, chosen=route['chosen'], output_scene_ref=result['output_scene_ref'], owner='NOT_GRANTED', independent_native_electrical_manufacturing='NOT_ESTABLISHED'))
    (out / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Synthetic adaptive bundle ABI</title><style>body{font:18px system-ui;margin:24px}img{max-width:100%}</style><h1>Explicit synthetic bundle model</h1><p>Actual T03 displacement followed by T04 on the derived routes. This is not source-board geometry.</p><img src="before.png"><img src="after.png"><p><a href="RECEIPT.json">Receipt</a> · <a href="RESULT.json">Full ABI transcript and composition</a></p>')
    print(result['status'])


if __name__ == '__main__':
    main()
