"""Bounded source-bound proof graph and conservative packed R-tree views.

The original source STRtree and its union operand order are deliberately kept.
This second index only replaces current/previous candidate broad-phase queries.
Every query filters maximum envelopes against the actual versioned AABBs.
Certificates are feasibility witnesses, not independently optimal width choices.
"""
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, asdict
import json
import numpy as np
from shapely import STRtree, to_wkb
from shapely.geometry import box
from src.native_inventory import ERROR_MM
from src.stage_abi.store import canonical, digest
from src.source_offset_width import FAMILY
from .assembly import CandidateSnapshot
from .checker import IncrementalWidthScene


@dataclass(frozen=True)
class Certificate:
    binding: str
    context: str
    payload: bytes
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class RouteTrial:
    """The last checked overlay and the accepted state it started from."""
    accepted: dict
    current: dict
    route_id: str
    version: str


class Certificates:
    def __init__(self,binding,budget):
        self.binding=binding;self.budget=budget;self.entries=OrderedDict()
        self.weight=0;self.hits=0;self.misses=0;self.evictions=0

    def get(self,key):
        row=self.entries.get(key)
        if row is None:self.misses+=1;return None
        proof,weight=row
        if proof.binding!=self.binding or proof.context!=key or digest(proof.payload)!=proof.payload_sha256:
            raise ValueError('U03_DEPENDENCY_CERTIFICATE_CHANGED')
        self.hits+=1;self.entries.move_to_end(key)
        envelope=json.loads(proof.payload)
        if envelope['binding']!=self.binding or envelope['context']!=key:
            raise ValueError('U03_DEPENDENCY_CERTIFICATE_CHANGED')
        return envelope['value']

    def put(self,key,value,dependencies=()):
        payload=canonical(dict(schema='u03-geometry-proof/1',binding=self.binding,context=key,
            dependencies=[list(d) for d in dependencies],value=value))
        weight=len(payload)+len(key)+256
        if weight>self.budget:return False
        if key in self.entries:self.weight-=self.entries.pop(key)[1]
        while self.entries and (self.weight+weight>self.budget or len(self.entries)>=8192):
            _,(_,size)=self.entries.popitem(last=False);self.weight-=size;self.evictions+=1
        self.entries[key]=(Certificate(self.binding,key,payload,digest(payload)),weight);self.weight+=weight
        return True

    def clear(self):self.entries.clear();self.weight=0


class ProofGraph:
    """Active consumers; old exact-version certificates remain usable on rollback.

The edge budget bounds diagnostics and eager invalidation. Cache authority always
comes from a freshly validated complete context, even if an active edge evicts.
    """
    def __init__(self,edge_budget=100000):
        self.active=OrderedDict();self.reverse=defaultdict(set);self.edges=0
        self.edge_budget=edge_budget;self.invalidated=0

    def drop(self,sid):
        old=self.active.pop(sid,None)
        if old is None:return
        for dependency in old[1]:
            self.reverse[dependency].discard(sid);self.edges-=1
            if not self.reverse[dependency]:del self.reverse[dependency]

    def register(self,sid,key,dependencies):
        self.drop(sid);versions=tuple(tuple(d) for d in dependencies);deps=frozenset(d[0] for d in versions)
        if len(deps)>self.edge_budget:return
        while self.active and self.edges+len(deps)>self.edge_budget:self.drop(next(iter(self.active)))
        self.active[sid]=(key,deps,versions)
        for node in deps:self.reverse[node].add(sid);self.edges+=1

    def invalidate(self,changed):
        consumers=set().union(*(self.reverse.get(s,set()) for s in changed)) if changed else set()
        self.invalidated+=len(consumers)
        for sid in consumers:self.drop(sid)
        return consumers

    def clear(self):self.active.clear();self.reverse.clear();self.edges=0


