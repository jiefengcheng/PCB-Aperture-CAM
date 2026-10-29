"""Bounded geometric proposals for immediate parallel membership, read-only.

Direction/overlap parameters select relationships; they never establish copper
clearance. The caller checks the actual finite-width strip and full routes.
"""
import math


def parallel_relation(a, b, *, max_angle_degrees=1., min_shared_length_mm=.25,
                      max_transverse_distance_mm=.5):
    def vector(points):
        x0,y0=points[0];x1,y1=points[1]
        length=math.hypot(x1-x0,y1-y0)
        if not math.isfinite(length) or length==0:
            raise ValueError('INVALID_SOURCE_SEGMENT')
        u=((x1-x0)/length,(y1-y0)/length)
        if u[0]<0 or (u[0]==0 and u[1]<0):u=(-u[0],-u[1])
        return u
    ua,ub=vector(a),vector(b)
    dot=lambda p,u:p[0]*u[0]+p[1]*u[1]
    alignment=dot(ua,ub)
    if alignment<0:
        ub=(-ub[0],-ub[1]);alignment=-alignment
    if alignment < math.cos(math.radians(max_angle_degrees)):
        return None
    ta=sorted(dot(p,ua) for p in a);tb=sorted(dot(p,ua) for p in b)
    lo,hi=max(ta[0],tb[0]),min(ta[1],tb[1])
    if hi-lo < min_shared_length_mm:return None
    def at(points,u,t):
        scale=(t-dot(points[0],ua))/dot(u,ua)
        return [points[0][j]+scale*u[j] for j in (0,1)]
    pairs=[(at(a,ua,t),at(b,ub,t)) for t in (lo,(lo+hi)/2,hi)]
    distances=[math.dist(p,q) for p,q in pairs]
    if max(distances)>max_transverse_distance_mm or min(distances)==0:return None
    return dict(shared_projected_length_mm=hi-lo,
                alignment_angle_degrees=math.degrees(math.acos(min(1.,max(-1.,alignment)))),
                transverse_distances_mm=distances,
                midpoint_cross_section_mm=list(pairs[1]),
                selection_only='No clearance or width-growth verdict')


def relation_groups(member_ids, edges):
    adjacent={sid:set() for sid in member_ids}
    for a,b in edges:
        if a==b or a not in adjacent or b not in adjacent:raise ValueError('INVALID_MEMBER_RELATION')
        adjacent[a].add(b);adjacent[b].add(a)
    unseen=set(member_ids);groups=[]
    while unseen:
        todo=[min(unseen)];seen=set()
        while todo:
            sid=todo.pop()
            if sid in seen:continue
            seen.add(sid);todo.extend(sorted(adjacent[sid]-seen,reverse=True))
        unseen-=seen;groups.append(sorted(seen))
    return sorted(groups)
