import unittest
from shapely.geometry import box, LineString
from src.trace_growth_eligibility import classify_stroke, overlapping_parallel_fill_witness


class SourceStrokeEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.stroke = box(0, 0, 10, 1)

    def row(self, geometry, sid='other', kind='gr_poly', width=0.):
        return dict(id=sid, geometry=geometry, kind=kind, trace_width_mm=width)

    def classify(self, neighbors, **kw):
        return classify_stroke('trace', self.stroke, 1., 'segment', neighbors, **kw)

    def test_isolated_trace_is_eligible(self):
        self.assertEqual(self.classify([])['disposition'], 'ELIGIBLE_EXPOSED_SOURCE_STROKE')

    def test_small_endpoint_attachment_does_not_hide_full_trace(self):
        r = self.classify([self.row(box(-1, -1, 1, 2))])
        self.assertEqual(r['disposition'], 'ELIGIBLE_EXPOSED_SOURCE_STROKE')
        self.assertAlmostEqual(r['independently_exposed_fraction'], .9)

    def test_embedded_stroke_remains_fixed(self):
        r = self.classify([self.row(box(-1, -1, 11, 2))])
        self.assertEqual(r['disposition'], 'FIXED_EMBEDDED_OR_FILL')
        self.assertEqual(r['exposed_area_mm2'], 0.)

    def test_partial_overlap_is_eligible_even_when_majority_covered(self):
        self.assertEqual(self.classify([self.row(box(0, 0, 5, 1))])['disposition'], 'ELIGIBLE_EXPOSED_SOURCE_STROKE')
        self.assertEqual(self.classify([self.row(box(0, 0, 9, 1))])['disposition'], 'ELIGIBLE_EXPOSED_SOURCE_STROKE')
        self.assertEqual(self.classify([self.row(box(0, 0, 10, 1))])['disposition'], 'FIXED_EMBEDDED_OR_FILL')

    def test_exposed_remote_part_cannot_hide_embedding_in_review_scope(self):
        neighbors = [self.row(box(0, 0, 3, 1))]
        self.assertEqual(self.classify(neighbors)['disposition'], 'ELIGIBLE_EXPOSED_SOURCE_STROKE')
        r = self.classify(neighbors, eligibility_scope=box(0, 0, 4, 1))
        self.assertEqual(r['disposition'], 'ELIGIBLE_EXPOSED_SOURCE_STROKE')
        self.assertEqual(r['scope_exposed_fraction'], .25)
        self.assertEqual(self.classify(neighbors, eligibility_scope=box(0, 0, 3, 1))['disposition'], 'FIXED_EMBEDDED_OR_FILL')
        # A remote-only object has no local classification operand; its full
        # source must still be retained by the caller as context.
        self.assertIsNone(self.classify(neighbors, eligibility_scope=box(20, 0, 21, 1))['scope_exposed_fraction'])

    def test_same_trace_continuation_caps_are_not_background(self):
        neighbors = [self.row(box(0, 0, 3, 1), sid='a', kind='segment', width=1.),
                     self.row(box(7, 0, 10, 1), sid='b', kind='arc', width=1.)]
        self.assertEqual(self.classify(neighbors)['disposition'], 'ELIGIBLE_EXPOSED_SOURCE_STROKE')
        r = self.classify(neighbors, continuation_source_ids=['a', 'b'])
        self.assertEqual(r['disposition'], 'ELIGIBLE_EXPOSED_SOURCE_STROKE')
        self.assertEqual(r['independently_exposed_fraction'], .4)
        self.assertEqual(r['same_trace_neighbor_ids'], ['a', 'b'])
        self.assertEqual(r['ignored_same_trace_source_ids'], [])
        with self.assertRaisesRegex(ValueError, 'SAME_UNIFORM_NATIVE_TRACE_CONTINUATION_REQUIRED'):
            self.classify([self.row(self.stroke)], continuation_source_ids=['other'])

    def test_exact_alias_does_not_hide_source_but_other_shape_does(self):
        alias = self.row(self.stroke, kind='segment', width=1.)
        self.assertEqual(self.classify([alias])['independently_exposed_fraction'], 1.)
        self.assertEqual(self.classify([self.row(self.stroke)])['disposition'], 'FIXED_EMBEDDED_OR_FILL')

    def test_fill_witness_requires_actual_neighbor_identity(self):
        witness = dict(neighbor_source_id='fill', longitudinal_overlap_mm=8.)
        r = self.classify([self.row(box(0, .8, 10, 1.8), sid='fill', kind='segment', width=1.)], fill_witness=witness)
        self.assertEqual(r['disposition'], 'ELIGIBLE_EXPOSED_SOURCE_STROKE')
        with self.assertRaisesRegex(ValueError, 'SOURCE_BOUND_FILL_WITNESS_REQUIRED'):
            self.classify([], fill_witness=witness)

    def test_invalid_geometry_and_duplicate_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'VALID_FINITE_SOURCE_COPPER_REQUIRED'):
            classify_stroke('trace', box(0, 0, 0, 0), 1., 'segment', [])
        row = self.row(box(0, 0, 1, 1))
        with self.assertRaisesRegex(ValueError, 'DISTINCT_OTHER_SOURCE_IDENTITIES_REQUIRED'):
            self.classify([row, row])


class ParallelFillWitnessTests(unittest.TestCase):
    def row(self, sid, a, b, width=.1):
        return dict(id=sid, start_mm=a, end_mm=b, width_mm=width,
                    geometry=LineString([a, b]).buffer(width / 2))

    def test_overlapping_fill_has_source_bound_geometric_witness(self):
        a=self.row('a', [0, 0], [2, 0]); b=self.row('b', [0, .04], [2, .04])
        r=overlapping_parallel_fill_witness(a, b)
        self.assertEqual(r['neighbor_source_id'], 'b')
        self.assertEqual(r['longitudinal_overlap_mm'], 2.)
        self.assertAlmostEqual(r['lateral_mm'], .04)
        self.assertEqual(len(r['source_geometry_sha256']), 64)

    def test_disjoint_parallel_traces_and_collinear_caps_are_not_fill(self):
        a=self.row('a', [0, 0], [2, 0])
        self.assertIsNone(overlapping_parallel_fill_witness(a, self.row('b', [0, .2], [2, .2])))
        self.assertIsNone(overlapping_parallel_fill_witness(a, self.row('b', [1.95, 0], [4, 0])))

    def test_short_junction_and_crossing_are_not_long_parallel_fill(self):
        a=self.row('a', [0, 0], [2, 0])
        self.assertIsNone(overlapping_parallel_fill_witness(a, self.row('b', [1.95, .04], [4, .04])))
        self.assertIsNone(overlapping_parallel_fill_witness(a, self.row('b', [1, -1], [1, 1])))

    def test_native_coordinates_do_not_override_disjoint_copper_evidence(self):
        a=self.row('a', [0, 0], [2, 0]); b=self.row('b', [0, .04], [2, .04])
        b['geometry']=box(10, 10, 11, 11)
        self.assertIsNone(overlapping_parallel_fill_witness(a, b))
