"""Additive, source-joint corner fills from a larger face into a smaller one.

Constructed groups are immutable supports. Only the new joint copper is
clearance-verified. Native adjacency supplies the work list; one fixed scene
index is shared by all proposals. No group search or original-copper union.
"""
from collections import defaultdict
from time import perf_counter
import math
import numpy as np
from shapely import STRtree,to_wkb
from shapely.geometry import LineString,Polygon,Point
from shapely.ops import unary_union
from .ribbon_profile import frame
from .smooth_transition import controls,value,tessellate
from .finite_profile_union import polygonal
from .limiting_math import GUARD,MARGIN
from .side_profile import extent
from .profile_refinement import clearance_barrier
from src.junction_spindle_blend import spindle_addition
from .arc_membership import tangent
from src.component_voids import holes,parts
from .normalized_additions import verify_patch
from src.native_inventory import ERROR_MM
from src.stage_abi.store import digest


def offsets(desc,t,endpoint,*,length_mm=None):
    fields=desc.get('fields')
    if fields:
        at=t if endpoint==0 else (LineString(desc['points']).length if length_mm is None else length_mm)-t
        piece=next((p for p in fields if at<=p['last_mm']+1e-12),fields[-1])
        u=min(1.,max(0.,(at-piece['first_mm'])/(piece['last_mm']-piece['first_mm'])))
        low,high=[value(c,u)for c in piece['controls']]
    else:low,high=desc['offsets_mm']
    return (low,high)if endpoint==0 else(-high,-low)


def oriented(desc,endpoint):
    return desc['points']if endpoint==0 else desc['points'][::-1]


def describe(rows,paths,straight_fields,frozen_straights,ribbons,arc_cores,*,supports=None):
    """Reuse recorded fields, retaining maximal-arc true-end identities."""
    result={}
    for s in sorted({s for ss in paths.values()for s in ss}):
        md=rows[s]['metadata'];w=md['minimum_caliper_mm']
        if md.get('aperture_family',['C'])[0]!='C':continue
        d=dict(points=md['route_points_mm'],source_width_mm=w,offsets_mm=[-w/2,w/2],route_kind=md.get('route_kind'))
        if s in arc_cores and arc_cores[s].get('complete_member'):
            v=arc_cores[s];interval=v['source_interval_mm'];sign=interval['direction']
            d['points']=v['member_points_mm']if sign==1 else v['member_points_mm'][::-1]
            a,b=(v['negative_growth_mm'],v['positive_growth_mm'])if sign==1 else(v['positive_growth_mm'],v['negative_growth_mm'])
            d['offsets_mm']=[-w/2-a,w/2+b];d['member_id']=v['member_id']
            stations=[interval['first_mm'],interval['last_mm']]
            if sign==-1:stations.reverse()
            d['real_endpoints']=[abs(t)<1e-10 or abs(t-v['member_length_mm'])<1e-10 for t in stations]
        elif s in frozen_straights:d['fields']=straight_fields[s]['pieces']
        elif s in ribbons:
            fields=[];first=0.
            for proof in ribbons[s]['side_field_proofs']:
                length=proof['length_mm'];negative,positive=proof['controls']
                fields.append(dict(first_mm=first,last_mm=first+length,
                                   controls=[[-w/2-v for v in negative],[w/2+v for v in positive]]));first+=length
            d['fields']=fields
        if supports is not None and s in supports:d['support']=supports[s]
        result[s]=d
    return result


def joint_frame(desc,points,*,extra_stations=()):
    """Stabilize only densely plotted native arcs at their true ends.

    A rounded plotting-end chord is not the arc's tangent. The durable arc
    catalogue already supplies an interior quadratic derivative. Blend that
    direction into the unchanged interior frame; never refit source points,
    sparse polylines, or straight corners.
    """
    if not desc.get('stabilize_joint_frame')or len(points)<8:return frame(points,extra_stations=extra_stations)
    length=LineString(points).length;span=min(.02,length*.1)
    pts,n,stations,_=frame(points,extra_stations=[span,length-span,*extra_stations])
    for end in (0,1):
        u=tangent(points,bool(end));normal=np.array([-u[1],u[0]])*(1 if end==0 else-1)
        distance=stations if end==0 else length-stations
        interior=n[int(np.argmin(abs(distance-span)))].copy();interior/=np.linalg.norm(interior)
        for i in np.flatnonzero(distance<span):
            a=value(controls(0.,1.),min(1.,max(0.,float(distance[i]/span))))
            v=(1-a)*normal+a*interior;n[i]=v/np.linalg.norm(v)
    return pts,n,stations,length


