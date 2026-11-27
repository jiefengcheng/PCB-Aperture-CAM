"""Source-rail clearance budgets before deterministic arc-core construction.

Any added point is in a declared source rail's radius-r buffer. Source-only
rail/core and rail/rail distances therefore certify clearance by the triangle
inequality. The pair-budget optimizer maximizes the sum of BOTH side growths.
No constructed contour is submitted to a clearance verifier.
"""
from time import perf_counter
import math
from shapely import STRtree,to_wkb
from shapely.geometry import LineString,Point
from shapely.ops import substring,unary_union
from shapely.errors import GEOSException
from .member_allocation import maximum_pair_packing
from .limiting_math import GUARD,MARGIN,SHARED_LENGTH
from . import pipeline as p


def retain_attached_skin(body, original):
    """Reject optional endpoint-buffer islands at their construction boundary.

    An independently buffered true-end point can be outside the plotted chord
    by more than a very small allocated growth. It then makes a separate disk,
    not a widening skin. Never remove a source face, even below the error
    bounds, and never silently discard a substantive disconnected proposal.
    This uses only this member's operands; no scene search or clearance pass.
    """
    from src.component_voids import parts
    from src.native_inventory import ERROR_MM
    faces=parts(body);attached=[g for g in faces if g.intersects(original)]
    pending=[g for g in faces if not g.intersects(original)]
    while pending:
        connected=[g for g in pending if any(g.intersects(a)for a in attached)]
        if not connected:break
        attached.extend(connected);ids={id(g)for g in connected}
        pending=[g for g in pending if id(g)not in ids]
    rejected=[dict(area_mm2=g.area,bounds_mm=list(g.bounds),wkb_hex=to_wkb(g).hex())for g in pending]
    passed=all(g.area<=p.EPS and max(g.bounds[2]-g.bounds[0],g.bounds[3]-g.bounds[1])<=ERROR_MM for g in pending)
    proof=dict(passed=passed,rejected_faces=len(pending),rejected=rejected,
        source_faces_removed=0,native_area_error_mm2=p.EPS,native_coordinate_error_mm=ERROR_MM,
        policy='SOURCE_ATTACHED_ARC_SKIN; REJECT_UNSUPPORTED_ENDPOINT_BUFFER_MICRO_FACES')
    if not passed:
        proof['reason']='UNATTACHED_ARC_SKIN_EXCEEDS_NATIVE_ERROR_BOUNDS'
        return None,proof
    return (unary_union(attached)if pending else body),proof


