"""Smooth two-sided residual ribbons inheriting exact frozen cross sections.

This is a default-case proposal materializer, not a clearance certificate. The
existing native residual verifier must accept it before it becomes copper.
"""
import math
from bisect import bisect_left
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from .smooth_transition import controls,value,certify


def sections(record,fields):
    a=np.asarray(record['reference_start_mm']);u=np.asarray(record['axis']);n=np.array([-u[1],u[0]])
    result=[]
    for t,piece,k in ((0.,fields['pieces'][0],0),(record['length_mm'],fields['pieces'][-1],-1)):
        center=a+u*t
        result.append(dict(normal=n.tolist(),lower_mm=(center+n*piece['controls'][0][k]).tolist(),
                           upper_mm=(center+n*piece['controls'][1][k]).tolist()))
    return result


def frame(points,*,extra_stations=()):
    """Sample the unchanged native path and its existing offset normals."""
    p=np.asarray(points,dtype=float);diff=np.diff(p,axis=0);lengths=np.linalg.norm(diff,axis=1)
    if len(p)<2 or np.any(lengths<=0):raise ValueError('NONDEGENERATE_NATIVE_PROFILE_PATH_REQUIRED')
    native_stations=np.r_[0.,np.cumsum(lengths)];length=float(native_stations[-1])
    u=diff/lengths[:,None];normal=np.column_stack((-u[:,1],u[:,0]));native_normals=[normal[0]]
    for a,b in zip(normal,normal[1:]):
        den=1+float(a@b)
        if den<=1e-12:raise ValueError('RESIDUAL_REVERSAL_JOIN_UNSUPPORTED')
        n=(a+b)/den
        if np.linalg.norm(n)>4:raise ValueError('RESIDUAL_MITER_OUTLIER')
        native_normals.append(n)
    native_normals.append(normal[-1]);native_normals=np.asarray(native_normals)
    extras=[length/2,*np.linspace(0.,length,max(2,math.ceil(length/.01)+1))]
    extras.extend(extra_stations)
    extra=[]
    for t in extras:
        i=int(np.searchsorted(native_stations,t))
        if min((abs(t-native_stations[j])for j in(i-1,i)if 0<=j<len(native_stations)),default=float('inf'))>1e-12:extra.append(t)
    combined=list(native_stations)
    for t in sorted(extra):
        i=bisect_left(combined,t)
        if min((abs(t-combined[j])for j in(i-1,i)if 0<=j<len(combined)),default=float('inf'))>1e-12:combined.insert(i,t)
    stations=np.asarray(combined);p=np.column_stack([np.interp(stations,native_stations,p[:,i])for i in(0,1)])
    # Subdivision samples the original offset rails. Recomputing a miter on
    # every new sample creates backward inner edges near a native corner.
    normals=np.column_stack([np.interp(stations,native_stations,native_normals[:,i])for i in(0,1)])
    return p,normals,stations,length


