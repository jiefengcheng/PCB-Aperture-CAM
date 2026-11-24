"""Source segments stay indivisible; group intervals are profile constraints.

This is an assembly plan, not authority to fill an unresolved interval. Width
stations may vary along one source body; they never mint extra source segments.
"""
import math


def source_profiles(rows, paths, construction):
    used={s:r for r,ss in paths.items() for s in ss}
    acquired={}
    for group in construction['groups']:
        for lane in group['lanes']:
            if not lane['mutable']:continue
            for s in lane['source_ids']:
                if s in used:
                    r=used[s];factor=lane['width_mm']/lane['source_width_mm']
                    acquired[r]=min(acquired.get(r,float('inf')),factor)
    result={}
    for s,r in sorted(used.items()):
        md=rows[s]['metadata']
        a,b=md['route_points_mm'][0],md['route_points_mm'][-1]
        length=sum(math.dist(x,y)for x,y in zip(md['route_points_mm'],md['route_points_mm'][1:]))
        if length<=0:raise ValueError('NONDEGENERATE_SOURCE_SEGMENT_REQUIRED')
        axis=[(b[i]-a[i])/length for i in (0,1)] if md['route_kind']=='segment' else None
        pose=construction.get('route_poses',{}).get(r,{}).get('translation_mm',[0.,0.])
        result[s]=dict(source_id=s,route_id=r,start_mm=a,end_mm=b,length_mm=length,
                       route_translation_mm=pose,
                       reference_start_mm=[a[i]+pose[i] for i in (0,1)],
                       reference_end_mm=[b[i]+pose[i] for i in (0,1)],
                       axis=axis,route_kind=md['route_kind'],constraints=[],body_count=1,source_segment_split=False,
                       inherited_factor=acquired.get(r),
                       inherited_width_mm=None if r not in acquired else md['minimum_caliper_mm']*acquired[r],
                       inheritance_is_ceiling=False,
                       override_policy='OWN_PARALLEL_GROUP_OR_EXPLICIT_DEFAULT_CASE_ONLY')
    for group in construction['groups']:
        for lane in group['lanes']:
            if not lane['mutable']:continue
            for s in lane['source_ids']:
                if s not in result or result[s]['axis'] is None:continue
                record=result[s];a=record['reference_start_mm'];u=record['axis']
                stations=[]
                for t in (group['first_mm'],group['last_mm']):
                    point=[t*group['axis'][0]-lane['source_normal_mm']*group['axis'][1],
                           t*group['axis'][1]+lane['source_normal_mm']*group['axis'][0]]
                    stations.append(sum((point[i]-a[i])*u[i] for i in (0,1)))
                lo,hi=max(0.,min(stations)),min(record['length_mm'],max(stations))
                if hi<=lo:continue
                record['constraints'].append(dict(first_mm=lo,last_mm=hi,width_mm=lane['width_mm'],
                    profile_midline_shift_mm=lane['profile_midline_shift_mm']*(1 if sum(u[i]*group['axis'][i] for i in (0,1))>=0 else -1)-sum(record['route_translation_mm'][i]*(-u[1],u[0])[i] for i in (0,1)),
                    group_band=group['catalogue_band_index']))
    for record in result.values():
        constraints=sorted(record['constraints'],key=lambda q:(q['first_mm'],q['last_mm']))
        record['constraints']=constraints
        default=construction.get('default_case_decisions',{}).get(record['source_id'])
        record['decision_basis']='OWN_PARALLEL_GROUP' if constraints else 'DEFAULT_CASE' if default is not None else 'INHERIT_ROUTE_GROWTH'
        if default is not None:record['default_case_decision']=default
        record['profile_stations_mm']=sorted({0.,record['length_mm'],*[v for q in constraints for v in(q['first_mm'],q['last_mm'])]})
        record['assembly_policy']='ONE_CONTINUOUS_SOURCE_BODY; RESOLVE_INTERVALS_AS_WIDTH_PROFILE'
        record['growth_domain_mm']=[0.,record['length_mm']]
        record['group_overlap_is_growth_domain']=False
        record['unconstrained_span_policy']='INHERIT_ACQUIRED_ROUTE_GROWTH; OVERRIDE_ONLY_BY_OTHER_PARALLEL_GROUP_OR_DEFAULT_CASE'
    # A native occurrence boundary inside one maximal straight member must
    # not restart a taper. Share the whole-member field, retaining source IDs
    # only as custody/materialization boundaries. Approximate polylines need
    # their own corridor constructor; never silently straighten them here.
    members=construction.get('full_member_catalogue',{}).get('maximal_straight_members',[])
    for member in members:
        sources=[s for s in member['source_ids']if s in result]
        if len(sources)<2:continue
        records=[result[s]for s in sources]
        a,b=member['start'],member['end'];length=math.dist(a,b)
        u=[(b[i]-a[i])/length for i in (0,1)]
        widths=[rows[s]['metadata']['minimum_caliper_mm']for s in sources]
        exact=all(q['axis'] is not None and abs(q['axis'][0]*u[1]-q['axis'][1]*u[0])<1e-10 for q in records)
        if (len(sources)!=len(member['source_ids']) or not exact or max(widths)-min(widths)>1e-12
                or any('default_case_decision'in q for q in records)):
            for q in records:q['maximal_member_field_disposition']='CATEGORY_OR_DEFAULT_CONSTRUCTION_REQUIRED; NO_REFIT'
            continue
        constraints=[];locations={}
        for q in records:
            start=sum((q['start_mm'][i]-a[i])*u[i]for i in (0,1))
            sign=1 if sum(q['axis'][i]*u[i]for i in (0,1))>0 else -1
            locations[q['source_id']]=(start,sign)
            for c in q['constraints']:
                lo,hi=sorted(start+sign*c[t]for t in ('first_mm','last_mm'))
                constraints.append(dict(c,first_mm=lo,last_mm=hi,profile_midline_shift_mm=sign*c['profile_midline_shift_mm']))
        context=dict(axis=u,length_mm=length,constraints=constraints,inherited_width_mm=records[0]['inherited_width_mm'])
        for q in records:
            q.update(maximal_member_id=member['run_id'],member_context=context,
                     member_source_start_mm=locations[q['source_id']][0],member_source_direction=locations[q['source_id']][1],
                     maximal_member_field_disposition='SHARED_EXACT_COLLINEAR_FIELD; SOURCE_SEAM_IS_NOT_TRANSITION')
    return dict(schema='t04-indivisible-source-profiles/1',segments=result,
                split_source_segments=0,geometry_emitted=False,acquired_route_factors=acquired,
                pending='CONTINUOUS_PROFILE_MATERIALIZATION_AND_INTERFACE_TREATMENT')


