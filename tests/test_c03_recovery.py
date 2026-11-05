"""Original obligations survive narrowed plans, clipped growth and tampering."""
import copy
import json
import math
from pathlib import Path

import pytest
from shapely import from_wkb, to_wkb
from shapely.geometry import box

from src.c03_recovery import (assess_round_output, bound_bytes,
    circle_obligations, digest, load_intent, permission_record,
    require_complete, required_rounds)
from src.native_inventory import inventory


def native_case(alias=False):
    circle = '(gr_circle (center 0 0) (end .1 0) (stroke (width 0) (type default)) (fill yes) (layer "F.Cu"))'
    raw = ('(kicad_pcb (version 20241229) (layers (0 "F.Cu" signal)) ' +
           circle + (' ' + circle if alias else '') +
           ' (gr_poly (pts (xy 3 3) (xy 4 3) (xy 4 4) (xy 3 4)) '
           '(stroke (width 0) (type default)) (fill yes) (layer "F.Cu")))').encode()
    inv = inventory(raw)
    rows = inv['objects']
    manifest = dict(source_sha256=digest(raw), objects=rows)
    blobs = {r['id']: inv['payloads'][r['geometry_sha256']] for r in rows}
    ids = sorted(r['id'] for r in rows if r['kind'] == 'gr_circle')
    definitions = [dict(source_id=ids[0], aliases=ids, key='native-circle',
                        original_radius_mm=.1, selected_diameter_mm=.3,
                        positive_growth=True)]
    obligations = circle_obligations(raw, manifest, blobs, definitions, digest(raw))
    actual = dict(blobs)
    for sid in ids:
        actual[sid] = to_wkb(required_rounds(obligations, blobs)[ids[0]])
    return raw, manifest, blobs, definitions, obligations, actual


def test_native_round_obligation_is_satisfied_without_historical_copper():
    _, _, original, _, obligations, actual = native_case(alias=True)
    report = assess_round_output(obligations, original, actual, box(-1, -1, 1, 1))
    assert report['passed'] and report['required_positive'] == 1
    require_complete(report)


def test_omission_from_generator_and_result_does_not_remove_independent_demand():
    _, _, original, _, obligations, _ = native_case()
    # A narrowed plan can reconstruct its unchanged result exactly; independent
    # demand still includes this original-positive source.
    report = assess_round_output(obligations, original, dict(original), box(-1, -1, 1, 1))
    assert not report['passed']
    assert 'REQUIRED_ROUND_EXTENT_MISSING' in report['records'][0]['failures']
    with pytest.raises(ValueError, match='COVERAGE_NOT_FULFILLED'):
        require_complete(report)


def test_irrelevant_extra_copper_cannot_compensate_for_missing_target():
    _, _, original, _, obligations, _ = native_case()
    actual = dict(original)
    fixed = next(s for s in original if s != obligations[0].source_id)
    actual[fixed] = to_wkb(box(2, 2, 5, 5))
    report = assess_round_output(obligations, original, actual, box(-10, -10, 10, 10))
    assert not report['passed'] and report['protected_source_changes'] == [fixed]
    assert report['records'][0]['missing_required_extent_mm2'] > .01


def test_positive_but_clipped_companion_is_not_full_round_recovery():
    _, _, original, _, obligations, actual = native_case()
    sid = obligations[0].source_id
    actual[sid] = to_wkb(from_wkb(actual[sid]).intersection(box(-.2, -.2, .12, .2)))
    assert from_wkb(actual[sid]).area > from_wkb(original[sid]).area
    failures = assess_round_output(obligations, original, actual, box(-1, -1, 1, 1))['records'][0]['failures']
    assert {'REQUIRED_ROUND_EXTENT_MISSING', 'FULL_ROUND_SHAPE_REQUIRED'} <= set(failures)


def test_output_alias_or_source_deletion_rejects():
    _, _, original, _, obligations, actual = native_case(alias=True)
    other = obligations[0].aliases[1]
    actual[other] = original[other]
    assert 'ALIAS_OUTPUT_CONFLICT' in assess_round_output(obligations, original, actual, box(-1, -1, 1, 1))['records'][0]['failures']
    del actual[other]
    with pytest.raises(ValueError, match='SOURCE_PARTITION_REQUIRED'):
        assess_round_output(obligations, original, actual, box(-1, -1, 1, 1))


def test_correct_extent_cannot_grant_its_own_write_permission():
    _, _, original, _, obligations, actual = native_case()
    report = assess_round_output(obligations, original, actual, box(-.11, -.2, .2, .2))
    assert not report['passed']
    assert 'ADDITION_OUTSIDE_WRITE_PERMISSION' in report['records'][0]['failures']
    assert report['records'][0]['permission']['required_addition_outside_mm2'] > 0


