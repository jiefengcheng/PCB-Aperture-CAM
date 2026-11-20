"""One rigid reference translation per connected route, from group equations.

No strip is moved or geometrically rechecked here. Incompatible group poses
remain unresolved; fitting a compromise would invalidate the given construction.
"""
import math
import numpy as np


def solve(construction, paths, *, maximum=.025):
    if construction.get('reference_policy')=='SOURCE_ANCHORED':
        conflicts=sorted({lane['route_id']for group in construction['groups']for lane in group['lanes']
                          if lane['mutable'] and min(lane['face_growth_mm'].values())<0})
        return dict(schema='t04-common-route-reference-pose/1',
            routes={r:dict(translation_mm=[0.,0.],compatible=r not in conflicts,
                           policy='SOURCE_ANCHORED_BEFORE_GROUP_ALLOCATION')for r in paths},
            passed=not conflicts,conflicting_routes=conflicts,
            constructed_group_geometry_changed=False,geometry_audit=False)
    owner={s:r for r,ss in paths.items() for s in ss};equations={r:[] for r in paths}
    for group in construction['groups']:
        ux,uy=group['axis'];normal=[-uy,ux]
        for lane in group['lanes']:
            if not lane['mutable']:continue
            for r in sorted({owner[s] for s in lane['source_ids'] if s in owner}):
                equations[r].append((normal,lane['profile_midline_shift_mm'],
                                     -lane['face_growth_mm']['left'],lane['face_growth_mm']['right']))
    records={};conflicts=[]
    for r,rows in sorted(equations.items()):
        if rows:
            a=np.asarray([n for n,v,lo,hi in rows]);b=np.asarray([v for n,v,lo,hi in rows])
            preferred=np.linalg.lstsq(a,b,rcond=None)[0]
            bounds=[(np.asarray(n),v) for n,_,lo,hi in rows for v in (lo,hi)]
            candidates=[np.zeros(2),preferred]
            if np.linalg.norm(preferred)>maximum:candidates.append(preferred*maximum/np.linalg.norm(preferred))
            for n,v in bounds:
                for origin in (np.zeros(2),preferred):candidates.append(origin+n*(v-n@origin)/(n@n))
            for i,(n,v) in enumerate(bounds):
                for m,w in bounds[i+1:]:
                    matrix=np.asarray([n,m])
                    if abs(np.linalg.det(matrix))>1e-14:candidates.append(np.linalg.solve(matrix,[v,w]))
            tolerance=5e-10 # half one allocation quantum, within reserved margin
            feasible=[p for p in candidates if np.linalg.norm(p)<=maximum+tolerance and
                      all(lo-tolerance<=n@p<=hi+tolerance for n,_,lo,hi in rows)]
            pose=min(feasible,key=lambda p:(float(p@p),float(np.sum((a@p-b)**2)))) if feasible else preferred
            error=max((max(lo-float(n@pose),float(n@pose)-hi,0.) for n,_,lo,hi in rows),default=0.)
        else:pose=np.zeros(2);error=0.;feasible=[pose];tolerance=5e-10
        # This is numerical equation tolerance, far below the construction
        # margin. It never relaxes the physical clearance or width limits.
        okay=bool(feasible) and error<=tolerance and math.hypot(*pose)<=maximum+tolerance
        if not okay:conflicts.append(r)
        records[r]=dict(translation_mm=pose.tolist(),maximum_equation_error_mm=error,
                        group_equations=len(rows),compatible=okay,
                        pose_rounding_budget_mm=tolerance,
                        policy='SAME_VECTOR_FOR_EVERY_SOURCE_POINT_AND_CURVE_ON_ROUTE')
    return dict(schema='t04-common-route-reference-pose/1',routes=records,
                passed=not conflicts,conflicting_routes=conflicts,
                constructed_group_geometry_changed=False,geometry_audit=False)
