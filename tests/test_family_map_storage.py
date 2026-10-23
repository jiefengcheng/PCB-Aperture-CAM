import json
import os
from pathlib import Path
import tempfile
import unittest

from src.ingestion_files import sha, write_json
from src.revision_catalog import CatalogError, RevisionCatalog, canonical, digest
from src.family_map_storage import (
    _validate_recognition_reference_closure, publish, verify_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture(root):
    store = root / 'base' / 'store'
    source = b'(kicad_pcb (fixture ORG only))\n'
    source_hash = digest(source)
    geom = b'fixture-geometry-payload'
    row = {
        'id': f'{source_hash}:bytes:0:{len(source)}',
        'source_sha256': source_hash,
        'source_span': [0, len(source)],
        'parent_id': None,
        'native_id': 'org-source-object-1',
        'kind': 'gr_circle',
        'layers': ['F.Cu'],
        'geometry_sha256': digest(geom),
        'bounds_mm': [0.0, 0.0, 1.0, 1.0],
        'coverage': 'GEOMETRY_AVAILABLE',
    }
    with RevisionCatalog(store) as catalog:
        catalog.put_payload(geom)
        revision = catalog.import_revision(source, [row], [], {'kind': 'fixture-org-source/1'})
    return store, revision, source_hash, row['id']


def input_spec(revision, source_hash):
    return {
        'org_revision': revision,
        'org_source_sha256': source_hash,
        'geometry_materialization_sha256': digest(b'fixture-geometry-materialization'),
        'parser_version': 'native-inventory-test/1',
        'implementation_sha256': digest(b'fixture-implementation'),
        'config': {'seed_types': ['gr_circle'], 'scope': 'fixture'},
        'predicate_versions': {'contact': 'fixture-contact/1'},
    }


def records(revision, source_object_id):
    keys = [digest(canonical(['fixture-member', i])) for i in range(3)]
    family_key = digest(canonical(['fixture-family', keys]))
    members = [
        {'entity_type': 'candidate_member', 'member_key': key,
         'source_refs': [{'source_revision': revision, 'object_id': source_object_id,
                          'role': 'local_copper_candidate'}],
         'candidate_family_keys': [],
         'geometry': {'basis': 'source-object', 'units': 'mm'}}
        for key in keys
    ]
    for member in members:
        member['candidate_family_keys'] = [family_key]
    return members + [
        {'entity_type': 'family', 'family_key': family_key, 'source_refs': [],
         'members': keys,
         'support_pairs': [
             {'member_keys': sorted([keys[0], keys[1]]), 'center_delta_mm': [1.0, 0.0]},
             {'member_keys': sorted([keys[1], keys[2]]), 'center_delta_mm': [1.0, 0.0]},
         ],
         'arrangement': {'type': 'synthetic-repeat-fixture'}},
    ]


def relation_rows():
    return [
        {'source_index': 3, 'target_index': i, 'type': 'family_member',
         'witness': {'method': 'fixture', 'distance_mm': 2.0}}
        for i in range(3)
    ]


class FamilyMapStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.family-map-test-', dir=ROOT / 'out')
        self.root = ROOT
        self.scratch = Path(self.temp.name)
        self.base_store, self.org_revision, self.source_hash, self.source_object_id = fixture(self.scratch)
        self.output_root = self.scratch / 'family-maps'
        self.dataset_id = 'test:org-family-map:v1'

    def tearDown(self):
        self.temp.cleanup()

    def publish(self, *, fail=False, fail_after_run_rename=False, entities=None, relations=None,
                coverage=None):
        return publish(
            self.root, base_store=self.base_store, org_revision=self.org_revision,
            output_root=self.output_root, dataset_id=self.dataset_id,
            input_spec=input_spec(self.org_revision, self.source_hash),
            entities=records(self.org_revision, self.source_object_id) if entities is None else entities,
            relations=relation_rows() if relations is None else relations,
            coverage=coverage or {'source_objects': 1, 'unsupported': 0, 'scope': 'fixture'},
            fail_before_publish=fail,
            fail_after_run_rename=fail_after_run_rename,
        )

    def test_publish_reopens_and_repeated_identical_input_is_deterministic(self):
        first, first_receipt = self.publish()
        self.assertEqual(verify_bundle(self.root, first)['status'], 'PASS')
        first_manifest = json.loads((first / 'materialization.json').read_text())
        self.assertNotEqual(first_receipt['writer_pid'], first_receipt['reader_pid'])
        self.assertEqual(first_manifest['derived_map']['record_count'], 4)
        second, _ = self.publish(relations=list(reversed(relation_rows())))
        second_manifest = json.loads((second / 'materialization.json').read_text())
        self.assertEqual(first_manifest['derived_map']['input_snapshot_id'],
                         second_manifest['derived_map']['input_snapshot_id'])
        self.assertEqual(first_manifest['derived_map']['content_sha256'],
                         second_manifest['derived_map']['content_sha256'])
        self.assertEqual(first_manifest['derived_map']['revision'], second_manifest['derived_map']['revision'])
        self.assertTrue(first.is_dir())
        self.assertTrue(second.is_dir())
        self.assertEqual(json.loads((self.output_root / 'current.json').read_text())['run'], second.name)

    def test_failed_publication_keeps_previous_pointer_and_immutable_run(self):
        first, _ = self.publish()
        pointer_before = (self.output_root / 'current.json').read_bytes()
        with self.assertRaisesRegex(CatalogError, 'INJECTED_FAMILY_MAP_PUBLICATION_FAILURE'):
            self.publish(fail=True)
        self.assertEqual((self.output_root / 'current.json').read_bytes(), pointer_before)
        self.assertTrue(first.is_dir())
        self.assertEqual(len(list(self.output_root.glob('.staging-*'))), 0)

    def test_interruption_after_run_rename_keeps_previous_pointer_and_run(self):
        first, _ = self.publish()
        pointer_before = (self.output_root / 'current.json').read_bytes()
        with self.assertRaisesRegex(CatalogError, 'INJECTED_FAILURE_AFTER_RUN_RENAME'):
            self.publish(fail_after_run_rename=True)
        self.assertEqual((self.output_root / 'current.json').read_bytes(), pointer_before)
        self.assertTrue(first.is_dir())
        published = json.loads((self.output_root / 'current.json').read_text())['run']
        self.assertEqual(published, first.name)
        runs = list(self.output_root.glob('run-*'))
        self.assertEqual(len(runs), 2)
        self.assertTrue(all(run.is_dir() for run in runs))
        self.assertEqual(len(list(self.output_root.glob('.staging-*'))), 0)
        self.assertEqual(verify_bundle(self.root, first)['status'], 'PASS')

    def test_cross_revision_and_dangling_source_refs_are_rejected(self):
        entities = records(self.org_revision, self.source_object_id)
        entities[0]['source_refs'][0]['source_revision'] = digest(b'other revision')
        with self.assertRaisesRegex(CatalogError, 'CROSS_REVISION_SOURCE_REF'):
            self.publish(entities=entities)
        entities = records(self.org_revision, 'f' * 64 + ':bytes:0:1')
        with self.assertRaisesRegex(CatalogError, 'DANGLING_ORG_OBJECT_REF'):
            self.publish(entities=entities)
        self.assertFalse((self.output_root / 'current.json').exists())

    def test_one_org_object_can_support_multiple_members_without_source_duplication(self):
        entities = records(self.org_revision, self.source_object_id)
        extra_key = digest(canonical(['fixture-extra-member']))
        entities.insert(1, {
            'entity_type': 'candidate_member',
            'member_key': extra_key,
            'source_refs': [{'source_revision': self.org_revision,
                             'object_id': self.source_object_id,
                             'role': 'local_copper_candidate'}],
            'candidate_family_keys': [],
            'geometry': {'basis': 'same-source-object', 'units': 'mm'},
        })
        bundle, _ = self.publish(entities=entities, relations=[
            {'source_index': 4, 'target_index': i, 'type': 'family_member',
             'witness': {'method': 'fixture'}} for i in (0, 2, 3)])
        manifest = json.loads((bundle / 'materialization.json').read_text())
        with RevisionCatalog(bundle / 'store', read_only=True) as catalog:
            org = catalog.snapshot(self.org_revision)
            derived = catalog.snapshot(manifest['derived_map']['revision'])
        self.assertEqual(len(org['objects']), 1)
        self.assertEqual(len(derived['objects']), 5)
        shared = [row for row in derived['objects']
                  if row['kind'] == 'candidate_member'
                  and row.get('source_refs', [{}])[0].get('object_id') == self.source_object_id]
        self.assertEqual(len(shared), 4)

    def test_dangling_family_member_and_missing_support_relation_are_rejected(self):
        entities = records(self.org_revision, self.source_object_id)
        entities[-1]['members'][0] = digest(canonical(['not-in-map']))
        with self.assertRaisesRegex(CatalogError, 'DANGLING_FAMILY_MEMBER_KEY'):
            self.publish(entities=entities)
        entities = records(self.org_revision, self.source_object_id)
        with self.assertRaisesRegex(CatalogError, 'FAMILY_MEMBER_RELATION_CLOSURE_MISMATCH'):
            self.publish(entities=entities, relations=relation_rows()[:-1])

    def test_member_backlinks_must_match_nonexclusive_family_membership(self):
        entities = records(self.org_revision, self.source_object_id)
        entities[0]['candidate_family_keys'] = []
        with self.assertRaisesRegex(CatalogError, 'MEMBER_FAMILY_BACKLINK_CLOSURE_MISMATCH'):
            self.publish(entities=entities)

    def test_nested_trace_and_reference_links_are_in_source_ref_closure(self):
        rev = digest(b'org-revision')
        seed_id, trace_id, mask_id, paste_id = 'seed', 'trace', 'mask', 'paste'
        org_rows = {
            seed_id: {'id': seed_id, 'kind': 'gr_circle', 'layers': ['F.Cu'],
                      'geometry_sha256': 'a' * 64},
            trace_id: {'id': trace_id, 'kind': 'segment', 'layers': ['F.Cu'],
                       'geometry_sha256': 'b' * 64},
            mask_id: {'id': mask_id, 'kind': 'gr_circle', 'layers': ['F.Mask'],
                      'geometry_sha256': 'c' * 64},
            paste_id: {'id': paste_id, 'kind': 'gr_poly', 'layers': ['F.Paste'],
                       'geometry_sha256': 'd' * 64},
        }
        ref = lambda object_id, role: {
            'source_revision': rev, 'object_id': object_id, 'role': role,
        }
        mask_ref = ref(mask_id, 'F.Mask_geometric_feature_candidate')
        paste_ref = ref(paste_id, 'F.Paste_geometric_feature_candidate')
        trace_ref = ref(trace_id, 'incident_trace')
        member = {
            'entity_type': 'candidate_member', 'status': 'RESTRICTED_SEED_HYPOTHESIS',
            'member_key': digest(b'member'),
            'source_refs': [ref(seed_id, 'local_land_candidate_seed'), trace_ref,
                            mask_ref, paste_ref],
            'geometry': {'source_kind': 'gr_circle', 'geometry_sha256': 'a' * 64},
            'trace_associations': {
                'predicate': 'fixture GEOS intersection',
                'nominal_contacts': [{**trace_ref, 'distance_mm': 0.0,
                                      'status': 'NOMINAL_CONTACT'}],
                'uncertain_associations': [],
            },
            'reference_features': {
                'F.Mask': {'status': 'UNIQUE_GEOMETRIC_CANDIDATE',
                           'candidates': [mask_ref], 'unsupported_candidates': []},
                'F.Paste': {'status': 'UNIQUE_GEOMETRIC_CANDIDATE',
                            'candidates': [paste_ref], 'unsupported_candidates': []},
            },
        }
        _validate_recognition_reference_closure(org_rows, [member], rev)
        member['source_refs'] = [ref(seed_id, 'local_land_candidate_seed'), mask_ref, paste_ref]
        with self.assertRaisesRegex(CatalogError, 'NESTED_TRACE_REF_NOT_INDEXED'):
            _validate_recognition_reference_closure(org_rows, [member], rev)
        member['source_refs'].append(ref(trace_id, 'incident_trace'))
        member['trace_associations']['nominal_contacts'][0]['source_revision'] = digest(b'other-rev')
        with self.assertRaisesRegex(CatalogError, 'RECOGNITION_SOURCE_REVISION_MISMATCH'):
            _validate_recognition_reference_closure(org_rows, [member], rev)

    def test_physical_group_partition_and_member_link_reopen_closure(self):
        group_key = digest(b'fixture-physical-group')
        member_key = digest(b'fixture-group-member')
        member = {
            'entity_type': 'candidate_member', 'member_key': member_key,
            'source_refs': [{'source_revision': self.org_revision,
                             'object_id': self.source_object_id,
                             'role': 'local_land_candidate_seed'}],
            'candidate_family_keys': [], 'physical_group_key': group_key,
        }
        group = {
            'entity_type': 'physical_group', 'physical_group_key': group_key,
            'layer': 'F.Cu', 'source_members': [self.source_object_id],
            'source_refs': [{'source_revision': self.org_revision,
                             'object_id': self.source_object_id,
                             'role': 'physical_group_member'}],
        }
        coverage = {'physical_group_records': 1, 'physical_topology': {
            'status': 'COMPLETE', 'physical_contact_components': 1, 'source_objects': 1}}
        relation = [{'source_index': 0, 'target_index': 1,
                     'type': 'member_physical_group', 'witness': {'layer': 'F.Cu'}}]
        bundle, _ = self.publish(entities=[member, group], relations=relation,
                                 coverage=coverage)
        self.assertEqual(verify_bundle(self.root, bundle)['status'], 'PASS')
        broken = [dict(member), dict(group)]
        broken[0]['physical_group_key'] = digest(b'dangling-group')
        with self.assertRaisesRegex(CatalogError, 'DANGLING_PHYSICAL_GROUP_KEY'):
            self.publish(entities=broken, relations=relation, coverage=coverage)

    def test_catalogue_foreign_keys_reject_cross_revision_sql_relations(self):
        map_payload = b'{"fixture":"derived"}'
        map_hash = digest(map_payload)
        map_id = f'{map_hash}:bytes:0:{len(map_payload)}'
        map_row = {'id': map_id, 'source_sha256': map_hash,
                   'source_span': [0, len(map_payload)], 'parent_id': None,
                   'native_id': None, 'kind': 'candidate_member'}
        with RevisionCatalog(self.base_store) as catalog:
            with self.assertRaises(CatalogError):
                catalog.import_revision(map_payload, [map_row], [{
                    'occurrence': digest(b'cross-revision-relation'),
                    'source': self.source_object_id,
                    'target': map_id,
                    'type': 'must-not-cross-revision',
                    'witness': None,
                }], {'kind': 'invalid-cross-revision-test'})

    def test_corrupt_derived_payload_is_rejected_even_if_receipt_hash_is_updated(self):
        bundle, _ = self.publish()
        manifest = json.loads((bundle / 'materialization.json').read_text())
        map_hash = manifest['derived_map']['source_sha256']
        payload_path = bundle / 'store' / 'payloads' / map_hash
        payload_path.write_bytes(b'corrupt-but-rehashed-in-receipt')
        receipt_path = bundle / 'acceptance.json'
        receipt = json.loads(receipt_path.read_text())
        receipt['outputs'][payload_path.relative_to(bundle).as_posix()] = sha(payload_path)
        write_json(receipt_path, receipt)
        with self.assertRaisesRegex(CatalogError, 'PAYLOAD_HASH_MISMATCH'):
            verify_bundle(self.root, bundle)

    def test_input_snapshot_is_deterministic_and_has_no_edit_input(self):
        from src.family_map_storage import _map_content_digest, input_snapshot_id
        spec = input_spec(self.org_revision, self.source_hash)
        first, inputs = input_snapshot_id(dataset_id=self.dataset_id, **spec)
        second, _ = input_snapshot_id(dataset_id=self.dataset_id, **dict(spec))
        self.assertEqual(first, second)
        self.assertNotIn('EDIT', inputs)
        self.assertNotIn('edit', inputs)
        changed_spec = dict(spec)
        changed_spec['parser_version'] = 'native-inventory-test/2'
        changed, _ = input_snapshot_id(dataset_id=self.dataset_id, **changed_spec)
        self.assertNotEqual(first, changed)
        semantic = _map_content_digest(
            records(self.org_revision, self.source_object_id),
            relation_rows(), {'source_objects': 1, 'unsupported': 0, 'scope': 'fixture'})
        self.assertEqual(semantic, _map_content_digest(
            records(self.org_revision, self.source_object_id),
            list(reversed(relation_rows())),
            {'source_objects': 1, 'unsupported': 0, 'scope': 'fixture'}))


if __name__ == '__main__':
    unittest.main()
