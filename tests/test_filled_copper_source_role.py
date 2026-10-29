import unittest
from shapely.geometry import box,Point
from src.filled_copper_source_role import buried_route_witness

class FilledCopperSourceRoleControls(unittest.TestCase):
    def fill(self,g,**kw):return dict(id='fill',kind='gr_poly',trace_width_mm=0,geometry=g,**kw)
    def test_whole_route_in_fill_is_fixed_role_even_if_cap_can_protrude(self):
        r=buried_route_witness('s',[[.1,.5],[.99,.5]],[self.fill(box(0,0,1,1))])
        self.assertTrue(r['entire_native_route_in_original_fill']);self.assertFalse(r['source_geometry_modified'])
    def test_pad_entry_does_not_hide_exposed_trace(self):
        self.assertIsNone(buried_route_witness('s',[[-1,.5],[.5,.5]],[self.fill(box(0,0,1,1))]))
    def test_disjoint_pads_do_not_cover_intervening_route(self):
        a=self.fill(box(0,0,1,1));b=dict(a,id='b',geometry=box(2,0,3,1))
        self.assertIsNone(buried_route_witness('s',[[.5,.5],[2.5,.5]],[a,b]))
    def test_overlapping_stroke_is_not_a_filled_land_operand(self):
        a=dict(self.fill(box(0,0,1,1)),kind='segment',trace_width_mm=.1)
        with self.assertRaisesRegex(ValueError,'ORIGINAL_FILLED'):buried_route_witness('s',[[.1,.5],[.9,.5]],[a])
    def test_original_circle_fill_can_cover_buried_route(self):
        a=dict(self.fill(Point(0,0).buffer(1)),kind='gr_circle')
        self.assertIsNotNone(buried_route_witness('s',[[-.5,0],[.5,0]],[a]))
    def test_invalid_route_rejected(self):
        with self.assertRaises(ValueError):buried_route_witness('s',[[float('nan'),0],[1,0]],[])

class BulkBoundarySourceRoleControls(unittest.TestCase):
    def test_isolated_trace_not_bulk(self):
        from src.filled_copper_source_role import bulk_boundary_route_witness
        self.assertIsNone(bulk_boundary_route_witness('s',[[0,0],[4,0]],.1,box(-.1,-.05,4.1,.05)))
    def test_complete_broad_side_has_source_role_witness(self):
        from src.filled_copper_source_role import bulk_boundary_route_witness
        r=bulk_boundary_route_witness('s',[[0,0],[4,0]],.1,box(-.1,-.05,4.1,.4))
        self.assertTrue(r['entire_one_sided_strip_already_original_copper']);self.assertFalse(r['source_geometry_modified'])
    def test_pad_only_at_one_endpoint_not_bulk(self):
        from shapely.ops import unary_union
        from src.filled_copper_source_role import bulk_boundary_route_witness
        copper=unary_union([box(-.1,-.05,4.1,.05),box(3,-1,5,1)])
        self.assertIsNone(bulk_boundary_route_witness('s',[[0,0],[4,0]],.1,copper))
    def test_disjoint_parallel_traces_do_not_become_bulk(self):
        from shapely.ops import unary_union
        from src.filled_copper_source_role import bulk_boundary_route_witness
        copper=unary_union([box(-.1,-.05,4.1,.05),box(-.1,.1,4.1,.2)])
        self.assertIsNone(bulk_boundary_route_witness('s',[[0,0],[4,0]],.1,copper))
