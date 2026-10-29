import unittest
from src.uniform_source_paths import uniform_source_paths


def row(sid,a,b,w=.1):
    return dict(source_id=sid,endpoints_decimal_mm=[[str(v) for v in a],[str(v) for v in b]],width_mm=w)


class UniformSourcePathTests(unittest.TestCase):
    def test_width_transition_is_explicit_boundary_not_whole_component_rejection(self):
        p=uniform_source_paths([row('a',(0,0),(1,0)),row('b',(1,0),(2,0),.2)],['a','b'])
        self.assertEqual(len(p),2)
        for r in p:
            self.assertEqual(r['path_status'],'PROPOSED_COMPLETE_UNIFORM_SOURCE_PATH')
            self.assertEqual(len(r['original_width_transition_ports']),1)
            self.assertEqual(r['original_width_transition_ports'][0]['point_decimal_mm'],['1','0'])

    def test_branch_kept_as_entire_network_no_independent_branch_acceptance(self):
        p=uniform_source_paths([row('a',(0,0),(1,0)),row('b',(1,0),(2,0)),row('c',(1,0),(1,1))],['a'])
        self.assertEqual(len(p),1);self.assertEqual(p[0]['source_ids'],['a','b','c'])
        self.assertEqual(p[0]['path_status'],'COMPLETE_UNIFORM_NETWORK_REQUIRES_JUNCTION_ASSESSMENT')

    def test_remote_source_members_retained_until_original_width_transition(self):
        p=uniform_source_paths([row('a',(0,0),(1,0)),row('remote',(1,0),(300,0)),row('wide',(300,0),(301,0),.2)],['a'])
        self.assertEqual(p[0]['source_ids'],['a','remote'])
        self.assertEqual(p[0]['original_width_transition_ports'][0]['other_width_source_ids'],['wide'])

    def test_equal_decimal_endpoint_and_reverse_direction_join(self):
        p=uniform_source_paths([row('a',(0,0),('1.00',0)),row('b',(2,0),('1.0',0))],['a'])
        self.assertEqual(p[0]['source_ids'],['a','b'])

    def test_nearby_nonidentical_endpoints_are_not_silently_snapped(self):
        p=uniform_source_paths([row('a',(0,0),(1,0)),row('b',('1.000001',0),(2,0))],['a','b'])
        self.assertEqual(len(p),2)

    def test_invalid_width_rejected(self):
        with self.assertRaisesRegex(ValueError,'INVALID_ORIGINAL_TRACE'):
            uniform_source_paths([row('a',(0,0),(1,0),0)],['a'])


if __name__=='__main__':unittest.main()
