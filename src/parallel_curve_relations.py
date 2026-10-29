"""Local source-curve neighbor proposals, never a clearance certificate."""
import math
from shapely.geometry import LineString


def parallel_curve_relation(a,b,*,min_shared_run_mm=.05,max_center_distance_mm=.5,
                            max_angle_degrees=1.,samples=49,allow_remote_intersections=False):
    curves=[LineString(a),LineString(b)]
    if any(not g.is_valid or g.length<=0 for g in curves):raise ValueError('INVALID_SOURCE_CURVE')
    if samples<3:raise ValueError('INSUFFICIENT_CURVE_SELECTION_SAMPLES')
    # Sampling the shorter curve avoids mistaking a long route's short local
    # coincidence for a relation over its entire length.
    reverse=curves[0].length>curves[1].length
    first,second=curves[::-1] if reverse else curves
    if (first.intersects(second) and not allow_remote_intersections) or first.length<min_shared_run_mm:return None
    def tangent(g,s):
        h=min(.002,g.length/4096)
        p,q=g.interpolate(max(0,s-h)),g.interpolate(min(g.length,s+h))
        dx,dy=q.x-p.x,q.y-p.y;n=math.hypot(dx,dy)
        return (dx/n,dy/n) if n else None
    limit=math.cos(math.radians(max_angle_degrees));runs=[];current=[]
    for i in range(samples):
        s=first.length*i/(samples-1);p=first.interpolate(s);t=second.project(p);q=second.interpolate(t)
        u,v=tangent(first,s),tangent(second,t);distance=p.distance(q)
        dot=abs(u[0]*v[0]+u[1]*v[1]) if u and v else 0
        sign=0 if not u else u[0]*(q.y-p.y)-u[1]*(q.x-p.x)
        transverse=(u and v and distance>0 and
            max(abs(u[0]*(q.x-p.x)+u[1]*(q.y-p.y)),abs(v[0]*(q.x-p.x)+v[1]*(q.y-p.y)))
            <=distance*math.sin(math.radians(max_angle_degrees))+1e-12)
        good=dot>=limit and 0<distance<=max_center_distance_mm and sign!=0 and transverse
        if good and current and sign*current[-1]['signed_side']<=0:good=False
        if good:current.append(dict(index=i,along_mm=s,p=[p.x,p.y],q=[q.x,q.y],signed_side=sign,
            distance_mm=distance,angle_degrees=math.degrees(math.acos(min(1.,dot)))))
        else:
            if current:runs.append(current)
            current=[]
    if current:runs.append(current)
    if not runs:return None
    run=max(runs,key=lambda r:r[-1]['along_mm']-r[0]['along_mm'])
    length=run[-1]['along_mm']-run[0]['along_mm']
    if length<min_shared_run_mm:return None
    middle=run[len(run)//2];cross=[middle['q'],middle['p']] if reverse else [middle['p'],middle['q']]
    return dict(shared_sampled_run_mm=length,matched_sample_count=len(run),total_selection_samples=samples,
        alignment_angle_degrees=max(r['angle_degrees'] for r in run),
        transverse_distances_mm=[min(r['distance_mm'] for r in run),max(r['distance_mm'] for r in run)],
        midpoint_cross_section_mm=cross,selection_only='Sampled source tangent/side consistency; no continuous clearance or width-growth verdict')
