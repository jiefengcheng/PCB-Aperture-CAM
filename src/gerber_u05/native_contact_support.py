"""Native end-cap proposals for lost noncoincident route contacts.

Only existing source copper is proposed. The caller verifies these residual
additions against the current fixed scene; no group body is edited or audited.
"""
from collections import Counter
import numpy as np
from shapely.geometry import Point
from shapely.ops import unary_union
from .finite_profile_union import polygonal, assembly_union
from .limiting_math import MARGIN


def component_count(body):
    """A retained zero contribution has zero components, not a lost identity."""
    from src.original_copper_owners import OriginalOwners
    if body.is_empty and body.is_valid:return 0
    return len(OriginalOwners(body).owners)


def assemble(sources, bodies, material, *, recoveries=None, label=None):
    """Use declared source contours, including every positive copper face.

    Covered sources use their unchanged material operand. Missing source
    custody is an error, never a silently shortened route inventory.
    """
    return assembly_union([bodies[s]if s in bodies else material[s]for s in sources],
        validate_result=True,recoveries=recoveries,label=label)


def contribution_contacts(sources,bodies,material):
    """Borrow the serialized faces and reuse the existing contact sweep."""
    from .boundary_finish import polygons,face_contact_components
    by_source={}
    for source in sources:
        body=bodies[source]if source in bodies else material[source]
        if not body.is_empty and (not body.is_valid or body.geom_type not in('Polygon','MultiPolygon')):
            raise ValueError('VALID_FILLED_SOURCE_REQUIRED')
        by_source[source]=polygons(body)
    return by_source,face_contact_components([face for faces in by_source.values()for face in faces])


def contribution_count(sources,bodies,material):
    return len(contribution_contacts(sources,bodies,material)[1])


def retain_generated_carriers(sources, bodies, material, floors, baseline, assembled):
    """Reject detached generated faces, keeping original and attached copper.

    Called only for an extra-component result at an existing route assembly.
    Reuse the local finite-face contact sweep; retain source faces byte for byte. A
    crossing face or a real lost source connection cannot be repaired here.
    No foreign search, new addition, tolerance or board reconstruction occurs.
    """
    from shapely.geometry import MultiPolygon
    from shapely import get_precision,get_srid
    by_source,groups=contribution_contacts(sources,bodies,material)
    kept_groups=[group for group in groups if any(face.intersects(baseline)for face in group)]
    if len(kept_groups)>contribution_count(sources,floors,{}):return {},assembled,None
    kept_faces={id(face)for group in kept_groups for face in group}
    updates={};removed=[]
    for source in sources:
        body=bodies[source]if source in bodies else material[source]
        faces=by_source[source]
        kept=[face for face in faces if id(face)in kept_faces]
        if len(kept)==len(faces):continue
        dropped=[face for face in faces if id(face)not in kept_faces]
        if not kept or any(face.intersection(floors[source]).area!=0 for face in dropped):
            return {},assembled,None
        candidate=kept[0]if len(kept)==1 else MultiPolygon(kept)
        if (not candidate.is_valid or get_precision(candidate)!=get_precision(body)
                or get_srid(candidate)!=get_srid(body)):
            return {},assembled,None
        updates[source]=candidate;removed.extend(dropped)
    if not updates:return {},assembled,None
    result=assemble(sources,dict(bodies,**updates),material)
    # Every retained contact group is unchanged, face for face. Re-unioning
    # those same operands again is not another proof of their connectivity.
    result_count=len(kept_groups)
    if result.area<baseline.area:
        return {},assembled,None
    return updates,result,dict(
        policy='RETAIN_ORIGINAL_AND_ATTACHED_GENERATED_CARRIERS',
        source_ids=list(updates),discarded_generated_faces=len(removed),
        discarded_generated_contribution_area_mm2=sum(face.area for face in removed),
        original_positive_copper_removed_mm2=0.,attached_widening_removed_mm2=0.,
        net_gain_over_entry_mm2=result.area-baseline.area,
        assembled_components=result_count,
        retained_face_coordinates_unchanged=True,clearance_queries=0,
        attached_copper_proof='UNCHANGED_COMPLETE_FINITE_CONTACT_GROUPS',
        board_unions=0,passed=True)


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
