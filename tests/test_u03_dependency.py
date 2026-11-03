import random
from dataclasses import replace
import pytest
from shapely import STRtree
from shapely.geometry import LineString,Point,box
from shapely.affinity import translate
from src.u03_board.checker import IncrementalWidthScene
from src.u03_board.dependency import DependencyWidthScene,ProofGraph,Certificates
from src.prepared_width_scene import PreparedWidthScene


def scene():
    cores=[LineString([(0,y),(1,y)]).buffer(.05) for y in (0,.16,.33,4)]
    return [dict(id=str(i),original=g,candidate=g,verified_original_width_mm=.1) for i,g in enumerate(cores)], [dict(id='land',geometry=box(1.1,-.2,1.4,.5))]


def trial(rows,factors):
    return [dict(r,candidate=r['original'] if f==1 else r['original'].buffer(.05*(f-1))) for r,f in zip(rows,factors)]


def test_rtree_views_match_legacy_queries_including_boundary_and_fallback():
    rows,fixed=scene();d=DependencyWidthScene(rows,fixed);rng=random.Random(7)
    for factors in [(1,1,1,1),(1.5,1.3,1,1.5)]:
        current=dict(d.original,**{r['id']:r['candidate'] for r in trial(rows,factors)})
        indexed=d.spatial_index(current);legacy=STRtree([current[s] for s in d.ids])
        for _ in range(100):
            x,y=rng.uniform(-.2,1.4),rng.uniform(-.3,4.3);q=box(x,y,x+.1,y+.1)
            assert set(indexed.query(q))==set(legacy.query(q))
        for g in current.values():
            x0,y0,x1,y1=g.bounds
            for q in (Point(x0,y0),Point(x1,y1),g.envelope.buffer(.0201+1e-12)):
                assert set(indexed.query(q))==set(legacy.query(q))
    current=dict(d.original);current['0']=translate(current['0'],xoff=50)
    assert isinstance(d.spatial_index(current),STRtree) and d.index_fallbacks==1


@pytest.mark.parametrize('budget',[0,1024,32*1024**2])
def test_complete_reports_match_across_rejection_rollback_and_changed_neighbors(budget):
    rows,fixed=scene();old=IncrementalWidthScene(rows,fixed)
    new=DependencyWidthScene(rows,fixed,proof_budget=budget,geometry_budget=budget)
    rng=random.Random(8)
    factors=[(1,1,1,1),(1.5,1,1,1),(1.5,1.5,1.5,1),(1,1,1,1),
             *(tuple(rng.choice([1.,1.1,1.25,1.5]) for _ in rows) for _ in range(80))]
    for f in factors:
        t=trial(rows,f)
        assert new.check(t,fail_fast=True)==old.check(t,fail_fast=True)
        assert new.routes.weight+new.pairs.weight<=budget
        assert new.geometry_weight<=budget
    t=trial(rows,(1.1,1.1,1.1,1.1))
    assert new.check(t,materialize_scene=True)==old.check(t,materialize_scene=True)
    assert new.routes.weight==new.pairs.weight==0


def test_active_dependency_graph_invalidates_locally_and_reuses_proofs():
    rows,fixed=scene();d=DependencyWidthScene(rows,fixed)
    assert d.check(rows,fail_fast=True)['passed']
    distant=d.graph.active['3']
    q=d.check(trial(rows,(1.1,1,1,1)),fail_fast=True)
    assert q['passed'] and d.graph.active['3']==distant
    assert d.check(rows,fail_fast=True)['passed']
    assert d.graph.invalidated>0 and d.routes.hits>0
    # Both insertion and withdrawal outside the supported frame use exact fallback.
    old=IncrementalWidthScene(rows,fixed);old.check(rows,fail_fast=True)
    old.check(trial(rows,(1.1,1,1,1)),fail_fast=True);old.check(rows,fail_fast=True)
    for y in (.12,4.,.16):
        t=list(rows);t[3]=dict(rows[3],candidate=translate(rows[3]['original'],yoff=y-4))
        # Original core removal must still reject, even if it approaches a cached piece.
        assert d.check(t,fail_fast=True)==old.check(t,fail_fast=True)


def test_certificate_corruption_rejects_without_recomputation():
    rows,fixed=scene();d=DependencyWidthScene(rows,fixed);d.check(rows,fail_fast=True)
    key=d._context('0',d.accepted_current,d.spatial_index(d.accepted_current))[0]
    proof,weight=d.routes.entries[key]
    d.routes.entries[key]=(replace(proof,payload=b'{}'),weight)
    d.check(trial(rows,(1.1,1,1,1)),fail_fast=True)
    with pytest.raises(ValueError,match='CERTIFICATE_CHANGED'):d.check(rows,fail_fast=True)


