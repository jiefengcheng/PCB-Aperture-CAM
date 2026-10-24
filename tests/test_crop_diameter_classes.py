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

if __name__=='__main__':unittest.main()
