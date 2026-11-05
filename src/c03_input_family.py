"""Owner-authorized exact C03 round/contact family; generic U02 is unchanged.

The supported operand is the exact source-bound round intent with the owner's
blocked targets retained. This is not a wider generic source port. All original
ports and raw generic stencil failures remain explicit. The new positive proof
uses the unchanged complete visible-surface kernel and original native widths.
"""
import json
from pathlib import Path

from shapely import STRtree, from_wkb, to_wkb

from src.c03_recovery import (SOURCE_SHA256, CROP_SHA256, bound_bytes,
    circle_obligations, digest, load_intent, permitted_rounds,
    assess_round_output, scope_round_assessment)
from src.crop_balanced_t01 import WorkingScene, CropSettings
from src.prepared_land_scene import PreparedLandScene
from src.stage_abi.store import canonical
from src.trace_width_clearance import TraceWidthContract
from src.u02_board.adapter import pair_check, TRACE_KINDS

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT/'contracts/operator/c03_input_family.json'
FAMILY = 'c03-exact-round-visible-contact/1'


def specification():
    blob = CONTRACT.read_bytes()
    value = json.loads(blob)
    keys = {'schema', 'family', 'source_sha256', 'crop_sha256', 'intent_profile',
            'authorization', 'numeric_policy', 'generic_U02', 'source_routes'}
    if (set(value) != keys or value['schema'] != 'c03-native-input-contact-family/1'
            or value['family'] != FAMILY or value['source_sha256'] != SOURCE_SHA256
            or value['crop_sha256'] != CROP_SHA256 or
            value['numeric_policy'] != dict(construction_gap_mm=.02010,
                actual_hard_floor_mm=.02000, original_contact_buffer_addition_mm=.02002,
                comparison_epsilon_mm=1e-12, quad_segs=128,
                source_generic_area_epsilon_mm2=1e-10)):
        raise ValueError('C03_INPUT_FAMILY_CONTRACT_CHANGED')
    refs = {}
    for key in ('intent_profile', 'authorization'):
        ref = value[key]
        if set(ref) != {'path', 'sha256'}:
            raise ValueError('C03_INPUT_FAMILY_REFERENCE_INVALID')
        refs[key] = json.loads(bound_bytes(ROOT, ref['path'], ref['sha256']))
    if (refs['authorization']['owner_response'] != 'Authorize bounded C03 family'
            or refs['authorization']['source_sha256'] != SOURCE_SHA256
            or refs['authorization']['crop_sha256'] != CROP_SHA256):
        raise ValueError('C03_INPUT_FAMILY_AUTHORIZATION_CHANGED')
    load_intent(ROOT, refs['intent_profile'])
    return value, refs['intent_profile'], digest(blob)


def selected(root):
    """Explicit job opt-in only; source/crop matching never auto-selects it."""
    path = Path(root)/'C03_INPUT_FAMILY.json'
    if path.is_symlink():
        raise ValueError('C03_INPUT_FAMILY_MARKER_UNSAFE')
    if not path.exists():
        return False
    value = json.loads(path.read_bytes())
    spec, _, sha = specification()
    if value != dict(schema='c03-input-family-selected/1', contract=spec,
                     contract_sha256=sha):
        raise ValueError('C03_INPUT_FAMILY_SELECTION_CHANGED')
    job = json.loads((Path(root).parent/'job.json').read_bytes())
    if (job['inputs']['kicad']['sha256'] != SOURCE_SHA256 or
            (job.get('crop') or {}).get('sha256') != CROP_SHA256):
        raise ValueError('C03_INPUT_FAMILY_JOB_SOURCE_OR_CROP_CHANGED')
    return True


def visible_model(rows, original, current, sites):
    """The existing full model; no construction/port/gap parameter changes."""
    aliases = {s for site in sites for s in site['aliases']}
    lands = [dict(id=s['source_id'], original=original[s['source_id']],
        candidate=current[s['source_id']], native_source_kind='gr_circle',
        native_stroke_width_mm=0.) for s in sites]
    fixed = [dict(id=r['id'], geometry=original[r['id']],
                  trace_width_mm=r['trace_width_mm'] or 0.)
             for r in rows if r['id'] not in aliases]
    return PreparedLandScene(lands, fixed, TraceWidthContract()).check(
        lands, materialize_scene=True, fail_fast=False)


