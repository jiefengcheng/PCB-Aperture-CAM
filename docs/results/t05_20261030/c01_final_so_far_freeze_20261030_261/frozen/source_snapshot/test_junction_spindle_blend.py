import pytest
from shapely.geometry import Point,LineString,box
from src.junction_spindle_blend import spindle_blend,check_spindle

def owner():
 return Point(0,0).buffer(.2,quad_segs=64).union(Point(.5,0).buffer(.2,quad_segs=64)).union(LineString([(0,0),(.5,0)]).buffer(.025))

def test_pair_of_circles_and_neck_broadens_without_source_removal():
 o=owner();w=box(-.3,-.3,.8,.3);c,a=spindle_blend(o,.2,w)
 assert a.area>.01 and o.difference(c).area<1e-12
 assert check_spindle(o,c,a,w,[])['passed']
 assert c.intersection(LineString([(.25,-1),(.25,1)])).length>.05

def test_separate_circles_cannot_become_owner_by_label():
 o=Point(0,0).buffer(.1).union(Point(1,0).buffer(.1))
 with pytest.raises(ValueError,match='CONNECTED'):spindle_blend(o,.5,box(-1,-1,2,1))

def test_foreign_contact_rejected():
 o=owner();w=box(-.3,-.3,.8,.3);c,a=spindle_blend(o,.2,w)
 assert not check_spindle(o,c,a,w,[('obstacle',a)])['passed']

def test_window_is_hard_bound():
 o=owner();w=box(.2,0,.3,.3);c,a=spindle_blend(o,.2,w)
 assert a.difference(w).area==0 and check_spindle(o,c,a,w,[])['passed']

def test_owner_deletion_rejected():
 o=owner();w=box(-1,-1,2,1);c,a=spindle_blend(o,.2,w)
 assert 'OWNER_REMOVED' in check_spindle(o,c.difference(box(-.2,-.2,0,.2)),a,w,[])['failures']
