"""Source-stroke eligibility evidence, separate from clearance acceptance.

Only fully covered source copper is suppressed. Partial overlap, including
overlapping fill evidence, never independently excludes a stroke. The caller
keeps the established common trace/group scale. No geometry is changed here.
"""
import hashlib
import math
from shapely import to_wkb
from shapely.ops import unary_union

VERSION = 'source-stroke-fully-covered-exclusion/4'


def _valid(geometry):
    if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in ('Polygon', 'MultiPolygon'):
        raise ValueError('VALID_FINITE_SOURCE_COPPER_REQUIRED')


def overlapping_parallel_fill_witness(stroke, other):
    """Measure long overlapping native straight strokes, not separate traces.

    Each row binds id, start_mm, end_mm, width_mm and original geometry. This
    detects lateral overlap along a substantial run. Collinear continuation
    caps, ordinary disjoint parallel traces and short junction contacts do not
    establish fill. The caller verifies native fragment/width provenance.
    """
    for row in (stroke, other):
        _valid(row['geometry'])
        if (not math.isfinite(row['width_mm']) or row['width_mm'] <= 0
                or any(len(row[k]) != 2 or not all(math.isfinite(v) for v in row[k])
                       for k in ('start_mm', 'end_mm'))):
            raise ValueError('VERIFIED_STRAIGHT_SOURCE_STROKE_REQUIRED')
    if stroke['id'] == other['id']:
        return None
    a, b = stroke['start_mm'], stroke['end_mm']
    c, d = other['start_mm'], other['end_mm']
    length, other_length = math.dist(a, b), math.dist(c, d)
    if not length or not other_length:
        return None
    u = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
    v = ((d[0] - c[0]) / other_length, (d[1] - c[1]) / other_length)
    if abs(u[0] * v[1] - u[1] * v[0]) > 1e-6:
        return None
    lateral = abs((c[0] - a[0]) * u[1] - (c[1] - a[1]) * u[0])
    if not 1e-6 < lateral < (stroke['width_mm'] + other['width_mm']) / 2:
        return None
    projections = [(p[0] - a[0]) * u[0] + (p[1] - a[1]) * u[1] for p in (c, d)]
    overlap = min(length, max(projections)) - max(0., min(projections))
    if overlap <= max(.1, 3 * max(stroke['width_mm'], other['width_mm'])):
        return None
    if stroke['geometry'].intersection(other['geometry']).area <= 0:
        return None
    return dict(source_id=stroke['id'], neighbor_source_id=other['id'],
                lateral_mm=lateral, longitudinal_overlap_mm=overlap,
                source_geometry_sha256=hashlib.sha256(to_wkb(stroke['geometry'])).hexdigest(),
                neighbor_geometry_sha256=hashlib.sha256(to_wkb(other['geometry'])).hexdigest(),
                source_width_mm=stroke['width_mm'], neighbor_width_mm=other['width_mm'])


def classify_stroke(source_id, geometry, width_mm, kind, neighbors, *, fill_witness=None, eligibility_scope=None, continuation_source_ids=()):
    """Return measured coverage and a proposed fixed/eligible disposition.

    Neighbors are original/frozen source objects with id, geometry, kind and
    trace_width_mm. Exact same-kind/same-width geometry aliases cannot hide the
    stroke from itself. Different source shapes remain real coverage operands.
    The caller must bind source identity, native widths and complete neighbors.
    A declared eligibility scope also checks local coverage: a remote exposed
    portion cannot qualify a bulk-embedded local portion. This is selection
    only; neither the original stroke nor later width construction is clipped.
    Continuation membership is recorded, but is not subtracted from the cover
    test: even a stroke under another piece of its trace can be fully covered.
    Partial overlaps remain eligible. No component/net clearance exemption.
    """
    _valid(geometry)
    if kind not in ('segment', 'arc') or not math.isfinite(width_mm) or width_mm <= 0:
        raise ValueError('VERIFIED_NATIVE_TRACE_STROKE_REQUIRED')
    blob = to_wkb(geometry)
    continuations = set(continuation_source_ids) - {source_id}
    aliases, ignored_continuations, operands, identities = [], [], [], set()
    for row in neighbors:
        sid = row['id']
        if sid == source_id or sid in identities:
            raise ValueError('DISTINCT_OTHER_SOURCE_IDENTITIES_REQUIRED')
        identities.add(sid)
        other = row['geometry']
        _valid(other)
        if sid in continuations:
            if row['kind'] not in ('segment', 'arc') or row['trace_width_mm'] != width_mm:
                raise ValueError('SAME_UNIFORM_NATIVE_TRACE_CONTINUATION_REQUIRED')
            ignored_continuations.append(sid)
        if (row['kind'] == kind and row['trace_width_mm'] == width_mm
                and to_wkb(other) == blob):
            aliases.append(sid)
        else:
            operands.append(other)
    other_copper = unary_union(operands)
    exposed = geometry.difference(other_copper)
    fraction = exposed.area / geometry.area
    scope_fraction = None
    scope_fully_covered = False
    if eligibility_scope is not None:
        _valid(eligibility_scope)
        local = geometry.intersection(eligibility_scope)
        if local.area:
            scope_fraction = exposed.intersection(eligibility_scope).area / local.area
            scope_fully_covered = other_copper.covers(local)
    reasons = []
    if other_copper.covers(geometry):
        reasons.append('FULLY_COVERED_BY_OTHER_EXISTING_COPPER')
    if scope_fully_covered:
        reasons.append('FULLY_COVERED_WITHIN_ELIGIBILITY_SCOPE')
    if fill_witness is not None:
        if (not isinstance(fill_witness, dict)
                or not fill_witness.get('neighbor_source_id')
                or fill_witness['neighbor_source_id'] not in identities
                or not math.isfinite(fill_witness.get('longitudinal_overlap_mm', float('nan')))
                or fill_witness['longitudinal_overlap_mm'] <= 0):
            raise ValueError('SOURCE_BOUND_FILL_WITNESS_REQUIRED')
    return dict(version=VERSION, source_id=source_id,
                source_geometry_sha256=hashlib.sha256(blob).hexdigest(),
                disposition='FIXED_EMBEDDED_OR_FILL' if reasons else 'ELIGIBLE_EXPOSED_SOURCE_STROKE',
                original_area_mm2=geometry.area, exposed_area_mm2=exposed.area,
                independently_exposed_fraction=fraction, reasons=reasons,
                scope_exposed_fraction=scope_fraction,
                ignored_exact_alias_ids=sorted(aliases),
                ignored_same_trace_source_ids=[],
                same_trace_neighbor_ids=sorted(ignored_continuations),
                coverage_source_ids=sorted(identities - set(aliases)),
                fully_covered=other_copper.covers(geometry),
                scope_fully_covered=scope_fully_covered,
                partial_overlap_rule='RETAIN_ELIGIBILITY_AND_ESTABLISHED_COMMON_TRACE_GROUP_SCALE',
                geometry_changes='NONE', qualification='PROVISIONAL_ELIGIBILITY_NOT_CLEARANCE_ACCEPTANCE')
