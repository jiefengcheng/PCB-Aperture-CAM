"""Bounded residual recovery after group/default decisions, before joints.

Reuse the ribbon constructor and one complete scalar corridor compilation.
Only nominal, ungrouped sources are eligible. Failed/inconclusive proposals
retain their existing result and their explicit reason; group interiors and
covered sources never enter this phase.
"""
from time import perf_counter
import numpy as np
from shapely.errors import GEOSException
from shapely.ops import unary_union
from .ribbon_profile import match_ends
from .finite_profile_union import certified_union
from .residual_corridor import Corridors
from src.native_inventory import ERROR_MM


def run(rows,material,paths,reports,endpoint_sections,width_caps,fixed_sources,owner,*,deviation=.1,protected_domains=(),source_cores=None):
    started=perf_counter();fixed_sources=set(fixed_sources);decisions={v['source_id']:v for v in reports}
    proposals={};records=[];routes={s:r for r,ss in paths.items()for s in ss}
    for s in sorted(routes):
        if s in fixed_sources or s not in material:continue
        old=decisions.get(s)
        if old is None or old['selected_factor']>1.+1e-10:continue
        md=rows[s]['metadata'];pts=md['route_points_mm'];w=md['minimum_caliper_mm']
        if md['aperture_family'][0]!='C':continue
        ends=[endpoint_sections.get((routes[s],tuple(round(float(v),10)for v in pt)))for pt in(pts[0],pts[-1])]
        if not any(e is not None and np.linalg.norm(np.subtract(e['upper_mm'],e['lower_mm']))>w+ERROR_MM for e in ends):continue
        record=dict(source_id=s,route_id=routes[s],preceding_factor=old['selected_factor'])
        try:
            length=sum(np.linalg.norm(np.subtract(b,a))for a,b in zip(pts,pts[1:]))
            slope=1. if md['route_kind']=='segment'and length<=.1 else .25
            body,recipe=match_ends(pts,w,width_caps[s],ends=ends,deviation=deviation,maximum_side_slope=slope)
            candidate,method=certified_union(material[s],body)
            enclosure=body
            if method=='EXACT_FLOOR_FALLBACK'and source_cores is not None and width_caps[s]>w+2*ERROR_MM:
                # Reuse the qualified nominal-skin stitch. Reserve its exact
                # width before materializing it, and include ALL new stitch
                # copper in the same corridor certificate.
                body,recipe=match_ends(pts,w,width_caps[s]-2*ERROR_MM,ends=ends,deviation=deviation,maximum_side_slope=slope)
                enclosure=unary_union([body,source_cores[s].buffer(ERROR_MM,quad_segs=128)])
                candidate,retry=certified_union(material[s],enclosure)
                method='NOMINAL_SOURCE_SKIN_STITCH; '+retry
                recipe['nominal_skin_stitch']=dict(radial_mm=ERROR_MM,reserved_width_mm=2*ERROR_MM,
                    physical_width_cap_mm=width_caps[s],source_ref=rows[s]['original_ref'])
                if retry=='EXACT_FLOOR_FALLBACK':raise ValueError('MATCHED_PROFILE_CANNOT_RETAIN_EXACT_SOURCE_FLOOR')
            if method=='EXACT_FLOOR_FALLBACK':raise ValueError('MATCHED_PROFILE_CANNOT_RETAIN_EXACT_SOURCE_FLOOR')
            if candidate.area<=material[s].area+ERROR_MM**2:raise ValueError('MATCHED_PROFILE_HAS_NO_NEW_COPPER')
            axis=np.subtract(pts[-1],pts[0])
            if np.linalg.norm(axis)<1e-12:raise ValueError('CLOSED_RESIDUAL_NEEDS_MEMBER_CORRIDOR')
            record.update(status='PROPOSED',recipe=recipe,finite_union=method)
            proposals[s]=dict(body=candidate,enclosure=enclosure,recipe=recipe,axis=axis,record=record)
        except (ValueError,GEOSException)as error:record.update(status='KEEP_PRECEDING_RESULT; CONSTRUCTION_LIMIT',reason=str(error))
        records.append(record)
    accepted={};corridor=None
    if proposals:
        operands=[(k,owner(k),g)for k,g in material.items()]
        operands.extend((f'protected:{i}',(f'protected:{i}',),g)for i,g in enumerate(protected_domains))
        reservations=[('future:'+s,owner(s),v['enclosure'].bounds)for s,v in sorted(proposals.items())]
        corridor=Corridors(operands,reservations)
        for s,v in sorted(proposals.items()):
            q=corridor.certify(v['enclosure'],v['axis'],owner(s));v['record']['corridor']=q
            if not q['passed']:v['record']['status']='KEEP_PRECEDING_RESULT; CORRIDOR_NOT_PROVEN';continue
            material[s]=v['body'];accepted[s]=v['recipe'];v['record']['status']='CONSTRUCTED_FROM_MATCHED_ENDS'
            d=decisions[s];d.update(selected_factor=v['recipe']['maximum_width_mm']/rows[s]['metadata']['minimum_caliper_mm'],
                factor_semantics='PROFILE_CEILING; INDEPENDENT_10_PERCENT_END_MATCH',status='MATCHED_RESIDUAL_ENDS')
            d.setdefault('attempts',[]).append(dict(passed=True,failures=[],decision='RESIDUAL_MATCHED_ENDS_SCALAR_CORRIDOR',
                factor=d['selected_factor'],geometry_verification=False,corridor_binding=q['complete_operand_binding']))
    return accepted,dict(schema='t04-residual-end-match-recovery/1',deviation=deviation,reports=records,
        eligible_sources=len(records),proposed_sources=len(proposals),constructed_sources=len(accepted),
        group_interiors_changed=False,constructed_groups_audited=0,r_tree_queries=0,geometry_distance_calls=0,
        candidate_geometry_verifications=0,complete_corridor_binding=None if corridor is None else corridor.binding,
        corridor_setup_wall_s=0. if corridor is None else corridor.setup_wall_s,
        scalar_boundary_projections=0 if corridor is None else corridor.projections,
        wall_s=perf_counter()-started)