class ProfileUnresolved(ValueError):
    pass


def reference_profile(record,width,*,zero_side_shift):
    """Remove optional growth from both local and shared-member records."""
    result=dict(record,inherited_width_mm=width,
                constraints=[dict(q,width_mm=width,
                    profile_midline_shift_mm=0. if zero_side_shift else q['profile_midline_shift_mm'])for q in record['constraints']])
    if 'member_context'in record:
        result['member_context']=reference_profile(record['member_context'],width,zero_side_shift=zero_side_shift)
    if 'endpoint_widths_mm'in record:result['endpoint_widths_mm']=[width,width]
    if 'endpoint_sides_mm'in record:result['endpoint_sides_mm']=[[-width/2,width/2]]*2
    return result


def joint_widths(profiles,rows,targets):
    """One symmetric width at each real source endpoint; internal seams share fields."""
    endpoints={}
    for s,q in profiles['segments'].items():
        width=targets[s]
        for pt in (q['start_mm'],q['end_mm']):
            endpoints.setdefault((q['route_id'],tuple(round(v,10)for v in pt)),[]).append(width)
    for s,q in profiles['segments'].items():
        q['inherited_width_mm']=targets[s]
        q['endpoint_widths_mm']=[min(endpoints[q['route_id'],tuple(round(v,10)for v in pt)])for pt in(q['start_mm'],q['end_mm'])]
    for s,q in profiles['segments'].items():
        if 'member_context'in q:
            context=dict(q['member_context']);start=q['member_source_start_mm'];sign=q['member_source_direction']
            # Set only true member endpoints. Internal source seams are exact
            # restrictions of this shared field and never reset its tangent.
            members=[(t,r)for t,r in profiles['segments'].items()if r.get('maximal_member_id')==q['maximal_member_id']]
            context['inherited_width_mm']=min(targets[t]for t,r in members)
            widths=[]
            for station in (0.,context['length_mm']):
                hits=[]
                for t,r in members:
                    for local,w in zip((0.,r['length_mm']),r['endpoint_widths_mm']if 'endpoint_widths_mm'in r else [targets[t]]*2):
                        if abs(r['member_source_start_mm']+r['member_source_direction']*local-station)<1e-9:hits.append(w)
                widths.append(min(hits)if hits else context['inherited_width_mm'])
            context['endpoint_widths_mm']=widths;q['member_context']=context
    return profiles


