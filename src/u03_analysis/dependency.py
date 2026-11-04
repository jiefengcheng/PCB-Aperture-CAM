"""Conservative variable dependencies for the retained fixed-source offset family.

At factor s<=1.5 each route envelope is within distance .25*width+ERROR_MM
of its original core. A clearance failure between two moving routes requires
original-core distance <= pad_i+pad_j+construction_guard. Fixed predecessor,
original-port masks and original-visibility unions introduce no new variables.
Numerical reserve only ADDS graph edges, never relaxes the PCB predicate.
"""
import math
from shapely import STRtree
from shapely.geometry import box


def dependencies(rows,*,envelope_margin_mm,guard_mm,numerical_reserve_mm=1e-8):
    if any(not math.isfinite(v) or v<0 for v in (envelope_margin_mm,guard_mm,numerical_reserve_mm)):raise ValueError('FINITE_NONNEGATIVE_BOUND_REQUIRED')
    ids=[r['id'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('DUPLICATE_ROUTE')
    boxes=[];pads=[]
    for r in rows:
        w=r['width'];g=r['core']
        if not math.isfinite(w) or w<=0 or g.is_empty or not g.is_valid:raise ValueError('QUALIFIED_CORE_AND_WIDTH_REQUIRED')
        pad=.25*w+envelope_margin_mm;pads.append(pad);a,b,c,d=g.bounds;boxes.append(box(a-pad,b-pad,c+pad,d+pad))
    groups=sorted({r['group'] for r in rows});broad={g:set() for g in groups};tight={g:set() for g in groups};tree=STRtree(boxes);witnesses={};candidates=0;kept=0;internal=0
    for i,r in enumerate(rows):
        a,b,c,d=boxes[i].bounds;radius=guard_mm+numerical_reserve_mm
        for j in sorted(int(x) for x in tree.query(box(a-radius,b-radius,c+radius,d+radius))):
            if j<=i:continue
            if r['group']==rows[j]['group']:internal+=1;continue
            candidates+=1;g,h=sorted((r['group'],rows[j]['group']));broad[g].add(h);broad[h].add(g)
            bound=pads[i]+pads[j]+guard_mm+numerical_reserve_mm;distance=r['core'].distance(rows[j]['core'])
            if distance<=bound:
                kept+=1;tight[g].add(h);tight[h].add(g);key=(g,h)
                if key not in witnesses:witnesses[key]=dict(groups=[g,h],routes=[r['id'],rows[j]['id']],core_distance_mm=distance,maximum_dependency_distance_mm=bound)
    return dict(broad=broad,tight=tight,witnesses=list(witnesses.values()),candidate_route_pairs=candidates,retained_route_pairs=kept,internal_group_pairs=internal,pads_mm=pads,numerical_reserve_mm=numerical_reserve_mm)
