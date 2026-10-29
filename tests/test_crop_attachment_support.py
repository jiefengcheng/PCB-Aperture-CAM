import hashlib
import unittest
from dataclasses import replace
from shapely import from_wkb
from shapely.affinity import scale, translate
from shapely.geometry import box
from src.crop_attachment_support import bind_original_trace_attachment
from src.crop_stage_growth import GrowthContract, check_proposal


class OriginalAttachmentSupportTests(unittest.TestCase):
    def setup_case(self, *, feed_width='.10008', feed_start='23.647 -14.232'):
        fragments = [
            '(gr_poly (pts (xy 23.60399 -14.188) (xy 23.30401 -14.188) (xy 23.30401 -13.838) (xy 23.60399 -13.838)) (stroke (width 0) (type solid)) (fill yes) (layer F.Cu))',
            '(arc (start 24 -14.379) (mid 23.80908 -14.34029) (end 23.647 -14.232) (width .10008) (layer F.Cu))',
            f'(segment (start {feed_start}) (end 23.454 -14.039) (width {feed_width}) (layer F.Cu))',
        ]
        source = ('(kicad_pcb\n'+'\n'.join(fragments)+'\n)').encode()
        prefix = hashlib.sha256(source).hexdigest()+':bytes:'
        ids = [prefix+str(source.index(f.encode()))+':'+str(source.index(f.encode())+len(f)) for f in fragments]
        return source, ids

    def bound_case(self):
        source, ids = self.setup_case()
        support = bind_original_trace_attachment(source,*ids)
        core = from_wkb(support.target_wkb)
        arc,feed = from_wkb(support.obstacle_wkb),from_wkb(support.feed_wkb)
        neighbors = [{'source_id':sid,'original':g,'geometry':g,'trace_width_mm':support.original_width_mm}
                     for sid,g in [(support.obstacle_id,arc),(support.feed_id,feed)]]
        return support,core,neighbors

    def test_positive_control_is_filled_source_attachment_not_clearance_waiver(self):
        support,core,neighbors = self.bound_case()
        candidate = scale(core,1.01,1.01,origin=core.centroid)
        self.assertFalse(check_proposal(core,candidate,neighbors)['passed'])
        result = check_proposal(core,candidate,neighbors,attachment_supports=[support])
        self.assertTrue(result['passed'])
        arc = result['pairs'][0]
        self.assertFalse(arc['original_source_contact'])
        self.assertGreater(arc['exposed_added_copper_to_full_obstacle_gap_mm'],.02010)
        self.assertGreater(arc['candidate_to_obstacle_outside_original_port_gap_mm'],.02010)

    def test_width_mismatch_or_near_endpoint_cannot_create_permission(self):
        for options in [{'feed_width':'.10009'}, {'feed_start':'23.647001 -14.232'}]:
            source,ids = self.setup_case(**options)
            with self.assertRaises(ValueError):
                bind_original_trace_attachment(source,*ids)

    def test_changed_source_hash_is_rejected(self):
        source,ids = self.setup_case()
        with self.assertRaisesRegex(ValueError,'SOURCE_HASH'):
            bind_original_trace_attachment(source+b' ',*ids)

    def test_missing_or_moved_support_cannot_enable_growth(self):
        support,core,neighbors = self.bound_case()
        candidate = scale(core,1.01,1.01,origin=core.centroid)
        self.assertFalse(check_proposal(core,candidate,neighbors[:1],attachment_supports=[support])['passed'])
        neighbors[1] = {**neighbors[1],'geometry':translate(neighbors[1]['geometry'],.001,0)}
        self.assertFalse(check_proposal(core,candidate,neighbors,attachment_supports=[support])['passed'])

    def test_enlarged_ports_or_weakened_floor_are_not_accepted(self):
        support,core,neighbors = self.bound_case()
        candidate = scale(core,1.01,1.01,origin=core.centroid)
        for contract in [replace(GrowthContract(),attachment_buffer_gap_mm=.2),
                         replace(GrowthContract(),hard_gap_mm=.001),
                         replace(GrowthContract(),construction_gap_mm=.001)]:
            with self.assertRaises(ValueError):
                check_proposal(core,candidate,neighbors,attachment_supports=[support],contract=contract)

    def test_new_contact_still_fails_inside_qualified_attachment(self):
        support,core,neighbors = self.bound_case()
        candidate = scale(core,1.25,1.25,origin=core.centroid)
        result = check_proposal(core,candidate,neighbors,attachment_supports=[support])
        self.assertFalse(result['passed'])
        self.assertIn('NEW_SOURCE_CONTACT',[f['reason'] for f in result['failures']])

    def test_unrelated_copper_has_no_component_exemption(self):
        support,core,neighbors = self.bound_case()
        candidate = scale(core,1.01,1.01,origin=core.centroid)
        other = box(core.bounds[2]+.001,-14.1,core.bounds[2]+.002,-13.9)
        neighbors.append({'source_id':'unrelated','original':other,'geometry':other,
                          'trace_width_mm':0,'physical_component':'same-as-feed'})
        result = check_proposal(core,candidate,neighbors,attachment_supports=[support])
        self.assertFalse(result['passed'])
        self.assertTrue(any(f['neighbor_id']=='unrelated' for f in result['failures']))


if __name__ == '__main__':
    unittest.main()
