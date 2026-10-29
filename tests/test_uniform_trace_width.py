import hashlib
import unittest
from shapely import to_wkb
from src.crop_attachment_diagnostic import _decode
from src.uniform_trace_width import construct_uniform_width,construct_group_width


def fixture(parts):
    source='\n'.join(parts).encode();sha=hashlib.sha256(source).hexdigest()
    ids=[];rows={};blobs={};offset=0
    for part in parts:
        size=len(part.encode());sid=f'{sha}:bytes:{offset}:{offset+size}';offset+=size+1;ids.append(sid)
        _,((_,attrs,geometry,_),)=_decode(source,[sid]);blob=to_wkb(geometry)
        rows[sid]=dict(id=sid,geometry_sha256=hashlib.sha256(blob).hexdigest(),trace_width_mm=float(attrs['width'][0]))
        blobs[sid]=blob
    return source,dict(component_id='synthetic-source-chain',source_ids=ids,source_sha256=sha),rows,blobs


class UniformTraceWidthTests(unittest.TestCase):
    def source(self):
        return fixture(['(segment (start 0 0) (end 10 0) (width 0.1) (layer F.Cu) (net 0))',
                        '(segment (start 10 0) (end 30 0) (width 0.1) (layer F.Cu) (net 0))'])

    def test_full_route_including_remote_section_gets_same_width(self):
        args=self.source();r,_,old,new=construct_uniform_width(*args,1.5)
        self.assertEqual(len(r['primitives']),2)
        self.assertTrue(all(p['nominal_candidate_width_mm']==.1*1.5 for p in r['primitives']))
        self.assertEqual(r['primitives'][-1]['end_mm'],[30.,0.])
        self.assertTrue(new.covers(old));self.assertGreater(r['added_area_mm2'],0)

    def test_keep_retains_exact_original_source_blobs(self):
        args=self.source();r,parts,_,_=construct_uniform_width(*args,1.)
        for sid,g in parts.items():self.assertEqual(to_wkb(g),args[3][sid])
        self.assertEqual(r['added_area_mm2'],0)

    def test_missing_remote_member_not_silently_dropped(self):
        source,chain,rows,blobs=self.source();blobs.pop(chain['source_ids'][-1])
        with self.assertRaisesRegex(ValueError,'COMPLETE_CHAIN_MEMBER_MISSING'):
            construct_uniform_width(source,chain,rows,blobs,1.5)

    def test_mixed_width_rejected_without_splitting_trace(self):
        args=fixture(['(segment (start 0 0) (end 1 0) (width 0.1) (layer F.Cu) (net 0))',
                      '(segment (start 1 0) (end 2 0) (width 0.2) (layer F.Cu) (net 0))'])
        with self.assertRaisesRegex(ValueError,'MIXED_ORIGINAL_WIDTHS'):construct_uniform_width(*args,1.5)

    def test_neckdown_shrink_and_above_ceiling_not_expressible(self):
        for factor in ([1.5,1.1],.9,1.500001,float('nan'),True):
            with self.assertRaisesRegex(ValueError,'ONE_FINITE_COMMON_SCALE'):construct_uniform_width(*self.source(),factor)

    def test_arc_keeps_exact_source_route_points_and_terminals(self):
        args=fixture(['(arc (start 1 0) (mid 0.707106781 0.707106781) (end 0 1) (width 0.1) (layer F.Cu) (net 0))'])
        a,*_=construct_uniform_width(*args,1.)
        b,_,old,new=construct_uniform_width(*args,1.5)
        self.assertEqual(a['primitives'][0]['fixed_source_route_points_mm'],b['primitives'][0]['fixed_source_route_points_mm'])
        self.assertTrue(new.covers(old))

    def test_parallel_group_uses_one_factor_and_retains_individual_original_widths(self):
        source,chain,rows,blobs=fixture(['(segment (start 0 0) (end 2 0) (width 0.1) (layer F.Cu) (net 0))',
                                      '(segment (start 0 1) (end 2 1) (width 0.2) (layer F.Cu) (net 0))'])
        chains={str(i):dict(component_id=str(i),source_ids=[sid]) for i,sid in enumerate(chain['source_ids'])}
        group=dict(group_id='synthetic-parallel',members=['0','1'])
        r,_,_,_=construct_group_width(source,group,chains,rows,blobs,1.4)
        self.assertEqual([p['factor'] for p in r['trace_members']],[1.4,1.4])
        self.assertEqual([p['uniform_nominal_width_mm'] for p in r['trace_members']],[.1*1.4,.2*1.4])

    def test_singleton_group_has_same_constructor_and_full_route(self):
        source,chain,rows,blobs=self.source()
        r,parts,_,_=construct_group_width(source,dict(group_id='single',members=['trace']),{'trace':chain},rows,blobs,1.5)
        self.assertEqual(len(parts),2)
        self.assertEqual(r['common_factor'],1.5)

    def test_group_cannot_silently_omit_a_declared_trace(self):
        source,chain,rows,blobs=self.source()
        with self.assertRaisesRegex(ValueError,'COMPLETE_GROUP_MEMBER_MISSING'):
            construct_group_width(source,dict(group_id='bad',members=['trace','missing']),{'trace':chain},rows,blobs,1.5)


if __name__=='__main__':unittest.main()