class BoundsView:
    def __init__(self,tree,limits,bounds):
        self.tree=tree;self.limits=limits;self.bounds=bounds;self.memo=OrderedDict();self.weight=0

    def with_bounds(self, position, bounds):
        """Reuse the maximum-envelope tree when one row fits its original limit."""
        limits = self.limits[position]
        if np.any(bounds[:2] < limits[:2]) or np.any(bounds[2:] > limits[2:]):
            return None
        updated = self.bounds.copy()
        updated[position] = bounds
        updated.setflags(write=False)
        return BoundsView(self.tree, self.limits, updated)

    def query(self,geometry):
        key=geometry.bounds
        if key not in self.memo:
            indices=self.tree.query(geometry)
            a=self.bounds[indices];x0,y0,x1,y1=key
            valid=(a[:,0]<=x1)&(a[:,2]>=x0)&(a[:,1]<=y1)&(a[:,3]>=y0)
            result=indices[valid];result.setflags(write=False)
            size=result.nbytes+128
            if size>8*1024**2:return result
            while self.memo and (self.weight+size>8*1024**2 or len(self.memo)>=1024):
                _,previous=self.memo.popitem(last=False);self.weight-=previous.nbytes+128
            self.memo[key]=result;self.weight+=size
        self.memo.move_to_end(key)
        return self.memo[key]


