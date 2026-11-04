"""Representation faults must not disappear behind a successful selected subset."""
import copy

import pytest

from tools.c03_catalogue_stage_a import ReplayStore, validate_projection


def model():
    revision = 'a' * 64
    ids = [f'{revision}:bytes:{i}:{i+10}' for i in (10, 20, 30)]
    refs = [dict(artifact_id='geometry:' + str(i) * 64, sha256=str(i) * 64) for i in (1, 2, 3)]
    rows = [dict(id=s, kind='segment' if i == 0 else 'gr_circle',
                 source_sha256=revision, source_span=[10 + i * 10, 20 + i * 10],
                 geometry_sha256=refs[i]['sha256'], coverage='GEOMETRY_AVAILABLE')
            for i, s in enumerate(ids)]
    objects = [dict(id=s, kind='fixed_source' if i == 0 else 'circle',
                    native_source_ids=[s], source_members=[s], aliases=[s],
                    original_ref=refs[i], geometry_ref=refs[i], qualified_land=i != 0,
                    preserve_existing=True, original_contact_support_ids=[])
               for i, s in enumerate(ids)]
    objects.append(dict(id='local', kind='trace', native_source_ids=[], source_members=[ids[0]],
                        aliases=[], original_ref=refs[0], geometry_ref=refs[0], qualified_land=False,
                        preserve_existing=True, original_contact_support_ids=[]))
    attachments = [dict(id='contact:' + str(i), cluster_id='local', land_id=s,
                        required_reference=True, status='TREATED_VERIFIED',
                        actual_export_check={'passed': True}) for i, s in enumerate(ids[1:])]
    return dict(source_sha256=revision, source_occurrences=rows, objects=objects,
                complete_paths=[dict(id='complete', source_ids=[ids[0]],
                                     T04_disposition='KEEP_CROP_GROUP_BOUNDARY')],
                width_groups=[dict(id='group', members=['complete'])],
                clusters=[dict(id='local', source_ids=[ids[0]], parent_path_id='complete',
                               complete_parent_source_ids=[ids[0]], land_ids=ids[1:],
                               attachment_ids=[a['id'] for a in attachments], reference_status='GROWN',
                               native_width_writable=False, local_additive_evaluation=True)],
                attachments=attachments, context_contacts=[])


def test_kept_complete_path_can_have_independent_local_treatment():
    counts = validate_projection(model())
    assert counts['t04_admitted_paths'] == 0
    assert counts['required_reference_attachments'] == 2


@pytest.mark.parametrize(('mutation', 'reason'), [
    (lambda m: m['source_occurrences'].append(copy.deepcopy(m['source_occurrences'][0])),
     'DUPLICATE_SOURCE_OCCURRENCE'),
    (lambda m: m['objects'][0].update(native_source_ids=[]), 'SOURCE_PARTITION'),
    (lambda m: m['objects'][-1].update(native_source_ids=[m['source_occurrences'][0]['id']]),
     'SOURCE_PARTITION'),
    (lambda m: m['clusters'][0].update(parent_path_id='missing'), 'CLUSTER_PARENT_UNRESOLVED'),
    (lambda m: m['clusters'][0].update(complete_parent_source_ids=[]), 'COMPLETE_PARENT_MEMBERSHIP'),
    (lambda m: m['clusters'][0].update(land_ids=m['clusters'][0]['land_ids'][:1]),
     'COVERED_OR_DECLARED_LAND_OMITTED'),
    (lambda m: m['clusters'][0].update(attachment_ids=['contact:0']), 'ATTACHMENT_MEMBERSHIP'),
    (lambda m: m['clusters'][0].update(native_width_writable=True), 'T04_T05_PERMISSION_COUPLING'),
    (lambda m: m['attachments'][0]['actual_export_check'].update(passed=False),
     'REQUIRED_ATTACHMENT_EXTENT_NOT_VERIFIED'),
    (lambda m: m['objects'][1].update(aliases=['missing']), 'ALIAS_UNRESOLVED'),
    (lambda m: m['source_occurrences'][0].update(source_sha256='b' * 64),
     'SOURCE_OCCURRENCE_REVISION_OR_SPAN'),
    (lambda m: m['width_groups'][0].update(members=['missing']), 'WIDTH_GROUP_PATH_UNRESOLVED'),
])
def test_representation_corruptions_reject(mutation, reason):
    value = model()
    mutation(value)
    with pytest.raises(ValueError, match=reason):
        validate_projection(value)


def test_generator_cannot_reduce_its_own_required_denominator():
    value = model()
    expected = validate_projection(value)
    value['attachments'].pop()
    value['clusters'][0]['attachment_ids'].pop()
    value['clusters'][0]['land_ids'].pop()
    with pytest.raises(ValueError, match='INDEPENDENT_COVERAGE_DENOMINATOR_CHANGED'):
        validate_projection(value, expected)


def test_diagnostic_store_cannot_write_or_hide_corruption_in_retained_layers(tmp_path):
    from src.stage_abi.store import ArtifactStore
    retained = ArtifactStore(tmp_path / 'retained')
    ref = retained.put('geometry', b'retained bytes')
    before = {p.name: p.read_bytes() for p in (retained.root / 'artifacts').iterdir()}
    replay = ReplayStore(tmp_path / 'new', [retained.root])
    assert replay.get(ref) == b'retained bytes'
    replay.put('geometry', b'diagnostic bytes')
    assert before == {p.name: p.read_bytes() for p in (retained.root / 'artifacts').iterdir()}
    (retained.root / 'artifacts' / ref['artifact_id']).write_bytes(b'changed')
    with pytest.raises(ValueError) as error:
        replay.verify_reads()
    assert error.value.code == 'ARTIFACT_CORRUPTED'
