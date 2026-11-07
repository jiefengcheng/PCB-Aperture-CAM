"""Crop trial of balanced local growth with a hard 1.5x radius ceiling.

Separate from frozen T01/T01-R1. Source-only groups and priority reservations
are fixed before live decisions. Current-scene indexes are revision checked.
"""
from __future__ import annotations
import math,re
from collections import defaultdict
from src.clearance_policy import HARD_GAP_MM, CONSTRUCTION_GAP_MM, CONTACT_BUFFER_MM, LEGACY_CONSTRUCTION_MM, BARRIER_GAP_MM
from dataclasses import dataclass
from shapely import STRtree
from shapely.geometry import Point
from shapely.ops import unary_union
from src.crop_balanced_capped_growth import require_radius_cap
from src.crop_square_neighbor_experiment import (
    Settings,construct,largest_feasible_round,inscribed_square,facing_square_side,
    geometry_hash,verify_addition,
)
from src.stage_abi.preparation import prepared_tree as STRtree,prepared_buffer,prepared_intersection


@dataclass(frozen=True)
class CropSettings:
    hard_factor:float=1.5
    construction_gap:float=LEGACY_CONSTRUCTION_MM
    hard_gap:float=HARD_GAP_MM
    safety:float=.00002
    orientation:float=-45
    qsegs:int=128
    area_epsilon:float=1e-10
    event_epsilon:float=1e-8

    def kernel(self):
        if self.hard_factor!=1.5:raise ValueError('HARD_CAP_MUST_BE_1_5')
        return Settings(construction_gap_mm=self.construction_gap,hard_gap_mm=self.hard_gap,
                        orientation_degrees=self.orientation,quad_segs=self.qsegs)


def local_groups(sites,seed_pair,gap=LEGACY_CONSTRUCTION_MM):
    """Disjoint nearest competition pairs; preserve the owner-reviewed pair."""
    byid={s['source_id']:s for s in sites}
    if len(seed_pair)!=2 or len(set(seed_pair))!=2 or any(i not in byid for i in seed_pair):
        raise ValueError('INVALID_REVIEWED_PAIR')
    used=set(seed_pair);groups=[list(seed_pair)];edges=[]
    for i,a in enumerate(sites):
        for b in sites[i+1:]:
            d=math.dist(a['center'],b['center'])
            if d-1.5*(a['radius']+b['radius'])<=gap:
                edges.append((d/(a['radius']+b['radius']),min(a['source_id'],b['source_id']),max(a['source_id'],b['source_id'])))
    for _,a,b in sorted(edges):
        if a not in used and b not in used:groups.append([a,b]);used.update([a,b])
    groups.extend([[s['source_id']] for s in sites if s['source_id'] not in used])
    return [{'group_id':f'G{i+1:02d}','site_ids':ids,'rule':'owner-reviewed pair' if i==0 else 'nearest available competing pair' if len(ids)==2 else 'unpaired singleton'} for i,ids in enumerate(groups)]


