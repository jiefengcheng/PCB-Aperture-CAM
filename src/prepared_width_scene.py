from src.indexed_polygon_distance import distance as indexed_distance, signature as sha
"""Reusable fixed-source context for growth-only width checks.

Policy and positive-proposal pair predicates match trace_width_clearance v1.
Exact unchanged source geometries carry zero growth by identity, avoiding a
spurious tiny difference created by recomputing a large Boolean source union.
The original audited verifier is preserved for independent final comparisons.
"""
import math
from shapely import STRtree
from shapely.geometry import box
from shapely.ops import unary_union
from .trace_width_clearance import TraceWidthContract
from src.stage_abi.preparation import prepared_tree as STRtree


class PreparedWidthScene:
    def __init__(self,traces,fixed_copper,contract=TraceWidthContract()):
        if contract!=TraceWidthContract():raise ValueError('WIDTH_CLEARANCE_POLICY_CHANGED')
        if not traces:raise ValueError('NO_COMPLETE_TRACES')
        self.contract=contract;self.original={};self.widths={};self.trace_ids={};self.fixed_count=len(fixed_copper)
        for r in traces:
            sid=r['id']
            if sid in self.original:raise ValueError('DUPLICATE_SCENE_SOURCE')
            self.original[sid]=r['original'];self.widths[sid]=r['verified_original_width_mm'];self.trace_ids[sid]=sha(r['original'])
            if not math.isfinite(self.widths[sid]) or self.widths[sid]<=0:raise ValueError('ORIGINAL_WIDTH_NOT_VERIFIED')
        for r in fixed_copper:
            sid=r['id']
            if sid in self.original:raise ValueError('DUPLICATE_SCENE_SOURCE')
            self.original[sid]=r['geometry'];self.widths[sid]=r.get('trace_width_mm',0.)
            if not math.isfinite(self.widths[sid]) or self.widths[sid]<0:raise ValueError('INVALID_FIXED_SOURCE_WIDTH')
        for g in self.original.values():self.valid_geometry(g)
        self.ids=sorted(self.original);self.tree=STRtree([self.original[sid] for sid in self.ids])
        self.predecessor=unary_union([self.original[sid] for sid in self.ids]);self.predecessor_sha=sha(self.predecessor)
        self.fixed_visibility={};self.trace_visibility={};self.ports={};self.addition_visibility={}
        # Opt in here, rather than on the class: filled lands have a separate
        # initializer and retain their existing owner-check calculation.
        self.owner_added_material=self._source_width_added_material

    @staticmethod
    def _source_width_added_material(predecessor,candidates):
        from src.component_clearance import joined
        # (A union B1 union ...) minus A = union(Bi minus A). Including all
        # unchanged A in a new large overlay can leave numerical boundary
        # spurs on old copper. Every positive-area candidate piece is retained;
        # there is no area epsilon, buffering, snapping or clearance waiver.
        return joined(candidate.difference(predecessor) for candidate in candidates)

    @staticmethod
    def valid_geometry(g):
        if g.is_empty or not g.is_valid or g.geom_type not in ('Polygon','MultiPolygon'):raise ValueError('INVALID_FINITE_COPPER_GEOMETRY')

    def required_new_copper_gap(self):
        return self.contract.construction_gap_mm

    def source_core_preserved(self,sid,core,candidate):
        return candidate.covers(core)

    def check(self,traces,*,materialize_scene=False,fail_fast=False):
        result=self._physical_check(traces,materialize_scene=materialize_scene,fail_fast=fail_fast)
        from src import source_channel_scope as functional
        if functional.ACTIVE is not None:
            from src.component_clearance import OwnerCheck
            if not hasattr(self,'_functional_check'):self._functional_check=OwnerCheck(self,context=functional.ACTIVE,active_test=lambda c:functional.ACTIVE is c)
            proof=self._functional_check.check(traces,materialize_scene=materialize_scene,fail_fast=fail_fast)
            result=dict(result,functional_channels=proof,passed=result['passed']and proof['passed'],failures=[*result['failures'],*[dict(r,clearance_scope='FUNCTIONAL_SOURCE_CHANNEL')for r in proof['failures']]])
        from src import pin_separation as pin
        if pin.ACTIVE is not None:
            if not hasattr(self,'_pin_check'):self._pin_check=pin.Prepared(self,pin.ACTIVE)
            proof=self._pin_check.check(traces,materialize_scene=materialize_scene)
            result=dict(result,pin_separation=proof,passed=result['passed']and proof['passed'],failures=[*result['failures'],*[dict(reason='PIN_SEPARATION',pin_check=r)for r in proof['checks']if not r['passed']]])
        return result

    def _physical_check(self,traces,*,materialize_scene=False,fail_fast=False):
        from src import component_clearance
        if component_clearance.ACTIVE is not None:
            if not hasattr(self,'_component_check'):self._component_check=component_clearance.OwnerCheck(self)
            return self._component_check.check(traces,materialize_scene=materialize_scene,fail_fast=fail_fast)
        if len(traces)!=len(self.trace_ids) or {r['id'] for r in traces}!=set(self.trace_ids):raise ValueError('COMPLETE_TRACE_IDENTITIES_CHANGED')
        current=dict(self.original)
        for r in traces:
            sid=r['id'];self.valid_geometry(r['candidate'])
            if sha(r['original'])!=self.trace_ids[sid] or r['verified_original_width_mm']!=self.widths[sid]:raise ValueError('ORIGINAL_TRACE_BINDING_CHANGED')
            current[sid]=r['candidate']
        c=self.contract;tree=STRtree([current[sid] for sid in self.ids]);failures=[];results=[]
        def visible(sid):
            key=sha(current[sid]);cache=self.trace_visibility if sid in self.trace_ids else self.fixed_visibility
            if sid not in cache or cache[sid][0]!=key:
                nearby=[self.original[self.ids[int(i)]] for i in self.tree.query(current[sid].envelope) if self.ids[int(i)]!=sid]
                cache[sid]=(key,current[sid].difference(unary_union(nearby)))
            return cache[sid][1]
        for r in sorted(traces,key=lambda r:r['id']):
            sid=r['id'];core=self.original[sid];candidate=current[sid];reasons=[]
            exact_keep=sha(candidate)==self.trace_ids[sid]
            if not self.source_core_preserved(sid,core,candidate):reasons.append('ORIGINAL_TRACE_CORE_REMOVED')
            added=candidate.difference(core)
            # A byte-identical source object introduces no copper or changed
            # relationships, regardless of roundoff in the surrounding union.
            if exact_keep:visible_added=added
            else:
                key=sha(candidate)
                if sid not in self.addition_visibility or self.addition_visibility[sid][0]!=key:
                    self.addition_visibility[sid]=(key,candidate.difference(self.predecessor))
                visible_added=self.addition_visibility[sid][1]
            pairs=[]
            if not exact_keep:
                x0,y0,x1,y1=candidate.bounds;radius=c.construction_gap_mm+c.comparison_epsilon_mm
                query=box(x0-radius,y0-radius,x1+radius,y1+radius)
                for i in sorted(int(v) for v in tree.query(query)):
                    oid=self.ids[i]
                    if oid==sid:continue
                    old=self.original[oid];neighbor=current[oid];key=(sid,oid)
                    if key not in self.ports:
                        overlap=core.intersection(old)
                        port=None if overlap.is_empty else overlap.buffer(max(self.widths[sid],self.widths[oid])+c.original_port_buffer_gap_mm,quad_segs=c.port_quad_segs)
                        self.ports[key]=(port,not overlap.is_empty,indexed_distance(core,old))
                    port,contact,original_gap=self.ports[key]
                    checked=visible_added if port is None else visible_added.difference(port)
                    exposed_neighbor=visible(oid)
                    gap=None if checked.is_empty or exposed_neighbor.is_empty else indexed_distance(checked,exposed_neighbor)
                    pair_failures=[]
                    if gap is not None and gap+c.comparison_epsilon_mm<self.required_new_copper_gap():pair_failures.append('NEW_EXPOSED_COPPER_BELOW_CONSTRUCTION_GUARD')
                    pair=dict(neighbor_id=oid,raw_original_primitive_gap_mm=original_gap,raw_current_primitive_gap_mm=indexed_distance(candidate,neighbor),original_contact=contact,original_port_wkb_sha256=None if port is None else sha(port),original_port_area_mm2=None if port is None else port.area,original_port_buffer_mm=None if port is None else max(self.widths[sid],self.widths[oid])+c.original_port_buffer_gap_mm,current_neighbor_visible_area_mm2=exposed_neighbor.area,checked_new_exposed_copper_area_mm2=checked.area,new_exposed_to_visible_neighbor_gap_mm=gap,failures=pair_failures)
                    pairs.append(pair);failures.extend(dict(trace_id=sid,neighbor_id=oid,reason=reason) for reason in pair_failures)
                    if fail_fast and pair_failures:break
            failures.extend(dict(trace_id=sid,reason=reason) for reason in reasons)
            results.append(dict(trace_id=sid,passed=not reasons and not any(p['failures'] for p in pairs),original_trace_wkb_sha256=self.trace_ids[sid],candidate_trace_wkb_sha256=sha(candidate),nominal_primitive_added_area_mm2=added.area,new_exposed_copper_area_mm2=visible_added.area,core_removed_mm2=core.difference(candidate).area,pairs=pairs,failures=reasons,unchanged_source_identity=exact_keep))
            if fail_fast and failures:break
        scene=unary_union([current[sid] for sid in self.ids]) if materialize_scene else None
        from dataclasses import asdict
        return dict(schema='trace-width-prepared-growth-identity/2',contract=asdict(c),passed=not failures,failures=failures,traces=results,scene_object_count=len(self.ids),fixed_object_count=self.fixed_count,trace_count=len(traces),checked_trace_count=len(results),evaluation_complete=not(fail_fast and failures),rejection_mode='FIRST_SOURCE_BOUND_FAILURE' if fail_fast and failures else 'COMPLETE_REQUESTED_CHECK',predecessor_union_wkb_sha256=self.predecessor_sha,candidate_union_wkb_sha256=None if scene is None else sha(scene),new_exposed_copper_area_mm2=(0. if len(results)==len(traces) and all(r['unchanged_source_identity'] for r in results) else None) if scene is None else scene.difference(self.predecessor).area,scene_union_materialized=materialize_scene,query_scope='FULL_TRACE_AABB_PLUS_CONSTRUCTION_GUARD; no crop clipping',visibility='Other original predecessor copper only; new candidates never hide boundaries',fixed_geometry_change='INEXPRESSIBLE_IN_THIS_API',unchanged_rule='Exact original WKB identity means zero growth; unchanged original relationships are outside growth remediation',limitations='Complete source/route/group binding remains caller responsibility; a rejected proposal may stop at its first recorded failure; every passing check is complete; deferred union hash is diagnostic only')
