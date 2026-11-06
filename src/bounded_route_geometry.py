"""Two current geometry versions per source ID within a global byte ceiling.

Only immutable geometry construction is reused. No policy or clearance verdict
is cached here, and eviction always causes exact reconstruction.
"""
from collections import OrderedDict,Counter
import math
from shapely import to_wkb
from src.stage_abi.loaded_geometry import geometry_checksum,budget

class VersionedGeometry:
 def __init__(self,source_ids,binding,*,limit,versions=2):
  self.source_ids=frozenset(source_ids);self.binding=binding;self.limit=budget(limit,'route-geometry');self.versions=budget(versions,'route-versions');self.values=OrderedDict();self.by_source={};self.weight=0;self.peak=0;self.stats=Counter()
  if not binding or self.versions!=2:raise ValueError('TWO_SOURCE_BOUND_GEOMETRY_VERSIONS_REQUIRED')
 def get(self,sid,factor,envelope,build):
  if sid not in self.source_ids:raise ValueError('GEOMETRY_SOURCE_ID_UNBOUND')
  if type(factor)not in(int,float)or not math.isfinite(factor)or not 1<=factor<=1.5 or type(envelope)is not bool:raise ValueError('GEOMETRY_FACTOR_OR_ENVELOPE_INVALID')
  key=(sid,factor,envelope);self.stats['requests']+=1;old=self.values.get(key)
  if old is not None:
   shape,checksum,size=old
   if geometry_checksum(shape)!=checksum:raise ValueError('SOURCE_ROUTE_GEOMETRY_CACHE_CORRUPTED')
   self.values.move_to_end(key);self.by_source[sid].move_to_end(key);self.stats['hits']+=1;return shape
  shape=build();self.stats['builds']+=1
  if shape.is_empty or not shape.is_valid or shape.geom_type not in('Polygon','MultiPolygon'):raise ValueError('INVALID_CACHED_ROUTE_GEOMETRY')
  blob=to_wkb(shape);size=2*len(blob)+640+len(repr(key))
  if size<=self.limit:
   local=self.by_source.get(sid)
   if local is not None and len(local)>=self.versions:self.evict(next(iter(local)))
   while self.values and self.weight+size>self.limit:self.evict(next(iter(self.values)))
   self.values[key]=(shape,geometry_checksum(shape),size);self.by_source.setdefault(sid,OrderedDict())[key]=None;self.weight+=size;self.peak=max(self.peak,self.weight)
  else:self.stats['not_retained']+=1
  return shape
 def evict(self,key):
  _,_,size=self.values.pop(key);self.weight-=size;local=self.by_source[key[0]];del local[key]
  if not local:del self.by_source[key[0]]
  self.stats['evictions']+=1
 def diagnostics(self):return dict(self.stats,retained_estimated_bytes=self.weight,peak_estimated_bytes=self.peak,limit_bytes=self.limit,entries=len(self.values),source_ids=len(self.source_ids),maximum_versions_per_source=self.versions)
 def close(self):self.values.clear();self.by_source.clear();self.weight=0
