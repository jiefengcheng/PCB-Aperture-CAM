"""Refine rejected free spans without changing constructed group interiors.

The native source and maximal member stay indivisible. Additional constraints
are width stations on the same continuous field, not new trace occurrences.
"""
from copy import deepcopy


def localize(record,source_width,fraction):
    if not 0<fraction<1:raise ValueError('SHOULDER_FRACTION_REQUIRED')
    result=deepcopy(record)
    if 'member_context'in result:
        result['member_context']=localize(result['member_context'],source_width,fraction)
        return result
    windows=sorted(result['constraints'],key=lambda q:(q['first_mm'],q['last_mm']))
    if not windows:raise ValueError('CONSTRUCTED_STRAIGHT_CONSTRAINT_REQUIRED')
    result.update(inherit_sided_endpoints=False,endpoint_widths_mm=[source_width,source_width])
    nominal=[];cursor=0.
    for q in windows:
        gap=q['first_mm']-cursor
        if gap>1e-12:
            # Keep a nominal middle only where two independent group fields
            # leave enough room for both shoulders. Source ends need one.
            lo=cursor+(gap*fraction/2 if cursor else 0.)
            hi=q['first_mm']-gap*fraction/2
            if hi-lo>1e-12:nominal.append(dict(first_mm=lo,last_mm=hi,width_mm=source_width,profile_midline_shift_mm=0.,group_band='DEFAULT_SHOULDER_LIMIT'))
        cursor=max(cursor,q['last_mm'])
    gap=result['length_mm']-cursor
    if gap>1e-12:nominal.append(dict(first_mm=cursor+gap*fraction/2,last_mm=result['length_mm'],width_mm=source_width,profile_midline_shift_mm=0.,group_band='DEFAULT_SHOULDER_LIMIT'))
    result['constraints']=[*windows,*nominal]
    result['free_span_refinement']=dict(policy='LOCAL_CONTINUOUS_SHOULDERS; GROUP_CONSTRAINTS_UNCHANGED',fraction=fraction)
    return result
