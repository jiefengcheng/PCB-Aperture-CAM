import unittest

from shapely.geometry import LineString, Polygon

from src.copper_correspondence import polygon_correspondence, trace_correspondence


def line(identity, points, width=0.2):
    return {'identity': identity, 'geometry': LineString(points), 'width_mm': width}


def polygon(identity, points):
    return {'identity': identity, 'geometry': Polygon(points)}


class TraceCorrespondenceTests(unittest.TestCase):
    def test_one_to_one_centerline_pair_ignores_width_but_reports_it(self):
        result = trace_correspondence(
            [line('org', [(0, 0), (2, 0)], .2)],
            [line('edit', [(0, .0005), (2, .0005)], .35)])
        self.assertEqual(result['summary']['one_to_one_count'], 1)
        relation = result['relations'][0]
        self.assertEqual(relation['status'], 'one_to_one_geometric_candidate')
        self.assertAlmostEqual(relation['candidate_edges'][0]['width_delta_mm'], .15)
        # Footprint evidence is a separate measurement channel; it does not alter
        # the centerline candidate or its classification.
        self.assertEqual(relation['candidate_edges'][0]['copper_footprint_comparison']['status'], 'MEASURED')
        self.assertGreater(relation['candidate_edges'][0]['copper_footprint_comparison']['symmetric_difference_area_mm2'], 0)
        self.assertEqual(relation['status'], 'one_to_one_geometric_candidate')

    def test_unchanged_trace_has_negligible_stroke_difference(self):
        result = trace_correspondence(
            [line('org', [(0, 0), (2, 0)], .2)],
            [line('edit', [(0, 0), (2, 0)], .2)])
        comparison = result['relations'][0]['copper_footprint_comparison']
        self.assertAlmostEqual(comparison['symmetric_difference_area_mm2'], 0.0, places=10)
        self.assertAlmostEqual(comparison['before_covered_fraction'], 1.0)
        self.assertAlmostEqual(comparison['after_covered_fraction'], 1.0)

    def test_split_trace_union_preserves_stroke_footprint(self):
        result = trace_correspondence(
            [line('org', [(0, 0), (2, 0)], .2)],
            [line('edit-a', [(0, 0), (1, 0)], .2),
             line('edit-b', [(1, 0), (2, 0)], .2)])
        relation = result['relations'][0]
        self.assertEqual(relation['classification'], 'one_to_many_overlap')
        comparison = relation['copper_footprint_comparison']
        self.assertEqual(comparison['status'], 'MEASURED')
        self.assertLess(comparison['symmetric_difference_area_mm2'], 1e-9)

    def test_merge_trace_union_preserves_stroke_footprint(self):
        result = trace_correspondence(
            [line('org-a', [(0, 0), (1, 0)], .2),
             line('org-b', [(1, 0), (2, 0)], .2)],
            [line('edit', [(0, 0), (2, 0)], .2)])
        relation = result['relations'][0]
        self.assertEqual(relation['classification'], 'many_to_one_overlap')
        self.assertLess(relation['copper_footprint_comparison']['symmetric_difference_area_mm2'], 1e-9)

    def test_narrowed_trace_reports_directional_footprint_change(self):
        result = trace_correspondence(
            [line('org-wide', [(0, 0), (2, 0)], .4)],
            [line('edit-narrow', [(0, 0), (2, 0)], .2)])
        comparison = result['relations'][0]['copper_footprint_comparison']
        self.assertLess(comparison['signed_area_delta_mm2'], 0)
        self.assertGreater(comparison['symmetric_difference_area_mm2'], 0)
        self.assertAlmostEqual(comparison['after_covered_fraction'], 1.0)
        self.assertLess(comparison['before_covered_fraction'], 1.0)

    def test_short_incidental_overlap_has_low_long_side_footprint_coverage(self):
        result = trace_correspondence(
            [line('org-long', [(0, 0), (10, 0)], .2)],
            [line('edit-short', [(5, 0), (5.1, 0)], .2)])
        relation = result['relations'][0]
        self.assertEqual(relation['status'], 'partial_geometric_correspondence_candidate')
        self.assertLess(relation['copper_footprint_comparison']['before_covered_fraction'], .03)
        self.assertGreater(relation['copper_footprint_comparison']['after_covered_fraction'], .99)

    def test_repeated_trace_layout_keeps_ambiguity_with_footprint_metrics(self):
        result = trace_correspondence(
            [line('org-a', [(0, 0), (1, 0)], .2),
             line('org-b', [(.02, 0), (1.02, 0)], .2)],
            [line('edit-a', [(.01, 0), (1.01, 0)], .2),
             line('edit-b', [(.03, 0), (1.03, 0)], .2)])
        self.assertEqual(result['summary']['many_to_many_ambiguous_count'], 1)
        self.assertEqual(result['relations'][0]['status'], 'ambiguous_geometric_candidate')
        self.assertEqual(result['relations'][0]['copper_footprint_comparison']['status'], 'MEASURED')

    def test_missing_trace_width_keeps_centerline_link_but_withholds_footprint_metric(self):
        before = line('org', [(0, 0), (1, 0)])
        after = line('edit', [(0, 0), (1, 0)])
        del after['width_mm']
        result = trace_correspondence([before], [after])
        self.assertEqual(result['relations'][0]['status'], 'one_to_one_geometric_candidate')
        self.assertEqual(result['relations'][0]['copper_footprint_comparison']['status'], 'NOT_AVAILABLE')
        self.assertEqual(result['relations'][0]['copper_footprint_comparison']['reason'], 'MISSING_OR_NONPOSITIVE_WIDTH')

    def test_trace_split_is_retained_as_one_to_many(self):
        result = trace_correspondence(
            [line('org', [(0, 0), (2, 0)])],
            [line('edit-a', [(0, 0), (1, 0)]), line('edit-b', [(1, 0), (2, 0)])])
        self.assertEqual(result['summary']['one_to_many_count'], 1)
        self.assertEqual(result['relations'][0]['before_identities'], ['org'])
        self.assertEqual(result['relations'][0]['after_identities'], ['edit-a', 'edit-b'])

    def test_coincident_duplicate_traces_remain_one_to_many_candidates(self):
        result = trace_correspondence(
            [line('org-a', [(0, 0), (1, 0)]), line('org-b', [(0, 0), (1, 0)])],
            [line('edit', [(0, 0), (1, 0)])])
        self.assertEqual(result['summary']['many_to_one_count'], 1)
        self.assertEqual(result['relations'][0]['status'], 'partial_geometric_correspondence_candidate')
        self.assertEqual(len(result['relations'][0]['before_identities']), 2)

    def test_crossing_and_distant_traces_are_not_correspondence(self):
        result = trace_correspondence(
            [line('horizontal', [(-1, 0), (1, 0)])],
            [line('crossing', [(0, -1), (0, 1)]), line('distant', [(3, 3), (4, 3)])])
        self.assertEqual(result['summary']['candidate_edge_count'], 0)
        self.assertEqual(result['summary']['unmatched_before_count'], 1)
        self.assertEqual(result['summary']['unmatched_after_count'], 2)

    def test_short_trace_overlap_is_retained_as_partial_not_full(self):
        result = trace_correspondence(
            [line('org-long', [(0, 0), (10, 0)])],
            [line('edit-short', [(5, 0), (5.1, 0)])])
        relation = result['relations'][0]
        edge = relation['candidate_edges'][0]
        self.assertEqual(relation['status'], 'partial_geometric_correspondence_candidate')
        self.assertAlmostEqual(edge['before_covered_fraction'], .0102)
        self.assertAlmostEqual(edge['after_covered_fraction'], 1.0)
        self.assertEqual(result['summary']['one_to_one_full_coverage_count'], 0)

    def test_trace_graph_accounting_lists_candidate_and_isolated_source_ids(self):
        result = trace_correspondence(
            [line('org-linked', [(0, 0), (1, 0)]), line('org-isolated', [(4, 4), (5, 4)])],
            [line('edit-linked', [(0, 0), (1, 0)]), line('edit-isolated', [(7, 7), (8, 7)])])
        receipt = result['graph_accounting']
        self.assertEqual(receipt['candidate_before_identities'], ['org-linked'])
        self.assertEqual(receipt['candidate_after_identities'], ['edit-linked'])
        self.assertEqual(receipt['unmatched_before_identities'], ['org-isolated'])
        self.assertEqual(receipt['unmatched_after_identities'], ['edit-isolated'])
        self.assertEqual(receipt['candidate_edge_count'], 1)
        self.assertEqual(receipt['relation_component_count'], 1)
        self.assertEqual(receipt['component_classification_counts'], {'one_to_one_geometric_candidate': 1})