def prepare(rows,original,material,groups,used,owner,roles,settings,width_caps,*,protected_domains=(),complete_members=False,source_reservations=None):
    started=perf_counter();working=dict(material);claimed=set();models=[];cores={};deferred=[]
    reservations_source=material if source_reservations is None else source_reservations
    ordered=sorted(groups,key=lambda g:(-sum(m['length_mm']for m in g['members']),g['group_id']))
    for group in ordered:
        if not any(m['source_id']in used and m['source_id']not in claimed for m in group['members']):continue
        reservations=[(s,identity,g)for s in sorted(working)for identity,g in
            (reservations_source.reservation_rows(s,working[s])if hasattr(reservations_source,'reservation_rows')else[(s,working[s])])if not g.is_empty]
        ids=[s for s,_,_ in reservations];shapes=[g for _,_,g in reservations]
        tree=STRtree(shapes)
        members={};caps={};rails={};pairs=[];witnesses=[]
        for member in group['members']:
            s=member['source_id']
            if s not in used or s in claimed:continue
            md=rows[s]['metadata'];w=md['minimum_caliper_mm']
            if md['aperture_family'][0]!='C':continue
            cap=min(w*(settings.maximum_factor-1),settings.maximum_total_width_increase_mm,width_caps[s]-w)
            path=LineString(md['route_points_mm']);reserve=0. if complete_members else max(.05,1.5*cap/.25)
            if path.length-2*reserve<SHARED_LENGTH:continue
            line=substring(path,reserve,path.length-reserve)
            try:
                domain=line.buffer(w/2+cap+.11,cap_style=1 if complete_members else 2,quad_segs=128)
                if any(domain.envelope.intersects(d.envelope)for d in protected_domains):continue
                side=[path.offset_curve(sign*w/2,quad_segs=128,join_style=1).intersection(domain)for sign in(-1,1)]
            except GEOSException:continue
            if any(g.is_empty or g.geom_type not in('LineString','MultiLineString')for g in side):continue
            if complete_members:
                # These are the same true-end normals later registered as
                # frozen sections. Budget their source-cap points before
                # allocation; an offset polyline's final noisy chord alone
                # does not enclose a section on the native arc tangent.
                from .arc_membership import tangent
                points=md['route_points_mm'];ends=[]
                for end,center in ((False,points[0]),(True,points[-1])):
                    u=tangent(points,end)*( -1 if end else 1)
                    ends.append((center,(-float(u[1]),float(u[0]))))
                side=[unary_union([g,*[Point(c[0]+sign*n[0]*w/2,c[1]+sign*n[1]*w/2)
                                       for c,n in ends]]) for sign,g in zip((-1,1),side)]
            members[s]=dict(width_mm=w,cap_mm=max(0.,cap),length_mm=path.length,
                first_mm=reserve,last_mm=path.length-reserve,domain=domain,
                original_core=original[s].intersection(domain),source_ref=rows[s]['original_ref'],
                source_refs=rows[s].get('member_source_refs',[rows[s]['original_ref']]))
            for label,g in zip(('negative','positive'),side):
                key=s+'#'+label;rails[key]=g;caps[key]=max(0.,cap)
                for i in sorted(map(int,tree.query(g.envelope.buffer(cap+GUARD+2*MARGIN)))):
                    other=ids[i]
                    if other==s or other in roles or owner(other)==owner(s):continue
                    gap=g.distance(shapes[i]);budget=max(0.,gap-GUARD-2*MARGIN)
                    caps[key]=min(caps[key],budget)
                    witnesses.append(dict(face=key,foreign_source=other,source_gap_mm=gap,
                        maximum_growth_mm=budget,foreign_geometry_sha256=p.digest(to_wkb(shapes[i]))))
            pairs.append((s+'#negative',s+'#positive',max(0.,cap)))
        if not members:
            deferred.append(dict(group_id=group['group_id'],reason='NO_ADMITTED_SOURCE_RAIL_MEMBERS'));continue
        keys=sorted(rails)
        for i,a in enumerate(keys):
            sa=a.rsplit('#',1)[0]
            for b in keys[i+1:]:
                sb=b.rsplit('#',1)[0]
                if sa==sb or owner(sa)==owner(sb):continue
                gap=rails[a].distance(rails[b]);budget=max(0.,gap-GUARD-2*MARGIN)
                pairs.append((a,b,budget));witnesses.append(dict(first_face=a,second_face=b,source_gap_mm=gap,budget_mm=budget))
        allocation=maximum_pair_packing(caps,pairs)
        active=[]
        for s,m in members.items():
            growth=[allocation['growth_mm'][s+'#'+label]for label in('negative','positive')]
            if max(growth)<=0:continue
            pieces=[m['original_core']]+[rails[s+'#'+label].buffer(r,quad_segs=128)for label,r in zip(('negative','positive'),growth)if r>0]
            try:body=unary_union(pieces).intersection(m['domain'])
            except GEOSException as error:
                deferred.append(dict(group_id=group['group_id'],source_id=s,reason='ARC_CORE_REPRESENTATION_FAILED',error=str(error)));continue
            if body.is_empty or not body.is_valid or body.geom_type not in('Polygon','MultiPolygon'):
                deferred.append(dict(group_id=group['group_id'],source_id=s,reason='ARC_CORE_REPRESENTATION_INVALID'));continue
            cap_proof=None
            if complete_members:
                from .arc_end_skin import retain_native_end_planes
                body,cap_proof=retain_native_end_planes(body,m['original_core'],rows[s]['metadata']['route_points_mm'])
            body,attachment=retain_attached_skin(body,m['original_core'])
            if body is None:
                deferred.append(dict(group_id=group['group_id'],source_id=s,
                    reason='UNATTACHED_ARC_SKIN',attachment=attachment));continue
            cores[s]=dict(body=body,domain=m['domain'],first_mm=m['first_mm'],last_mm=m['last_mm'],
                          negative_growth_mm=growth[0],positive_growth_mm=growth[1],group_id=group['group_id'],
                          complete_member=complete_members,end_skin=cap_proof,source_attachment=attachment)
            claimed.add(s);active.append(s)
            working[s]=unary_union([working[s],body])
        models.append(dict(group_id=group['group_id'],active_sources=active,allocation=allocation,witnesses=witnesses,
            source_attachment={s:cores[s]['source_attachment']for s in active},
            source_members={s:{k:v for k,v in m.items()if k not in('domain','original_core')}for s,m in members.items()},
            rail_sha256={k:p.digest(to_wkb(g))for k,g in rails.items()},
            construction_guarantee='SOURCE_RAIL_BUFFER_ENCLOSURE_AND_PAIR_BUDGET_TRIANGLE_INEQUALITY',geometry_audit=False))
    return cores,dict(schema='t04-source-rail-arc-construction/1',models=models,deferred=deferred,
                       wall_s=perf_counter()-started,geometry_audit=False)