def corners(desc,endpoint,*,skin=True):
    pts,n,_,_=joint_frame(desc,oriented(desc,endpoint));low,high=offsets(desc,0.,endpoint)
    values=[pts[0]+n[0]*low,pts[0]+n[0]*high]
    if skin and 'support'in desc:
        # Anchor inside the actual frozen skin, with the same 20 nm overlap
        # used by source assembly. This is a boundary read, not a group audit.
        u=pts[1]-pts[0];u/=np.linalg.norm(u);p=pts[0]+u*min(2*ERROR_MM,np.linalg.norm(pts[1]-pts[0])/4)
        unit=n[0]/np.linalg.norm(n[0]);section=extent(desc['support'],p,unit,max(abs(low),abs(high))+.11)
        if section is not None:values=[p-unit*section[1],p+unit*section[0]]
    return values,n[0]


def propose(receiver,endpoint,donor_corner,side,length,*,maximum_reach_mm=.11,maximum_slope=.25,donor_backing=None):
    path=LineString(oriented(receiver,endpoint))
    if not math.isfinite(length)or not 0<length<=path.length+1e-12:raise ValueError('VALID_CORNER_TRANSITION_LENGTH_REQUIRED')
    corner,n=corners(receiver,endpoint);delta=np.asarray(donor_corner)-corner[side]
    outward=n*(-1 if side==0 else 1)
    if float(delta@outward)<=ERROR_MM:raise ValueError('NO_LARGER_EXPOSED_CORNER')
    reach=float(np.linalg.norm(delta));slope=1.5*reach/length
    if slope>maximum_slope+1e-12:raise ValueError('CORNER_TRANSITION_TOO_SHORT')
    cs=[controls(float(v),0.)for v in delta]
    extra=sorted({t for c in cs for t,_ in tessellate(c,length)})
    # A taper endpoint is not a new source vertex. Retain the full native
    # member's normals, including the interpolated normal at the cutoff.
    pts,normals,stations,_=joint_frame(receiver,list(path.coords),extra_stations=[length,*extra])
    keep=stations<=length+1e-12
    pts,normals,stations=pts[keep],normals[keep],stations[keep]
    # Reuse the exact forward GEOS length for reversed varying fields. A
    # constant section needs no path construction at any sampled station.
    source_length=LineString(receiver['points']).length if endpoint==1 and receiver.get('fields')else None
    base=np.array([point+normal*offsets(receiver,float(t),endpoint,length_mm=source_length)[side]for point,normal,t in zip(pts,normals,stations)])
    unit=normals/np.linalg.norm(normals,axis=1)[:,None]
    if 'support'in receiver:
        for i,(point,normal)in enumerate(zip(pts,unit)):
            section=extent(receiver['support'],point,normal,receiver['source_width_mm']/2+maximum_reach_mm)
            if section is not None:base[i]=point+normal*(-section[1]if side==0 else section[0])
    tangent=np.column_stack((unit[:,1],-unit[:,0]))
    donor=np.asarray(donor_corner)-pts[0]
    dn=float(donor@unit[0]);dt=float(donor@tangent[0])
    alpha=np.array([value(controls(1.,0.),min(1.,max(0.,float(t/length))))for t in stations])
    # Transport the larger endpoint section through the native moving frame.
    # A convex blend of endpoint and local face vectors cannot create a bulb
    # beyond both input sections, unlike a fixed world-space correction.
    transported=unit*dn+tangent*dt
    expanded=pts+(base-pts)*(1-alpha[:,None])+transported*alpha[:,None]
    bump=expanded-base
    # A common convex control field points outwards along every native normal.
    # This is a source-frame construction precondition, not a contour audit.
    signs=normals*(-1 if side==0 else 1)
    if min(float(sign@delta)for sign in signs)<-ERROR_MM:raise ValueError('CORNER_FIELD_TURNS_INWARD')
    source_half=receiver['source_width_mm']/2
    bound=max(float(np.linalg.norm(b-p))for b,p in zip(expanded,pts))-source_half
    if bound>maximum_reach_mm+1e-12:raise ValueError('CORNER_TRANSITION_REACH_OUTLIER')
    envelope_radius=max(max(float(np.linalg.norm(b-p))for b,p in zip(base,pts)),float(np.linalg.norm(np.asarray(donor_corner)-pts[0])))
    # Measure the joined endpoint envelope against the source path, rather
    # than pairing a translated curved face with one arbitrary station.
    corridor=path.buffer(envelope_radius+ERROR_MM,quad_segs=128)
    if not corridor.covers(LineString(expanded)):
        raise ValueError('CORNER_FIELD_EXCEEDS_INPUT_ENVELOPE')
    # Reuse the side-profile half-cell construction. Extending the support
    # to the source centerline prevents a nominal offset rail from closing
    # a tiny notch while leaving an enclosed sliver below that rail. Existing
    # copper is subtracted before verification, so this is still additive.
    backing=pts[0]+tangent[0]*min(0.,dt)if donor_backing is None else np.asarray(donor_backing)
    shape=Polygon([backing.tolist(),*pts.tolist(),*expanded[::-1].tolist()])
    if not shape.is_valid:
        shape=unary_union([Polygon([backing,pts[0],expanded[0]]).convex_hull,*[Polygon([pts[i],pts[i+1],expanded[i+1],expanded[i]]).convex_hull for i in range(len(base)-1)]])
    shape=polygonal(shape)
    if shape.is_empty or not shape.is_valid:raise ValueError('CORNER_TRANSITION_NOT_FINITE')
    return shape,dict(schema='t04-larger-corner-transition/1',side=side,length_mm=length,
        start_corner_mm=np.asarray(donor_corner).tolist(),end_correction_mm=[0.,0.],
        initial_correction_controls_mm=cs,blend_controls=[1.,1.,0.,0.],blend_endpoint_derivatives=[0.,0.],
        field_policy='CONVEX_ENDPOINT_SECTION_TRANSPORT_IN_NATIVE_FRAME',
        support_backing_mm=backing.tolist(),
        frozen_skin_sampled='support'in receiver,assembly_overlap_mm=2*ERROR_MM if 'support'in receiver else 0.,
        maximum_correction_mm=float(np.linalg.norm(bump,axis=1).max()),endpoint_step_slope_mm_per_mm=slope,
        endpoint_step_slope_limit_mm_per_mm=maximum_slope,
        input_face_envelope_radius_mm=envelope_radius,
        extra_reach_bound_mm=bound,extra_reach_limit_mm=maximum_reach_mm,
        source_path_changed=False,group_copper_changed=False,geometry_audit=False,
        width_scope='EXISTING_JOINED_ENDPOINT_ENVELOPE; SEGMENT_INTERIOR_CAPS_UNCHANGED')


