import unittest
from shapely.geometry import LineString,box
from src.trace_width_clearance import verify_width_scene
from src.prepared_width_scene import PreparedWidthScene


def trace(sid,y=0.,f=1.5):
    route=LineString([(0,y),(2,y)])
    return dict(id=sid,original=route.buffer(.05,quad_segs=128),candidate=route.buffer(.05*f,quad_segs=128),verified_original_width_mm=.1)


class PreparedWidthSceneTests(unittest.TestCase):
    def compare(self,traces,fixed):
        old=verify_width_scene(traces,fixed);new=PreparedWidthScene(traces,fixed).check(traces,materialize_scene=True)
        self.assertEqual(old['passed'],new['passed']);self.assertEqual(old['failures'],new['failures'])
        self.assertEqual(old['candidate_union_wkb_sha256'],new['candidate_union_wkb_sha256'])
        for a,b in zip(old['traces'],new['traces']):
            self.assertEqual(a['pairs'],b['pairs'])

    def test_positive_fixed_attachment_matches_original_verifier(self):
        self.compare([trace('a')],[dict(id='land',geometry=box(-.3,-.2,.3,.2))])

    def test_simultaneous_bridge_and_neighbor_failures_match_original(self):
        self.compare([trace('a'),trace('b',y=.14)],[])

    def test_hidden_primitive_classification_matches_original(self):
        self.compare([trace('a')],[dict(id='land',geometry=box(-.3,-.2,.3,.2)),dict(id='hidden',geometry=box(.05,.055,.2,.07))])

    def test_exact_keep_is_zero_growth_and_does_not_repair_inherited_gap(self):
        t=trace('a',f=1.);r=PreparedWidthScene([t],[dict(id='old',geometry=box(0,.055,2,.2))]).check([t])
        self.assertTrue(r['passed']);self.assertEqual(r['new_exposed_copper_area_mm2'],0)
        self.assertTrue(r['traces'][0]['unchanged_source_identity']);self.assertEqual(r['traces'][0]['pairs'],[])

    def test_prepared_context_rejects_original_identity_changes(self):
        t=trace('a');context=PreparedWidthScene([t],[]);bad=dict(t,original=box(20,20,21,21))
        with self.assertRaisesRegex(ValueError,'ORIGINAL_TRACE_BINDING_CHANGED'):context.check([bad])

    def test_reused_context_matches_fresh_checks_over_multiple_scales(self):
        t=trace('a');fixed=[dict(id='obstacle',geometry=box(1,.09,3,.2))];context=PreparedWidthScene([t],fixed)
        for factor in [1.01,1.1,1.3,1.5]:
            tt=trace('a',f=factor);old=verify_width_scene([tt],fixed);new=context.check([tt],materialize_scene=True)
            self.assertEqual(old['traces'][0]['pairs'],new['traces'][0]['pairs']);self.assertEqual(old['passed'],new['passed'])

    def test_unchanged_neighbor_cannot_hide_a_new_bridge_from_growing_trace(self):
        traces=[trace('a'),trace('b',y=.12,f=1.)]
        r=PreparedWidthScene(traces,[]).check(traces)
        self.assertFalse(r['passed'])
        self.assertTrue(any(f['trace_id']=='a' and f['neighbor_id']=='b' for f in r['failures']))
        self.assertTrue(r['traces'][1]['unchanged_source_identity'])

    def test_fast_rejection_retains_first_exact_witness_and_never_claims_pass(self):
        traces=[trace('a'),trace('b',y=.14)]
        context=PreparedWidthScene(traces,[])
        fast=context.check(traces,fail_fast=True);full=context.check(traces)
        self.assertFalse(fast['passed']);self.assertFalse(fast['evaluation_complete'])
        self.assertEqual(fast['failures'][0],full['failures'][0])

    def test_passing_fast_mode_still_checks_complete_scene(self):
        traces=[trace('a'),trace('b',y=.3)];r=PreparedWidthScene(traces,[]).check(traces,fail_fast=True)
        self.assertTrue(r['passed']);self.assertTrue(r['evaluation_complete']);self.assertEqual(r['checked_trace_count'],2)

    def test_primitive_decomposition_changes_the_declared_route_target_scope(self):
        from shapely.ops import unary_union
        routes=[[(0,0),(2,0)],[(2,0),(2,.14)],[(2,.14),(0,.14)]]
        pieces=[dict(id=str(i),original=LineString(p).buffer(.05,quad_segs=128),candidate=LineString(p).buffer(.075,quad_segs=128),verified_original_width_mm=.1) for i,p in enumerate(routes)]
        joined=dict(id='whole-route',original=unary_union([r['original'] for r in pieces]),candidate=unary_union([r['candidate'] for r in pieces]),verified_original_width_mm=.1)
        # The two representations apply different target/contact operands. The
        # primitive diagnostic is not an adopted whole-route acceptance rule.
        self.assertTrue(PreparedWidthScene([joined],[]).check([joined])['passed'])
        checked=PreparedWidthScene(pieces,[]).check(pieces)
        self.assertFalse(checked['passed'])
        self.assertTrue(any({f['trace_id'],f['neighbor_id']}=={'0','2'} for f in checked['failures']))


if __name__=='__main__':unittest.main()
