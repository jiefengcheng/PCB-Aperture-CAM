"""Separator-conditioned trial state; predicates/report order stay in checker.py.

Partitions use the AABB report-dependency supergraph, not the tighter feasibility
only graph: even a passing distant pair's reported distance must stay identical.
Immutable row snapshots validate each new row and carry validated unchanged rows.
All ordinary mutable sequences and out-of-domain indexes retain legacy paths.
"""
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
import numpy as np
from shapely.geometry import box
from src.u03_analysis.graph import recursive_partition
from src.stage_abi.store import canonical,digest
from .assembly import CandidateSnapshot,CandidateTrace
from .source_union import SourceUnionWidthScene
from .dependency import Certificates


class PartitionMap(Mapping):
    """Immutable shallow shards; replacement copies touched pieces only."""
    def __init__(self,base,positions,shards,keys):
        self.base=base;self.positions=positions;self.shards=shards;self._keys=keys
    def __getitem__(self,key):
        p=self.positions.get(key)
        return self.base[key] if p is None else self.shards[p][key]
    def __iter__(self):return iter(self._keys)
    def __len__(self):return len(self._keys)
    def replace(self,updates):
        pieces={}
        for key,value in updates.items():
            p=self.positions[key]
            if p not in pieces:pieces[p]=dict(self.shards[p])
            pieces[p][key]=value
        shards=list(self.shards)
        for p,values in pieces.items():shards[p]=MappingProxyType(values)
        return PartitionMap(self.base,self.positions,tuple(shards),self._keys)


