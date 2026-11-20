"""Optional bounded 10% local tube profile with original cores retained exactly."""
import math
import numpy as np
from shapely.geometry import LineString,Point,Polygon
from shapely.ops import unary_union
from .limiting_math import MARGIN


def local_targets(paths,rows,targets,allocation,tolerance=.10):
    owner={s:r for r,ss in paths.items() for s in ss}
    widths={r:rows[ss[0]]['metadata']['minimum_caliper_mm'] for r,ss in paths.items()}
    upper={r:min(allocation['source_caps_radial_mm'][r],targets[r]+tolerance*(widths[r]+2*targets[r])/2) for r in paths}
    parts={s:upper[r] for s,r in owner.items()}
    for c in allocation['constraints']:
        if c['kind']!='neighbor':continue
        a,b=c['a'],c['b'];sid=c['segment']
        if sid not in parts:continue
        remaining=c['budget_mm']-(upper[b] if b is not None else 0.)
        parts[sid]=min(parts[sid],max(targets[a],remaining))
    for c in allocation['source_witnesses']:
        budget=max(0.,c['gap_mm']-.0401-2*MARGIN)
        for aa,bb in ((c['a'],c['b']),(c['b'],c['a'])):
            for sid in aa:
                if sid not in parts:continue
                r=owner[sid];other=max((upper[owner[t]] for t in bb if t in owner and owner[t]!=r),default=0.)
                parts[sid]=min(parts[sid],max(targets[r],budget-other))
    endpoints={}
    for sid,r in owner.items():
        pts=rows[sid]['metadata']['route_points_mm']
        for pt in (pts[0],pts[-1]):endpoints.setdefault((r,tuple(pt)),[]).append(sid)
    result={}
    for sid,r in owner.items():
        pts=rows[sid]['metadata']['route_points_mm'];g=parts[sid]
        ends=[min(parts[s] for s in endpoints[r,tuple(pt)]) for pt in (pts[0],pts[-1])]
        result[sid]=dict(radial_mm=g,start_radial_mm=ends[0],end_radial_mm=ends[1],route_floor_radial_mm=targets[r],route_upper_radial_mm=upper[r],tolerance=tolerance,transition_length_mm=.05)
    return result


def profile_part(original,points,width,profile,progress,envelope):
    floor=profile['route_floor_radial_mm']*progress;high=profile['radial_mm']*progress
    if high<=0:return original
    if high-floor<1e-14:return original.buffer(high+(MARGIN if envelope else 0.),quad_segs=128)
    path=LineString(points);length=path.length;transition=profile['transition_length_mm']
    if length<=0:return original
    g0=profile['start_radial_mm']*progress;g1=profile['end_radial_mm']*progress
    def delta(t):
        def smooth(v):
            v=min(1.,max(0.,v));return v*v*(3-2*v)
        return min(high,g0+(high-g0)*smooth(t/transition),g1+(high-g1)*smooth((length-t)/transition))
    # Mask tessellation never substitutes for original source geometry. Its
    # intersection can only remove optional growth from an exact upper offset.
    stations=sorted({0.,length,min(length,transition),max(0.,length-transition),*[i*length/math.ceil(length/.01) for i in range(math.ceil(length/.01)+1)]})
    coords=[np.array(path.interpolate(t).coords[0]) for t in stations];radii=[width/2+delta(t) for t in stations];pieces=[]
    for pt,r in ((coords[0],radii[0]),(coords[-1],radii[-1])):pieces.append(Point(pt).buffer(r,quad_segs=128))
    for a,b,ra,rb in zip(coords,coords[1:],radii,radii[1:]):
        diff=b-a;norm=np.linalg.norm(diff)
        if norm==0:continue
        n=np.array([-diff[1],diff[0]])/norm
        pieces.append(Polygon([a+n*ra,b+n*rb,b-n*rb,a-n*ra]))
    ceiling=original.buffer(high,quad_segs=128);base=original if floor<=0 else original.buffer(floor,quad_segs=128)
    shape=unary_union([original,base,ceiling.intersection(unary_union(pieces))])
    if not shape.covers(original) or not shape.is_valid:raise ValueError('LOCAL_PROFILE_SOURCE_CORE_CHANGED')
    if shape.difference(ceiling).area>1e-12:raise ValueError('LOCAL_PROFILE_UPPER_CAP_CHANGED')
    return shape.buffer(MARGIN,quad_segs=128) if envelope else shape