def joint_side_fields(profiles,rows):
    """Resolve tangent straight joins before constructing any source body.

    Width alone does not bind the two physical edges of an asymmetric group.
    An endpoint reached by a frozen group supplies its exact sides; the next
    free span interpolates to those sides using the existing C1 field. Two
    incompatible frozen endpoints remain unresolved, never averaged or shaved.
    Native seams inside one maximal member already share a complete field.
    Curved/corner joins retain their existing moving-frame constructors.
    """
    segments=profiles['segments'];sites={};resolved=[];unresolved=[]
    for s,q in segments.items():
        for i,pt in enumerate((q['start_mm'],q['end_mm'])):
            sites.setdefault((q['route_id'],tuple(round(v,10)for v in pt)),[]).append((s,i))
    for (route,point),ends in sorted(sites.items()):
        if len(ends)<2 or any(segments[s]['axis']is None for s,i in ends):continue
        member_ids={segments[s].get('maximal_member_id')for s,i in ends}
        if len(member_ids)==1 and None not in member_ids:continue
        axis=segments[ends[0][0]]['axis']
        if any(abs(axis[0]*segments[s]['axis'][1]-axis[1]*segments[s]['axis'][0])>1e-10 for s,i in ends):continue
        hard=[]
        for s,i in ends:
            q=segments[s];station=0. if i==0 else q['length_mm']
            sign=1 if sum(a*b for a,b in zip(axis,q['axis']))>=0 else -1
            for window in q['constraints']:
                if window['first_mm']-1e-12<=station<=window['last_mm']+1e-12:
                    sides=[window['profile_midline_shift_mm']-window['width_mm']/2,
                           window['profile_midline_shift_mm']+window['width_mm']/2]
                    hard.append(sides if sign>0 else[-sides[1],-sides[0]])
        if hard:
            common=hard[0]
            if any(max(abs(a-b)for a,b in zip(common,v))>1e-12 for v in hard[1:]):
                unresolved.append(dict(route_id=route,point_mm=list(point),reason='FROZEN_GROUP_SIDES_DISAGREE',sources=[s for s,i in ends]));continue
        else:
            width=min(segments[s]['endpoint_widths_mm'][i]for s,i in ends)
            common=[-width/2,width/2]
        source_half=max(rows[s]['metadata']['minimum_caliper_mm']/2 for s,i in ends)
        if common[0]>-source_half+1e-12 or common[1]<source_half-1e-12:
            unresolved.append(dict(route_id=route,point_mm=list(point),reason='SHARED_SECTION_WOULD_THIN_SOURCE',sources=[s for s,i in ends]));continue
        for s,i in ends:
            q=segments[s];sign=1 if sum(a*b for a,b in zip(axis,q['axis']))>=0 else -1
            sides=list(common)if sign>0 else[-common[1],-common[0]]
            q.setdefault('endpoint_sides_mm',[None,None])[i]=sides
            if 'member_context'in q:
                station=q['member_source_start_mm']+q['member_source_direction']*(0. if i==0 else q['length_mm'])
                if abs(station)<1e-9:member_end=0
                elif abs(station-q['member_context']['length_mm'])<1e-9:member_end=1
                else:continue
                member_sides=sides if q['member_source_direction']>0 else[-sides[1],-sides[0]]
                for other in segments.values():
                    if other.get('maximal_member_id')!=q['maximal_member_id']:continue
                    context=dict(other['member_context'])
                    values=list(context.get('endpoint_sides_mm',[None,None]));values[member_end]=member_sides
                    context['endpoint_sides_mm']=values;other['member_context']=context
        resolved.append(dict(route_id=route,point_mm=list(point),sources=[s for s,i in ends],
                             sides_mm=common,frozen_group_authority=bool(hard)))
    report=dict(schema='t04-tangent-straight-joint-fields/1',resolved=resolved,unresolved=unresolved,
                geometry_searches=0,geometry_emitted=False,
                scope='TANGENT_STRAIGHT_JOINS; CURVED_AND_CORNER_CONSTRUCTORS_REMAIN_SEPARATE')
    profiles['joint_side_fields']=report
    return report


