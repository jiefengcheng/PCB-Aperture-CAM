import copy,unittest
from tests.test_crop_balanced_t01 import fixture
from src.crop_balanced_t01 import local_groups,CropSettings,execute
from src.crop_diameter_classes import admissible_diameters,select_targets
from tools.audit_crop_balanced_t01 import audit_diameter_contract

class DiameterClassTests(unittest.TestCase):
    def test_strict_ceiling_never_rounds_up(self):
        self.assertNotIn(.375,admissible_diameters(.12497,[.2999,.3749,.375]))
        self.assertEqual(admissible_diameters(.12497,[.2999,.3749,.4499]),[.2999,.3749])
        with self.assertRaises(ValueError):admissible_diameters(1,[2.9,2.8])

    def test_tight_priority_does_not_shrink_roomy_partner(self):
        sites,scene,rows,shapes=fixture(extra=(0,2.3));groups=local_groups(sites,['A','B'])
        targets,records,_=select_targets(sites,groups,{'ca':'A'},scene,CropSettings(),[2.2,2.6,2.9])
        self.assertEqual(targets['A'],1.1);self.assertEqual(targets['B'],1.45)
        result=execute(b'',rows,shapes,sites,groups,{'ca':'A'},targets=targets)
        self.assertFalse(result['failed_patches'])
        self.assertTrue(all(d['verification']['passed'] for d in result['decisions']))

    def test_discrete_reservations_demote_both_sides_without_continuous_values(self):
        sites,scene,_,_=fixture(((0,0),(2.5,0)));groups=local_groups(sites,['A','B'])
        targets,_,_=select_targets(sites,groups,{'ca':'A','cb':'B'},scene,CropSettings(),[2.2,2.6,2.9])
        self.assertEqual(targets['A'],1.1)
        self.assertIn(targets['B'],[1.,1.1])  # square-side bound can tighten B further
        self.assertGreaterEqual(2.5-sum(targets.values()),.02)

    def test_different_sources_can_share_absolute_diameter(self):
        self.assertIn(.3749,admissible_diameters(.12497,[.2999,.3374,.3749,.4499]))
        self.assertIn(.3749,admissible_diameters(.14999,[.2999,.3374,.3749,.4499]))

    def test_fresh_contract_rejects_continuous_size_and_over_cap(self):
        site={'source_id':'A','radius':1.}
        policy={'diameter_classes_mm':[2.2,2.6,2.9]}
        selection={'sites':[site],'groups':[{'site_ids':['A'],'target_diameter_mm':2.9}],
                   'size_classes':{'A':{'proposed_radius_mm':1.45,'admissible_classes_mm':[2.2,2.6,2.9],'category_mm':2.9,'original_keep':False}}}
        decisions={'A':{'proposed_radius_mm':1.45,'factor':1.45}}
        audit_diameter_contract(policy,selection,decisions)
        for radius in [1.35,1.50000001]:
            mutated=copy.deepcopy(selection);mutated['size_classes']['A'].update(proposed_radius_mm=radius,category_mm=2*radius)
            with self.assertRaises(AssertionError):audit_diameter_contract(policy,mutated,{'A':{'proposed_radius_mm':radius,'factor':radius}})


class SquareGuidedRecessTests(unittest.TestCase):
    def test_one_actual_conflict_guides_recess_without_replacing_circle_by_square(self):
        from shapely.geometry import Point
        from src.crop_diameter_classes import square_guided_recess
        from src.crop_square_neighbor_experiment import construct,verify_addition
        site={'core':Point(0,0).buffer(1,quad_segs=128),'center':[0,0]}
        obs=[{'source_id':'neighbor','geometry':Point(1.8,0).buffer(.6,quad_segs=128),'port_zone':None}]
        settings=CropSettings()
        final,recesses=square_guided_recess(site,1.5,obs,settings)
        plain=construct(site['core'],site['center'],1.5,obs,square_enabled=False,settings=settings.kernel())
        self.assertEqual(len(recesses),1)
        self.assertGreater(final.symmetric_difference(plain['candidate']).area,1e-8)
        self.assertTrue(verify_addition(site['core'],final,plain['envelope'],obs,settings=settings.kernel())['passed'])
        self.assertLessEqual(site['core'].difference(final).area,1e-10)
        self.assertGreater(final.area,site['core'].area)
        clear,recesses=square_guided_recess(site,1.5,[],settings)
        self.assertFalse(recesses);self.assertAlmostEqual(clear.area,plain['envelope'].area)

