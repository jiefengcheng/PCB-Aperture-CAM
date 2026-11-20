"""One scalar allocation per maximal parallel member, over unequal domains.

Compile source supports once. Local overlap is a pair constraint, never the
member's physical extent. Reuse the source framer and integer face allocator;
default/joint copper remains subject to the existing residual verification.
"""
import math
from time import perf_counter
from shapely import get_coordinates
from .group_boundaries import interior_intervals
from .group_profile import outline
from .member_allocation import maximum_faces
from .limiting_math import GUARD,MARGIN,SHARED_LENGTH


class MaximalGroups:
    def __init__(self,straight,membership,route_ids,settings,boundaries=None,*,mutable_sources=None):
        started=perf_counter();self.routes=set(route_ids);self.settings=settings;self.models=[];self.residual=[]
        active_sources=None if mutable_sources is None else set(mutable_sources)
        self.framing_wall_s=0.;runs=straight['runs']
        for group in membership['straight_groups']:
            if not any(m['route_id']in self.routes for m in group['members']):continue
            indices=sorted({i for m in group['members']for i in m['native_run_indices']})
            anchor=max(indices,key=lambda i:runs[i]['length_mm']);a,b=runs[anchor]['start'],runs[anchor]['end']
            length=math.dist(a,b);u=[(b[i]-a[i])/length for i in(0,1)];n=[-u[1],u[0]]
            exact=[]
            for i in indices:
                r=runs[i];drift=abs(sum((r['end'][j]-r['start'][j])*n[j]for j in(0,1)))
                if drift<=1e-9:exact.append(i)
                elif r['route_id']in self.routes:self.residual.append(dict(reason='APPROXIMATE_MEMBER_NEEDS_CATEGORY_CONSTRUCTION',run_id=r['run_id']))
            if len(exact)<2:continue
            lanes=[]
            for i in exact:
                r=runs[i];ts=sorted(sum(pt[j]*u[j]for j in(0,1))for pt in(r['start'],r['end']))
                normal=sum((r['start'][j]+r['end'][j])*n[j]/2 for j in(0,1));w=r['width_mm']
                requested=r['route_id']in self.routes
                mutable=requested and (active_sources is None or set(r['source_ids'])<=active_sources)
                if requested and active_sources is not None and set(r['source_ids'])&active_sources and not mutable:
                    self.residual.append(dict(reason='MIXED_COVERED_NATIVE_RUN_DEFAULT_ONLY; NO_MEMBER_FRAGMENTATION',run_id=r['run_id']))
                parts=[];framing=[];limits=dict(left=float('inf'),right=float('inf'))
                # The maximum permitted face excursion needs at most .18 mm
                # to meet a zero-growth endpoint at slope .25. This is a
                # derived joint reserve on a whole member, not fragmentation
                # at every relationship event.
                reserve=max(.05,1.5*settings.maximum_total_width_increase_mm/.25)
                first,last=ts[0]+reserve,ts[1]-reserve
                if mutable and last-first>=SHARED_LENGTH:
                    band=dict(axis=u,first=first,last=last,members=exact)
                    frame=boundaries.for_band(runs,band,settings)if boundaries is not None else None
                    unresolved=[]if frame is None else [x for x in frame['unresolved']if x['run_id']==r['run_id']]
                    free,_=interior_intervals(first,last,unresolved,transition=.05)
                    for lo,hi in free:
                        if hi-lo<SHARED_LENGTH:continue
                        f=boundaries.for_band(runs,dict(band,first=lo,last=hi),settings)if boundaries is not None else None
                        if f is not None and any(x['run_id']==r['run_id']for x in f['unresolved']):continue
                        face=f['face_caps'][r['run_id']]if f is not None else dict(left=.03,right=.03)
                        if min(face.values())<0:continue
                        parts.append([lo,hi]);framing.append(f)
                        for side in limits:limits[side]=min(limits[side],face[side])
                admitted=mutable and bool(parts)
                if not admitted and boundaries is not None:
                    points=[(float(pt[0]),float(pt[1]))for s in r['source_ids']for pt in get_coordinates(boundaries.current[s])]
                    ns=[sum(pt[j]*n[j]for j in(0,1))for pt in points]
                    longs=[sum(pt[j]*u[j]for j in(0,1))for pt in points]
                    normal=(max(ns)+min(ns))/2;w=max(w,max(ns)-min(ns));ts=[min(longs),max(longs)]
                lanes.append(dict(run_id=r['run_id'],route_id=r['route_id'],source_ids=r['source_ids'],
                    source_width_mm=w,source_normal_mm=normal,member_domain_mm=ts,
                    mutable=admitted,requested_mutable=mutable,intervals_mm=parts,source_framing=framing,face_caps_mm=limits))
            lanes.sort(key=lambda q:(q['source_normal_mm'],q['run_id']))
            # All longitudinally relevant pairs are constraints, including
            # short overlaps absent from the original .05 selection screen.
            pairs=[];bad=set()
            for i,low in enumerate(lanes):
                for high in lanes[i+1:]:
                    if not(low['mutable']or high['mutable']):continue
                    aa=low['intervals_mm']if low['mutable']else[low['member_domain_mm']]
                    bb=high['intervals_mm']if high['mutable']else[high['member_domain_mm']]
                    if not any(max(a[0]-b[1],b[0]-a[1])<=GUARD for a in aa for b in bb):continue
                    budget=high['source_normal_mm']-low['source_normal_mm']-(low['source_width_mm']+high['source_width_mm'])/2-GUARD-2*MARGIN
                    if budget<0:
                        bad.update(q['run_id']for q in(low,high)if q['mutable'])
                    else:pairs.append((low['run_id'],high['run_id'],budget))
            if bad:
                # Freeze only implicated lanes. A source overlap in a filled
                # area must not suppress unrelated members of the catalogue.
                # Retain all nonnegative pair constraints against frozen lanes.
                self.residual.append(dict(reason='NOMINAL_MEMBER_SUPPORT_BELOW_CONSTRUCTION_GAP',group_id=group['group_id'],members=sorted(bad)))
                for lane in lanes:
                    if lane['run_id']in bad:lane['mutable']=False
            if any(q['mutable']for q in lanes):self.models.append(dict(group_id=group['group_id'],axis=u,lanes=lanes,pairs=pairs))
        self.framing_wall_s=perf_counter()-started

    def plan(self,*,width_caps=None):
        started=perf_counter();groups=[];models=[]
        for model in self.models:
            caps={};faces={}
            for lane in model['lanes']:
                r=lane['run_id'];w=lane['source_width_mm']
                cap=min(w*self.settings.maximum_factor,w+self.settings.maximum_total_width_increase_mm)
                if width_caps is not None:cap=min(cap,width_caps.get(r,cap))
                caps[r]=max(0.,cap-w)if lane['mutable']else 0.
                faces[r]={s:min(caps[r],lane['face_caps_mm'][s])if lane['mutable']else 0. for s in('left','right')}
            allocation=maximum_faces(list(caps),caps,model['pairs'],face_caps=faces)
            models.append(dict(group_id=model['group_id'],allocation=allocation,
                               member_domains={q['run_id']:q['member_domain_mm']for q in model['lanes']}))
            for lane in model['lanes']:
                if not lane['mutable']:continue
                growth=allocation['face_growth_mm'][lane['run_id']];w=lane['source_width_mm'];n=lane['source_normal_mm']
                left=n-w/2-growth['left'];right=n+w/2+growth['right']
                for index,(first,last)in enumerate(lane['intervals_mm']):
                    value=dict(lane,left_mm=left,right_mm=right,width_mm=w+sum(growth.values()),
                               face_growth_mm=growth,profile_midline_shift_mm=(growth['right']-growth['left'])/2,
                               vertices_mm=outline(model['axis'],first,last,left,right))
                    groups.append(dict(status='CONSTRUCTED_INTERIOR',axis=model['axis'],first_mm=first,last_mm=last,
                        lanes=[value],catalogue_band_index=f"{model['group_id']}:{lane['run_id']}:{index}",
                        maximal_group_id=model['group_id'],member_domain_mm=lane['member_domain_mm'],
                        construction_clearance_mm=GUARD+2*MARGIN,geometry_audit=False,
                        source_edge_policy='NEW_IDEAL_STRAIGHT_BOUNDARIES',source_boundary_constraints=dict(
                            editable_bulk_source_ids=sorted({s for f in lane['source_framing']if f for s in f['editable_bulk_source_ids']}),
                            complete_source_bounds=True),allocation_model_index=len(models)-1))
        return dict(schema='t04-maximal-member-group-plan/1',reference_policy='SOURCE_ANCHORED',
            status='MAXIMAL_MEMBER_CONSTRUCTION; JOINT_ASSEMBLY_PENDING',requested_routes=sorted(self.routes),
            groups=groups,residual_groups=self.residual,member_allocation_models=models,
            planning_wall_s=perf_counter()-started,source_framing_wall_s=self.framing_wall_s,
            width_deviation=dict(value=.25,scope='CONSECUTIVE_SEGMENTS_ONLY',route_wide=False),
            geometry_audit=False,native_final_audit='NOT_RUN_BY_DESIGN',publication_ready=False,
            full_board_run=False,replay=False,export=False,pending=['SMOOTH_JOINTS','DEFAULT_CASE_VERIFICATION','ASSEMBLY_CUSTODY'])
