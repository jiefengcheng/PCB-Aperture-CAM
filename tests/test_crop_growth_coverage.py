import unittest
from src.crop_growth_coverage import focused_rectangle_coverage


class CoverageTests(unittest.TestCase):
    def test_attachment_and_corner_candidates_both_selected_without_defect_claim(self):
        rectangles = [{'source_id': x} for x in ('a', 'b', 'c')]
        work = {'clearance_issues': [
            {'rectangle_source_id': 'a', 'trace_source_id': 'feed',
             'issue_type': 'EXISTING_ATTACHMENT_EXTENSION_REVIEW'},
        ], 'items': [
            {'rectangle_source_id': 'b', 'trace_source_id': 'arc',
             'interaction_class': 'NON_SIDE_DEFERRED'},
        ]}
        result = focused_rectangle_coverage(rectangles, work, [{'source_id': 'a', 'key': 'R11'}])
        self.assertEqual([r['selected'] for r in result], [True, True, False])
        self.assertEqual(result[0]['previous_eleven_site_key'], 'R11')
        self.assertEqual(result[0]['trace_work_references'][0]['original_record'], work['clearance_issues'][0])
        self.assertEqual(result[2]['selection_reason'], 'CONTEXT_ONLY_NO_TRACE_WORK_REFERENCE')

    def test_unknown_source_fails_instead_of_silent_omission(self):
        work = {'clearance_issues': [], 'items': [
            {'rectangle_source_id': 'missing', 'trace_source_id': 'arc'}]}
        with self.assertRaisesRegex(ValueError, 'NOT_IN_ELIGIBLE_SET'):
            focused_rectangle_coverage([{'source_id': 'a'}], work)

    def test_duplicate_inventory_source_fails(self):
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_RECTANGLE_SOURCE'):
            focused_rectangle_coverage([{'source_id': 'a'}, {'source_id': 'a'}],
                                       {'clearance_issues': [], 'items': []})
