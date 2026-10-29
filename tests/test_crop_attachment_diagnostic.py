import hashlib
import unittest
from dataclasses import replace
from shapely import from_wkb
from shapely.affinity import scale, translate
from shapely.geometry import box
from src.crop_attachment_diagnostic import (
    bind_circle_attachment, bind_overlapping_feed_attachment, check_attachment_diagnostic)
from src.crop_stage_growth import GrowthContract


def source(*fragments):
    data = '\n'.join(fragments).encode()
    prefix = hashlib.sha256(data).hexdigest()+':bytes:'
    ids = []
    start = 0
    for fragment in fragments:
        end = start+len(fragment.encode())
        ids.append(prefix+f'{start}:{end}')
        start = end+1
    return data, ids


RECT = '(gr_poly (pts (xy 0 0) (xy 1 0) (xy 1 1) (xy 0 1)) (stroke (width 0) (type solid)) (fill yes) (layer F.Cu))'
CIRCLE = '(gr_circle (center .5 .95) (end .7 .95) (stroke (width 0) (type solid)) (fill yes) (layer F.Cu))'
FEED = '(segment (start -.2 0) (end 1.2 0) (width .05) (layer F.Cu) (net 0))'
OBSTACLE = '(segment (start -.2 -.04) (end 1.2 -.04) (width .05) (layer F.Cu) (net 0))'


class AttachmentDiagnosticTests(unittest.TestCase):
    def circle(self, text=CIRCLE):
        raw, ids = source(RECT,text)
        binding = bind_circle_attachment(raw,*ids)
        core = from_wkb(binding.target_wkb)
        circle = from_wkb(binding.obstacle_wkb)
        rows = [dict(source_id=ids[1],original=circle,geometry=circle,trace_width_mm=0.)]
        return binding,core,rows

    def feed(self):
        raw, ids = source(RECT,OBSTACLE,FEED)
        binding = bind_overlapping_feed_attachment(raw,*ids)
        core, ob, fg = map(from_wkb,(binding.target_wkb,binding.obstacle_wkb,binding.feed_wkb))
        rows = [dict(source_id=ids[1],original=ob,geometry=ob,trace_width_mm=.05),
                dict(source_id=ids[2],original=fg,geometry=fg,trace_width_mm=.05)]
        return binding,core,rows

    def check(self, binding, core, rows, factors=(1.001,1.), contract=None):
        return check_attachment_diagnostic(core,scale(core,*factors,origin=core.centroid),rows,binding,
            crop=box(-2,-2,3,3),cap=scale(core,1.25,1.25,origin=core.centroid),contract=contract or GrowthContract())

    def test_circle_positive_preserves_visible_surface_outside_original_port(self):
        b,c,n=self.circle();q=self.check(b,c,n)
        self.assertTrue(q['passed'])
        r=q['pairs'][-1]
        self.assertEqual(r['protected_visible_circle_new_coverage_mm2'],0.)
        self.assertGreater(r['checked_exposed_to_visible_circle_gap_mm'],.02010)

    def test_circle_cap_cannot_swallow_exposed_round_surface(self):
        b,c,n=self.circle();q=self.check(b,c,n,(1.25,1.25))
        self.assertFalse(q['passed'])
        self.assertIn('ORIGINAL_VISIBLE_CIRCLE_OUTSIDE_PORT_COVERED',[f['reason'] for f in q['failures']])

    def test_circle_no_component_exemption_for_unrelated_neighbor(self):
        b,c,n=self.circle();ob=box(1.0201,.2,1.2,.8)
        n.append(dict(source_id='unrelated',original=ob,geometry=ob,trace_width_mm=0.))
        q=self.check(b,c,n)
        self.assertFalse(q['passed'])
        self.assertTrue(any(f['neighbor_id']=='unrelated' for f in q['failures']))

    def test_circle_moved_current_source_fails_closed(self):
        b,c,n=self.circle();n[0]['geometry']=translate(n[0]['geometry'],.1,0)
        with self.assertRaisesRegex(ValueError,'STALE_OR_UNBOUND'):self.check(b,c,n)

    def test_circle_absent_original_contact_rejected(self):
        raw, ids=source(RECT,CIRCLE.replace('.5 .95','2 .95').replace('.7 .95','2.2 .95'))
        with self.assertRaisesRegex(ValueError,'NO_ORIGINAL'):bind_circle_attachment(raw,*ids)

    def test_fully_covered_circle_is_skipped(self):
        raw, ids=source(RECT,CIRCLE.replace('.5 .95','.5 .5').replace('.7 .95','.7 .5'))
        with self.assertRaisesRegex(ValueError,'FULLY_COVERED'):bind_circle_attachment(raw,*ids)

    def test_circle_port_and_guard_policy_cannot_be_changed(self):
        b,c,n=self.circle()
        for policy in (replace(GrowthContract(),attachment_buffer_gap_mm=.02011),
                       replace(GrowthContract(),construction_gap_mm=.02000)):
            with self.assertRaisesRegex(ValueError,'UNCHANGED_CONTRACT'):self.check(b,c,n,contract=policy)

    def test_overlapping_feed_needs_no_fictitious_shared_endpoint(self):
        b,c,n=self.feed();q=self.check(b,c,n)
        self.assertTrue(q['passed'])
        self.assertGreater(q['pairs'][-1]['original_feed_obstacle_overlap_mm2'],0.)
        self.assertTrue(q['pairs'][-1]['original_raw_gap_filled_by_feed'])

    def test_feed_cap_new_contact_rejected(self):
        b,c,n=self.feed();q=self.check(b,c,n,(1.25,1.25))
        self.assertFalse(q['passed'])
        self.assertIn('NEW_SOURCE_CONTACT',[f['reason'] for f in q['failures']])

    def test_missing_or_changed_feed_fails_closed(self):
        b,c,n=self.feed()
        with self.assertRaisesRegex(ValueError,'STALE_OR_MISSING'):self.check(b,c,n[:1])
        n[1]['trace_width_mm']=.049
        with self.assertRaisesRegex(ValueError,'STALE_OR_MISSING'):self.check(b,c,n)

    def test_wrong_source_hash_rejected(self):
        raw,ids=source(RECT,OBSTACLE,FEED)
        with self.assertRaisesRegex(ValueError,'SOURCE_HASH'):bind_overlapping_feed_attachment(raw+b' ',*ids)

    def test_disconnected_feed_cannot_qualify_by_component_label(self):
        raw,ids=source(RECT,OBSTACLE,FEED.replace(' 0)', ' .5)'))
        with self.assertRaisesRegex(ValueError,'NO_SOURCE_BOUND'):bind_overlapping_feed_attachment(raw,*ids)


if __name__=='__main__':unittest.main()
