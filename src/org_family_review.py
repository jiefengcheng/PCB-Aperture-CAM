"""Build a read-only visual index from one verified ORG family-map bundle."""
from __future__ import annotations

import json
import hashlib
import math
from collections import Counter
from pathlib import Path

from shapely import from_wkb

from .family_map_storage import verify_bundle
from .revision_catalog import RevisionCatalog
from .visual_scene import svg_path


REVIEW_SCHEMA = 'pcb-org-family-review-projection/3'
MAX_REVIEW_BYTES = 64 * 1024 * 1024
SIMPLIFICATION_MM = 0.00005
SIMPLIFIED_COORDINATE_DECIMALS = 5
STORED_COORDINATE_DECIMALS = 9


def require_org_family_resource_budget(label, size, limit=MAX_REVIEW_BYTES):
    """Enforce the cap against the exact bytes published or loaded."""
    if not isinstance(size, int) or size < 0 or size > limit:
        raise ValueError(f'{label} exceeds the 64 MiB resource budget')


def validate_geometry_path_bindings(projection, stored_geometry_paths=None):
    """Verify each serialized SVG path against its pinned WKB identity and digest."""
    paths = projection.get('geometry_paths', {})
    bindings = projection.get('geometry_bindings', {})
    if not isinstance(paths, dict) or not isinstance(bindings, dict) or set(paths) != set(bindings):
        raise ValueError('ORG_FAMILY_GEOMETRY_BINDING_SET_MISMATCH')
    stored = stored_geometry_paths
    if stored is None:
        stored = projection.get('stored_geometry_paths')
    if stored is not None and (not isinstance(stored, dict) or set(stored) != set(bindings)):
        raise ValueError('ORG_FAMILY_STORED_GEOMETRY_BINDING_SET_MISMATCH')
    for geometry_key, binding in bindings.items():
        if (not isinstance(geometry_key, str) or len(geometry_key) != 64 or
                any(c not in '0123456789abcdef' for c in geometry_key) or
                not isinstance(binding, dict) or binding.get('source_wkb_sha256') != geometry_key or
                binding.get('derivation') != 'pcb-org-svg-path/v1'):
            raise ValueError('ORG_FAMILY_GEOMETRY_SOURCE_BINDING_INVALID')
        simple = paths.get(geometry_key)
        if (not isinstance(simple, str) or not simple.strip() or
                hashlib.sha256(simple.encode('utf-8')).hexdigest() != binding.get('simplified_path_sha256')):
            raise ValueError('ORG_FAMILY_SIMPLIFIED_GEOMETRY_PATH_HASH_MISMATCH')
        if stored is not None:
            exact = stored.get(geometry_key)
            if (not isinstance(exact, str) or not exact.strip() or
                    hashlib.sha256(exact.encode('utf-8')).hexdigest() != binding.get('stored_path_sha256')):
                raise ValueError('ORG_FAMILY_STORED_GEOMETRY_PATH_HASH_MISMATCH')


