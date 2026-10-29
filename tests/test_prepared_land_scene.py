import unittest
from shapely.geometry import box,Point
from src.prepared_land_scene import PreparedLandScene

class PreparedLandControls(unittest.TestCase):
    def land(self,candidate=None):
        core=box(0,0,.1,.1)
        return dict(id='land',original=core,candidate=core if candidate is None else candidate,native_source_kind='gr_poly',native_stroke_width_mm=0.)

    def test_fully_buried_circle_does_not_create_external_clearance(self):
        row=self.land(box(0,0,.11,.1));circle=Point(.095,.05).buffer(.004)
        checker=PreparedLandScene([row],[dict(id='covered',geometry=circle)])
        r=checker.check([row]);self.assertTrue(r['passed'])
        pair=r['lands'][0]['pairs'][0];self.assertEqual(pair['current_neighbor_visible_area_mm2'],0.)

    def test_exposed_circle_still_limits_growth(self):
        row=self.land(box(0,0,.11,.1));circle=Point(.12,.05).buffer(.005)
        r=PreparedLandScene([row],[dict(id='exposed',geometry=circle)]).check([row])
        self.assertFalse(r['passed']);self.assertEqual(r['failures'][0]['neighbor_id'],'exposed')

    def test_candidate_cannot_hide_a_new_contact(self):
        row=self.land(box(0,0,.13,.1));other=box(.12,.03,.14,.07)
        self.assertFalse(PreparedLandScene([row],[dict(id='other',geometry=other)]).check([row])['passed'])

    def test_exact_keep_preserves_inherited_small_gap(self):
        row=self.land();r=PreparedLandScene([row],[dict(id='old_gap',geometry=box(.101,0,.2,.1))]).check([row])
        self.assertTrue(r['passed']);self.assertTrue(r['lands'][0]['unchanged_source_identity'])

    def test_native_kind_or_stroke_change_fails_closed(self):
        row=self.land();checker=PreparedLandScene([row],[])
        with self.assertRaisesRegex(ValueError,'NATIVE_LAND_BINDING_CHANGED'):checker.check([dict(row,native_stroke_width_mm=.01)])
        with self.assertRaisesRegex(ValueError,'VERIFIED_ZERO_STROKE'):PreparedLandScene([dict(row,native_source_kind='segment')],[])
