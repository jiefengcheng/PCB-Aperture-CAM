"""Conservative local certificate for reusing an older *full* fidelity buffer.

Only the width guard's buffer preparation changes. Its ordered subtractions,
raw overlap, final difference, area proof and all independent guards still run.
The buffer remains bound to the geometry that actually constructed it: a local
hit NEVER relabels that old buffer as belonging to the newer whole owner.
"""
import math
from contextlib import contextmanager
from contextvars import ContextVar
import numpy as np
import shapely
from shapely.geometry import box

# Only large buffers justify certification overhead. Smaller owners retain the
# exact original operation path, including its floating overlay measurements.
MIN_COORDINATES=32768


def boundary_rows(shape, bounds):
    """Original oriented segments plus adjacent vertices near a closed window.

    Comparing clipped surfaces alone would miss changed collinear segmentation
    or different remote endpoints of a long segment, which can affect GEOS's
    floating offset arithmetic. Preserve both complete endpoints and the next
    vertex at either end. No clipping/simplification/rounding creates these rows.
    Ring orientation is canonical, but coordinates are untouched. Ring order and
    start vertex do not matter because rows are lexicographically sorted.
    Arrays are temporary; there is no retained mutable boundary-index cache.
    """
    rings=shapely.get_rings(shapely.get_parts(shapely.orient_polygons(shape)))
    coordinates,owners=shapely.get_coordinates(rings,return_index=True)
    if len(coordinates)<4:return np.empty((0,8),dtype=np.float64)
    positions=np.flatnonzero(owners[:-1]==owners[1:])
    a=coordinates[positions];b=coordinates[positions+1]
    x,y,X,Y=bounds
    selected=(np.minimum(a[:,0],b[:,0])<=X)&(np.maximum(a[:,0],b[:,0])>=x)&(np.minimum(a[:,1],b[:,1])<=Y)&(np.maximum(a[:,1],b[:,1])>=y)
    positions=positions[selected]
    if not len(positions):return np.empty((0,8),dtype=np.float64)
    starts=np.r_[0,np.flatnonzero(np.diff(owners))+1]
    ends=np.r_[starts[1:],len(coordinates)]
    begin=starts[owners[positions]];end=ends[owners[positions]]
    prior=np.where(positions==begin,end-2,positions-1)
    after=begin+(positions+2-begin)%(end-begin-1)
    rows=np.concatenate((coordinates[prior],coordinates[positions],coordinates[positions+1],coordinates[after]),axis=1)
    return rows[np.lexsort(rows.T[::-1])]


def certify(previous,current,logical,radius,eligible):
    """Certify the buffer's needed region, or conservatively decline reuse.

    A positive round buffer only depends on copper within its radius. The
    window covers the COMPLETE logical proposal (hence its raw overlap), padded
    by four radii and a coordinate-ULP guard. Equal local copper establishes the
    same inside/outside region. Equal original adjacent segment coordinates
    additionally preserve the actual local GEOS offset construction operands.
    Fixed precision, invalid/nonareal/Z geometry and oversized inputs fall back.
    """
    if not eligible(previous) or not eligible(current):return False,'unsupported'
    if shapely.get_srid(previous)!=shapely.get_srid(current):return False,'srid'
    bounds=logical.bounds
    if len(bounds)!=4 or not all(math.isfinite(v)and abs(v)<1e6 for v in bounds):return False,'bounds'
    pad=max(4*radius,1e-6,128*math.ulp(max(1.,*(abs(v)for v in bounds))))
    x,y,X,Y=bounds;window=box(x-pad,y-pad,X+pad,Y+pad)
    # Fail quickly when a preceding accepted fill changes this neighborhood.
    old=shapely.normalize(previous.intersection(window))
    new=shapely.normalize(current.intersection(window))
    if not shapely.equals_identical(old,new):return False,'local_copper_changed'
    a=boundary_rows(previous,window.bounds);b=boundary_rows(current,window.bounds)
    if a.shape!=b.shape or not np.array_equal(a,b):return False,'boundary_operands_changed'
    return True,'certified'


# Runtime scopes are opt-in for a bounded proof comparison. The prior
# small-owner trial showed that arithmetic order can change numeric witnesses.
# A future fresh-board profile must establish its own reference equivalence.
ACTIVE = ContextVar('t04_local_predecessor_buffer', default=None)


class LocalReuse:
    """Retain at most two immutable input identities and their validity facts."""
    def __init__(self):
        self.eligibility = []

    def eligible(self, shape):
        for original, valid in self.eligibility:
            if shape is original:
                return valid
        valid = (
            shape.geom_type in ('Polygon', 'MultiPolygon') and not shape.is_empty
            and not shapely.has_z(shape) and not shapely.has_m(shape)
            and shapely.get_precision(shape) == 0
            and MIN_COORDINATES <= shapely.get_num_coordinates(shape) <= 250000
            and shape.is_valid
        )
        self.eligibility.append((shape, valid))
        if len(self.eligibility) > 2:
            self.eligibility.pop(0)
        return valid

    def reusable(self, cached, predecessor, logical, radius):
        if cached is None:
            return None
        previous, buffered = cached
        if previous is predecessor or (
            shapely.get_precision(previous) == shapely.get_precision(predecessor)
            and shapely.equals_identical(previous, predecessor)
        ):
            # The normal path already handles complete equality.
            return None
        admitted, _ = certify(previous, predecessor, logical, radius, self.eligible)
        return buffered if admitted else None


@contextmanager
def bounded_local_reuse():
    """Enable the local width certificate within a paired bounded probe."""
    token = ACTIVE.set(LocalReuse())
    try:
        yield
    finally:
        ACTIVE.reset(token)