def prepare_maximal(rows,original,material,groups,used,owner,roles,settings,width_caps,*,protected_domains=()):
    """Use the existing rail constructor on whole native member chains.

    A virtual row is an explicit collection of real source refs, not a new
    source occurrence. Its single contour and side allocation are shared by
    all native occurrences. Internal seams never acquire a taper or reserve.
    No completed source-scene ABI is published by this bounded prototype.
    """
    virtual_rows=dict(rows);virtual_original=dict(original);working=dict(material)
    members={};virtual_caps={};projected=[];deferred=[]
    for group in groups:
        live=[]
        for m in group['members']:
            sources=m['source_ids'];mid=m['member_id']
            if not set(sources)&used:continue
            if not set(sources)<=used:
                deferred.append(dict(member_id=mid,reason='FIXED_OR_COVERED_OCCURRENCE_IN_MAXIMAL_ARC; DEFAULT_ONLY'));continue
            widths=[rows[s]['metadata']['minimum_caliper_mm']for s in sources]
            if max(widths)-min(widths)>1e-12:continue
            if any(rows[s]['metadata']['aperture_family'][0]!='C'for s in sources):continue
            # Source membership batches use JSON arrays; live channel scopes
            # use tuples. Preserve the complete ordered owner collection in
            # the equality key without depending on its container type.
            if len({tuple(owner(s))for s in sources})!=1:raise ValueError('MAXIMAL_ARC_SOURCE_OWNER_CHANGED')
            members[mid]=m;virtual_caps[mid]=min(width_caps[s]for s in sources)
            virtual_rows[mid]=dict(original_ref=rows[sources[0]]['original_ref'],
                member_source_refs=[dict(source_id=s,original_ref=rows[s]['original_ref'])for s in sources],
                metadata=dict(rows[sources[0]]['metadata'],route_points_mm=m['reference_points_mm']))
            virtual_original[mid]=unary_union([original[s]for s in sources]);working[mid]=virtual_original[mid]
            live.append(dict(source_id=mid,length_mm=m['length_mm']))
        if live:projected.append(dict(group_id=group['group_id'],members=live))
    def member_owner(k):return owner(members[k]['source_ids'][0])if k in members else owner(k)
    built,proof=prepare(virtual_rows,virtual_original,working,projected,set(members),member_owner,roles,
        settings,virtual_caps,protected_domains=protected_domains,complete_members=True,source_reservations=material)
    cores={}
    for mid,value in built.items():
        m=members[mid]
        for interval in m['source_intervals_mm']:
            s=interval['source_id']
            cores[s]=dict(value,member_id=mid,member_source_ids=m['source_ids'],
                          source_interval_mm=interval,member_points_mm=m['reference_points_mm'],
                          member_length_mm=m['length_mm'])
    proof.update(schema='t04-maximal-arc-rail-construction/1',member_deferrals=deferred,
                 complete_member_domains=True,native_source_seam_reserves=0,
                 source_projection='SHARED_MEMBER_CONTOUR; ALL_NATIVE_SOURCE_REFS_RETAINED',
                 source_scene_publication='NOT_QUALIFIED; BOUNDED_CONSTRUCTION_RECIPES_ONLY')
    return cores,proof
