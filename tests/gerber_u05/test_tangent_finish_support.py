from shapely.geometry import box
from shapely.ops import unary_union
from src.gerber_u05.tangent_finish import run


def test_finishing_preserves_accepted_source_bodies_and_only_removes_optional_corner_copper():
    rows={s:dict(metadata=dict(route_points_mm=pts))for s,pts in [('a',[[-.3,0],[0,0]]),('b',[[0,0],[.3,0]])]}
    floors=dict(a=box(-.3,-.035,0,.035),b=box(0,-.035,.3,.035))
    desc={s:dict(points=r['metadata']['route_points_mm'],source_width_mm=.05,offsets_mm=[-.035,.035],support=floors[s])for s,r in rows.items()}
    before={s:g.wkb for s,g in floors.items()};tooth=box(.004,.034,.008,.038)
    bodies=dict(a=floors['a'],b=unary_union([floors['b'],tooth]))
    cuts,report=run(rows,dict(r=['a','b']),bodies,desc,[])
    assert report['trimmed_joints']==1
    assert all(c.intersection(unary_union(list(floors.values()))).area==0 for c in cuts.values())
    finished=unary_union([*floors.values(),tooth.difference(cuts['b'])])
    assert finished.geom_type=='Polygon'and finished.covers(unary_union(list(floors.values())))
    assert {s:g.wkb for s,g in floors.items()}==before


def test_no_optional_corner_copper_means_no_tangent_trim():
    rows={s:dict(metadata=dict(route_points_mm=pts))for s,pts in [('a',[[-.3,0],[0,0]]),('b',[[0,0],[.3,0]])]}
    bodies=dict(a=box(-.3,-.035,0,.035),b=box(0,-.035,.3,.035))
    desc={s:dict(points=r['metadata']['route_points_mm'],source_width_mm=.05,offsets_mm=[-.035,.035],support=bodies[s])for s,r in rows.items()}
    cuts,report=run(rows,dict(r=['a','b']),bodies,desc,[])
    assert cuts=={}and report['trimmed_joints']==0