def validate_complete_physical_groups(projection, stored_geometry_paths=None, *, validate_paths=True):
    """Reject COMPLETE groups whose IDs do not resolve to pinned drawable sources."""
    if validate_paths:
        validate_geometry_path_bindings(projection, stored_geometry_paths)
    binding = projection.get('binding', {})
    source_objects = projection.get('source_objects', {})
    geometry_paths = projection.get('geometry_paths', {})
    for group in projection.get('physical_groups', []):
        if group.get('inspection_status') != 'COMPLETE':
            continue
        if (not isinstance(binding.get('org_revision'), str) or
                not isinstance(binding.get('org_source_sha256'), str)):
            raise ValueError('ORG_FAMILY_GROUP_SOURCE_BINDING_MISSING')
        ids = group.get('source_member_ids')
        count = group.get('source_member_count')
        if (not isinstance(ids, list) or not isinstance(count, int) or
                count < 1 or count > 100 or len(ids) != count or
                any(not isinstance(object_id, str) for object_id in ids) or
                len(set(ids)) != count):
            raise ValueError('ORG_FAMILY_GROUP_MEMBER_COUNT_MISMATCH')
        layer = group.get('layer')
        for object_id in ids:
            record = source_objects.get(object_id)
            if not isinstance(record, dict) or record.get('object_id') != object_id:
                raise ValueError('ORG_FAMILY_GROUP_SOURCE_ID_MISMATCH')
            if (record.get('source_revision') != binding.get('org_revision') or
                    record.get('source_sha256') != binding.get('org_source_sha256')):
                raise ValueError('ORG_FAMILY_GROUP_SOURCE_BINDING_MISMATCH')
            span = record.get('source_span')
            if (not isinstance(span, list) or len(span) != 2 or
                    not all(isinstance(value, int) for value in span) or
                    span[0] < 0 or span[1] <= span[0]):
                raise ValueError('ORG_FAMILY_GROUP_SOURCE_SPAN_INVALID')
            if not layer or layer not in record.get('layers', []):
                raise ValueError('ORG_FAMILY_GROUP_LAYER_MISMATCH')
            geometry_key = record.get('geometry_sha256')
            path = geometry_paths.get(geometry_key) if geometry_key else None
            bounds = record.get('bounds_mm')
            if (not geometry_key or not isinstance(path, str) or not path.strip() or
                    not isinstance(bounds, list) or len(bounds) != 4 or
                    not all(isinstance(value, (int, float)) and math.isfinite(value)
                            for value in bounds)):
                raise ValueError('ORG_FAMILY_GROUP_GEOMETRY_MISSING')


