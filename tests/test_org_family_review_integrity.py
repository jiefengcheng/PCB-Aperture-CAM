import unittest
import hashlib

from src.org_family_review import (
    MAX_REVIEW_BYTES,
    require_org_family_resource_budget,
    validate_complete_physical_groups,
)


class PhysicalGroupIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.org_revision = 'a' * 64
        self.org_sha = 'b' * 64
        self.projection = {
            'binding': {'org_revision': self.org_revision,
                        'org_source_sha256': self.org_sha},
            'source_objects': {
                'circle': {'object_id': 'circle', 'source_revision': self.org_revision,
                           'source_sha256': self.org_sha, 'source_span': [10, 20],
                           'layers': ['F.Cu'], 'geometry_sha256': '1' * 64,
                           'bounds_mm': [0.0, 0.0, 1.0, 1.0]},
                'trace': {'object_id': 'trace', 'source_revision': self.org_revision,
                          'source_sha256': self.org_sha, 'source_span': [21, 30],
                          'layers': ['F.Cu'], 'geometry_sha256': '2' * 64,
                          'bounds_mm': [0.5, 0.5, 2.0, 0.6]},
            },
            'geometry_paths': {'1' * 64: 'M0 0L1 1Z', '2' * 64: 'M.5 .5L2 .6'},
            'stored_geometry_paths': {'1' * 64: 'M0 0L1 1Z', '2' * 64: 'M.5 .5L2 .6'},
            'physical_groups': [{
                'inspection_status': 'COMPLETE', 'source_member_ids': ['circle', 'trace'],
                'source_member_count': 2, 'layer': 'F.Cu',
            }],
        }
        self.projection['geometry_bindings'] = {
            key: {'source_wkb_sha256': key, 'derivation': 'pcb-org-svg-path/v1',
                  'simplified_path_sha256': hashlib.sha256(path.encode()).hexdigest(),
                  'stored_path_sha256': hashlib.sha256(
                      self.projection['stored_geometry_paths'][key].encode()).hexdigest()}
            for key, path in self.projection['geometry_paths'].items()
        }

    def test_complete_group_resolves_every_source_identity_and_geometry(self):
        validate_complete_physical_groups(self.projection)

    def test_missing_source_record_is_rejected(self):
        del self.projection['source_objects']['trace']
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_GROUP_SOURCE_ID_MISMATCH'):
            validate_complete_physical_groups(self.projection)

    def test_source_id_substitution_is_rejected(self):
        self.projection['source_objects']['trace']['object_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_GROUP_SOURCE_ID_MISMATCH'):
            validate_complete_physical_groups(self.projection)

    def test_revision_or_source_hash_mismatch_is_rejected(self):
        self.projection['source_objects']['trace']['source_revision'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_GROUP_SOURCE_BINDING_MISMATCH'):
            validate_complete_physical_groups(self.projection)
        self.projection['source_objects']['trace']['source_revision'] = self.org_revision
        self.projection['source_objects']['trace']['source_sha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_GROUP_SOURCE_BINDING_MISMATCH'):
            validate_complete_physical_groups(self.projection)

    def test_missing_geometry_or_wrong_layer_is_rejected(self):
        del self.projection['geometry_paths']['2' * 64]
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_GEOMETRY_BINDING_SET_MISMATCH'):
            validate_complete_physical_groups(self.projection)
        key = '2' * 64
        self.projection['geometry_paths'][key] = 'M.5 .5L2 .6'
        self.projection['geometry_bindings'][key]['simplified_path_sha256'] = hashlib.sha256(
            self.projection['geometry_paths'][key].encode()).hexdigest()
        self.projection['source_objects']['trace']['layers'] = ['B.Cu']
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_GROUP_LAYER_MISMATCH'):
            validate_complete_physical_groups(self.projection)

    def test_duplicate_or_wrong_member_count_is_rejected(self):
        self.projection['physical_groups'][0]['source_member_ids'] = ['circle', 'circle']
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_GROUP_MEMBER_COUNT_MISMATCH'):
            validate_complete_physical_groups(self.projection)
        self.projection['physical_groups'][0]['source_member_ids'] = ['circle']
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_GROUP_MEMBER_COUNT_MISMATCH'):
            validate_complete_physical_groups(self.projection)

    def test_incomplete_group_is_not_misrepresented_as_complete(self):
        self.projection['physical_groups'][0]['inspection_status'] = 'SUMMARY_ONLY_LARGE_OR_UNPROJECTED_GROUP'
        validate_complete_physical_groups(self.projection)

    def test_resource_cap_accepts_limit_and_rejects_overflow(self):
        require_org_family_resource_budget('fixture', MAX_REVIEW_BYTES)
        with self.assertRaisesRegex(ValueError, '64 MiB resource budget'):
            require_org_family_resource_budget('fixture', MAX_REVIEW_BYTES + 1)

    def test_geometry_path_substitution_and_corruption_are_rejected(self):
        key = '1' * 64
        self.projection['geometry_paths'][key] = 'M9 9L10 10Z'
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_SIMPLIFIED_GEOMETRY_PATH_HASH_MISMATCH'):
            validate_complete_physical_groups(self.projection)

    def test_stored_path_substitution_and_missing_binding_are_rejected(self):
        key = '2' * 64
        self.projection['stored_geometry_paths'][key] = 'M8 8L9 9Z'
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_STORED_GEOMETRY_PATH_HASH_MISMATCH'):
            validate_complete_physical_groups(self.projection)
        del self.projection['geometry_bindings'][key]
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_GEOMETRY_BINDING_SET_MISMATCH'):
            validate_complete_physical_groups(self.projection)

    def test_wrong_wkb_identity_is_rejected_even_with_valid_path_hashes(self):
        key = '1' * 64
        self.projection['geometry_bindings'][key]['source_wkb_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'ORG_FAMILY_GEOMETRY_SOURCE_BINDING_INVALID'):
            validate_complete_physical_groups(self.projection)


if __name__ == '__main__':
    unittest.main()
