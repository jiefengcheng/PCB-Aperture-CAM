"""Independent source-bound C03 intent, separate from generic T01 admission.

This module never grants write permission and never imports historical candidate
copper. Reference decisions supply required semantic parameters; native source
bytes and geometry supply construction. An unmet obligation remains a failure
even if a generator removes the same target from its own plan and result.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat

import sexpdata
from shapely import from_wkb, to_wkb
from shapely.geometry import Point

from src.native_reference import one
from src.stage_abi.spindle import filled_circle


SCHEMA = 'c03-source-bound-treatment-recovery/1'
SOURCE_SHA256 = '850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0'
CROP_SHA256 = '9c33ecc73238c0a1124971faad2de7b5eeb5a6e96d008c9ad6755e19c8cc0ea4'
AREA_EPSILON = 1e-12
ROUND_QUADRANTS = 128


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bound_bytes(root, name, expected):
    """Read/hash actual regular-file bytes on every access, without symlinks."""
    root = Path(root).absolute()
    path = root / name
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('C03_REFERENCE_PATH_OUTSIDE_CHECKOUT')
    current = root
    for part in Path(name).parts:
        current /= part
        if current.is_symlink():
            raise ValueError('C03_REFERENCE_SYMLINK')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('C03_REFERENCE_NOT_REGULAR')
        data = stream.read()
    if digest(data) != expected:
        raise ValueError('C03_REFERENCE_BYTES_CHANGED:' + name)
    return data


@dataclass(frozen=True)
class CircleObligation:
    source_id: str
    key: str
    aliases: tuple
    source_span: tuple
    source_geometry_sha256: str
    native_bytes_sha256: str
    center: tuple
    original_radius: float
    required_diameter: float
    positive: bool


def load_intent(root, profile):
    """Load the independently pinned intent; current admission is not an input."""
    if (set(profile) != {'schema', 'source_sha256', 'crop_sha256',
                         'family', 'references', 'denominators', 'execution_permissions'} or
            profile['schema'] != SCHEMA or
            profile['source_sha256'] != SOURCE_SHA256 or
            profile['crop_sha256'] != CROP_SHA256 or
            profile['family'] != 'c03-native-round-class-intent/1' or
            profile['denominators'] != dict(circle_records=153,
                circle_positive=121, rectangle_records=46,
                rectangle_positive=45, inclusive_positive=6,
                width_records=97, width_positive=94)):
        raise ValueError('C03_INTENT_PROFILE_INVALID')
    required = {'T01_DECISIONS', 'T02_DECISIONS', 'T02_INCLUSIVE',
                'T04_CONSTRUCTION', 'T04_RESULT'}
    if set(profile['references']) != required:
        raise ValueError('C03_INDEPENDENT_REFERENCE_SET_REQUIRED')
    values = {}
    permissions = profile['execution_permissions']
    if (set(permissions) != {'mode', 'blocked_original_obligations', 'owner_decision'} or
            permissions['mode'] != 'KEEP_EXISTING_BOUNDARY' or
            permissions['blocked_original_obligations'] != ['T01:C028', 'T02:R304', 'T02:R305']):
        raise ValueError('C03_WRITE_PERMISSION_PROFILE_INVALID')
    ref = permissions['owner_decision']
    if set(ref) != {'path', 'sha256'}:
        raise ValueError('C03_OWNER_DECISION_BINDING_REQUIRED')
    decision = json.loads(bound_bytes(root, ref['path'], ref['sha256']))
    if (decision['owner_response'] != 'Keep the boundary; retain these obligations as blocked' or
            decision['source_sha256'] != profile['source_sha256'] or
            decision['crop_sha256'] != profile['crop_sha256'] or
            decision['write_region'] != 'EXISTING_VERIFIED_SAFE_WINDOW_UNCHANGED' or
            decision['blocked_original_obligations'] != permissions['blocked_original_obligations']):
        raise ValueError('C03_OWNER_WRITE_DECISION_CHANGED')
    for kind, ref in profile['references'].items():
        if set(ref) != {'path', 'sha256'}:
            raise ValueError('C03_REFERENCE_BINDING_INVALID')
        values[kind] = json.loads(bound_bytes(root, ref['path'], ref['sha256']))
    circles, rectangles = values['T01_DECISIONS'], values['T02_DECISIONS']
    widths = values['T04_CONSTRUCTION']
    if (len(circles) != 153 or len({r['source_id'] for r in circles}) != 153 or
            sum(r['positive_growth'] for r in circles) != 121 or
            len(rectangles) != 46 or
            len({r['source_id'] for r in rectangles}) != 46 or
            sum(r['status'] == 'GROWN' for r in rectangles) != 45 or
            sum(r['status'] == 'MERGED' for r in values['T02_INCLUSIVE']) != 6 or
            len(widths) != 97 or
            len({r['component_id'] for r in widths}) != 97 or
            sum(r['factor'] > 1 for r in widths) != 94 or
            values['T04_RESULT']['source_sha256'] != profile['source_sha256']):
        raise ValueError('C03_INDEPENDENT_DENOMINATOR_CHANGED')
    return values


def circle_obligations(raw, manifest, original_blobs, definitions, source_sha256):
    """Rebind every reference identity/parameter to complete native source."""
    if digest(raw) != source_sha256 or manifest['source_sha256'] != source_sha256:
        raise ValueError('C03_NATIVE_SOURCE_CHANGED')
    rows = manifest['objects']
    meta = {r['id']: r for r in rows}
    if len(meta) != len(rows) or set(meta) != set(original_blobs):
        raise ValueError('C03_COMPLETE_SOURCE_INVENTORY_REQUIRED')
    for sid, row in meta.items():
        start, end = row['source_span']
        if (sid != f'{source_sha256}:bytes:{start}:{end}' or
                row['source_sha256'] != source_sha256 or 'F.Cu' not in row['layers'] or
                not 0 <= start < end <= len(raw) or
                digest(original_blobs[sid]) != row['geometry_sha256']):
            raise ValueError('C03_NATIVE_OCCURRENCE_CHANGED:' + sid)
    seen = set()
    result = []
    for definition in definitions:
        sid = definition['source_id']
        if sid in seen or sid not in meta:
            raise ValueError('C03_REFERENCE_SOURCE_MISSING_OR_DUPLICATED')
        seen.add(sid)
        row = meta[sid]
        start, end = row['source_span']
        fragment = raw[start:end]
        node = sexpdata.loads(fragment.decode())
        if (row['kind'] != 'gr_circle' or str(node[0]) != 'gr_circle' or
                list(map(str, one(node, 'layer'))) != ['F.Cu'] or
                str(one(node, 'fill', ['none'])[0]) not in ('yes', 'solid') or
                float(one(one(node, 'stroke'), 'width')[0]) != 0):
            raise ValueError('C03_FILLED_NATIVE_CIRCLE_REQUIRED')
        center = tuple(map(float, one(node, 'center')))
        radius = math.dist(center, tuple(map(float, one(node, 'end'))))
        if radius != definition['original_radius_mm']:
            raise ValueError('C03_REFERENCE_NATIVE_RADIUS_CHANGED')
        aliases = tuple(sorted(r['id'] for r in rows
            if r['kind'] == 'gr_circle' and
            r['geometry_sha256'] == row['geometry_sha256']))
        if aliases != tuple(sorted(definition['aliases'])):
            raise ValueError('C03_NATIVE_ALIAS_MEMBERSHIP_CHANGED')
        diameter = definition['selected_diameter_mm']
        positive = definition['positive_growth']
        if (type(positive) is not bool or type(diameter) not in (int, float) or
                not math.isfinite(diameter) or
                not 2 * radius <= diameter <= 3 * radius or
                positive != (diameter > 2 * radius)):
            raise ValueError('C03_REQUIRED_ROUND_CLASS_INVALID')
        result.append(CircleObligation(sid, definition['key'], aliases,
            (start, end), row['geometry_sha256'], digest(fragment), center,
            radius, diameter, positive))
    return result


def required_rounds(obligations, original_blobs):
    """Construct approved round extents from native parameters, not old WKB."""
    result = {}
    for row in obligations:
        blob = original_blobs[row.source_id]
        if digest(blob) != row.source_geometry_sha256:
            raise ValueError('C03_ORIGINAL_OPERAND_CHANGED')
        core = from_wkb(blob)
        shape = Point(*row.center).buffer(row.required_diameter / 2,
                                         quad_segs=ROUND_QUADRANTS)
        if not row.positive:
            shape = core
        if not shape.covers(core):
            raise ValueError('C03_ROUND_SOURCE_CORE_NOT_RETAINED')
        result[row.source_id] = shape
    return result


def permission_record(core, required, writable):
    """Existing copper outside write space is distinct from new additions."""
    addition = required.difference(core)
    forbidden = addition.difference(writable)
    return dict(required_wkb_sha256=digest(to_wkb(required)),
                required_bounds_mm=list(required.bounds),
                required_extent_outside_mm2=required.difference(writable).area,
                original_core_outside_mm2=core.difference(writable).area,
                required_addition_outside_mm2=forbidden.area,
                addition_permitted=forbidden.area <= AREA_EPSILON,
                whole_extent_inside=writable.covers(required),
                permission='UNCHANGED; no implicit scope extension')


def permitted_rounds(obligations, original_blobs, profile):
    """Keep an owner-blocked target intact; retain its unmet original demand."""
    required = required_rounds(obligations, original_blobs)
    blocked = set(profile['execution_permissions']['blocked_original_obligations'])
    return {r.source_id: from_wkb(original_blobs[r.source_id])
            if 'T01:'+r.key in blocked else required[r.source_id] for r in obligations}


def scope_round_assessment(assessment, obligations, original_blobs, actual_blobs, profile):
    """A scoped pass never turns blocked original coverage into a full pass."""
    blocked = set(profile['execution_permissions']['blocked_original_obligations'])
    byid = {r.source_id: r for r in obligations}
    records = []
    for record in assessment['records']:
        row = byid[record['source_id']]
        is_blocked = 'T01:'+row.key in blocked
        untouched = all(actual_blobs[s] == original_blobs[s] for s in row.aliases)
        records.append(dict(record,
            disposition='BLOCKED_WRITE_BOUNDARY_OWNER_RETAINED' if is_blocked else
                        'MET' if record['passed'] else 'UNMET',
            scoped_execution_pass=untouched if is_blocked else record['passed']))
    return dict(assessment, records=records,
        original_full_coverage_pass=assessment['passed'],
        scoped_execution_pass=not assessment['protected_source_changes'] and
                              all(r['scoped_execution_pass'] for r in records),
        blocked_original_positive=sum(r['required_positive'] and
            r['disposition']=='BLOCKED_WRITE_BOUNDARY_OWNER_RETAINED' for r in records))


def assess_round_output(obligations, original_blobs, actual_blobs, writable):
    """Fail closed against independent positive shape/extent and all sources.

    This is an additional coverage guard, never a finite-clearance, native
    correspondence or export qualification substitute. It reports unmet work
    without erasing the denominator or allowing extra copper to compensate.
    """
    if set(actual_blobs) != set(original_blobs):
        raise ValueError('C03_COMPLETE_OUTPUT_SOURCE_PARTITION_REQUIRED')
    required = required_rounds(obligations, original_blobs)
    aliases = {a for row in obligations for a in row.aliases}
    protected = sorted(s for s in original_blobs if s not in aliases and
                       original_blobs[s] != actual_blobs[s])
    records = []
    for row in obligations:
        core = from_wkb(original_blobs[row.source_id])
        actual = from_wkb(actual_blobs[row.source_id])
        desired = required[row.source_id]
        reasons = []
        if any(actual_blobs[a] != actual_blobs[row.source_id] for a in row.aliases):
            reasons.append('ALIAS_OUTPUT_CONFLICT')
        missing = desired.difference(actual).area
        if missing > AREA_EPSILON:
            reasons.append('REQUIRED_ROUND_EXTENT_MISSING')
        if not filled_circle(actual):
            reasons.append('FULL_ROUND_SHAPE_REQUIRED')
        if not actual.covers(core):
            reasons.append('ORIGINAL_CORE_REMOVED')
        cap = Point(*row.center).buffer(1.5 * row.original_radius,
                                       quad_segs=ROUND_QUADRANTS)
        if actual.difference(cap).area > AREA_EPSILON:
            reasons.append('ORIGINAL_1P5_CAP_EXCEEDED')
        if actual.difference(core).difference(writable).area > AREA_EPSILON:
            reasons.append('ADDITION_OUTSIDE_WRITE_PERMISSION')
        records.append(dict(source_id=row.source_id, key=row.key,
            required_positive=row.positive, aliases=list(row.aliases),
            required_wkb_sha256=digest(to_wkb(desired)),
            actual_wkb_sha256=digest(actual_blobs[row.source_id]),
            missing_required_extent_mm2=missing, passed=not reasons,
            failures=reasons, permission=permission_record(core, desired, writable)))
    passed = not protected and all(r['passed'] for r in records)
    return dict(status='PASS_ADDITIONAL_COVERAGE_GUARD' if passed else
                'FAIL_UNMET_OR_UNPERMITTED_C03_OBLIGATIONS',
                passed=passed, records=records,
                required_positive=sum(r.positive for r in obligations),
                protected_source_changes=protected,
                native_and_finite_checks='SEPARATE_MANDATORY; not established here')


def require_complete(assessment):
    if assessment['passed'] is not True:
        raise ValueError('C03_ORIGINAL_TREATMENT_COVERAGE_NOT_FULFILLED')


def width_membership_obligations(raw, manifest, original_blobs, report, definitions):
    """Retain every local witness and complete group; never grant edit rights.

    The caller must freshly qualify the supplied report against its exact scene.
    This projection checks source partitions and records ALL membership/role
    blockers, even when a first-failure disposition hid subsequent blockers.
    """
    from src.u02_board.adapter import TRACE_KINDS
    source = digest(raw)
    meta = {r['id']: r for r in manifest['objects']}
    if (source != manifest['source_sha256'] or source != report['source_sha256'] or
            len(meta) != len(manifest['objects']) or
            set(meta) != set(original_blobs) or
            any(digest(original_blobs[s]) != r['geometry_sha256']
                for s, r in meta.items())):
        raise ValueError('C03_WIDTH_SOURCE_BINDING_CHANGED')
    paths = {r['path']['path_id']: r for r in report['paths'] if r.get('path')}
    owner = {}
    for pid, row in paths.items():
        for sid in row['path']['source_ids']:
            if sid in owner:
                raise ValueError('C03_NATIVE_PATH_PARTITION_DUPLICATED')
            owner[sid] = pid
    trace_ids = {s for s, r in meta.items() if r['kind'] in TRACE_KINDS}
    if set(owner) != trace_ids:
        raise ValueError('C03_NATIVE_PATH_PARTITION_INCOMPLETE')
    adjacency = {pid: set() for pid in paths}
    for relation in report['relations']:
        a, b = relation['path_a'], relation['path_b']
        if (a not in paths or b not in paths or
                owner.get(relation['source_a']) != a or
                owner.get(relation['source_b']) != b or relation['blocker_source_ids']):
            raise ValueError('C03_PARALLEL_RELATION_MEMBERSHIP_CHANGED')
        adjacency[a].add(b)
        adjacency[b].add(a)
    components = {}
    for pid in paths:
        if pid in components:
            continue
        seen, todo = {pid}, [pid]
        while todo:
            for neighbor in adjacency[todo.pop()] - seen:
                seen.add(neighbor)
                todo.append(neighbor)
        members = tuple(sorted(seen))
        components.update({p: members for p in members})
    fixed = set(report.get('reviewed_source_roles', {}).get('protected', {}))
    result, groups, seen_definitions = [], {}, set()
    for definition in definitions:
        key = definition['component_id']
        if key in seen_definitions:
            raise ValueError('C03_ORIGINAL_WIDTH_OBLIGATION_DUPLICATED')
        seen_definitions.add(key)
        local = definition['complete_source_ids']
        factor = definition['factor']
        if (not local or len(local) != len(set(local)) or
                type(factor) not in (int, float) or not math.isfinite(factor) or
                not 1 <= factor <= 1.5):
            raise ValueError('C03_COMPLETE_WIDTH_INTENT_INVALID')
        parents = {owner.get(s) for s in local}
        if len(parents) != 1 or None in parents:
            raise ValueError('C03_LOCAL_WIDTH_PARENT_NOT_ESTABLISHED')
        pid = next(iter(parents))
        members = components[pid]
        group_id = digest(json.dumps(members, separators=(',', ':')).encode())
        native = sorted(s for p in members for s in paths[p]['path']['source_ids'])
        if group_id not in groups:
            groups[group_id] = dict(parent_paths=list(members),
                native_source_ids=native, reviewed_fixed_source_ids=sorted(fixed.intersection(native)),
                requested_reference_factors=[], reference_obligation_ids=[])
        group = groups[group_id]
        group['reference_obligation_ids'].append(key)
        group['requested_reference_factors'].append(definition['factor'])
        result.append(dict(reference_route=key, reference_factor=definition['factor'],
            required_positive=definition['factor'] > 1, complete_parent=pid,
            local_source_ids=local, complete_parent_members=paths[pid]['path']['source_ids'],
            extra_parent_members=sorted(set(paths[pid]['path']['source_ids'])-set(local)),
            complete_group_id=group_id, disposition=paths[pid]['disposition'],
            fixed_parent_members=sorted(fixed.intersection(paths[pid]['path']['source_ids'])),
            scope='Complete parent/group authority required; local view grants no width permission'))
    for group in groups.values():
        group['minimum_requested_uniform_factor'] = max(group['requested_reference_factors'])
        group['permissions_granted'] = False
    return dict(records=result, groups=groups,
                original_positive=sum(r['required_positive'] for r in result),
                complete_native_partition=len(owner), permissions='UNCHANGED')
