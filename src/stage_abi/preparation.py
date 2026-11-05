"""Shared bounded preparation; no treatment policy, permissions or verdict cache.

The owner scope ends before the adapter returns a result to the stage dispatcher.
Legacy index order is retained for ordinary adapters; exact predicates still run.
"""
from collections import OrderedDict,Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
import hashlib,math,weakref
import numpy as np
from shapely import STRtree as NativeTree,from_wkb,to_wkb
from .store import canonical,digest
from .loaded_geometry import GeometryMemo,GeometryEntry,MeasurementEntry,valid,geometry_checksum,SNAPSHOT_BYTES,MEMO_BYTES,MEMO_ENTRIES,SIGNATURE_ENTRIES
from .spatial_queries import INDEX_BYTES,QUERY_BYTES,QUERY_ENTRIES
from src.native_preparation import preparation_scope

ACTIVE=ContextVar('pcb_preparation_resources',default=None)
@dataclass(frozen=True)
class Decoded:
    shape:object
    checksum:str
    weight:int
@dataclass(frozen=True)
class OrderedCandidates:
    envelope:tuple
    indices:tuple
    checksum:str
    weight:int

class PreparedTree:
    def __init__(self,geometries,kwargs):
        self.expected=tuple(geometries);self.tree=NativeTree(geometries,**kwargs)
        self.versions=tuple(geometry_checksum(g) for g in self.expected)
        self.token=digest(canonical([list(self.versions),kwargs]))
        self.geometries=self.tree.geometries
    def __getattr__(self,name):return getattr(self.tree,name)
    def query(self,geometry,predicate=None,distance=None):
        owner=ACTIVE.get()
        # Exact predicates are not memoized. Non-scalar/empty queries retain
        # the original STRtree call and its validation/error behavior.
        if owner is None or predicate is not None or distance is not None or not hasattr(geometry,'is_empty') or geometry.is_empty:
            return self.tree.query(geometry,predicate=predicate,distance=distance)
        envelope=tuple(geometry.bounds)
        if len(envelope)!=4 or not all(math.isfinite(x) for x in envelope):return self.tree.query(geometry)
        return owner.query(self,geometry,envelope)
    def validate(self):
        if self.geometries is not self.tree.geometries or len(self.geometries)!=len(self.expected) or any(a is not b for a,b in zip(self.expected,self.geometries)):
            raise ValueError('PREPARATION_SPATIAL_BINDING_CHANGED')
        if tuple(geometry_checksum(g) for g in self.expected)!=self.versions:
            raise ValueError('PREPARATION_SPATIAL_GEOMETRY_CHANGED')