class WorkingScene:
    """Full source geometry, alias-aware atomic updates and rebuilt STRtree."""
    def __init__(self,source,rows,shapes,sites,settings=CropSettings()):
        self.source=source;self.rows=rows;self.original=list(shapes);self.shapes=list(shapes)
        self.sites={s['source_id']:s for s in sites};self.settings=settings
        self.alias={alias:s['source_id'] for s in sites for alias in s['aliases']}
        self.revision=0;self.index_revision=0;self.tree=STRtree(self.shapes)
        self.accepted={};self.history=[];self.ports={}
        for site in sites:
            cap=Point(*site['center']).buffer(1.5*site['radius'],quad_segs=settings.qsegs)
            ids=self.tree.query(cap.buffer(max(.031,settings.construction_gap+.001),quad_segs=settings.qsegs))
            zones={}
            for item in ids:
                i=int(item);row=rows[i];geometry=shapes[i]
                if 't01_original_region'in row:
                    from src.t01_region_contacts import original_port
                    port=original_port(site,row,geometry,quad_segs=settings.qsegs)
                    if port is not None:zones[row['id']]=port
                    continue
                if row['kind'] not in ('segment','arc') or not geometry.intersects(site['core'].buffer(1e-7,quad_segs=settings.qsegs)):continue
                width=re.search(r'\(\s*width\s+([0-9.]+)\s*\)',source[slice(*row['source_span'])].decode())
                if not width:raise ValueError('SOURCE_TRACE_WIDTH_MISSING')
                zones[row['id']]=prepared_intersection(prepared_buffer(geometry,max(.005,float(width.group(1))/2+.005),quad_segs=settings.qsegs),prepared_buffer(site['core'],.5*site['radius'],quad_segs=settings.qsegs))
            if any('t01_original_region'in rows[int(i)]for i in ids):
                from src.t01_region_contacts import integral_trace_ports
                local_ids=sorted(map(int,ids))
                linked=integral_trace_ports(site,[rows[i]for i in local_ids],
                                           [shapes[i]for i in local_ids],quad_segs=settings.qsegs)
                for sid,permission in linked.items():
                    zones[sid]=permission if sid not in zones else zones[sid].union(permission)
            self.ports[site['source_id']]=zones

    def obstacles(self,site,expected_revision,overrides=None):
        if expected_revision!=self.revision or self.index_revision!=self.revision:
            raise ValueError('STALE_SCENE_OR_INDEX_REVISION')
        cap=Point(*site['center']).buffer(1.5*site['radius'],quad_segs=self.settings.qsegs)
        influence=cap.buffer(max(.031,self.settings.construction_gap+.001),quad_segs=self.settings.qsegs)
        indexes={int(i) for i in self.tree.query(influence)}
        if overrides:
            for key in overrides:indexes.update(self.sites[key]['indexes'])
        result={}
        for i in sorted(indexes):
            row=self.rows[i];sid=row['id'];canonical=self.alias.get(sid,sid)
            if canonical==site['source_id']:continue
            geometry=self.shapes[i]
            if overrides and canonical in overrides:geometry=overrides[canonical]
            result[canonical]={'source_id':canonical,'kind':row['kind'],'geometry':geometry,
                               'port_zone':self.ports[site['source_id']].get(sid)}
        return list(result.values())

    def commit(self,site,candidate,expected_revision):
        if expected_revision!=self.revision:raise ValueError('STALE_ATOMIC_PATCH')
        radius=site['radius'];cap=Point(*site['center']).buffer(1.5*radius,quad_segs=self.settings.qsegs)
        if site['core'].difference(candidate).area>self.settings.area_epsilon or candidate.difference(cap).area>self.settings.area_epsilon:
            raise ValueError('PATCH_CORE_OR_HARD_CAP_FAILURE')
        old=self.revision
        for i in site['indexes']:self.shapes[i]=candidate
        self.accepted[site['source_id']]=candidate
        self.revision+=1;self.tree=STRtree(self.shapes);self.index_revision=self.revision
        self.history.append({'source_id':site['source_id'],'input_revision':old,'output_revision':self.revision,'geometry_sha256':geometry_hash(candidate)})


def choose_priorities(sites,scene):
    groups=defaultdict(list)
    for s in sites:groups[s['physical_contact_group']].append(s)
    selected={};exceptions=[]
    for group,members in sorted(groups.items()):
        for s in sorted(members,key=lambda s:(-s['radius'],s['source_id'])):
            obs=scene.obstacles(s,0)
            ports=unary_union(list(scene.ports[s['source_id']].values()))
            visible=s['core'].boundary.difference(ports)
            residual=max(abs(math.dist(s['center'],v)-s['radius']) for v in s['core'].exterior.coords)
            if residual>.00002:continue
            if any(visible.intersection(r['geometry']).length>1e-5 for r in obs if r['port_zone'] is None):continue
            selected[group]=s['source_id'];break
        else:exceptions.append({'component_id':group,'reason':'NO_SOURCE_QUALIFIED_ROUND_PRIORITY','site_ids':[s['source_id'] for s in members]})
    return selected,exceptions