def fixed_continuation_sections(profiles,rows,native_paths):
    """Keep covered native members in the route's endpoint obligations.

    Covered/KEEP strokes are omitted from growth, not from route topology.
    Without these anchors the next eligible ribbon can inherit full optional
    width at a seam where its continuation is fixed at the input width.
    This preparation follows exact native endpoints only: no spatial search,
    reconstructed ownership, or geometry treatment.
    """
    from .ribbon_profile import frame
    fixed_sites={}
    live=set(profiles['segments'])
    for route,members in native_paths.items():
        for s in members:
            if s in live:continue
            points=rows[s]['metadata']['route_points_mm']
            for point in(points[0],points[-1]):
                fixed_sites.setdefault((route,tuple(round(v,10)for v in point)),[]).append(s)
    sections={};records=[]
    for s,q in profiles['segments'].items():
        hits=[fixed_sites.get((q['route_id'],tuple(round(v,10)for v in pt)),[])
              for pt in(q['start_mm'],q['end_mm'])]
        if not any(hits):continue
        points,normals,_,_=frame(rows[s]['metadata']['route_points_mm'])
        width=rows[s]['metadata']['minimum_caliper_mm'];values=[None,None]
        for i,support in enumerate(hits):
            if not support:continue
            normal=normals[0 if i==0 else-1];center=points[0 if i==0 else-1]
            values[i]=dict(normal=normal.tolist(),lower_mm=(center-normal*width/2).tolist(),
                           upper_mm=(center+normal*width/2).tolist())
            q.setdefault('endpoint_sides_mm',[None,None])[i]=[-width/2,width/2]
            records.append(dict(route_id=q['route_id'],source_id=s,endpoint_index=i,
                                fixed_continuation_source_ids=support,width_mm=width))
            if 'member_context'in q:
                station=q['member_source_start_mm']+q['member_source_direction']*(0. if i==0 else q['length_mm'])
                end=0 if abs(station)<1e-9 else 1 if abs(station-q['member_context']['length_mm'])<1e-9 else None
                if end is not None:
                    for other in profiles['segments'].values():
                        if other.get('maximal_member_id')!=q['maximal_member_id']:continue
                        context=dict(other['member_context']);sides=list(context.get('endpoint_sides_mm',[None,None]))
                        sides[end]=[-width/2,width/2];context['endpoint_sides_mm']=sides;other['member_context']=context
        sections[s]=values
    profiles['fixed_continuation_joints']=dict(schema='t04-fixed-native-continuations/1',records=records,geometry_searches=0)
    return sections