def test_preserving_existing_outside_copper_is_not_new_write_authority():
    record = permission_record(box(-1, 0, 1, 1), box(-1, 0, 2, 1), box(1, 0, 2, 1))
    assert record['addition_permitted'] and not record['whole_extent_inside']
    assert record['original_core_outside_mm2'] == 2


@pytest.mark.parametrize('fault', ['source', 'geometry', 'alias', 'radius', 'class'])
def test_native_and_semantic_parameter_mutations_reject(fault):
    raw, manifest, blobs, definitions, _, _ = native_case(alias=True)
    definitions = copy.deepcopy(definitions)
    if fault == 'source':
        raw += b' '
    elif fault == 'geometry':
        sid = definitions[0]['source_id']
        blobs[sid] = to_wkb(box(0, 0, 1, 1))
    elif fault == 'alias':
        definitions[0]['aliases'].pop()
    elif fault == 'radius':
        definitions[0]['original_radius_mm'] = .11
    else:
        definitions[0]['selected_diameter_mm'] = math.nextafter(3 * .1, math.inf)
    with pytest.raises(ValueError):
        circle_obligations(raw, manifest, blobs, definitions, manifest['source_sha256'])


def test_actual_reference_bytes_are_rehashed_and_symlink_rejects(tmp_path):
    p = tmp_path/'reference.json'
    p.write_bytes(b'[]')
    expected = digest(p.read_bytes())
    assert bound_bytes(tmp_path, p.name, expected) == b'[]'
    p.write_bytes(b'[1]')
    with pytest.raises(ValueError, match='BYTES_CHANGED'):
        bound_bytes(tmp_path, p.name, expected)
    q = tmp_path/'link.json'
    q.symlink_to(p)
    with pytest.raises(ValueError, match='SYMLINK'):
        bound_bytes(tmp_path, q.name, digest(p.read_bytes()))


def test_reference_profile_cannot_broaden_to_another_source_or_crop():
    root = Path(__file__).resolve().parents[1]
    profile = json.loads((root/'contracts/operator/c03_coverage_recovery.json').read_text())
    for field in ('source_sha256', 'crop_sha256'):
        bad = copy.deepcopy(profile)
        bad[field] = '0'*64
        with pytest.raises(ValueError, match='PROFILE_INVALID'):
            load_intent(root, bad)


def test_width_obligation_retains_transitive_complete_group_and_fixed_member():
    from tests.test_u03_board import source_case
    from src.u03_board.source import qualify
    from src.c03_recovery import width_membership_obligations
    raw, rows, blobs = source_case([
        f'(segment (start 0 {y}) (end 1 {y}) (width .1) (layer "F.Cu"))'
        for y in (0, .3, .6)])
    manifest = dict(source_sha256=digest(raw), objects=rows)
    report = qualify(raw, rows, blobs, blobs)
    report['reviewed_source_roles'] = dict(protected={rows[1]['id']: {}})
    definition = dict(component_id='local', complete_source_ids=[rows[0]['id']], factor=1.5)
    q = width_membership_obligations(raw, manifest, blobs, report, [definition])
    group = next(iter(q['groups'].values()))
    assert len(group['parent_paths']) == 3
    assert group['reviewed_fixed_source_ids'] == [rows[1]['id']]
    assert not group['permissions_granted'] and q['original_positive'] == 1
    bad = copy.deepcopy(report)
    bad['paths'].pop()
    with pytest.raises(ValueError, match='PARTITION_INCOMPLETE'):
        width_membership_obligations(raw, manifest, blobs, bad, [definition])
    with pytest.raises(ValueError, match='OBLIGATION_DUPLICATED'):
        width_membership_obligations(raw, manifest, blobs, report, [definition, definition])


def test_width_group_projection_does_not_allow_unsafe_scale_or_changed_source():
    from tests.test_u03_board import source_case
    from src.u03_board.source import qualify
    from src.c03_recovery import width_membership_obligations
    raw, rows, blobs = source_case([
        '(segment (start 0 0) (end 1 0) (width .1) (layer "F.Cu"))'])
    manifest = dict(source_sha256=digest(raw), objects=rows)
    report = qualify(raw, rows, blobs, blobs)
    definition = dict(component_id='local', complete_source_ids=[rows[0]['id']], factor=1.6)
    with pytest.raises(ValueError, match='WIDTH_INTENT_INVALID'):
        width_membership_obligations(raw, manifest, blobs, report, [definition])
    with pytest.raises(ValueError, match='SOURCE_BINDING_CHANGED'):
        width_membership_obligations(raw+b' ', manifest, blobs, report, [definition])


