"""Deterministic parallel polyline offsets with explicit miter join semantics.

All member centerlines derive from one reference; tangent/offset equality holds
analytically on every segment, with common miter vertices, not sampled stations.
"""
import math
from shapely.geometry import LineString


def points(value):
 if type(value) is not list or len(value)<2 or any(type(p) is not list or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in value):raise ValueError('FINITE_POLYLINE_REQUIRED')
 if any(a==b for a,b in zip(value,value[1:])) or not LineString(value).is_simple:raise ValueError('SIMPLE_NONDEGENERATE_POLYLINE_REQUIRED')
 return [list(p) for p in value]

def parallel_points(reference,offset,*,miter_limit=4.):
 p=points(reference)
 if type(offset) not in (int,float) or not math.isfinite(offset):raise ValueError('FINITE_OFFSET_REQUIRED')
 normals=[]
 for a,b in zip(p,p[1:]):
  dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy);normals.append((-dy/length,dx/length))
 result=[]
 for i,(x,y) in enumerate(p):
  if i==0:nx,ny=normals[0]
  elif i==len(p)-1:nx,ny=normals[-1]
  else:
   a,b=normals[i-1],normals[i];denom=1+a[0]*b[0]+a[1]*b[1]
   if denom<=1e-12:raise ValueError('REVERSAL_JOIN_UNSUPPORTED')
   nx,ny=(a[0]+b[0])/denom,(a[1]+b[1])/denom
   if math.hypot(nx,ny)>miter_limit:raise ValueError('MITER_LIMIT_EXCEEDED')
  result.append([x+offset*nx,y+offset*ny])
 for a,b,c,d in zip(p,p[1:],result,result[1:]):
  dx,dy=b[0]-a[0],b[1]-a[1];ux,uy=d[0]-c[0],d[1]-c[1]
  if dx*ux+dy*uy<=0 or abs(dx*uy-dy*ux)>1e-10*max(1.,math.hypot(dx,dy)*math.hypot(ux,uy)):raise ValueError('OFFSET_TANGENT_OR_ORDER_INVALID')
 if not LineString(result).is_simple:raise ValueError('OFFSET_SELF_INTERSECTION')
 return result

def displaced_reference(reference,start,end,vector,distance):
 p=points(reference)
 if type(start) is not int or type(end) is not int or not 2<=start<=end<=len(p)-3:raise ValueError('FIXED_ENDPOINT_TANGENTS_REQUIRED')
 result=[list(x) for x in p]
 for i in range(start,end+1):result[i]=[p[i][0]+vector[0]*distance,p[i][1]+vector[1]*distance]
 points(result);return result

def extension_distance(reference,initial,expanded):
 p=points(reference);a,b=initial;i,j=expanded
 if i>a or j<b:raise ValueError('PATCH_EXTENSION_MUST_CONTAIN_INITIAL')
 return sum(math.dist(p[k],p[k+1]) for k in range(i,a))+sum(math.dist(p[k],p[k+1]) for k in range(b,j))


def route_copper(path,width,*,quad_segs=128):
    from shapely.ops import unary_union
    p=points(path)
    if type(width) not in (int,float) or not math.isfinite(width) or width<=0:raise ValueError('POSITIVE_FIXED_WIDTH_REQUIRED')
    return unary_union([LineString([a,b]).buffer(width/2,quad_segs=quad_segs) for a,b in zip(p,p[1:])])
