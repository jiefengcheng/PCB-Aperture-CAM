"""Full source members, with local parallel witnesses kept separately.

Reuse the source catalogue and primary-cohort selector. Confidence selects a
relationship, never supplies clearance authority or permission to rotate it.
"""
import hashlib
import math
from src.parallel_trace_relations import relation_groups
from src.primary_parallel_cohorts import choose_primary_cohorts


def maximal_members(runs,*,noise_fraction=.01):
    """Extend consecutive native runs before considering group membership.

    Source order and endpoints are retained. An approximate join keeps its
    polyline; it is never replaced by a rotated perfect line. Direction span
    is measured over the whole member, so small turns cannot accumulate into
    a bend admitted by transitive pairwise similarity.
    """
    if not math.isfinite(noise_fraction) or not 0<noise_fraction<1:
        raise ValueError('VALID_PARALLEL_CONFIDENCE_PARAMETERS_REQUIRED')
    limit=math.asin(noise_fraction);by_route={}
    for i,r in enumerate(runs):by_route.setdefault(r['route_id'],[]).append(i)
    members=[];mapping={}
    for route,indices in sorted(by_route.items()):
        active=[];points=[];angles=[]
        def emit():
            if not active:return
            native=[runs[i]for i in active]
            length=sum(r['length_mm']for r in native)
            a,b=points[0],points[-1];dx,dy=b[0]-a[0],b[1]-a[1];chord=math.hypot(dx,dy)
            residual=max(abs((p[0]-a[0])*dy-(p[1]-a[1])*dx)/chord for p in points)
            source_ids=[s for r in native for s in r['source_ids']]
            identifier=native[0]['run_id'] if len(native)==1 else 'SM-'+hashlib.sha256('\n'.join(source_ids).encode()).hexdigest()[:16]
            member=dict(run_id=identifier,route_id=route,source_ids=source_ids,start=a,end=b,
                        length_mm=length,angle_degrees=math.degrees(math.atan2(dy,dx))%180,
                        native_run_indices=list(active),reference_points_mm=list(points),
                        direction_span_fraction=math.sin(max(angles)-min(angles)),
                        chord_residual_mm=residual,normalized_chord_residual=residual/length,
                        reference_refitted=False)
            if member['normalized_chord_residual']>noise_fraction+1e-12:
                raise ValueError('MAXIMAL_MEMBER_FIT_BOUND_CHANGED')
            index=len(members);members.append(member)
            mapping.update({i:index for i in active})
        for i in indices:
            r=runs[i];a,b=r['start'],r['end'];theta=math.atan2(b[1]-a[1],b[0]-a[0])
            relative=(theta-angles[0]+math.pi)%(2*math.pi)-math.pi+angles[0] if angles else theta
            append=(bool(active) and points[-1]==a
                    and max(*angles,relative)-min(*angles,relative)<=limit+1e-12)
            if active and not append:emit();active=[];points=[];angles=[]
            active.append(i);points.extend([a,b]if not points else[b]);angles.append(relative if append else theta)
        emit()
    return members,mapping


