import unittest
from shapely.geometry import box
from src.trace_chain_contacts import qualify_chain


class TraceChainContactTests(unittest.TestCase):
    def component(self):
        return dict(source_ids=['a'],terminal_points_decimal_mm=[['0','0'],['2','0']],unresolved_reasons=[])

    def lands(self):
        return [dict(source_id='L',kind='gr_poly',geometry=box(-.2,-.2,.2,.2)),
                dict(source_id='R',kind='gr_poly',geometry=box(1.8,-.2,2.2,.2))]

    def test_two_land_terminals_qualified(self):
        q=qualify_chain(self.component(),{'a':box(0,-.05,2,.05)},self.lands())
        self.assertEqual(q['status'],'SOURCE_CHAIN_GEOMETRICALLY_QUALIFIED_FOR_WIDTH_FEASIBILITY')

    def test_interior_crossing_not_hidden_by_common_component(self):
        crossing=dict(source_id='cross',kind='segment',geometry=box(.9,-1,1.1,1))
        q=qualify_chain(self.component(),{'a':box(0,-.05,2,.05)},self.lands()+[crossing])
        self.assertIn('INTERIOR_TRACE_CONTACT_REQUIRES_JUNCTION_SCOPE',q['unresolved_reasons'])

    def test_original_contact_entirely_inside_terminal_land_is_internal(self):
        internal=dict(source_id='b',kind='segment',geometry=box(-.1,-.1,.1,.1))
        q=qualify_chain(self.component(),{'a':box(0,-.05,2,.05)},self.lands()+[internal])
        self.assertFalse(q['interior_trace_source_ids'])

    def test_covered_source_is_not_independent_width_target(self):
        q=qualify_chain(self.component(),{'a':box(0,-.05,2,.05)},
            [dict(source_id='plane',kind='gr_poly',geometry=box(-1,-1,3,1))])
        self.assertEqual(q['status'],'COVERED_SOURCE_TRACE_NO_INDEPENDENT_EXPOSED_ROUTE')

    def test_source_stroke_covered_by_other_trace_is_also_skipped(self):
        q=qualify_chain(self.component(),{'a':box(0,-.05,2,.05)},
            [dict(source_id='wide_trace',kind='segment',geometry=box(-1,-1,3,1))])
        self.assertEqual(q['status'],'COVERED_SOURCE_TRACE_NO_INDEPENDENT_EXPOSED_ROUTE')
        self.assertEqual(q['exposed_outside_all_other_source_copper_area_mm2'],0)


if __name__=='__main__':
    unittest.main()
