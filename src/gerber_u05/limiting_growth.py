"""Opt-in bounded limiting-segment construction for the real T04 caller.

Immutable source identities remain unchanged. A subtraction ledger authorizes
only indexed bulk edits, with source cores, terminals, frames and pin domains
protected. Working owner baselines are scoped to this call and restored even
when admission, proposal checks or final checks fail.
"""
from collections import defaultdict
from contextlib import contextmanager,redirect_stdout
import copy,gzip,hashlib,io,json,runpy,shutil
from pathlib import Path
from time import perf_counter
from shapely import STRtree,to_wkb
from shapely.geometry import Point,Polygon
from shapely.ops import unary_union
from src import component_clearance as cc,source_channel_scope as sc,pin_separation as pin
from src.original_copper_owners import OriginalOwners
from src.filled_copper_source_role import bulk_boundary_route_witness
from src.trace_width_clearance import TraceWidthContract
from . import pipeline as p
from .limiting_math import collect_proposals,GUARD,MARGIN

SCHEMA='t04-limiting-segment-route-default/1'


def split_budget(budget,width,other_width=None):
    budget=max(0.,budget)
    if other_width is None:return budget,0.
    return budget*width/(width+other_width),budget*other_width/(width+other_width)


def local_allowance(segment,other,maximum,port):
    relevant=segment if port is None else segment.difference(port.buffer(-maximum-MARGIN,quad_segs=128))
    return None if relevant.is_empty else max(0.,relevant.distance(other)-GUARD-2*MARGIN)




class Construction:
    def __init__(self,paths,original,rows,targets,settings,receipt,admission):
        self.paths=paths;self.original=original;self.rows=rows;self.targets=targets
        self.admission=admission
        self.owner={s:r for r,members in paths.items() for s in members};self.receipt=receipt
        self.maximum={}
        self.cache={}
        for r,members in paths.items():
            w=rows[members[0]]['metadata']['minimum_caliper_mm']
            self.maximum[r]=max(settings.rung(w,k)['factor'] for k in range(11) if settings.rung(w,k)['within_growth_limits'])
    def effective(self,s,f):
        r=self.owner[s]
        if r not in self.targets:return f
        w=self.rows[s]['metadata']['minimum_caliper_mm'];top=self.maximum[r]
        return 1. if top==1 else 1.+2*self.targets[r]*(f-1)/(top-1)/w
    def part(self,s,f,envelope):
        r=self.owner[s];w=self.rows[s]['metadata']['minimum_caliper_mm']
        if r not in self.targets:return p.offset_part(self.original[s],w,f,envelope,extra_envelope_mm=.000004 if envelope else 0.)
        effective=self.effective(s,f)
        if effective==1:return self.original[s]
        # The bounded route cache owns reuse. Do not retain a second,
        # unbounded cache of intermediate source-part offsets.
        delta=w*(effective-1)/2+(MARGIN if envelope else 0.)
        g=self.original[s].buffer(delta,quad_segs=128)
        if not g.covers(self.original[s]):raise ValueError('T04_LIMITING_CORE_REMOVED')
        return g
    def solve(self,widths,settings,evaluate,accept,**kwargs):
        from .profile_schedule import solve
        if kwargs.get('prefix') is not None or kwargs.get('checkpoint') is not None:raise ValueError('T04_LIMITING_FRESH_ONLY')
        direct={};attempts=[]
        for r in sorted(self.targets):
            factor=self.maximum[r];q=evaluate(r,factor)
            attempts.append(dict(route_id=r,factor=factor,passed=q['passed'],failures=q['failures']))
            if q['passed']:accept(r,factor);direct[r]=factor
        remaining={r:w for r,w in widths.items() if r not in direct}
        if remaining:
            solution=solve(remaining,settings,evaluate,accept,**kwargs)
        else:
            solution=dict(selected_scales={},passes=[dict(number=i+1,advanced_routes=[]) for i in range(len(kwargs['pass_increments']))],evaluations=[],decisions=[],evaluation_count=0,geometry_evaluation_count=0,process_completed=True,passed=True,pass_increments=kwargs['pass_increments'])
        solution['selected_scales'].update(direct)
        solution['schema']=SCHEMA;solution['geometry_family']='uniform-route-limiting-segment-default'
        solution['direct_construction']=dict(attempts=attempts,closed_routes=sorted(direct),factor_semantics='progress to recorded route default',targets_radial_mm=self.targets)
        solution['evaluation_count']+=len(attempts);solution['geometry_evaluation_count']+=len(attempts)
        self.receipt['direct_attempts']=len(attempts);self.receipt['direct_accepted']=len(direct)
        self.receipt['direct_rejected']=[r for r in attempts if not r['passed']]
        return solution


