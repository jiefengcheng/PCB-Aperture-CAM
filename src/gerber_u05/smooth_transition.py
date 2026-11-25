"""Cubic side fields with algebraic corridor and slope certificates.

The four Bernstein controls bound the complete curve, not sampled locations.
Control-budget checks are construction preconditions, not geometry audits.
"""
import math


def controls(first,last):
    if not all(math.isfinite(v)for v in (first,last)):
        raise ValueError('FINITE_SIDE_FIELD_REQUIRED')
    return [first,first,last,last]


def value(c,t):
    if len(c)!=4 or not 0<=t<=1:raise ValueError('CUBIC_UNIT_PARAMETER_REQUIRED')
    return c[0]*(1-t)**3+3*c[1]*(1-t)**2*t+3*c[2]*(1-t)*t*t+c[3]*t**3


def restrict(c,first,last):
    """Exact polynomial restriction, retaining the tangent at source seams."""
    if not 0<=first<=last<=1:raise ValueError('ORDERED_CUBIC_SUBDOMAIN_REQUIRED')
    def derivative(t):
        return 3*((c[1]-c[0])*(1-t)**2+2*(c[2]-c[1])*(1-t)*t+(c[3]-c[2])*t*t)
    a,b=value(c,first),value(c,last);span=(last-first)/3
    return [a,a+span*derivative(first),b-span*derivative(last),b]


def certify(first,last,length,*,paired_budgets=(),maximum_side_slope=.25):
    """First/last are lane side coordinates, lower face then upper face.

    paired_budgets contains (lower-lane upper face, upper-lane lower face,
    start gap, end gap). Gap bounds may be affine in source arclength.
    Coordinates can be signed: these are side locations, not growth amounts.
    """
    if (len(first)!=len(last) or not first or not math.isfinite(length) or length<=0
            or not math.isfinite(maximum_side_slope) or maximum_side_slope<=0):
        raise ValueError('VALID_SMOOTH_TRANSITION_REQUIRED')
    fields=[controls(a,b)for a,b in zip(first,last)]
    failures=[]
    slope=max(1.5*abs(b-a)/length for a,b in zip(first,last))
    if slope>maximum_side_slope+1e-12:failures.append('TRANSITION_TOO_SHORT_FOR_SIDE_SLOPE')
    gap_controls=[]
    for lower,upper,g0,g1 in paired_budgets:
        if not (0<=lower<len(fields) and 0<=upper<len(fields)) or not all(math.isfinite(v)and v>=0 for v in(g0,g1)):
            raise ValueError('VALID_PAIRED_CORRIDOR_BUDGET_REQUIRED')
        # Degree elevation of an affine bound gives its cubic controls.
        required=[g0+(g1-g0)*i/3 for i in range(4)]
        spare=[fields[upper][i]-fields[lower][i]-required[i]for i in range(4)]
        gap_controls.append(spare)
        if min(spare)<-1e-12:failures.append('PAIRED_CORRIDOR_CONTROL_BUDGET_EXCEEDED')
    return dict(schema='t04-cubic-side-field/1',passed=not failures,failures=failures,
        controls=fields,length_mm=length,maximum_side_slope=maximum_side_slope,
        actual_maximum_side_slope=slope,endpoint_derivatives=[0.,0.],
        spare_gap_controls_mm=gap_controls,geometry_audit=False,
        proof='BERNSTEIN_CONVEX_HULL; SHARED_PARAMETER; AFFINE_CORRIDOR_BOUNDS')


def tessellate(c,length,*,error_mm=1e-7):
    """Common uniform knots with a rigorous linear-interpolation error bound."""
    if error_mm<=0 or length<=0 or len(c)!=4:raise ValueError('VALID_TESSELLATION_REQUIRED')
    second=6*max(abs(c[2]-2*c[1]+c[0]),abs(c[3]-2*c[2]+c[1]))
    count=max(1,math.ceil(math.sqrt(second/(8*error_mm))))
    # Multiplying then dividing can put the final station one ULP beyond
    # length (for example 3*.1/3). Preserve the exact certified endpoint.
    return [(length if i==count else i*length/count,value(c,i/count))for i in range(count+1)]
