"""Opt-in corner-cut proposals and reusable clearance workspaces.

This module does not edit a scene, export copper, or waive existing stage
guards. Source role classification belongs to the caller's source-bound
inventory. A Gerber Region or FIXED growth assignment alone is not evidence
that a shape is neither pad, trace, terminal nor pin.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import math

import shapely
from shapely.ops import unary_union



def qualify_bulk_region(row, region, policy, *, catalogue, route_members,
                        declared_pin_ids, source_sha256):
    """Classify a retained source occurrence, not an arbitrary union polygon.

    Authority is limited to the current Gerber source-family catalogue and
    explicit pin registry. Large Regions may contain contact/root areas; those
    areas must still be protected by plan_trim's complete protection operands.
    This is not a claim of external netlist or manufacturing qualification.
    """
    from src.gerber_u05.source_catalogue import authority
    sid = row['source_id']
    record = authority(row)
    matches = [r for r in catalogue['records'] if r['source_id'] == sid]
    failures = []
    if matches != [record]:
        failures.append('SOURCE_CATALOGUE_BINDING_CHANGED')
    if sha256(shapely.to_wkb(region)).hexdigest() != row['original_ref']['sha256']:
        failures.append('SOURCE_GEOMETRY_BINDING_CHANGED')
    if (row['kind'] != 'fixed_source' or record['source_kind'] != 'Region' or
            record['growth_owner'] != 'FIXED' or
            row['metadata'].get('qualified_land') is not False or
            row['metadata'].get('rectangle_terminal') or sid in route_members or
            sid in declared_pin_ids):
        failures.append('PROTECTED_SOURCE_FAMILY')
    if region.area <= policy.outline_area_mm2 * policy.minimum_outline_fraction:
        failures.append('REGION_TOO_SMALL')
    if (catalogue.get('source_sha256') != source_sha256 or
            not sid.startswith(source_sha256 + ':')):
        failures.append('SOURCE_IDENTITY_CHANGED')
    evidence = dict(source_sha256=source_sha256, source_id=sid, record=record,
                    route_member=False if sid not in route_members else True,
                    declared_pin=sid in declared_pin_ids, area_mm2=region.area,
                    policy=dict(policy.__dict__),
                    scope='Gerber source-family roles and declared pin inventory; '
                          'all contact/root domains remain protected')
    return dict(region_sha256=fingerprint(region), established=not failures,
                classification='NON_PAD_TRACE_TERMINAL_PIN', failures=failures,
                source_evidence_sha256=sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest(),
                evidence=evidence)


def fingerprint(shape):
    """Bind actual coordinates, ring order, SRID and precision, without rounding."""
    return sha256(shapely.to_wkb(shape, include_srid=True) +
                  repr(shapely.get_precision(shape)).encode()).hexdigest()


@dataclass(frozen=True)
class CutPolicy:
    # Owner rule: region area must EXCEED 5% of the rough closed board outline.
    # The one-direction cut cap reuses the T04 TOTAL width-increase setting;
    # this is separate from T04's centred growth, whose per-side cap is half.
    outline_area_mm2: float
    minimum_outline_fraction: float
    maximum_retreat_mm: float
    protected_margin_mm: float
    t04_settings_sha256: str
    # Bounded overlay resemblance for this proposal only. Actual stage guards
    # are not changed. Both area AND spatial bounds must pass, so a thin long
    # missing contact cannot hide behind a small area alone.
    overlay_area_epsilon_mm2: float = 1e-12
    overlay_distance_epsilon_mm: float = 1e-9

    def __post_init__(self):
        values = (self.outline_area_mm2, self.minimum_outline_fraction,
                  self.maximum_retreat_mm, self.protected_margin_mm,
                  self.overlay_area_epsilon_mm2, self.overlay_distance_epsilon_mm)
        if (any(not math.isfinite(v) or v <= 0 for v in values) or
                self.minimum_outline_fraction >= 1 or not self.t04_settings_sha256):
            raise ValueError('POSITIVE_FINITE_BOUNDED_CUT_POLICY_REQUIRED')

    @classmethod
    def from_t04(cls, rough_outline, settings, *, protected_margin_mm):
        if (rough_outline.geom_type != 'Polygon' or not rough_outline.is_valid or
                rough_outline.is_empty or rough_outline.interiors):
            raise ValueError('ROUGH_CLOSED_OUTLINE_REQUIRED')
        return cls(rough_outline.area, .05, settings.maximum_total_width_increase_mm,
                   protected_margin_mm, settings.source_sha256)


def plan_trim(region, cut_window, protected, policy, *, role_evidence=None):
    """Return a proposal, never an applied edit.

    `cut_window` is the union of ALL proposed local cuts for this source region;
    depth limits apply against the unchanged source on every pass. The caller
    supplies complete protected pad/trace/terminal/pin and uncertain material.
    Preserve its surrounding margin and reject topology changes to this region.
    This is necessary geometric evidence, not complete electrical qualification.

    Missing source-bound role evidence makes the result NOT_ESTABLISHED even
    when its geometric proposal passes. Keep the preview for review, rather
    than silently treating large polygons as expendable copper.
    """
    protected = tuple(protected)
    if (region.geom_type != 'Polygon' or region.is_empty or not region.is_valid or
            not cut_window.is_valid or any(not g.is_valid for g in protected)):
        raise ValueError('VALID_REGION_WINDOW_AND_PROTECTION_REQUIRED')
    if any(shapely.get_precision(g) != 0 for g in (region, cut_window, *protected)):
        raise ValueError('FLOATING_GEOMETRY_REQUIRED')
    guard = unary_union(protected).buffer(policy.protected_margin_mm)
    # Keep the interior core and edit only a shallow boundary band. The smaller
    # offset plus round-join polygonal arcs conservatively retains extra copper
    # at concave turns. Do not erode the previous candidate repeatedly: always
    # pass the immutable original region and cumulative cut-window union.
    depth = policy.maximum_retreat_mm * math.cos(math.pi / (4 * 64))
    interior_core = region.buffer(-depth, quad_segs=64)
    removal = region.intersection(cut_window).difference(guard).difference(interior_core)
    candidate = region.difference(removal)
    # GEOS overlay may retain an identical geometric boundary with different
    # last-bit segment endpoints. Empty contacts are vacuous; covers(empty)
    # is False in GEOS and must never become a lost-contact finding.
    near_candidate = candidate.buffer(policy.overlay_distance_epsilon_mm)
    def retained(container, near_container, target):
        return (target.is_empty or container.covers(target) or
                (target.difference(container).area <= policy.overlay_area_epsilon_mm2
                 and near_container.covers(target)))
    failures = []
    if region.area <= policy.outline_area_mm2 * policy.minimum_outline_fraction:
        failures.append('REGION_TOO_SMALL')
    if not retained(candidate, near_candidate, interior_core):
        failures.append('ORIGINAL_BOUNDARY_RETREAT_EXCEEDED')
    if (candidate.is_empty or not candidate.is_valid or candidate.geom_type != 'Polygon'):
        failures.append('REGION_DISCONNECTED_OR_INVALID')
    elif len(candidate.interiors) != len(region.interiors):
        failures.append('SOURCE_HOLE_TOPOLOGY_CHANGED')
    if (not retained(region, region.buffer(policy.overlay_distance_epsilon_mm), candidate) or
            not retained(cut_window, cut_window.buffer(policy.overlay_distance_epsilon_mm), removal)):
        failures.append('SUBTRACTION_SCOPE_CHANGED')
    lost_contacts = []
    for g in protected:
        contact = region.intersection(g)
        # User-authorized subtraction preserves base geometry and relations,
        # not exact copper-boundary equivalence. Keep each positive-area
        # attachment positive and each existing touching relation present.
        # The protected operand itself is immutable and never subtracted.
        remaining_contact = candidate.intersection(g)
        if (not contact.is_empty and remaining_contact.is_empty or
                contact.area > 0 and remaining_contact.area <= 0):
            lost_contacts.append(contact.difference(candidate).area)
    if lost_contacts:
        failures.append('PROTECTED_CONTACT_CHANGED')
    expected = dict(region_sha256=fingerprint(region),
                    classification='NON_PAD_TRACE_TERMINAL_PIN', established=True)
    classified = (isinstance(role_evidence, dict) and
                  all(role_evidence.get(k) == v for k, v in expected.items()) and
                  bool(role_evidence.get('source_evidence_sha256')))
    status = ('FAIL_GEOMETRIC_PROPOSAL' if failures else
              'NOT_ESTABLISHED_SOURCE_ROLE' if not classified else
              'PASS_LOCAL_GEOMETRIC_PROPOSAL')
    return candidate, removal, dict(
        status=status, geometry_passed=not failures, failures=failures,
        role_established=classified, role_evidence=role_evidence,
        source_region_sha256=fingerprint(region),
        candidate_sha256=fingerprint(candidate), removal_sha256=fingerprint(removal),
        cut_window_sha256=fingerprint(cut_window),
        protected_sha256=[fingerprint(g) for g in protected],
        policy=dict(policy.__dict__), removed_area_mm2=removal.area,
        interior_core_sha256=fingerprint(interior_core),
        diagnostics=dict(core_missing_area_mm2=interior_core.difference(candidate).area,
                         outside_source_area_mm2=candidate.difference(region).area,
                         removal_outside_window_area_mm2=removal.difference(cut_window).area,
                         failed_contact_count=len(lost_contacts),
                         maximum_contact_loss_mm2=max(lost_contacts, default=0.)),
        removed_fraction=removal.area/region.area,
        stage_integration='NOT_RUN', applied=False)
