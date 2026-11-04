"""Domain-bound completeness and independently known graph families."""
import copy
import random
import pytest
from shapely.geometry import Point, LineString
from src.u03_analysis.dependency import dependencies
from src.u03_analysis.graph import analyze,components,blocks,elimination,minor_lower_bound,balanced_separator


def graph(n,edges):
    a={i:set() for i in range(n)}
    for v,w in edges:a[v].add(w);a[w].add(v)
    return a


@pytest.mark.parametrize('n,edges,width',[
    (1,[],0),(12,[(i,i+1) for i in range(11)],1),
    (9,[(0,i) for i in range(1,9)],1),
    (10,[(i,(i+1)%10) for i in range(10)],2),
    (7,[(i,j) for i in range(7) for j in range(i)],6),
    (6,[(i,j) for i in range(3) for j in range(3,6)],3),
])
def test_known_treewidth_and_valid_balanced_separator(n,edges,width):
    a=graph(n,edges);before=copy.deepcopy(a)
    assert minor_lower_bound(a)['width']==width
    d=elimination(a);assert d['width']==width and d['certificate_verified']
    s=balanced_separator(a,range(n));remaining=components(a,set(a)-set(s['vertices']))
    assert 3*max(map(len,remaining),default=0)<=2*n
    assert a==before


def test_disconnected_blocks_and_articulation_are_exact():
    a=graph(9,[(0,1),(1,2),(2,0),(2,3),(3,4),(4,5),(5,3),(6,7)])
    m=analyze(a)
    assert m['component_sizes']==[6,2,1]
    assert m['blocks']['articulation_vertices']==[2,3]
    assert m['blocks']['bridges']==[[2,3],[6,7]]
    assert m['block_sizes']==[3,3,2,2,1]


def test_diagonal_aabb_false_positive_removed_without_dropping_close_pair():
    rows=[dict(id='a',group=0,core=LineString([(0,0),(10,10)]).buffer(.02),width=.04),
          dict(id='b',group=1,core=LineString([(0,1),(9,10)]).buffer(.02),width=.04),
          dict(id='c',group=2,core=Point(0,0).buffer(.02),width=.04)]
    q=dependencies(rows,envelope_margin_mm=.00001,guard_mm=.020100000001)
    assert 1 in q['broad'][0] and 1 not in q['tight'][0]
    assert 2 in q['tight'][0]


def test_maximum_factor_bound_covers_all_sampled_interactions():
    rng=random.Random(311)
    rows=[dict(id=str(i),group=i//2,width=.04,core=Point(rng.random(),rng.random()).buffer(.02,quad_segs=128)) for i in range(40)]
    q=dependencies(rows,envelope_margin_mm=.00001,guard_mm=.0201)
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            if a['group']==b['group']:continue
            for sa in (1.,1.15,1.5):
                for sb in (1.,1.25,1.5):
                    ga=a['core'] if sa==1 else a['core'].buffer(a['width']*(sa-1)/2+.00001)
                    gb=b['core'] if sb==1 else b['core'].buffer(b['width']*(sb-1)/2+.00001)
                    if ga.distance(gb)<=.0201:
                        assert b['group'] in q['tight'][a['group']]
    assert all(g not in n for g,n in q['tight'].items())


def test_bound_includes_uncertain_numerical_boundary():
    rows=[dict(id='a',group=0,width=.04,core=Point(0,0).buffer(.02)),dict(id='b',group=1,width=.04,core=Point(.080120005,0).buffer(.02))]
    # Two original radii .02 + two max growth radii .01001 + .0201 guard.
    q=dependencies(rows,envelope_margin_mm=.00001,guard_mm=.0201)
    assert q['tight'][0]=={1}
    with pytest.raises(ValueError,match='DUPLICATE_ROUTE'):dependencies([rows[0],rows[0]],envelope_margin_mm=0,guard_mm=.02)


def test_decomposition_finds_small_separator_when_bfs_layers_are_bad():
    from src.u03_analysis.graph import decomposition_separator,recursive_partition,verify_minor_certificate
    # One universal hub attached to a long path: huge BFS shell, treewidth two.
    a=graph(201,[(i,i+1) for i in range(1,200)]+[(0,i) for i in range(1,201)])
    d=elimination(a);cut=decomposition_separator(a,d)
    assert cut['size']<=3 and max(cut['remaining_component_sizes'])<=134
    lower=minor_lower_bound(a);assert verify_minor_certificate(a,lower)
    altered=copy.deepcopy(lower);altered['width']+=1
    with pytest.raises(AssertionError):verify_minor_certificate(a,altered)
    p=recursive_partition(a,leaf_limit=16)
    assert max(p['leaf_sizes'])<=16 and max(p['separator_sizes'])<=3


@pytest.mark.parametrize('field', ['envelope_margin_mm','guard_mm','numerical_reserve_mm'])
def test_nonfinite_bound_cannot_silently_drop_dependencies(field):
    values=dict(envelope_margin_mm=.00001,guard_mm=.0201,numerical_reserve_mm=1e-8);values[field]=float('nan')
    with pytest.raises(ValueError,match='FINITE_NONNEGATIVE'):dependencies([],**values)
