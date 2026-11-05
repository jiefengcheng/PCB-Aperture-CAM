#!/usr/bin/env python3
"""Source-bound recovery diagnostic; never a native job or candidate export.

Construct the independent round intent, check its permissions and unchanged
native T03 accommodation, and retain every result before asking for extra rights.
This cannot advance any managed pipeline or promote retained qualification.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shapely import STRtree, from_wkb, to_wkb
from shapely.geometry import box
from src.c03_recovery import (assess_round_output, circle_obligations,
    digest, load_intent, permission_record, required_rounds, permitted_rounds,
    scope_round_assessment)
from src.crop_balanced_t01 import CropSettings, WorkingScene
from src.prepared_land_scene import PreparedLandScene
from src.stage_abi.store import canonical
from src.u02_board.adapter import pair_check, TRACE_KINDS
from tools.pcb_workspace import configure, WORK


def inspect(native, output):
    configure()
    native = Path(native).absolute()
    output = Path(output).absolute()
    if not output.is_relative_to(WORK) or output.exists():
        raise ValueError('C03_FRESH_EXTERNAL_EVIDENCE_REQUIRED')
    if not native.is_relative_to(WORK) or not native.is_dir():
        raise ValueError('C03_EXPLICIT_RETAINED_NATIVE_ROOT_REQUIRED')
    bindings = {}

    def body(path):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError('C03_UNSAFE_DIAGNOSTIC_INPUT')
        blob = path.read_bytes()
        bindings[str(path)] = digest(blob)
        return blob

    def read(path):
        return json.loads(body(path))

    def artifact(ref):
        blob = body(native/'runtime/artifacts'/ref['artifact_id'])
        if digest(blob) != ref['sha256']:
            raise ValueError('C03_NATIVE_ARTIFACT_CHANGED')
        return blob

    started = time.monotonic()
    profile = read(ROOT/'contracts/operator/c03_coverage_recovery.json')
    for path in ('tools/inspect_c03_recovery.py', 'src/c03_recovery.py',
                 'src/u02_board/adapter.py', 'src/prepared_land_scene.py',
                 'src/prepared_width_scene.py', 'src/trace_width_clearance.py'):
        body(ROOT/path)
    reference = load_intent(ROOT, profile)
    body(ROOT/profile['execution_permissions']['owner_decision']['path'])
    for ref in profile['references'].values():
        body(ROOT/ref['path'])
    selection = read(native/'U03_SELECTION.json')
    if (selection['source_sha256'] != profile['source_sha256'] or
            selection['crop_sha256'] != profile['crop_sha256'] or
            digest(body(selection['crop_path'])) != profile['crop_sha256']):
        raise ValueError('C03_EXPLICIT_SOURCE_CROP_PROFILE_MISMATCH')
    # The normal source/crop gates remain mandatory in an actual job. This
    # diagnostic also rechecks the retained location/verification bytes.
    for field in ('location', 'verification'):
        if digest(body(selection[field+'_path'])) != selection[field+'_sha256']:
            raise ValueError('C03_RETAINED_CROP_EVIDENCE_CHANGED')
    a, b, c, d = selection['bounds_mm']
    e = selection['edge_uncertainty_mm']
    writable = box(a+e, b+e, c-e, d-e)
    receipt = read(native/'RECEIPT.json')
    binding = json.loads(artifact(receipt['binding_ref']))
    raw = artifact(binding['source_ref'])
    manifest_blob = body(native/'data_board/source_manifest.json')
    if (digest(manifest_blob) != binding['manifest_sha256'] or
            artifact(binding['manifest_ref']) != manifest_blob):
        raise ValueError('C03_QUALIFIED_SOURCE_MANIFEST_CHANGED')
    manifest = json.loads(manifest_blob)
    meta = {r['id']: r for r in manifest['objects']}
    originals = {s: body(native/'data_board/source_wkb'/
                          (r['geometry_sha256']+'.wkb')) for s, r in meta.items()}
    obligations = circle_obligations(raw, manifest, originals,
        reference['T01_DECISIONS'], profile['source_sha256'])
    required = required_rounds(obligations, originals)
    permitted = permitted_rounds(obligations, originals, profile)
    proposed = dict(originals)
    for row in obligations:
        for alias in row.aliases:
            proposed[alias] = to_wkb(permitted[row.source_id])
    candidate = json.loads(artifact(receipt['candidate_ref']))
    retained_scene = json.loads(artifact(candidate['output_scene_ref']))
    current = {r['source_id']: artifact(r['geometry_ref'])
               for r in retained_scene['objects']}
    current_coverage = assess_round_output(obligations, originals, current, writable)
    proposed_coverage = assess_round_output(obligations, originals, proposed, writable)
    proposed_coverage = scope_round_assessment(proposed_coverage, obligations,
                                             originals, proposed, profile)
    rows = manifest['objects']
    shapes = [from_wkb(originals[r['id']]) for r in rows]
    positions = {r['id']: i for i, r in enumerate(rows)}
    sites = [dict(source_id=r.source_id, aliases=list(r.aliases),
                  core=shapes[positions[r.source_id]], center=list(r.center),
                  radius=r.original_radius,
                  indexes=[positions[s] for s in r.aliases]) for r in obligations]
    source_ports = WorkingScene(raw, rows, shapes, sites, CropSettings())
    traces = [(r, g) for r, g in zip(rows, shapes, strict=True)
              if r['kind'] in TRACE_KINDS]
    tree = STRtree([g for _, g in traces])
    policy = dict(hard_gap_mm=.020, quad_segs=128, area_epsilon_mm2=1e-10)
    pairs = []
    for site in sites:
        target = permitted[site['source_id']]
        for index in sorted(map(int, tree.query(target.buffer(.020001)))):
            row, trace = traces[index]
            q = pair_check(site['core'], target, trace,
                source_ports.ports[site['source_id']].get(row['id']), policy)
            pairs.append(dict(site_source_id=site['source_id'],
                              trace_source_id=row['id'], **q))
    trace_check = dict(trace_occurrences=len(traces), affected_pairs=len(pairs),
        failed_pairs=sum(not q['passed'] or not q['original_contact_preserved']
                         for q in pairs), pairs=pairs,
        status='COUNTERFACTUAL_UNCHANGED_PATHS_DIAGNOSTIC_NOT_U02_QUALIFICATION')
    alias_ids = {s for row in obligations for s in row.aliases}
    lands = [dict(id=row.source_id, original=from_wkb(originals[row.source_id]),
                  candidate=permitted[row.source_id], native_source_kind='gr_circle',
                  native_stroke_width_mm=0.) for row in obligations]
    fixed = [dict(id=r['id'], geometry=g,
                  trace_width_mm=r.get('trace_width_mm') or 0.)
             for r, g in zip(rows, shapes, strict=True) if r['id'] not in alias_ids]
    final_surfaces = PreparedLandScene(lands, fixed).check(
        lands, materialize_scene=True, fail_fast=False)
    rectangle_permissions = []
    for definition in reference['T02_DECISIONS']:
        if definition['status'] != 'GROWN':
            continue
        from shapely.affinity import scale
        sid = definition['source_id']
        core = from_wkb(originals[sid])
        sx, sy = definition['factors']
        desired = scale(core, sx, sy, origin=core.centroid)
        rectangle_permissions.append(dict(source_id=sid, key=definition['key'],
            factors=[sx, sy], **permission_record(core, desired, writable)))
    # Hash every consulted operand again at return; source and reference bytes
    # may not drift while a diagnostic is constructing its findings.
    changed = [p for p, h in bindings.items() if digest(Path(p).read_bytes()) != h]
    if changed:
        raise ValueError('C03_DIAGNOSTIC_INPUT_CHANGED:' + str(changed))
    result = dict(status='DIAGNOSTIC_WITH_UNRESOLVED_OBLIGATIONS',
        qualification='NOT_NATIVE_QUALIFICATION; no managed job or export',
        source_sha256=profile['source_sha256'], profile=profile,
        native_root=str(native), writable_bounds_mm=list(writable.bounds),
        independent_circles=[dict(asdict(row), aliases=list(row.aliases),
            source_span=list(row.source_span), center=list(row.center))
            for row in obligations],
        retained_current_coverage=current_coverage,
        proposed_round_coverage=proposed_coverage,
        full_simultaneous_land_surface_check=final_surfaces,
        unchanged_T03_accommodation=trace_check,
        rectangle_permission_records=rectangle_permissions,
        historical_candidate_geometry_used=False,
        elapsed_diagnostic_seconds=time.monotonic()-started,
        input_sha256=bindings, owner='PENDING_USER',
        independent='NOT_RUN: CHANNEL_UNAVAILABLE',
        electrical_manufacturing='NOT_ESTABLISHED')
    output.write_bytes(canonical(result))
    print(json.dumps(dict(output=str(output),
        circles=len(obligations), positive=sum(r.positive for r in obligations),
        round_failures=[dict(key=r['key'], failures=r['failures'])
                        for r in proposed_coverage['records'] if not r['passed']],
        finite_surface_pass=final_surfaces['passed'],
        T03_failed_pairs=trace_check['failed_pairs'],
        rectangle_write_conflicts=[r['key'] for r in rectangle_permissions
                                   if not r['addition_permitted']],
        elapsed_seconds=result['elapsed_diagnostic_seconds'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inspect(args.native_root, args.output)
