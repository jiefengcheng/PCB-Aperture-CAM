"""Maximal native arc chains and unequal full-length parallel members.

Reuse the original curve fit and neighbor discovery. Fit windows select a
relationship; neither a window nor a native occurrence seam cuts a member.
"""
import math
from collections import defaultdict
import numpy as np
from shapely import STRtree
from shapely.geometry import LineString
from shapely.ops import substring
from src.stage_abi.store import canonical,digest
from src.primary_parallel_cohorts import choose_primary_cohorts
from ._curve_catalogue import candidate_neighbor,sample_curve,fit_model,full_residual


def tangent(points,at_end):
    """Interior quadratic derivative, avoiding the rounded source end chord."""
    p=np.asarray(points,float);t=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    if at_end:p=p[::-1];t=t[-1]-t[::-1]
    inside=np.flatnonzero((t>0)&(t<t[-1])&(t<=min(.02,t[-1]*.1)))
    if len(inside)<3:inside=np.arange(1,min(len(p)-1,5))
    if len(inside)>=3:
        span=t[inside[-1]];coeff=np.polynomial.polynomial.polyfit(t[inside]/span,p[inside],2)
        vector=coeff[1]/span
    else:vector=p[-1]-p[0]
    size=float(np.linalg.norm(vector))
    if size<=1e-15:raise ValueError('NONDEGENERATE_ARC_TANGENT_REQUIRED')
    return vector/size


def maximal_members(straight,curves,*,noise_fraction=.01):
    if not math.isfinite(noise_fraction)or not 0<noise_fraction<1:raise ValueError('VALID_ARC_CONFIDENCE_REQUIRED')
    arcs=curves['arcs'];nodes=defaultdict(list)
    for i,a in enumerate(arcs):
        for side,pt in enumerate((a['points'][0],a['points'][-1])):nodes[a['route_id'],tuple(pt)].append((i,side))
    for i,r in enumerate(straight['runs']):
        for pt in(r['start'],r['end']):nodes[r['route_id'],tuple(pt)].append(('straight:'+str(i),None))
    links=defaultdict(dict);rejected=[]
    for (route,pt),ends in sorted(nodes.items()):
        if len(ends)!=2 or any(not isinstance(i,int)for i,_ in ends):continue
        (a,ea),(b,eb)=ends
        if a==b or abs(arcs[a]['width_mm']-arcs[b]['width_mm'])>1e-12:continue
        first=tangent(arcs[a]['points'],ea==1);second=tangent(arcs[b]['points'],eb==1)
        alignment=float(first@second);sine=abs(float(first[0]*second[1]-first[1]*second[0]))
        if alignment>=0 or sine>noise_fraction+1e-12:
            rejected.append(dict(a=a,b=b,endpoint_mm=list(pt),sine=sine,reason='NATIVE_ARC_JOIN_TANGENT_OUTSIDE_CONFIDENCE'));continue
        links[a][ea]=(b,eb);links[b][eb]=(a,ea)
    visited=set();members=[];mapping={}
    for seed in sorted(range(len(arcs)),key=lambda i:(len(links[i])==2,arcs[i]['source_id'])):
        if seed in visited:continue
        start_side=next((side for side in(0,1)if side not in links[seed]),0)
        index=seed;side=start_side;points=[];sources=[];intervals=[];length=0.;native=[]
        while index not in visited:
            a=arcs[index];part=a['points']if side==0 else a['points'][::-1]
            proposed=part if not points else points+part[1:]
            if points and not LineString(proposed).is_simple:break
            size=float(LineString(part).length)
            intervals.append(dict(source_id=a['source_id'],first_mm=length,last_mm=length+size,direction=1 if side==0 else-1))
            sources.append(a['source_id']);native.append(index);points=proposed;length+=size;visited.add(index)
            next_edge=links[index].get(1-side)
            if next_edge is None or next_edge[0]in visited:break
            index,side=next_edge
        member=dict(member_id='AM-'+digest(canonical(intervals))[:16],route_id=arcs[seed]['route_id'],
                    source_ids=sources,native_arc_indices=native,source_intervals_mm=intervals,
                    reference_points_mm=points,length_mm=length,width_mm=arcs[seed]['width_mm'],
                    member_domain_mm=[0.,length],reference_refitted=False)
        for i in native:mapping[i]=len(members)
        members.append(member)
    return members,mapping,rejected


