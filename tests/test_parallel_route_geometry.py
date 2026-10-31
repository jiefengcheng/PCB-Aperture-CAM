import pytest
from src.parallel_route_geometry import parallel_points,displaced_reference,extension_distance


def test_piecewise_normal_offsets_preserve_segment_tangent_and_order():
 reference=[[0,0],[1,0],[2,1],[3,1]];a=parallel_points(reference,.1);b=parallel_points(reference,.2)
 for x,y,p,q in zip(reference,reference[1:],a,a[1:]):
  dx,dy=y[0]-x[0],y[1]-x[1];ux,uy=q[0]-p[0],q[1]-p[1];assert abs(dx*uy-dy*ux)<1e-12 and dx*ux+dy*uy>0
 assert a!=b

def test_inner_offset_cannot_reverse_a_short_segment():
 with pytest.raises(ValueError,match='OFFSET_TANGENT_OR_ORDER_INVALID'):parallel_points([[0,0],[1,0],[1,.1],[0,.1]],.2)

def test_reference_endpoint_tangents_cannot_be_displaced():
 with pytest.raises(ValueError,match='FIXED_ENDPOINT'):displaced_reference([[i,0] for i in range(7)],1,3,[0,1],.1)

def test_patch_must_retain_initial_domain():
 with pytest.raises(ValueError,match='CONTAIN_INITIAL'):extension_distance([[i,0] for i in range(9)],[3,5],[4,5])