class Resources:
    def __init__(self,binding,*,geometry_bytes=SNAPSHOT_BYTES,memo_bytes=MEMO_BYTES,index_bytes=INDEX_BYTES,query_bytes=QUERY_BYTES,query_entries=QUERY_ENTRIES):
        self.binding=binding;self.geometry_limit=geometry_bytes;self.index_limit=index_bytes;self.query_limit=query_bytes;self.query_entries=query_entries
        if any(type(v)is not int or v<0 for v in (geometry_bytes,memo_bytes,index_bytes,query_bytes,query_entries)):raise ValueError('PREPARATION_BUDGET_INVALID')
        self.decoded=OrderedDict();self.geometry_weight=0;self.trees=OrderedDict();self.index_weight=0
        self.queries=OrderedDict();self.query_weight=0;self.used_trees=weakref.WeakValueDictionary();self.stats=Counter()
        self.memo=GeometryMemo(binding,limit=memo_bytes,entries=MEMO_ENTRIES,signatures=SIGNATURE_ENTRIES)
    def decode(self,body):
        key=digest(body);old=self.decoded.get(key);self.stats['geometry_reads']+=1
        if old is not None:
            if geometry_checksum(old.shape)!=old.checksum:raise ValueError('PREPARATION_DECODED_GEOMETRY_CHANGED')
            self.decoded.move_to_end(key);self.stats['geometry_hits']+=1;return old.shape
        shape=from_wkb(body);blob=to_wkb(shape);weight=2*len(body)+len(blob)+512
        if weight<=self.geometry_limit:
            while self.decoded and self.geometry_weight+weight>self.geometry_limit:
                _,entry=self.decoded.popitem(last=False);self.geometry_weight-=entry.weight;self.stats['geometry_evictions']+=1
            self.decoded[key]=Decoded(shape,geometry_checksum(shape),weight);self.geometry_weight+=weight
        self.stats['geometry_decodes']+=1;return shape
    def index(self,geometries,kwargs):
        # Strong references in each retained tree prevent identity reuse. Full
        # geometry/index bindings are checked before a verdict; no stat cache.
        key=(tuple(id(g) for g in geometries),tuple(sorted(kwargs.items())))
        old=self.trees.get(key)
        if old is not None:
            self.trees.move_to_end(key);self.used_trees[id(old)]=old;self.stats['index_hits']+=1;return old
        weight=len(geometries)*1024+512
        if weight>self.index_limit:
            self.stats['index_checked_legacy']+=1;return NativeTree(geometries,**kwargs)
        while self.trees and (self.index_weight+weight>self.index_limit or len(self.trees)>=8):
            _,entry=self.trees.popitem(last=False);self.index_weight-=len(entry.expected)*1024+512
        tree=PreparedTree(geometries,kwargs);self.trees[key]=tree;self.index_weight+=weight;self.used_trees[id(tree)]=tree;self.stats['index_builds']+=1
        return tree
    def query(self,tree,geometry,envelope):
        self.used_trees[id(tree)]=tree;key=(tree.token,envelope);old=self.queries.get(key);self.stats['spatial_queries']+=1
        def checksum(indices):return digest(canonical([self.binding,tree.token,list(envelope),list(indices)]))
        if old is not None:
            if old.envelope!=envelope or old.checksum!=checksum(old.indices):raise ValueError('PREPARATION_NEIGHBORHOOD_CHANGED')
            self.queries.move_to_end(key);self.stats['spatial_hits']+=1;return np.asarray(old.indices,dtype=np.intp)
        indices=tuple(map(int,tree.tree.query(geometry)));weight=512+40*len(indices)
        if weight<=self.query_limit and self.query_entries:
            while self.queries and (self.query_weight+weight>self.query_limit or len(self.queries)>=self.query_entries):
                _,entry=self.queries.popitem(last=False);self.query_weight-=entry.weight
            self.queries[key]=OrderedCandidates(envelope,indices,checksum(indices),weight);self.query_weight+=weight
        return np.asarray(indices,dtype=np.intp)
    def validate(self):
        if self.memo.binding!=self.binding:raise ValueError('PREPARATION_RESOURCE_BINDING_CHANGED')
        from src.native_preparation import ACTIVE as NATIVE_ACTIVE
        native=NATIVE_ACTIVE.get()
        if native is not None:native.validate()
        for entry in self.decoded.values():
            if geometry_checksum(entry.shape)!=entry.checksum:raise ValueError('PREPARATION_DECODED_GEOMETRY_CHANGED')
        for entry in self.memo.values.values():
            if isinstance(entry,MeasurementEntry):
                if type(entry.value)is not bool or digest(str(entry.value).encode())!=entry.sha256:raise ValueError('LOADED_GEOMETRY_MEASUREMENT_CORRUPTED')
            elif not isinstance(entry,GeometryEntry) or geometry_checksum(entry.value)!=entry.sha256:raise ValueError('LOADED_GEOMETRY_CACHE_CORRUPTED')
        for (token,envelope),entry in self.queries.items():
            if entry.envelope!=envelope or entry.checksum!=digest(canonical([self.binding,token,list(envelope),list(entry.indices)])):raise ValueError('PREPARATION_NEIGHBORHOOD_CHANGED')
        for tree in self.used_trees.values():tree.validate()
    def diagnostics(self):return dict(self.stats,geometry_retained_bytes=self.geometry_weight,geometry_limit=self.geometry_limit,index_retained_bytes=self.index_weight,index_limit=self.index_limit,query_retained_bytes=self.query_weight,query_limit=self.query_limit,memo=self.memo.diagnostics())
    def close(self):
        self.decoded.clear();self.trees.clear();self.queries.clear();self.used_trees.clear();self.memo.close();self.geometry_weight=self.index_weight=self.query_weight=0

