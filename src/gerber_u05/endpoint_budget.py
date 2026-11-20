"""Small integer endpoint-budget extension of the existing face allocator.

Four face variables, source caps, independent end intervals and two sided
Lipschitz bounds. The constraint matrix is a signed bipartite incidence
matrix and is totally unimodular. Enumerating its integer vertices closes
the lower-width feasibility gap left by clipping an unconstrained optimum.
No geometry or iterative candidate search belongs in this module.
"""
from functools import lru_cache
from itertools import combinations
from decimal import Decimal,ROUND_CEILING
import numpy as np
from .group_allocation import units,mm,QUANTUM_MM
from .member_allocation import maximum_pair_packing


@lru_cache(maxsize=1)
def vertices():
    """Cache the fixed four-variable bases, not any geometry or route state.

    Rows encode face caps, nonnegativity, two end-width intervals and the
    positive/negative face change allowed between ends. Nonsingular bases
    have determinant +/-1, so integer bounds produce integer vertices.
    """
    a=np.r_[np.eye(4,dtype=np.int64),-np.eye(4,dtype=np.int64),
        [[1,1,0,0],[-1,-1,0,0],[0,0,1,1],[0,0,-1,-1],
         [1,0,-1,0],[-1,0,1,0],[0,1,0,-1],[0,-1,0,1]]]
    ix=np.array(list(combinations(range(len(a)),4)));matrices=a[ix]
    determinants=np.rint(np.linalg.det(matrices)).astype(int);live=determinants!=0
    if np.any(abs(determinants[live])!=1):raise ValueError('ENDPOINT_MATRIX_NOT_UNIMODULAR')
    return a,ix[live],np.rint(np.linalg.inv(matrices[live])).astype(np.int64)


def allocate(caps,intervals,allowance):
    """Maximize total end growth inside caps, end intervals and slope bounds.

    ``caps`` has the four keys below, ``intervals`` contains the two end
    growth-sum intervals, and all inputs use mm. Upper bounds round down to
    the existing 10^-9 mm quantum; lower bounds round up. Equal optima use the
    existing deterministic lexicographic choice. Infeasibility raises rather
    than weakening a bound or partially accepting an endpoint.
    """
    keys=['0:negative','0:positive','1:negative','1:positive']
    cap=[units(float(caps[k]))for k in keys]
    span=units(float(allowance))
    bounds=[]
    for low,high in intervals:
        minimum=int((Decimal(str(float(low)))/QUANTUM_MM).to_integral_value(rounding=ROUND_CEILING))
        bounds.extend([units(float(high)),-minimum])
    a,ix,inverse=vertices()
    b=np.array(cap+[0]*4+bounds+[span]*4,dtype=np.int64)
    # Reuse the established allocator whenever its optimum is feasible.
    old=maximum_pair_packing(caps,[(keys[0],keys[1],float(intervals[0][1])),(keys[2],keys[3],float(intervals[1][1]))])
    seed=np.array([units(float(old['growth_mm'][k]))for k in keys],dtype=np.int64)
    if np.all(a@seed<=b)and 2*int(seed.sum())==old['primal_objective_doubled_units']:chosen=seed;count=None;method='EXISTING_PAIR_PACKING_OPTIMUM'
    else:
        corners=np.einsum('ijk,ik->ij',inverse,b[ix])
        valid=np.all(corners@a.T<=b,axis=1)
        feasible=corners[valid]
        if not len(feasible):raise ValueError('RESIDUAL_END_BUDGETS_INFEASIBLE')
        totals=feasible.sum(axis=1)
        best=feasible[totals==totals.max()]
        chosen=min(best,key=lambda x:tuple(int(v)for v in x))
        count=int(valid.sum())
        method='INTEGER_ENDPOINT_VERTEX_OPTIMUM'
    return dict(schema='t04-budgeted-endpoint-allocation/1',growth_mm={k:mm(int(v))for k,v in zip(keys,chosen)},
        growth_units=[int(v)for v in chosen],constraint_rows=a.tolist(),bounds_units=b.tolist(),
        maximum_total_end_growth_units=int(chosen.sum()),feasible_vertices=count,method=method,
        proof='EXACT_INTEGER_PRIMAL; TOTALLY_UNIMODULAR_FOUR_FACE_POLYTOPE',geometry_audit=False)
