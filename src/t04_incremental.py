"""Route-local exact owner checks; immutable baseline and one prepared index.

Distance to a union is the minimum of distances to its operands. Checking a
new route's additions against frozen foreign owners and accepted foreign route
contributions therefore avoids rebuilding complete owner unions at each rung.
Full PreparedWidthScene validation remains a separate final gate.
"""
from collections import OrderedDict
from shapely import STRtree
from shapely.geometry import box
from shapely.ops import unary_union
from src.component_distance import distance
from src.stage_abi.store import canonical, digest
from src.u03_board.assembly import CandidateTrace, CandidateSnapshot


class OwnerDependencies:
    def __init__(self, parent, context, route_ids, maximum_padding, scope):
        self.context = context; self.binding = context.binding; self.scope = scope
        self.before = context.project(parent.original)
        self.owners = {s:context.owner(s,parent.original[s]) for s in route_ids}
        self.ids = sorted(self.before)
        from src.gerber_u05.checking_envelopes import constraint
        self.foreign = {o:constraint(context,o,self.before[o]) for o in self.ids}
        self.tree = STRtree([self.foreign[o] for o in self.ids])
        self.route_ids = list(route_ids)
        self.route_tree = STRtree([box(*parent.original[s].bounds).buffer(maximum_padding[s]).envelope
                                  for s in route_ids])
        self.gap = parent.required_new_copper_gap()
        self.epsilon = parent.contract.comparison_epsilon_mm
        self.cache = OrderedDict(); self.bytes = 0; self.limit = 16*1024**2
        from src.t04_topology import SourceVoids
        self.source_voids=SourceVoids(self,self.limit)
        self.source_void_bytes=self.source_voids.bytes;self.bytes=self.source_void_bytes
        self.exact_distances = self.hits = 0

    def memo(self, key, calculate):
        if key in self.cache:
            self.hits += 1; self.cache.move_to_end(key); return self.cache[key][0]
        result = calculate(); size = len(canonical(result)) + len(canonical(list(key))) + 128
        if size <= self.limit-getattr(self,'source_void_bytes',0):
            while self.cache and (self.bytes+size>self.limit or len(self.cache)>=8192):
                self.bytes -= self.cache.popitem(last=False)[1][1]
            self.cache[key]=(result,size); self.bytes+=size
        return result

    def check(self,sid,factor,candidate,current,versions):
        from src import component_clearance as physical,source_channel_scope as functional
        active=physical.ACTIVE if self.scope=='PHYSICAL_ORIGINAL_OWNER' else functional.ACTIVE
        if active is not self.context or self.context.binding != self.binding:
            raise ValueError('T04_FROZEN_OWNER_DEPENDENCIES_CHANGED')
        own=self.owners[sid]
        # The owner baseline includes prior stages, preserving integral joints.
        from src.component_clearance import joined,surfaces
        delta=joined(surfaces(candidate.difference(self.before[own])))
        if delta.is_empty:return dict(passed=True,failures=[],pairs=[],scope=self.scope)
        query=delta.envelope.buffer(self.gap+self.epsilon).envelope; pairs=[];failures=[]
        def measured(other,geometry,key):
            def calculate():
                self.exact_distances+=1
                return float(distance(delta,geometry))
            gap=self.memo(key,calculate);passed=gap+self.epsilon>=self.gap
            pairs.append(dict(foreign_id=other,gap_mm=gap,passed=passed))
            if not passed:failures.append(dict(trace_id=sid,owner=own,foreign_id=other,
                                               reason='NEW_COPPER_BELOW_FOREIGN_COMPONENT_GAP',
                                               gap_mm=gap,clearance_scope=self.scope))
        for i in sorted(map(int,self.tree.query(query))):
            other=self.ids[i]
            if other!=own:
                measured(other,self.foreign[other],('base',sid,factor,other))
                if failures:break
        if not failures:
            for i in sorted(map(int,self.route_tree.query(query))):
                other=self.route_ids[i]
                if self.owners[other]!=own and versions[other]!=1:
                    measured(other,current[other],('route',sid,factor,other,versions[other]))
                    if failures:break
        if not failures:
            # Frozen 20% partial-pocket budgets are also checked locally. Union
            # only pieces inside a registered pocket; never reconstruct a board.
            for value in self.context.approved_partial_pockets.values():
                spec=value['spec'];key='original_channel_id' if self.scope=='FUNCTIONAL_SOURCE_CHANNEL' else 'original_owner_id'
                if spec[key]!=own or not candidate.intersects(value['initial']):continue
                patch=value['initial']; pieces=[self.before[own].intersection(patch),candidate.intersection(patch)]
                pieces.extend(current[s].intersection(patch) for s in self.route_ids
                              if s!=sid and self.owners[s]==own and versions[s]!=1 and current[s].intersects(patch))
                body=unary_union(pieces)
                if body.area>spec['decision']['maximum_added_area_mm2'] or body.intersection(value['protected_core']).area>value['contract'].area_epsilon_mm2:
                    failures.append(dict(trace_id=sid,reason='FROZEN_PARTIAL_POCKET_BUDGET_OR_OPENING_CHANGED',clearance_scope=self.scope))
        return dict(passed=not failures,failures=failures,pairs=pairs,scope=self.scope)


