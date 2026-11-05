import math,random
import pytest
from shapely.geometry import Point,box
from src import component_distance as d
from src import indexed_polygon_distance as legacy

@pytest.mark.parametrize('gap',[.04,.04-2e-13,.04+2e-13,.0401,.0401-1.01e-12,.0401-0.99e-12,.2])
def test_exact_original_boundary_verdict_is_retained(gap):
 a=Point(0,0).buffer(1,quad_segs=400);b=Point(2+gap,0).buffer(1,quad_segs=400);x=d.distance(a,b);y=a.distance(b)
 assert all((x+1e-12>=t)==(y+1e-12>=t)for t in(.04,.0401))
 if abs(y-.04)<=4e-12 or abs(y-.0401)<=4e-12:assert x.hex()==y.hex()

def test_large_disjoint_owners_keep_all_edges_and_full_distance_within_roundoff():
 rng=random.Random(94)
 for i in range(12):
  a=Point(0,0).buffer(1,quad_segs=512).difference(box(-.5,-.1,.5,.1));b=Point(2.1+rng.random(),rng.random()).buffer(1,quad_segs=512);x=d.distance(a,b);y=a.distance(b)
  assert math.isclose(x,y,rel_tol=0,abs_tol=1e-13)
  assert all((x+1e-12>=t)==(y+1e-12>=t)for t in(.04,.0401))
 assert len(d.VALUES)<=d.MAX_ENTRIES

def test_indexed_native_error_remains_a_hard_failure(monkeypatch):
 class Broken:
  def measure(self,*args):raise RuntimeError('DELIBERATE_INDEX_ERROR')
 d.VALUES.clear();monkeypatch.setattr(legacy,'ENGINE',Broken());a=Point(0,0).buffer(1,quad_segs=400);b=Point(5,0).buffer(1,quad_segs=400)
 with pytest.raises(RuntimeError,match='DELIBERATE_INDEX_ERROR'):d.distance(a,b)

def test_changed_distance_cache_certificate_is_rejected():
 d.VALUES.clear();a=box(0,0,1,1);b=box(2,0,3,1);d.distance(a,b);key=next(iter(d.VALUES));value,proof=d.VALUES[key];d.VALUES[key]=(value+.1,proof)
 with pytest.raises(ValueError,match='CERTIFICATE_CHANGED'):d.distance(a,b)
 d.VALUES.clear()
