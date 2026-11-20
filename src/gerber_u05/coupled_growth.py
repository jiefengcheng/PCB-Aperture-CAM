"""Bounded owner-aware lanes and deterministic proportional max-min allocation.

These are proposals only. All existing native proposal and final checks remain
mandatory. Same-owner screening never waives source-void or attachment checks.
"""
from collections import defaultdict
from pathlib import Path
import gzip,hashlib,json
from shapely import STRtree
from shapely.ops import unary_union
from src.trace_width_clearance import TraceWidthContract
from .limiting_growth import local_allowance
from .limiting_math import collect_proposals,GUARD,MARGIN


def proportional_fill(caps,widths,edges):
    """Weighted max-min filling with hard caps; reclaim saturated neighbours' shares."""
    if set(caps)!=set(widths) or any(c<0 for c in caps.values()) or any(w<=0 for w in widths.values()):
        raise ValueError('POSITIVE_WIDTHS_AND_NONNEGATIVE_CAPS_REQUIRED')
    budgets={}
    for a,b,budget in edges:
        if a==b:raise ValueError('DISTINCT_ALLOCATION_VARIABLES_REQUIRED')
        if a not in caps or b not in caps or budget<0:raise ValueError('ALLOCATION_EDGE_INVALID')
        key=tuple(sorted((a,b)));budgets[key]=min(budgets.get(key,float('inf')),budget)
    growth=dict.fromkeys(caps,0.);active=set(caps);rounds=[]
    while active:
        increments=[max(0.,caps[r]-growth[r])/widths[r] for r in sorted(active)]
        for (a,b),budget in sorted(budgets.items()):
            speed=sum(widths[r] for r in (a,b) if r in active)
            if speed:increments.append(max(0.,budget-growth[a]-growth[b])/speed)
        step=min(increments)
        for r in sorted(active):growth[r]=min(caps[r],growth[r]+step*widths[r])
        frozen={r for r in active if caps[r]-growth[r]<=1e-14}
        for (a,b),budget in sorted(budgets.items()):
            if budget-growth[a]-growth[b]<=1e-14:frozen.update({a,b}&active)
        if not frozen:raise ValueError('ALLOCATION_DID_NOT_MAKE_PROGRESS')
        rounds.append(dict(increment=step,frozen=sorted(frozen)));active-=frozen
    assert all(growth[a]+growth[b]<=v+1e-12 for (a,b),v in budgets.items())
    return growth,rounds


def allocate(rows,current,original,paths,roles,context,straight,curves,caps):
    owner={s:r for r,ss in paths.items() for s in ss};owners=context.ids
    excluded=[]
    parallel,proposals,witnesses,_=collect_proposals(rows,paths,straight,curves,original,roles,owner_ids=owners,excluded=excluded)
    widths={r:rows[ss[0]]['metadata']['minimum_caliper_mm'] for r,ss in paths.items()}
    hardcaps=dict(caps);edges=[];constraints=[];skipped=[]
    def bound(a,b,budget,witness):
        budget=max(0.,budget)
        if a==b:return
        constraints.append(dict(a=a,b=b,budget_mm=budget,**witness))
        if b is None:hardcaps[a]=min(hardcaps[a],budget)
        else:edges.append((a,b,budget))
    for i,w in enumerate(witnesses):
        aa={owner[s] for s in w['a'] if s in owner};bb={owner[s] for s in w['b'] if s in owner}
        for a in sorted(aa):
            for b in sorted(bb):
                if a!=b:bound(a,b,w['gap_mm']-GUARD-2*MARGIN,dict(kind='parallel',witness=i))
    cores={r:unary_union([original[s] for s in ss]) for r,ss in paths.items()};used=set(owner)
    fixed=sorted(set(rows)-set(roles)-used);ids=fixed+sorted(paths);geoms=[current[s] for s in fixed]+[cores[r] for r in sorted(paths)];tree=STRtree(geoms);contract=TraceWidthContract()
    r_owners={r:{o for s in ss for o in owners[s]} for r,ss in paths.items()}
    for r in sorted(paths):
        port_width=max(rows[s]['metadata']['source_port_width_mm'] for s in paths[r])
        for i in sorted(map(int,tree.query(cores[r],predicate='dwithin',distance=caps[r]+max(caps.values())+GUARD+2*MARGIN))):
            oid=ids[i]
            if oid==r:continue
            otherowners=r_owners[oid] if oid in paths else set(owners[oid])
            if len(r_owners[r])==1 and r_owners[r]==otherowners:
                skipped.append(dict(route=r,neighbor=oid,reason='SAME_FROZEN_OWNER; NATIVE_SOURCE_VOID_CHECK_RETAINED'));continue
            other=geoms[i];overlap=cores[r].intersection(other)
            otherport=max(rows[s]['metadata']['source_port_width_mm'] for s in paths[oid]) if oid in paths else rows[oid]['metadata'].get('original_width_mm',0.)
            port=None if overlap.is_empty else overlap.buffer(max(port_width,otherport)+contract.original_port_buffer_gap_mm,quad_segs=contract.port_quad_segs)
            for sid in paths[r]:
                budget=local_allowance(original[sid],other,max(caps[r],caps.get(oid,0.)),port)
                if budget is not None:bound(r,oid if oid in paths else None,budget,dict(kind='neighbor',segment=sid,neighbor=oid,original_contact=port is not None))
    targets,rounds=proportional_fill(hardcaps,widths,edges)
    receipt=dict(schema='t04-coupled-proportional-allocation/1',parallel_seeds_before_coupling=parallel,excluded_overlap_relations=excluded,source_witnesses=witnesses,constraints=constraints,source_caps_radial_mm=caps,hard_caps_radial_mm=hardcaps,proportional_rounds=rounds,same_owner_planner_obstacles=skipped,targets_radial_mm=targets,full_board_enabled=False)
    return targets,receipt
