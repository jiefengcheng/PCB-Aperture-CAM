"""Once-compiled fixed operands and source-rail budgets for residual chains.

Distances concern source rails, before allocation. Future chains share their
pair budgets through the established face optimizer, not hypothetical AABBs.
Only residual positive additions receive the existing final patch check.
"""
import numpy as np
from shapely import to_wkb
from .group_allocation import units,mm
from .limiting_math import GUARD,MARGIN
from .member_allocation import maximum_pair_packing
from src.stage_abi.store import canonical,digest


def allocate_components(caps,pairs):
    """Exact component decomposition after propagating zero-face budgets.

    This changes neither the pair constraints nor the maximum-sum objective.
    Integer bounds identify redundant edges; every nontrivial component uses
    the existing general pair allocator. No geometry is searched here.
    """
    original={k:units(float(caps[k]))for k in sorted(caps)};limits=dict(original);edges={}
    for a,b,budget in pairs:
        key=tuple(sorted((a,b)));value=units(float(budget));edges[key]=min(edges.get(key,value),value)
    edges=dict(sorted(edges.items()))
    changed=True
    while changed:
        changed=False
        for (a,b),budget in edges.items():
            if budget==0:
                for k in(a,b):
                    if limits[k]:limits[k]=0;changed=True
            elif not limits[a]or not limits[b]:
                k=b if not limits[a]else a
                if limits[k]>budget:limits[k]=budget;changed=True
    active={(a,b):v for(a,b),v in edges.items()if limits[a]>0 and limits[b]>0 and v<limits[a]+limits[b]}
    adjacency={k:set()for k in limits if limits[k]>0}
    for a,b in active:adjacency[a].add(b);adjacency[b].add(a)
    live=set(adjacency);growth={k:0. for k in limits};components=[];objective=0
    while live:
        seed=min(live);component={seed};todo=[seed]
        while todo:
            for neighbor in adjacency[todo.pop()]-component:component.add(neighbor);todo.append(neighbor)
        live-=component;members=sorted(component)
        if len(members)==1:
            growth[seed]=mm(limits[seed]);objective+=2*limits[seed]
            components.append(dict(members=members,isolated_cap_units=limits[seed]));continue
        proof=maximum_pair_packing({k:mm(limits[k])for k in members},[(a,b,mm(v))for(a,b),v in active.items()if a in component])
        growth.update(proof['growth_mm']);objective+=proof['primal_objective_doubled_units'];components.append(dict(members=members,allocation=proof))
    gu={k:int(round(v*2e9))for k,v in growth.items()}
    if any(v>2*original[k]or v<0 for k,v in gu.items())or any(gu[a]+gu[b]>2*v for(a,b),v in edges.items()):raise ValueError('DECOMPOSED_FACE_BUDGET_CHANGED')
    return dict(schema='t04-component-pair-budget-packing/1',growth_mm=growth,primal_objective_doubled_units=objective,
        total_growth_mm=mm(objective)/2,original_face_caps_units=original,propagated_face_caps_units=limits,
        original_pairs=len(edges),active_pairs=len(active),components=components,
        proof='EXACT_ZERO_PROPAGATION; REDUNDANT_EDGES_REMOVED; SEPARABLE_EXISTING_PAIR_OPTIMA',geometry_audit=False)