def retention_proof(raw, manifest, original_blobs, current_blobs, sites, writable):
    """Complete source/contact reconstruction, never a generic predicate waiver."""
    _, profile, contract_sha = specification()
    def signature():
        return digest(canonical(dict(source_sha256=digest(raw), manifest=manifest,
            original={s:digest(b) for s,b in original_blobs.items()},
            current={s:digest(b) for s,b in current_blobs.items()},
            sites=[dict(source_id=s['source_id'], aliases=list(s['aliases']),
                indexes=list(s['indexes']), center=list(s['center']), radius=s['radius'],
                core_sha256=digest(to_wkb(s['core']))) for s in sites])))
    entry = signature()
    if set(original_blobs) != set(current_blobs):
        raise ValueError('C03_COMPLETE_PREDECESSOR_PARTITION_REQUIRED')
    definitions = load_intent(ROOT, profile)['T01_DECISIONS']
    obligations = circle_obligations(raw, manifest, original_blobs,
                                    definitions, SOURCE_SHA256)
    permitted = permitted_rounds(obligations, original_blobs, profile)
    expected = dict(original_blobs)
    for row in obligations:
        for alias in row.aliases:
            expected[alias] = to_wkb(permitted[row.source_id])
    if expected != current_blobs:
        raise ValueError('C03_EXACT_ROUND_INPUT_REQUIRED')
    coverage = scope_round_assessment(
        assess_round_output(obligations, original_blobs, current_blobs, writable),
        obligations, original_blobs, current_blobs, profile)
    if not coverage['scoped_execution_pass']:
        raise ValueError('C03_SCOPED_ROUND_INPUT_COVERAGE_FAILED')
    byid = {s['source_id']:s for s in sites}
    if (len(byid) != len(sites) or set(byid) != set(permitted) or
            any(tuple(sorted(byid[r.source_id]['aliases'])) != r.aliases
                for r in obligations)):
        raise ValueError('C03_COMPLETE_CONTACT_SITE_SET_REQUIRED')
    positions = {r['id']:i for i,r in enumerate(manifest['objects'])}
    for row in obligations:
        site = byid[row.source_id]
        if (tuple(site['center']) != row.center or site['radius'] != row.original_radius or
                sorted(site['indexes']) != sorted(positions[s] for s in row.aliases) or
                digest(to_wkb(site['core'])) != row.source_geometry_sha256):
            raise ValueError('C03_NATIVE_CONTACT_SITE_PARAMETERS_CHANGED')
    from src.source_locators import locate
    locations = {s.identity:s for s in locate(raw)}
    if any(r['id'] not in locations or locations[r['id']].head != r['kind']
           for r in manifest['objects']):
        raise ValueError('C03_NATIVE_OCCURRENCE_KIND_CHANGED')
    from src.u03_board.source import native_rows
    native_rows(raw, manifest['objects'])
    decoded = {}

    def shape(blob):
        sha = digest(blob)
        if sha not in decoded:
            decoded[sha] = from_wkb(blob)
        return decoded[sha]

    original = {s:shape(b) for s,b in original_blobs.items()}
    current = {s:shape(b) for s,b in current_blobs.items()}
    rows = manifest['objects']
    model = visible_model(rows, original, current, sites)
    if not model['passed'] or not model['evaluation_complete']:
        raise ValueError('C03_FULL_VISIBLE_CONTACT_MODEL_FAILED')
    land_checks = {r['source_id']:r for r in model['lands']}
    ws = WorkingScene(raw, rows, [original[r['id']] for r in rows], sites, CropSettings())
    traces = [r for r in rows if r['kind'] in TRACE_KINDS]
    tree = STRtree([original[r['id']] for r in traces])
    records = {}
    for row in traces:
        sid = row['id']
        if current_blobs[sid] != original_blobs[sid] or row['trace_width_mm'] <= 0:
            raise ValueError('C03_NATIVE_ROUTE_OR_WIDTH_CHANGED')
        start,end = row['source_span']
        records[sid] = dict(source_id=sid, native_kind=row['kind'],
            source_span=[start,end], native_bytes_sha256=digest(raw[start:end]),
            geometry_sha256=row['geometry_sha256'],
            original_width_mm=row['trace_width_mm'], disposition='RETAIN_ORIGINAL', pairs=[])
    policy = dict(hard_gap_mm=.020, quad_segs=128, area_epsilon_mm2=1e-10)
    raw_failures = []
    for site in sites:
        sid = site['source_id']
        target = current[sid]
        for index in sorted(map(int, tree.query(target.buffer(.020001)))):
            trace = traces[index]
            tid = trace['id']
            generic = pair_check(original[sid], target, original[tid],
                                 ws.ports[sid].get(tid), policy)
            if not generic['passed'] or not generic['original_contact_preserved']:
                raw_failures.append(dict(site_source_id=sid, trace_source_id=tid, **generic))
            # The new family uses the existing complete visible-surface proof,
            # not an enlarged generic port or an exempt physical component.
            records[tid]['pairs'].append(dict(site_source_id=sid, family=FAMILY,
                passed=land_checks[sid]['passed'] and generic['original_contact_preserved'],
                original_contact_preserved=generic['original_contact_preserved'],
                full_land_check_sha256=digest(canonical(land_checks[sid])),
                generic_source_port_predicate=generic,
                generic_source_port_disposition='RETAINED_RESULT; not a C03-family verdict'))
    if signature() != entry:
        raise ValueError('C03_INPUT_CONTEXT_MUTATED')
    return dict(family=FAMILY, contract_sha256=contract_sha,
        trace_records=list(records.values()), source_occurrences=len(rows),
        exact_route_retention=True, original_widths_retained=True,
        ports={sid:{other:to_wkb(g,byte_order=1).hex() for other,g in ports.items()}
               for sid,ports in ws.ports.items()},
        complete_visible_surface=model, original_obligations=coverage,
        retained_generic_source_port_failures=raw_failures,
        scope='Exact owner-authorized C03 round inputs only; no movement/net/manufacturing claim')