def test_source_and_policy_binding_cannot_reuse_a_different_certificate():
    a=Certificates('source-a',1024);a.put('key',dict(gap=.02))
    b=Certificates('source-b',1024);b.entries.update(a.entries)
    with pytest.raises(ValueError,match='CERTIFICATE_CHANGED'):b.get('key')
    rows,fixed=scene();d=DependencyWidthScene(rows,fixed)
    assert DependencyWidthScene(rows,fixed,source_binding='a'*64).binding!=DependencyWidthScene(rows,fixed,source_binding='b'*64).binding
    d.contract=replace(d.contract,hard_gap_mm=.01)
    with pytest.raises(ValueError,match='POLICY_CHANGED'):d.check(rows,fail_fast=True)


def test_empty_checked_copper_has_a_geometry_independent_gap_witness():
    g=Point(0,0).buffer(.05);rows=[dict(id='trace',original=g,candidate=g,verified_original_width_mm=.1)]
    fixed=[dict(id='bulk',geometry=box(-1,-1,1,1))]
    old=IncrementalWidthScene(rows,fixed);new=DependencyWidthScene(rows,fixed)
    t=[dict(rows[0],candidate=g.buffer(.01))]
    assert new.check(t,fail_fast=True)==old.check(t,fail_fast=True)
    assert new.empty_witnesses>0 and not new.visible_cache
    assert new.check(t,materialize_scene=True)==PreparedWidthScene(rows,fixed).check(t,materialize_scene=True)


def test_pair_proof_is_bound_to_both_actual_visible_geometries():
    rows,fixed=scene();d=DependencyWidthScene(rows,fixed)
    a,b=rows[0]['original'],rows[1]['original']
    assert d.exact_distance('0','1',a,b)==a.distance(b)
    assert d.exact_distance('0','1',a,b)==a.distance(b) and d.pairs.hits==1
    moved=translate(b,yoff=.1)
    assert d.exact_distance('0','1',a,moved)==a.distance(moved) and d.pairs.misses==2


def test_newly_entering_neighbor_invalidates_a_previously_empty_query_scope():
    cores=[LineString([(0,y),(1,y)]).buffer(.05) for y in (0,.14)]
    rows=[dict(id=str(i),original=g,candidate=g,verified_original_width_mm=.1) for i,g in enumerate(cores)]
    a=DependencyWidthScene(rows,[]);b=IncrementalWidthScene(rows,[])
    for factors in ((1,1),(1.25,1),(1.25,1.5),(1.25,1),(1,1)):
        q=a.check(trial(rows,factors),fail_fast=True)
        assert q==b.check(trial(rows,factors),fail_fast=True)
        if factors==(1.25,1.5):assert not q['passed']


def test_replaced_fixed_geometry_uses_legacy_index_and_cache_budgets_reject_bad_values():
    rows,fixed=scene();d=DependencyWidthScene(rows,fixed);current=dict(d.original)
    current['land']=translate(current['land'],xoff=10)
    assert isinstance(d.spatial_index(current),STRtree) and d.index_fallbacks==1
    for args in (dict(proof_budget=-1),dict(geometry_budget=-1),dict(proof_budget=True)):
        with pytest.raises(ValueError,match='BUDGET_INVALID'):DependencyWidthScene(rows,fixed,**args)


def test_geometry_cache_keys_are_unambiguous_for_source_ids_containing_delimiters():
    rows,fixed=scene();d=DependencyWidthScene(rows,fixed)
    a,b=rows[0]['original'].buffer(.005),rows[2]['original'].buffer(.01)
    ha,hb=d.cached_sha(a),d.cached_sha(b);port=Point(0,0).buffer(.1)
    # These tuples collide if encoded by concatenating colon-delimited strings.
    sid1,oid1='A','B:'+hb+':C';sid2,oid2='A:'+ha+':B','C'
    x=d.checked_copper(sid1,oid1,a,a,port)
    y=d.checked_copper(sid2,oid2,b,b,port)
    assert x.equals(a.difference(port)) and y.equals(b.difference(port))


def test_existing_epsilon_boundary_fallback_still_runs_after_reuse():
    core=LineString([(0,0),(1,0)]).buffer(.05)
    neighbor=LineString([(0,.1251-1.2e-12),(1,.1251-1.2e-12)]).buffer(.05)
    rows=[dict(id=str(i),original=g,candidate=g,verified_original_width_mm=.1) for i,g in enumerate((core,neighbor))]
    d=DependencyWidthScene(rows,[]);assert d.check(rows,fail_fast=True)['passed']
    d.visible_cache['1']=(d.cached_sha(neighbor),translate(neighbor,yoff=.4e-12))
    t=[dict(rows[0],candidate=core.buffer(.005)),rows[1]]
    assert not d.check(t,fail_fast=True)['passed']
    assert d.original_union_boundary_rechecks>0
    assert not d.check(t,fail_fast=True)['passed']
