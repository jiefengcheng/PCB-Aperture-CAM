import unittest

from shapely.geometry import GeometryCollection, LineString

from tools.decompose_real_arc_unresolved import decompose
from tools.evaluate_arc_attribution_coupon import incremental_geometry, stroke


class ArcAttributionCouponTests(unittest.TestCase):
    def test_isolated_target_increment_is_the_round_stroke(self):
        target = stroke([0, 0], [0.01, 0], 0.1)
        observed = incremental_geometry(GeometryCollection(), target)
        self.assertAlmostEqual(observed.symmetric_difference(target).area, 0.0, places=12)

    def test_fully_occluded_target_has_no_plot_increment(self):
        target = stroke([0, 0], [0.01, 0], 0.05)
        covering = LineString([[-0.01, 0], [0.02, 0]]).buffer(0.05, cap_style='round')
        self.assertTrue(incremental_geometry(covering, covering.union(target)).is_empty)

    def test_unresolved_reasons_are_multilabel_and_statuses_do_not_change(self):
        metrics = {
            'area_reference_pass': True,
            'relative_area_reference_pass': True,
            'boundary_reference_pass': False,
        }
        record = {
            'source_identity': 'source:1',
            'coupon_geometry_class_match': True,
            'coupon_width_range_match': True,
            'coupon_length_range_match': True,
            'unsupported_arc_count_in_roi': 2,
            'target_unique_area_mm2': 0.0,
            'status': 'UNRESOLVED',
            'reason': 'primary reason only',
            'supported_neighbor_count': 4,
            'target_only_plot_metrics': metrics,
        }
        result = decompose({'records': [record]})
        row = result['records'][0]
        self.assertEqual(result['status_counts_unchanged'], {'UNRESOLVED': 1})
        self.assertTrue(row['reason_flags']['multiple_unsupported_arcs_in_roi'])
        self.assertTrue(row['reason_flags']['no_unique_target_area'])
        self.assertTrue(row['reason_flags']['boundary_reference_miss'])


if __name__ == '__main__':
    unittest.main()
