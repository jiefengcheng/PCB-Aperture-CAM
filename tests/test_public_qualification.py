import json, unittest
from pathlib import Path
from tools.qualify_public import inventory, parser_probe
from src.validator import ROOT, sha

class PublicQualification(unittest.TestCase):
    def test_public_source_custody_and_bounded_claims(self):
        for name in ('GlowStitch','HALPI2-HDMI-FPC'):
            with self.subTest(source=name):
                r=json.loads((ROOT/'out/v1_5'/name/'qualification.json').read_text())
                self.assertEqual(inventory(ROOT/'external/sources'/name),r['source_inventory'])
                self.assertTrue(r['source_immutable'])
                self.assertEqual(r['overall'],'NOT_ESTABLISHED')
                self.assertTrue(any(x['status']=='NOT_ESTABLISHED' for x in r['frozen_v1_readonly_import']))
                self.assertEqual(r['cursor_review']['status'],'NOT_RUN')

    def test_repeated_regions_have_stable_primitive_fingerprint(self):
        p=ROOT/'out/v1_5/GlowStitch'
        a=next((p/'export_1').glob('*F_Mask.gbr'))
        first=parser_probe(a);second=parser_probe(p/'export_2'/a.name)
        self.assertEqual(first['status'],'PASS',first)
        self.assertGreater(first['object_types'].get('Region',0),0)
        self.assertEqual(first['parsed_object_fingerprint'],second['parsed_object_fingerprint'])
        self.assertEqual(first['parsed_object_fingerprint'],parser_probe(a)['parsed_object_fingerprint'])

    def test_official_aperture_blocks_do_not_silently_pass(self):
        r=json.loads((ROOT/'out/v1_5/Ucamco/compatibility.json').read_text())
        self.assertEqual(sha(ROOT/'external/sources/Ucamco/gerber-layer-format-test-files_en.zip'),r['archive_sha256'])
        blocked=[x for x in r['results'] if Path(x['path']).name in ('Nested_blocks.gbr','Block_with_different_orientations.gbr')]
        self.assertEqual(len(blocked),2)
        for row in blocked:
            self.assertEqual(row['gerbonara_parse_and_primitive_expansion']['status'],'NOT_ESTABLISHED')
            self.assertTrue(row['gerbonara_parse_and_primitive_expansion']['warnings'])
            self.assertEqual(row['frozen_v1_lexical_coverage']['status'],'NOT_ESTABLISHED')