class MandatorySquareControlTests(unittest.TestCase):
    def test_absent_empty_or_ineffective_control_cannot_verify(self):
        from tools.audit_crop_balanced_t01 import require_square_control
        for report in [{},{'square_disabled_controls':[]},
                       {'square_disabled_controls':[{'key':'S31','source_id':'A','symmetric_difference_mm2':0}],
                        'decisions':[{'key':'S31','source_id':'A','square_guided':True,'square_recesses':[{}]}]}]:
            with self.assertRaises((KeyError,AssertionError)):require_square_control(report)


class RoundPromotionTests(unittest.TestCase):
    def test_recovers_free_class_without_shrinking_neighbour(self):
        from src.crop_diameter_classes import promote_round_priorities
        sites,scene,_,_=fixture(((0,0),(2.8,0)));groups=local_groups(sites,['A','B']);priorities={'ca':'A','cb':'B'}
        targets,records,_=select_targets(sites,groups,priorities,scene,CropSettings(),[2.2,2.6,2.9])
        before=dict(targets)
        events=promote_round_priorities(sites,groups,priorities,scene,CropSettings(),targets,records)
        self.assertTrue(events)
        self.assertTrue(all(targets[sid]>=radius for sid,radius in before.items()))
        self.assertEqual(targets['A'],1.45)
        self.assertTrue(all(radius<=1.5 for radius in targets.values()))

    def test_true_source_blocker_prevents_round_promotion(self):
        from src.crop_diameter_classes import promote_round_priorities
        sites,scene,_,_=fixture(extra=(0,2.3));groups=local_groups(sites,['A','B']);priorities={'ca':'A'}
        targets,records,_=select_targets(sites,groups,priorities,scene,CropSettings(),[2.2,2.6,2.9])
        promote_round_priorities(sites,groups,priorities,scene,CropSettings(),targets,records)
        self.assertEqual(targets['A'],1.1)
        self.assertIn('ORIGINAL_COPPER_OR_SOURCE_PORT_CLEARANCE',[b['reason'] for b in records['A']['round_opportunity']['blockers']])

class RoundDiagnosticPublicationTests(unittest.TestCase):
    def test_missing_or_empty_next_class_proofs_cannot_publish(self):
        from tools.render_crop_balanced_t01 import require_round_diagnostics
        report={'decisions':[{'source_id':'A','priority':True,'size_class':{'round_opportunity':{'next_class_diameter_mm':2.9}}}]}
        for audit in [{},{'round_next_class_controls':[]},{'round_next_class_controls':[{'source_id':'A','diameter_mm':2.9,'source_case':{'violations':[]},'round_blockers':[],'square_blockers':[]}]}]:
            with self.assertRaises((KeyError,AssertionError)):require_round_diagnostics(report,audit)


class OwnerReviewTests(unittest.TestCase):
    def test_owner_neighbor_controls_recess_instead_of_larger_unrelated_conflict(self):
        from shapely.geometry import Point
        from src.crop_diameter_classes import square_guided_recess
        site={'core':Point(0,0).buffer(1,quad_segs=128),'center':[0,0],'square_recess_neighbor_id':'owner'}
        obstacles=[{'source_id':'owner','geometry':Point(1.8,0).buffer(.6,quad_segs=128),'port_zone':None},
                   {'source_id':'other','geometry':Point(-1.75,0).buffer(.6,quad_segs=128),'port_zone':None}]
        candidate,records=square_guided_recess(site,1.5,obstacles,CropSettings())
        self.assertEqual(records[0]['source_id'],'owner')
        with self.assertRaisesRegex(ValueError,'NO_ACTUAL_CONFLICT'):square_guided_recess(site,1.5,obstacles[1:],CropSettings())

    def test_missing_second_recess_control_cannot_pass(self):
        from tools.audit_crop_balanced_t01 import require_square_control
        report={'square_disabled_controls':[{'key':'S31','source_id':'A','symmetric_difference_mm2':.1}],
                'decisions':[{'key':'S31','source_id':'A','square_guided':True,'square_recesses':[{}]}]}
        with self.assertRaises(AssertionError):require_square_control(report,['S31','S08'])

    def test_changed_review_reference_is_rejected(self):
        import tempfile
        from pathlib import Path
        from src.crop_diameter_classes import select_owner_review_targets
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'out/frozen';folder.mkdir(parents=True);(folder/'report.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):
                select_owner_review_targets(root,{'previous_bundle':'out/frozen','previous_report_sha256':'0'*64},[])

if __name__=='__main__':unittest.main()