class Budgets:
    """Owner-aware fixed operands plus admitted residual additions.

    Operand identity and geometry are bound once in canonical source order.
    ``screen_cells`` bounds scratch array batching only; it is never a route,
    neighbor or candidate limit. This workspace neither owns group mutation
    nor certifies a proposed contour: the existing residual verifier does that.
    """
    def __init__(self,records,*,screen_cells=262144):
        if type(screen_cells)is not int or screen_cells<1:raise ValueError('POSITIVE_SCREEN_WORKSPACE_REQUIRED')
        self.screen_cells=screen_cells;self.screen_rejections=0;self.screen_queries=0
        self.records=[(k,tuple(o),g,g.bounds)for k,o,g in sorted(records,key=lambda r:r[0])if not g.is_empty]
        self.bounds=np.array([r[3]for r in self.records]).reshape((-1,4));self.distance_calls=0
        self.binding=digest(canonical([[k,list(o),digest(to_wkb(g))]for k,o,g,b in self.records]))
        self.accepted=[]

    def add(self,key,owner,shape):
        """Expose only an accepted addition to later chains in this stage."""
        if shape.is_empty:return
        self.records.append((key,tuple(owner),shape,shape.bounds));self.bounds=np.vstack([self.bounds,shape.bounds])
        self.accepted.append(dict(id=key,owner=list(owner),geometry_sha256=digest(to_wkb(shape))))

    def neighbors(self,shape,owner,padding):
        """Return all potentially binding foreign operands in stored order.

        Complete rail-segment boxes can exclude distant operands before GEOS
        distance evaluation. They are lookup buckets, never growth members or
        taper boundaries. Polygon additions retain the ordinary bounds screen.
        """
        x0,y0,x1,y1=shape.bounds;b=self.bounds
        hits=np.flatnonzero((b[:,0]<=x1+padding)&(b[:,2]>=x0-padding)&(b[:,1]<=y1+padding)&(b[:,3]>=y0-padding))
        hits=np.array([int(i)for i in hits if self.records[int(i)][1]!=tuple(owner)],dtype=int)
        if shape.geom_type=='LineString'and len(hits):
            # Every bucket encloses complete native rail segments. A foreign
            # geometry outside ALL expanded bucket boxes cannot restrict this
            # rail's reach. Dense source framing makes these boxes local even
            # when one whole-rail AABB covers a large empty diagonal region.
            xy=np.asarray(shape.coords);boxes=[]
            for i in range(0,len(xy)-1,32):
                part=xy[i:i+33];lo=part.min(axis=0);hi=part.max(axis=0);boxes.append([*lo,*hi])
            boxes=np.asarray(boxes);selected=np.zeros(len(hits),dtype=bool);pad=padding+1e-12
            box_chunk=min(len(boxes),max(1,self.screen_cells//64));row_chunk=max(1,self.screen_cells//box_chunk)
            # Workspace budgets control batching only, never inventory size.
            for first in range(0,len(hits),row_chunk):
                foreign=b[hits[first:first+row_chunk]];keep=np.zeros(len(foreign),dtype=bool)
                for j in range(0,len(boxes),box_chunk):
                    q=boxes[j:j+box_chunk]
                    overlap=((foreign[:,None,0]<=q[None,:,2]+pad)&(foreign[:,None,2]>=q[None,:,0]-pad)&
                             (foreign[:,None,1]<=q[None,:,3]+pad)&(foreign[:,None,3]>=q[None,:,1]-pad))
                    keep|=overlap.any(axis=1)
                    if keep.all():break
                selected[first:first+len(foreign)]=keep
            self.screen_queries+=1;self.screen_rejections+=int((~selected).sum());hits=hits[selected]
        return [(self.records[int(i)][0],self.records[int(i)][2])for i in hits]

    def allocate(self,chains):
        """Compile fixed-neighbor and future-chain constraints before widths.

        Distances use original rails. The scalar allocator shares their reach
        without reserving hypothetical future copper; a rejected chain leaves
        no accepted geometry in this workspace.
        """
        caps={};pairs=[];witnesses=[];required=GUARD+2*MARGIN
        for key,c in chains.items():
            for side,rail in c['rails'].items():
                face=key+'#'+side;cap=c['reach_cap'];caps[face]=cap
                for source,g in self.neighbors(rail,c['owner'],cap+required):
                    gap=rail.distance(g);self.distance_calls+=1;budget=max(0.,gap-required)
                    caps[face]=min(caps[face],budget)
                    witnesses.append(dict(face=face,foreign_source=source,rail_gap_mm=gap,budget_mm=budget))
            pairs.append((key+'#negative',key+'#positive',c['total_growth_cap']))
        faces=sorted(caps)
        for i,a in enumerate(faces):
            ca,sa=a.rsplit('#',1);x=chains[ca]
            for b in faces[i+1:]:
                cb,sb=b.rsplit('#',1);y=chains[cb]
                if ca==cb or x['owner']==y['owner']:continue
                ra,rb=x['rails'][sa],y['rails'][sb]
                xa,ya,xb,yb=ra.bounds;xx,yy,xxx,yyy=rb.bounds
                dx=max(xa-xxx,xx-xb,0.);dy=max(ya-yyy,yy-yb,0.)
                if np.hypot(dx,dy)>caps[a]+caps[b]+required+1e-12:continue
                gap=ra.distance(rb);self.distance_calls+=1;budget=max(0.,gap-required)
                pairs.append((a,b,budget));witnesses.append(dict(first_face=a,second_face=b,source_rail_gap_mm=gap,budget_mm=budget))
        result=allocate_components(caps,pairs)if len(caps)>=2 else None
        return result,witnesses