@contextmanager
def worker_resources(binding,**limits):
    current=ACTIVE.get()
    if current is not None:
        yield current
        current.validate()
        return
    resource=Resources(binding,**limits);token=ACTIVE.set(resource)
    try:
        with preparation_scope(binding):
            yield resource
            resource.validate()
    finally:resource.close();ACTIVE.reset(token)

def decode_geometry(body):
    owner=ACTIVE.get();return from_wkb(body) if owner is None else owner.decode(body)
def prepared_tree(geometries,**kwargs):
    owner=ACTIVE.get()
    if owner is None:return NativeTree(geometries,**kwargs)
    values=list(geometries)
    if any(g is None or not hasattr(g,'geom_type') for g in values):return NativeTree(values,**kwargs)
    return owner.index(values,kwargs)
def geometry_memo():
    owner=ACTIVE.get();return None if owner is None else owner.memo

class PreparedAdapter:
    def __init__(self,adapter):self.adapter=adapter;self.last_preparation=None
    def __getattr__(self,name):return getattr(self.adapter,name)
    def _call(self,name,store,scene,policy,*args,**kwargs):
        bound=digest(canonical([scene,policy,name]));rows={r['source_id']:r for r in scene['objects']}
        with worker_resources(bound) as owner:
            result=getattr(self.adapter,name)(store,scene,policy,*args,**kwargs)
            if digest(canonical([scene,policy,name]))!=bound:raise ValueError('PREPARATION_SCENE_OR_POLICY_CHANGED')
            # Re-read complete original/current operands before publishing the
            # adapter result. No budget-limited cache can prune this full pass.
            decoded={}
            for row in rows.values():
                for key in ('geometry_ref','original_ref'):
                    ref=row[key];token=(ref['artifact_id'],ref['sha256'])
                    if token not in decoded:decoded[token]=owner.decode(store.get(ref,kind='geometry'))
            checked={}
            def stamp(g):
                key=id(g)
                if key not in checked:checked[key]=(g,geometry_checksum(g))
                return checked[key][1]
            for attr in ('_prepared_context','_source_context'):
                value=getattr(self.adapter,attr,None)
                if not isinstance(value,tuple) or len(value)<3 or not all(isinstance(x,dict) for x in value[:3]):continue
                if value[0]!=rows or value[1].keys()!=rows.keys() or value[2].keys()!=rows.keys():raise ValueError('PREPARATION_ADAPTER_BINDING_CHANGED')
                for sid,row in rows.items():
                    expected=[decoded[(row[k]['artifact_id'],row[k]['sha256'])] for k in ('geometry_ref','original_ref')]
                    if stamp(value[1][sid])!=stamp(expected[0]) or stamp(value[2][sid])!=stamp(expected[1]):raise ValueError('PREPARATION_ADAPTER_GEOMETRY_CHANGED')
            owner.validate();self.last_preparation=owner.diagnostics()
            return result
    def plan(self,*args,**kwargs):return self._call('plan',*args,**kwargs)
    def run(self,*args,**kwargs):return self._call('run',*args,**kwargs)
    def verify(self,*args,**kwargs):return self._call('verify',*args,**kwargs)

def prepare_adapter(adapter):return adapter if adapter is None or isinstance(adapter,PreparedAdapter) else PreparedAdapter(adapter)

def native_operation(fn):
    """Activate shared preparation before native service construction."""
    @wraps(fn)
    def call(*args,**kwargs):
        root=str(args[0]) if args else str(kwargs.get('session',kwargs.get('root','')))
        request=args[1] if len(args)>1 and isinstance(args[1],dict) else {}
        binding=fn.__module__+'.'+fn.__name__+':'+root+':'+str(request.get('operation','native'))
        with worker_resources(binding):return fn(*args,**kwargs)
    return call

def prepared_dispatch(factory,request):
    # Preparation starts before service construction and native source parsing.
    binding='native-dispatch:'+digest(canonical(request))
    with worker_resources(binding):return factory().dispatch(request)

def prepared_buffer(shape,distance,**kwargs):
    memo=geometry_memo()
    return shape.buffer(distance,**kwargs) if memo is None else memo.construct('app-buffer',[shape],(distance,tuple(sorted(kwargs.items()))),lambda:shape.buffer(distance,**kwargs))

def prepared_intersection(left,right):
    memo=geometry_memo()
    return left.intersection(right) if memo is None else memo.intersection(left,right)