def skin_fill(support,path,window,face_radius,*,radius=.05,maximum_depth=.005):
    """Existing rolling-disc shoulder constructor, restricted to a joint skin.

    Equal endpoint sections do not imply that the plotted shoulders meet.
    This additive mask treats the two shoulders together, including a notch
    displaced slightly from the native endpoint. It never erodes a support.
    """
    addition=spindle_addition(support,radius,window)
    if support.interiors:
        addition=addition.difference(unary_union([Polygon(r)for r in support.interiors]))
    corridor=path.buffer(face_radius+ERROR_MM,quad_segs=128)
    return polygonal(addition.intersection(corridor).intersection(support.buffer(maximum_depth,quad_segs=128)))


def new_pocket_regions(before,after):
    """Reuse the void kernel for pockets enclosed by new joint copper only."""
    new=polygonal(unary_union(holes(after)).difference(unary_union(holes(before))))
    return [g for g in parts(new)if g.area>ERROR_MM**2]


def joined_cap_envelope(descriptors,ends,radius):
    """Bind a joint's recorded radius to both adjacent native paths.

    The radius is unchanged. The receiving source is only the storage owner
    of a joint addition, not its complete geometric input domain.
    """
    return unary_union([LineString(descriptors[s]['points']).buffer(radius+ERROR_MM,quad_segs=128)for s,_ in ends])


