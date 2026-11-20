"""Exact nearby sections must preserve gaps, holes and fallback semantics."""
import math
import random
import pytest
import shapely
from shapely.geometry import box, Point, MultiPolygon
from src import indexed_polygon_distance as distance
from src.t05_prior_boundary_screen import Screen


@pytest.fixture(autouse=True)
def reset_cache():
    distance.clear()
    yield
    distance.clear()


@pytest.mark.parametrize('gap', [.04, .04010, .04-1e-12, .04+1e-12, .04010-1e-12, .04010+1e-12, .2])
def test_exact_gaps_both_orders_and_index_reuse(gap):
    a = Point(0,0).buffer(1,quad_segs=400)
    b = Point(2+gap,0).buffer(1,quad_segs=400)
    screen = Screen(distance)
    for left,right in [(a,b),(b,a),(a,b)]:
        assert screen.measure(left,right,lambda x,y:x.distance(y)).hex() == left.distance(right).hex()
    assert screen.stats['screened'] == 3
    assert screen.stats['sections_selected'] < screen.stats['sections_considered']
    assert distance.diagnostics()['chunk_hits'] == 1


def test_all_hole_edges_and_multipart_inputs():
    ring = Point(0,0).buffer(2,quad_segs=400).difference(Point(0,0).buffer(1,quad_segs=400))
    b = MultiPolygon([ring,box(20,20,21,21)])
    a = Point(0,0).buffer(.2,quad_segs=100)
    screen = Screen(distance)
    assert screen.measure(a,b,lambda x,y:x.distance(y)).hex() == a.distance(b).hex()
    assert screen.stats['screened'] == 1


def test_no_cut_or_reversed_edges_in_selected_sections():
    b = box(0,0,4,4).segmentize(.005)
    tree,parts = distance.boundary_index(b)
    expected = list(zip(list(b.exterior.coords),list(b.exterior.coords)[1:]))
    actual = [edge for part in parts for edge in zip(list(part.coords),list(part.coords)[1:])]
    assert actual == expected
    a = box(-1,1,-.04,2)
    ids = sorted(map(int,tree.query(a,predicate='dwithin',distance=.040000001)))
    selected = [edge for i in ids for edge in zip(list(parts[i].coords),list(parts[i].coords)[1:])]
    assert selected and all(e in expected for e in selected)
    assert Screen(distance).measure(a,b,lambda x,y:x.distance(y)).hex()==a.distance(b).hex()


@pytest.mark.parametrize('mode',['overlap','touch','contained','precision','small','point'])
def test_original_fallbacks(mode):
    b = box(0,0,4,4).segmentize(.005)
    a = {'overlap':box(-1,1,1,2),'touch':box(-1,1,0,2),
         'contained':box(1,1,2,2),'precision':shapely.set_precision(box(-1,1,-.04,2),.001),
         'small':box(-1,1,-.04,2),'point':Point(-1,1)}[mode]
    if mode=='small':b=box(0,0,4,4)
    calls=[]
    def fallback(x,y):calls.append(True);return x.distance(y)
    assert Screen(distance).measure(a,b,fallback).hex()==a.distance(b).hex()
    assert len(calls)==1


def test_changed_copper_and_cache_corruption():
    a=box(-1,1,-.04,2);b=box(0,0,4,4).segmentize(.005);screen=Screen(distance)
    for g in [b,shapely.affinity.translate(b,xoff=.1)]:
        assert screen.measure(a,g,lambda x,y:x.distance(y)).hex()==a.distance(g).hex()
    assert distance.diagnostics()['chunk_builds']==2
    entry=next(iter(distance.CHUNKS.values()));parts=entry[1];parts.flags.writeable=True
    parts[0]=shapely.geometry.LineString([(100,100),(101,100)])
    with pytest.raises(ValueError,match='BOUNDARY_CACHE_CHANGED'):
        screen.measure(a,b,lambda x,y:x.distance(y))


def test_invalid_native_bound_cannot_supply_a_false_gap(monkeypatch):
    class Bad:
        def measure(self,a,b):return 0.001
        def close(self):pass
    monkeypatch.setattr(distance,'ENGINE',Bad())
    a=box(-1,1,-.04,2);b=box(0,0,4,4).segmentize(.005);calls=[]
    def fallback(x,y):calls.append(True);return x.distance(y)
    assert Screen(distance).measure(a,b,fallback).hex()==a.distance(b).hex()
    assert len(calls)==1


def test_seeded_complex_shapes_exact_numeric_witnesses():
    rng=random.Random(6041);screen=Screen(distance)
    for _ in range(24):
        a=Point(rng.random(),rng.random()).buffer(.3+rng.random(),quad_segs=300)
        b=Point(4+rng.random(),rng.random()).buffer(.3+rng.random(),quad_segs=500)
        assert screen.measure(a,b,lambda x,y:x.distance(y)).hex()==a.distance(b).hex()
    assert distance.diagnostics()['retained_bytes']<=distance.LIMIT
