"""Separate exact enclosure containment from the existing T05 window policy.

A GEOS intersection of an enclosure and a window can manufacture tiny boundary
residues even when a patch is contained in each input independently. Do not
materialize that intersection as a proof object. Certify clearance of the WHOLE
local enclosure; apply the original window-area rule to ACTUAL copper separately.
No board copper is changed and exact cell containment is never relaxed.
"""
from math import isfinite,ulp
from time import perf_counter
from shapely import to_wkb
from src.stage_abi.loaded_geometry import geometry_checksum
from src.stage_abi.store import digest

MIN_GUARD_MM=1e-10
MAX_GUARD_MM=1e-8
WINDOW_SCHEMA='t05-stored-patch-window-area/1'

def window_policy_proof(patch,domain,*,area_epsilon_mm2):
    """Measure the unchanged window rule once for a specific immutable patch.

    This is the existing `patch.difference(window).area <= epsilon` predicate,
    not an area tolerance for enclosure containment. Fingerprints bind both
    operands. The caller authenticates this witness together with the stored
    patch reference, policy and accepted-prefix state; replay consumes those
    bindings instead of repeating an overlay on the old window boundary.
    """
    if (type(area_epsilon_mm2)not in(int,float) or not isfinite(area_epsilon_mm2)
            or area_epsilon_mm2<0):
        raise ValueError('CERTIFICATE_WINDOW_POLICY_INVALID')
    if patch.is_empty or not patch.is_valid or domain.is_empty or not domain.is_valid:
        raise ValueError('CERTIFICATE_WINDOW_GEOMETRY_INVALID')
    outside=float(patch.difference(domain).area)
    if not isfinite(outside)or outside<0 or outside>area_epsilon_mm2:
        raise ValueError('CERTIFICATE_WINDOW_POLICY_REJECTED')
    return dict(schema=WINDOW_SCHEMA,patch_sha256=digest(to_wkb(patch)),
        window_fingerprint=geometry_checksum(domain),
        area_epsilon_mm2=float(area_epsilon_mm2),outside_area_mm2=outside,
        predicate='GEOS_DIFFERENCE_AREA_LEQ_EXISTING_POLICY')

def certified_enclosure(base,patch,domain,certify,*,area_epsilon_mm2):
    """Prove exact local containment and independently preserve window policy.

    ``certify`` MUST freshly establish the original foreign-clearance predicate
    for the entire uncut cover. It is clearance-only: the proof geometry need
    not itself fit the window, because ACTUAL copper has the separate original
    window-policy witness. No caller may pass a generic success flag. A cover
    with inadequate obstacle clearance is rejected even if the patch fits.
    """
    began=perf_counter()
    if base.is_empty or patch.is_empty or not base.is_valid or not patch.is_valid or not domain.is_valid:
        raise ValueError('CERTIFICATE_ENCLOSURE_INVALID_INPUT')
    scale=max(1.,*(abs(v)for v in base.bounds))
    guard=max(MIN_GUARD_MM,1024*ulp(scale))
    if not isfinite(guard)or guard>MAX_GUARD_MM:
        raise ValueError('CERTIFICATE_ENCLOSURE_ROUNDOFF_BOUND')
    cover=base.buffer(guard,quad_segs=1,join_style='mitre')
    if not cover.is_valid or cover.is_empty:
        raise ValueError('CERTIFICATE_ENCLOSURE_INVALID_COVER')
    if not(cover.covers(patch)or patch.difference(cover).is_empty):
        raise ValueError('CERTIFICATE_ENCLOSURE_PATCH_OUTSIDE')
    window_began=perf_counter()
    witness=window_policy_proof(patch,domain,area_epsilon_mm2=area_epsilon_mm2)
    window_seconds=perf_counter()-window_began
    check_started=perf_counter()
    if not certify(cover):
        raise ValueError('CERTIFICATE_ENCLOSURE_CLEARANCE_REJECTED')
    check_seconds=perf_counter()-check_started
    return cover,dict(roundoff_enclosure_guard_mm=guard,
        roundoff_enclosure_added_area_mm2=cover.difference(base).area,
        roundoff_enclosure_fresh_certifications=1,
        roundoff_enclosure_physical_seconds=check_seconds,
        roundoff_enclosure_total_seconds=perf_counter()-began,
        separate_window_policy_seconds=window_seconds,
        separate_window_outside_area_mm2=witness['outside_area_mm2'],
        separate_window_area_epsilon_mm2=witness['area_epsilon_mm2'])
