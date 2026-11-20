"""Complete conservative residual corridors compiled once from fixed operands.

No R-tree, GEOS distance, buffer or trial-shape verification is used here.
Project source boundary edges into a longitudinal slab and compare scalar
normal bounds. Future residual envelopes participate before any are admitted.
An inconclusive bound defers a proposal; it never waives a neighbour.
"""
import math
from time import perf_counter
import numpy as np
from shapely import get_coordinates,to_wkb
from .limiting_math import GUARD,MARGIN
from src.stage_abi.store import digest,canonical


def slab_interval(coordinates,axis,first,last):
    """Enclose polygon copper intersecting a closed longitudinal slab.

    Extrema occur at input vertices or boundary/slab intersections. Extra
    edges between flattened rings only enlarge the conservative enclosure.
    """
    xy=np.asarray(coordinates);u=np.asarray(axis);n=np.array([-u[1],u[0]])
    ts=xy@u;ns=xy@n;inside=(ts>=first)&(ts<=last);values=ns[inside]
    a,b=ts[:-1],ts[1:];na,nb=ns[:-1],ns[1:];delta=b-a
    for t in(first,last):
        hit=(np.minimum(a,b)<=t)&(np.maximum(a,b)>=t)&(abs(delta)>1e-15)
        if np.any(hit):values=np.r_[values,na[hit]+(t-a[hit])/delta[hit]*(nb[hit]-na[hit])]
    return None if len(values)==0 else(float(values.min()),float(values.max()))


class Corridors:
    def __init__(self,records,reservations=()):
        started=perf_counter();self.records=[];self.coordinates={};self.projections=0
        for key,owner,shape in sorted(records,key=lambda r:r[0]):
            if shape.is_empty:continue
            self.records.append((key,tuple(owner),shape,shape.bounds,digest(to_wkb(shape))))
        for key,owner,bounds in sorted(reservations,key=lambda r:r[0]):
            x0,y0,x1,y1=bounds
            coordinates=np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]])
            self.coordinates[key]=coordinates
            self.records.append((key,tuple(owner),None,bounds,digest(canonical(list(bounds)))))
        self.bounds=np.array([v[3]for v in self.records]).reshape((-1,4))
        self.binding=digest(canonical([[k,list(o),list(b),h]for k,o,g,b,h in self.records]))
        self.setup_wall_s=perf_counter()-started

    def certify(self,shape,axis,owner):
        started=perf_counter();u=np.asarray(axis,dtype=float);length=np.linalg.norm(u)
        if not math.isfinite(length)or length<=0:raise ValueError('RESIDUAL_CORRIDOR_AXIS_REQUIRED')
        u/=length;n=np.array([-u[1],u[0]]);xy=get_coordinates(shape)
        ts=xy@u;ns=xy@n;first,last=float(ts.min()),float(ts.max());low,high=float(ns.min()),float(ns.max())
        required=GUARD+2*MARGIN;x0,y0,x1,y1=shape.bounds;b=self.bounds
        hits=np.flatnonzero((b[:,0]<=x1+required)&(b[:,2]>=x0-required)&(b[:,1]<=y1+required)&(b[:,3]>=y0-required))
        witnesses=[];failures=[]
        for i in hits:
            key,other,g,bounds,sha=self.records[int(i)]
            if other==tuple(owner):continue
            if key not in self.coordinates:self.coordinates[key]=get_coordinates(g)
            interval=slab_interval(self.coordinates[key],u,first-required,last+required);self.projections+=1
            if interval is None:continue
            gap=max(interval[0]-high,low-interval[1]);passed=gap>=required
            witness=dict(source_id=key,geometry_sha256=sha,normal_interval_mm=list(interval),
                         normal_gap_lower_bound_mm=gap,required_gap_mm=required,passed=passed)
            witnesses.append(witness)
            if not passed:failures.append(key)
        return dict(schema='t04-residual-slab-corridor/1',passed=not failures,
            failure='RESIDUAL_CORRIDOR_NOT_PROVEN'if failures else None,unproven_neighbors=failures,
            axis=u.tolist(),longitudinal_interval_mm=[first,last],normal_interval_mm=[low,high],
            witnesses=witnesses,complete_operand_binding=self.binding,complete_obstacle_inventory=True,
            future_residual_envelopes_reserved=True,r_tree_queries=0,geometry_distance_calls=0,
            candidate_geometry_verifications=0,proof='POLYGON_SLAB_EXTREMA; SEPARATING_NORMAL_INTERVALS',
            constructed_groups_audited=0,wall_s=perf_counter()-started)
