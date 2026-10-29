"""Analytical shared-width bounds for already-applicable surface constraints.

No routes move. A member's radius increases by (factor-1)*original_width/2.
This bound is preparation, not a substitute for complete finite-copper checking.
"""
import math


def shared_scale_bound(widths, constraints, *, minimum_gap_mm=.02010, ceiling=1.5):
    if not widths or not math.isfinite(minimum_gap_mm) or minimum_gap_mm<=0 or ceiling!=1.5:
        raise ValueError('INVALID_WIDTH_CONTRACT')
    if any(not math.isfinite(w) or w<=0 for w in widths.values()):
        raise ValueError('INVALID_ORIGINAL_WIDTH')
    factor=ceiling;rows=[]
    for c in constraints:
        a,b=c['member_a'],c.get('member_b')
        gap=c['surface_gap_mm']
        if a not in widths or (b is not None and b not in widths) or a==b:
            raise ValueError('UNKNOWN_OR_DUPLICATED_GROUP_MEMBER')
        if not math.isfinite(gap) or gap<0:
            raise ValueError('INVALID_SURFACE_DISTANCE')
        if c.get('applicability')!='EXPOSED_DISCONNECTED_SURFACES':
            raise ValueError('SURFACE_APPLICABILITY_NOT_ESTABLISHED')
        denominator=widths[a]+(widths[b] if b is not None else 0.)
        raw=1.+2.*(gap-minimum_gap_mm)/denominator
        bounded=max(1.,min(ceiling,raw))
        factor=min(factor,bounded)
        rows.append(dict(constraint_id=c['constraint_id'],member_a=a,member_b=b,
            original_surface_gap_mm=gap,unclamped_common_factor_limit=raw,
            bounded_common_factor_limit=bounded,
            status='NO_POSITIVE_GROWTH_UNDER_THIS_CONSTRAINT' if raw<=1 else 'POSITIVE_GROWTH_BOUND'))
    return dict(common_factor_upper_bound=factor,hard_ceiling=ceiling,minimum_gap_mm=minimum_gap_mm,
        original_widths_mm=dict(sorted(widths.items())),
        resulting_nominal_width_upper_bounds_mm={sid:w*factor for sid,w in sorted(widths.items())},
        limiting_constraint_ids=[r['constraint_id'] for r in rows if r['bounded_common_factor_limit']==factor],
        constraints=rows,
        interpretation='Analytical bound for ideal uniform radial growth; finite-copper construction/verifier still required',
        width_construction='NOT_RUN')
