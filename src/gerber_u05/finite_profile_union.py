"""Strict saved-floor unions of finite polygonal supplemental copper."""
from shapely.geometry import Polygon,MultiPolygon
from shapely import get_precision,get_srid
from shapely.ops import unary_union
from shapely.errors import GEOSException


def assembly_union(parts, *, recoveries=None, label=None, validate_result=False):
    """Retain the normal local union; recover a kernel failure with exact overlays.

    Only an exceptional union pays for the fallback and area-custody checks.
    No operand is snapped, buffered, repaired or omitted. If neither ordered
    binary assembly retains every area component, preserve the original error.
    """
    parts=list(parts)
    try:
        raw=unary_union(parts);result=polygonal(raw)
        custody=result is raw or all(g.difference(result).area==0 for g in parts)
    except GEOSException as error:failure=error
    else:
        if custody and (not validate_result or (result.is_valid and result.geom_type in ('Polygon','MultiPolygon'))):
            if result is not raw and recoveries is not None:
                recoveries.append(dict(label=label,method='EXACT_CONTAINED_OVERLAY_FACES',
                    operands=len(parts),all_operand_area_retained=True,coordinate_adjustment=False))
            return result
        failure=GEOSException(('INVALID_LOCAL_UNION_RESULT:'if custody else'LOCAL_UNION_AREA_CUSTODY:')+result.geom_type)
    if not parts or any(not g.is_valid or g.geom_type not in ('Polygon','MultiPolygon') for g in parts):
        raise failure
    for name,ordered in (('BINARY_INPUT_ORDER',parts),('BINARY_REVERSE_ORDER',parts[::-1])):
        try:
            result=ordered[0]
            for part in ordered[1:]:result=result.union(part)
            if (result.is_empty or not result.is_valid or result.geom_type not in ('Polygon','MultiPolygon')
                    or any(g.difference(result).area!=0 for g in parts)):
                continue
        except GEOSException:
            continue
        if recoveries is not None:
            recoveries.append(dict(label=label,method=name,operands=len(parts),
                original_error=str(failure),all_operand_area_retained=True,
                coordinate_adjustment=False))
        return result
    raise failure


def polygonal(g):
    """Discard overlay-only lines/points; never snap, buffer or simplify copper."""
    if g.geom_type=='Polygon':return g
    if g.geom_type=='MultiPolygon':return _contained_shells(g)
    parts=[]
    def collect(x):
        if x.geom_type=='Polygon':parts.append(x)
        elif hasattr(x,'geoms'):
            for y in x.geoms:collect(y)
        else:
            if x.area!=0:raise ValueError('NONPOLYGONAL_NONZERO_AREA_COPPER')
    collect(g)
    return _contained_shells(unary_union(parts)) if parts else Polygon()


def _contained_shells(g):
    """Remove only exactly covered redundant faces of an invalid overlay.

    GEOS can emit a valid polygon plus a duplicate shell nested inside it.
    Keep original face coordinates and prove complete coverage before omitting
    any face. Invalid rings, overlaps without containment and holes are not
    repaired by this operation.
    """
    if g.geom_type!='MultiPolygon' or g.is_valid:return g
    faces=list(g.geoms)
    if any(not face.is_valid for face in faces):return g
    kept=[];covered=[]
    for i in sorted(range(len(faces)),key=lambda i:(-faces[i].area,i)):
        a=faces[i];ax,ay,bx,by=a.bounds
        container=next((j for j in kept
            if faces[j].bounds[0]<=ax and faces[j].bounds[1]<=ay
            and faces[j].bounds[2]>=bx and faces[j].bounds[3]>=by
            and faces[j].covers(a)),None)
        if container is None:kept.append(i)
        else:covered.append(i)
    if not covered:return g
    kept.sort()
    result=faces[kept[0]] if len(kept)==1 else MultiPolygon([faces[i]for i in kept])
    if get_precision(result)!=get_precision(g) or get_srid(result)!=get_srid(g):return g
    return result if result.is_valid else g


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
