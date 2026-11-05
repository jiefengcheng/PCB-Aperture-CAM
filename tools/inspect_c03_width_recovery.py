#!/usr/bin/env python3
"""Complete-parent/group recovery diagnostic; no native job or write authority."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shapely import from_wkb, to_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.c03_recovery import (circle_obligations, digest, load_intent,
    permitted_rounds, width_membership_obligations)
from src.native_inventory import ERROR_MM
from src.prepared_width_scene import PreparedWidthScene
from src.source_offset_width import construct_source_offset_width
from src.stage_abi.store import canonical
from src.u04_board.roles import qualify
from tools.pcb_workspace import configure, WORK


def inspect(native, output):
    configure()
    native, output = Path(native).absolute(), Path(output).absolute()
    if (not native.is_relative_to(WORK) or not output.is_relative_to(WORK)
            or output.exists()):
        raise ValueError('C03_FRESH_EXTERNAL_DIAGNOSTIC_REQUIRED')
    bindings = {}

    def body(path):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError('C03_UNSAFE_INPUT')
        value = path.read_bytes()
        bindings[str(path)] = digest(value)
        return value

    def read(path):
        return json.loads(body(path))

    def artifact(ref):
        value = body(native/'runtime/artifacts'/ref['artifact_id'])
        if digest(value) != ref['sha256']:
            raise ValueError('C03_NATIVE_ARTIFACT_CHANGED')
        return value

    started = time.monotonic()
    profile = read(ROOT/'contracts/operator/c03_coverage_recovery.json')
    for path in ('tools/inspect_c03_width_recovery.py', 'src/c03_recovery.py',
                 'src/u04_board/roles.py', 'src/u03_board/source.py',
                 'src/source_offset_width.py', 'src/prepared_width_scene.py',
                 'src/trace_width_clearance.py'):
        body(ROOT/path)
    references = load_intent(ROOT, profile)
    body(ROOT/profile['execution_permissions']['owner_decision']['path'])
    for ref in profile['references'].values():
        body(ROOT/ref['path'])
    receipt = read(native/'RECEIPT.json')
    binding = json.loads(artifact(receipt['binding_ref']))
    raw = artifact(binding['source_ref'])
    manifest_blob = body(native/'data_board/source_manifest.json')
    if (digest(manifest_blob) != binding['manifest_sha256'] or
            artifact(binding['manifest_ref']) != manifest_blob):
        raise ValueError('C03_QUALIFIED_SOURCE_MANIFEST_CHANGED')
    manifest = json.loads(manifest_blob)
    meta = {r['id']: r for r in manifest['objects']}
    original = {s: body(native/'data_board/source_wkb'/
                       (r['geometry_sha256']+'.wkb')) for s, r in meta.items()}
    obligations = circle_obligations(raw, manifest, original,
        references['T01_DECISIONS'], profile['source_sha256'])
    rounds = permitted_rounds(obligations, original, profile)
    current = dict(original)
    for row in obligations:
        for alias in row.aliases:
            current[alias] = to_wkb(rounds[row.source_id])
    selection = read(native/'U03_SELECTION.json')
    if selection['source_sha256'] != profile['source_sha256'] or selection['crop_sha256'] != profile['crop_sha256']:
        raise ValueError('C03_SOURCE_CROP_INTENT_MISMATCH')
    a, b, c, d = selection['bounds_mm']
    e = selection['edge_uncertainty_mm']
    writable = box(a+e, b+e, c-e, d-e)
    # Freshly rederive all complete paths and source-qualified relationships on
    # restored T01 geometry. This is a counterfactual: T03 still has unresolved
    # raw predicate failures, and no managed stage can advance from this report.
    report = qualify(raw, manifest['objects'], original, current, selection=selection)
    print(json.dumps(dict(phase='COMPLETE_SOURCE_ADMISSION_REDERIVED',
                          paths=len(report['paths']),
                          admitted_paths=len(report['admitted_paths']))), flush=True)
    projection = width_membership_obligations(raw, manifest, original, report,
                                            references['T04_CONSTRUCTION'])
    paths = {r['path']['path_id']: r for r in report['paths'] if r.get('path')}
    by_source = {s: from_wkb(blob) for s, blob in current.items()}
    predecessor = unary_union([by_source[s] for s in sorted(by_source)])
    traces, envelopes, used = [], [], set()
    groups = {}
    for gid, group in projection['groups'].items():
        factor = group['minimum_requested_uniform_factor']
        nominal_parts, core_parts, max_cap_blockers = [], [], []
        admitted = (not group['reviewed_fixed_source_ids'] and
                    all(paths[p]['disposition']=='ADMIT_COMPLETE_NATIVE_ROUTE'
                        for p in group['parent_paths']))
        for pid in group['parent_paths']:
            path = paths[pid]['path']
            chain = dict(component_id=pid, source_ids=path['source_ids'],
                         source_sha256=profile['source_sha256'])
            record, _, _, core, nominal, envelope = construct_source_offset_width(
                raw, chain, meta, original, factor)
            for sid in path['source_ids']:
                g = by_source[sid]
                w = meta[sid]['trace_width_mm']
                x0, y0, x1, y1 = g.bounds
                if not writable.covers(box(x0-.25*w-ERROR_MM, y0-.25*w-ERROR_MM,
                                           x1+.25*w+ERROR_MM, y1+.25*w+ERROR_MM)):
                    max_cap_blockers.append(sid)
            nominal_parts.append(nominal)
            core_parts.append(core)
            if admitted and pid not in used:
                used.add(pid)
                base = dict(id='route:'+pid, original=core,
                            verified_original_width_mm=record['verified_original_width_mm'])
                traces.append(dict(base, candidate=nominal))
                envelopes.append(dict(base, candidate=envelope))
        nominal = unary_union(nominal_parts)
        core = unary_union(core_parts)
        groups[gid] = dict(group,
            maximum_envelope_crop_blocker_source_ids=sorted(set(max_cap_blockers)),
            required_nominal_sha256=digest(to_wkb(nominal)),
            required_group_owned_addition_outside_mm2=nominal.difference(core).difference(writable).area,
            required_group_effective_addition_outside_mm2=nominal.difference(predecessor).difference(writable).area,
            current_admissions={p: paths[p]['disposition'] for p in group['parent_paths']},
            finite_check_disposition='RUN_ON_COMPLETE_PERMITTED_GROUP' if admitted else
                                     'NOT_RUN_PERMISSION_BLOCKED',
            rights='UNRESOLVED where any fixed contributor or crop blocker exists; no grant')
    membership_output = output.with_name(output.stem+'_MEMBERSHIP.json')
    if membership_output.exists():
        raise ValueError('C03_FRESH_MEMBERSHIP_EVIDENCE_REQUIRED')
    membership_output.write_bytes(canonical(dict(projection=projection,
        complete_group_findings=groups, native_admission_report=report,
        candidate_geometry='NOT_CONSTRUCTED_FOR_EXPORT',
        finite_check_status='PENDING_FOR_PERMITTED_GROUPS; BLOCKED_GROUPS_NOT_RUN')))
    print(json.dumps(dict(phase='ALL_MEMBERSHIP_AND_PERMISSION_FINDINGS_RETAINED',
                          groups=len(groups), permitted_complete_parents=len(used))), flush=True)
    native_members = {s for p in used for s in paths[p]['path']['source_ids']}
    fixed = [dict(id=s, geometry=by_source[s], trace_width_mm=meta[s]['trace_width_mm'] or 0.)
             for s in sorted(set(meta)-native_members)]
    if traces:
        checker = PreparedWidthScene(traces, fixed)
        nominal_check = checker.check(traces, materialize_scene=True, fail_fast=False)
        envelope_check = checker.check(envelopes, materialize_scene=True, fail_fast=False)
    else:
        nominal_check = envelope_check = dict(status='NOT_RUN_NO_PERMITTED_COMPLETE_GROUPS')
    changed = [p for p, h in bindings.items() if digest(Path(p).read_bytes()) != h]
    if changed:
        raise ValueError('C03_WIDTH_DIAGNOSTIC_INPUT_CHANGED:' + str(changed))
    result = dict(status='COUNTERFACTUAL_WITH_PERMISSION_AND_PREDECESSOR_GAPS',
        qualification='NOT_NATIVE_QUALIFICATION; neither T03 movement nor width rights granted',
        source_sha256=profile['source_sha256'], projection=projection,
        complete_group_findings=groups, restored_T01_admission_report=report,
        nominal_simultaneous_check=nominal_check,
        envelope_simultaneous_check=envelope_check,
        elapsed_diagnostic_seconds=time.monotonic()-started,
        input_sha256=bindings, owner='PENDING_USER',
        independent='NOT_RUN: CHANNEL_UNAVAILABLE', electrical_manufacturing='NOT_ESTABLISHED')
    output.write_bytes(canonical(result))
    print(json.dumps(dict(output=str(output), references=len(projection['records']),
        reference_positive=projection['original_positive'], groups=len(groups),
        complete_counterfactual_parents=len(used),
        groups_with_fixed_contributors=sum(bool(g['reviewed_fixed_source_ids']) for g in groups.values()),
        groups_with_max_envelope_crop_blockers=sum(bool(g['maximum_envelope_crop_blocker_source_ids']) for g in groups.values()),
        groups_with_actual_additions_outside_write=sum(g['required_group_effective_addition_outside_mm2']>1e-12 for g in groups.values()),
        nominal_pass=nominal_check.get('passed'), envelope_pass=envelope_check.get('passed'),
        elapsed_seconds=result['elapsed_diagnostic_seconds'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inspect(args.native_root, args.output)
