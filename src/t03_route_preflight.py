"""Bounded, deterministic T03 route candidate primitives for audited preflight.

The module separates candidate enumeration, path construction, and source-scene
verification.  The real C2 search is deliberately not run by this module's CLI;
``verify_scene`` only validates the frozen, hash-bound inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from itertools import product
import json
import math
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

from shapely import to_wkb
from shapely.geometry import LineString, Point
from shapely.wkb import loads as load_wkb


OFFSETS_MM = tuple(Decimal(v) for v in ("-0.25", "-0.15", "-0.05", "0", "0.05", "0.15", "0.25"))
REGULAR_PORT_STEP_MM = Decimal("0.025")
MAX_EXTENSION_MM = Decimal("0.500")
MAX_ADDED_SPANS = 4
MAX_CANDIDATES = 10_000
PORT_TRANSITION_BUFFER_MM = 0.12010
SOURCE_SURFACE_FLOOR_MM = 0.02000
SOURCE_SURFACE_TARGET_MM = 0.02002
WIDTH_MM = 0.10008
SOURCE_GEOMETRY_TOLERANCE_MM = 0.00001
ROUTE_TESSELLATION_TOLERANCE_MM = 0.00001
BUFFER_TESSELLATION_TOLERANCE_MM = 0.00001
PRECISION_GRID_MM = 0.000001
SOURCE_SPAN_UNION_TOLERANCE_MM2 = 1e-15
# A round-buffer boundary is tessellated with maximum sagitta delta. The
# symmetric difference between two such representations is bounded by the
# full circular boundary band of width 2*delta: pi((r+delta)^2-(r-delta)^2)
# = 4*pi*r*delta. Keep this limit local to one native-source join.
_BUFFER_RADIUS_MM = WIDTH_MM / 2.0
SOURCE_SPAN_JOIN_RESIDUAL_MAX_MM2 = (
    4.0 * math.pi * _BUFFER_RADIUS_MM * BUFFER_TESSELLATION_TOLERANCE_MM
)


class PreflightError(ValueError):
    """Raised when input geometry cannot be accepted without guessing."""


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


@dataclass(frozen=True)
class Primitive:
    source_id: str
    kind: str
    start: tuple[float, float]
    end: tuple[float, float]
    width_mm: float
    mid: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"segment", "arc"}:
            raise PreflightError(f"UNSUPPORTED_PRIMITIVE:{self.kind}")
        if self.width_mm != WIDTH_MM:
            raise PreflightError(f"WIDTH_MISMATCH:{self.source_id}:{self.width_mm}")
        if self.kind == "arc" and self.mid is None:
            raise PreflightError(f"ARC_MIDPOINT_MISSING:{self.source_id}")

    @property
    def arc(self) -> tuple[tuple[float, float], float, float, float] | None:
        if self.kind != "arc":
            return None
        assert self.mid is not None
        ax, ay = self.start
        mx, my = self.mid
        bx, by = self.end
        det = 2.0 * (ax * (my - by) + mx * (by - ay) + bx * (ay - my))
        if abs(det) <= 1e-15:
            raise PreflightError(f"DEGENERATE_ARC:{self.source_id}")
        a2 = ax * ax + ay * ay
        m2 = mx * mx + my * my
        b2 = bx * bx + by * by
        cx = (a2 * (my - by) + m2 * (by - ay) + b2 * (ay - my)) / det
        cy = (a2 * (bx - mx) + m2 * (ax - bx) + b2 * (mx - ax)) / det
        a0 = math.atan2(ay - cy, ax - cx)
        am = math.atan2(my - cy, mx - cx)
        a1 = math.atan2(by - cy, bx - cx)
        forward = (a1 - a0) % (2 * math.pi)
        sweep = forward if (am - a0) % (2 * math.pi) <= forward else forward - 2 * math.pi
        radius = math.hypot(ax - cx, ay - cy)
        if not math.isfinite(radius) or radius <= 0 or abs(sweep) <= 1e-15:
            raise PreflightError(f"DEGENERATE_ARC:{self.source_id}")
        return (cx, cy), radius, a0, sweep

    @property
    def length_mm(self) -> float:
        arc = self.arc
        if arc is None:
            return math.dist(self.start, self.end)
        return arc[1] * abs(arc[3])

    def point(self, fraction: float) -> tuple[float, float]:
        if not 0.0 <= fraction <= 1.0:
            raise PreflightError("PRIMITIVE_FRACTION_OUT_OF_RANGE")
        arc = self.arc
        if arc is None:
            return (
                self.start[0] + (self.end[0] - self.start[0]) * fraction,
                self.start[1] + (self.end[1] - self.start[1]) * fraction,
            )
        (cx, cy), radius, a0, sweep = arc
        angle = a0 + sweep * fraction
        return cx + radius * math.cos(angle), cy + radius * math.sin(angle)

    def tangent(self, fraction: float) -> tuple[float, float]:
        arc = self.arc
        if arc is None:
            dx, dy = self.end[0] - self.start[0], self.end[1] - self.start[1]
        else:
            _, _, a0, sweep = arc
            angle = a0 + sweep * fraction
            dx, dy = -math.sin(angle) * sweep, math.cos(angle) * sweep
        norm = math.hypot(dx, dy)
        if norm <= 1e-15:
            raise PreflightError(f"ZERO_TANGENT:{self.source_id}")
        return dx / norm, dy / norm


@dataclass(frozen=True)
class SourcePath:
    primitives: tuple[Primitive, ...]
    initial_patch_end_mm: float
    continuity_tolerance_mm: float = 1e-9

    def __post_init__(self) -> None:
        if not self.primitives:
            raise PreflightError("EMPTY_SOURCE_PATH")
        for left, right in zip(self.primitives, self.primitives[1:]):
            if math.dist(left.end, right.start) > self.continuity_tolerance_mm:
                raise PreflightError(f"SOURCE_CHAIN_GAP:{left.source_id}:{right.source_id}")
        if not 0.0 < self.initial_patch_end_mm < self.length_mm:
            raise PreflightError("INVALID_INITIAL_PATCH_BOUNDARY")

    @property
    def length_mm(self) -> float:
        return sum(p.length_mm for p in self.primitives)

    @property
    def boundaries_mm(self) -> tuple[float, ...]:
        total = 0.0
        result = []
        for primitive in self.primitives[:-1]:
            total += primitive.length_mm
            result.append(total)
        return tuple(result)

    def primitive_at(self, distance_mm: float) -> tuple[int, Primitive, float, float]:
        if not 0.0 <= distance_mm <= self.length_mm:
            raise PreflightError("PATH_DISTANCE_OUT_OF_RANGE")
        total = 0.0
        for index, primitive in enumerate(self.primitives):
            nxt = total + primitive.length_mm
            if distance_mm <= nxt or index == len(self.primitives) - 1:
                local = min(max(distance_mm - total, 0.0), primitive.length_mm)
                fraction = local / primitive.length_mm
                return index, primitive, fraction, total
            total = nxt
        raise PreflightError("PATH_LOOKUP_FAILED")

    def point_at(self, distance_mm: float) -> tuple[float, float]:
        _, primitive, fraction, _ = self.primitive_at(distance_mm)
        return primitive.point(fraction)

    def tangent_at(self, distance_mm: float) -> tuple[float, float]:
        _, primitive, fraction, _ = self.primitive_at(distance_mm)
        return primitive.tangent(fraction)


@dataclass(frozen=True)
class CutPort:
    distance_mm: Decimal
    extension_mm: Decimal
    source_id: str
    eligible: bool
    reason: str | None


def enumerate_cut_ports(
    path: SourcePath,
    *,
    step_mm: Decimal = REGULAR_PORT_STEP_MM,
    max_extension_mm: Decimal = MAX_EXTENSION_MM,
    transition_buffer_mm: float = PORT_TRANSITION_BUFFER_MM,
    max_added_spans: int = MAX_ADDED_SPANS,
) -> tuple[CutPort, ...]:
    """List regular and exact-junction cut ports in stable arclength order.

    Junction ports are retained in the report but fail the transition-buffer
    predicate. This makes the finite search domain auditable without treating
    a source-span transition as a valid cut by default.
    """
    if step_mm <= 0 or max_extension_mm < 0:
        raise PreflightError("INVALID_PORT_GRID")
    stations: dict[Decimal, str] = {}
    n = int(max_extension_mm / step_mm)
    for i in range(n + 1):
        extension = min(step_mm * i, max_extension_mm)
        stations[extension] = "REGULAR"
    for boundary in path.boundaries_mm:
        if boundary > path.initial_patch_end_mm:
            ext = Decimal(str(boundary - path.initial_patch_end_mm)).quantize(Decimal("0.000000001"))
            if 0 <= ext <= max_extension_mm:
                stations[ext] = "SOURCE_JUNCTION"

    out: list[CutPort] = []
    boundaries = (0.0, *path.boundaries_mm, path.length_mm)
    for extension, _station_kind in sorted(stations.items()):
        absolute = Decimal(str(path.initial_patch_end_mm)) + extension
        absolute_float = float(absolute)
        if absolute_float > path.length_mm + 1e-9:
            continue
        idx, primitive, _, primitive_start = path.primitive_at(min(absolute_float, path.length_mm))
        span_count = sum(1 for b in path.boundaries_mm if path.initial_patch_end_mm < b < absolute_float)
        reason = None
        if span_count > max_added_spans:
            reason = "ADDED_SOURCE_SPAN_CAP"
        else:
            left_transition = absolute_float - primitive_start
            right_transition = primitive.length_mm - left_transition
            if min(left_transition, right_transition) + 1e-12 < transition_buffer_mm:
                reason = "TRANSITION_BUFFER"
        out.append(CutPort(absolute, extension, primitive.source_id, reason is None, reason))
    return tuple(out)


def offset_tuples() -> tuple[tuple[Decimal, Decimal, Decimal], ...]:
    return tuple(product(OFFSETS_MM, repeat=3))


def candidate_order_key(port: CutPort, offsets: tuple[Decimal, Decimal, Decimal]) -> tuple[Any, ...]:
    return (
        port.extension_mm,
        max(abs(v) for v in offsets),
        sum(abs(v) for v in offsets),
        offsets[0], offsets[1], offsets[2], port.source_id,
    )


def enumerate_candidate_specs(path: SourcePath) -> tuple[tuple[CutPort, tuple[Decimal, Decimal, Decimal]], ...]:
    ports = [p for p in enumerate_cut_ports(path) if p.eligible]
    candidates = [(port, offsets) for port in ports for offsets in offset_tuples()]
    candidates.sort(key=lambda item: candidate_order_key(item[0], item[1]))
    if len(candidates) > MAX_CANDIDATES:
        raise PreflightError("CANDIDATE_BUDGET_EXCEEDED")
    return tuple(candidates)


def _smoothstep(u: float) -> float:
    return 3.0 * u * u - 2.0 * u * u * u


def _offset_at(s: float, values: tuple[float, float, float]) -> float:
    knots = (0.0, 0.25, 0.5, 0.75, 1.0)
    vals = (0.0, *values, 0.0)
    segment = min(3, int(s / 0.25))
    u = min(1.0, max(0.0, (s - knots[segment]) / 0.25))
    h = _smoothstep(u)
    return (1.0 - h) * vals[segment] + h * vals[segment + 1]


def _bounded_source_span_fraction(start_mm: float, stop_mm: float, length_mm: float) -> float:
    """Map a bounded source span to [0, 1] without masking invalid stations.

    At a full primitive endpoint, subtracting the cumulative start from the
    accumulated endpoint can produce a span one ULP larger than the primitive
    length. Equality with the computed endpoint proves that this is endpoint
    rounding, so return the exact endpoint fraction. Partial or out-of-range
    stations retain the strict fraction check.
    """
    if not math.isfinite(length_mm) or length_mm <= 0.0:
        raise PreflightError("INVALID_PRIMITIVE_LENGTH")
    primitive_end_mm = start_mm + length_mm
    if stop_mm == primitive_end_mm:
        return 1.0
    fraction = (stop_mm - start_mm) / length_mm
    if not 0.0 <= fraction <= 1.0:
        raise PreflightError("PRIMITIVE_FRACTION_OUT_OF_RANGE")
    return fraction


def construct_candidate_centerline(
    path: SourcePath,
    cut_distance_mm: float,
    offsets_mm: tuple[float, float, float],
    *,
    max_sagitta_mm: float = ROUTE_TESSELLATION_TOLERANCE_MM,
) -> LineString:
    """Build a deterministic sampled offset curve from exact line/arc sources.

    The source path is analytic. Sampling uses a curvature bound combining
    source-arc curvature and the cubic-offset second derivative; inability to
    meet the requested tolerance within fixed resource limits fails closed.
    """
    if len(offsets_mm) != 3 or any(abs(v) > 0.25 for v in offsets_mm):
        raise PreflightError("OFFSET_OUT_OF_BOUNDS")
    if cut_distance_mm <= 0 or cut_distance_mm > path.length_mm:
        raise PreflightError("INVALID_CUT_DISTANCE")
    start = path.point_at(0.0)
    end = path.point_at(cut_distance_mm)
    chord = (end[0] - start[0], end[1] - start[1])
    chord_length = math.hypot(*chord)
    if chord_length <= 1e-12:
        raise PreflightError("ZERO_ENDPOINT_CHORD")
    normal = (-chord[1] / chord_length, chord[0] / chord_length)

    active: list[tuple[int, Primitive, float, float, float]] = []
    cumulative = 0.0
    max_curvature = 0.0
    for index, primitive in enumerate(path.primitives):
        length = primitive.length_mm
        primitive_end = cumulative + length
        stop = min(cut_distance_mm, primitive_end)
        if stop > cumulative:
            fraction_end = _bounded_source_span_fraction(cumulative, stop, length)
            active.append((index, primitive, cumulative, stop, fraction_end))
            arc = primitive.arc
            if arc:
                max_curvature = max(max_curvature, 1.0 / arc[1])
        cumulative += length
        if cumulative >= cut_distance_mm:
            break
    route_length = cut_distance_mm
    max_delta = 0.5  # Difference between adjacent interior offset values.
    max_second = max_curvature + 96.0 * max_delta / (route_length * route_length)
    step_bound = math.sqrt(8.0 * max_sagitta_mm / max(max_second, 1e-12))
    if not math.isfinite(step_bound) or step_bound <= 0:
        raise PreflightError("TESSELLATION_BOUND_FAILED")
    coords: list[tuple[float, float]] = []
    max_samples = 200_000
    for _, primitive, primitive_start, primitive_stop, fraction_end in active:
        span = primitive_stop - primitive_start
        pieces = max(1, math.ceil(span / step_bound))
        for j in range(pieces + 1):
            if coords and j == 0:
                continue
            d = primitive_start + span * j / pieces
            fraction = min(fraction_end, max(0.0, (d - primitive_start) / primitive.length_mm))
            px, py = primitive.point(fraction)
            s = d / route_length
            delta = _offset_at(s, offsets_mm)
            coords.append((px + delta * normal[0], py + delta * normal[1]))
            if len(coords) > max_samples:
                raise PreflightError("TESSELLATION_RESOURCE_CAP")
    if len(coords) < 2 or any(not all(math.isfinite(v) for v in p) for p in coords):
        raise PreflightError("INVALID_GENERATED_CENTERLINE")
    line = LineString(coords)
    if line.is_empty or not line.is_valid or line.length <= 0:
        raise PreflightError("INVALID_GENERATED_CENTERLINE")
    if math.dist(line.coords[0], start) > 1e-9 or math.dist(line.coords[-1], end) > 1e-9:
        raise PreflightError("ENDPOINT_DISPLACEMENT")
    return line


def construct_candidate_centerline_source_spans(
    path: SourcePath,
    cut_distance_mm: float,
    offsets_mm: tuple[float, float, float],
    *,
    max_sagitta_mm: float = ROUTE_TESSELLATION_TOLERANCE_MM,
) -> tuple[LineString, dict[str, LineString]]:
    """Return the canonical route plus exact sampled sub-lines per source span.

    Sampling and station math deliberately mirror ``construct_candidate_centerline``.
    The result is compared byte-for-byte in tests so this attribution helper cannot
    silently create a different route. A cut inside a native primitive yields only
    the prefix through the selected cut port for that primitive.
    """
    line = construct_candidate_centerline(
        path, cut_distance_mm, offsets_mm, max_sagitta_mm=max_sagitta_mm
    )
    start = path.point_at(0.0)
    end = path.point_at(cut_distance_mm)
    chord = (end[0] - start[0], end[1] - start[1])
    chord_length = math.hypot(*chord)
    if chord_length <= 1e-12:
        raise PreflightError("ZERO_ENDPOINT_CHORD")
    normal = (-chord[1] / chord_length, chord[0] / chord_length)

    active: list[tuple[Primitive, float, float]] = []
    cumulative = 0.0
    max_curvature = 0.0
    for primitive in path.primitives:
        stop = min(cut_distance_mm, cumulative + primitive.length_mm)
        if stop > cumulative:
            active.append((primitive, cumulative, stop))
            arc = primitive.arc
            if arc:
                max_curvature = max(max_curvature, 1.0 / arc[1])
        cumulative += primitive.length_mm
        if cumulative >= cut_distance_mm:
            break
    max_second = max_curvature + 96.0 * 0.5 / (cut_distance_mm * cut_distance_mm)
    step_bound = math.sqrt(8.0 * max_sagitta_mm / max(max_second, 1e-12))
    if not math.isfinite(step_bound) or step_bound <= 0:
        raise PreflightError("TESSELLATION_BOUND_FAILED")
    spans: dict[str, LineString] = {}
    complete_coords: list[tuple[float, float]] = []
    max_samples = 200_000
    for primitive, primitive_start, primitive_stop in active:
        span_length = primitive_stop - primitive_start
        pieces = max(1, math.ceil(span_length / step_bound))
        span_coords: list[tuple[float, float]] = []
        for index in range(pieces + 1):
            if span_coords and index == 0:
                continue
            station = primitive_start + span_length * index / pieces
            fraction = min(1.0, max(0.0, (station - primitive_start) / primitive.length_mm))
            px, py = primitive.point(fraction)
            delta = _offset_at(station / cut_distance_mm, offsets_mm)
            point = (px + delta * normal[0], py + delta * normal[1])
            span_coords.append(point)
            if complete_coords and index == 0:
                continue
            complete_coords.append(point)
            if len(complete_coords) > max_samples:
                raise PreflightError("TESSELLATION_RESOURCE_CAP")
        if len(span_coords) < 2:
            raise PreflightError("INVALID_GENERATED_SOURCE_SPAN")
        spans[primitive.source_id] = LineString(span_coords)
    reconstructed = LineString(complete_coords)
    if not reconstructed.equals_exact(line, tolerance=0.0):
        raise PreflightError("SOURCE_SPAN_ATTRIBUTION_ROUTE_MISMATCH")
    return line, spans


def buffer_centerline(line: LineString, width_mm: float = WIDTH_MM):
    if width_mm != WIDTH_MM:
        raise PreflightError("WIDTH_CHANGE_FORBIDDEN")
    radius = width_mm / 2.0
    angle = math.acos(max(-1.0, min(1.0, 1.0 - BUFFER_TESSELLATION_TOLERANCE_MM / radius)))
    quad_segs = max(1, math.ceil(math.pi / (4.0 * angle)))
    geom = line.buffer(radius, quad_segs=quad_segs, cap_style="round", join_style="round")
    if geom.is_empty or not geom.is_valid:
        raise PreflightError("INVALID_COPPER_BUFFER")
    return geom, quad_segs


def candidate_source_copper_by_id(
    spans: dict[str, LineString],
    ordered_source_ids: list[str] | tuple[str, ...],
    cut_source_id: str,
    candidate_copper: Any,
    *,
    width_mm: float = WIDTH_MM,
) -> dict[str, Any]:
    """Attribute overlapping generated copper spans to their native source IDs.

    Each source keeps its own buffered span, including positive-area overlap at
    native joins. The selected cut source owns its generated prefix; its exact
    immutable downstream suffix is added by the archive materializer. The
    returned generated-span union must reproduce the canonical route copper.
    """
    from shapely.ops import unary_union

    ordered = list(ordered_source_ids)
    if not ordered or ordered[-1] != cut_source_id or set(spans) != set(ordered):
        raise PreflightError("CANDIDATE_SOURCE_SPAN_ORDER_INVALID")
    if len(ordered) < 2:
        raise PreflightError("CANDIDATE_SOURCE_SPAN_NO_REPLACEMENT")
    mapped: dict[str, Any] = {}
    for source_id in ordered:
        copper, _ = buffer_centerline(spans[source_id], width_mm)
        # Independent round caps can protrude by a few floating-point units at
        # source joins. Clip every sub-span to the canonical whole-route copper
        # before assigning the uncovered join residue deterministically.
        copper = copper.intersection(candidate_copper)
        if copper.is_empty or not copper.is_valid:
            raise PreflightError(f"CANDIDATE_SOURCE_SPAN_COPPER_INVALID:{source_id}")
        # Keep each generated span under its own source identity. Do not
        # subtract neighboring spans: their overlap is the source-bound
        # positive-area witness required at trace joins.
        mapped[source_id] = copper
    mapped_union = unary_union(list(mapped.values()))
    # Only canonical copper absent from the independently buffered source
    # spans may be considered. Localize each connected residual to one
    # declared source join, cap each join by the buffer-boundary tessellation
    # error bound, and assign it to that join's upstream source identity.
    uncovered = candidate_copper.difference(mapped_union)
    join_records: list[tuple[str, str, Point, Any]] = []
    for left_id, right_id in zip(ordered, ordered[1:]):
        left_xy = spans[left_id].coords[-1]
        right_xy = spans[right_id].coords[0]
        left_endpoint = Point(left_xy)
        right_endpoint = Point(right_xy)
        if left_endpoint.distance(right_endpoint) > SOURCE_GEOMETRY_TOLERANCE_MM:
            raise PreflightError(f"CANDIDATE_SOURCE_SPAN_JOIN_ENDPOINT_MISMATCH:{left_id}:{right_id}")
        join_xy = ((left_xy[0] + right_xy[0]) / 2.0, (left_xy[1] + right_xy[1]) / 2.0)
        join_point = Point(join_xy)
        join_region = join_point.buffer(
            width_mm / 2.0 + SOURCE_GEOMETRY_TOLERANCE_MM,
            quad_segs=256,
        )
        join_records.append((left_id, right_id, join_point, join_region))

    def polygon_parts(geom: Any) -> list[Any]:
        if geom.is_empty:
            return []
        if geom.geom_type == "Polygon":
            return [geom]
        parts: list[Any] = []
        for part in getattr(geom, "geoms", ()):
            parts.extend(polygon_parts(part))
        return parts

    assigned_by_join: dict[tuple[str, str], list[Any]] = {}
    for residual in polygon_parts(uncovered):
        representative = residual.representative_point()
        eligible = [
            record for record in join_records
            if record[3].covers(residual)
        ]
        if not eligible:
            raise PreflightError("CANDIDATE_SOURCE_SPAN_UNION_GAP_OUTSIDE_JOIN_NEIGHBORHOOD")
        # If broad neighboring join regions overlap, bind the component to the
        # nearest declared junction; ordered source IDs break exact ties.
        selected = min(
            eligible,
            key=lambda record: (representative.distance(record[2]), ordered.index(record[0])),
        )
        key = (selected[0], selected[1])
        assigned_by_join.setdefault(key, []).append(residual)

    for left_id, right_id, _join_point, _join_region in join_records:
        residual_parts = assigned_by_join.get((left_id, right_id), [])
        if not residual_parts:
            continue
        join_residual = unary_union(residual_parts)
        if join_residual.area > SOURCE_SPAN_JOIN_RESIDUAL_MAX_MM2:
            raise PreflightError(
                f"CANDIDATE_SOURCE_SPAN_JOIN_RESIDUAL_EXCEEDS_TOLERANCE:{left_id}:{right_id}"
            )
        mapped[left_id] = unary_union([mapped[left_id], join_residual])
    mapped_union = unary_union(list(mapped.values()))
    if (
        set(mapped) != set(ordered)
        or mapped_union.symmetric_difference(candidate_copper).area > SOURCE_SPAN_UNION_TOLERANCE_MM2
    ):
        raise PreflightError("CANDIDATE_SOURCE_SPAN_COPPER_UNION_MISMATCH")
    return mapped


def verify_candidate_copper(
    centerline: LineString,
    copper,
    obstacles: Iterable[dict[str, Any]],
    *,
    width_mm: float = WIDTH_MM,
    hard_floor_mm: float = SOURCE_SURFACE_FLOOR_MM,
    construction_target_mm: float = SOURCE_SURFACE_TARGET_MM,
    numeric_tolerance_mm: float = SOURCE_GEOMETRY_TOLERANCE_MM,
    area_tolerance_mm2: float = PRECISION_GRID_MM * PRECISION_GRID_MM,
) -> dict[str, Any]:
    """Fail-closed finite-width clearance check for a supplied test candidate.

    Each obstacle must be classified as ``protected``, ``writable`` or
    ``attachment_exception``. An attachment exception must include the exact
    allowed-contact geometry; only that area is removed from the obstacle
    before clearance is measured. This function does not infer net intent or
    prove that the classification is complete; production callers must provide
    a source-bound exhaustive obstacle partition before invoking it.
    """
    if width_mm != WIDTH_MM:
        raise PreflightError("WIDTH_CHANGE_FORBIDDEN")
    if not centerline.is_valid or centerline.is_empty or centerline.geom_type != "LineString":
        raise PreflightError("INVALID_CANDIDATE_CENTERLINE")
    if copper.is_empty or not copper.is_valid or copper.geom_type not in {"Polygon", "MultiPolygon"}:
        raise PreflightError("INVALID_CANDIDATE_COPPER")
    expected_copper, quad_segs = buffer_centerline(centerline, width_mm)
    if copper.symmetric_difference(expected_copper).area > area_tolerance_mm2:
        raise PreflightError("CANDIDATE_WIDTH_OR_BUFFER_MISMATCH")

    observations: list[dict[str, Any]] = []
    identities: set[str] = set()
    for obstacle in obstacles:
        if not isinstance(obstacle, dict) or not obstacle.get("source_id"):
            raise PreflightError("UNIDENTIFIED_SCENE_OBSTACLE")
        identity = obstacle["source_id"]
        if identity in identities:
            raise PreflightError(f"DUPLICATE_SCENE_OBSTACLE:{identity}")
        identities.add(identity)
        geometry = obstacle.get("geometry")
        if geometry is None or geometry.is_empty or not geometry.is_valid:
            raise PreflightError(f"INVALID_SCENE_OBSTACLE:{identity}")
        disposition = obstacle.get("disposition")
        if disposition == "writable":
            observations.append({"source_id": identity, "disposition": disposition, "checked": False})
            continue
        if disposition == "protected":
            measured = geometry
        elif disposition == "attachment_exception":
            region = obstacle.get("allowed_contact_region")
            if region is None or region.is_empty or not region.is_valid:
                raise PreflightError(f"ATTACHMENT_EXCEPTION_UNBOUNDED:{identity}")
            measured = geometry.difference(region)
        else:
            raise PreflightError(f"UNCLASSIFIED_SCENE_OBSTACLE:{identity}")
        if measured.is_empty:
            observations.append({"source_id": identity, "disposition": disposition, "checked": True, "distance_mm": None})
            continue
        overlap_area = copper.intersection(measured).area
        distance = copper.distance(measured)
        if overlap_area > area_tolerance_mm2:
            status = "FAIL_OVERLAP"
        # Numerical equivalence is diagnostic only. It must never be added to
        # the observed distance to waive the v15 hard floor or target.
        elif distance < hard_floor_mm:
            status = "FAIL_HARD_CLEARANCE_FLOOR"
        elif distance < construction_target_mm:
            status = "BELOW_TARGET_WITHIN_HARD_FLOOR"
        else:
            status = "PASS_CONSTRUCTION_TARGET"
        observations.append({
            "source_id": identity,
            "disposition": disposition,
            "checked": True,
            "distance_mm": distance,
            "overlap_area_mm2": overlap_area,
            "status": status,
        })
    if not observations:
        raise PreflightError("EMPTY_SCENE_PARTITION")
    statuses = {row.get("status") for row in observations if row.get("checked") and row.get("status")}
    if "FAIL_OVERLAP" in statuses or "FAIL_HARD_CLEARANCE_FLOOR" in statuses:
        status = "FAIL"
    elif "BELOW_TARGET_WITHIN_HARD_FLOOR" in statuses:
        status = "NOT_TARGET_COMPLIANT"
    else:
        status = "PASS_GEOMETRIC_CLEARANCE_ONLY"
    return {
        "status": status,
        "width_mm": width_mm,
        "hard_floor_mm": hard_floor_mm,
        "construction_target_mm": construction_target_mm,
        "numeric_tolerance_mm": numeric_tolerance_mm,
        "buffer_quad_segs": quad_segs,
        "obstacle_count": len(observations),
        "obstacle_checks": observations,
        "electrical_intent": "NOT_ESTABLISHED",
    }


def verify_scene(package_manifest_path: Path) -> dict[str, Any]:
    """Hash-check and load the complete ORG F.Cu scene and accepted v69 lands."""
    package_manifest_path = Path(package_manifest_path)
    root = package_manifest_path.resolve().parent
    spec = json.loads(package_manifest_path.read_text(encoding="utf-8"))

    def read_bound(rel: str, expected: str) -> bytes:
        path = root / rel
        data = path.read_bytes()
        actual = digest(data)
        if actual != expected:
            raise PreflightError(f"INPUT_HASH_MISMATCH:{rel}:{actual}")
        return data

    source_bytes = read_bound(spec["source"]["path"], spec["source"]["sha256"])
    inventory_bytes = read_bound(spec["inventory"]["path"], spec["inventory"]["sha256"])
    archive_bytes = read_bound(spec["org_archive"]["path"], spec["org_archive"]["sha256"])
    land_manifest_bytes = read_bound(spec["land_manifest"]["path"], spec["land_manifest"]["sha256"])
    policy_bytes = read_bound(spec["policy"]["path"], spec["policy"]["sha256"])
    receipt_bytes = read_bound(spec["execution_receipt"]["path"], spec["execution_receipt"]["sha256"])
    determinism_bytes = read_bound(spec["determinism_receipt"]["path"], spec["determinism_receipt"]["sha256"])
    inventory = json.loads(inventory_bytes)
    rows = inventory.get("rows")
    if not isinstance(rows, list) or len(rows) != spec["inventory"]["row_count"]:
        raise PreflightError("ORG_INVENTORY_ROW_COUNT")
    if digest(source_bytes) != spec["source"]["sha256"] or inventory.get("source_hash") != spec["source"]["sha256"]:
        raise PreflightError("ORG_SOURCE_BINDING")
    fcu_rows = [r for r in rows if "F.Cu" in r.get("layers", []) and r.get("coverage") == "GEOMETRY_AVAILABLE"]
    expected_fcu_count = int(spec["org_archive"]["fcu_object_count"])
    if not spec.get("test_fixture") and expected_fcu_count != 17_849:
        raise PreflightError("C2_FCU_COUNT_CONTRACT")
    if len(fcu_rows) != expected_fcu_count:
        raise PreflightError(f"ORG_FCU_COUNT:{len(fcu_rows)}")
    kinds: dict[str, int] = {}
    for row in fcu_rows:
        kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
        if row.get("source_sha256") != spec["source"]["sha256"] or not row.get("geometry_sha256"):
            raise PreflightError(f"ORG_ROW_BINDING:{row.get('id')}")
    if kinds != spec["org_archive"]["fcu_kind_counts"]:
        raise PreflightError(f"ORG_FCU_KIND_COUNTS:{kinds}")

    archive_path = root / spec["org_archive"]["path"]
    with ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise PreflightError("ORG_ARCHIVE_CRC")
        members = {name[:-4]: name for name in archive.namelist() if name.endswith(".wkb")}
        if len(members) != spec["org_archive"]["unique_wkb_count"]:
            raise PreflightError("ORG_ARCHIVE_MEMBER_COUNT")
        fcu_hashes = {r["geometry_sha256"] for r in fcu_rows}
        if not fcu_hashes <= set(members):
            raise PreflightError(f"ORG_ARCHIVE_MISSING_HASHES:{len(fcu_hashes - set(members))}")
        for key in sorted(fcu_hashes):
            data = archive.read(members[key])
            if digest(data) != key:
                raise PreflightError(f"ORG_WKB_HASH:{key}")
            geometry = load_wkb(data)
            if geometry.is_empty or not geometry.is_valid:
                raise PreflightError(f"ORG_WKB_GEOMETRY:{key}")

    land_manifest = json.loads(land_manifest_bytes)
    targets = land_manifest.get("targets", [])
    expected_land_count = int(spec["land_manifest"]["target_count"])
    if not spec.get("test_fixture") and expected_land_count != 80:
        raise PreflightError("C2_V69_TARGET_COUNT_CONTRACT")
    if len(targets) != expected_land_count:
        raise PreflightError("V69_TARGET_COUNT")
    if land_manifest.get("status") != "PASS_SOURCE_WKB_HASH_BOUND" and not land_manifest.get("all_candidate_wkb_valid_bounds_hash_bound"):
        raise PreflightError("V69_TARGET_MANIFEST_STATUS")
    target_root = root / spec["land_manifest"]["target_root"]
    target_ids: set[str] = set()
    for target in targets:
        identity = target["source_id"]
        if identity in target_ids:
            raise PreflightError(f"V69_DUPLICATE_TARGET:{identity}")
        target_ids.add(identity)
        path = target_root / Path(target["candidate_wkb_path"]).name
        data = path.read_bytes()
        if len(data) != target["candidate_wkb_bytes"] or digest(data) != target["candidate_wkb_sha256"]:
            raise PreflightError(f"V69_LAND_HASH:{identity}")
        geom = load_wkb(data)
        if geom.is_empty or not geom.is_valid:
            raise PreflightError(f"V69_LAND_GEOMETRY:{identity}")
        actual_bounds = list(geom.bounds)
        if any(abs(a - b) > 1e-9 for a, b in zip(actual_bounds, target["accepted_bounds_mm"])):
            raise PreflightError(f"V69_LAND_BOUNDS:{identity}")

    policy = json.loads(policy_bytes)
    receipt = json.loads(receipt_bytes)
    determinism = json.loads(determinism_bytes)
    if receipt.get("t02_policy_sha256") != digest(policy_bytes):
        raise PreflightError("V69_POLICY_BINDING")
    if receipt.get("trace_changed_in_t02") is not False:
        raise PreflightError("T02_TRACE_NOT_FROZEN")
    if determinism.get("status") != "PASS_BYTE_IDENTICAL_REPLAY":
        raise PreflightError("V69_DETERMINISM_STATUS")
    if policy.get("schema") != "crop-rect-t02-policy/15":
        raise PreflightError("UNEXPECTED_T02_POLICY_VERSION")
    return {
        "status": "PASS_COMPLETE_SCENE_INPUT_HASH_AND_LOAD",
        "source_sha256": spec["source"]["sha256"],
        "org_fcu_geometry_count": len(fcu_rows),
        "org_fcu_unique_wkb_count": len(fcu_hashes),
        "org_fcu_kind_counts": dict(sorted(kinds.items())),
        "accepted_v69_land_count": len(targets),
        "t02_execution_receipt_sha256": digest(receipt_bytes),
        "v69_determinism_receipt_sha256": digest(determinism_bytes),
        "policy_sha256": digest(policy_bytes),
        "route_search_executed": False,
        "native_export_executed": False,
        "electrical_intent": "NOT_ESTABLISHED",
    }


def serialize_candidate(line: LineString) -> tuple[bytes, str]:
    data = to_wkb(line, byte_order=0, output_dimension=2, include_srid=False)
    return data, digest(data)
