"""Hard-capped shared enlargement factors for a bounded pair experiment."""
import math

MAX_RADIUS_FACTOR=1.5


def shared_factor(source_radii, *, source_feasible_factor, square_pair_factor):
    if len(source_radii)!=2 or any(not math.isfinite(r) or r<=0 for r in source_radii):
        raise ValueError('INVALID_SOURCE_RADII')
    if any(not math.isfinite(f) or f<1 for f in (source_feasible_factor,square_pair_factor)):
        raise ValueError('NO_SHARED_NONSHRINKING_GROWTH')
    factor=min(MAX_RADIUS_FACTOR,source_feasible_factor,square_pair_factor)
    return factor,[factor*r for r in source_radii]


def require_radius_cap(source_radius, proposed_radius):
    if not all(math.isfinite(v) and v>0 for v in (source_radius,proposed_radius)):
        raise ValueError('INVALID_RADIUS')
    if proposed_radius>MAX_RADIUS_FACTOR*source_radius:
        raise ValueError('HARD_1_5X_CEILING_EXCEEDED')
    return True
