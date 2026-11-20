import numpy as np
from shapely.geometry import LineString
from src.gerber_u05.corner_transition import joint_frame,corners
from src.gerber_u05.ribbon_profile import frame


def test_rounded_dense_arc_end_uses_the_interior_tangent_without_moving_source_points():
    t=np.linspace(0,np.pi/2,301);points=np.column_stack((.3*np.sin(t),.3*(1-np.cos(t)))).tolist()
    # Source cap noise turns the final chord almost transverse to the arc.
    points[-2]=[points[-1][0]-.0001,points[-1][1]-.00001]
    desc=dict(stabilize_joint_frame=True,route_kind='arc',points=points,source_width_mm=.05,offsets_mm=[-.025,.025])
    before=LineString(points).wkb
    pts,n,stations,length=joint_frame(desc,points)
    assert abs(n[-1,0])>.99 and abs(n[-1,1])<.02
    faces,normal=corners(desc,1,skin=False)
    assert abs(normal[0])>.99
    assert abs(np.linalg.norm(faces[1]-faces[0])-.05)<1e-12
    assert LineString(points).wkb==before
    raw=frame(points,extra_stations=[.02,length-.02])
    middle=(stations>=.02)&(stations<=length-.02)
    assert np.allclose(n[middle],raw[1][middle])


def test_sparse_or_nonarc_paths_keep_the_original_corner_frame_exactly():
    points=[[0.,0.],[.2,0.],[.3,.1],[.3,.3]]
    for kind in ('segment','arc'):
        raw=frame(points,extra_stations=[.25]);actual=joint_frame(dict(route_kind=kind),points,extra_stations=[.25])
        assert all(np.array_equal(a,b)for a,b in zip(raw[:3],actual[:3]))
