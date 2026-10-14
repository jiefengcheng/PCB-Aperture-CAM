import json, unittest
from shapely.geometry import Point
from shapely.ops import unary_union
from src.fc1_oracle import (analytic_area, analytic_bounds, MATRICES,
    placed_polygons, assess_polygons, synthetic_probes, polygon_vs_analytic_grid,
    png_comparison, LINEAR_BUDGET, AREA_BUDGET)
from src.fc1_run import ROOT, OUT, NAME, eligible, custody, sha

class FC1Oracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        custody()
        cls.ledger=json.loads((ROOT/'tests/fc1_expected.json').read_text())
        cls.shapes=placed_polygons()

    def test_literal_expected_area_bounds_and_topology(self):
        e=self.ledger
        self.assertAlmostEqual(analytic_area(),e['base_area_mm2'],places=12)
        scene=unary_union(self.shapes)
        self.assertLess(abs(scene.area-e['total_area_mm2']),4*AREA_BUDGET)
        self.assertEqual(len(scene.geoms),e['scene_components'])
        self.assertEqual(sum(len(g.interiors) for g in scene.geoms),e['scene_holes'])
        for i,(g,b) in enumerate(zip(self.shapes,e['placement_bounds_mm'])):
            with self.subTest(placement=i):
                self.assertLess(max(abs(a-c) for a,c in zip(g.bounds,b)),LINEAR_BUDGET)
                self.assertLess(max(abs(a-c) for a,c in zip(analytic_bounds(MATRICES[i]),b)),1e-12)
                self.assertFalse(g.covers(Point(e['hole_centers_mm'][i])))
                self.assertTrue(g.covers(Point(e['solid_centers_mm'][i])))
        self.assertEqual(assess_polygons(self.shapes)['status'],'PASS')

    def test_faults_fail_named_obligations(self):
        faults={'wrong_mirror':(2,'landmark'),'wrong_order':(2,'landmark'),
          'wrong_scale':(3,'area'),'clear_as_dark':(0,'hole'),
          'major_arc':(0,'absent_major_arc'),'wrong_arc_center':(0,'arc_mid'),
          'inch_units':(0,'bounds')}
        for name,(idx,kind) in faults.items():
            with self.subTest(fault=name):
                r=assess_polygons(placed_polygons(name));self.assertEqual(r['status'],'FAIL')
                row=r['placements'][idx]
                if kind=='area':self.assertGreater(row['area_error_mm2'],AREA_BUDGET)
                elif kind=='bounds':self.assertGreater(row['max_bounds_error_mm'],LINEAR_BUDGET)
                elif kind=='landmark':self.assertTrue(any(p['status']=='FAIL' for p in row['landmarks']))
                else:self.assertEqual(next(p['status'] for p in row['landmarks'] if p['name']==kind),'FAIL')

    def test_separate_reset_and_global_clear_scene_probes(self):
        r=synthetic_probes()
        self.assertTrue(r['transparent_clear']['positive_context_survives'])
        self.assertTrue(r['transparent_clear']['wrong_global_clear_rejected'])
        self.assertTrue(r['reset']['positive_identity_copper'])
        self.assertTrue(r['reset']['leaked_transform_rejected'])

    def test_analytic_membership_matches_polygons_away_from_boundaries(self):
        r=polygon_vs_analytic_grid();self.assertEqual(r['status'],'PASS',r)
        self.assertGreater(r['stable_samples'],300000)
        self.assertEqual(r['mismatches'],0)

    def test_png_reference_crosscheck_with_explicit_raster_limits(self):
        r=png_comparison(OUT/(NAME+'.png'))
        self.assertEqual(r['status'],'PASS',r)
        self.assertEqual(r['components'],12)
        self.assertEqual(r['excluded_boundary_band_px'],2)
        self.assertEqual(r['scale_px_per_mm'],36)
        self.assertEqual(r['mismatched_interior_pixels'],0)

    def test_polygonization_converges_within_analytic_budget(self):
        # Finer witness must improve area and remain within fixed oracle budget.
        coarse=placed_polygons(quadrants=256,segments=1024)
        for index,(c,f) in enumerate(zip(coarse,self.shapes)):
            target=analytic_area()*(.64 if index==3 else 1)
            self.assertLess(abs(f.area-target),abs(c.area-target))
            self.assertLess(f.hausdorff_distance(c),LINEAR_BUDGET)

    def test_unsupported_inputs_are_scope_rejections_not_parser_passes(self):
        with self.assertRaises(ValueError):placed_polygons('unknown_operation')
        report=json.loads((OUT/'report.json').read_text())
        source=OUT/(NAME+'.gbr');known=sha(source)
        self.assertEqual(eligible(source,known)['status'],'PASS')
        self.assertEqual(len(report['unsupported_scope_controls']),5)
        for row in report['unsupported_scope_controls']:
            p=OUT/'unsupported_controls'/(row['name']+'.gbr')
            with self.subTest(input=row['name']):
                self.assertEqual(sha(p),row['sha256'])
                self.assertEqual(eligible(p,known)['status'],'NOT_ESTABLISHED')
                self.assertIn('no semantic/parser coverage',eligible(p,known)['reason'])
        self.assertEqual(report['current_parser_probe']['status'],'NOT_ESTABLISHED')
        self.assertTrue(report['current_parser_probe']['warnings'])
        self.assertEqual(report['extended_parser_support'],'NOT_ESTABLISHED')

    def test_frozen_parser_contract_and_prior_evidence_unchanged(self):
        import subprocess,hashlib
        frozen='36eab151a0bf00ea57eef09f1dc425c4b5603e50'
        for rel in ('src/validator.py','src/falsification.py','tools/validate_native.py',
                    'contracts/report.schema.json','contracts/asset_manifest.sha256','requirements.lock.txt'):
            b=subprocess.check_output(['git','show',frozen+':'+rel],cwd=ROOT)
            self.assertEqual(hashlib.sha256(b).hexdigest(),sha(ROOT/rel),rel)
        prior=json.loads((ROOT/'out/fc1/prior_evidence_hashes.json').read_text())
        for rel,digest in prior.items():self.assertEqual(sha(ROOT/rel),digest,rel)