def catalogue(straight,curves,*,noise_fraction=.01,minimum_shared_mm=.05):
    members,mapping,rejected=maximal_members(straight,curves,noise_fraction=noise_fraction)
    shapes=[LineString(m['reference_points_mm'])for m in members];tree=STRtree(shapes)
    samples=[sample_curve(m['reference_points_mm'])for m in members]
    relations=[]
    for i,a in enumerate(members):
        if a['length_mm']<minimum_shared_mm:continue
        for j in sorted(map(int,tree.query(shapes[i],predicate='dwithin',distance=.5))):
            if j<=i:continue
            b=members[j]
            if a['route_id']==b['route_id']or b['length_mm']<minimum_shared_mm:continue
            if shapes[i].distance(shapes[j])<=(a['width_mm']+b['width_mm'])/2:continue
            forward=fit_model(samples[i],samples[j]);reverse=fit_model(samples[j],samples[i])
            if forward is not None and reverse is not None:
                error=full_residual(a['reference_points_mm'],b['reference_points_mm'],forward)/b['length_mm']
                back=full_residual(b['reference_points_mm'],a['reference_points_mm'],reverse)/a['length_mm']
                if max(error,back)<=noise_fraction+1e-12:
                    # A spatially translated copy need not have matching
                    # nearest-point tangents. Template fit is the user's
                    # curve category; source-rail budgets prove clearance.
                    relations.append(dict(a=str(i),b=str(j),normalized_error=error,reverse_normalized_error=back,
                        fit=forward,reverse_fit=reverse,fit_scope='FULL_MEMBERS',
                        shared_sampled_run_mm=min(a['length_mm'],b['length_mm']),
                        a_stations_mm=[0.,a['length_mm']],b_stations_mm=[0.,b['length_mm']]))
                    continue
            witness=candidate_neighbor(a,b,shapes[i],shapes[j])
            if witness is None or witness['shared_sampled_run_mm']<minimum_shared_mm:continue
            aa=substring(shapes[i],*witness['a_stations_mm']);bb=substring(shapes[j],*witness['b_stations_mm'])
            forward=fit_model(sample_curve(aa.coords),sample_curve(bb.coords))
            reverse=fit_model(sample_curve(bb.coords),sample_curve(aa.coords))
            if forward is None or reverse is None:continue
            error=full_residual(aa.coords,bb.coords,forward)/bb.length
            back=full_residual(bb.coords,aa.coords,reverse)/aa.length
            if max(error,back)>noise_fraction+1e-12:continue
            relations.append(dict(a=str(i),b=str(j),normalized_error=error,reverse_normalized_error=back,
                                  fit=forward,reverse_fit=reverse,fit_scope='COMMON_WITNESS',**witness))
    adjacent=defaultdict(set)
    for e in relations:adjacent[e['a']].add(e['b']);adjacent[e['b']].add(e['a'])
    candidates=[]
    for anchor,others in sorted(adjacent.items()):
        units=sorted({anchor,*others});token=sorted(members[int(i)]['member_id']for i in units)
        candidates.append(dict(candidate_id='PGCM-'+digest(canonical(token))[:16],members=units,
            edges=[(anchor,i)for i in sorted(others)],score=sum(members[int(i)]['length_mm']for i in units),anchor=anchor))
    primary=choose_primary_cohorts(sorted(adjacent),candidates);groups=[]
    selected=[g for g in primary if len(g['units'])>=2]
    assigned={i for g in selected for i in g['units']}
    # Like the retained native curve catalogue, secondary template groups may
    # overlap. Do not strand a valid member merely because its anchor already
    # has a primary group. The constructor claims each whole member once;
    # later groups see previously constructed members as fixed obstacles.
    for c in sorted(candidates,key=lambda c:(-c['score'],c['candidate_id'])):
        if set(c['members'])<=assigned:continue
        selected.append(dict(units=c['members'],primary_candidate_id=c['candidate_id']))
        assigned.update(c['members'])
    for g in selected:
        if len(g['units'])<2:continue
        indices=sorted(map(int,g['units']));units=set(g['units'])
        groups.append(dict(group_id=g['primary_candidate_id'],kind='MAXIMAL_CURVE',
            members=[members[i]for i in indices],
            relationship_witnesses=[e for e in relations if e['a']in units and e['b']in units],
            equal_member_length_required=False,overlap_is_member_domain=False,geometry_authority=False))
    return dict(schema='t04-maximal-arc-catalogue/1',noise_fraction=noise_fraction,minimum_shared_mm=minimum_shared_mm,
        maximal_curve_members=members,native_arc_to_member={str(i):m for i,m in mapping.items()},
        curve_groups=groups,all_curve_relationships=relations,rejected_native_joins=rejected,
        member_selection='MAXIMAL_CONTINUOUS_NATIVE_ARC_CHAIN; TRUE_ENDPOINTS_ONLY',
        fit_domain='RECORDED_COMMON_WITNESS; FULL_UNEQUAL_MEMBERS_RETAINED',
        geometry_audit=False,source_copper_changed=False,source_members_split=False)
