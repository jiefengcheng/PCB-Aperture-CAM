import unittest
from src.primary_parallel_cohorts import choose_primary_cohorts

class PrimaryCohortControls(unittest.TestCase):
    def candidate(self,i,m,e,s):return dict(candidate_id=i,members=m,edges=e,score=s)
    def test_route_visiting_two_bundles_does_not_fuse_them(self):
        c=[self.candidate('top',['wrap','a','b'],[['wrap','a'],['a','b']],10),self.candidate('bottom',['wrap','c','d'],[['wrap','c'],['c','d']],8)]
        r=choose_primary_cohorts(['wrap','a','b','c','d'],c)
        self.assertEqual({tuple(x['units']) for x in r},{('a','b','wrap'),('c','d')})
    def test_no_unproven_connection_after_bridge_assigned_elsewhere(self):
        c=[self.candidate('strong',['x','q'],[['x','q']],10),self.candidate('weak',['a','x','b'],[['a','x'],['x','b']],5)]
        r=choose_primary_cohorts(['a','x','b','q'],c)
        self.assertIn(['a'],[x['units'] for x in r]);self.assertIn(['b'],[x['units'] for x in r])
    def test_order_independent_and_singletons_retained(self):
        c=[self.candidate('a',['a','b'],[['a','b']],4),self.candidate('b',['c','d'],[['c','d']],2)]
        self.assertEqual(choose_primary_cohorts(['a','b','c','d','e'],c),choose_primary_cohorts(['e','d','c','b','a'],list(reversed(c))))
    def test_unknown_member_rejected(self):
        with self.assertRaises(ValueError):choose_primary_cohorts(['a'],[self.candidate('bad',['a','x'],[['a','x']],1)])

class StationSpacingControls(unittest.TestCase):
    def edge(self,a,b,g):return dict(port_a=a,port_b=b,surface_gap_mm=g)
    def test_large_bridge_between_two_bundles_is_not_equality(self):
        from src.primary_parallel_cohorts import station_spacing_links
        a=self.edge('a','b',.05);bridge=self.edge('b','c',.17);b=self.edge('c','d',.05)
        keep,reject=station_spacing_links([a,bridge,b]);self.assertEqual(keep,[a,b]);self.assertEqual(reject,[bridge])
    def test_regular_bundle_and_isolated_pair_retained(self):
        from src.primary_parallel_cohorts import station_spacing_links
        e=[self.edge('a','b',.05),self.edge('b','c',.07),self.edge('x','y',.3)]
        self.assertEqual(station_spacing_links(e),(e,[]))
    def test_invalid_gap_rejected(self):
        from src.primary_parallel_cohorts import station_spacing_links
        with self.assertRaises(ValueError):station_spacing_links([self.edge('a','b',float('nan'))])
