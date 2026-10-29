import unittest
from src.source_junction_paths import junction_source_paths


def row(sid,a,b,w=.1,sha=None):
    return dict(source_id=sid,width_mm=w,endpoints_decimal_mm=[[str(v) for v in a],[str(v) for v in b]],route_points_mm=[list(a),list(b)],source_wkb_sha256=sha or sid)


class SourceJunctionPathTests(unittest.TestCase):
    def test_t_junction_keeps_backbone_and_explicit_branch_port(self):
        rows=[row('a',(0,0),(1,0)),row('b',(1,0),(2,0)),row('c',(1,0),(1,1))]
        p=junction_source_paths(rows,['a','b','c'])
        self.assertEqual(sorted(r['source_ids'] for r in p),[['a','b'],['c']])
        self.assertTrue(all(r['original_junction_ports'][0]['point_decimal_mm']==['1','0'] for r in p))

    def test_four_way_cross_keeps_two_straight_routes_without_net_claim(self):
        rows=[row('a',(-1,0),(0,0)),row('b',(0,0),(1,0)),row('c',(0,-1),(0,0)),row('d',(0,0),(0,1))]
        p=junction_source_paths(rows,[r['source_id'] for r in rows])
        self.assertEqual(sorted(r['source_ids'] for r in p),[['a','b'],['c','d']])

    def test_aliases_preserve_ids_without_creating_false_closed_route(self):
        p=junction_source_paths([row('a',(0,0),(1,0),sha='same'),row('copy',(1,0),(0,0),sha='same')],['a','copy'])
        self.assertEqual(len(p),1);self.assertEqual(p[0]['source_ids'],['a','copy'])
        self.assertEqual(p[0]['route_type'],'OPEN_UNIFORM_SOURCE_ROUTE')

    def test_ambiguous_angled_junction_ends_routes_at_original_node(self):
        rows=[row('a',(0,0),(1,0)),row('b',(0,0),(-.5,.866)),row('c',(0,0),(-.5,-.866))]
        p=junction_source_paths(rows,['a','b','c']);self.assertEqual(len(p),3)
        self.assertTrue(all(r['original_junction_ports'] for r in p))

    def test_original_width_transition_is_not_joined_or_normalized(self):
        p=junction_source_paths([row('a',(0,0),(1,0)),row('b',(1,0),(2,0),.2)],['a','b'])
        self.assertEqual(len(p),2);self.assertTrue(all(r['original_width_transition_ports'] for r in p))

    def test_remote_members_preserved_to_original_junction(self):
        rows=[row('a',(0,0),(1,0)),row('remote',(1,0),(300,0)),row('branch',(300,0),(300,1))]
        p=junction_source_paths(rows,['a']);self.assertEqual(p[0]['source_ids'],['a','branch','remote'])

    def test_ordered_route_crosses_fragment_boundaries_and_reversed_edges(self):
        rows=[row('z',(0,0),(1,0)),row('a',(2,0),(1,0)),row('b',(2,0),(3,0))]
        p=junction_source_paths(rows,['z'])[0]
        points=p['ordered_route_points_mm']
        self.assertIn(points,[[[0.,0.],[1.,0.],[2.,0.],[3.,0.]],[[3.,0.],[2.,0.],[1.,0.],[0.,0.]]])
        self.assertEqual(len(p['ordered_source_edges']),3)

    def test_closed_route_traversal_visits_each_source_edge_once(self):
        rows=[row('a',(0,0),(1,0)),row('b',(1,0),(1,1)),row('c',(1,1),(0,0))]
        p=junction_source_paths(rows,['a'])[0]
        self.assertEqual(p['route_type'],'CLOSED_UNIFORM_SOURCE_ROUTE')
        self.assertEqual(len(p['ordered_source_edges']),3)
        self.assertEqual(p['ordered_route_points_mm'][0],p['ordered_route_points_mm'][-1])


if __name__=='__main__':unittest.main()
