import math
import unittest
from src.collective_width_bounds import shared_scale_bound


def constraint(key,a,gap,b=None):
    return dict(constraint_id=key,member_a=a,member_b=b,surface_gap_mm=gap,
                applicability='EXPOSED_DISCONNECTED_SURFACES')


class CollectiveWidthBoundTests(unittest.TestCase):
    def test_neighbors_share_factor_but_keep_original_width_ratio(self):
        q=shared_scale_bound({'a':.1,'b':.2},[constraint('ab','a',.05,'b')],minimum_gap_mm=.02)
        self.assertAlmostEqual(q['common_factor_upper_bound'],1.2)
        self.assertAlmostEqual(q['resulting_nominal_width_upper_bounds_mm']['b'],.24)

    def test_remote_fixed_obstacle_limits_every_group_member(self):
        q=shared_scale_bound({'a':.1,'b':.2},[constraint('ab','a',.05,'b'),constraint('remote','a',.025)],minimum_gap_mm=.02)
        self.assertAlmostEqual(q['common_factor_upper_bound'],1.1)
        self.assertEqual(q['limiting_constraint_ids'],['remote'])

    def test_preexisting_small_gap_does_not_authorize_shrink_or_repair(self):
        q=shared_scale_bound({'a':.1},[constraint('old','a',.005)])
        self.assertEqual(q['common_factor_upper_bound'],1.)
        self.assertEqual(q['width_construction'],'NOT_RUN')

    def test_ceiling_is_cap_not_mandatory_target(self):
        self.assertEqual(shared_scale_bound({'a':.1},[])['common_factor_upper_bound'],1.5)
        self.assertEqual(shared_scale_bound({'a':.1},[constraint('x','a',.02)])['common_factor_upper_bound'],1.)

    def test_internal_or_unknown_pair_is_not_silently_clearance_constraint(self):
        c=constraint('x','a',.001);c['applicability']='INTERNAL_PRIMITIVE_BOUNDARY'
        with self.assertRaisesRegex(ValueError,'SURFACE_APPLICABILITY_NOT_ESTABLISHED'):
            shared_scale_bound({'a':.1},[c])

    def test_nonfinite_width_or_gap_rejected(self):
        with self.assertRaisesRegex(ValueError,'INVALID_ORIGINAL_WIDTH'):
            shared_scale_bound({'a':math.nan},[])
        with self.assertRaisesRegex(ValueError,'INVALID_SURFACE_DISTANCE'):
            shared_scale_bound({'a':.1},[constraint('x','a',math.inf)])


if __name__=='__main__':unittest.main()
