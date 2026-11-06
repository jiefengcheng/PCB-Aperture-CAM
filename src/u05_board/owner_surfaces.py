"""Disk-backed immutable owner unions with a bounded decoded working set.

Every read still checks the artifact. Eviction changes preparation cost, never
which original owner or foreign surface participates in a route check.
"""
from collections import OrderedDict,Counter
from collections.abc import Mapping
from types import MappingProxyType
import weakref
from shapely import STRtree,to_wkb,from_wkb
from shapely.geometry import box
from src.stage_abi.loaded_geometry import budget,geometry_checksum,valid
from src.stage_abi.store import canonical,digest

class OwnerSurfaces(Mapping):
 def __init__(self,context,material,store,*,limit):
  self.store=store;self.limit=budget(limit,'owner-surfaces');self.cache=OrderedDict();self.live=weakref.WeakValueDictionary();self.weight=0;self.peak=0;self.stats=Counter();refs={};envelopes=[]
  # The same exact ordered operands as Context.project; only one derived
  # union needs to exist during preparation. Geometry lives in the job store.
  for own,g in context.iter_project(material):
   refs[own]=store.put('geometry',to_wkb(g));envelopes.append(box(*g.bounds))
  self.refs=MappingProxyType(refs);self.ids=tuple(refs);self.tree=STRtree(envelopes);self.binding=digest(canonical(refs))
 def __iter__(self):return iter(self.ids)
 def __len__(self):return len(self.ids)
 def __getitem__(self,own):
  reference=self.refs[own];blob=self.store.get(reference,kind='geometry');self.stats['artifact_reads']+=1
  shape=self.live.get(own)
  if shape is not None:
   if to_wkb(shape)!=blob:raise ValueError('OWNER_SURFACE_CACHE_CORRUPTED')
   self.stats['reuse']+=1
   if own in self.cache:self.cache.move_to_end(own)
   return shape
  shape=valid(from_wkb(blob));self.stats['decodes']+=1;self.live[own]=shape;size=2*len(blob)+512
  if size<=self.limit:
   while self.cache and self.weight+size>self.limit:
    _,(_,oldsize)=self.cache.popitem(last=False);self.weight-=oldsize;self.stats['evictions']+=1
   self.cache[own]=(shape,size);self.weight+=size;self.peak=max(self.peak,self.weight)
  else:self.stats['not_retained']+=1
  return shape
 def query(self,window):
  # Complete conservative envelope query. The caller retains the original
  # exact intersects test and all exact finite-copper predicates.
  return [self.ids[i]for i in sorted(map(int,self.tree.query(window)))]
 def validate_bindings(self):
  if self.ids!=tuple(self.refs)or self.binding!=digest(canonical(dict(self.refs))):raise ValueError('OWNER_SURFACE_BINDING_CHANGED')
  for own,g in list(self.live.items()):
   if self.store.get(self.refs[own],kind='geometry')!=to_wkb(g):raise ValueError('OWNER_SURFACE_CACHE_CORRUPTED')
 def diagnostics(self):return dict(self.stats,resident_estimated_bytes=self.weight,peak_estimated_bytes=self.peak,limit_bytes=self.limit,owners=len(self.ids),weak_entries=len(self.live),resident_entries=len(self.cache))
 def close(self):
  self.cache.clear();self.live.clear();self.weight=0
