"""Independent round-trip checks for the ORG WKB-to-SVG display derivative."""
from __future__ import annotations

import math
import re

from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Polygon
from shapely.ops import polygonize, unary_union


_TOKEN = re.compile(r"[MLZ]|-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def parse_linear_svg_rings(path: str) -> list[list[tuple[float, float]]]:
    """Parse the deliberately small absolute M/L/Z dialect emitted by svg_path."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError("SVG path must be a non-empty string")
    tokens = _TOKEN.findall(path)
    if not tokens:
        raise ValueError("SVG path has no commands or coordinates")
    residue = _TOKEN.sub("", path)
    if residue.strip(" ,\t\r\n"):
        raise ValueError("SVG path contains unsupported syntax")

    rings: list[list[tuple[float, float]]] = []
    index = 0
    while index < len(tokens):
        if tokens[index] != "M":
            raise ValueError("each SVG subpath must start with absolute M")
        index += 1
        points: list[tuple[float, float]] = []
        command = "M"
        while index < len(tokens) and tokens[index] != "M":
            token = tokens[index]
            if token in ("L", "Z"):
                command = token
                index += 1
                if command == "Z":
                    break
                continue
            if command not in ("M", "L") or index + 1 >= len(tokens):
                raise ValueError("SVG coordinate pair is incomplete")
            x, y = float(tokens[index]), float(tokens[index + 1])
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("SVG coordinates must be finite")
            points.append((x, y))
            index += 2
            command = "L"
        if command != "Z" or len(points) < 4 or points[0] != points[-1]:
            raise ValueError("SVG polygon rings must be closed with at least four points")
        rings.append(points)
    if not rings:
        raise ValueError("SVG path contains no closed rings")
    return rings


def geometry_from_evenodd_path(path: str):
    """Reconstruct the filled planar set using the explicit SVG even-odd rule."""
    rings = parse_linear_svg_rings(path)
    polygons = [Polygon(ring) for ring in rings]
    if any(not polygon.is_valid or polygon.area <= 0 for polygon in polygons):
        raise ValueError("SVG path contains an invalid or zero-area ring")
    faces = list(polygonize(unary_union([LineString(ring) for ring in rings])))
    selected = [face for face in faces
                if sum(ring.covers(face.representative_point()) for ring in polygons) % 2 == 1]
    if not selected:
        raise ValueError("SVG even-odd path has no filled area")
    result = unary_union(selected)
    if not result.is_valid or result.is_empty:
        raise ValueError("SVG even-odd reconstruction is invalid or empty")
    return result


def topology_counts(geometry) -> dict[str, int]:
    polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
    if any(polygon.geom_type != "Polygon" for polygon in polygons):
        raise ValueError("only polygonal WKB is supported by the SVG path dialect")
    return {
        "polygon_components": len(polygons),
        "interior_rings": sum(len(polygon.interiors) for polygon in polygons),
    }


def compare_path_to_wkb(source, path: str) -> dict:
    """Measure an SVG path against source WKB without trusting its digest alone."""
    expected = source
    actual = geometry_from_evenodd_path(path)
    expected_topology = topology_counts(expected)
    actual_topology = topology_counts(actual)
    delta = expected.symmetric_difference(actual)
    expected_bounds, actual_bounds = expected.bounds, actual.bounds
    bound_delta = max(abs(a - b) for a, b in zip(expected_bounds, actual_bounds))
    return {
        "source_geometry_type": expected.geom_type,
        "svg_geometry_type": actual.geom_type,
        "source_area_mm2": expected.area,
        "svg_area_mm2": actual.area,
        "symmetric_difference_area_mm2": delta.area,
        "relative_symmetric_difference": delta.area / expected.area if expected.area else None,
        "hausdorff_distance_mm": expected.hausdorff_distance(actual),
        "boundary_hausdorff_distance_mm": expected.boundary.hausdorff_distance(actual.boundary),
        "max_bounds_delta_mm": bound_delta,
        "source_topology": expected_topology,
        "svg_topology": actual_topology,
        "topology_counts_match": expected_topology == actual_topology,
        "svg_valid": actual.is_valid,
        "source_valid": expected.is_valid,
        "svg_ring_count": len(parse_linear_svg_rings(path)),
    }


def stored_round_trip_pass(metrics: dict, coordinate_decimals: int) -> bool:
    coordinate_error = math.sqrt(2) * 0.5 * 10 ** (-coordinate_decimals)
    return (metrics["svg_valid"] and metrics["topology_counts_match"] and
            metrics["hausdorff_distance_mm"] <= coordinate_error * (1 + 1e-6) and
            metrics["max_bounds_delta_mm"] <= 0.5 * 10 ** (-coordinate_decimals) * (1 + 1e-6))


def simplified_round_trip_status(metrics: dict, tolerance_mm: float,
                                 coordinate_decimals: int) -> dict:
    coordinate_error = math.sqrt(2) * 0.5 * 10 ** (-coordinate_decimals)
    observed_limit = tolerance_mm + coordinate_error
    passes = (metrics["svg_valid"] and metrics["topology_counts_match"] and
              metrics["hausdorff_distance_mm"] <= observed_limit * (1 + 1e-6))
    return {
        "status": "PASS_OBSERVED_BOUNDED" if passes else "NOT_ESTABLISHED",
        "observed_hausdorff_limit_mm": observed_limit,
        "warning": "The simplification parameter is not asserted as a library guarantee; this is measured evidence for the pinned paths only.",
    }