def freeze_factors(sites,groups,priorities,scene,settings=CropSettings()):
    byid={s['source_id']:s for s in sites};bygroup={g['group_id']:g for g in groups}
    membergroup={sid:g['group_id'] for g in groups for sid in g['site_ids']}
    factors={g['group_id']:1.5 for g in groups};limits=[];round_factors={}
    for sid in priorities.values():
        s=byid[sid]
        result=largest_feasible_round(s['core'],s['center'],s['radius'],1.5*s['radius'],scene.obstacles(s,0),settings=settings.kernel(),safety_mm=settings.safety)
        k=result['radius_mm']/s['radius'];round_factors[sid]=k;gid=membergroup[sid]
        if k<factors[gid]:limits.append({'group_id':gid,'reason':'ROUND_PRIORITY_SOURCE_FEASIBILITY','source_id':sid,'factor':k});factors[gid]=k
    # Within a local pair, A's enlarged-circle square bounds B's envelope.
    for group in groups:
        ids=group['site_ids']
        if len(ids)!=2:continue
        pair=[byid[i] for i in ids]
        anchors=[s for s in pair if s['source_id'] in priorities.values()]
        anchor=next((s for s in pair if s['source_id']==ids[0]),pair[0]) if not anchors else sorted(anchors,key=lambda s:s['source_id'])[0]
        b=next(s for s in pair if s is not anchor)
        side=facing_square_side(inscribed_square(anchor['center'],anchor['radius'],orientation_degrees=settings.orientation),anchor['center'],b['center'])
        projection=sum(side['normal'][j]*(b['center'][j]-anchor['center'][j]) for j in range(2))
        bound=(projection-settings.construction_gap-settings.safety)/(b['radius']+anchor['radius']/math.sqrt(2))
        group['square_anchor_id']=anchor['source_id'];group['square_follower_id']=b['source_id'];group['square_factor_bound']=bound
        if bound<factors[group['group_id']]:
            factors[group['group_id']]=max(1,bound);limits.append({'group_id':group['group_id'],'reason':'EARLIER_SQUARE_ENVELOPE_BOUND','factor':max(1,bound)})
    # Co-reserve all round priorities. Reduce growth increments, preserving each
    # local group's common factor, until round-round separation is feasible.
    ids=sorted(priorities.values())
    for i,aid in enumerate(ids):
        a=byid[aid]
        for bid in ids[i+1:]:
            b=byid[bid];ga=membergroup[aid];gb=membergroup[bid]
            d=math.dist(a['center'],b['center']);budget=d-settings.construction_gap-settings.safety-a['radius']-b['radius']
            growth=(factors[ga]-1)*a['radius']+(factors[gb]-1)*b['radius']
            if growth<=max(0,budget)+1e-12:continue
            t=max(0,min(1,budget/growth))
            for gid in sorted({ga,gb}):
                before=factors[gid];factors[gid]=1+(before-1)*t
                limits.append({'group_id':gid,'reason':'CO_RESERVED_ROUND_PRIORITIES','other_pair':[aid,bid],'previous_factor':before,'factor':factors[gid]})
    for group in groups:
        gid=group['group_id'];k=factors[gid]
        if max((k-1)*byid[i]['radius'] for i in group['site_ids'])<=settings.safety:k=1.;factors[gid]=k
        for sid in group['site_ids']:require_radius_cap(byid[sid]['radius'],k*byid[sid]['radius'])
        group['factor']=k
    return factors,limits,round_factors


