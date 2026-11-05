"""Additional C03 rectangle/inclusive extent guards, independent of admission.

Native and simultaneous finite-copper qualification remain mandatory. These
guards cannot grant a crop exception or erase a blocked original positive.
"""
import math

import sexpdata
from shapely import from_wkb, to_wkb
from shapely.affinity import scale
from shapely.geometry import box
from shapely.ops import unary_union

from src.c03_recovery import AREA_EPSILON, digest
from src.native_reference import one


def rectangle_intents(raw, manifest, original_blobs, definitions):
    source = digest(raw)
    meta = {r['id']: r for r in manifest['objects']}
    if (source != manifest['source_sha256'] or len(meta) != len(manifest['objects'])
            or set(meta) != set(original_blobs) or
            any(digest(original_blobs[s]) != r['geometry_sha256'] for s, r in meta.items())):
        raise ValueError('C03_RECTANGLE_SOURCE_BINDING_CHANGED')
    result = []
    seen = set()
    for definition in definitions:
        sid = definition['source_id']
        if sid in seen or sid not in meta:
            raise ValueError('C03_RECTANGLE_OBLIGATION_MISSING_OR_DUPLICATED')
        seen.add(sid)
        row = meta[sid]
        start, end = row['source_span']
        if sid != f'{source}:bytes:{start}:{end}' or not 0 <= start < end <= len(raw):
            raise ValueError('C03_RECTANGLE_NATIVE_ID_CHANGED')
        node = sexpdata.loads(raw[start:end].decode())
        core = from_wkb(original_blobs[sid])
        if (row['kind'] != 'gr_poly' or str(node[0]) != 'gr_poly' or
                list(map(str, one(node, 'layer'))) != ['F.Cu'] or
                str(one(node, 'fill', ['none'])[0]) not in ('yes', 'solid') or
                float(one(one(node, 'stroke'), 'width')[0]) != 0 or
                core.is_empty or not core.equals(box(*core.bounds))):
            raise ValueError('C03_ORIGINAL_WHOLE_RECTANGLE_REQUIRED')
        factors = definition['factors']
        if (type(factors) is not list or len(factors) != 2 or
                any(type(x) not in (int, float) or not math.isfinite(x) or
                    not 1 <= x <= 1.25 for x in factors)):
            raise ValueError('C03_ORIGINAL_RECTANGLE_CAP_REQUIRED')
        required = scale(core, *factors, origin=core.centroid)
        if not required.covers(core):
            raise ValueError('C03_RECTANGLE_CORE_REMOVED')
        result.append(dict(source_id=sid, key=definition['key'],
            required_positive=definition['status'] == 'GROWN',
            source_geometry_sha256=row['geometry_sha256'],
            required_geometry=required, original_geometry=core,
            required_wkb_sha256=digest(to_wkb(required)), factors=factors))
    return result


def assess_rectangles(obligations, actual, writable):
    records = []
    for row in obligations:
        sid = row['source_id']
        required, core = row['required_geometry'], row['original_geometry']
        failures = []
        candidate = actual.get(sid)
        missing = required.area
        if candidate is None:
            failures.append('ORIGINAL_RECTANGLE_TARGET_MISSING')
        elif candidate.is_empty or not candidate.is_valid:
            failures.append('INVALID_RECTANGLE_COPPER')
        else:
            missing = required.difference(candidate).area
            if missing > AREA_EPSILON:
                failures.append('REQUIRED_RECTANGLE_EXTENT_MISSING')
            if not candidate.equals(box(*candidate.bounds)):
                failures.append('WHOLE_RECTANGLE_SHAPE_REQUIRED')
            if not candidate.covers(core):
                failures.append('ORIGINAL_RECTANGLE_CORE_REMOVED')
            if candidate.centroid.distance(core.centroid) > 1e-12:
                failures.append('ORIGINAL_RECTANGLE_CENTER_CHANGED')
            cap = scale(core, 1.25, 1.25, origin=core.centroid)
            if candidate.difference(cap).area > AREA_EPSILON:
                failures.append('ORIGINAL_RECTANGLE_1P25_CAP_EXCEEDED')
            if candidate.difference(core).difference(writable).area > AREA_EPSILON:
                failures.append('RECTANGLE_ADDITION_OUTSIDE_WRITE_PERMISSION')
        records.append(dict(source_id=sid, key=row['key'],
            required_positive=row['required_positive'],
            missing_required_extent_mm2=missing, failures=failures,
            passed=not failures, required_wkb_sha256=row['required_wkb_sha256']))
    return dict(passed=all(r['passed'] for r in records), records=records,
        required_positive=sum(r['required_positive'] for r in records),
        qualification='Additional rectangle extent guard only; inclusive, native and finite checks separate')


def inclusive_intents(definitions, rectangles, original_blobs):
    grown = {r['source_id']: r['required_geometry'] for r in rectangles}
    result = []
    seen = set()
    for definition in definitions:
        if definition['status'] != 'MERGED':
            continue
        members = tuple(sorted(definition['rectangle_members']))
        if (not members or len(members) != len(set(members)) or members in seen or
                any(s not in original_blobs for s in members) or
                any(s not in original_blobs for s in definition['support_trace_source_ids'])):
            raise ValueError('C03_INCLUSIVE_ORIGINAL_MEMBERS_REQUIRED')
        seen.add(members)
        parts = [grown[s] if s in grown else from_wkb(original_blobs[s]) for s in members]
        required = box(*unary_union(parts).bounds)
        witness = box(*definition['inclusive_bounds_mm'])
        if required.symmetric_difference(witness).area > AREA_EPSILON:
            raise ValueError('C03_INCLUSIVE_SOURCE_PARAMETER_RECONSTRUCTION_CHANGED')
        result.append(dict(members=members, required_geometry=required,
            support_source_ids=list(definition['support_trace_source_ids']),
            required_wkb_sha256=digest(to_wkb(required))))
    return result


def assess_inclusive(obligations, actual, writable):
    """Missing member sets fail even when removed from both plan and output."""
    records = []
    for row in obligations:
        candidate = actual.get(row['members'])
        required = row['required_geometry']
        failures = []
        missing = required.area
        if candidate is None:
            failures.append('REQUIRED_INCLUSIVE_MEMBER_SET_MISSING')
        elif candidate.is_empty or not candidate.is_valid:
            failures.append('INVALID_INCLUSIVE_COPPER')
        else:
            missing = required.difference(candidate).area
            if missing > AREA_EPSILON:
                failures.append('REQUIRED_INCLUSIVE_EXTENT_MISSING')
            if not candidate.equals(box(*candidate.bounds)):
                failures.append('WHOLE_INCLUSIVE_RECTANGLE_REQUIRED')
            if candidate.difference(writable).area > AREA_EPSILON:
                failures.append('INCLUSIVE_EXTENT_OUTSIDE_WRITE_PERMISSION')
        records.append(dict(members=list(row['members']),
            support_source_ids=row['support_source_ids'],
            missing_required_extent_mm2=missing, failures=failures,
            passed=not failures, required_wkb_sha256=row['required_wkb_sha256']))
    return dict(passed=all(r['passed'] for r in records), records=records,
                required_member_sets=len(records),
                qualification='Additional extent/member guard; original contact, shortage, finite/native checks mandatory')
