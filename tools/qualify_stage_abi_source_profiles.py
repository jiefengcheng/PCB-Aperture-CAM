#!/usr/bin/env python3
"""Fresh, bounded ABI executions on actual C03 source/predecessor operands.

Host preparation is explicit and retained. Accepted scenes are read-only inputs;
these executions never replace their receipts or imply whole-board acceptance.
"""
from pathlib import Path
import argparse
import json
import subprocess
import shutil
import sys
from dataclasses import asdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shapely import from_wkb, to_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.junction_spindle_stage import CONTRACT
from src.parallel_route_geometry import route_copper
from src.stage_abi import ABI_VERSION
from src.stage_abi.lands import LandAdapter, land_parameters
from src.stage_abi.native_import import import_width_scene
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.routes import RouteAdapter, route_parameters
from src.stage_abi.scene import composed, validate_scene
from src.stage_abi.service import StageService, runtime_fingerprint
from src.stage_abi.spindle import SpindleAdapter
from src.stage_abi.store import ArtifactStore
from src.trace_first_pipeline import digest, read, write
from tools.c03_sequence_scene import CACHE, load_scene
from tools.render_c03_source_frame import render_source_frame

STAGES = {
    't01': (LandAdapter('t01'), 'round-class-v1', 'round_class_growth', 'complete-source-land-and-inclusive'),
    't02': (LandAdapter('t02'), 'rectangle-inclusive-v1', 'whole_rectangle_growth', 'complete-source-land-and-inclusive'),
    't03': (RouteAdapter(), 'parallel-route-v1', 'obstacle_directed_single_or_bundle', 'complete-source-parallel-route-and-attachments'),
    't05': (SpindleAdapter(), 'spindle-v1', 'bounded_additive_spindle', 'complete-source-and-all-patches'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=STAGES)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / 'out') or out.exists():
        raise ValueError('FRESH_PROJECT_OUTPUT_REQUIRED')
    assets = verify_assets()
    run = ROOT / 'out/crop_dynamic_tasks/c03_sequence_20261030_269'
    stage = args.stage
    through = dict(t01='T01', t02='T04', t03='T01', t05='T02')[stage]
    scope, meta, original, current, replacements, routes = load_scene(run, through)
    raw = (CACHE / 'ORG_source.kicad_pcb').read_bytes()
    manifest = read(CACHE / 'source_manifest.json')
    blobs = {sid: (CACHE / 'source_wkb' / f"{m['geometry_sha256']}.wkb").read_bytes() for sid, m in meta.items()}
    if stage == 't01':
        current = original
        replacements = {}
    widths = {p['source_id']: p['nominal_candidate_width_mm'] for r in routes for p in r['primitives']}
    out.mkdir(parents=True)
    source_fingerprint = runtime_fingerprint()
    for source in [*sorted((ROOT / 'src').glob('*.py')), *sorted((ROOT / 'src/stage_abi').glob('*.py')), Path(__file__)]:
        target = out / 'code_snapshot' / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    store = ArtifactStore(out / 'runtime')
    preparation = dict(source_sha256=digest(CACHE / 'ORG_source.kicad_pcb'), source_manifest_sha256=digest(CACHE / 'source_manifest.json'), predecessor=through if stage != 't01' else 'ORG', viewport_mm=scope['viewport_mm'], source_run=str(run.relative_to(ROOT)), scope='One explicitly selected operation with complete original source context. C03 screenshot localization remains provisional; no new accepted scene.')
    imported = import_width_scene(store, source=raw, manifest=manifest, original_blobs=blobs, current_blobs=replacements, chains=[], viewport_mm=scope['viewport_mm'], qualification=preparation, current_widths=widths)
    scene = store.get_json(imported['scene_ref'], kind='scene')
    rows = {r['source_id']: r for r in scene['objects']}
    for sid in sorted(set(current) - set(meta)):
        ref = store.put('geometry', to_wkb(current[sid]))
        rows[sid] = dict(source_id=sid, kind='inclusive_rectangle', original_ref=ref, geometry_ref=ref, metadata=dict(origin='qualified-T02-inclusive-input', source_result_sha256=digest(run / 'T02/RESULT.json')))
    detail = None
    extras = {}
    if stage == 't01':
        target = next(r for r in scope['records'] if r.get('key') == 'C202')
        sid = target['source_id']
        rows[sid]['metadata'].update({k: target[k] for k in ['center_mm', 'original_radius_mm', 'admissible_diameters_mm', 'desired_diameter_mm']})
        rows[sid]['metadata']['original_quad_segs'] = (len(original[sid].exterior.coords) - 1) // 4
        selected = [sid]
        preparation['target_record'] = target
        detail = original[sid].buffer(.12).bounds
    elif stage == 't02':
        target = next(r for r in read(run / 'T02/DECISIONS.json') if r['status'] == 'GROWN' and len(r['aliases']) == 1)
        selected = target['aliases']
        preparation['target_record'] = {k: target[k] for k in ['key', 'source_id', 'aliases']}
        detail = current[selected[0]].buffer(.5).bounds
    else:
        construction = read(run / 'T04/CONSTRUCTION.json')
        if stage == 't05':
            target = next(r for r in read(run / 'T05/DECISIONS.json') if r['status'] == 'GROWN' and r['land_kinds'] == ['circle', 'circle'])
            route = next(r for r in construction if r['component_id'] == target['route_id'])
        else:
            route = next(r for r in construction if len(r['primitives']) == 1 and r['primitives'][0]['kind'] == 'segment')
        members = route['complete_source_ids']
        sid = 'route:' + route['component_id']
        original_route = unary_union([original[s] for s in members])
        current_route = unary_union([current[s] for s in members])
        metadata = dict(native_source_ids=members, nominal_width_mm=route['primitives'][0]['original_width_mm'] if stage == 't03' else route['primitives'][0]['nominal_candidate_width_mm'], complete_route_qualification=preparation)
        if stage == 't05':
            metadata['land_ids'] = target['land_ids']
        else:
            primitive = route['primitives'][0]
            a, b = primitive['start_mm'], primitive['end_mm']
            path = [[a[0] + (b[0] - a[0]) * i / 8, a[1] + (b[1] - a[1]) * i / 8] for i in range(9)]
            quad = (len(original_route.exterior.coords) - 3) // 4
            if not route_copper(path, metadata['nominal_width_mm'], quad_segs=quad).equals(current_route):
                raise ValueError('EXACT_NATIVE_POLYLINE_ADMISSION_REQUIRED')
            metadata.update(route_points_mm=path, route_quad_segs=quad)
            obstacle = min((s for s, r in rows.items() if r['kind'] == 'rectangle' and current_route.distance(current[s]) >= .0201), key=lambda s: (current_route.distance(current[s]), s))
            extras = dict(seed_ids=[sid], obstacle_ids=[obstacle], bundle_ref=store.put_json('parallel-bundle', dict(reference_points_mm=path, members=[dict(source_id=sid, offset_mm=0.)])), corridor_ref=store.put('geometry', to_wkb(current_route.buffer(.2))), initial_indices=[3, 3], objective='explicit-clearance')
            preparation['objective_note'] = 'Actual closest admitted rectangle already meets clearance: correct result is NO_CHANGE_REQUIRED. Positive adaptive two-member displacement is tested separately on a labelled synthetic model, not a fabricated source defect.'
        for member in members:
            del rows[member]
        rows[sid] = dict(source_id=sid, kind='trace', original_ref=store.put('geometry', to_wkb(original_route)), geometry_ref=store.put('geometry', to_wkb(current_route)), metadata=metadata)
        selected = [sid]
        preparation['native_complete_route'] = dict(component_id=route['component_id'], source_ids=members)
        detail = current_route.buffer(.4).bounds
    scene['objects'] = list(rows.values())
    scene_ref = store.put_json('scene', scene)
    scene = validate_scene(store, scene_ref)
    actual_before = composed(store, scene)
    expected = unary_union([current[s] for s in sorted(current)]).intersection(box(*scope['viewport_mm']))
    if actual_before.symmetric_difference(expected).area > 1e-12:
        raise ValueError('PREDECESSOR_COMPOSITION_MISMATCH')
    adapter, factory, strategy, proof = STAGES[stage]
    parameters = land_parameters(stage) if stage in ('t01', 't02') else route_parameters() if stage == 't03' else dict(asdict(CONTRACT), radius_scales=list(CONTRACT.radius_scales))
    policy = store.put_json('policy', dict(stage=stage, parameters=parameters))
    limits = dict(max_source_objects=20000, max_targets=1, max_evaluations=1000, max_output_bytes=100000000, max_seconds=300)
    if stage == 't03':
        limits.update(max_displacement_um=100, max_members=1, max_extension_um=2000, max_extension_steps=2, max_recursion_depth=1)
    bounds = store.put_json('bounds', limits)
    verifier = store.put_json('verifier', dict(family=adapter.describe()['family']))
    profile = 'c03-native-' + stage
    doc = dict(schema='stage-agent-registry/1', profiles={profile: dict(stage=stage, adapter=factory, policy_ref=policy, scene_refs=[scene_ref], bounds_ref=bounds, verifier_ref=verifier)}, authorization_refs=[], decision_refs=[])
    service = StageService(store, TrustedRegistry(store, doc), {factory: adapter})
    transcript = []

    def call(verb, payload, **kw):
        request = dict(abi_version=ABI_VERSION, request_id='source-' + verb, operation=stage + '_' + verb, profile_id=profile, scene_ref=scene_ref, policy_ref=policy, plan_ref=kw.get('plan_ref'), authorization_ref=kw.get('authorization_ref'), idempotency_key=kw.get('idempotency_key'), payload=payload)
        response = service.dispatch(request)
        transcript.append(dict(request=request, response=response))
        write(out / 'TRANSCRIPT.json', transcript)
        if response['status'] != 'OK':
            raise ValueError(response)
        return response['result']

    inspected = call('inspect', dict(source_ids=selected, finding_ids=[], page_size=10, cursor=None))
    selection = store.put_json('selection', dict(stage=stage, scene_ref=scene_ref, source_ids=selected, **extras))
    qualification = store.put_json('verification', dict(scene_ref=scene_ref, geometric_status='PASS', scope='Host-qualified exact source/cache footprint and predecessor composition; not clearance/electrical acceptance of every inherited relationship', preparation=preparation))
    planned = call('plan', dict(inspection_ref=inspected['inspection_ref'], selection_ref=selection, predecessor_qualification_ref=qualification, bounds_ref=bounds, strategy=strategy))
    plan = planned['plan_ref']
    output = store.put_json('output-scope', dict(kind='immutable-local-artifacts'))
    auth = store.put_json('authorization', dict(profile_id=profile, scene_ref=scene_ref, policy_ref=policy, plan_ref=plan, operations=[stage + ('_search' if stage == 't03' else '_run'), stage + '_verify'], authority='User standing active goal: fully implement all ABI suites; new local qualification only, frozen C01/C02/C03 remain immutable', output_scope_ref=output))
    doc['authorization_refs'].append(auth)
    result = call('search' if stage == 't03' else 'run', dict(output_scope_ref=output), plan_ref=plan, authorization_ref=auth, idempotency_key='native-construct')['result']
    candidate = result['candidate']
    verified = call('verify', dict(candidate_ref=result['candidate_ref'], verifier_ref=verifier, proof_scope_ref=store.put_json('proof-scope', dict(scope=proof))), plan_ref=plan, authorization_ref=auth, idempotency_key='native-verify')['result']
    if verified['verification']['geometric_status'] != 'PASS':
        raise ValueError('SOURCE_REPLAY_NOT_PASS')
    if stage != 't03' and not any(r['status'] == 'GROWN' for r in candidate['decisions']):
        raise ValueError('POSITIVE_NATIVE_CONSTRUCTION_REQUIRED')
    before = from_wkb(store.get(candidate['before_ref'], kind='geometry'))
    after = from_wkb(store.get(candidate['after_ref'], kind='geometry'))
    for label, geometry in [('before', before), ('after', after)]:
        (out / (label + '.wkb')).write_bytes(to_wkb(geometry))
        for view, viewport in [('full', scope['viewport_mm']), ('detail', list(box(*detail).intersection(box(*scope['viewport_mm'])).bounds))]:
            image = out / (view + '_' + label + '.svg')
            render_source_frame(image, 'C03 / source-bound ABI ' + stage.upper() + ' / ' + view + ' ' + label, geometry, after.difference(before) if label == 'after' else before.difference(before), viewport, notes=['One source-bound operation, complete source context. Red=cumulative copper; teal=actual new copper.', 'ABI local construction and direct replay PASS; no new owner/native/electrical/manufacturing acceptance.', 'Frozen C01/C02/C03 unchanged. C03 screenshot localization remains provisional.'])
            subprocess.run(['sips', '-s', 'format', 'png', str(image), '--out', str(image.with_suffix('.png'))], check=True, capture_output=True)
    if runtime_fingerprint() != source_fingerprint:
        raise ValueError('RUNTIME_CHANGED_DURING_QUALIFICATION')
    receipt = dict(status='PASS_REAL_SOURCE_BOUNDED_' + stage.upper(), stage=stage, runtime_fingerprint=source_fingerprint, asset_integrity=assets, preparation=preparation, native_source_objects=len(meta), scene_objects=len(rows), selected_source_ids=selected, before_sha256=digest(out / 'before.wkb'), after_sha256=digest(out / 'after.wkb'), added_area_mm2=after.difference(before).area, removed_area_mm2=before.difference(after).area, candidate_ref=result['candidate_ref'], verification_ref=verified['verification_ref'], output_scene_ref=candidate['output_scene_ref'], geometry_status='PASS', owner='NOT_GRANTED_FOR_NEW_SCENE', independent='NOT_RUN', native_electrical_manufacturing='NOT_ESTABLISHED')
    write(out / 'RECEIPT.json', receipt)
    write(out / 'registry.json', doc)
    write(out / 'PREPARATION.json', preparation)
    (out / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Actual source ABI qualification</title><style>body{font:18px system-ui;margin:24px}img{max-width:100%}</style><h1>C03 source-bound ' + stage.upper() + ' ABI qualification</h1><p>Bounded local execution and direct replay. Frozen accepted scenes unchanged; no new acceptance.</p>' + ''.join('<h2>' + name.replace('_', ' ') + '</h2><img src="' + name + '.png">' for name in ['full_before', 'full_after', 'detail_before', 'detail_after']) + '<p><a href="RECEIPT.json">Receipt</a> · <a href="TRANSCRIPT.json">Actual requests/responses</a> · <a href="PREPARATION.json">Host source preparation</a></p>')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
