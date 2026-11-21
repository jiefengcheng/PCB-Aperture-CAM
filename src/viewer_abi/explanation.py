"""Read-only source/candidate difference for a selection-bound explanation."""
from shapely import from_wkb
from shapely.geometry import GeometryCollection
from .publisher import bounds, digest, path_data
from .live import display


def area_artwork(shape):
    """SVG fills describe area; GEOS may also return zero-area difference boundaries."""
    polygons = []
    def visit(g):
        if g.geom_type == 'Polygon' and not g.is_empty:
            polygons.append(g)
        elif g.geom_type in ('MultiPolygon', 'GeometryCollection'):
            for part in g.geoms: visit(part)
        elif g.area != 0:
            raise ValueError('EXPLANATION_UNSUPPORTED_AREA')
    visit(shape)
    if not polygons: return None
    area = GeometryCollection(polygons)
    return dict(path=path_data(area), bounds=bounds(area))


def growth_comparison(original_wkb, current_wkb, selected, *, summary, snapshot_note):
    original, current = from_wkb(original_wkb), from_wkb(current_wkb)
    for shape in (original, current):
        if shape.is_empty or not shape.is_valid or shape.area <= 0:
            raise ValueError('EXPLANATION_INVALID_AREA')
    derivative, error = display(current)
    if derivative is None or path_data(derivative) != selected['path']:
        raise ValueError('EXPLANATION_CURRENT_BODY_NOT_DISPLAYED')

    added, removed = current.difference(original), original.difference(current)
    return dict(schema=1, selectedPathSHA256=digest(selected['path'].encode()),
                originalWkbSHA256=digest(original_wkb), currentWkbSHA256=digest(current_wkb),
                original=area_artwork(original), added=area_artwork(added), removed=area_artwork(removed),
                addedAreaMM2=added.area, removedAreaMM2=removed.area,
                displayHausdorffMM=error, summary=summary, snapshotNote=snapshot_note)
