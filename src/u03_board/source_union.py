"""Bounded lookahead for *identical* source unions, consumed in serial order.

The original R-tree keys, ordered operands and GEOS unary union are unchanged.
Workers touch immutable geometry only; all LRU/proof/report mutations stay on the
coordinator. Final closure drains workers and uses the original serial path.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from shapely import get_num_coordinates,to_wkb,get_precision
from shapely.geometry import box
from shapely.ops import unary_union
from .dependency import DependencyWidthScene
from src.stage_abi.store import canonical,digest


@dataclass(frozen=True)
class UnionProof:
    binding: str
    operands_sha256: str
    geometry: object
    geometry_sha256: str
    precision: float


def construct_union(binding,key,operands):
    geometry=unary_union(operands)
    return UnionProof(binding,digest(canonical(list(key))),geometry,
        digest(to_wkb(geometry,include_srid=True)),get_precision(geometry))


class SourceUnionWidthScene(DependencyWidthScene):
    def __init__(self,*args,union_workers=3,union_prefetch_bytes=128*1024**2,union_lookahead=8,**kwargs):
        if any(type(v) is not int or v<0 for v in (union_workers,union_prefetch_bytes,union_lookahead)) or union_workers>3 or union_lookahead>32:
            raise ValueError('U03_SOURCE_UNION_BUDGET_INVALID')
        super().__init__(*args,**kwargs)
        self.union_workers=union_workers;self.union_prefetch_bytes=union_prefetch_bytes;self.union_lookahead=union_lookahead
        self.source_union_search=True;self.pool=None;self.pending=OrderedDict();self.pending_weight=0
        self.source_sizes=[int(get_num_coordinates(self.original[s])) for s in self.ids]
        self.union_submitted=0;self.union_hits=0;self.union_unused=0;self.union_serial=0;self.union_peak_bytes=0
        self.route_view=None;self.epoch=0;self.epochs={};self.planned={};self.validated={}

    def _validate(self,key,future):
        proof=future.result()
        old=self.validated.get(key)
        if old is not None and old==(future,proof.binding,proof.operands_sha256,proof.geometry_sha256,proof.precision,id(proof.geometry)):
            return proof.geometry
        if (proof.binding!=self.binding or proof.operands_sha256!=digest(canonical(list(key))) or
            proof.geometry_sha256!=digest(to_wkb(proof.geometry,include_srid=True)) or
            proof.precision!=get_precision(proof.geometry)):
            raise ValueError('U03_SOURCE_UNION_CERTIFICATE_CHANGED')
        self.validated[key]=(future,proof.binding,proof.operands_sha256,proof.geometry_sha256,proof.precision,id(proof.geometry))
        return proof.geometry

    def _take(self,key):
        row=self.pending.pop(key,None)
        if row is not None:
            self.pending_weight-=row[1];self.epochs.pop(key,None)
            self.planned={token:k for token,k in self.planned.items() if k!=key}
        return row

    def _done(self):
        # A speculative computation failure/corrupt certificate is never hidden
        # by a cache eviction or a later route that no longer needs the union.
        for key,(future,_) in self.pending.items():
            if future.done():self._validate(key,future)

    def _submit(self,sid,candidate):
        if not self.union_workers or not self.union_prefetch_bytes:return
        token=sid,self.cached_sha(candidate)
        if token in self.planned:return
        if len(self.pending)>=4 and not any(f.done() and self.epochs[k]!=self.epoch for k,(f,_) in self.pending.items()):return
        key=self.original_union_key(sid,candidate)
        if key in self.original_union_cache or key in self.pending:return
        coordinates=sum(self.source_sizes[i] for i in key)
        if coordinates<4096:return
        weight=64*coordinates+40*len(key)+1024
        if weight>self.union_prefetch_bytes:return
        # Four bounded slots, three worker threads; no global executor/config.
        while self.pending and (len(self.pending)>=4 or self.pending_weight+weight>self.union_prefetch_bytes):
            old=next((k for k,(f,_) in self.pending.items() if f.done() and self.epochs[k]!=self.epoch),None)
            if old is None:return
            future,size=self._take(old);self._validate(old,future);self.validated.pop(old,None);self.union_unused+=1
        if self.pool is None:self.pool=ThreadPoolExecutor(max_workers=self.union_workers,thread_name_prefix='u03-source-union')
        operands=[self.original[self.ids[i]] for i in key]
        future=self.pool.submit(construct_union,self.binding,key,operands)
        self.pending[key]=(future,weight);self.pending_weight+=weight
        self.epochs[key]=self.epoch;self.planned[token]=key
        self.union_submitted+=1;self.union_peak_bytes=max(self.union_peak_bytes,self.pending_weight)

    def _prefetch(self,sid,oid,current):
        if not self.source_union_search or not self.union_workers or not self.union_prefetch_bytes or not self.union_lookahead:return
        if self.route_view is None or self.route_view[0] is not current or self.route_view[1]!=sid:
            self.epoch+=1
            radius=self.contract.construction_gap_mm+self.contract.comparison_epsilon_mm
            x0,y0,x1,y1=current[sid].bounds
            neighbors=[self.ids[int(i)] for i in sorted(self.spatial_index(current).query(box(x0-radius,y0-radius,x1+radius,y1+radius)))]
            self.route_view=(current,sid,neighbors,{s:i for i,s in enumerate(neighbors)})
        neighbors,positions=self.route_view[2:];start=positions[oid]+1
        added=self.added_cache[sid][1];core=self.original[sid];c=self.contract
        for neighbor in neighbors[start:start+self.union_lookahead]:
            if neighbor==sid:continue
            version=self.cached_sha(current[neighbor]);entry=self.visible_cache.get(neighbor)
            if entry is not None and entry[0]==version:continue
            if ('visible',neighbor,version) in self.geometries:continue
            retained=self.trace_visibility.get(neighbor,self.fixed_visibility.get(neighbor))
            if retained is not None and retained[0]==version:continue
            pair=sid,neighbor
            if pair not in self.incremental_ports:
                overlap=core.intersection(self.original[neighbor])
                self.incremental_ports[pair]=None if overlap.is_empty else overlap.buffer(max(self.widths[sid],self.widths[neighbor])+c.original_port_buffer_gap_mm,quad_segs=c.port_quad_segs)
            checked=self.checked_copper(sid,neighbor,current[sid],added,self.incremental_ports[pair])
            if not checked.is_empty:self._submit(neighbor,current[neighbor])

    def pair_visibility(self,sid,oid,checked,current):
        if not checked.is_empty:self._prefetch(sid,oid,current)
        return super().pair_visibility(sid,oid,checked,current)

    def compute_original_union(self,key):
        row=self._take(key)
        if row is not None:
            future,size=row;self.union_hits+=1
            geometry=self._validate(key,future);self.validated.pop(key,None);return geometry
        self.union_serial+=1
        return super().compute_original_union(key)

    def drain(self):
        for key,(future,_) in self.pending.items():self._validate(key,future)

    def close(self):
        if self.pool is not None:
            self.pool.shutdown(wait=True);self.pool=None
        try:self.drain()
        finally:
            self.union_unused+=len(self.pending);self.pending.clear();self.pending_weight=0;self.route_view=None
            self.validated.clear();self.epochs.clear();self.planned.clear()

    def check(self,traces,*,materialize_scene=False,fail_fast=False):
        if materialize_scene or not fail_fast:
            self.close();self.source_union_search=False
        self._done()
        try:
            result=super().check(traces,materialize_scene=materialize_scene,fail_fast=fail_fast)
            self._done();return result
        except BaseException:
            self.close();raise

    def diagnostics(self):
        return dict(super().diagnostics(),source_union_search=self.source_union_search,
            source_union_workers=self.union_workers,source_union_submitted=self.union_submitted,
            source_union_prefetch_hits=self.union_hits,source_union_unused=self.union_unused,
            source_union_serial=self.union_serial,source_union_pending=len(self.pending),
            source_union_pending_estimated_bytes=self.pending_weight,source_union_peak_estimated_bytes=self.union_peak_bytes,
            source_union_cache_hits=self.original_union_hits,source_union_cache_misses=self.original_union_misses)
