import pytest
from shapely.geometry import box,LineString,Point
from src.bulk_edge_restore import fit_straight_flanks
from src.gerber_u05.source_edge_cleanup import trim_supported_feature


def fixture():
    shapes=dict(fill=box(0,0,4,4),trace=LineString([(-.02,2),(2,2)]).buffer(.0254,quad_segs=128),
                fragment=LineString([(-.025,2),(-.02,2)]).buffer(.005,quad_segs=128))
    rows={s:dict(kind='stroke',metadata={})for s in shapes}
    rows['trace']['metadata']['route_points_mm']=[[-.02,2],[2,2]]
    domain=box(-.1,1.8,0,2.2);edge=LineString([(0,1),(0,3)])
    _,evidence=fit_straight_flanks([(0,1.5),(0,1.7)],[(0,2.3),(0,2.5)],(.2,2),domain)
    return rows,shapes,domain,edge,evidence


def test_physical_cap_is_removed_even_when_an_overlap_fragment_becomes_empty():
    rows,g,domain,edge,evidence=fixture();raw={s:v.wkb for s,v in g.items()}
    after,proof=trim_supported_feature(rows,g,g,'trace',domain,edge,evidence,(.2,2))
    assert after['fragment'].is_empty and after['trace'].bounds[0]==0
    assert proof['conservative_area_fraction']<.1
    assert proof['physical_topology_before']==proof['physical_topology_after']==[1,0]
    assert proof['empty_derived_source_ids']==['fragment']
    assert proof['owner_authorized_free_source_end_retreats']
    assert raw=={s:v.wkb for s,v in g.items()}


def test_window_cannot_hide_a_continuing_external_connection():
    rows,g,domain,edge,evidence=fixture();rows['wire']=dict(kind='stroke',metadata={})
    g['wire']=LineString([(-.02,2),(-.5,2)]).buffer(.025)
    with pytest.raises(ValueError,match='CROPS_CONNECTION|TOPOLOGY_CHANGED'):
        trim_supported_feature(rows,g,g,'trace',domain,edge,evidence,(.2,2))


def test_touching_terminal_is_not_deleted_as_an_overlapping_fragment():
    rows,g,domain,edge,evidence=fixture();rows['pad']=dict(kind='circle',metadata=dict(center_mm=[-.025,2]))
    g['pad']=Point(-.025,2).buffer(.02)
    with pytest.raises(ValueError,match='TERMINAL_SHAPE_TOUCHED'):
        trim_supported_feature(rows,g,g,'trace',domain,edge,evidence,(.2,2))


def test_independent_terminal_inside_inspection_window_is_kept_byte_identical():
    rows,g,domain,edge,evidence=fixture()
    rows['nearby']=dict(kind='circle',metadata=dict(center_mm=[-.085,2]))
    g['nearby']=Point(-.085,2).buffer(.005)
    after,proof=trim_supported_feature(rows,g,g,'trace',domain,edge,evidence,(.2,2))
    assert after['nearby'].wkb==g['nearby'].wkb
    assert proof['physical_topology_before']==proof['physical_topology_after']==[2,0]