class IncrementalRoutes:
    def __init__(self,baseline,fixed,build,settings,source_widths,*,checking_headroom_mm=0.):
        from src.prepared_width_scene import PreparedWidthScene
        from src import component_clearance as cc, source_channel_scope as functional, pin_separation as pin
        self.parent=PreparedWidthScene(baseline,fixed);self.build=build
        self.order=sorted(r['id']for r in baseline);self.positions={s:i for i,s in enumerate(self.order)}
        self.current={r['id']:r['original']for r in baseline};self.versions=dict.fromkeys(self.order,1.)
        self.rows=[CandidateTrace(s,self.current[s],self.current[s],self.parent.widths[s])for s in self.order]
        self.pending=None;self.constructed_routes=self.accepted_updates=0
        self.owner_checks=[];self.pin=pin.Prepared(self.parent,pin.ACTIVE)if pin.ACTIVE is not None else None
        from src.native_inventory import ERROR_MM
        padding={s:float(source_widths[s]*(settings.maximum_factor-1)/2)+ERROR_MM+checking_headroom_mm+self.parent.contract.comparison_epsilon_mm for s in self.order}
        if cc.ACTIVE is not None:
            self.owner_checks.append(OwnerDependencies(self.parent,cc.ACTIVE,self.order,padding,'PHYSICAL_ORIGINAL_OWNER'))
        if functional.ACTIVE is not None:
            self.owner_checks.append(OwnerDependencies(self.parent,functional.ACTIVE,self.order,padding,'FUNCTIONAL_SOURCE_CHANNEL'))
        # A functional owner proof supplements the legacy primitive predicate;
        # it cannot replace it when the physical-owner profile is inactive.
        self.fallback=None
        if cc.ACTIVE is None:
            from src.u03_board.dependency import DependencyWidthScene
            self.fallback=DependencyWidthScene(baseline,fixed)
        self.baseline_check=self.parent.check(CandidateSnapshot(tuple(self.rows)),fail_fast=True)
        if not self.baseline_check['passed']:raise ValueError('T04_QUALIFIED_STAGE_ENTRY_REQUIRED')

    def evaluate(self,sid,factor):
        candidate=self.build(sid,factor,True);self.constructed_routes+=1
        self.parent.valid_geometry(candidate)
        if not candidate.covers(self.parent.original[sid]):
            return dict(passed=False,failures=[dict(trace_id=sid,reason='ORIGINAL_TRACE_CORE_REMOVED')])
        rows=list(self.rows);rows[self.positions[sid]]=CandidateTrace(sid,self.parent.original[sid],candidate,self.parent.widths[sid])
        snapshot=CandidateSnapshot(tuple(rows));checks=[]
        for check in self.owner_checks:
            checks.append(check.check(sid,factor,candidate,self.current,self.versions))
            if not checks[-1]['passed']:break
        if self.fallback is not None:checks.append(self.fallback.check(snapshot,fail_fast=True))
        if self.owner_checks and all(q['passed']for q in checks):
            from src.t04_topology import check as topology_check
            checks.append(topology_check(self.owner_checks[-1],sid,factor,candidate,self.current,self.versions))
        if self.pin is not None:checks.append(self.pin.check(snapshot))
        failures=[f for q in checks for f in q.get('failures',[])]
        for q in checks:
            if not q['passed'] and not q.get('failures'):
                failures.extend(dict(reason='PIN_SEPARATION',pin_check=r)for r in q.get('checks',[])if not r['passed'])
        result=dict(passed=all(q['passed']for q in checks),failures=failures,checks=checks)
        self.pending=(sid,factor,candidate,rows)if result['passed']else None
        return result

    def accept(self,sid,factor):
        if self.pending is None or self.pending[:2]!=(sid,factor):raise ValueError('T04_CHECKED_ROUTE_PROPOSAL_REQUIRED')
        _,_,candidate,rows=self.pending;self.current[sid]=candidate;self.versions[sid]=factor
        self.rows=rows;self.pending=None;self.accepted_updates+=1

    def diagnostics(self):
        return dict(route_candidate_requests=self.constructed_routes,accepted_updates=self.accepted_updates,
                    full_scene_checks_during_attempts=0 if self.fallback is None else 'DEPENDENCY_CHECKER_FALLBACK',
                    owner_indices_prepared=len(self.owner_checks),
                    owner_cache_bytes=sum(c.bytes for c in self.owner_checks),
                    source_void_index_bytes=sum(c.source_void_bytes for c in self.owner_checks),
                    owner_cache_limit_bytes=sum(c.limit for c in self.owner_checks),
                    exact_distance_calls=sum(c.exact_distances for c in self.owner_checks),
                    cached_distance_hits=sum(c.hits for c in self.owner_checks))
