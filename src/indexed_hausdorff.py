"""Complete discrete boundary-vertex Hausdorff, indexed by target segments.

Every ring/line/point vertex is retained. No densification, simplification or
geometry repair. Queries use installed GEOS native point/segment distances.
A result at the acceptance boundary falls back to the original native metric.
"""
import math
import numpy as np
from shapely import STRtree,get_coordinates,linestrings,points,box,hausdorff_distance


def _paths(g):
    if g.geom_type=='Polygon':
        yield np.asarray(g.exterior.coords)
        for r in g.interiors:yield np.asarray(r.coords)
    elif g.geom_type in('LineString','LinearRing','Point'):yield np.asarray(g.coords)
    elif g.geom_type in('MultiPolygon','MultiLineString','MultiPoint','GeometryCollection'):
        for part in g.geoms:yield from _paths(part)
    else:raise ValueError('UNSUPPORTED_HAUSDORFF_GEOMETRY')


def _directed(source,target,*,budget_bytes,batch):
    paths=list(_paths(target));segments=sum(max(0,len(a)-1)for a in paths);singletons=sum(len(a)==1 for a in paths)
    charged=(segments+singletons)*256+sum(a.nbytes for a in paths)+batch*256
    if charged>budget_bytes:raise ValueError('HAUSDORFF_INDEX_BUDGET_EXCEEDED')
    edges=[np.stack((a[:-1],a[1:]),axis=1)for a in paths if len(a)>1]
    geom=[]
    if edges:geom.append(linestrings(np.concatenate(edges)))
    pts=[a for a in paths if len(a)==1]
    if pts:geom.append(points(np.concatenate(pts)))
    if not geom:raise ValueError('EMPTY_HAUSDORFF_TARGET')
    tree=STRtree(np.concatenate(geom));coords=get_coordinates(source)
    if not np.isfinite(coords).all():raise ValueError('NONFINITE_HAUSDORFF_COORDINATE')
    segment_xy=np.concatenate(edges)if edges else np.empty((0,2,2))
    if pts:
        pxy=np.concatenate(pts);segment_xy=np.concatenate([segment_xy,np.stack([pxy,pxy],axis=1)])
    # Reserve worst-case query pairs (two int64 arrays) and work in small
    # projection chunks. This remains bounded even for overlapping AABBs.
    available=budget_bytes-charged-coords.nbytes
    if available<max(1,len(segment_xy))*32:raise ValueError('HAUSDORFF_QUERY_BUDGET_EXCEEDED')
    query_batch=max(1,min(batch,available//(max(1,len(segment_xy))*32)))
    magnitude=max(1.,*(abs(v)for v in (*source.bounds,*target.bounds)))
    guard=float(max(1e-12,256*np.finfo(float).eps*magnitude))
    maximum=0.;queries=0;candidate_pairs=0
    for i in range(0,len(coords),query_batch):
        xy=coords[i:i+query_batch];indices,near=tree.query_nearest(points(xy),all_matches=False,return_distance=True)
        if len(near)!=len(xy)or not np.isfinite(near).all():raise ValueError('INCOMPLETE_HAUSDORFF_VERTEX_COVERAGE')
        radius=near+guard;pairs=tree.query(box(xy[:,0]-radius,xy[:,1]-radius,xy[:,0]+radius,xy[:,1]+radius));candidate_pairs+=pairs.shape[1]
        minimum=np.full(len(xy),np.inf)
        for j in range(0,pairs.shape[1],4096):
            own,other=pairs[:,j:j+4096];p=xy[own];ab=segment_xy[other];a=ab[:,0];delta=ab[:,1]-a
            # Native three-vertex probe [query,a,b] contains the complete
            # target segment [a,b]. Its symmetric native Hausdorff is exactly
            # the query-to-segment DistanceToPoint used by the original metric:
            # reverse distance and both endpoint distances are zero.
            probe=linestrings(np.stack([p,ab[:,0],ab[:,1]],axis=1))
            native=hausdorff_distance(probe,tree.geometries[other]);np.minimum.at(minimum,own,native)

        if not np.isfinite(minimum).all():raise ValueError('INCOMPLETE_HAUSDORFF_NEAREST_SEGMENT_COVERAGE')
        maximum=max(maximum,float(np.max(minimum)));queries+=len(minimum)

    return maximum,dict(vertices=queries,target_segments=segments,target_points=singletons,charged_index_bytes=charged,batch_vertices=query_batch,nearest_candidate_pairs=candidate_pairs)


def distance(a,b,*,tolerance=None,budget_bytes=256*1024**2,batch=8192):
    if type(budget_bytes)is not int or budget_bytes<=0 or type(batch)is not int or not 1<=batch<=65536:raise ValueError('HAUSDORFF_RESOURCE_BOUNDS_INVALID')
    if a.is_empty or b.is_empty or not a.is_valid or not b.is_valid:raise ValueError('HAUSDORFF_GEOMETRY_INVALID')
    first,pa=_directed(a,b,budget_bytes=budget_bytes,batch=batch);second,pb=_directed(b,a,budget_bytes=budget_bytes,batch=batch);result=max(first,second)
    magnitude=max(1.,*(abs(x)for x in (*a.bounds,*b.bounds)));guard=float(max(1e-12,256*np.finfo(float).eps*magnitude));fallback=False
    if tolerance is not None and abs(result-tolerance)<=guard and len(get_coordinates(a))+len(get_coordinates(b))<=2048:
        result=a.hausdorff_distance(b);fallback=True
    if not math.isfinite(result):raise ValueError('HAUSDORFF_METRIC_NONFINITE')
    return result,dict(method='All vertices; spatial candidate index; exact native GEOS three-vertex point/segment Hausdorff probes; symmetric maximum',forward=pa,reverse=pb,native_boundary_fallback=fallback,roundoff_fallback_guard_mm=guard,tolerance_unchanged=True)