def reject_enclosing_additions(before,patches):
    """Reject whole joint proposals that enclose an unfillable new pocket.

    No mask acts on the frozen floor. Other joint sites and pre-existing voids
    remain intact. If withdrawing those proposals does not resolve every new
    enclosure, keep the failed evidence and let the existing gate fail.
    """
    site=lambda p:tuple(p['endpoint_mm'])
    kept=list(patches);withdrawn=[];rejected_sites=set();rounds=[]
    candidate=polygonal(unary_union([before,*[p['geometry']for p in kept]]))
    pockets=new_pocket_regions(before,candidate)
    while pockets and kept:
        sites={site(p)for p in kept if any(p['geometry'].distance(h)<=ERROR_MM for h in pockets)}
        rejected=[p for p in kept if site(p)in sites]
        reason='WITHDRAW_ENCLOSING_JOINT_SITES'
        if not rejected:
            # An unlocalized enclosure cannot authorize any remaining batch
            # member. Restore the exact floor rather than accepting a hole or
            # enlarging its cap. The separate connection gate still applies.
            rejected=list(kept);sites={site(p)for p in kept}
            reason='WITHDRAW_REMAINING_ROUTE_JOINT_BATCH; ENCLOSURE_NOT_LOCALIZED'
        rounds.append(dict(pocket_areas_mm2=[h.area for h in pockets],rejected_endpoints_mm=[list(s)for s in sorted(sites)],reason=reason))
        withdrawn.extend(rejected);rejected_sites.update(sites)
        kept=[p for p in kept if site(p)not in sites]
        # Removing one overlapping proposal can uncover another enclosure.
        # Every round withdraws at least one whole proposal, so this terminates.
        candidate=polygonal(unary_union([before,*[p['geometry']for p in kept]]))if kept else before
        pockets=new_pocket_regions(before,candidate)
    passed=bool(withdrawn)and not pockets
    receipt=dict(passed=passed,rejected_endpoints_mm=[list(s)for s in sorted(rejected_sites)],
        withdrawn_patch_sha256=[digest(to_wkb(p['geometry']))for p in withdrawn],
        rounds=rounds,floor_sha256=digest(to_wkb(before)),candidate_sha256=digest(to_wkb(candidate)),
        floor_changed=False,constructed_groups_audited=0)
    return (kept if passed else patches),receipt