def test_owner_block_is_retained_and_never_counts_as_original_coverage():
    from src.c03_recovery import permitted_rounds, scope_round_assessment
    _, _, original, _, obligations, actual = native_case()
    profile = dict(execution_permissions=dict(blocked_original_obligations=['T01:native-circle']))
    permitted = permitted_rounds(obligations, original, profile)
    assert permitted[obligations[0].source_id].equals(from_wkb(original[obligations[0].source_id]))
    scoped = scope_round_assessment(assess_round_output(obligations, original, original, box(-1,-1,1,1)), obligations, original, original, profile)
    assert scoped['scoped_execution_pass']
    assert not scoped['original_full_coverage_pass']
    assert scoped['blocked_original_positive'] == 1
    # The owner said keep the target intact, not silently grow it anyway.
    illegal = scope_round_assessment(assess_round_output(obligations, original, actual, box(-1,-1,1,1)), obligations, original, actual, profile)
    assert not illegal['scoped_execution_pass']


def rectangle_case():
    from src.c03_recovery_rectangles import rectangle_intents
    raw, manifest, original, _, _, _ = native_case()
    sid = next(r['id'] for r in manifest['objects'] if r['kind'] == 'gr_poly')
    definitions = [dict(source_id=sid, key='native-rectangle', status='GROWN', factors=[1.25,1.25])]
    intents = rectangle_intents(raw, manifest, original, definitions)
    return raw, manifest, original, definitions, intents


def test_whole_rectangle_extent_and_cap_are_independent_of_admission():
    from shapely.affinity import scale
    from src.c03_recovery_rectangles import assess_rectangles, rectangle_intents
    raw, manifest, original, definitions, intents = rectangle_case()
    sid = intents[0]['source_id']
    core = intents[0]['original_geometry']
    window = box(-10,-10,10,10)
    assert assess_rectangles(intents, {sid:intents[0]['required_geometry']}, window)['passed']
    missing = assess_rectangles(intents, {}, window)
    assert missing['records'][0]['failures'] == ['ORIGINAL_RECTANGLE_TARGET_MISSING']
    tiny = assess_rectangles(intents, {sid:scale(core,1.01,1.01)}, window)
    assert 'REQUIRED_RECTANGLE_EXTENT_MISSING' in tiny['records'][0]['failures']
    oversized = assess_rectangles(intents, {sid:scale(core,1.3,1.3)}, window)
    assert 'ORIGINAL_RECTANGLE_1P25_CAP_EXCEEDED' in oversized['records'][0]['failures']
    definitions[0]['factors'] = [1.26,1.25]
    with pytest.raises(ValueError, match='CAP_REQUIRED'):
        rectangle_intents(raw, manifest, original, definitions)


def test_rectangle_boundary_and_native_identity_cannot_be_rewritten():
    from src.c03_recovery_rectangles import assess_rectangles, rectangle_intents
    raw, manifest, original, definitions, intents = rectangle_case()
    sid = intents[0]['source_id']
    report = assess_rectangles(intents,{sid:intents[0]['required_geometry']},box(3,3,4,4))
    assert 'RECTANGLE_ADDITION_OUTSIDE_WRITE_PERMISSION' in report['records'][0]['failures']
    with pytest.raises(ValueError,match='SOURCE_BINDING_CHANGED'):
        rectangle_intents(raw+b' ',manifest,original,definitions)


def test_independent_inclusive_member_set_survives_narrowed_result_and_extra_fill():
    from src.c03_recovery_rectangles import inclusive_intents, assess_inclusive
    original = {'a':to_wkb(box(0,0,1,1)), 'b':to_wkb(box(1.1,0,2.1,1)),
                'support':to_wkb(box(.9,.4,1.2,.6))}
    definitions = [dict(status='MERGED',rectangle_members=['a','b'],
        support_trace_source_ids=['support'],inclusive_bounds_mm=[0,0,2.1,1])]
    obligations = inclusive_intents(definitions, [], original)
    assert assess_inclusive(obligations, {('a','b'):box(0,0,2.1,1)},box(-1,-1,3,2))['passed']
    narrowed = assess_inclusive(obligations, {('irrelevant',):box(10,10,12,12)},box(-1,-1,3,2))
    assert not narrowed['passed']
    assert narrowed['records'][0]['failures'] == ['REQUIRED_INCLUSIVE_MEMBER_SET_MISSING']
    definitions[0]['support_trace_source_ids']=['missing']
    with pytest.raises(ValueError,match='ORIGINAL_MEMBERS_REQUIRED'):
        inclusive_intents(definitions,[],original)
