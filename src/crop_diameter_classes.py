"""Source-only, discrete physical-diameter sizing for the bounded T01 trial.

Class membership describes the pre-clipping envelope. A recessed contour is not
silently reported as a circle of that diameter. Original KEEP radii are exempt
from the experimental palette, never rescaled or shaved to fit it.
"""
from __future__ import annotations
import math
from shapely.geometry import Point
from shapely.ops import unary_union
from src.crop_square_neighbor_experiment import inscribed_square, facing_square_side, verify_addition


def admissible_diameters(radius, palette):
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError('INVALID_SOURCE_RADIUS')
    if not palette or list(palette) != sorted(set(palette)) or any(not math.isfinite(d) or d <= 0 for d in palette):
        raise ValueError('INVALID_DIAMETER_PALETTE')
    # Strict upper comparison: even a rounded display label cannot exceed cap.
    return [d for d in palette if 2*radius < d <= 3*radius]


def select_targets(sites, groups, priorities, scene, settings, palette):
    """Freeze classes before construction, using ORG and fixed source ports only.

    Pairs prefer their largest shared physical class. Full-round priority
    constraints demote only the constrained priority, not its roomy companion.
    Round-round conflicts demote both sides one class at a time. No continuous
    radius optimizer or EDIT lookup enters this policy.
    """
    byid = {s['source_id']: s for s in sites}
    choices = {sid: admissible_diameters(s['radius'], palette) for sid,s in byid.items()}
    targets = {}; records = {}; limits = []
    for group in groups:
        ids = group['site_ids']
        common = set(choices[ids[0]])
        for sid in ids[1:]: common.intersection_update(choices[sid])
        shared = max(common) if common else None
        group['target_diameter_mm'] = shared
        group['factor'] = None  # this policy shares mm classes, never factors
        for sid in ids:
            diameter = shared or max(choices[sid], default=2*byid[sid]['radius'])
            targets[sid] = diameter/2
            records[sid] = {'desired_diameter_mm':diameter, 'shared_group_class_mm':shared,
                            'admissible_classes_mm':choices[sid], 'limits':[]}
    priority_ids = sorted(priorities.values())
    for sid in priority_ids:
        s=byid[sid];obs=scene.obstacles(s,0)
        for diameter in sorted([d for d in choices[sid] if d/2 <= targets[sid]], reverse=True):
            candidate=unary_union([s['core'],Point(*s['center']).buffer(diameter/2,quad_segs=settings.qsegs)])
            check=verify_addition(s['core'],candidate,candidate,obs,settings=settings.kernel())
            if check['passed']:
                targets[sid]=diameter/2;break
            records[sid]['limits'].append({'reason':'ROUND_PRIORITY_SOURCE_CLEARANCE','rejected_diameter_mm':diameter,'verification':check})
        else: targets[sid]=s['radius']
    # Every step strictly descends a finite palette (or reaches exact source).
    def demote(sid,reason):
        s=byid[sid];before=targets[sid]
        lower=[d/2 for d in choices[sid] if s['radius'] < d/2 < before]
        targets[sid]=max(lower,default=s['radius'])
        record={'reason':reason,'previous_diameter_mm':2*before,'diameter_mm':2*targets[sid]}
        records[sid]['limits'].append(record);limits.append({'source_id':sid,**record})
    while True:
        conflicts=[]
        for i,aid in enumerate(priority_ids):
            for bid in priority_ids[i+1:]:
                a,b=byid[aid],byid[bid]
                if targets[aid]==a['radius'] and targets[bid]==b['radius']:continue
                if math.dist(a['center'],b['center'])-targets[aid]-targets[bid] < settings.construction_gap+settings.safety:
                    conflicts.append((aid,bid))
        if not conflicts:break
        to_demote=sorted({sid for pair in conflicts for sid in pair if targets[sid]>byid[sid]['radius']})
        if not to_demote: raise ValueError('UNRESOLVABLE_ROUND_RESERVATION')
        for sid in to_demote:demote(sid,'DISCRETE_CO_RESERVED_ROUND_PRIORITIES')
    # Preserve the prior A-square/B-envelope stopping definition, without
    # transmitting a round priority's reduced size to its partner as a factor.
    for group in groups:
        ids=group['site_ids']
        if len(ids)!=2:continue
        anchors=sorted(sid for sid in ids if sid in priority_ids)
        aid=anchors[0] if anchors else ids[0];bid=next(sid for sid in ids if sid!=aid)
        a,b=byid[aid],byid[bid]
        side=facing_square_side(inscribed_square(a['center'],targets[aid],orientation_degrees=settings.orientation),a['center'],b['center'])
        projection=sum(side['normal'][j]*(b['center'][j]-a['center'][j]) for j in range(2))
        bound=projection-settings.construction_gap-settings.safety-targets[aid]/math.sqrt(2)
        group.update(square_anchor_id=aid,square_follower_id=bid,square_radius_bound_mm=bound)
        while targets[bid]>max(b['radius'],bound):demote(bid,'A_SQUARE_ENVELOPE_BOUND')
    for sid,s in byid.items():
        assert s['radius']<=targets[sid]<=1.5*s['radius']
        records[sid].update(proposed_radius_mm=targets[sid],selected_diameter_mm=2*targets[sid],
                            category_mm=2*targets[sid] if targets[sid]>s['radius'] else None,
                            original_keep=targets[sid]==s['radius'],
                            hard_cap_diameter_mm=3*s['radius'])
    return targets,records,limits