def run(rows,paths,material,owner,descriptors,*,covered=(),protected_domains=(),maximum_reach_mm=.11):
    started=perf_counter();covered=set(covered);ids=sorted(s for s,g in material.items()if not g.is_empty)
    tree=STRtree([material[s]for s in ids]);nodes=defaultdict(list);patches=[];reports=[]
    for route,sources in sorted(paths.items()):
        for s in sources:
            if s not in descriptors:continue
            points=rows[s]['metadata']['route_points_mm']
            for end,pt in enumerate((points[0],points[-1])):
                if descriptors[s].get('real_endpoints',[True,True])[end]:nodes[route,tuple(round(v,10)for v in pt)].append((s,end))
    for (route,pt),ends in sorted(nodes.items()):
        if len(ends)!=2:continue
        (a,ae),(b,be)=ends
        if descriptors[a].get('member_id')is not None and descriptors[a].get('member_id')==descriptors[b].get('member_id'):continue
        for target,end,donor,de in((a,ae,b,be),(b,be,a,ae)):
            if target in covered:continue
            receive=descriptors[target];other=descriptors[donor]
            if receive.get('route_kind')==other.get('route_kind')=='arc':
                # Arc-to-arc endpoint chords carry plotting noise. Reuse the
                # catalogue tangent for this joint field, never for a group
                # contour or a straight/default interface.
                receive=dict(receive,stabilize_joint_frame=True)
                other=dict(other,stabilize_joint_frame=True)
            small,n=corners(receive,end);large,_=corners(other,de)
            declared_small,_=corners(receive,end,skin=False);declared_large,_=corners(other,de,skin=False)
            donor_points=np.asarray(oriented(other,de));du=donor_points[1]-donor_points[0];du/=np.linalg.norm(du)
            donor_backing=donor_points[0]+du*2*ERROR_MM
            available=LineString(receive['points']).length
            for side,sign in((0,-1),(1,1)):
                outward=n*sign;big=max(large,key=lambda p:float(p@outward));difference=float((big-small[side])@outward)
                if max(float((v-declared_small[side])@outward)for v in declared_large)<=ERROR_MM and difference<=10*ERROR_MM:continue
                if difference<=ERROR_MM:continue
                # Only reserve half a face when its opposite true end also
                # needs an incoming taper. The group search length is not a
                # lower bound on a joint's taper span.
                other_end=1-end;other_small,other_n=corners(receive,other_end)
                physical_side=1-side;competing=False
                other_pt=tuple(round(v,10)for v in rows[target]['metadata']['route_points_mm'][other_end])
                if receive.get('real_endpoints',[True,True])[other_end]:
                    for neighbor,ne in nodes.get((route,other_pt),[]):
                        if neighbor==target:continue
                        neighbor_corners,_=corners(descriptors[neighbor],ne,skin=False)
                        direction=other_n*(-1 if physical_side==0 else 1)
                        competing=any(float((v-other_small[physical_side])@direction)>ERROR_MM for v in neighbor_corners)
                span=available/2 if competing else available
                required=max(2*ERROR_MM,1.5*float(np.linalg.norm(big-small[side]))/.25)
                lengths=[span]
                while lengths[-1]/2>required:lengths.append(lengths[-1]/2)
                lengths=sorted(set([*lengths,required]),reverse=True)
                # Prefer the established gentle field. A corner may use a
                # shorter C1 blend, up to a 1:1 local side slope, when crowded.
                # This is independent of the 25% consecutive-width parameter;
                # the unchanged 0.11 mm reach and input-face caps still bind.
                trials=[(v,.25)for v in lengths]
                tight=max(2*ERROR_MM,1.5*float(np.linalg.norm(big-small[side])))
                v=min(span,required)
                while v/2>tight:
                    v/=2;trials.append((v,1.))
                trials.append((tight,1.))
                record=dict(route_id=route,endpoint_mm=list(pt),source_id=target,donor_source_id=donor,side=side,attempts=[],status='KEEP_UNRESOLVED')
                limited=None
                for length,slope_limit in trials:
                    if length>span+1e-12:continue
                    try:shape,recipe=propose(receive,end,big,side,length,maximum_reach_mm=maximum_reach_mm,maximum_slope=slope_limit,donor_backing=donor_backing)
                    except ValueError as error:
                        record['attempts'].append(dict(length_mm=length,passed=False,reasons=[str(error)]));continue
                    window=shape.envelope.buffer(GUARD+2*MARGIN);near=sorted(map(int,tree.query(window)))
                    own=owner(target);same=[material[ids[i]].intersection(shape.envelope.buffer(ERROR_MM))for i in near if owner(ids[i])==own]
                    same.extend(p['geometry'].intersection(shape.envelope.buffer(ERROR_MM))for p in patches if p['owner']==own and p['geometry'].envelope.intersects(window))
                    support=unary_union(same)
                    addition=polygonal(shape.difference(support))
                    if addition.is_empty or addition.area<=1e-14:
                        record.update(status='ALREADY_COVERED',recipe=recipe);break
                    if any(addition.intersects(d)for d in protected_domains):
                        record['attempts'].append(dict(length_mm=length,passed=False,reasons=['PROTECTED_PIN_DOMAIN']));continue
                    fixed=[dict(id=ids[i],geometry=material[ids[i]])for i in near if owner(ids[i])!=own]
                    fixed.extend(dict(id='joint:'+str(i),geometry=p['geometry'])for i,p in enumerate(patches)if p['owner']!=own and p['geometry'].envelope.intersects(window))
                    check=verify_patch(addition,fixed)
                    record['attempts'].append(dict(length_mm=length,passed=check['passed'],failures=check['failures'],check=check))
                    if check['passed']:
                        # Keep the backed half-cell as the assembly operand.
                        # Verifying only its new copper avoids re-auditing the
                        # supports; retaining overlap prevents tangent-only
                        # joins from reopening after union/serialization.
                        patches.append(dict(source_id=target,route_id=route,owner=own,geometry=shape,recipe=recipe,endpoint_mm=list(pt),side=side))
                        record.update(status='FILLED',added_area_mm2=addition.area,patch_sha256=digest(to_wkb(shape)),positive_delta_sha256=digest(to_wkb(addition)),recipe=recipe);break
                    limited=shape,recipe,support,fixed
                if record['status']=='KEEP_UNRESOLVED'and limited is not None:
                    # Reuse the default-growth obstacle mask only for this
                    # new joint operand. The group's existing copper remains
                    # immutable, including source edges already inside the
                    # guard. Reserve the checking margin before verification.
                    shape,recipe,support,fixed=limited
                    barriers=[clearance_barrier(r['geometry'],GUARD+2*MARGIN)for r in fixed]
                    barriers.extend(protected_domains)
                    clipped=polygonal(shape.difference(unary_union(barriers)))
                    route_support=unary_union([receive.get('support',material.get(target,Polygon())),
                        other.get('support',material.get(donor,Polygon())),
                        *[p['geometry']for p in patches if p['route_id']==route and p['geometry'].envelope.intersects(shape.envelope)]])
                    backed=polygonal(unary_union([clipped,shape.intersection(route_support)]))
                    addition=polygonal(backed.difference(support))
                    if not addition.is_empty and addition.area>1e-14:
                        check=verify_patch(addition,fixed)
                        if check['passed']and not any(addition.intersects(d)for d in protected_domains):
                            recipe=dict(recipe,clearance_limited=True,unfilled_proposal_area_mm2=shape.difference(backed).area)
                            patches.append(dict(source_id=target,route_id=route,owner=own,geometry=backed,recipe=recipe,endpoint_mm=list(pt),side=side))
                            record.update(status='FILLED_TO_CLEARANCE_LIMIT',added_area_mm2=addition.area,patch_sha256=digest(to_wkb(backed)),positive_delta_sha256=digest(to_wkb(addition)),recipe=recipe,limited_check=check)
                reports.append(record)
    skin_reports=[];skin_started=perf_counter()
    for (route,pt),ends in sorted(nodes.items()):
        if len(ends)!=2 or any(s in covered for s,_ in ends):continue
        (a,ae),(b,be)=ends
        if descriptors[a].get('member_id')is not None and descriptors[a].get('member_id')==descriptors[b].get('member_id'):continue
        own=owner(a)
        if owner(b)!=own:raise ValueError('NATIVE_JOINT_OWNER_CHANGED')
        center=np.asarray(pt)
        # Reuse the catalogue's interior tangent. The final plotting chord can
        # be almost transverse to the real arc, clipping one shoulder out of
        # a window aligned to that chord (the remaining H2 teeth).
        ta=tangent(oriented(descriptors[a],ae),False);tb=tangent(oriented(descriptors[b],be),False)
        u=ta-tb
        if np.linalg.norm(u)<1e-12:u=ta
        u/=np.linalg.norm(u);n=np.array([-u[1],u[0]])
        faces=[v for s,e in ends for v in corners(descriptors[s],e)[0]]
        reach=max(float(np.linalg.norm(v-center))for v in faces)
        if reach>max(descriptors[s]['source_width_mm']/2 for s,_ in ends)+maximum_reach_mm:continue
        # Include the complete plotted end-cap footprint on both sides.
        # A fixed 15 um window can leave a second tooth where the noisy final
        # chord displaces the offset skin along the true arc tangent.
        shoulder=max(.015,reach);radius=.05;depth=.005
        window=Polygon([center+u*x+n*y for x,y in[(-shoulder,-reach-shoulder),(shoulder,-reach-shoulder),(shoulder,reach+shoulder),(-shoulder,reach+shoulder)]])
        prep=window.buffer(2*radius)
        near=sorted(map(int,tree.query(prep)))
        # A connected electrical owner can contain several native routes.
        # Its other branches are not supports for this route's joint: using
        # them can create additions attached only to a different route.
        same=[descriptors[s].get('support',material.get(s,Polygon())).intersection(prep)for s,_ in ends]
        same.extend(p['geometry'].intersection(prep)for p in patches if p['route_id']==route and p['geometry'].envelope.intersects(prep))
        support=polygonal(unary_union(same))
        record=dict(route_id=route,endpoint_mm=list(pt),source_ids=[a,b],status='NOT_NEEDED')
        if support.geom_type=='MultiPolygon':
            touching=[g for g in support.geoms if g.distance(Point(pt))<=ERROR_MM]
            if len(touching)==1:support=touching[0]
        if support.geom_type!='Polygon':
            record['status']='KEEP_DISCONNECTED_SUPPORT';skin_reports.append(record);continue
        path=unary_union([LineString(descriptors[s]['points'])for s,_ in ends])
        addition=skin_fill(support,path,window,reach,radius=radius,maximum_depth=depth)
        if addition.is_empty or addition.area<=1e-14:skin_reports.append(record);continue
        if addition.difference(support.buffer(ERROR_MM,quad_segs=128)).is_empty:
            skin_reports.append(record);continue
        fixed=[dict(id=ids[i],geometry=material[ids[i]])for i in near if owner(ids[i])!=own]
        fixed.extend(dict(id='joint:'+str(i),geometry=p['geometry'])for i,p in enumerate(patches)if p['owner']!=own and p['geometry'].envelope.intersects(prep))
        check=verify_patch(addition,fixed)
        limited=False
        if not check['passed']or any(addition.intersects(d)for d in protected_domains):
            barriers=[clearance_barrier(r['geometry'],GUARD+2*MARGIN)for r in fixed]+list(protected_domains)
            addition=polygonal(addition.difference(unary_union(barriers)));limited=True
            check=verify_patch(addition,fixed)
        if addition.is_empty or addition.area<=1e-14:
            record['status']='KEEP_CLEARANCE_LIMIT';skin_reports.append(record);continue
        if not check['passed']:raise ValueError('JOINT_SKIN_MASK_FAILED_CLEARANCE')
        # Keep a redundant supported overlap as an assembly operand, just as
        # for the larger-corner fields. The positive delta alone is checked.
        backed=polygonal(unary_union([addition,support.intersection(addition.buffer(2*ERROR_MM,quad_segs=128))]))
        recipe=dict(schema='t04-native-joint-skin-closure/1',radius_mm=radius,shoulder_mm=shoulder,maximum_depth_mm=depth,
                    input_face_envelope_radius_mm=reach,clearance_limited=limited,source_path_changed=False,
                    group_copper_changed=False,geometry_audit=False,assembly_overlap_mm=2*ERROR_MM,
                    width_scope='EXISTING_JOINED_ENDPOINT_ENVELOPE; SEGMENT_INTERIOR_CAPS_UNCHANGED')
        patches.append(dict(source_id=a,route_id=route,owner=own,geometry=backed,recipe=recipe,endpoint_mm=list(pt),side='JOINT_SKIN'))
        record.update(status='FILLED_TO_CLEARANCE_LIMIT'if limited else'FILLED',added_area_mm2=addition.area,check=check,recipe=recipe,
                      patch_sha256=digest(to_wkb(backed)),positive_delta_sha256=digest(to_wkb(addition)))
        skin_reports.append(record)
    skin_wall=perf_counter()-skin_started;pocket_started=perf_counter();pocket_reports=[]
    for route,sources in sorted(paths.items()):
        route_patches=[p for p in patches if p['route_id']==route]
        if not route_patches:continue
        before=polygonal(unary_union([descriptors[s].get('support',material.get(s,Polygon()))for s in sources if s in descriptors]))
        assembled=polygonal(unary_union([before,*[p['geometry']for p in route_patches]]))
        for hole in new_pocket_regions(before,assembled):
            adjacent=[p for p in route_patches if p['geometry'].distance(hole)<=ERROR_MM]
            record=dict(route_id=route,pocket_area_mm2=hole.area,pocket_sha256=digest(to_wkb(hole)),status='KEEP_UNRESOLVED')
            if not adjacent:pocket_reports.append(record);continue
            # Fill only inside an already admitted joint's source envelope.
            # Existing route holes were removed from the work list above.
            cap_inputs=[]
            for patch in adjacent:
                key=route,tuple(round(v,10)for v in patch['endpoint_mm'])
                ends=nodes.get(key,[(patch['source_id'],0)])
                cap_inputs.append(joined_cap_envelope(descriptors,ends,patch['recipe']['input_face_envelope_radius_mm']))
            caps=unary_union(cap_inputs)
            record.update(input_caps_sha256=digest(to_wkb(caps)),cap_scope='BOTH_ADJACENT_NATIVE_MEMBERS; INDIVIDUAL_RADII_UNCHANGED')
            if not hole.difference(caps).is_empty:
                record['reason']='JOINT_POCKET_OUTSIDE_INPUT_CAPS';pocket_reports.append(record);continue
            target=adjacent[0]['source_id'];own=owner(target)
            window=hole.envelope.buffer(GUARD+2*MARGIN);near=sorted(map(int,tree.query(window)))
            fixed=[dict(id=ids[i],geometry=material[ids[i]])for i in near if owner(ids[i])!=own]
            fixed.extend(dict(id='joint:'+str(i),geometry=p['geometry'])for i,p in enumerate(patches)if p['owner']!=own and p['geometry'].envelope.intersects(window))
            if any(hole.intersects(d)for d in protected_domains):
                record['reason']='PROTECTED_PIN_DOMAIN';pocket_reports.append(record);continue
            check=verify_patch(hole,fixed)
            if not check['passed']:
                record.update(reason='JOINT_POCKET_CLEARANCE',check=check);pocket_reports.append(record);continue
            backed=polygonal(unary_union([hole,assembled.intersection(hole.buffer(2*ERROR_MM,quad_segs=128))]))
            recipe=dict(schema='t04-new-joint-pocket-completion/1',input_face_envelope_radius_mm=max(p['recipe']['input_face_envelope_radius_mm']for p in adjacent),
                source_path_changed=False,group_copper_changed=False,geometry_audit=False,assembly_overlap_mm=2*ERROR_MM,
                source_void_policy='ONLY_NEW_JOINT_ENCLOSURES; PREEXISTING_ROUTE_HOLES_EXCLUDED',
                width_scope='EXISTING_JOINED_ENDPOINT_ENVELOPE; SEGMENT_INTERIOR_CAPS_UNCHANGED')
            patches.append(dict(source_id=target,route_id=route,owner=own,geometry=backed,recipe=recipe,endpoint_mm=adjacent[0]['endpoint_mm'],side='JOINT_POCKET'))
            record.update(status='FILLED',check=check,patch_sha256=digest(to_wkb(backed)),recipe=recipe);pocket_reports.append(record)
        # A failed pocket fill cannot leave its enclosing proposal published.
        # Withdraw only the implicated native joint sites, then evaluate the
        # same differential-pocket predicate again against the unchanged floor.
        if not any(r['route_id']==route and r['status']!='FILLED'for r in pocket_reports):continue
        route_patches=[p for p in patches if p['route_id']==route]
        kept,rejection=reject_enclosing_additions(before,route_patches)
        for record in pocket_reports:
            if record['route_id']==route and record['status']!='FILLED':record['rejection']=rejection
        if rejection['passed']:
            keep_ids={id(p)for p in kept}
            patches[:]=[p for p in patches if p['route_id']!=route or id(p)in keep_ids]
            sites={tuple(pt)for pt in rejection['rejected_endpoints_mm']}
            withdrawn=set(rejection['withdrawn_patch_sha256'])
            for record in reports+skin_reports:
                if record['route_id']==route and tuple(record['endpoint_mm'])in sites:
                    record.update(proposal_status_before_enclosure_rejection=record['status'],status='REJECTED_NEW_POCKET',final_added_area_mm2=0.)
            for record in pocket_reports:
                if record['route_id']==route and (record['status']!='FILLED'or record.get('patch_sha256')in withdrawn):
                    record.update(status='REJECTED_ENCLOSING_ADDITIONS',rejection=rejection)
    return patches,dict(schema='t04-native-joint-corner-fill/1',reports=reports,wall_s=perf_counter()-started,
        filled=sum(r['status']=='FILLED'for r in reports),already_covered=sum(r['status']=='ALREADY_COVERED'for r in reports),
        clearance_limited=sum(r['status']=='FILLED_TO_CLEARANCE_LIMIT'for r in reports),
        unresolved=sum(r['status']in('KEEP_UNRESOLVED','REJECTED_NEW_POCKET')for r in reports),constructed_groups_audited=0,
        skin_closure=dict(reports=skin_reports,wall_s=skin_wall,
            filled=sum(r['status']in('FILLED','FILLED_TO_CLEARANCE_LIMIT')for r in skin_reports)),
        pocket_completion=dict(reports=pocket_reports,wall_s=perf_counter()-pocket_started,
            filled=sum(r['status']=='FILLED'for r in pocket_reports),
            rejected_enclosures=sum(r['status']=='REJECTED_ENCLOSING_ADDITIONS'for r in pocket_reports),
            passed=all(r['status']in('FILLED','REJECTED_ENCLOSING_ADDITIONS')for r in pocket_reports)),
        group_shapes_changed=False,source_segments_split=False,scene_indexes_built=1)
