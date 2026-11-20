"""Route-minimum proposals derived exclusively from parallel source relations."""
from collections import defaultdict
import math

GUARD=.0401
MARGIN=.000014
SHARED_LENGTH=.05
TOLERANCE=.10

def share(gap, first_width, second_width, first_cap, second_cap):
    spare=max(0.,gap-GUARD-2*MARGIN)
    return (min(first_cap,spare*first_width/(first_width+second_width)),
            min(second_cap,spare*second_width/(first_width+second_width)))

def minimum_growth(members, proposals, caps):
    selected=[proposals[s] for s in members if s in proposals]
    return min(selected) if selected else None

def fit_within_tolerance(targets, constraints, tolerance=TOLERANCE, original_widths=None):
    """Reduce growth only within the allowed band; report unsatisfiable edges."""
    growth=dict(targets)
    floors={r:max(0.,(1-tolerance)*g-tolerance*original_widths[r]/2)
            if original_widths is not None else (1-tolerance)*g for r,g in targets.items()}
    conflicts=[]
    for a,b,budget in constraints:
        if floors.get(a,0.)+floors.get(b,0.)>budget+1e-12:
            conflicts.append(dict(a=a,b=b,budget_mm=budget,minimum_required_mm=floors.get(a,0.)+floors.get(b,0.)))
    if conflicts:
        return growth,conflicts
    for a,b,budget in constraints:
        excess=growth.get(a,0.)+growth.get(b,0.)-budget
        if excess<=1e-12:continue
        variables=[r for r in (a,b) if r in growth]
        for r in sorted(variables,key=lambda r:growth[r]-floors[r],reverse=True):
            reduction=min(excess,growth[r]-floors[r])
            growth[r]-=reduction
            excess-=reduction
    assert all(growth.get(a,0.)+growth.get(b,0.)<=budget+1e-12 for a,b,budget in constraints)
    return growth,[]

def collect_proposals(rows, paths, straight, curves, original, bulk_source_ids=(), *, owner_ids=None, excluded=None):
    bulk_source_ids=set(bulk_source_ids)
    from shapely.geometry import LineString,Polygon
    from shapely.ops import substring,unary_union
    from shapely import line_locate_point
    import numpy as np
    widths={s:r['metadata']['minimum_caliper_mm'] for s,r in rows.items() if r['kind']=='stroke'}
    caps={s:min(.25*w,.015) for s,w in widths.items()}
    proposals={}
    witnesses=[]
    def add(first,second,gap,kind,interval,overlap_mm2=0.):
        if not first or not second:return
        if owner_ids is not None and overlap_mm2>0:
            aa={o for s in first for o in owner_ids[s]};bb={o for s in second for o in owner_ids[s]}
            if len(aa)==1 and aa==bb:
                if excluded is not None:excluded.append(dict(a=first,b=second,kind=kind,interval=interval,overlap_mm2=overlap_mm2,owner=next(iter(aa)),reason='OVERLAPPING_ORIGINAL_COPPER_NOT_SEPARATE_LANES'))
                return
        wi,wj=widths[first[0]],widths[second[0]]
        di,dj=share(gap,wi,wj,caps[first[0]],caps[second[0]])
        for ids,delta in ((first,di),(second,dj)):
            for sid in ids:proposals[sid]=min(proposals.get(sid,math.inf),delta)
        witnesses.append(dict(a=first,b=second,gap_mm=gap,a_radial_mm=di,b_radial_mm=dj,kind=kind,interval=interval))
    runs=straight['runs']
    def segment(run,band):
        axis=band['axis'];a,b=run['start'],run['end']
        start=sum(x*y for x,y in zip(a,axis));end=sum(x*y for x,y in zip(b,axis))
        points=[[a[k]+(t-start)/(end-start)*(b[k]-a[k]) for k in (0,1)]
                for t in (band['first'],band['last'])]
        ids=[]
        for sid in run['source_ids']:
            ends=rows[sid]['metadata']['route_points_mm']
            lo,hi=sorted(sum(x*y for x,y in zip(point,axis)) for point in (ends[0],ends[-1]))
            if min(hi,band['last'])-max(lo,band['first'])>1e-10:ids.append(sid)
        return LineString(points),ids
    for band in straight['cases']['admitted_0.05']['bands']:
        ux,uy=band['axis'];normal=(-uy,ux)
        shapes={i:segment(runs[i],band) for i in band['members']}
        shapes={i:(line,[sid for sid in ids if sid not in bulk_source_ids]) for i,(line,ids) in shapes.items()}
        shapes={i:value for i,value in shapes.items() if value[1]}
        order=sorted(shapes,key=lambda i:sum(v*n for v,n in zip(shapes[i][0].interpolate(.5,normalized=True).coords[0],normal)))
        for i,j in zip(order,order[1:]):
            a,idsa=shapes[i];b,idsb=shapes[j]
            if not idsa or not idsb:continue
            # Native copper contours determine the free gap. Source widths
            # determine proportional weights, avoiding an ideal-strip estimate.
            normal=(-uy,ux)
            material_a=unary_union([original[s] for s in idsa])
            material_b=unary_union([original[s] for s in idsb])
            bounds=[material_a.bounds,material_b.bounds]
            transverse=[x*normal[0]+y*normal[1] for box_ in bounds
                        for x in (box_[0],box_[2]) for y in (box_[1],box_[3])]
            def xy(t,n):return (t*ux+n*normal[0],t*uy+n*normal[1])
            low,high=min(transverse)-1,max(transverse)+1
            slab=Polygon([xy(band['first'],low),xy(band['last'],low),
                          xy(band['last'],high),xy(band['first'],high)])
            part_a,part_b=material_a.intersection(slab),material_b.intersection(slab)
            if part_a.is_empty or part_b.is_empty:continue
            gap=part_a.distance(part_b)
            add(idsa,idsb,gap,'straight',dict(first=band['first'],last=band['last']),part_a.intersection(part_b).area if owner_ids is not None and gap==0 else 0.)
    arcs=curves['arcs']
    for group in curves['cases']['admitted_0.05']['groups']:
        anchor=LineString(arcs[group['template']]['points'])
        lo,hi=group['template_stations_mm'];mid=anchor.interpolate((lo+hi)/2)
        a,b=anchor.interpolate(max(0.,(lo+hi)/2-.00001)),anchor.interpolate(min(anchor.length,(lo+hi)/2+.00001))
        normal=(-(b.y-a.y),b.x-a.x)
        intervals={v['member']:v['stations_mm'] for v in group['member_intervals_mm']}
        shapes={i:substring(LineString(arcs[i]['points']),*intervals[i]) for i in group['members'] if arcs[i]['source_id'] not in bulk_source_ids}
        order=sorted(shapes,key=lambda i:sum(v*n for v,n in zip(shapes[i].interpolate(.5,normalized=True).coords[0],normal)))
        for i,j in zip(order,order[1:]):
            si,sj=arcs[i]['source_id'],arcs[j]['source_id']
            part_i=original[si].intersection(shapes[i].buffer(widths[si]+MARGIN,quad_segs=64))
            part_j=original[sj].intersection(shapes[j].buffer(widths[sj]+MARGIN,quad_segs=64))
            if part_i.is_empty or part_j.is_empty:continue
            gap=part_i.distance(part_j)
            add([si],[sj],gap,'arc',dict(template=group['template'],stations=group['template_stations_mm']),part_i.intersection(part_j).area if owner_ids is not None and gap==0 else 0.)
    targets={rid:minimum_growth(members,proposals,caps) for rid,members in paths.items()}
    return {r:v for r,v in targets.items() if v is not None},proposals,witnesses,caps