def straight_fields(record,source_width,*,maximum_side_slope=.25):
    """Full-domain C1 side fields; never taper inside a group constraint.

    Use the whole free interval for a change, rather than a short arbitrary
    collar. A field certificate proves smoothness and local interpolation
    bounds only. External corridor and cross-source join obligations remain.
    """
    from .smooth_transition import certify,restrict
    if record['axis'] is None:raise ValueError('STRAIGHT_SOURCE_PROFILE_REQUIRED')
    if 'member_context'in record:
        whole=straight_fields(record['member_context'],source_width,maximum_side_slope=maximum_side_slope)
        start=record['member_source_start_mm'];sign=record['member_source_direction']
        lo,hi=sorted((start,start+sign*record['length_mm']));pieces=[]
        for p in whole['pieces']:
            a,b=max(lo,p['first_mm']),min(hi,p['last_mm'])
            if b-a<=1e-12:continue
            c=[restrict(q,max(0.,(a-p['first_mm'])/p['length_mm']),min(1.,(b-p['first_mm'])/p['length_mm']))for q in p['controls']]
            if sign<0:c=[[-v for v in q[::-1]]for q in c[::-1]]
            first,last=sorted((sign*(a-start),sign*(b-start)))
            pieces.append(dict(p,first_mm=first,last_mm=last,length_mm=last-first,controls=c,
                               endpoint_derivatives=None,restriction_of_maximal_member=True))
        pieces.sort(key=lambda p:p['first_mm'])
        return dict(whole,pieces=pieces,maximal_member_id=record['maximal_member_id'],
                    source_seam_restarts_transition=False)
    length=record['length_mm'];windows=[];conflicts=[]
    for q in sorted(record['constraints'],key=lambda q:(q['first_mm'],q['last_mm'])):
        lo,hi=max(0.,q['first_mm']),min(length,q['last_mm'])
        if hi<=lo:continue
        shift=q['profile_midline_shift_mm'];half=q['width_mm']/2
        sides=[shift-half,shift+half]
        if windows and lo<=windows[-1]['last_mm']+1e-12:
            if max(abs(a-b)for a,b in zip(sides,windows[-1]['sides']))<1e-12:
                windows[-1]['last_mm']=max(hi,windows[-1]['last_mm']);continue
            if lo<windows[-1]['last_mm']-1e-12:
                conflicts.append('OVERLAPPING_GROUP_SIDE_FIELDS_DISAGREE')
        windows.append(dict(first_mm=lo,last_mm=hi,sides=sides))
    inherited=record.get('inherited_width_mm') or source_width
    end_widths=record.get('endpoint_widths_mm',[inherited,inherited])
    first_endpoint=[-end_widths[0]/2,end_widths[0]/2]
    last_endpoint=[-end_widths[1]/2,end_widths[1]/2];pieces=[]
    if windows and record.get('inherit_sided_endpoints'):
        first_endpoint=windows[0]['sides'];last_endpoint=windows[-1]['sides']
    explicit=record.get('endpoint_sides_mm',[None,None])
    if explicit[0]is not None:first_endpoint=explicit[0]
    if explicit[1]is not None:last_endpoint=explicit[1]
    def add(lo,hi,first,last,kind):
        if hi-lo<=1e-12:
            if max(abs(a-b)for a,b in zip(first,last))>1e-12:conflicts.append('NO_ROOM_FOR_SMOOTH_SIDE_TRANSITION')
            return
        proof=certify(first,last,hi-lo,maximum_side_slope=maximum_side_slope)
        conflicts.extend(proof['failures'])
        pieces.append(dict(first_mm=lo,last_mm=hi,kind=kind,**proof))
    if not windows:
        add(0.,length/2,first_endpoint,[-inherited/2,inherited/2],'INHERITED')
        add(length/2,length,[-inherited/2,inherited/2],last_endpoint,'INHERITED')
    else:
        if windows[0]['first_mm']>1e-12:
            add(0.,windows[0]['first_mm'],first_endpoint,windows[0]['sides'],'FREE_SPAN_TRANSITION')
        for i,q in enumerate(windows):
            if i:add(windows[i-1]['last_mm'],q['first_mm'],windows[i-1]['sides'],q['sides'],'FREE_SPAN_TRANSITION')
            add(q['first_mm'],q['last_mm'],q['sides'],q['sides'],'OWN_PARALLEL_GROUP')
        if length-windows[-1]['last_mm']>1e-12:
            add(windows[-1]['last_mm'],length,windows[-1]['sides'],last_endpoint,'FREE_SPAN_TRANSITION')
    # At a real source end a group may supply the endpoint itself. That join
    # must share this value with its next source; do not silently force zero.
    return dict(schema='t04-smooth-source-fields/1',passed=not conflicts,failures=conflicts,
        pieces=pieces,body_count=1,source_segment_split=False,
        interpolation='CUBIC_ZERO_ENDPOINT_DERIVATIVES',maximum_side_slope=maximum_side_slope,
        inherited_width_mm=inherited,external_corridor_certified=False,cross_source_join_certified=False)


def straight_body(record, source_width, *, transition=.05):
    """Materialize certified smooth fields as one native-length body.

    ``transition`` is retained for caller ABI compatibility. All available free
    length is used; no fixed short collar is cut out of a longer source.
    """
    import numpy as np
    from shapely.geometry import Polygon
    from .smooth_transition import tessellate
    fields=straight_fields(record,source_width)
    if not fields['passed']:raise ProfileUnresolved(';'.join(fields['failures']))
    a=np.asarray(record.get('reference_start_mm',record['start_mm']));u=np.asarray(record['axis']);n=np.array([-u[1],u[0]])
    sides=[[],[]]
    for piece in fields['pieces']:
        for side,c in enumerate(piece['controls']):
            for t,v in tessellate(c,piece['length_mm']):
                point=(a+u*(piece['first_mm']+t)+n*v).tolist()
                if not sides[side] or point!=sides[side][-1]:sides[side].append(point)
    return Polygon(sides[0]+sides[1][::-1])
