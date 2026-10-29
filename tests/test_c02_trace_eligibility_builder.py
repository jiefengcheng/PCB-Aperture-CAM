import hashlib
import unittest
from tools.build_c02_trace_eligibility import native_rows, edge_runs, native_edge_points, select_complete_parent_runs


class EligibilityBuilderControls(unittest.TestCase):
    def fixture(self, layer='F.Cu'):
        source = ('(segment (start 0 0) (end 1 0) (width 0.1) (layer "' + layer + '"))').encode()
        sid = hashlib.sha256(source).hexdigest() + ':bytes:0:' + str(len(source))
        return source, sid, {sid: dict(kind='segment', trace_width_mm=.1)}

    def test_native_fragment_and_width_binding(self):
        source, sid, meta = self.fixture()
        row = native_rows(source, meta, [sid])[sid]
        self.assertEqual(row['width'], .1)
        self.assertEqual(row['fragment_sha256'], hashlib.sha256(source).hexdigest())

    def test_corrupt_source_wrong_width_and_wrong_layer_fail_for_their_reason(self):
        source, sid, meta = self.fixture()
        with self.assertRaisesRegex(ValueError, 'SOURCE_HASH_OR_ID_MISMATCH'):
            native_rows(source+b' ', meta, [sid])
        meta[sid]['trace_width_mm'] = .2
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_WIDTH_NOT_VERIFIED'):
            native_rows(source, meta, [sid])
        source, sid, meta = self.fixture('B.Cu')
        with self.assertRaisesRegex(ValueError, 'SUPPORTED_NATIVE_FCU_TRACE_REQUIRED'):
            native_rows(source, meta, [sid])

    def parent(self, closed=False):
        edges = [dict(source_alias_ids=[s], start_decimal_mm=[str(i), '0'],
                      end_decimal_mm=[str((i+1) % 3 if closed else i+1), '0'])
                 for i, s in enumerate(('a', 'b', 'c'))]
        return dict(ordered_source_edges=edges, route_type='CLOSED_UNIFORM_SOURCE_ROUTE' if closed else 'OPEN_UNIFORM_SOURCE_ROUTE')

    def test_excluding_middle_stroke_keeps_exact_original_edge_boundaries(self):
        p = self.parent()
        self.assertEqual(edge_runs(p, {'a', 'c'}), [[p['ordered_source_edges'][0]], [p['ordered_source_edges'][2]]])

    def test_closed_route_wrap_preserves_native_order(self):
        p = self.parent(True)
        self.assertEqual(edge_runs(p, {'a', 'c'}), [[p['ordered_source_edges'][2], p['ordered_source_edges'][0]]])

    def test_aliases_cannot_receive_conflicting_eligibility(self):
        p = self.parent()
        p['ordered_source_edges'][0]['source_alias_ids'].append('a_alias')
        with self.assertRaisesRegex(ValueError, 'ALIAS_ELIGIBILITY_CONFLICT'):
            edge_runs(p, {'a'})

    def test_original_native_endpoints_can_reverse_but_cannot_move(self):
        native = {'a': dict(kind='segment', attrs=dict(start=[0, 0], end=[1, 0]))}
        edge = dict(representative_source_id='a', start_decimal_mm=['1', '0'], end_decimal_mm=['0', '0'])
        self.assertEqual(native_edge_points(edge, native), [[1., 0.], [0., 0.]])
        edge['start_decimal_mm'] = ['2', '0']
        with self.assertRaisesRegex(ValueError, 'NATIVE_EDGE_ENDPOINT_BINDING_CHANGED'):
            native_edge_points(edge, native)


class CompleteParentSelectionControls(unittest.TestCase):
    def test_remote_eligible_runs_follow_visible_parent_but_unrelated_remote_stays_fixed(self):
        rows=[dict(parent_route_id='P',definition_status='VISIBLE_COMPLETE_UNIFORM_PATH_PROPOSAL_CONTACT_CHECKS_RETAINED'),
              dict(parent_route_id='P',definition_status='SOURCE_PATH_VISIBLE_ONLY_OUTSIDE_CROP_CONTEXT'),
              dict(parent_route_id='Q',definition_status='SOURCE_PATH_VISIBLE_ONLY_OUTSIDE_CROP_CONTEXT')]
        select_complete_parent_runs(rows)
        self.assertTrue(rows[1]['definition_status'].startswith('VISIBLE'))
        self.assertEqual(rows[1]['selection_role'],'REMOTE_ELIGIBLE_RUN_OF_CROP_SELECTED_ORIGINAL_TRACE')
        self.assertFalse(rows[2]['definition_status'].startswith('VISIBLE'))

    def test_remote_selection_does_not_depend_on_input_order(self):
        rows=[dict(parent_route_id='P',definition_status='SOURCE_PATH_VISIBLE_ONLY_OUTSIDE_CROP_CONTEXT'),
              dict(parent_route_id='P',definition_status='VISIBLE_COMPLETE_UNIFORM_PATH_PROPOSAL_CONTACT_CHECKS_RETAINED')]
        select_complete_parent_runs(rows)
        self.assertTrue(all(r['definition_status'].startswith('VISIBLE') for r in rows))
