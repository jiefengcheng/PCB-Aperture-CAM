"""Construct optional square-guided recesses against real nearby copper."""
from __future__ import annotations
from shapely.geometry import Point


def square_guided_recess(site, radius, obstacles, settings):
    """Recess optional growth on conflicting square-facing sides, then clip.

    Directions come from nearest points of actual applicable source/live copper.
    Every consumed side is logged. No EDIT direction or target contour is read.
    """
    from shapely.ops import nearest_points
    from src.crop_square_neighbor_experiment import construct, square_facing_lobe, retain_attached
    core=site['core'];center=site['center'];kernel=settings.kernel()
    result=construct(core,center,radius,obstacles,square_enabled=False,settings=kernel)
    envelope=result['envelope'];optional=envelope.difference(core);consumed=[]
    conflicts=[]
    for row in obstacles:
        excluded=row['geometry'].buffer(settings.construction_gap,quad_segs=settings.qsegs)
        if row.get('port_zone') is not None:excluded=excluded.difference(row['port_zone'])
        area=optional.intersection(excluded).area
        if area>settings.event_epsilon:conflicts.append((area,row['source_id'],excluded))
    # One primary recess, selected by greatest real conflict area, stable ID tie.
    # Other obstacles still clip ordinarily; do not replace every arc by a square.
    preferred=site.get('square_recess_neighbor_id')
    if preferred:
        conflicts=[item for item in conflicts if item[1]==preferred]
        if not conflicts:raise ValueError('OWNER_RECESS_NEIGHBOR_HAS_NO_ACTUAL_CONFLICT')
    if conflicts:
        area,source_id,excluded=sorted(conflicts,key=lambda item:(-item[0],item[1]))[0]
        point=nearest_points(Point(*center),excluded)[1]
        if point.distance(Point(*center))>1e-12:
            lobe,side=square_facing_lobe(envelope,result['square'],center,(point.x,point.y))
            removed=optional.intersection(lobe)
            if removed.area>settings.event_epsilon:
                consumed.append({'source_id':source_id,'square_side':side,'conflict_area_mm2':area,'removed_optional_area_mm2':removed.area,'direction_point_mm':[point.x,point.y]})
                optional=optional.difference(lobe)
    # Square guides only optional recesses. Actual copper always sets hard gap.
    candidate,_=retain_attached(optional.intersection(result['candidate']),core,kernel)
    return candidate,consumed

