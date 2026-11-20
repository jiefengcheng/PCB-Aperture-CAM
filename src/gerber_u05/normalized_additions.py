"""Conservative default-case checks for a normalized source-bound body.

The legacy width verifier requires a candidate containing every old edge. A
normalized body need not contain source edge noise, and a GEOS union used only
to satisfy that precondition can lose coincident edges. Instead check ALL new
copper against ALL foreign copper. These are supersets of the legacy visible
addition and visible neighbor, respectively; no visibility or port exemption
is needed. Group copper is an obstacle, never a checked candidate here.

This proves clearance of additions only. Width, source custody, removal policy
and route/joint continuity remain separate obligations of the caller.
"""
from dataclasses import asdict
from src.native_inventory import ERROR_MM
from src.trace_width_clearance import TraceWidthContract,sha


def verify_patch(delta,fixed,contract=TraceWidthContract()):
    """Verify only new joint copper; the supporting groups are never audited."""
    if contract!=TraceWidthContract():raise ValueError('WIDTH_CLEARANCE_POLICY_CHANGED')
    for g in [delta,*[r['geometry']for r in fixed]]:
        if (g.is_empty and g is not delta)or not g.is_valid or g.geom_type not in('Polygon','MultiPolygon'):
            raise ValueError('INVALID_FINITE_COPPER_GEOMETRY')
    envelope=delta.buffer(ERROR_MM,quad_segs=128)if not delta.is_empty else delta
    pairs=[];failures=[]
    for row in sorted(fixed,key=lambda r:r['id']):
        gap=None if envelope.is_empty else envelope.distance(row['geometry'])
        passed=gap is None or gap+contract.comparison_epsilon_mm>=contract.construction_gap_mm
        pairs.append(dict(neighbor_id=row['id'],gap_mm=gap,passed=passed,foreign_sha256=sha(row['geometry'])))
        if not passed:failures.append(dict(neighbor_id=row['id'],reason='NEW_EXPOSED_COPPER_BELOW_CONSTRUCTION_GUARD'))
    return dict(schema='t04-verified-joint-additions/1',contract=asdict(contract),passed=not failures,failures=failures,pairs=pairs,
                positive_delta_sha256=sha(delta),checking_envelope_sha256=sha(envelope),added_area_mm2=delta.area,
                checking_margin_mm=ERROR_MM,constructed_groups_audited=0)


def verify(core,actual,fixed,contract=TraceWidthContract()):
    if contract!=TraceWidthContract():raise ValueError('WIDTH_CLEARANCE_POLICY_CHANGED')
    for geometry in [core,actual,*[r['geometry']for r in fixed]]:
        if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in('Polygon','MultiPolygon'):
            raise ValueError('INVALID_FINITE_COPPER_GEOMETRY')
    delta=actual.difference(core)
    # A checking reservation only. It never becomes plotted copper and never
    # rounds down the unchanged construction guard.
    check=verify_patch(delta,fixed,contract)
    return dict(schema='t04-normalized-default-additions/1',contract=asdict(contract),
        passed=check['passed'],failures=check['failures'],pairs=check['pairs'],
        actual_body_sha256=sha(actual),source_core_sha256=sha(core),
        positive_delta_sha256=sha(delta),checking_envelope_sha256=check['checking_envelope_sha256'],
        added_area_mm2=delta.area,removed_area_mm2=core.difference(actual).area,
        checking_margin_mm=ERROR_MM,
        check_scope='ALL_POSITIVE_CHANGE_TO_ALL_FOREIGN_COPPER; NO_VISIBILITY_OR_PORT_EXEMPTION',
        constructed_groups_audited=0)
