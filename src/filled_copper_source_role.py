"""Proposed source-role evidence for native strokes buried in filled lands.

This selects fixed source objects; it is never a trace-distance/clearance rule.
No coverage percentage, geometry rounding, or net/component exemption is used.
"""
import hashlib
import math
from dataclasses import dataclass
from shapely import to_wkb
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

ROLE_VERSION = 'native-route-buried-in-original-filled-copper/1'


def buried_route_witness(source_id, native_points, filled_sources):
    """Prove that the entire source-bound native route is inside original fill.

    Curves use the existing native inventory's retained route tessellation.
    Finite source copper remains unchanged even if its outer cap protrudes.
    Merely entering a pad or partially overlapping it is insufficient.
    """
    if len(native_points) < 2 or any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in native_points):
        raise ValueError('FINITE_BOUND_NATIVE_ROUTE_REQUIRED')
    route = Point(native_points[0]) if all(p == native_points[0] for p in native_points) else LineString(native_points)
    fills=[];seen=set();bindings=[]
    for row in filled_sources:
        sid=row['id'];g=row['geometry']
        if sid == source_id or sid in seen:raise ValueError('DISTINCT_FILLED_SOURCE_REQUIRED')
        seen.add(sid)
        if row['kind'] not in ('gr_poly','gr_circle') or row['trace_width_mm'] != 0:
            raise ValueError('ORIGINAL_FILLED_LAND_SOURCE_REQUIRED')
        if g.is_empty or not g.is_valid or g.geom_type not in ('Polygon','MultiPolygon'):
            raise ValueError('VALID_ORIGINAL_FILLED_COPPER_REQUIRED')
        if g.intersects(route):
            fills.append(g);bindings.append(dict(source_id=sid,geometry_sha256=hashlib.sha256(to_wkb(g)).hexdigest()))
    if not fills or not unary_union(fills).covers(route):return None
    return dict(schema=ROLE_VERSION,source_id=source_id,native_route_sha256=hashlib.sha256(to_wkb(route)).hexdigest(),
                original_filled_sources=sorted(bindings,key=lambda x:x['source_id']),
                entire_native_route_in_original_fill=True,source_geometry_modified=False,
                role='PROPOSED_FIXED_BURIED_SOURCE_NOT_INDEPENDENT_TRACE',
                limitation='Source-role selection only; curved membership uses existing native-route tessellation; no clearance verdict')


def _bulk_boundary_route_witness(source_id, native_points, width_mm, original_copper, *, validate_body):
    """Propose fixed role for a stroke building the edge of broad original fill.

    A full one-sided strip twice the verified native width must already be
    covered by original copper. An isolated trace or separated parallel bundle
    cannot satisfy this proof. It is a source-role heuristic, not clearance.
    """
    if not math.isfinite(width_mm) or width_mm <= 0:raise ValueError('VERIFIED_POSITIVE_SOURCE_WIDTH_REQUIRED')
    if len(native_points)<2 or any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in native_points):
        raise ValueError('FINITE_BOUND_NATIVE_ROUTE_REQUIRED')
    route=LineString(native_points)
    if not route.length:return None
    if validate_body and (original_copper.is_empty or not original_copper.is_valid):raise ValueError('VALID_ORIGINAL_COPPER_UNION_REQUIRED')
    for side in (1,-1):
        strip=route.buffer(side*2*width_mm,single_sided=True,quad_segs=128)
        if not strip.is_empty and strip.is_valid and original_copper.covers(strip):
            return dict(schema='native-bulk-boundary-source-role/1',source_id=source_id,
                native_route_sha256=hashlib.sha256(to_wkb(route)).hexdigest(),verified_original_width_mm=width_mm,
                inward_strip_width_multiplier=2.,side=side,strip_wkb_sha256=hashlib.sha256(to_wkb(strip)).hexdigest(),
                strip_area_mm2=strip.area,entire_one_sided_strip_already_original_copper=True,
                role='PROPOSED_FIXED_BULK_BOUNDARY_SOURCE',source_geometry_modified=False,
                limitation='Source-role heuristic requires visual qualification; never changes clearance policy or hides new copper')
    return None


@dataclass(frozen=True, slots=True)
class PreparedBulkBoundary:
    """One validity proof for one immutable Shapely copper geometry.

    The exact strip construction, validity, coverage and witness bytes are
    unchanged. The retained object cannot be replaced; a different geometry
    requires a different prepared instance and a fresh validity check.
    """
    copper: object

    def __post_init__(self):
        if self.copper.is_empty or not self.copper.is_valid:
            raise ValueError('VALID_ORIGINAL_COPPER_UNION_REQUIRED')

    def witness(self, source_id, native_points, width_mm):
        return _bulk_boundary_route_witness(source_id,native_points,width_mm,self.copper,validate_body=False)


def bulk_boundary_route_witness(source_id, native_points, width_mm, original_copper):
    """Compatibility entry: independently validate an uncached copper body."""
    return _bulk_boundary_route_witness(source_id,native_points,width_mm,original_copper,validate_body=True)