def execute(source,rows,shapes,sites,groups,priorities,*,dynamic=True,settings=CropSettings(),counterfactuals=True,targets=None,square_guided_ids=(),surface_guard=None):
    scene=WorkingScene(source,rows,shapes,sites,settings);byid=scene.sites
    groupfor={sid:g for g in groups for sid in g['site_ids']};priority_ids=set(priorities.values())
    order=sorted(priority_ids)+[s['source_id'] for s in sites if s['source_id'] not in priority_ids]
    decisions=[];events=[];failed=[];frozen_scene=None
    def companion_candidate(site,radius,obs):
        if site['source_id'] in square_guided_ids:
            from src.crop_square_recess import square_guided_recess
            return square_guided_recess(site,radius,obs,settings)
        return construct(site['core'],site['center'],radius,obs,square_enabled=False,settings=settings.kernel())['candidate'],[]
    for sid in order:
        s=byid[sid];group=groupfor[sid];radius=targets[sid] if targets is not None else group['factor']*s['radius'];require_radius_cap(s['radius'],radius)
        if sid not in priority_ids and frozen_scene is None:
            frozen_scene=WorkingScene(source,rows,shapes,sites,settings)
            for pid in sorted(priority_ids):frozen_scene.commit(byid[pid],scene.accepted[pid],frozen_scene.revision)
        context=scene if dynamic or sid in priority_ids else frozen_scene
        obs=context.obstacles(s,context.revision);rev=scene.revision
        # Native circle vertices can have a different angular phase from the
        # inscribed buffer polygon at the same analytic radius. Preserve the
        # exact immutable core; do not shave it or weaken the containment test.
        envelope=unary_union([s['core'],Point(*s['center']).buffer(radius,quad_segs=settings.qsegs)])
        square_recesses=[]
        if radius==s['radius']:candidate=s['core']
        elif sid in priority_ids:candidate=envelope
        else:candidate,square_recesses=companion_candidate(s,radius,obs)
        if surface_guard is not None:candidate=surface_guard.limit(s,candidate,context,priority=sid in priority_ids)
        verification=verify_addition(s['core'],candidate,envelope,obs,settings=settings.kernel())
        if not verification['passed']:
            failed.append({'source_id':sid,'input_revision':context.revision,'candidate_sha256':geometry_hash(candidate),'candidate':candidate,'verification':verification})
            candidate=s['core'];decision='REJECT_KEEP_SOURCE'
            verification=verify_addition(s['core'],candidate,envelope,obs,settings=settings.kernel())
        else:decision=('ROUND_GROW_PRIORITY' if sid in priority_ids else 'GROW_COMPANION') if candidate.difference(s['core']).area>settings.area_epsilon else 'KEEP_PRIORITY' if sid in priority_ids else 'KEEP_CONSTRAINED'
        active=[]
        if dynamic and counterfactuals and sid not in priority_ids and verification['passed'] and candidate.difference(s['core']).area>settings.event_epsilon:
            for neighbor in sorted(scene.accepted):
                n=byid[neighbor];earlier=scene.accepted[neighbor]
                if earlier.difference(n['core']).area<=settings.event_epsilon:continue
                if not any(r['source_id']==neighbor for r in obs):continue
                cfobs=context.obstacles(s,context.revision,{neighbor:n['core']})
                cf,_=companion_candidate(s,radius,cfobs)
                if surface_guard is not None:cf=surface_guard.limit(s,cf,context,record=False,overrides={neighbor:n['core']})
                area=candidate.symmetric_difference(cf).area
                if area>settings.event_epsilon:
                    verified=verify_addition(s['core'],cf,envelope,cfobs,settings=settings.kernel())
                    event={'target_source_id':sid,'neighbor_source_id':neighbor,'neighbor_role':'reserved round priority' if neighbor in priority_ids else 'earlier accepted companion','input_scene_revision':context.revision,'radius_held_fixed_mm':radius,'changed_area_mm2':area,'candidate_sha256':geometry_hash(candidate),'counterfactual_sha256':geometry_hash(cf),'counterfactual':cf,'earlier_copper':earlier,'counterfactual_verification':verified}
                    events.append(event);active.append(neighbor)
        scene.commit(s,candidate,rev)
        decisions.append({'source_id':sid,'aliases':s['aliases'],'center':s['center'],'source_radius_mm':s['radius'],'proposed_radius_mm':radius,
            'factor':group['factor'] if targets is None else radius/s['radius'],'group_id':group['group_id'],'physical_component':s['physical_contact_group'],'priority':sid in priority_ids,
            'decision':decision,'input_revision':rev,'context_revision':context.revision if not dynamic else rev,'output_revision':scene.revision,
            'added_area_mm2':candidate.difference(s['core']).area,'clipped_optional_area_mm2':envelope.difference(candidate).area,
            'active_earlier_neighbors':active,'candidate_sha256':geometry_hash(candidate),'verification':verification})
        if targets is not None:decisions[-1].update(square_guided=sid in square_guided_ids,square_recesses=square_recesses)
    return {'scene':scene,'decisions':decisions,'events':events,'failed_patches':failed,'order':order}
