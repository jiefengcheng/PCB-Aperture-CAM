"""Bounded axis-aligned rectangle growth with a caller's joint-scene predicate."""
import math
from shapely.affinity import scale
from shapely.geometry import box


def fit_joint_rectangle(core, feasible, *, max_factor=1.25, steps=36):
    if (not core.is_valid or core.is_empty or not core.equals(box(*core.bounds))
            or not math.isfinite(max_factor) or not 1<=max_factor<=1.25
            or type(steps) is not int or not 1<=steps<=64):
        raise ValueError('BOUNDED_AXIS_ALIGNED_RECTANGLE_REQUIRED')
    center=core.centroid
    def shape(sx,sy):return core if sx==sy==1 else scale(core,sx,sy,origin=center)
    def valid(sx,sy):
        candidate=shape(sx,sy)
        return candidate.covers(core) and bool(feasible(candidate))
    if not valid(1.,1.):raise ValueError('INVALID_KEEP_PREDECESSOR')
    def axis(fixed,index):
        lo,hi=1.,max_factor
        if valid(max_factor,fixed) if index==0 else valid(fixed,max_factor):return max_factor
        for _ in range(steps):
            mid=(lo+hi)/2
            if valid(mid,fixed) if index==0 else valid(fixed,mid):lo=mid
            else:hi=mid
        return lo
    choices=[(1.,1.)]
    for first in (0,1):
        sx=sy=1.
        for _ in range(2):
            if first==0:sx=axis(sy,0);sy=axis(sx,1)
            else:sy=axis(sx,1);sx=axis(sy,0)
        if valid(sx,sy):choices.append((sx,sy))
    factors=max(choices,key=lambda p:(p[0]*p[1],sum(p),p))
    return shape(*factors),factors
