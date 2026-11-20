"""Exact operand/candidate parity, including empty and changing scenes."""
import pytest
from shapely import STRtree, to_wkb
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
from src.gerber_u05.component_workspace import StripReservations, ResidualScene
from src.gerber_u05.limiting_math import GUARD, MARGIN


def legacy_reservations(strips, owners, owner, source):
    return [g.buffer(GUARD+2*MARGIN, quad_segs=128) for lane,g in strips
            if owners[lane['source_ids'][0]] != owner
            and g.envelope.buffer(GUARD).intersects(source.envelope)]


def test_reservations_keep_owner_holes_operand_order_and_source_updates():
    ring=box(0,0,3,3).difference(box(1,1,2,2))
    strips=[({'source_ids':[s]},g) for s,g in
            [('c',box(.5,-1,.55,4)),('a',ring),('b',box(8,8,9,9))]]
    owners={'a':(1,), 'b':(2,), 'c':(3,)}
    workspace=StripReservations(strips,owners)
    for source in (box(-1,-1,4,4), box(7,7,10,10), box(100,100,101,101)):
        for owner in owners.values():
            actual=workspace.foreign(owner,source)
            expected=legacy_reservations(strips,owners,owner,source)
            assert [to_wkb(g) for g in actual]==[to_wkb(g) for g in expected]
            assert to_wkb(unary_union(actual))==to_wkb(unary_union(expected))
    first=workspace.foreign((99,),box(-1,-1,4,4))
    second=workspace.foreign((99,),box(-1,-1,4,4))
    assert all(a is b for a,b in zip(first,second))
    assert len(workspace.buffers)==3


def legacy_candidates(scene,window):
    ids=sorted(s for s,g in scene.items() if not g.is_empty)
    tree=STRtree([scene[s] for s in ids])
    return tuple(ids[int(i)] for i in sorted(map(int,tree.query(window))))


@pytest.mark.parametrize('count',[0,64,2048])
@pytest.mark.parametrize('budget',[0,1024,32*1024**2])
def test_candidate_count_is_independent_of_index_budget(count,budget):
    scene=ResidualScene({str(i):box(i,0,i+.5,1) for i in range(count)},index_bytes=budget)
    window=box(-1,-1,count+1,2)
    assert scene.query(window)==legacy_candidates(scene,window)
    assert len(scene.query(window))==count
    assert len(scene)==count
    scene['new']=box(-.5,0,0,1)
    assert len(scene.query(window))==count+1
    scene.close()
    assert len(scene)==count+1


@pytest.mark.parametrize('budget',[0,2*1024,32*1024**2])
def test_accepted_neighbor_moves_empty_replacement_and_deletion(budget):
    scene=ResidualScene({'a':box(0,0,1,1),'b':box(20,20,21,21)},index_bytes=budget)
    windows=[box(-1,-1,2,2),box(19,19,22,22)]
    def compare():
        for window in windows:
            assert scene.query(window)==legacy_candidates(scene,window)
    compare()
    scene.update({'b':box(.5,.5,1.5,1.5),'c':box(20,20,21,21)})
    compare()
    scene['a']=Polygon();compare()
    del scene['b'];compare()
    # Repeated rejected proposals must not mutate the accepted obstacle scene.
    for _ in range(4):compare()
    assert scene['a'].is_empty and 'b' not in scene and 'c' in scene


def test_overlay_rebuild_keeps_every_updated_source():
    scene=ResidualScene({str(i):box(i,0,i+.5,1) for i in range(160)})
    window=box(-1,-1,200,2);scene.query(window)
    for i in range(160):scene[str(i)]=box(i,10,i+.5,11)
    assert scene.query(window)==()
    upper=box(-1,9,200,12)
    assert scene.query(upper)==legacy_candidates(scene,upper)
    assert len(scene.query(upper))==160
    assert scene._index.diagnostics()['index_builds']==2
    scene.close()


def test_empty_trial_has_no_candidates_without_losing_material():
    scene=ResidualScene({'a':box(0,0,1,1)})
    assert scene.query(Polygon())==()
    assert len(scene)==1
    assert scene.query(box(-1,-1,2,2))==('a',)
