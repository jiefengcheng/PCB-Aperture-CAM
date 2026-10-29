import unittest
from shapely.geometry import box
from src.source_bulk_components import bind_bulk_regions,source_bulk_role

class SourceBulkComponentControls(unittest.TestCase):
    def test_selected_background_does_not_select_separate_trace(self):
        background=box(0,0,5,5);trace=box(6,0,6.1,4)
        selected,_=bind_bulk_regions([background,trace],[dict(name='owner_bg',point_mm=[1,1])])
        self.assertIsNotNone(source_bulk_role('bulk',box(.1,.1,1,1),selected))
        self.assertIsNone(source_bulk_role('trace',trace,selected))
    def test_repeated_seeds_bind_same_bulk_object_once(self):
        selected,b=bind_bulk_regions([box(0,0,5,5)],[dict(name='a',point_mm=[1,1]),dict(name='b',point_mm=[2,2])])
        self.assertEqual(len(selected),1);self.assertEqual(len(b),2)
    def test_missing_seed_fails_closed(self):
        with self.assertRaises(ValueError):bind_bulk_regions([box(0,0,1,1)],[dict(name='bad',point_mm=[3,3])])
    def test_role_does_not_grant_clearance_or_net_exemption(self):
        selected,_=bind_bulk_regions([box(0,0,5,5)],[dict(name='bg',point_mm=[1,1])]);r=source_bulk_role('s',box(0,0,1,1),selected)
        self.assertEqual(r['clearance_exemption'],'NONE');self.assertEqual(r['electrical_claim'],'NONE');self.assertFalse(r['source_copper_modified'])
    def test_remote_connection_does_not_hide_exposed_crop_trace(self):
        background=box(0,0,1,4);trace=box(2,0,2.1,4);outside_bridge=box(0,3,2.1,3.2);scope=box(-.5,-.5,2.5,2.5)
        selected,_=bind_bulk_regions([background,trace,outside_bridge],[dict(name='bg',point_mm=[.5,.5])],scope=scope)
        self.assertIsNone(source_bulk_role('trace',trace,selected,scope=scope))
        self.assertIsNotNone(source_bulk_role('background',background,selected,scope=scope))
