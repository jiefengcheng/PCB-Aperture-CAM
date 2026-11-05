"""Exact integer-grid partition for polygons a single Gerber cut-in cannot encode.

The ordinary cut-in path is retained whenever it succeeds. The alternate only
changes serialization: signed boundary edges and doubled integer area must be
identical, and every positive triangle is retained, including minimum-grid ones.
"""
from collections import Counter
import hashlib
import math

from shapely import STRtree, constrained_delaunay_triangles, to_wkb
from shapely.geometry import Point, box
from shapely.geometry.polygon import orient


def _ring_points(ring, grid):
    result = []
    for x, y in ring.coords:
        point = []
        for value in (x, y):
            integer = round(value / grid)
            if not math.isfinite(value) or abs(value - integer * grid) > 4 * math.ulp(value):
                raise ValueError('PARTITION_REQUIRES_EXISTING_FILE_GRID')
            point.append(integer)
        result.append(tuple(point))
    return result


def _edges(points):
    return [(a, b) for a, b in zip(points, points[1:]) if a != b]


def _area2(points):
    return sum(a[0] * b[1] - a[1] * b[0] for a, b in _edges(points))


def _signed(edges):
    result = Counter()
    for a, b in edges:
        key = (a, b) if a < b else (b, a)
        result[key] += 1 if a < b else -1
    return {edge: count for edge, count in result.items() if count}


def _atomic_boundary(edges, vertices):
    points = sorted(vertices)
    tree = STRtree([Point(*point) for point in points])
    atomic = []
    for a, b in edges:
        dx, dy = b[0] - a[0], b[1] - a[1]
        length2 = dx * dx + dy * dy
        indices = tree.query(box(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
        split = []
        for index in indices:
            point = points[int(index)]
            px, py = point[0] - a[0], point[1] - a[1]
            projection = px * dx + py * dy
            if dx * py == dy * px and 0 <= projection <= length2:
                split.append((projection, point))
        ordered = [point for _, point in sorted(split)]
        if not ordered or ordered[0] != a or ordered[-1] != b:
            raise ValueError('PARTITION_BOUNDARY_COVERAGE_INCOMPLETE')
        atomic.extend(_edges(ordered))
    return _signed(atomic)


def verify_partition(shape, pieces, *, grid_mm):
    source = orient(shape, sign=1.)
    source_rings = [_ring_points(ring, grid_mm) for ring in [source.exterior, *source.interiors]]
    source_vertices = {point for ring in source_rings for point in ring}
    source_edges = [edge for ring in source_rings for edge in _edges(ring)]
    source_area = sum(_area2(ring) for ring in source_rings)
    if source_area <= 0:
        raise ValueError('PARTITION_SOURCE_AREA_INVALID')
    result_edges, result_area = [], 0
    for piece in pieces:
        if piece.geom_type != 'Polygon' or not piece.is_valid or piece.is_empty or piece.interiors:
            raise ValueError('PARTITION_PART_INVALID')
        ring = _ring_points(orient(piece, sign=1.).exterior, grid_mm)
        if not set(ring) <= source_vertices:
            raise ValueError('PARTITION_INTRODUCED_VERTEX')
        area = _area2(ring)
        if area <= 0:
            raise ValueError('PARTITION_POSITIVE_PART_LOST')
        result_area += area
        result_edges.extend(_edges(ring))
    if result_area != source_area:
        raise ValueError('PARTITION_INTEGER_AREA_CHANGED')
    remainder = _signed(result_edges)
    if any(abs(count) != 1 for count in remainder.values()):
        raise ValueError('PARTITION_BOUNDARY_MULTIPLICITY_CHANGED')
    directed = [(a, b) if count == 1 else (b, a) for (a, b), count in remainder.items()]
    expected = _atomic_boundary(source_edges, source_vertices)
    actual = _atomic_boundary(directed, source_vertices)
    if actual != expected:
        raise ValueError('PARTITION_EXACT_BOUNDARY_CHANGED')
    return dict(status='EXACT_INTEGER_GRID_PARTITION', grid_mm=grid_mm,
                source_sha256=hashlib.sha256(to_wkb(shape)).hexdigest(),
                doubled_integer_area=source_area, parts=len(pieces),
                signed_atomic_boundary_edges=len(expected),
                new_vertices=0, dropped_positive_parts=0,
                proof='Exact signed boundary and doubled integer area equality; no tolerance allowance')


def partition(shape, *, grid_mm):
    if not math.isfinite(grid_mm) or grid_mm <= 0:
        raise ValueError('PARTITION_GRID_INVALID')
    if shape.geom_type != 'Polygon' or shape.is_empty or not shape.is_valid:
        raise ValueError('PARTITION_SOURCE_INVALID')
    raw = constrained_delaunay_triangles(shape)
    pieces = sorted(list(raw.geoms), key=to_wkb)
    vertices = len(shape.exterior.coords) + sum(len(ring.coords) for ring in shape.interiors)
    if not pieces or len(pieces) > 4 * vertices + 8:
        raise ValueError('PARTITION_RESOURCE_OR_COVERAGE_INVALID')
    proof = verify_partition(shape, pieces, grid_mm=grid_mm)
    return pieces, proof


def contours(shape, bridge, *, grid_mm):
    if shape.geom_type != 'Polygon' or shape.is_empty or not shape.is_valid:
        raise ValueError('PARTITION_SOURCE_INVALID')
    for ring in [shape.exterior, *shape.interiors]:
        _ring_points(ring, grid_mm)
    from src.validator import Unsupported
    material_changed=False
    try:
        points = bridge(shape)
        from src.gerber_image import contour
        from .native_material import equality
        native=[(round(x/grid_mm)*grid_mm,round(y/grid_mm)*grid_mm)for x,y in points]
        try:
            exact=equality(shape,contour(native+[native[0]]),grid_mm=grid_mm)
        except ValueError:
            material_changed=True
            raise
        return [(shape, points)], dict(status='ORIGINAL_CUT_IN_ENCODING',native_material=exact)
    except (ValueError, Unsupported) as error:
        bridge_error = str(error)
    if material_changed:
        from .exact_cut_in import bridge as exact_bridge
        try:
            points,exact=exact_bridge(shape,grid_mm=grid_mm)
            return [(shape,points)],dict(status='EXACT_AXIAL_CUT_IN_ENCODING',original_cut_in_rejection=bridge_error,native_material=exact)
        except(ValueError,Unsupported):pass
    pieces, proof = partition(shape, grid_mm=grid_mm)
    proof['original_cut_in_rejection'] = bridge_error
    from src.gerber_image import contour
    from src.native_grid_reference import fidelity
    result = []
    for piece in pieces:
        points = [tuple(point) for point in orient(piece, sign=1.).exterior.coords[:-1]]
        restored = contour(points + [points[0]])
        fidelity(piece, restored)
        result.append((piece, points))
    return result, proof
