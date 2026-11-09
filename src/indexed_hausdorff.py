"""Complete discrete boundary-vertex Hausdorff, indexed by target segments.

Every ring/line/point vertex is retained. No densification, simplification or
geometry repair. Queries use installed GEOS native point/segment distances.
A result at the acceptance boundary falls back to the original native metric.
"""
import math
import numpy as np
from shapely import STRtree,get_coordinates,linestrings,points,box,hausdorff_distance,get_num_coordinates,to_wkb


def _paths(g):
    if g.geom_type=='Polygon':
        yield np.asarray(g.exterior.coords)
        for r in g.interiors:yield np.asarray(r.coords)
    elif g.geom_type in('LineString','LinearRing','Point'):yield np.asarray(g.coords)
    elif g.geom_type in('MultiPolygon','MultiLineString','MultiPoint','GeometryCollection'):
        for part in g.geoms:yield from _paths(part)
    else:raise ValueError('UNSUPPORTED_HAUSDORFF_GEOMETRY')


def _directed(source,target,*,budget_bytes,batch,shard_queries=False):
    paths=list(_paths(target));segments=sum(max(0,len(a)-1)for a in paths);singletons=sum(len(a)==1 for a in paths)
    charged=(segments+singletons)*256+sum(a.nbytes for a in paths)+batch*256
    if charged>budget_bytes:raise ValueError('HAUSDORFF_INDEX_BUDGET_EXCEEDED')
    edges=[np.stack((a[:-1],a[1:]),axis=1)for a in paths if len(a)>1]
    geom=[]
    if edges:geom.append(linestrings(np.concatenate(edges)))
    pts=[a for a in paths if len(a)==1]
    if pts:geom.append(points(np.concatenate(pts)))
    if not geom:raise ValueError('EMPTY_HAUSDORFF_TARGET')
    geometries=np.concatenate(geom);coords=get_coordinates(source)
    if not np.isfinite(coords).all():raise ValueError('NONFINITE_HAUSDORFF_COORDINATE')
    segment_xy=np.concatenate(edges)if edges else np.empty((0,2,2))
    if pts:
        pxy=np.concatenate(pts);segment_xy=np.concatenate([segment_xy,np.stack([pxy,pxy],axis=1)])
    # Reserve worst-case query pairs (two int64 arrays) and work in small
    # projection chunks. This remains bounded even for overlapping AABBs.
    available=budget_bytes-charged-coords.nbytes
    count=len(segment_xy)
    if available>=count*32:
        trees=[(0,STRtree(geometries))]
        shard_size=count
    else:
        if not shard_queries:raise ValueError('HAUSDORFF_QUERY_BUDGET_EXCEEDED')
        # Splitting the target does not change the nearest distance. Reserve
        # separate index headers and keep only one shard's query pairs live.
        for shards in (2,4,8,16,32,64):
            headers=4096*shards
            shard_size=(count+shards-1)//shards
            if available>=headers+shard_size*32:break
        else:raise ValueError('HAUSDORFF_QUERY_BUDGET_EXCEEDED')
        available-=headers
        charged+=headers
        trees=[(i,STRtree(geometries[i:i+shard_size])) for i in range(0,count,shard_size)]
    query_batch=max(1,min(batch,available//(shard_size*32)))
    magnitude=max(1.,*(abs(v)for v in (*source.bounds,*target.bounds)))
    guard=float(max(1e-12,256*np.finfo(float).eps*magnitude))
    maximum=0.;queries=0;candidate_pairs=0
    for i in range(0,len(coords),query_batch):
        xy=coords[i:i+query_batch];query_points=points(xy);near=np.full(len(xy),np.inf)
        for _,tree in trees:
            indices,distances=tree.query_nearest(query_points,all_matches=False,return_distance=True)
            if len(distances)!=len(xy)or not np.isfinite(distances).all():raise ValueError('INCOMPLETE_HAUSDORFF_VERTEX_COVERAGE')
            np.minimum.at(near,indices[0],distances)
        radius=near+guard
        boxes=box(xy[:,0]-radius,xy[:,1]-radius,xy[:,0]+radius,xy[:,1]+radius)
        minimum=np.full(len(xy),np.inf)
        for offset,tree in trees:
            pairs=tree.query(boxes)
            candidate_pairs+=pairs.shape[1]
            for j in range(0,pairs.shape[1],4096):
                own,other=pairs[:,j:j+4096];p=xy[own];ab=segment_xy[other+offset]
                # The probe contains the complete target segment, so its
                # native Hausdorff is the query-to-segment distance.
                probe=linestrings(np.stack([p,ab[:,0],ab[:,1]],axis=1))
                native=hausdorff_distance(probe,tree.geometries[other]);np.minimum.at(minimum,own,native)
                del own,other
            del pairs

        if not np.isfinite(minimum).all():raise ValueError('INCOMPLETE_HAUSDORFF_NEAREST_SEGMENT_COVERAGE')
        maximum=max(maximum,float(np.max(minimum)));queries+=len(minimum)

    proof=dict(vertices=queries,target_segments=segments,target_points=singletons,charged_index_bytes=charged,batch_vertices=query_batch,nearest_candidate_pairs=candidate_pairs)
    if len(trees)>1:proof.update(target_index_shards=len(trees),maximum_shard_targets=shard_size)
    return maximum,proof


def distance(a,b,*,tolerance=None,budget_bytes=256*1024**2,batch=8192,shard_queries=False):
    if type(budget_bytes)is not int or budget_bytes<=0 or type(batch)is not int or not 1<=batch<=65536:raise ValueError('HAUSDORFF_RESOURCE_BOUNDS_INVALID')
    if a.is_empty or b.is_empty or not a.is_valid or not b.is_valid:raise ValueError('HAUSDORFF_GEOMETRY_INVALID')
    # Exact complete native bytes prove zero distance without a segment index.
    # Charge a conservative bound before allocating either byte string; the
    # existing index/query path and its budget still apply to every difference.
    if a.geom_type in ('Polygon','MultiPolygon') and b.geom_type in ('Polygon','MultiPolygon'):
        na,nb=int(get_num_coordinates(a)),int(get_num_coordinates(b))
        charged=(na+nb)*32+4096
        if na==nb and charged<=budget_bytes:
            one,two=to_wkb(a),to_wkb(b)
            if one==two:
                return 0.,dict(method='Exact complete native WKB identity',vertices=na+nb,
                               charged_identity_bytes=charged,budget_bytes=budget_bytes,
                               tolerance_unchanged=True,native_boundary_fallback=False)
    first,pa=_directed(a,b,budget_bytes=budget_bytes,batch=batch,shard_queries=shard_queries);second,pb=_directed(b,a,budget_bytes=budget_bytes,batch=batch,shard_queries=shard_queries);result=max(first,second)
    magnitude=max(1.,*(abs(x)for x in (*a.bounds,*b.bounds)));guard=float(max(1e-12,256*np.finfo(float).eps*magnitude));fallback=False
    if tolerance is not None and abs(result-tolerance)<=guard and len(get_coordinates(a))+len(get_coordinates(b))<=2048:
        result=a.hausdorff_distance(b);fallback=True
    if not math.isfinite(result):raise ValueError('HAUSDORFF_METRIC_NONFINITE')
    return result,dict(method='All vertices; spatial candidate index; exact native GEOS three-vertex point/segment Hausdorff probes; symmetric maximum',forward=pa,reverse=pb,native_boundary_fallback=fallback,roundoff_fallback_guard_mm=guard,tolerance_unchanged=True)
