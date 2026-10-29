import copy
import math
import unittest
from src.crop_replay_comparison import compare_final_scene_checks,AREA_EPSILON_MM2


class DiagnosticAreaComparisonTests(unittest.TestCase):
    def base(self):
        return [{'source_id':'fixed','check':{'passed':True,'failures':[],
            'pairs':[{'neighbor_id':'arc','attachment_port_area_mm2':0.25,
                      'candidate_surface_gap_mm':.0201,'port_sha256':'fixed-hash'}]}}]

    def test_one_ulp_area_difference_is_logged_without_rounding(self):
        a=self.base();b=copy.deepcopy(a)
        b[0]['check']['pairs'][0]['attachment_port_area_mm2']=math.nextafter(.25,math.inf)
        r=compare_final_scene_checks(a,b)
        self.assertTrue(r['passed']);self.assertFalse(r['original_exact_equality'])
        self.assertEqual(len(r['admitted_differences']),1)
        self.assertEqual(r['admitted_differences'][0]['path'],'$[0].check.pairs[0].attachment_port_area_mm2')
        self.assertGreater(r['admitted_differences'][0]['signed_delta_mm2'],0)

    def test_exact_absolute_boundary_passes_and_next_float_fails(self):
        a=self.base();a[0]['check']['pairs'][0]['attachment_port_area_mm2']=0.0
        b=copy.deepcopy(a);b[0]['check']['pairs'][0]['attachment_port_area_mm2']=AREA_EPSILON_MM2
        self.assertTrue(compare_final_scene_checks(a,b)['passed'])
        b[0]['check']['pairs'][0]['attachment_port_area_mm2']=math.nextafter(AREA_EPSILON_MM2,math.inf)
        self.assertFalse(compare_final_scene_checks(a,b)['passed'])

    def test_any_distance_difference_fails(self):
        a=self.base();b=copy.deepcopy(a)
        b[0]['check']['pairs'][0]['candidate_surface_gap_mm']+=1e-16
        self.assertFalse(compare_final_scene_checks(a,b)['passed'])

    def test_same_field_name_at_wrong_path_has_no_allowance(self):
        a=self.base();a[0]['attachment_port_area_mm2']=.25;b=copy.deepcopy(a)
        b[0]['attachment_port_area_mm2']=math.nextafter(.25,math.inf)
        self.assertFalse(compare_final_scene_checks(a,b)['passed'])

    def test_identity_hash_and_decision_changes_fail(self):
        a=self.base()
        for mutation in ('source','hash','passed','failure'):
            b=copy.deepcopy(a)
            if mutation=='source':b[0]['source_id']='changed'
            elif mutation=='hash':b[0]['check']['pairs'][0]['port_sha256']='changed'
            elif mutation=='passed':b[0]['check']['passed']=False
            else:b[0]['check']['failures']=[{'reason':'NEW_SOURCE_CONTACT'}]
            self.assertFalse(compare_final_scene_checks(a,b)['passed'],mutation)

    def test_missing_keys_container_lengths_and_types_fail(self):
        a=self.base()
        for mutation in ('key','list','type'):
            b=copy.deepcopy(a)
            if mutation=='key':del b[0]['check']['pairs'][0]['neighbor_id']
            elif mutation=='list':b[0]['check']['pairs'].append(copy.deepcopy(b[0]['check']['pairs'][0]))
            else:b[0]['check']['passed']=1
            self.assertFalse(compare_final_scene_checks(a,b)['passed'],mutation)

    def test_nonfinite_and_invalid_numeric_area_values_fail(self):
        a=self.base()
        for value in (float('nan'),float('inf'),float('-inf'),True,'0.25',None,-.25):
            b=copy.deepcopy(a);b[0]['check']['pairs'][0]['attachment_port_area_mm2']=value
            self.assertFalse(compare_final_scene_checks(a,b)['passed'],str(value))
        b=copy.deepcopy(a);b[0]['check']['pairs'][0]['candidate_surface_gap_mm']=float('inf')
        self.assertFalse(compare_final_scene_checks(b,b)['passed'])

    def test_unchanged_no_port_null_is_exact_not_numerically_admitted(self):
        a=self.base();a[0]['check']['pairs'][0]['attachment_port_area_mm2']=None
        r=compare_final_scene_checks(a,copy.deepcopy(a))
        self.assertTrue(r['passed']);self.assertEqual(r['admitted_differences'],[])

    def test_admitted_area_cannot_hide_an_unauthorized_difference(self):
        a=self.base();b=copy.deepcopy(a)
        b[0]['check']['pairs'][0]['attachment_port_area_mm2']=math.nextafter(.25,math.inf)
        b[0]['check']['passed']=False
        r=compare_final_scene_checks(a,b)
        self.assertFalse(r['passed']);self.assertEqual(len(r['admitted_differences']),1)
        self.assertGreater(len(r['rejected_differences']),0)