def owner_material(scope,material):
    buckets={o:[] for o in scope.cores}
    frame=getattr(scope,'frame_ids',frozenset())
    for sid,g in material.items():
        if sid in frame:continue
        owners=scope.ids[sid]
        if len(owners)!=1:raise ValueError('T04_LIMITING_MULTI_OWNER_EDIT_UNSUPPORTED')
        buckets[owners[0]].append(g)
    return {o:unary_union(values) for o,values in buckets.items()}


def preserve_connections(scope,current,changed):
    """Retain exact source operands if a cut would newly disconnect an owner.

    This never discards an area fragment or waives a clearance predicate.
    Restored bulk is actual copper in the entry scene; every resulting growth
    proposal must still pass the native checks, with ordinary ladder fallback.
    """
    if scope is None:return changed,[],{}
    before=owner_material(scope,current)
    counts={o:len(OriginalOwners(g).owners) for o,g in before.items()}
    restored=[]
    for attempt in range(4):
        after=owner_material(scope,changed)
        bad={o:OriginalOwners(g).owners for o,g in after.items()
             if not g.equals_exact(before[o],0) and len(OriginalOwners(g).owners)>counts[o]}
        if not bad:return changed,restored,counts
        recover=set()
        for own,parts in bad.items():
            # Protect every disconnected descendant beyond the original
            # component count, using a spatial search only to select WHOLE
            # immutable operands. All pieces, including ulp faces, remain.
            for piece in sorted(parts,key=lambda g:g.area)[:-counts[own]]:
                window=piece.buffer(MARGIN).envelope
                for sid,g in current.items():
                    if own in scope.ids.get(sid,()) and not changed[sid].equals_exact(g,0) and g.intersects(window):recover.add(sid)
        if not recover:raise ValueError('T04_LIMITING_SOURCE_CONNECTION_RECOVERY_UNAVAILABLE')
        for sid in sorted(recover):changed[sid]=current[sid]
        restored.extend(sorted(recover))
    raise ValueError('T04_LIMITING_SOURCE_CONNECTION_RECOVERY_BUDGET_EXCEEDED')


def working_scope(scope,removal,ledger,material=None,baseline_components=None):
    if scope is None:return None
    if scope.reserved or getattr(scope,'checking_envelopes',{}) or scope.approved_partial_pockets:
        raise ValueError('T04_LIMITING_RESERVED_CONTEXT_UNSUPPORTED')
    result=copy.copy(scope)
    result.ids=dict(scope.ids)
    if material is None:
        result.cores={o:g.difference(removal) for o,g in scope.cores.items()}
    else:
        # Actual accepted occurrences are authoritative. Subtracting from a
        # separately rendered raw-source union can create isolated ulp faces
        # and omit accepted T01 joint support. Preserve every edited operand;
        # no positive-area fragment is discarded or rounded away.
        buckets={o:[] for o in scope.cores}
        frame=getattr(scope,'frame_ids',frozenset())
        for sid,g in material.items():
            if sid in frame:continue
            owners=scope.ids[sid]
            if len(owners)!=1:raise ValueError('T04_LIMITING_MULTI_OWNER_EDIT_UNSUPPORTED')
            buckets[owners[0]].append(g)
        result.cores={o:unary_union(values) for o,values in buckets.items()}

    for o,g in result.cores.items():
        old=scope.cores[o]
        if g.is_empty or not g.is_valid:raise ValueError('T04_LIMITING_OWNER_SPLIT_OR_LOSS')
        if not g.equals_exact(old,0) and len(OriginalOwners(g).owners)>(1 if baseline_components is None else baseline_components[o]):raise ValueError('T04_LIMITING_OWNER_SPLIT_OR_LOSS')
        if material is None and old.difference(g).difference(removal).area>1e-12:raise ValueError('T04_LIMITING_SUBTRACTION_SCOPE_CHANGED')
    if hasattr(scope,'channels'):
        result.channels=copy.copy(scope.channels);result.channels.original=result.cores
        result.channels.analytic_source=scope.channels.analytic_source.difference(removal)
    result.binding=p.digest(p.canonical([scope.binding,ledger]))
    return result