def catalogue(straight, curves, *, noise_fraction=.01, minimum_shared_mm=.05):
    if not 0 < noise_fraction < 1 or not math.isfinite(minimum_shared_mm) or minimum_shared_mm <= 0:
        raise ValueError('VALID_PARALLEL_CONFIDENCE_PARAMETERS_REQUIRED')
    native=straight['runs'];runs,mapping=maximal_members(native,noise_fraction=noise_fraction);arcs=curves['arcs']
    angle=math.degrees(math.asin(noise_fraction))
    witnesses=[];rejected=[]
    for e in straight['cases']['admitted_0.05']['edges']:
        a,b=mapping[e['a']],mapping[e['b']]
        if a==b:continue
        difference=abs(runs[a]['angle_degrees']-runs[b]['angle_degrees'])%180
        difference=min(difference,180-difference)
        target=witnesses if (e['shared_projected_length_mm'] >= minimum_shared_mm-1e-12
                            and e['alignment_angle_degrees'] <= angle+1e-10
                            and difference<=angle+1e-10) else rejected
        target.append(dict(e,a=a,b=b,native_run_pair=[e['a'],e['b']],
                           maximal_member_direction_difference_degrees=difference))
    ids={str(e[k]) for e in witnesses for k in ('a','b')}
    candidates=[]
    for component in relation_groups(ids,[(str(e['a']),str(e['b']))for e in witnesses]):
        members=set(component)
        edges=[e for e in witnesses if str(e['a'])in members and str(e['b'])in members]
        directions={i:runs[int(i)]['angle_degrees']%180 for i in component}
        # A connected chain is not a common template. Every candidate fits
        # inside one angular window, including the 0/180-degree seam.
        seen=set()
        for start in sorted(set(directions.values())):
            window=frozenset(i for i,a in directions.items() if (a-start)%180 <= angle+1e-10)
            if len(window)<2 or window in seen:continue
            seen.add(window)
            live=[e for e in edges if str(e['a'])in window and str(e['b'])in window]
            for group in relation_groups(window,[(str(e['a']),str(e['b']))for e in live]):
                if len(group)<2:continue
                token='\n'.join(sorted(runs[int(i)]['run_id']for i in group))
                candidates.append(dict(candidate_id='PGS-'+hashlib.sha256(token.encode()).hexdigest()[:16],
                    members=group,edges=[(str(e['a']),str(e['b']))for e in live
                                         if str(e['a'])in group and str(e['b'])in group],
                    score=sum(runs[int(i)]['length_mm']for i in group)))
    primary=choose_primary_cohorts(ids,candidates)
    groups=[]
    for c in primary:
        if len(c['units'])<2:continue
        indices=sorted(map(int,c['units']))
        groups.append(dict(group_id=c['primary_candidate_id'],kind='STRAIGHT',
            members=[dict(run_id=runs[i]['run_id'],route_id=runs[i]['route_id'],
                source_ids=runs[i]['source_ids'],start_mm=runs[i]['start'],end_mm=runs[i]['end'],
                reference_points_mm=runs[i]['reference_points_mm'],native_run_indices=runs[i]['native_run_indices'],
                normalized_chord_residual=runs[i]['normalized_chord_residual'],reference_refitted=False,
                member_domain_mm=[0.,runs[i]['length_mm']],length_mm=runs[i]['length_mm'])for i in indices],
            relationship_witnesses=[e for e in witnesses if e['a']in indices and e['b']in indices],
            equal_member_length_required=False,geometry_authority=False))
    curve_groups=[]
    for g in curves['cases']['admitted_0.05']['groups']:
        if any(t['normalized_error']>noise_fraction+1e-12 for t in g['transforms']):continue
        # Fitting applies only on the retained witness domains. Preserve the
        # whole native arc identity without extrapolating that fit certificate.
        curve_groups.append(dict(group_id=g['group_id'],kind='CURVE',
            members=[dict(source_id=arcs[i]['source_id'],route_id=arcs[i]['route_id'],
                          member_domain_mm=[0.,arcs[i]['length_mm']],length_mm=arcs[i]['length_mm'])for i in g['members']],
            relationship_witness=g,equal_member_length_required=False,geometry_authority=False))
    return dict(schema='t04-full-member-parallel-catalogue/1',noise_fraction=noise_fraction,
        maximal_straight_members=runs,native_run_to_member={str(i):m for i,m in mapping.items()},
        member_selection='LONGEST_CONTINUOUS_NATIVE_PREFIX_WITHIN_WHOLE_MEMBER_DIRECTION_WINDOW',
        group_selection='DESCENDING_SUM_OF_FULL_MEMBER_LENGTHS; EXISTING_PRIMARY_COHORT_SELECTOR',
        straight_metric='ABS_SIN_RELATIVE_DIRECTION; TRANSVERSE_DRIFT_PER_MEMBER_LENGTH',
        maximum_direction_difference_degrees=angle,
        curve_metric='EXISTING_FULL_POLYLINE_FIT_RESIDUAL_OVER_TARGET_CURVE_LENGTH_ON_WITNESS_DOMAIN',
        minimum_shared_mm=minimum_shared_mm,straight_groups=groups,curve_groups=curve_groups,
        all_straight_relationships=witnesses,rejected_straight_relationships=rejected,
        nonprimary_relationships_retained=True,source_members_split=False,
        overlap_is_member_domain=False,source_copper_changed=False,geometry_audit=False)
