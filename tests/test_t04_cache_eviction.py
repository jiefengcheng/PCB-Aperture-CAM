from collections import OrderedDict
from src.t04_incremental import OwnerDependencies


def test_lru_eviction_keeps_proof_values_and_enforces_memory_bound():
 cache=object.__new__(OwnerDependencies)
 cache.cache=OrderedDict();cache.bytes=0;cache.limit=400;cache.hits=0
 calls=[]
 def measured(i):
  calls.append(i)
  return i+.125
 for i in range(20):
  assert cache.memo(('distance',i),lambda i=i:measured(i))==i+.125
  assert 0<=cache.bytes<=cache.limit
 assert len(cache.cache)<20
 assert cache.memo(('distance',19),lambda:measured(999))==19.125
 assert 999 not in calls
 assert cache.memo(('distance',0),lambda:measured(0))==.125
 assert calls.count(0)==2 # Evicted values are remeasured, never substituted.
 assert 0<=cache.bytes<=cache.limit


def test_fixed_source_void_storage_is_charged_before_memo_entries():
 cache=object.__new__(OwnerDependencies);cache.cache=OrderedDict();cache.source_void_bytes=180;cache.bytes=180;cache.limit=400;cache.hits=0
 for i in range(20):
  assert cache.memo(('distance',i),lambda i=i:i)==i
  assert cache.source_void_bytes<=cache.bytes<=cache.limit
 assert len(cache.cache)<20
 cache.source_void_bytes=400;cache.cache.clear();cache.bytes=400
 assert cache.memo(('uncached',1),lambda:123)==123
 assert not cache.cache and cache.bytes==cache.limit
