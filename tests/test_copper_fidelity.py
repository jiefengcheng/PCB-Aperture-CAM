import unittest

from shapely.geometry import LineString, box

from src.copper_fidelity import (bounds_intersect, collinear_arc_fallback,
                                 comparison_metrics, diagnostic_arc_roi,
                                 local_scope)


class CopperFidelityTests(unittest.TestCase):
    def test_only_collinear_arc_records_get_a_diagnostic_stroke(self):
        source = b'(arc (start 0 0) (mid 1 0) (end 2 0) (width 0.2) (layer "F.Cu"))'
        item = {'kind': 'arc', 'source_span': [0, len(source)], 'id': 'source:bytes:0:1'}
        result = collinear_arc_fallback(source, item)
        self.assertIsNotNone(result)
        self.assertEqual(result['fallback_kind'], 'collinear_arc_as_round_stroke_diagnostic')
        self.assertAlmostEqual(result['geometry'].area, 0.4 + 3.141592653589793 * 0.1**2, places=5)
        self.assertAlmostEqual(result['midpoint_deviation_mm'], 0.0)

    def test_curved_and_zero_width_arcs_remain_unsupported(self):
        source = b'(arc (start 0 0) (mid 1 1) (end 2 0) (width 0.2) (layer "F.Cu"))'
        item = {'kind': 'arc', 'source_span': [0, len(source)], 'id': 'source:bytes:0:1'}
        self.assertIsNone(collinear_arc_fallback(source, item))
        zero = b'(arc (start 0 0) (mid 1 0) (end 2 0) (width 0) (layer "F.Cu"))'
        item['source_span'] = [0, len(zero)]
        self.assertIsNone(collinear_arc_fallback(zero, item))

    def test_scope_bbox_intersection_and_directional_metrics(self):
        self.assertTrue(bounds_intersect((0, 0, 1, 1), (1, 1, 2, 2)))
        self.assertFalse(bounds_intersect((0, 0, 1, 1), (1.01, 0, 2, 2)))
        metrics = comparison_metrics(LineString([(0, 0), (1, 0)]).buffer(0.1),
                                    box(0, -0.1, 1, 0.1))
        self.assertEqual(metrics['status'], 'MEASURED')
        self.assertLess(metrics['expected_covered_fraction'], 1.0)
        self.assertGreater(metrics['symmetric_difference_area_mm2'], 0.0)

    def test_diagnostic_arc_roi_uses_fixed_context_rule(self):
        stroke = LineString([(0, 0), (1, 0)]).buffer(0.1)
        roi = diagnostic_arc_roi({'geometry': stroke, 'width_mm': 0.2})
        self.assertEqual(tuple(round(v, 6) for v in roi.bounds),
                         (-0.5, -1.0, 1.5, 1.0))

    def test_diagnostic_arc_roi_rejects_invalid_width_or_context(self):
        stroke = LineString([(0, 0), (1, 0)]).buffer(0.1)
        with self.assertRaises(ValueError):
            diagnostic_arc_roi({'geometry': stroke, 'width_mm': 0})
        with self.assertRaises(ValueError):
            diagnostic_arc_roi({'geometry': stroke, 'width_mm': 0.2}, -1)

    def test_local_scope_enumerates_supported_and_unsupported_source_ids(self):
        inside = box(-0.25, -0.25, 0.25, 0.25)
        outside = box(3, 3, 4, 4)
        source = b'(arc (start 0 0) (mid 1 0) (end 2 0) (width 0.2) (layer "F.Cu"))'
        unsupported = {'id': 'source:bytes:0:1', 'kind': 'arc',
                       'source_span': [0, len(source)], 'bounds_mm': None}
        fallback = collinear_arc_fallback(source, unsupported)
        scope = local_scope(
            [({'id': 'inside', 'bounds_mm': list(inside.bounds)}, inside),
             ({'id': 'outside', 'bounds_mm': list(outside.bounds)}, outside)],
            [unsupported], [(unsupported, fallback)], [], (0, 0), 1.0)
        self.assertEqual(scope['supported_source_identities'], ['inside'])
        self.assertEqual(scope['unsupported_source_identities'], ['source:bytes:0:1'])
        self.assertEqual(scope['unresolved_unsupported_source_count'], 0)


if __name__ == '__main__':
    unittest.main()
