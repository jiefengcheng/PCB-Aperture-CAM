"""Strict saved-floor unions of finite polygonal supplemental copper."""
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.errors import GEOSException


def polygonal(g):
    """Discard overlay-only lines/points; never snap, buffer or simplify copper."""
    if g.geom_type in ('Polygon','MultiPolygon'):return g
    parts=[]
    def collect(x):
        if x.geom_type=='Polygon':parts.append(x)
        elif hasattr(x,'geoms'):
            for y in x.geoms:collect(y)
        else:
            if x.area!=0:raise ValueError('NONPOLYGONAL_NONZERO_AREA_COPPER')
    collect(g)
    return unary_union(parts) if parts else Polygon()


def difference_for_window(left,right,window):
    """Keep the original overlay; on GEOS failure solve only the declared domain.

    Callers consume the result inside window. Buffer-generated masks can have
    invalid boundaries elsewhere. Never snap/repair either operand or invent
    an empty result: both restricted operands and the result must be valid.
    """
    try:return left.difference(right)
    except GEOSException:
        a=polygonal(left.intersection(window));b=polygonal(right.intersection(window))
        if not a.is_valid or not b.is_valid:raise
        result=polygonal(a.difference(b))
        if not result.is_valid:raise
        return result


def certified_union(floor,extension):
    """Try exact ordered overlays; fallback is the entire unchanged saved floor."""
    from .profile_refinement import contains_floor
    extra=polygonal(extension)
    if extra.is_empty:return floor,'IDENTITY_NO_FINITE_EXTENSION'
    operations=(('UNARY_FLOOR_FIRST',lambda:unary_union([floor,extra])),
                ('BINARY_FLOOR_FIRST',lambda:floor.union(extra)),
                ('BINARY_EXTENSION_FIRST',lambda:extra.union(floor)),
                ('UNARY_EXTENSION_FIRST',lambda:unary_union([extra,floor])))
    for name,op in operations:
        try:g=polygonal(op())
        except GEOSException:continue
        if not g.is_empty and g.is_valid and g.geom_type in ('Polygon','MultiPolygon') and contains_floor(g,floor):return g,name
    return floor,'EXACT_FLOOR_FALLBACK'
