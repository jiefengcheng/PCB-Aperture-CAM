import hashlib
import unittest
from shapely import to_wkb
from shapely.geometry import box
from src.uniform_trace_width_v2 import construct_uniform_width,construct_group_width,FAMILY
from tests.test_uniform_trace_width import fixture


class NestedWidthFamilyTests(unittest.TestCase):
    def source(self):
        return fixture(['(arc (start 1 0) (mid 0.707106781 0.707106781) (end 0 1) (width 0.1) (layer F.Cu) (net 0))'])

    def test_nested_even_very_near_original_width(self):
        previous=None;quadrants=set()
        for factor in [1.,1.000001,1.001,1.02,1.2,1.5]:
            record,_,core,candidate=construct_uniform_width(*self.source(),factor)
            self.assertTrue(candidate.covers(core))
            if previous is not None:self.assertTrue(candidate.covers(previous))
            previous=candidate;quadrants.add(record['primitives'][0]['fixed_buffer_quadrant_segments'])
            self.assertEqual(record['geometry_family'],FAMILY)
        self.assertEqual(len(quadrants),1)

    def test_original_width_retains_exact_cached_bytes(self):
        args=self.source();_,parts,_,_=construct_uniform_width(*args,1.)
        for sid,g in parts.items():self.assertEqual(to_wkb(g),args[3][sid])

    def test_forged_far_away_cache_rejects_even_with_matching_forged_manifest_hash(self):
        source,chain,rows,blobs=self.source();sid=chain['source_ids'][0]
        blobs[sid]=to_wkb(box(100,100,101,101));rows[sid]['geometry_sha256']=hashlib.sha256(blobs[sid]).hexdigest()
        with self.assertRaisesRegex(ValueError,'SOURCE_CORE_OUTSIDE_DECLARED_ROUTE_ENVELOPE'):
            construct_uniform_width(source,chain,rows,blobs,1.)

    def test_singleton_uses_same_family_and_one_factor(self):
        source,chain,rows,blobs=self.source()
        r,_,_,_=construct_group_width(source,dict(group_id='g',members=['a']),{'a':chain},rows,blobs,1.5)
        self.assertEqual(r['geometry_family'],FAMILY);self.assertEqual(r['trace_members'][0]['factor'],1.5)

    def test_nominal_ceiling_is_not_relaxed_by_geometry_envelope(self):
        with self.assertRaisesRegex(ValueError,'ONE_FINITE_COMMON_SCALE'):
            construct_uniform_width(*self.source(),1.500001)


if __name__=='__main__':unittest.main()
