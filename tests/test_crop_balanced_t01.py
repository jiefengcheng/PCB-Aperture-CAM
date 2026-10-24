import unittest,math
from shapely.affinity import rotate
from shapely.geometry import Point
from src.crop_balanced_t01 import CropSettings,WorkingScene,local_groups,freeze_factors,execute
from tools.audit_crop_balanced_t01 import parts


def fixture(centers=((0,0),(4,0)),extra=None):
    sites=[];rows=[];shapes=[]
    for i,c in enumerate(centers):
        sid=chr(65+i);g=Point(*c).buffer(1,quad_segs=128)
        sites.append({'source_id':sid,'aliases':[sid],'core':g,'center':list(c),'radius':1.,'indexes':[i],'physical_contact_group':sid})
        rows.append({'id':sid,'kind':'gr_circle'});shapes.append(g)
    if extra:
        rows.append({'id':'fixed','kind':'gr_circle'});shapes.append(Point(*extra).buffer(1,quad_segs=128))
    return sites,WorkingScene(b'',rows,shapes,sites),rows,shapes


class BalancedCropTests(unittest.TestCase):
    def test_fresh_verifier_treats_empty_addition_as_no_components(self):
        source=Point(0,0).buffer(1)
        self.assertEqual(parts(source.difference(source)),[])

    def test_unchanged_native_circle_phase_preserves_exact_source_core(self):
        sites,scene,rows,shapes=fixture()
        native=rotate(Point(0,0).buffer(1,quad_segs=32),.8,origin=(0,0))
        sites[0]['core']=native;shapes[0]=native
        self.assertGreater(native.difference(Point(0,0).buffer(1,quad_segs=128)).area,1e-10)
        groups=local_groups(sites,['A','B']);groups[0]['factor']=1.
        result=execute(b'',rows,shapes,sites,groups,{'ca':'A'})
        self.assertTrue(result['scene'].accepted['A'].equals_exact(native,0))
        self.assertTrue(all(d['verification']['passed'] for d in result['decisions']))
        self.assertFalse(result['failed_patches'])

    def test_local_groups_do_not_transitively_share_one_factor(self):
        sites,_,_,_=fixture(((0,0),(2.8,0),(5.6,0),(8.4,0),(11.2,0)))
        groups=local_groups(sites,['A','B'])
        self.assertEqual(groups[0]['site_ids'],['A','B'])
        self.assertTrue(all(len(g['site_ids'])<=2 for g in groups))
        self.assertEqual(sorted(i for g in groups for i in g['site_ids']),list('ABCDE'))

    def test_stale_scene_and_index_are_rejected(self):
        sites,scene,_,_=fixture()
        scene.commit(sites[0],sites[0]['core'],0)
        with self.assertRaisesRegex(ValueError,'STALE'):scene.obstacles(sites[1],0)
        scene.index_revision=0
        with self.assertRaisesRegex(ValueError,'STALE'):scene.obstacles(sites[1],1)
        with self.assertRaisesRegex(ValueError,'STALE'):scene.commit(sites[1],sites[1]['core'],0)

    def test_scene_rebuild_exposes_actual_accepted_growth(self):
        sites,scene,_,_=fixture(((0,0),(2.8,0)))
        candidate=Point(0,0).buffer(1.4,quad_segs=128)
        scene.commit(sites[0],candidate,0)
        row=next(r for r in scene.obstacles(sites[1],1) if r['source_id']=='A')
        self.assertTrue(row['geometry'].equals(candidate));self.assertEqual(scene.index_revision,scene.revision)

    def test_same_seed_and_policy_respond_to_crowding(self):
        values=[]
        for extra in [None,(0,2.3)]:
            sites,scene,_,_=fixture(extra=extra);groups=local_groups(sites,['A','B'])
            f,_,_=freeze_factors(sites,groups,{'componentA':'A'},scene)
            values.append(f['G01'])
        self.assertLess(values[1],values[0]);self.assertLessEqual(max(values),1.5)

    def test_joint_round_reservations_preserve_shared_factors_and_gap(self):
        sites,scene,_,_=fixture(((0,0),(2.5,0)))
        groups=local_groups(sites,['A','B']);f,_,_=freeze_factors(sites,groups,{'ca':'A','cb':'B'},scene)
        radius=f['G01']
        self.assertGreaterEqual(2.5-2*radius,.020)
        result=execute(b'',scene.rows,scene.original,sites,groups,{'ca':'A','cb':'B'})
        self.assertTrue(all(r['verification']['passed'] for r in result['decisions']))
        self.assertEqual(result['decisions'][0]['factor'],result['decisions'][1]['factor'])

    def test_cap_and_core_corruption_rejected_before_atomic_commit(self):
        sites,scene,_,_=fixture()
        for candidate in [Point(0,0).buffer(1.6),Point(0,0).buffer(.9)]:
            with self.assertRaisesRegex(ValueError,'CORE_OR_HARD_CAP'):scene.commit(sites[0],candidate,0)
        self.assertEqual(scene.revision,0)

if __name__=='__main__':unittest.main()
