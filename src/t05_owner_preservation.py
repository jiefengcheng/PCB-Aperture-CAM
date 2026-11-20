"""A sufficient owner-preservation proof; failure still needs the original cut.

Prepared containment avoids constructing a large empty difference. It proves
that every owner point belongs to the actual candidate, without relying on how
the candidate was assembled. It never supplies a clearance/connectivity verdict.
"""
from shapely import (destroy_prepared, get_num_coordinates, get_precision,
                     is_prepared, prepare)


def owner_is_covered(owner, candidate, candidate_valid):
    """Return True only for proven coverage; False means use the original check.

    Small owners retain the inexpensive subtraction. The threshold matches the
    existing large-geometry indexing threshold, not a geometry tolerance.
    Preparation is scoped to this call and released unless owned by the caller;
    no new persistent cache, stale verdict or unbounded retained index is added.
    Unsupported/invalid/unequal-precision inputs take the original path.
    """
    if (get_num_coordinates(owner) < 32768 or not candidate_valid or
            candidate.geom_type != 'Polygon' or owner.geom_type != 'Polygon' or
            get_precision(owner) != get_precision(candidate) or not owner.is_valid):
        return False
    already_prepared = is_prepared(candidate)
    try:
        if not already_prepared:
            prepare(candidate)
        return bool(candidate.covers(owner))
    finally:
        if not already_prepared:
            destroy_prepared(candidate)