def build(points,width,target_width,*,ends=(None,None),maximum_side_slope=.25,interior_width=None,plateau=None,maximum_extra_reach_mm=.11):
    p,normals,stations,length=frame(points,extra_stations=()if plateau is None else(plateau['first_mm'],plateau['last_mm']))
    desired=max(0.,((target_width if interior_width is None else interior_width)-width)/2)
    faces=[];oriented=[]
    for i,end in enumerate(ends):
        if end is None:faces.append(None);oriented.append(None);continue
        native=normals[0 if i==0 else -1];n=np.asarray(end['normal']);same=float(native@n)>=0
        normals[0 if i==0 else -1]=n if same else -n
        lower=np.asarray(end['lower_mm']if same else end['upper_mm']);upper=np.asarray(end['upper_mm']if same else end['lower_mm'])
        center=p[0 if i==0 else -1];n=normals[0 if i==0 else -1]
        low=float((lower-center)@n);high=float((upper-center)@n)
        if low>1e-9 or high<-1e-9:raise ValueError('FROZEN_END_SECTION_LOST_SOURCE_CENTERLINE')
        faces.append([max(0.,-low-width/2),max(0.,high-width/2)])
        oriented.append((lower,upper))
    if faces[0]is None:faces[0]=list(faces[1])if faces[1]is not None else[desired,desired]
    if faces[1]is None:faces[1]=list(faces[0])
    inherited=np.mean(faces,axis=0);total=float(inherited.sum())
    desired_faces=[float(2*desired*v/total) for v in inherited]if total>0 else[desired,desired]
    delta=maximum_side_slope*length/3;middle=[];bounds=[]
    for side,(a,b)in enumerate(zip(*faces)):
        lo=max(0.,max(a,b)-delta);hi=min(a,b)+delta
        if lo>hi+1e-12:raise ValueError('FROZEN_JOINT_TRANSITION_TOO_SHORT')
        middle.append(min(hi,max(lo,desired_faces[side])));bounds.append(lo)
    cap=max(0.,target_width-width)
    if sum(faces[0])>cap+1e-9 or sum(faces[1])>cap+1e-9:raise ValueError('FROZEN_JOINT_EXCEEDS_SOURCE_WIDTH_CAP')
    excess=max(0.,sum(middle)-cap)
    for i in sorted(range(2),key=lambda i:-(middle[i]-bounds[i])):
        take=min(excess,middle[i]-bounds[i]);middle[i]-=take;excess-=take
    if excess>1e-12:raise ValueError('FROZEN_JOINT_WIDTH_BUDGET_INFEASIBLE')
    if plateau is None:
        intervals=[(0.,length/2,faces[0],middle),(length/2,length,middle,faces[1])]
    else:
        middle=[plateau['negative_growth_mm'],plateau['positive_growth_mm']]
        if min(middle)<0 or sum(middle)>cap+1e-9:raise ValueError('ARC_CORE_WIDTH_CAP_CHANGED')
        first,last=plateau['first_mm'],plateau['last_mm']
        if not 0<first<last<length:raise ValueError('ARC_CORE_WITH_TWO_JOINTS_REQUIRED')
        intervals=[(0.,first,faces[0],middle),(first,last,middle,middle),(last,length,middle,faces[1])]
    proofs=[certify(a,b,hi-lo,maximum_side_slope=maximum_side_slope)for lo,hi,a,b in intervals]
    if not all(q['passed']for q in proofs):raise ValueError('RESIDUAL_SIDE_FIELD_SLOPE_CHANGED')
    offsets=[]
    for t in stations:
        side=next((i for i,(lo,hi,a,b)in enumerate(intervals)if t<=hi+1e-12),len(intervals)-1)
        lo,hi,_,_=intervals[side];fraction=(t-lo)/(hi-lo)
        offsets.append([value(c,min(1.,max(0.,fraction)))for c in proofs[side]['controls']])
    offsets=np.asarray(offsets);lower=p-normals*(width/2+offsets[:,0])[:,None];upper=p+normals*(width/2+offsets[:,1])[:,None]
    for i,end in enumerate(oriented):
        if end is not None:lower[0 if i==0 else -1],upper[0 if i==0 else -1]=end
    reach=max(float(np.linalg.norm(side-p,axis=1).max())for side in(lower,upper))-width/2
    if reach>maximum_extra_reach_mm+1e-12:raise ValueError('RESIDUAL_TRANSITION_REACH_OUTLIER')
    body=Polygon(lower.tolist()+upper[::-1].tolist())
    method='SIMPLE_TWO_RAIL_POLYGON'
    if not body.is_valid:
        # A short, tight source bend can have a collapsed inner rail. Its
        # swept cross sections still define finite material, just as the
        # existing cell-based side profile does. Materialize those cells;
        # never repair a constructed group or pretend this proves clearance.
        # Each hull lies in the convex sweep of two adjacent cross sections.
        cells=[Polygon([lower[i],lower[i+1],upper[i+1],upper[i]]).convex_hull
               for i in range(len(p)-1)]
        body=unary_union([g for g in cells if g.area>0])
        method='DEFAULT_SWEEP_CELL_UNION; CLEARANCE_VERIFICATION_REQUIRED'
    if body.is_empty or not body.is_valid or body.geom_type not in('Polygon','MultiPolygon'):
        raise ValueError('RESIDUAL_RIBBON_NOT_SIMPLE')
    endpoint_sections=[dict(normal=normals[i].tolist(),lower_mm=lower[i].tolist(),upper_mm=upper[i].tolist())for i in(0,-1)]
    actual=max(width+sum(v)for v in[faces[0],middle,faces[1]])
    return body,dict(schema='t04-inherited-sided-ribbon/1',materialization=method,endpoint_sections=endpoint_sections,
        endpoint_faces_mm=faces,midpoint_faces_mm=middle,side_field_proofs=proofs,
        maximum_width_mm=actual,target_width_mm=target_width,length_mm=length,
        maximum_extra_reach_mm=reach,transition_extra_reach_limit_mm=maximum_extra_reach_mm,
        exact_frozen_sections_retained=True,source_path_changed=False,clearance_certified=False)