def square_guided_recess(site, radius, obstacles, settings):
    """Recess optional growth on conflicting square-facing sides, then clip.

    Directions come from nearest points of actual applicable source/live copper.
    Every consumed side is logged. No EDIT direction or target contour is read.
    """
    from shapely.ops import nearest_points
    from src.crop_square_neighbor_experiment import construct, square_facing_lobe, retain_attached
    core=site['core'];center=site['center'];kernel=settings.kernel()
    result=construct(core,center,radius,obstacles,square_enabled=False,settings=kernel)
    envelope=result['envelope'];optional=envelope.difference(core);consumed=[]
    conflicts=[]
    for row in obstacles:
        excluded=row['geometry'].buffer(settings.construction_gap,quad_segs=settings.qsegs)
        if row.get('port_zone') is not None:excluded=excluded.difference(row['port_zone'])
        area=optional.intersection(excluded).area
        if area>settings.event_epsilon:conflicts.append((area,row['source_id'],excluded))
    # One primary recess, selected by greatest real conflict area, stable ID tie.
    # Other obstacles still clip ordinarily; do not replace every arc by a square.
    preferred=site.get('square_recess_neighbor_id')
    if preferred:
        conflicts=[item for item in conflicts if item[1]==preferred]
        if not conflicts:raise ValueError('OWNER_RECESS_NEIGHBOR_HAS_NO_ACTUAL_CONFLICT')
    if conflicts:
        area,source_id,excluded=sorted(conflicts,key=lambda item:(-item[0],item[1]))[0]
        point=nearest_points(Point(*center),excluded)[1]
        if point.distance(Point(*center))>1e-12:
            lobe,side=square_facing_lobe(envelope,result['square'],center,(point.x,point.y))
            removed=optional.intersection(lobe)
            if removed.area>settings.event_epsilon:
                consumed.append({'source_id':source_id,'square_side':side,'conflict_area_mm2':area,'removed_optional_area_mm2':removed.area,'direction_point_mm':[point.x,point.y]})
                optional=optional.difference(lobe)
    # Square guides only optional recesses. Actual copper always sets hard gap.
    candidate,_=retain_attached(optional.intersection(result['candidate']),core,kernel)
    return candidate,consumed


