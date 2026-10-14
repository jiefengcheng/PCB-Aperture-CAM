import unittest
from shapely import to_wkb
from shapely.geometry import box
from src.spatial_context import SpatialContext
from src.revision_catalog import digest,CatalogError

class SpatialContextTests(unittest.TestCase):
    def build(self,shapes,revision='r'):
        payloads={digest(to_wkb(g)):to_wkb(g) for g in shapes.values()}
        objects=[{'id':uid,'geometry_sha256':digest(to_wkb(g)),'layers':['F.Cu']} for uid,g in shapes.items()]
        return SpatialContext(revision,objects,payloads)
    def test_positive_distance_recall_matches_bruteforce(self):
        shapes={'a':box(0,0,1,1),'b':box(1.2,0,2,1),'c':box(2.1,0,3,1),'d':box(0,2,1,3)}
        ctx=self.build(shapes)
        for distance in [0,.1,.21,1,3]:
            for uid,shape in shapes.items():
                hits={r['id'] for r in ctx.query(uid,'F.Cu',distance_mm=distance)['matches']}
                brute={other for other,g in shapes.items() if other!=uid and shape.distance(g)<=distance}
                self.assertEqual(hits,brute)
        self.assertEqual(ctx.query('a','F.Cu')['matches'],[])
        self.assertEqual([r['id'] for r in ctx.query('a','F.Cu',distance_mm=.21)['matches']],['b'])
    def test_removal_and_shaving_split_components(self):
        original={'a':box(0,0,1,1),'bridge':box(1,0,2,1),'b':box(2,0,3,1)}
        self.assertEqual(len(self.build(original).topology()['components']),1)
        removed={k:v for k,v in original.items() if k!='bridge'}
        self.assertEqual(len(self.build(removed,'removed').topology()['components']),2)
        shaved={**original,'bridge':box(1.1,0,1.9,1)}
        self.assertEqual(len(self.build(shaved,'shaved').topology()['components']),3)
    def test_incomplete_missing_and_stale_are_not_empty_success(self):
        ctx=self.build({'a':box(0,0,1,1),'b':box(1,0,2,1)})
        self.assertEqual(ctx.query('a','F.Cu',limit=0)['status'],'TRUNCATED')
        self.assertEqual(ctx.query('a','F.Cu',cancel=lambda:True)['status'],'CANCELLED')
        with self.assertRaisesRegex(CatalogError,'STALE_SPATIAL_SNAPSHOT'):ctx.query('a','F.Cu',expected_snapshot='wrong')
        with self.assertRaisesRegex(CatalogError,'LAYER_INDEX_UNAVAILABLE'):ctx.query('a','B.Cu')

    def test_extreme_distance_overflow_is_explicit_error(self):
        import sys
        ctx=self.build({'a':box(1e308,0,1.1e308,1)})
        with self.assertRaisesRegex(CatalogError,'SPATIAL_ENVELOPE_OVERFLOW'):
            ctx.query('a','F.Cu',distance_mm=sys.float_info.max)
