from src.indexed_polygon_distance import distance as indexed_distance
"""Incremental whole-scene evaluation of the unchanged T04 surface predicate.

Passing unchanged checks are carried only when neither their own candidate nor
any current/previous finite neighbor changed. Every final native verification
also runs the original full PreparedWidthScene predicate on nominal/envelope.
"""
from collections import OrderedDict
import zlib
from shapely import STRtree,to_wkb,from_wkb,get_precision
from shapely.geometry import box
from shapely.ops import unary_union
from src.prepared_width_scene import PreparedWidthScene
from src.trace_width_clearance import sha
from src.stage_abi.store import canonical, digest
from src.native_inventory import ERROR_MM


class IncrementalWidthScene(PreparedWidthScene):
    def __init__(self, traces, fixed, *, original_union_cache_bytes=512*1024**2):
        if type(original_union_cache_bytes) is not int or original_union_cache_bytes<0:
            raise ValueError('U03_UNION_CACHE_BUDGET_INVALID')
        super().__init__(traces, fixed)
        self.accepted_current = None; self.accepted_results = {}; self.accepted_hash = None
        self.geometry_hashes = {}; self.visible_cache = {}; self.added_cache = {}
        self.incremental_ports = {}
        self.original_union_cache=OrderedDict();self.original_union_cache_limit=original_union_cache_bytes
        self.original_union_cache_weight=0;self.original_union_hits=0;self.original_union_misses=0;self.original_union_evictions=0
        self.original_union_compressed_hits=0
        self.original_union_targets=set(self.trace_ids)
        self.use_width_union_window=False
        self.original_union_boundary_rechecks=0

    def original_union_key(self,sid,candidate):
        # The source operands and STRtree are immutable for this checker.
        # Preserve the original query order exactly: a new trial may change
        # the candidate without changing this expensive original-source union.
        window=candidate.envelope
        if self.original_union_cache_limit and self.use_width_union_window and sid in self.trace_ids:
            # Every supported 1..1.5 source-offset envelope lies within the
            # original AABB expanded by .25*width + the existing envelope
            # margin. All other original copper outside a candidate's AABB
            # is disjoint from it, so retaining that copper in this union
            # preserves the same global source-visibility predicate.
            x0,y0,x1,y1=self.original[sid].bounds;pad=.25*self.widths[sid]+ERROR_MM
            a,b,c,d=candidate.bounds
            if x0-pad<=a and y0-pad<=b and x1+pad>=c and y1+pad>=d:
                window=box(x0-pad,y0-pad,x1+pad,y1+pad)
        return self.original_union_operands(sid,candidate,window)

    def other_original_union(self,sid,candidate):
        key=self.original_union_key(sid,candidate)
        cached=self.original_union_cache.get(key)
        if cached is not None:
            self.original_union_hits+=1;self.original_union_cache.move_to_end(key)
            codec,payload,sha,_=cached
            if codec=='geometry':return payload
            try:blob=zlib.decompress(payload)
            except zlib.error as error:raise ValueError('U03_ORIGINAL_UNION_CACHE_CHANGED') from error
            if digest(blob)!=sha:raise ValueError('U03_ORIGINAL_UNION_CACHE_CHANGED')
            self.original_union_compressed_hits+=1
            return from_wkb(blob)
        self.original_union_misses+=1
        geometry=self.compute_original_union(key)
        # Stable neighbors already retain their complete visible geometry.
        # Do not let their one-time unions evict the moving traces' reusable
        # source unions, especially when a long group first visits the board.
        if not self.original_union_cache_limit or sid not in self.original_union_targets or self.cached_sha(candidate)==self.trace_ids[sid]:
            return geometry
        # Large double-precision unions use lossless WKB compression. A cache
        # hit restores exactly those coordinate bytes; it never rounds copper.
        # Retain non-default precision models directly rather than losing
        # their GEOS precision metadata in a WKB round-trip.
        blob=to_wkb(geometry,include_srid=True)
        if len(blob)>16384 and get_precision(geometry)==0:
            codec='zlib';payload=zlib.compress(blob,1);sha=digest(blob);stored=len(payload)
        else:codec='geometry';payload=geometry;sha=None;stored=2*len(blob)
        # Weighted bound includes tuple/integer keys and allocation overhead.
        # An oversized entry is computed without caching.
        weight=stored+40*len(key)+256
        if weight<=self.original_union_cache_limit:
            while self.original_union_cache and (self.original_union_cache_weight+weight>self.original_union_cache_limit or len(self.original_union_cache)>=4096):
                _,(_,_,_,old_weight)=self.original_union_cache.popitem(last=False)
                self.original_union_cache_weight-=old_weight;self.original_union_evictions+=1
            self.original_union_cache[key]=(codec,payload,sha,weight);self.original_union_cache_weight+=weight
        return geometry

    def original_union_operands(self,sid,candidate,window):
        return tuple(int(i) for i in self.tree.query(window) if self.ids[int(i)]!=sid)

    def compute_original_union(self,key):
        return unary_union([self.original[self.ids[i]] for i in key])

    def cached_sha(self, g):
        key = id(g); cached = self.geometry_hashes.get(key)
        if cached is None or cached[0] is not g:
            cached = (g, sha(g)); self.geometry_hashes[key] = cached
        return cached[1]

    def exact_other_original_union(self,sid,candidate):
        nearby=[self.original[self.ids[int(i)]] for i in self.tree.query(candidate.envelope) if self.ids[int(i)]!=sid]
        return unary_union(nearby)

    # Default hooks retain the original predicate and index implementation.
    def spatial_index(self,current):return STRtree([current[s] for s in self.ids])
    def invalidate_proofs(self,changed):pass
    def route_proof(self,sid,current,tree):return None
    def save_route_proof(self,sid,current,tree,result,failures):pass
    def checked_copper(self,sid,oid,candidate,added,port):return added if port is None else added.difference(port)
    def exact_distance(self,sid,oid,checked,neighbor):return indexed_distance(checked,neighbor)
    def set_visible(self,sid,entry):self.visible_cache[sid]=entry
    def pair_visibility(self,sid,oid,checked,current):return self.visible_geometry(oid,current)
    def visible_geometry(self,sid,current):
        key = self.cached_sha(current[sid]); entry = self.visible_cache.get(sid)
        if entry is None or entry[0] != key:
            retained=self.trace_visibility.get(sid,self.fixed_visibility.get(sid))
            entry=retained if retained is not None and retained[0]==key else (key,current[sid].difference(self.other_original_union(sid,current[sid])))
            self.set_visible(sid,entry)
        return entry[1]

    def prepare_trial(self,traces):
        """Reference preparation; optimized immutable snapshots validate deltas."""
        if len(traces) != len(self.trace_ids) or {r['id'] for r in traces} != set(self.trace_ids):
            raise ValueError('COMPLETE_TRACE_IDENTITIES_CHANGED')
        current = dict(self.original); rows = {r['id']:r for r in traces}
        for sid, r in rows.items():
            cached=self.geometry_hashes.get(id(r['candidate']))
            if cached is None or cached[0] is not r['candidate']:self.valid_geometry(r['candidate'])
            if self.cached_sha(r['original']) != self.trace_ids[sid] or r['verified_original_width_mm'] != self.widths[sid]:
                raise ValueError('ORIGINAL_TRACE_BINDING_CHANGED')
            current[sid] = r['candidate']
        changed = set(rows) if self.accepted_current is None else {s for s in rows if self.cached_sha(current[s]) != self.cached_sha(self.accepted_current[s])}
        return current,rows,changed

    def check(self, traces, *, materialize_scene=False, fail_fast=False):
        if materialize_scene or not fail_fast:
            self.use_width_union_window=False
            self.original_union_targets=set(self.trace_ids)
            result=super().check(traces, materialize_scene=materialize_scene, fail_fast=fail_fast)
            if result['passed']:
                self.accepted_current=dict(self.original,**{r['id']:r['candidate'] for r in traces})
                self.accepted_results={r['trace_id']:dict(trace_id=r['trace_id'],passed=r['passed'],candidate_sha256=r['candidate_trace_wkb_sha256']) for r in result['traces']}
                self.accepted_hash=digest(canonical(result))
                # These are identical source-visibility/addition/port
                # predicates already executed by the full verifier. Retain
                # them when proceeding to final-neighbor upper proofs.
                self.visible_cache.update(self.fixed_visibility);self.visible_cache.update(self.trace_visibility)
                self.added_cache.update(self.addition_visibility)
                self.incremental_ports.update({key:value[0] for key,value in self.ports.items()})
            return result
        current,rows,changed=self.prepare_trial(traces)
        c = self.contract; tree = self.spatial_index(current)
        self.use_width_union_window=True
        self.original_union_targets=changed
        self.invalidate_proofs(changed)
        affected = set(changed)
        if self.accepted_current is not None:
            oldtree = self.spatial_index(self.accepted_current)
            radius = c.construction_gap_mm + c.comparison_epsilon_mm
            for sid in changed:
                # Symmetric finite-neighbor dependency, covering both insertion
                # and removal from a prior candidate's query neighborhood.
                for t, geom in ((tree,current[sid]), (oldtree,self.accepted_current[sid])):
                    for i in t.query(geom.envelope.buffer(radius)):
                        neighbor = self.ids[int(i)]
                        if neighbor in rows: affected.add(neighbor)
        results = dict(self.accepted_results); failures = []; updated = []
        for sid in sorted(affected):
            reused=self.route_proof(sid,current,tree)
            if reused is not None:
                result,local_failures=reused
                failures.extend(local_failures);updated.append(result);results[sid]=result
                if failures:break
                continue
            failure_start=len(failures)
            core = self.original[sid]; candidate = current[sid]; reasons = []; pairs = []
            exact = self.cached_sha(candidate) == self.trace_ids[sid]
            if not candidate.covers(core): reasons.append('ORIGINAL_TRACE_CORE_REMOVED')
            if not exact:
                key = self.cached_sha(candidate); entry = self.added_cache.get(sid)
                if entry is None or entry[0] != key:
                    retained=self.addition_visibility.get(sid)
                    entry=retained if retained is not None and retained[0]==key else (key,candidate.difference(self.predecessor))
                    self.added_cache[sid] = entry
                added = entry[1]
                radius = c.construction_gap_mm + c.comparison_epsilon_mm
                x0,y0,x1,y1 = candidate.bounds
                for i in sorted(int(v) for v in tree.query(box(x0-radius,y0-radius,x1+radius,y1+radius))):
                    oid = self.ids[i]
                    if oid == sid: continue
                    old = self.original[oid]; key = sid,oid
                    if key not in self.incremental_ports:
                        overlap = core.intersection(old)
                        self.incremental_ports[key] = None if overlap.is_empty else overlap.buffer(max(self.widths[sid],self.widths[oid])+c.original_port_buffer_gap_mm,quad_segs=c.port_quad_segs)
                    port = self.incremental_ports[key]; checked = self.checked_copper(sid,oid,candidate,added,port)
                    neighbor = self.pair_visibility(sid,oid,checked,current); gap = None if checked.is_empty or neighbor.is_empty else self.exact_distance(sid,oid,checked,neighbor)
                    if gap is not None and abs(gap+c.comparison_epsilon_mm-c.construction_gap_mm)<=c.comparison_epsilon_mm:
                        # A larger union window is mathematically equivalent,
                        # but GEOS may change a distant gap by a few ULPs. At
                        # the existing comparison boundary, execute the exact
                        # original query before deciding; never widen epsilon.
                        neighbor=current[oid].difference(self.exact_other_original_union(oid,current[oid]))
                        self.set_visible(oid,(self.cached_sha(current[oid]),neighbor))
                        gap=None if neighbor.is_empty else indexed_distance(checked,neighbor)
                        self.original_union_boundary_rechecks+=1
                    bad = gap is not None and gap+c.comparison_epsilon_mm < c.construction_gap_mm
                    pairs.append(dict(neighbor_id=oid, port_sha256=None if port is None else self.cached_sha(port), gap_mm=gap, passed=not bad))
                    if bad:
                        failures.append(dict(trace_id=sid,neighbor_id=oid,reason='NEW_EXPOSED_COPPER_BELOW_CONSTRUCTION_GUARD')); break
            failures.extend(dict(trace_id=sid,reason=r) for r in reasons)
            result = dict(trace_id=sid, candidate_sha256=self.cached_sha(candidate), passed=not reasons and not any(not p['passed'] for p in pairs), pairs=pairs)
            self.save_route_proof(sid,current,tree,result,failures[failure_start:])
            updated.append(result); results[sid] = result
            if failures: break
        pin_proof=None
        from src import pin_separation as pin
        if pin.ACTIVE is not None:
            if not hasattr(self,'_pin_check'):self._pin_check=pin.Prepared(self,pin.ACTIVE)
            pin_proof=self._pin_check.check(traces,materialize_scene=False)
            failures.extend(dict(reason='PIN_SEPARATION',pin_check=r)for r in pin_proof['checks']if not r['passed'])
        previous = self.accepted_hash
        if not failures:
            if set(results) != set(rows): raise ValueError('U03_CARRIED_CHECK_COVERAGE_MISSING')
            self.accepted_current = current; self.accepted_results = results
            # The ledger chains each complete passing state to its prior state
            # plus explicitly re-evaluated source-bound predicates.
            self.accepted_hash = digest(canonical(dict(previous=previous,updates=updated)))
        # Keep at most the current and accepted candidate geometries alive.
        if len(self.geometry_hashes)>3*len(self.original)+1000:
            self.geometry_hashes = {id(g):(g,self.cached_sha(g)) for g in [*self.original.values(),*current.values(),*([] if self.accepted_current is None else self.accepted_current.values())]}
        return dict(schema='u03-incremental-width-check/1',passed=not failures,failures=failures,**({}if pin_proof is None else{'pin_separation':pin_proof}),
                    trace_count=len(rows),scene_object_count=len(self.ids),affected_trace_count=len(affected),
                    checked_trace_count=len(updated),carried_trace_count=len(rows)-len(affected),
                    previous_passing_state_sha256=previous,passing_state_sha256=self.accepted_hash if not failures else None,
                    updates=updated,policy='Unchanged PreparedWidthScene finite-copper predicate; full final verification mandatory')