def promote_round_priorities(sites, groups, priorities, scene, settings, targets, records):
    """Recover feasible discrete steps discarded by simultaneous demotions.

    Greedy largest area gain, stable source-ID tie break; a maximal allocation,
    not a global optimum. Never shrink another site or relax any constraint.
    """
    byid={s['source_id']:s for s in sites};priority_ids=sorted(priorities.values())
    accepted=[]
    def check(sid,radius):
        s=byid[sid];candidate=unary_union([s['core'],Point(*s['center']).buffer(radius,quad_segs=settings.qsegs)])
        source_check=verify_addition(s['core'],candidate,candidate,scene.obstacles(s,0),settings=settings.kernel())
        blockers=[]
        if not source_check['passed']:blockers.append({'reason':'ORIGINAL_COPPER_OR_SOURCE_PORT_CLEARANCE','verification':source_check})
        for other in priority_ids:
            if other==sid:continue
            n=byid[other]
            if math.dist(s['center'],n['center'])-radius-targets[other] < settings.construction_gap+settings.safety:
                blockers.append({'reason':'OTHER_FULL_ROUND_RESERVATION','source_id':other,'diameter_mm':2*targets[other]})
        for group in groups:
            if len(group['site_ids'])!=2:continue
            aid,bid=group['square_anchor_id'],group['square_follower_id']
            if sid not in (aid,bid):continue
            a,b=byid[aid],byid[bid];ra=radius if sid==aid else targets[aid];rb=radius if sid==bid else targets[bid]
            side=facing_square_side(inscribed_square(a['center'],ra,orientation_degrees=settings.orientation),a['center'],b['center'])
            bound=sum(side['normal'][j]*(b['center'][j]-a['center'][j]) for j in range(2))-settings.construction_gap-settings.safety-ra/math.sqrt(2)
            if rb>max(b['radius'],bound):blockers.append({'reason':'A_SQUARE_ENVELOPE_BOUND','group_id':group['group_id'],'follower_source_id':bid,'radius_bound_mm':bound})
        return blockers
    while True:
        options=[]
        for sid in priority_ids:
            larger=[d/2 for d in records[sid]['admissible_classes_mm'] if targets[sid]<d/2<=records[sid]['desired_diameter_mm']/2]
            if not larger:continue
            radius=min(larger)
            if not check(sid,radius):options.append((math.pi*(radius**2-targets[sid]**2),sid,radius))
        if not options:break
        gain,sid,radius=sorted(options,key=lambda item:(-item[0],item[1]))[0]
        accepted.append({'source_id':sid,'previous_diameter_mm':2*targets[sid],'diameter_mm':2*radius,'round_area_gain_mm2':gain})
        targets[sid]=radius
    # Freeze the stopping explanation for every source-bound round priority.
    for sid in priority_ids:
        larger=[d/2 for d in records[sid]['admissible_classes_mm'] if targets[sid]<d/2<=records[sid]['desired_diameter_mm']/2]
        blockers=check(sid,min(larger)) if larger else []
        assert not larger or blockers,'FREE_DISCRETE_ROUND_GROWTH_LEFT'
        records[sid]['round_opportunity']={'next_class_diameter_mm':2*min(larger) if larger else None,
            'blockers':blockers,'status':'BLOCKED_NEXT_CLASS' if larger else 'AT_DESIRED_CLASS_OR_CAP'}
        records[sid].update(proposed_radius_mm=targets[sid],selected_diameter_mm=2*targets[sid],
            category_mm=2*targets[sid] if targets[sid]>byid[sid]['radius'] else None,
            original_keep=targets[sid]==byid[sid]['radius'])
        assert targets[sid]<=1.5*byid[sid]['radius']
    # Square bounds depend on the final enlarged A radius, not an earlier value.
    for group in groups:
        if len(group['site_ids'])!=2:continue
        a,b=(byid[group[key]] for key in ['square_anchor_id','square_follower_id'])
        side=facing_square_side(inscribed_square(a['center'],targets[a['source_id']],orientation_degrees=settings.orientation),a['center'],b['center'])
        group['square_radius_bound_mm']=sum(side['normal'][j]*(b['center'][j]-a['center'][j]) for j in range(2))-settings.construction_gap-settings.safety-targets[a['source_id']]/math.sqrt(2)
    return accepted


