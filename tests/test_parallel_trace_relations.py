import unittest
from src.parallel_trace_relations import parallel_relation,relation_groups


class ParallelRelationTests(unittest.TestCase):
    def test_reversed_source_direction_does_not_change_parallel_relation(self):
        a=[[0,0],[2,0]];b=[[2,.2],[0,.2]]
        q=parallel_relation(a,b)
        self.assertEqual(q['shared_projected_length_mm'],2)
        self.assertEqual(q['midpoint_cross_section_mm'],[[1.,0.],[1.,.2]])

    def test_crossing_short_or_distant_routes_not_grouped(self):
        a=[[0,0],[2,0]]
        for b in ([[1,-1],[1,1]],[[1,.2],[1.1,.2]],[[0,2],[2,2]]):
            self.assertIsNone(parallel_relation(a,b))

    def test_near_vertical_opposite_parameterizations_are_parallel(self):
        self.assertIsNotNone(parallel_relation([[0,0],[.001,2]],[[.2,2],[.201,0]]))

    def test_group_propagates_common_membership_and_keeps_singletons(self):
        self.assertEqual(relation_groups(['a','b','c','d'],[('a','b'),('b','c')]),[['a','b','c'],['d']])

    def test_unknown_member_rejected(self):
        with self.assertRaisesRegex(ValueError,'INVALID_MEMBER_RELATION'):
            relation_groups(['a'],[('a','missing')])


if __name__=='__main__':unittest.main()