def build_review_projection(root, bundle):
    """Project verified map records and referenced ORG geometry for inspection.

    The projection contains no source bytes. ORG object IDs, revision IDs,
    geometry hashes, predicates, uncertainty and family alternatives survive.
    """
    root, bundle = Path(root).resolve(), Path(bundle).resolve()
    verified = verify_bundle(root, bundle)
    materialization = json.loads((bundle / 'materialization.json').read_text())
    map_info = materialization['derived_map']
    org_revision = materialization['org_artifact']['revision']

    with RevisionCatalog(bundle / 'store', read_only=True) as catalog:
        derived = catalog.snapshot(map_info['revision'])
        org = catalog.snapshot(org_revision)
        map_document = json.loads(catalog.read_payload(derived['source_sha256']))
        source_by_id = {record['id']: record for record in org['objects']}
        geometry_paths = {}
        stored_geometry_paths = {}
        geometry_bindings = {}
        source_objects = {}

        def source_projection(object_id):
            if object_id in source_objects:
                return source_objects[object_id]
            record = source_by_id.get(object_id)
            if record is None:
                raise ValueError('ORG source reference missing while building review projection')
            geometry_key = record.get('geometry_sha256')
            if geometry_key and geometry_key not in geometry_paths:
                geometry = from_wkb(catalog.read_payload(geometry_key))
                geometry_paths[geometry_key] = svg_path(
                    geometry, tolerance=SIMPLIFICATION_MM,
                    coordinate_precision=SIMPLIFIED_COORDINATE_DECIMALS)
                stored_geometry_paths[geometry_key] = svg_path(
                    geometry, tolerance=None,
                    coordinate_precision=STORED_COORDINATE_DECIMALS)
                geometry_bindings[geometry_key] = {
                    'source_wkb_sha256': geometry_key,
                    'derivation': 'pcb-org-svg-path/v1',
                    'simplified_path_sha256': hashlib.sha256(
                        geometry_paths[geometry_key].encode('utf-8')).hexdigest(),
                    'stored_path_sha256': hashlib.sha256(
                        stored_geometry_paths[geometry_key].encode('utf-8')).hexdigest(),
                }
            projected = {
                'object_id': record['id'],
                'source_revision': org_revision,
                'source_sha256': org['source_sha256'],
                'source_span': record['source_span'],
                'kind': record['kind'],
                'layers': record.get('layers', []),
                'native_id': record.get('native_id'),
                'geometry_sha256': geometry_key,
                'bounds_mm': record.get('bounds_mm'),
                'coverage': record.get('coverage'),
            }
            source_objects[object_id] = projected
            return projected

        entities = map_document['records']
        member_rows = {row['member_key']: row for row in entities
                       if row.get('entity_type') == 'candidate_member'}
        family_rows = [row for row in entities if row.get('entity_type') == 'family']
        group_rows = [row for row in entities if row.get('entity_type') == 'physical_group']
        catalog_ids = {}
        for entity, stored in zip(entities, derived['objects']):
            key = entity.get('member_key') or entity.get('family_key') or entity.get('physical_group_key')
            catalog_ids[(entity['entity_type'], key)] = stored['id']

        members = []
        for key, row in sorted(member_rows.items()):
            refs = []
            for ref in row.get('source_refs', []):
                source_projection(ref['object_id'])
                refs.append(dict(ref))
            members.append({
                'member_key': key,
                'catalogue_record_id': catalog_ids[('candidate_member', key)],
                'status': row['status'],
                'family_membership_status': row['family_membership_status'],
                'candidate_family_keys': row.get('candidate_family_keys', []),
                'physical_group_key': row.get('physical_group_key'),
                'geometry': row['geometry'],
                'trace_associations': row.get('trace_associations', {}),
                'reference_features': row.get('reference_features', {}),
                'source_refs': refs,
            })

        # Map physical-group keys to persisted record identities and counts.
        groups = []
        for row in group_rows:
            catalog_id = catalog_ids[('physical_group', row['physical_group_key'])]
            source_ids = sorted(row['source_members'])
            kind_counts = Counter(source_by_id[object_id]['kind'] for object_id in source_ids)
            # Source objects are already projected through map/member evidence.
            # Store only IDs here rather than repeating full object records in
            # every group; those copies pushed this review over its 64 MiB cap.
            inspectable = len(source_ids) <= 100 and all(
                object_id in source_objects
                and source_objects[object_id].get('geometry_sha256') in geometry_paths
                for object_id in source_ids)
            groups.append({'physical_group_key': row['physical_group_key'],
                           'catalogue_record_id': catalog_id,
                           'layer': row['layer'], 'predicate': row['predicate'],
                           'source_member_count': len(source_ids),
                           'source_member_kind_counts': dict(sorted(kind_counts.items())),
                           'inspection_status': 'COMPLETE' if inspectable else 'SUMMARY_ONLY_LARGE_OR_UNPROJECTED_GROUP',
                           'source_member_ids': source_ids if inspectable else []})
        group_index = {row['physical_group_key']: row for row in groups}

        families = []
        for row in family_rows:
            families.append({
                'family_key': row['family_key'],
                'status': row['status'],
                'member_keys': row['members'],
                'shape_signature': row['shape_signature'],
                'nominal_trace_contact_count': row['nominal_trace_contact_count'],
                'canonical_displacement_mm': row['canonical_displacement_mm'],
                'vector_bucket': row['vector_bucket'],
                'vector_tolerance_mm': row['vector_tolerance_mm'],
                'locality_radius_mm': row['locality_radius_mm'],
                'family_rule': row['family_rule'],
                'support_pairs': row['support_pairs'],
            })

        # Excluded filled F.Cu source shapes are not family-map members. Re-run
        # the existing classifier against the same pinned ORG bytes so the UI
        # can navigate them without changing recognition output or identity.
        source_bytes = catalog.read_payload(org['source_sha256'])
        if hashlib.sha256(source_bytes).hexdigest() != org['source_sha256']:
            raise ValueError('ORG source bytes changed during review projection')
        source_text = source_bytes.decode('utf-8')
        from .org_family_recognition import _source_node, _supported_feature
        excluded_features = []
        excluded_counts = Counter()
        for record in org['objects']:
            if 'F.Cu' not in record.get('layers', []) or record.get('kind') not in ('gr_circle', 'gr_poly'):
                continue
            geometry_key = record.get('geometry_sha256')
            if not geometry_key:
                excluded_counts['GEOMETRY_UNAVAILABLE'] += 1
                continue
            geometry = from_wkb(catalog.read_payload(geometry_key))
            node = _source_node(source_text, record, org['source_sha256'])
            feature, reason = _supported_feature(record, node, geometry)
            if reason:
                excluded_counts[reason] += 1
                source_projection(record['id'])
                excluded_features.append({
                    'object_id': record['id'],
                    'source_revision': org_revision,
                    'source_sha256': org['source_sha256'],
                    'source_span': record['source_span'],
                    'kind': record['kind'],
                    'layer': 'F.Cu',
                    'exclusion_reason': reason,
                    'geometry_sha256': geometry_key,
                    'area_mm2': record.get('filled_area_mm2'),
                })
        declared_exclusions = materialization.get('coverage', {}).get('seed_exclusions', {})
        if dict(sorted(excluded_counts.items())) != dict(sorted(declared_exclusions.items())):
            raise ValueError('Recomputed ORG seed exclusions do not match the pinned map coverage')

    for member in members:
        group = group_index.get(member['physical_group_key'])
        member['physical_group'] = group
    map_source_ids = {ref['object_id'] for member in members for ref in member['source_refs']}
    group_inspection_source_ids = {
        object_id for group in groups for object_id in group['source_member_ids']
    }
    map_geometry_hashes = {source_objects[object_id]['geometry_sha256']
                           for object_id in map_source_ids
                           if source_objects[object_id].get('geometry_sha256')}
    projection = {
        'schema': REVIEW_SCHEMA,
        'binding': {
            'dataset_id': materialization['dataset_id'],
            'org_revision': org_revision,
            'org_source_sha256': materialization['org_artifact']['source_sha256'],
            'map_revision': verified['map_revision'],
            'map_content_sha256': verified['content_sha256'],
            'input_snapshot_id': materialization['derived_map']['input_snapshot_id'],
        },
        'coverage': materialization['coverage'],
        'members': members,
        'families': families,
        'physical_groups': groups,
        'source_objects': source_objects,
        'projection_counts': {
            'map_referenced_source_object_count': len(map_source_ids),
            'map_referenced_geometry_path_count': len(map_geometry_hashes),
            'group_inspection_additional_source_object_count': len(group_inspection_source_ids - map_source_ids),
            'group_inspection_group_count': sum(group['inspection_status'] == 'COMPLETE' for group in groups),
            'exception_source_object_count': len(excluded_features),
        },
        'geometry_paths': geometry_paths,
        'geometry_bindings': geometry_bindings,
        'stored_geometry_paths': stored_geometry_paths,
        'excluded_features': sorted(excluded_features, key=lambda row: row['source_span']),
        'display_geometry': {
            'default_mode': 'SIMPLIFIED',
            'simplification_parameter_mm': SIMPLIFICATION_MM,
            'simplified_coordinate_decimals': SIMPLIFIED_COORDINATE_DECIMALS,
            'stored_mode': 'STORED_WKB_UNSIMPLIFIED',
            'stored_coordinate_decimals': STORED_COORDINATE_DECIMALS,
            'stored_coordinate_rounding_bound_mm': 0.5 * 10 ** -STORED_COORDINATE_DECIMALS,
            'coordinate_unit': 'mm',
            'coordinate_transform': 'identity_from_org_wkb_xy',
            'path_fill_rule': 'evenodd',
            'viewport_policy': 'source_bounds_with_padding_no_geometry_clipping',
        },
        'display_limitations': [
            'Display paths are simplified for inspection and do not replace stored geometry or acceptance predicates.',
            'Candidate members and families are hypotheses; physical groups are connected components, not lands or nets.',
            'F.Mask and F.Paste are geometric associations only; their manufacturing purpose is unknown.',
        ],
    }
    validate_complete_physical_groups(projection)
    # Stored-precision paths are written to a separate, hash-bound snapshot by
    # the publisher and fetched only when the reviewer selects stored mode.
    # Budget the two published resources separately, as they are serialized
    # and served separately; counting both in this in-memory intermediate made
    # a valid 27 MiB review view fail just because its independent 40 MiB
    # optional geometry resource was present in the builder result.
    stored_encoded = json.dumps(projection['stored_geometry_paths'], sort_keys=True,
                                separators=(',', ':'), allow_nan=False).encode()
    review_projection = {key: value for key, value in projection.items()
                         if key != 'stored_geometry_paths'}
    encoded = json.dumps(review_projection, sort_keys=True, separators=(',', ':'),
                         allow_nan=False).encode()
    require_org_family_resource_budget('ORG family review projection', len(encoded))
    require_org_family_resource_budget('ORG stored-geometry resource', len(stored_encoded))
    projection['projection_sha256'] = __import__('hashlib').sha256(encoded).hexdigest()
    return projection