class PolygonCorrespondenceTests(unittest.TestCase):
    def test_filled_polygon_growth_is_a_geometric_candidate(self):
        result = polygon_correspondence(
            [polygon('org', [(0, 0), (1, 0), (1, 1), (0, 1)])],
            [polygon('edit', [(-.2, -.2), (1.2, -.2), (1.2, 1.2), (-.2, 1.2)])])
        self.assertEqual(result['summary']['one_to_one_count'], 1)
        edge = result['relations'][0]['candidate_edges'][0]
        self.assertGreater(edge['after_area_mm2'], edge['before_area_mm2'])
        self.assertEqual(result['relations'][0]['status'], 'partial_geometric_correspondence_candidate')
        self.assertGreater(edge['area_delta_mm2'], 0)
        self.assertLess(edge['after_covered_fraction'], .9)
        self.assertGreater(edge['copper_footprint_comparison']['symmetric_difference_area_mm2'], 0)

    def test_polygon_split_and_duplicate_alternatives_are_not_forced_one_to_one(self):
        org = polygon('org', [(0, 0), (2, 0), (2, 1), (0, 1)])
        split = polygon_correspondence(
            [org],
            [polygon('edit-left', [(0, 0), (1, 0), (1, 1), (0, 1)]),
             polygon('edit-right', [(1, 0), (2, 0), (2, 1), (1, 1)])])
        self.assertEqual(split['summary']['one_to_many_count'], 1)
        duplicated = polygon_correspondence(
            [org, polygon('org-copy', [(0, 0), (2, 0), (2, 1), (0, 1)])],
            [polygon('edit', [(0, 0), (2, 0), (2, 1), (0, 1)])])
        self.assertEqual(duplicated['summary']['many_to_one_count'], 1)
        self.assertEqual(len(duplicated['relations'][0]['before_identities']), 2)

    def test_tiny_polygon_inside_large_polygon_stays_partial(self):
        result = polygon_correspondence(
            [polygon('org-large', [(0, 0), (1, 0), (1, 1), (0, 1)])],
            [polygon('edit-tiny', [(.45, .45), (.55, .45), (.55, .55), (.45, .55)])])
        relation = result['relations'][0]
        edge = relation['candidate_edges'][0]
        self.assertEqual(relation['status'], 'partial_geometric_correspondence_candidate')
        self.assertAlmostEqual(edge['before_covered_fraction'], .01)
        self.assertAlmostEqual(edge['after_covered_fraction'], 1.0)
        self.assertEqual(result['summary']['one_to_one_full_coverage_count'], 0)

    def test_repeated_nearby_polygons_remain_many_to_many_ambiguous(self):
        before = [polygon('org-a', [(0, 0), (1, 0), (1, 1), (0, 1)]),
                  polygon('org-b', [(.02, 0), (1.02, 0), (1.02, 1), (.02, 1)])]
        after = [polygon('edit-a', [(.01, 0), (1.01, 0), (1.01, 1), (.01, 1)]),
                 polygon('edit-b', [(.03, 0), (1.03, 0), (1.03, 1), (.03, 1)])]
        result = polygon_correspondence(before, after)
        self.assertEqual(result['summary']['many_to_many_ambiguous_count'], 1)
        self.assertEqual(result['summary']['candidate_edge_count'], 4)
        self.assertEqual(result['relations'][0]['status'], 'ambiguous_geometric_candidate')
        self.assertEqual(result['relations'][0]['copper_footprint_comparison']['status'], 'MEASURED')

    def test_polygon_graph_accounting_lists_candidate_and_isolated_source_ids(self):
        result = polygon_correspondence(
            [polygon('org-linked', [(0, 0), (1, 0), (1, 1), (0, 1)]),
             polygon('org-isolated', [(4, 4), (5, 4), (5, 5), (4, 5)])],
            [polygon('edit-linked', [(0, 0), (1, 0), (1, 1), (0, 1)]),
             polygon('edit-isolated', [(7, 7), (8, 7), (8, 8), (7, 8)])])
        receipt = result['graph_accounting']
        self.assertEqual(receipt['candidate_before_identities'], ['org-linked'])
        self.assertEqual(receipt['candidate_after_identities'], ['edit-linked'])
        self.assertEqual(receipt['unmatched_before_identities'], ['org-isolated'])
        self.assertEqual(receipt['unmatched_after_identities'], ['edit-isolated'])
        self.assertEqual(receipt['candidate_edge_count'], 1)
        self.assertEqual(receipt['relation_component_count'], 1)

    def test_polygon_below_overlap_or_centroid_gate_stays_unmatched(self):
        result = polygon_correspondence(
            [polygon('org', [(0, 0), (1, 0), (1, 1), (0, 1)])],
            [polygon('low-overlap', [(0.8, 0), (1.8, 0), (1.8, 1), (0.8, 1)]),
             polygon('far', [(3, 3), (4, 3), (4, 4), (3, 4)])])
        self.assertEqual(result['summary']['candidate_edge_count'], 0)
        self.assertEqual(result['summary']['unmatched_before_count'], 1)
        self.assertEqual(result['summary']['unmatched_after_count'], 2)


if __name__ == '__main__':
    unittest.main()