def select_owner_review_targets(root, policy, sites):
    """Freeze reviewed radii, then apply only the owner's named sizing edits."""
    import copy, hashlib, json
    root=root.resolve()
    def read_bundle(relative, expected):
        folder=(root/relative).resolve()
        if not folder.is_relative_to(root/'out'):raise ValueError('REVIEW_BUNDLE_OUTSIDE_PROJECT_OUT')
        raw=(folder/'report.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('REVIEW_REPORT_HASH_MISMATCH')
        report=json.loads(raw)
        if report['source_sha256']!=policy['source_sha256']:raise ValueError('REVIEW_SOURCE_MISMATCH')
        return report
    reviewed=read_bundle(policy['previous_bundle'],policy['previous_report_sha256'])
    undo=read_bundle(policy['undo_reference_bundle'],policy['undo_reference_report_sha256'])
    bykey={d['key']:d for d in reviewed['decisions']};oldkeys={d['key']:d for d in undo['decisions']}
    byid={s['source_id']:s for s in sites}
    if set(byid)!={d['source_id'] for d in reviewed['decisions']}:raise ValueError('REVIEW_SITE_IDENTITY_MISMATCH')
    targets={d['source_id']:d['proposed_radius_mm'] for d in reviewed['decisions']}
    records={d['source_id']:copy.deepcopy(d['size_class']) for d in reviewed['decisions']}
    changes=[]
    for key in policy['undo_sites']:
        current,old=bykey[key],oldkeys[key]
        if current['source_id']!=old['source_id'] or old['proposed_radius_mm']>current['proposed_radius_mm']:raise ValueError('INVALID_OWNER_UNDO_REFERENCE')
        targets[current['source_id']]=old['proposed_radius_mm']
        changes.append({'key':key,'source_id':current['source_id'],'reason':'OWNER_CONFIRMED_UNDO','diameter_mm':2*old['proposed_radius_mm']})
    for key,neighbor_key in policy['square_recess_neighbors'].items():
        sid=bykey[key]['source_id'];s=byid[sid]
        targets[sid]=max(admissible_diameters(s['radius'],policy['diameter_classes_mm']))/2
        s['square_recess_neighbor_id']=bykey[neighbor_key]['source_id']
        changes.append({'key':key,'source_id':sid,'reason':'OWNER_SPECIFIC_SQUARE_GUIDED_RECESS','neighbor_key':neighbor_key,'diameter_mm':2*targets[sid]})
    groups=copy.deepcopy(reviewed['groups'])
    for group in groups:
        if len(group['site_ids'])!=2:continue
        a,b=(byid[group[key]] for key in ['square_anchor_id','square_follower_id'])
        side=facing_square_side(inscribed_square(a['center'],targets[a['source_id']],orientation_degrees=policy['orientation']),a['center'],b['center'])
        group['square_radius_bound_mm']=sum(side['normal'][j]*(b['center'][j]-a['center'][j]) for j in range(2))-policy['construction_gap']-policy['safety']-targets[a['source_id']]/math.sqrt(2)
    for sid,s in byid.items():
        radius=targets[sid]
        if not s['radius']<=radius<=1.5*s['radius']:raise ValueError('OWNER_EDIT_EXCEEDS_HARD_CAP_OR_SHAVES_CORE')
        record=records[sid];record.pop('round_opportunity',None)
        record.update(proposed_radius_mm=radius,selected_diameter_mm=2*radius,category_mm=2*radius if radius>s['radius'] else None,
            original_keep=radius==s['radius'],limits=[{'reason':'FROZEN_REVIEW_TARGET'}],desired_diameter_mm=max(record['desired_diameter_mm'],2*radius))
        for change in changes:
            if change['source_id']==sid:record['limits'].append(change)
    return targets,records,groups,changes