class SeparatorPlan:
    def __init__(self,ids,trace_ids,groups,tree,limits,guard,leaf_limit):
        names=sorted(set(groups.values()));index={g:i for i,g in enumerate(names)};graph={i:set() for i in range(len(names))}
        for i,sid in enumerate(ids):
            if sid not in trace_ids:continue
            a,b,c,d=limits[i];g=index[groups[sid]]
            for j in tree.query(box(a-guard,b-guard,c+guard,d+guard)):
                oid=ids[int(j)]
                if oid not in trace_ids:continue
                h=index[groups[oid]]
                if h!=g:graph[g].add(h);graph[h].add(g)
        partition=recursive_partition(graph,leaf_limit)
        self.regions=[]
        for r in partition['records']:
            values=r['nodes'] if r['leaf'] else r['separator']['vertices']
            self.regions.append(tuple(names[g] for g in values))
        self.owner={g:i for i,region in enumerate(self.regions) for g in region}
        assert len(self.owner)==len(names) and sum(map(len,self.regions))==len(names)
        self.boundaries=[];self.consumers={g:set() for g in names}
        for i,region in enumerate(self.regions):
            own=set(region);boundary={names[h] for g in region for h in graph[index[g]]}-own
            self.boundaries.append(tuple(sorted(boundary)))
            for g in own|boundary:self.consumers[g].add(i)
        self.group_routes={g:[] for g in names}
        for sid in sorted(trace_ids):self.group_routes[groups[sid]].append(sid)
        self.positions={sid:self.owner[groups[sid]] for sid in trace_ids}
        self.diagnostics=dict(groups=len(names),regions=len(self.regions),leaves=partition['leaf_count'],
            separator_groups=partition['separator_vertices_total'],largest_leaf=max(partition['leaf_sizes'],default=0),
            largest_separator=max(partition['separator_sizes'],default=0),
            maximum_leaf_boundary=partition['maximum_leaf_boundary'],edges=sum(map(len,graph.values()))//2)
        self.sha256=digest(canonical(dict(regions=[list(r) for r in self.regions],boundaries=[list(b) for b in self.boundaries])))


class LocalBoundsView:
    def __init__(self,checker,state):self.checker=checker;self.state=state;self.memo=OrderedDict();self.weight=0
    def query(self,geometry):
        key=geometry.bounds
        if key in self.memo:self.memo.move_to_end(key);return self.memo[key]
        c=self.checker;indices=c.dependency_tree.query(geometry);x0,y0,x1,y1=key
        # Only this local query's candidates need actual AABB lookup. Fixed
        # objects retain source bounds, and trial bounds live in immutable shards.
        bounds=np.asarray([self.state.bounds[c.ids[int(i)]] for i in indices]).reshape((-1,4))
        valid=(bounds[:,0]<=x1)&(bounds[:,2]>=x0)&(bounds[:,1]<=y1)&(bounds[:,3]>=y0)
        result=indices[valid];result.setflags(write=False);size=result.nbytes+128
        if size<=8*1024**2:
            while self.memo and (self.weight+size>8*1024**2 or len(self.memo)>=1024):
                _,old=self.memo.popitem(last=False);self.weight-=old.nbytes+128
            self.memo[key]=result;self.weight+=size
        return result


@dataclass
class TrialState:
    snapshot: object
    current: PartitionMap
    rows: PartitionMap
    versions: PartitionMap
    bounds: PartitionMap
    outliers: frozenset
    pending: set
    conditions: dict


class SeparatorWidthScene(SourceUnionWidthScene):
    def __init__(self,*args,separator_leaf_limit=64,condition_budget=16*1024**2,**kwargs):
        if type(separator_leaf_limit) is not int or separator_leaf_limit<1 or type(condition_budget) is not int or condition_budget<0:
            raise ValueError('U03_SEPARATOR_BUDGET_INVALID')
        super().__init__(*args,**kwargs)
        guard=self.contract.construction_gap_mm+self.contract.comparison_epsilon_mm
        self.plan=SeparatorPlan(self.ids,self.trace_ids,self.groups,self.dependency_tree,self.limits,guard,separator_leaf_limit)
        self.route_order=tuple(sorted(self.trace_ids));self.state=None;self.prepared=None
        self.state_views=OrderedDict();self.local_proofs=Certificates(self.binding,condition_budget)
        self.validated_rows=0;self.reused_rows=0;self.local_index_views=0;self.condition_builds=0;self.condition_invalidations=0

    def _map(self,values,*,base=None,keys=None):
        shards=[{} for _ in self.plan.regions]
        for sid,value in values.items():shards[self.plan.positions[sid]][sid]=value
        return PartitionMap({} if base is None else base,self.plan.positions,tuple(MappingProxyType(s) for s in shards),self.route_order if keys is None else keys)

    def _prepare(self,traces):
        if len(traces)!=len(self.route_order):raise ValueError('COMPLETE_TRACE_IDENTITIES_CHANGED')
        prior=self.state;changed={};versions={};bounds={};geometries={};outliers=set(() if prior is None else prior.outliers)
        for i,(sid,row) in enumerate(zip(self.route_order,traces,strict=True)):
            if row.id!=sid:raise ValueError('COMPLETE_TRACE_IDENTITIES_CHANGED')
            if prior is not None and row is prior.snapshot[i]:self.reused_rows+=1;continue
            self.valid_geometry(row.candidate)
            if self.cached_sha(row.original)!=self.trace_ids[sid] or row.verified_original_width_mm!=self.widths[sid]:raise ValueError('ORIGINAL_TRACE_BINDING_CHANGED')
            self.validated_rows+=1;changed[sid]=row;versions[sid]=self.cached_sha(row.candidate);bounds[sid]=row.candidate.bounds;geometries[sid]=row.candidate
            a,b,c,d=bounds[sid];x,y,z,w=self.limits[self.positions[sid]]
            if x<=a and y<=b and z>=c and w>=d:outliers.discard(sid)
            else:outliers.add(sid)
        if prior is None:
            current=self._map(geometries,base=self.original,keys=tuple(self.ids));rows=self._map(changed)
            version_map=self._map(versions);bound_map=self._map(bounds,base={s:self.original[s].bounds for s in self.fixed_ids},keys=tuple(self.ids));pending=set(versions);conditions={}
        else:
            current=prior.current.replace(geometries);rows=prior.rows.replace(changed);version_map=prior.versions.replace(versions);bound_map=prior.bounds.replace(bounds)
            pending={s for s,v in versions.items() if prior.versions[s]!=v}
            invalid=set().union(*(self.plan.consumers[self.groups[s]] for s in pending)) if pending else set()
            conditions={p:key for p,key in prior.conditions.items() if p not in invalid};self.condition_invalidations+=len(invalid)
        return TrialState(traces,current,rows,version_map,bound_map,frozenset(outliers),pending,conditions)

    def check(self,traces,*,materialize_scene=False,fail_fast=False):
        optimized=(fail_fast and not materialize_scene and type(traces) is CandidateSnapshot and
            type(traces.rows) is tuple and all(type(r) is CandidateTrace for r in traces))
        try:
            if self.contract!=self.bound_contract:raise ValueError('U03_DEPENDENCY_POLICY_CHANGED')
            self.prepared=self._prepare(traces) if optimized else None
            if materialize_scene or not fail_fast:self.local_proofs.clear()
            result=super().check(traces,materialize_scene=materialize_scene,fail_fast=fail_fast)
            self.state=self.prepared if optimized else None
            return result
        except BaseException:
            self.close();raise
        finally:self.prepared=None

    def trial_versions(self,traces):
        if self.prepared is None:return super().trial_versions(traces)
        # Mutable-sequence/full-check transitions establish a new immutable state.
        return self.prepared.versions,self.prepared.pending

    def prepare_trial(self,traces):
        state=self.prepared
        if state is None:return super().prepare_trial(traces)
        if self.accepted_current is None:changed=set(self.trace_ids)
        elif isinstance(self.accepted_current,PartitionMap) and self.accepted_current.positions is state.current.positions:
            changed=set()
            for p,shard in enumerate(state.current.shards):
                accepted=self.accepted_current.shards[p]
                if shard is accepted:continue
                changed.update(s for s,g in shard.items() if self.cached_sha(g)!=self.cached_sha(accepted[s]))
        else:changed={s for s in self.trace_ids if state.versions[s]!=self.cached_sha(self.accepted_current[s])}
        return state.current,state.rows,changed

    def spatial_index(self,current):
        old=self.state_views.get(id(current))
        if old is not None and old[0] is current:return old[1]
        states=(self.prepared,self.state)
        state=next((s for s in states if s is not None and s.current is current),None)
        # An accepted state's view is retained independently of the last trial.
        if state is None or state.outliers:return super().spatial_index(current)
        view=LocalBoundsView(self,state);self.local_index_views+=1;self.state_views[id(current)]=(current,view)
        while len(self.state_views)>4:self.state_views.popitem(last=False)
        return view

    def _condition(self,sid):
        state=self.prepared;region=self.plan.positions[sid]
        key=state.conditions.get(region)
        if key is None:
            groups=(*self.plan.regions[region],*self.plan.boundaries[region])
            values=[[s,state.versions[s]] for g in groups for s in self.plan.group_routes[g]]
            key=digest(canonical(dict(binding=self.binding,partition=self.plan.sha256,region=region,versions=values)))
            state.conditions[region]=key;self.condition_builds+=1
        return key

    def _local_key(self,sid,current,tree):
        # Complete pointwise context additionally pins dynamic visibility tokens
        # and exact queried neighbors, including all fixed-obstacle witnesses.
        key,deps=self._context(sid,current,tree)
        return digest(canonical([self._condition(sid),key])),deps

    def route_proof(self,sid,current,tree):
        if self.prepared is None or self.prepared.outliers or self.cached_sha(current[sid])==self.trace_ids[sid]:return super().route_proof(sid,current,tree)
        key,deps=self._local_key(sid,current,tree);q=self.local_proofs.get(key)
        if q is None:return None
        self.graph.register(sid,key,deps);return q['result'],q['failures']

    def save_route_proof(self,sid,current,tree,result,failures):
        if self.prepared is None or self.prepared.outliers or self.cached_sha(current[sid])==self.trace_ids[sid]:return super().save_route_proof(sid,current,tree,result,failures)
        key,deps=self._local_key(sid,current,tree)
        if self.local_proofs.put(key,dict(result=result,failures=failures),deps):self.graph.register(sid,key,deps)

    def diagnostics(self):
        return dict(super().diagnostics(),separator_plan=self.plan.diagnostics,separator_plan_sha256=self.plan.sha256,
            validated_trial_rows=self.validated_rows,reused_trial_rows=self.reused_rows,local_index_views=self.local_index_views,
            condition_builds=self.condition_builds,condition_invalidations=self.condition_invalidations,
            conditioned_hits=self.local_proofs.hits,conditioned_misses=self.local_proofs.misses,conditioned_bytes=self.local_proofs.weight)
