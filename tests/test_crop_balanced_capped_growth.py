import unittest
from src.crop_balanced_capped_growth import shared_factor,require_radius_cap

class BalancedCappedGrowthTests(unittest.TestCase):
    def test_shared_scale_respects_hard_ceiling_even_when_space_allows_more(self):
        factor,radii=shared_factor([.15,.15],source_feasible_factor=3,square_pair_factor=2)
        self.assertEqual(factor,1.5)
        for radius in radii:self.assertTrue(require_radius_cap(.15,radius))

    def test_tighter_source_limit_applies_to_both_sites(self):
        factor,radii=shared_factor([.15,.15],source_feasible_factor=1.43,square_pair_factor=2)
        self.assertEqual(radii,[.15*1.43]*2)
        self.assertEqual(factor,1.43)

    def test_different_source_sizes_receive_same_scale_not_same_radius(self):
        factor,radii=shared_factor([.10,.15],source_feasible_factor=1.4,square_pair_factor=1.45)
        self.assertAlmostEqual(radii[0]/.10,radii[1]/.15)
        self.assertEqual(factor,1.4)

    def test_any_above_cap_proposal_rejected_without_clearance_override(self):
        for radius in [.15*1.50000001,.15*2,float('nan')]:
            with self.assertRaises(ValueError):require_radius_cap(.15,radius)
        with self.assertRaises(ValueError):shared_factor([.15,.15],source_feasible_factor=.9,square_pair_factor=2)

if __name__=='__main__':unittest.main()
