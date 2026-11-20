"""Native end-cap proposals for lost noncoincident route contacts.

Only existing source copper is proposed. The caller verifies these residual
additions against the current fixed scene; no group body is edited or audited.
"""
from collections import Counter
import numpy as np
from shapely.geometry import Point
from shapely.ops import unary_union
from .finite_profile_union import polygonal
from .limiting_math import MARGIN


def assemble(sources, bodies, material):
    """Use declared source contours, including every positive copper face.

    Covered sources use their unchanged material operand. Missing source
    custody is an error, never a silently shortened route inventory.
    """
    return unary_union([bodies[s]if s in bodies else material[s]for s in sources])


def proposals(rows, sources, references, mutable, translations, *, shared=False):
    def ends(s):
        points=rows[s]['metadata']['route_points_mm']
        move=np.asarray(translations.get(s,(0.,0.)))
        return [np.asarray(pt)+move for pt in (points[0],points[-1])]
    endpoints={s:ends(s)for s in sources}
    key=lambda pt:tuple(round(float(v),10)for v in pt)
    counts=Counter(key(pt)for pts in endpoints.values()for pt in pts)
    for s in sorted(set(sources)&set(mutable)):
        radius=rows[s]['metadata']['minimum_caliper_mm']/2+MARGIN
        for pt in endpoints[s]:
            if (counts[key(pt)]>1)!=shared:continue
            cap=polygonal(references[s].intersection(Point(pt).buffer(radius,quad_segs=128)))
            if cap.is_empty:continue
            contacts=[other for other in sources if other!=s and cap.intersects(references[other])]
            if contacts:
                record=dict(source_id=s,endpoint_mm=list(map(float,pt)),
                            contact_sources=contacts,geometry=cap)
                if shared:record['shared_endpoint']=True
                yield record
