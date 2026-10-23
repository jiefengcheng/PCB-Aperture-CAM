import json
import tempfile
import unittest
from pathlib import Path

from src.profile_materialization import _gerber_inventory, _read_materialization, _revision_side

ROOT = Path(__file__).resolve().parents[1]


class ProfileMaterializationTests(unittest.TestCase):
    def test_pair_roles_follow_sealed_source_folder_names(self):
        self.assertEqual(_revision_side('ORG/top.kicad_pcb'), 'before')
        self.assertEqual(_revision_side('EDIT/top_layer.kicad_pcb'), 'after')
        self.assertIsNone(_revision_side('other/top.kicad_pcb'))
        self.assertIsNone(_revision_side('top.kicad_pcb'))

    def test_gerber_records_keep_source_spans_and_unresolved_layer_role(self):
        source = (b'%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.200*%\nD10*\n'
                  b'X1000000Y2000000D03*\nM02*\n')
        parsed = _gerber_inventory(source, 'EDIT/copper.gbr')
        self.assertEqual(parsed['status'], 'PARSED')
        self.assertEqual(len(parsed['source_objects']), 1)
        record = parsed['source_objects'][0]
        self.assertEqual(record['source_sha256'], parsed['source_sha256'])
        self.assertEqual(source[slice(*record['source_span'])], b'X1000000Y2000000D03')
        self.assertEqual(record['side'] if 'side' in record else _revision_side(record['source_label']), 'after')
        self.assertEqual(record['layer_role'], 'UNRESOLVED_FROM_SOURCE_ATTRIBUTES')
        self.assertEqual(record['coverage'], 'BOUNDS_ONLY')
        self.assertIsNone(record['geometry_sha256'])
        self.assertIsNone(record['position_mm'])

    def test_failed_empty_receipt_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'out') as temporary:
            bundle = Path(temporary)
            (bundle / 'materialization.json').write_text(json.dumps({'schema': 'pcb-profile-record-materialization/1'}))
            (bundle / 'acceptance.json').write_text(json.dumps({'status': 'FAIL'}))
            with self.assertRaisesRegex(ValueError, 'acceptance receipt is missing or failed'):
                _read_materialization(ROOT, bundle)


if __name__ == '__main__':
    unittest.main()
