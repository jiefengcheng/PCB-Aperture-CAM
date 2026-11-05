"""Versioned finite-copper growth verifier for complete fixed-route trace groups.

Visibility is computed against predecessor copper only. New candidates must never
hide one another's bridges. The input scene must include all source objects; its
provenance/completeness is the responsibility of the source-bound caller.
"""
from src.clearance_policy import HARD_GAP_MM, CONSTRUCTION_GAP_MM, CONTACT_BUFFER_MM, LEGACY_CONSTRUCTION_MM, BARRIER_GAP_MM
from dataclasses import dataclass,asdict
import hashlib
import math
from shapely import STRtree,to_wkb
from shapely.geometry import box
from shapely.ops import unary_union


@dataclass(frozen=True)
class TraceWidthContract:
    version: str = 'trace-width-visible-surface/1'
    hard_gap_mm: float = HARD_GAP_MM
    construction_gap_mm: float = CONSTRUCTION_GAP_MM
    original_port_buffer_gap_mm: float = CONTACT_BUFFER_MM
    comparison_epsilon_mm: float = 1e-12
    port_quad_segs: int = 128


def sha(g):
    return hashlib.sha256(to_wkb(g)).hexdigest()


def verify_width_scene(traces,fixed_copper,contract=TraceWidthContract()):
    """Validate all simultaneous candidates; no shape/width/route mutation here.

    Trace rows: id, original, candidate, verified_original_width_mm.
    Fixed rows: id, geometry, optional trace_width_mm (zero for a land).
    Fixed geometry is supplied once, making land edits inexpressible in this API.
    """
    if contract!=TraceWidthContract():raise ValueError('WIDTH_CLEARANCE_POLICY_CHANGED')
    if not traces:raise ValueError('NO_COMPLETE_TRACES')
    original={};current={};widths={}
    for row in traces:
        sid=row['id']
        if sid in original:raise ValueError('DUPLICATE_SCENE_SOURCE')
        original[sid]=row['original'];current[sid]=row['candidate']
        widths[sid]=row['verified_original_width_mm']
        if not math.isfinite(widths[sid]) or widths[sid]<=0:raise ValueError('ORIGINAL_WIDTH_NOT_VERIFIED')
    for row in fixed_copper:
        sid=row['id']
        if sid in original:raise ValueError('DUPLICATE_SCENE_SOURCE')
        original[sid]=current[sid]=row['geometry'];widths[sid]=row.get('trace_width_mm',0.)
        if not math.isfinite(widths[sid]) or widths[sid]<0:raise ValueError('INVALID_FIXED_SOURCE_WIDTH')
    for g in list(original.values())+list(current.values()):
        if g.is_empty or not g.is_valid or g.geom_type not in ('Polygon','MultiPolygon'):
            raise ValueError('INVALID_FINITE_COPPER_GEOMETRY')
    ids=sorted(original);index={sid:i for i,sid in enumerate(ids)}
    original_tree=STRtree([original[sid] for sid in ids])
    current_tree=STRtree([current[sid] for sid in ids])
    predecessor=unary_union([original[sid] for sid in ids])
    neighbor_visible={}
    def visible_neighbor(sid):
        if sid not in neighbor_visible:
            # Only ORIGINAL other copper may cover a primitive boundary. Never
            # subtract other new candidates, which could conceal new contacts.
            nearby=[original[ids[int(i)]] for i in original_tree.query(current[sid].envelope)
                    if ids[int(i)]!=sid]
            neighbor_visible[sid]=current[sid].difference(unary_union(nearby))
        return neighbor_visible[sid]
    results=[];failures=[]
    for row in sorted(traces,key=lambda r:r['id']):
        sid=row['id'];core=original[sid];candidate=current[sid]
        reasons=[]
        if not candidate.covers(core):reasons.append('ORIGINAL_TRACE_CORE_REMOVED')
        added=candidate.difference(core)
        visible_added=candidate.difference(predecessor)
        pairs=[]
        x0,y0,x1,y1=candidate.bounds
        radius=contract.construction_gap_mm+contract.comparison_epsilon_mm
        query=box(x0-radius,y0-radius,x1+radius,y1+radius)
        for i in sorted(int(i) for i in current_tree.query(query)):
            oid=ids[i]
            if oid==sid:continue
            old=original[oid];neighbor=current[oid]
            overlap=core.intersection(old)
            port=(overlap.buffer(max(widths[sid],widths[oid])+contract.original_port_buffer_gap_mm,
                                 quad_segs=contract.port_quad_segs) if not overlap.is_empty else None)
            checked=visible_added if port is None else visible_added.difference(port)
            exposed_neighbor=visible_neighbor(oid)
            gap=None if checked.is_empty or exposed_neighbor.is_empty else checked.distance(exposed_neighbor)
            pair_failures=[]
            if gap is not None and gap+contract.comparison_epsilon_mm<contract.construction_gap_mm:
                pair_failures.append('NEW_EXPOSED_COPPER_BELOW_CONSTRUCTION_GUARD')
            pair=dict(neighbor_id=oid,raw_original_primitive_gap_mm=core.distance(old),
                raw_current_primitive_gap_mm=candidate.distance(neighbor),
                original_contact=not overlap.is_empty,
                original_port_wkb_sha256=None if port is None else sha(port),
                original_port_area_mm2=None if port is None else port.area,
                original_port_buffer_mm=None if port is None else max(widths[sid],widths[oid])+contract.original_port_buffer_gap_mm,
                current_neighbor_visible_area_mm2=exposed_neighbor.area,
                checked_new_exposed_copper_area_mm2=checked.area,
                new_exposed_to_visible_neighbor_gap_mm=gap,failures=pair_failures)
            pairs.append(pair)
            failures.extend(dict(trace_id=sid,neighbor_id=oid,reason=r) for r in pair_failures)
        failures.extend(dict(trace_id=sid,reason=r) for r in reasons)
        results.append(dict(trace_id=sid,passed=not reasons and not any(p['failures'] for p in pairs),
            original_trace_wkb_sha256=sha(core),candidate_trace_wkb_sha256=sha(candidate),
            nominal_primitive_added_area_mm2=added.area,new_exposed_copper_area_mm2=visible_added.area,
            core_removed_mm2=core.difference(candidate).area,pairs=pairs,failures=reasons))
    scene=unary_union([current[sid] for sid in ids])
    return dict(schema=contract.version,contract=asdict(contract),passed=not failures,failures=failures,traces=results,
        scene_object_count=len(ids),fixed_object_count=len(fixed_copper),trace_count=len(traces),
        predecessor_union_wkb_sha256=sha(predecessor),candidate_union_wkb_sha256=sha(scene),
        new_exposed_copper_area_mm2=scene.difference(predecessor).area,
        query_scope='FULL_TRACE_AABB_PLUS_CONSTRUCTION_GUARD; no crop clipping',
        visibility='Other original predecessor copper only; new candidates never hide boundaries',
        fixed_geometry_change='INEXPRESSIBLE_IN_THIS_API',
        limitations='Finite input-scene model only; width/route construction and source-scene completeness require separate binding')
