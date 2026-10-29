import unittest
from shapely.geometry import LineString,box
from src.trace_width_clearance import verify_width_scene


def trace(sid,start,end,width=.1,factor=1.5):
    route=LineString([start,end])
    return dict(id=sid,original=route.buffer(width/2,quad_segs=128),
                candidate=route.buffer(width*factor/2,quad_segs=128),verified_original_width_mm=width)


class TraceWidthClearanceTests(unittest.TestCase):
    def test_original_land_attachment_passes_and_port_does_not_expand_with_factor(self):
        fixed=[dict(id='land',geometry=box(-.3,-.2,.3,.2))]
        a=verify_width_scene([trace('a',(0,0),(2,0),factor=1.2)],fixed)
        b=verify_width_scene([trace('a',(0,0),(2,0),factor=1.5)],fixed)
        self.assertTrue(a['passed']);self.assertTrue(b['passed'])
        self.assertEqual(a['traces'][0]['pairs'][0]['original_port_wkb_sha256'],b['traces'][0]['pairs'][0]['original_port_wkb_sha256'])

    def test_remote_obstacle_limits_entire_full_trace(self):
        fixed=[dict(id='remote',geometry=box(29,.09,31,.2))]
        self.assertFalse(verify_width_scene([trace('a',(0,0),(30,0))],fixed)['passed'])
        self.assertTrue(verify_width_scene([trace('a',(0,0),(30,0),factor=1.3)],fixed)['passed'])

    def test_simultaneous_neighbors_checked_not_only_against_originals(self):
        a=trace('a',(0,0),(2,0));b=trace('b',(0,.17),(2,.17))
        fixed_b=[dict(id='b',geometry=b['original'],trace_width_mm=.1)]
        self.assertTrue(verify_width_scene([a],fixed_b)['passed'])
        self.assertFalse(verify_width_scene([a,b],[])['passed'])

    def test_covered_internal_primitive_does_not_create_false_failure(self):
        fixed=[dict(id='land',geometry=box(-.3,-.2,.3,.2)),
               dict(id='internal',geometry=box(.05,.055,.2,.07))]
        q=verify_width_scene([trace('a',(0,0),(2,0))],fixed)
        self.assertTrue(q['passed'])
        internal=next(p for p in q['traces'][0]['pairs'] if p['neighbor_id']=='internal')
        self.assertEqual(internal['current_neighbor_visible_area_mm2'],0)

    def test_new_bridge_cannot_hide_behind_other_new_candidate(self):
        a=trace('a',(0,0),(2,0));b=trace('b',(0,.14),(2,.14))
        q=verify_width_scene([a,b],[])
        self.assertFalse(q['passed'])
        self.assertTrue(any(p['new_exposed_to_visible_neighbor_gap_mm']==0 for r in q['traces'] for p in r['pairs']))

    def test_unchanged_inherited_small_gap_is_not_repair_target(self):
        fixed=[dict(id='old',geometry=box(0,.055,2,.2))]
        self.assertTrue(verify_width_scene([trace('a',(0,0),(2,0),factor=1.)],fixed)['passed'])
        self.assertFalse(verify_width_scene([trace('a',(0,0),(2,0),factor=1.1)],fixed)['passed'])

    def test_unrelated_obstacle_is_not_exempted_by_an_attachment_elsewhere(self):
        fixed=[dict(id='land',geometry=box(-.3,-.2,.3,.2)),
               dict(id='separate',geometry=box(1,.09,1.5,.2))]
        self.assertFalse(verify_width_scene([trace('a',(0,0),(2,0))],fixed)['passed'])

    def test_core_loss_rejects_even_if_clearance_is_large(self):
        a=trace('a',(0,0),(2,0));a['candidate']=a['original'].buffer(-.01)
        self.assertFalse(verify_width_scene([a],[])['passed'])


if __name__=='__main__':unittest.main()
