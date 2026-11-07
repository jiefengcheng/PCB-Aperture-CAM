"""Immutable predecessor reuse cannot change a no-bypass predicate or budget."""
import pytest
from shapely import from_wkb,to_wkb,set_precision
from shapely.geometry import box
from src.t04_width_fence import Rule

def fixture(*,cache_bytes=32*1024**2):
 before=box(0,0,1,1);return Rule(box(1,0,2,1),before,'frozen',cache_bytes=cache_bytes),before,box(.5,.1,1.5,.9)

def test_same_immutable_predecessor_buffer_is_built_once_and_proofs_match_uncached():
 rule,before,logical=fixture();uncached,_,_=fixture(cache_bytes=0)
 expected=uncached.remedy(logical,before)
 assert not expected['passed']
 for _ in range(12):assert rule.remedy(logical,before)==expected
 stats=rule.cache_statistics();assert stats['misses']==1 and stats['hits']==11 and stats['entries']==1
 assert stats['estimated_bytes']<=stats['limit_bytes']

def test_new_object_and_precision_metadata_do_not_hit_a_stale_skin():
 rule,before,logical=fixture();uncached,_,_=fixture(cache_bytes=0)
 for predecessor in [before,from_wkb(to_wkb(before)),set_precision(before,1e-6),box(0,0,1.1,1)]:
  assert rule.remedy(logical,predecessor)==uncached.remedy(logical,predecessor)
 assert rule.cache_statistics()['hits']==0 and rule.cache_statistics()['misses']==4
 assert rule.cache_statistics()['entries']==1

def test_tolerance_is_part_of_cache_identity(monkeypatch):
 import src.pcb_data_abi.geometry as geometry
 rule,before,logical=fixture();uncached,_,_=fixture(cache_bytes=0)
 rule.remedy(logical,before);monkeypatch.setattr(geometry,'POLYGON_TOLERANCE_MM',geometry.POLYGON_TOLERANCE_MM*2)
 assert rule.remedy(logical,before)==uncached.remedy(logical,before)
 assert rule.cache_statistics()['misses']==2

@pytest.mark.parametrize('limit',[0,1,1024])
def test_cache_budget_rejects_retention_without_removing_checks(limit):
 rule,before,logical=fixture(cache_bytes=limit);uncached,_,_=fixture(cache_bytes=0)
 for _ in range(3):assert rule.remedy(logical,before)==uncached.remedy(logical,before)
 stats=rule.cache_statistics();assert stats['entries']==0 and stats['estimated_bytes']==0 and stats['misses']==3

def test_cached_state_remains_the_same_source_bound_geometry(tmp_path):
 from src.stage_abi.store import ArtifactStore
 rule,before,logical=fixture();store=ArtifactStore(tmp_path/'runtime');initial=rule.state(store)
 rule.remedy(logical,before);assert rule.state(store)==initial
 rule.remedy(logical,box(0,0,1.1,1));assert rule.state(store)==initial

def test_empty_raw_intersection_does_not_prepare_a_buffer():
 rule,before,_=fixture();assert rule.remedy(before,before)['passed']
 assert rule.cache_statistics()['entries']==0 and rule.cache_statistics()['misses']==0

@pytest.mark.parametrize('limit',[-1,True,1.5])
def test_invalid_cache_budgets_fail_closed(limit):
 with pytest.raises(ValueError,match='CACHE_BUDGET_INVALID'):fixture(cache_bytes=limit)
