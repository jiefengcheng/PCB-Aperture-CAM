from functools import lru_cache
import pytest
from shapely import to_wkb
from shapely.geometry import box
from src.bounded_route_geometry import VersionedGeometry

def test_more_than_800_source_routes_do_not_evict_each_other_between_stationary_passes():
 ids=[str(i)for i in range(1001)];memo=VersionedGeometry(ids,'source-and-native-width-policy',limit=8*1024**2);counts={'new':0,'old':0}
 def make(s,which):counts[which]+=1;return box(int(s),0,int(s)+1,1)
 @lru_cache(maxsize=800)
 def previous(s):return make(s,'old')
 for _ in range(2):
  for sid in ids:
   assert to_wkb(memo.get(sid,1.25,True,lambda sid=sid:make(sid,'new')))==to_wkb(previous(sid))
 assert counts=={'new':1001,'old':2002}
 assert memo.diagnostics()['peak_estimated_bytes']<=memo.limit

def test_each_source_has_only_two_versions_and_global_bytes_are_bounded():
 memo=VersionedGeometry(['A','B'],'source',limit=4000)
 for sid in ['A','B']*5:
  for factor in(1.1,1.2,1.3,1.4,1.5):
   result=memo.get(sid,factor,True,lambda factor=factor:box(0,0,factor,1))
   assert to_wkb(result)==to_wkb(box(0,0,factor,1))
   assert memo.weight<=4000 and all(len(v)<=2 for v in memo.by_source.values())
 assert memo.stats['evictions']>0
 memo.close();assert memo.weight==0 and not memo.values and not memo.by_source

def test_disabled_cache_and_oversized_route_recompute_identical_shapes():
 memo=VersionedGeometry(['A'],'source',limit=0);one=memo.get('A',1.5,False,lambda:box(0,0,1,1));two=memo.get('A',1.5,False,lambda:box(0,0,1,1))
 assert to_wkb(one)==to_wkb(two)and not memo.values and memo.stats['builds']==2

def test_geometry_cache_corruption_and_source_substitution_fail():
 memo=VersionedGeometry(['A'],'source',limit=4000);memo.get('A',1.25,True,lambda:box(0,0,1,1));key=next(iter(memo.values));_,checksum,size=memo.values[key];memo.values[key]=(box(2,2,3,3),checksum,size)
 with pytest.raises(ValueError,match='CACHE_CORRUPTED'):memo.get('A',1.25,True,lambda:box(0,0,1,1))
 with pytest.raises(ValueError,match='SOURCE_ID_UNBOUND'):memo.get('other',1.25,True,lambda:box(0,0,1,1))

@pytest.mark.parametrize('factor,envelope',[(True,True),(.99,True),(1.51,True),(float('nan'),True),(1.25,1)])
def test_factor_and_envelope_bindings_are_strict(factor,envelope):
 memo=VersionedGeometry(['A'],'source',limit=4000)
 with pytest.raises(ValueError,match='FACTOR_OR_ENVELOPE_INVALID'):memo.get('A',factor,envelope,lambda:box(0,0,1,1))