class DependencyWidthScene(IncrementalWidthScene):
    def __init__(self,traces,fixed,*,groups=None,source_binding=None,proof_budget=32*1024**2,geometry_budget=64*1024**2,**kwargs):
        if any(type(b) is not int or b<0 for b in (proof_budget,geometry_budget)):
            raise ValueError('U03_DEPENDENCY_CACHE_BUDGET_INVALID')
        super().__init__(traces,fixed,**kwargs)
        self.bound_contract=self.contract
        self.groups=dict(groups) if groups is not None else {s:s for s in self.trace_ids}
        if set(self.groups)!=set(self.trace_ids):raise ValueError('U03_DEPENDENCY_GROUP_COVERAGE_CHANGED')
        self.source_binding=source_binding
        self.binding=digest(canonical(dict(source_sha256=source_binding,geometry_family=FAMILY,
            groups=self.groups,contract=asdict(self.contract),objects=[
            dict(id=s,width=self.widths[s],sha=self.cached_sha(self.original[s])) for s in self.ids])))
        self.last_trial_versions=None;self.pending_changes=set()
        self.last_single_trial = None
        self.route_positions = {sid: i for i, sid in enumerate(sorted(self.trace_ids))}
        self.graph=ProofGraph();self.routes=Certificates(self.binding,proof_budget//2);self.pairs=Certificates(self.binding,proof_budget//2)
        self.geometry_budget=geometry_budget;self.geometries=OrderedDict();self.geometry_weight=0
        self.geometry_hits=0;self.empty_witnesses=0;self.visibility_tokens={};self.index_views=OrderedDict()
        from .visibility_records import VisibilityRecords
        self.visibility_records=VisibilityRecords(self)
        self.index_builds=1;self.index_fallbacks=0;self.bounds_updates=0
        self.positions={sid:i for i,sid in enumerate(self.ids)}
        self.fixed_ids=[sid for sid in self.ids if sid not in self.trace_ids]
        self.node_bounds={sid:(self.original[sid],self.original[sid].bounds) for sid in self.trace_ids}
        self.base_bounds=np.asarray([self.original[sid].bounds for sid in self.ids])
        bounds=[]
        for sid in self.ids:
            x0,y0,x1,y1=self.original[sid].bounds
            # Extra ERROR_MM is conservative index padding, not a clearance or
            # geometry tolerance. Actual AABB filtering below remains exact.
            pad=.25*self.widths[sid]+2*ERROR_MM if sid in self.trace_ids else 0.
            bounds.append((x0-pad,y0-pad,x1+pad,y1+pad))
        self.limits=np.asarray(bounds);self.dependency_tree=STRtree([box(*b) for b in bounds])
        self.limits.setflags(write=False);self.base_bounds.setflags(write=False)

    def check(self,traces,*,materialize_scene=False,fail_fast=False):
        from src import component_clearance
        if component_clearance.ACTIVE is not None:
            from src.prepared_width_scene import PreparedWidthScene
            return PreparedWidthScene.check(self,traces,materialize_scene=materialize_scene,fail_fast=fail_fast)
        if self.contract!=self.bound_contract:raise ValueError('U03_DEPENDENCY_POLICY_CHANGED')
        if self.last_single_trial is not None:
            self.last_single_trial = None
            self.last_trial_versions = None
        if materialize_scene or not fail_fast:
            # Full closure still executes the untouched PreparedWidthScene path.
            self.routes.clear();self.pairs.clear();self.graph.clear()
        versions,self.pending_changes=self.trial_versions(traces)
        result=super().check(traces,materialize_scene=materialize_scene,fail_fast=fail_fast)
        self.last_trial_versions=versions
        return result

    def _check_single_route(self, traces, proposal):
        """Prepare T04's checker-owned proposal against the accepted proof state."""
        from src import component_clearance
        if self.accepted_current is None or component_clearance.ACTIVE is not None:
            return self.check(traces, fail_fast=True)
        if self.contract != self.bound_contract:
            raise ValueError('U03_DEPENDENCY_POLICY_CHANGED')

        sid = proposal.id
        if (not isinstance(traces, CandidateSnapshot) or len(traces) != len(self.trace_ids)
                or sid not in self.trace_ids or traces[self.route_positions[sid]] is not proposal
                or self.cached_sha(proposal.original) != self.trace_ids[sid]
                or proposal.verified_original_width_mm != self.widths[sid]):
            raise ValueError('ORIGINAL_TRACE_BINDING_CHANGED')
        accepted = self.accepted_current
        candidate = proposal.candidate
        cached = self.geometry_hashes.get(id(candidate))
        if cached is None or cached[0] is not candidate:
            self.valid_geometry(candidate)
        version = self.cached_sha(candidate)
        accepted_version = self.accepted_results[sid]['candidate_sha256']
        changed = {sid} if version != accepted_version else set()
        current = accepted.copy()
        current[sid] = candidate

        previous = self.last_single_trial
        if previous is None or (accepted is not previous.accepted and accepted is not previous.current):
            # A restored or unrelated state has no validated local transition.
            self.graph.clear()
            self.pending_changes = set()
        elif accepted is previous.current:
            self.pending_changes = changed
        else:
            old_sid = previous.route_id
            versions = {sid: version}
            if old_sid != sid:
                versions[old_sid] = self.accepted_results[old_sid]['candidate_sha256']
            self.pending_changes = {
                route for route, value in versions.items()
                if value != (previous.version if route == old_sid else accepted_version)}

        oldtree = self.spatial_index(accepted)
        tree = oldtree.with_bounds(self.positions[sid], np.asarray(candidate.bounds)) if isinstance(oldtree, BoundsView) else None
        tree = self.spatial_index(current) if tree is None else self._remember_index(current, tree)
        report = self._check_prepared(traces, current, self.trace_ids, changed, tree, oldtree=oldtree)
        self.last_single_trial = RouteTrial(accepted, current, sid, version)
        self.last_trial_versions = None
        return report

    def trial_versions(self,traces):
        versions={r['id']:self.cached_sha(r['candidate']) for r in traces}
        changed=set(versions) if self.last_trial_versions is None else {
            s for s,v in versions.items() if self.last_trial_versions.get(s)!=v}
        return versions,changed

    def spatial_index(self,current):
        old=self.index_views.get(id(current))
        if old is not None and old[0] is current:
            self.index_views.move_to_end(id(current));return old[1]
        # Fixed copper is immutable in the native caller. Unexpected replacements
        # use the legacy index instead of relying on that authority implicitly.
        if any(current[s] is not self.original[s] for s in self.fixed_ids):
            self.index_fallbacks+=1
            return super().spatial_index(current)
        bounds=self.base_bounds.copy()
        for sid in self.trace_ids:
            g=current[sid];old_bounds=self.node_bounds[sid]
            if old_bounds[0] is not g:
                old_bounds=(g,g.bounds);self.node_bounds[sid]=old_bounds;self.bounds_updates+=1
            bounds[self.positions[sid]]=old_bounds[1]
        within=np.all(bounds[:,:2]>=self.limits[:,:2]) and np.all(bounds[:,2:]<=self.limits[:,2:])
        if within:view=BoundsView(self.dependency_tree,self.limits,bounds)
        else:
            # No unproved cap assumption: arbitrary or roundoff-outside inputs
            # get the exact legacy index, never an incomplete neighbor set.
            view=super().spatial_index(current);self.index_fallbacks+=1
        return self._remember_index(current, view)

    def _remember_index(self, current, view):
        self.index_views[id(current)]=(current,view)
        while len(self.index_views)>3:self.index_views.popitem(last=False)
        return view

    def invalidate_proofs(self,changed):
        # Active graph state follows the last trial, including rejected states.
        # The original checker's affected set still follows the accepted state.
        self.graph.invalidate(self.pending_changes)

    def _visible_token(self,sid,current):
        entry=self.visible_cache.get(sid)
        if entry is None or entry[0]!=self.cached_sha(current[sid]):return None
        old=self.visibility_tokens.get(sid)
        if old is None or old[0] is not entry[1]:
            old=(entry[1],digest(to_wkb(entry[1])));self.visibility_tokens[sid]=old
        return old[1]

    def _context(self,sid,current,tree):
        own=self.cached_sha(current[sid]);neighbors=[]
        if own!=self.trace_ids[sid]:
            r=self.contract.construction_gap_mm+self.contract.comparison_epsilon_mm
            x0,y0,x1,y1=current[sid].bounds
            for i in sorted(tree.query(box(x0-r,y0-r,x1+r,y1+r)).tolist()):
                oid=self.ids[i]
                if oid!=sid:neighbors.append([oid,self.cached_sha(current[oid]),self._visible_token(oid,current)])
        key=digest(canonical(dict(source=self.binding,route=sid,version=own,neighbors=neighbors)))
        return key,[[sid,own,None],*neighbors]

    def route_proof(self,sid,current,tree):
        key,deps=self._context(sid,current,tree);q=self.routes.get(key)
        if q is None:return None
        self.graph.register(sid,key,deps)
        return q['result'],q['failures']

    def save_route_proof(self,sid,current,tree,result,failures):
        key,deps=self._context(sid,current,tree)
        if self.routes.put(key,dict(result=result,failures=failures),deps):self.graph.register(sid,key,deps)

    def _geometry(self,key):
        row=self.geometries.get(key)
        if row is None:return None
        self.geometries.move_to_end(key);self.geometry_hits+=1
        return row[0]

    def _save_geometry(self,key,g):
        weight=2*len(to_wkb(g))+sum(len(part) for part in key)+len(key)-1+256
        if weight>self.geometry_budget:return
        if key in self.geometries:self.geometry_weight-=self.geometries.pop(key)[1]
        while self.geometries and (self.geometry_weight+weight>self.geometry_budget or len(self.geometries)>=8192):
            _,(_,size)=self.geometries.popitem(last=False);self.geometry_weight-=size
        self.geometries[key]=(g,weight);self.geometry_weight+=weight

    def visible_geometry(self,sid,current):
        version=self.cached_sha(current[sid]);entry=self.visible_cache.get(sid)
        if entry is not None and entry[0]==version:return entry[1]
        key=('visible',sid,version);g=self._geometry(key)
        if g is None:
            g=self.visibility_records.get(sid,version)
            if g is not None:self._save_geometry(key,g)
        if g is None:
            g=super().visible_geometry(sid,current);self._save_geometry(key,g)
        else:self.set_visible(sid,(version,g))
        return g

    def checked_copper(self,sid,oid,candidate,added,port):
        if port is None:return added
        key=('checked',sid,self.cached_sha(candidate),oid)
        g=self._geometry(key)
        if g is None:
            g=super().checked_copper(sid,oid,candidate,added,port);self._save_geometry(key,g)
        return g

    def pair_visibility(self,sid,oid,checked,current):
        if checked.is_empty:
            # Exact predicate certificate: distance is None for empty checked
            # copper irrespective of the neighbor. Its visibility is irrelevant.
            self.empty_witnesses+=1
            version=self.cached_sha(checked)
            key=digest(canonical([self.binding,'EMPTY_CHECKED_COPPER',version]))
            if self.pairs.get(key) is None:
                self.pairs.put(key,dict(gap=None,reason='EMPTY_CHECKED_COPPER'),[['checked',version]])
            return checked
        return self.visible_geometry(oid,current)

    def exact_distance(self,sid,oid,checked,neighbor):
        a,b=self.cached_sha(checked),self.cached_sha(neighbor)
        key=digest(canonical([self.binding,sid,oid,a,b]))
        q=self.pairs.get(key)
        if q is not None:return q['gap']
        gap=super().exact_distance(sid,oid,checked,neighbor);self.pairs.put(key,dict(gap=gap),[[sid+':checked',a],[oid+':visible',b]])
        return gap

    def diagnostics(self):
        return dict(binding=self.binding,index_builds=self.index_builds,index_fallbacks=self.index_fallbacks,
            source_sha256=self.source_binding,bounds_updates=self.bounds_updates,groups=len(set(self.groups.values())),
            active_proofs=len(self.graph.active),dependency_edges=self.graph.edges,invalidated=self.graph.invalidated,
            route_hits=self.routes.hits,route_misses=self.routes.misses,pair_hits=self.pairs.hits,pair_misses=self.pairs.misses,
            proof_bytes=self.routes.weight+self.pairs.weight,geometry_hits=self.geometry_hits,geometry_bytes=self.geometry_weight,
            empty_checked_witnesses=self.empty_witnesses)
