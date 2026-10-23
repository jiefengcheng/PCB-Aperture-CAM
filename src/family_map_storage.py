"""Immutable ORG-only derived map revisions on the existing RevisionCatalog.

The map has its own revision namespace. References to ORG objects live in
validated record fields; same-revision SQL relations never cross revisions.
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

from .revision_catalog import CatalogError, RevisionCatalog, canonical, digest
from .ingestion_files import sha

MAP_SCHEMA = 'pcb-org-family-map/2'
LEGACY_MAP_SCHEMA = 'pcb-org-family-map/1'
BUNDLE_SCHEMA = 'pcb-profile-derived-family-map/1'
RECEIPT_SCHEMA = 'pcb-profile-derived-family-map-receipt/1'
ENTITY_KINDS = {'candidate_member', 'family', 'physical_group', 'geometry_probe'}


def require(condition, reason):
    if not condition:
        raise CatalogError(reason)


def input_snapshot_id(*, dataset_id, org_revision, org_source_sha256,
                      geometry_materialization_sha256, parser_version,
                      implementation_sha256, config, predicate_versions):
    """Hash only ORG and recognition inputs. There is deliberately no EDIT arg."""
    for value, reason in ((org_revision, 'INVALID_ORG_REVISION'),
                          (org_source_sha256, 'INVALID_ORG_SOURCE_HASH'),
                          (geometry_materialization_sha256, 'INVALID_GEOMETRY_DIGEST'),
                          (implementation_sha256, 'INVALID_IMPLEMENTATION_DIGEST')):
        require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), reason)
    inputs = {
        'schema': 'pcb-org-family-map-input/1',
        'dataset_id': dataset_id,
        'org_revision': org_revision,
        'org_source_sha256': org_source_sha256,
        'geometry_materialization_sha256': geometry_materialization_sha256,
        'parser_version': parser_version,
        'implementation_sha256': implementation_sha256,
        'config': config,
        'predicate_versions': predicate_versions,
    }
    return digest(canonical(inputs)), inputs


def _map_bytes(input_id, entities, *, schema=MAP_SCHEMA):
    require(re.fullmatch(r'[0-9a-f]{64}', input_id) is not None, 'INVALID_INPUT_SNAPSHOT_ID')
    require(isinstance(entities, list), 'INVALID_DERIVED_RECORDS')
    encoded = []
    for entity in entities:
        require(isinstance(entity, dict) and entity.get('entity_type') in ENTITY_KINDS,
                'INVALID_DERIVED_ENTITY_KIND')
        encoded.append(canonical(entity))
    prefix = b'{"input_snapshot_id":' + canonical(input_id) + b',"records":['
    out = bytearray(prefix)
    spans = []
    for index, record in enumerate(encoded):
        if index:
            out.extend(b',')
        start = len(out)
        out.extend(record)
        spans.append([start, len(out)])
    out.extend(b'],"schema":' + canonical(schema) + b'}')
    return bytes(out), spans


def _relation_rows(relations, row_ids, input_id):
    rows = []
    require(isinstance(relations, list), 'INVALID_DERIVED_RELATIONS')
    for relation in relations:
        source_index = relation.get('source_index')
        target_index = relation.get('target_index')
        require(isinstance(source_index, int) and not isinstance(source_index, bool)
                and 0 <= source_index < len(row_ids), 'INVALID_RELATION_SOURCE')
        require(isinstance(target_index, int) and not isinstance(target_index, bool)
                and 0 <= target_index < len(row_ids), 'INVALID_RELATION_TARGET')
        relation_type = relation.get('type')
        require(isinstance(relation_type, str) and relation_type, 'INVALID_RELATION_TYPE')
        witness = relation.get('witness')
        source_id, target_id = row_ids[source_index], row_ids[target_index]
        occurrence = digest(canonical([input_id, source_id, target_id, relation_type, witness]))
        rows.append({'occurrence': occurrence, 'source': source_id, 'target': target_id,
                     'type': relation_type, 'witness': witness})
    return sorted(rows, key=lambda row: row['occurrence'])


def _rows_for_entities(payload, spans, entities):
    source_hash = digest(payload)
    rows = []
    for entity, span in zip(entities, spans):
        start, end = span
        row = dict(entity)
        row.update({'id': f'{source_hash}:bytes:{start}:{end}', 'source_sha256': source_hash,
                    'source_span': span, 'representation': 'derived_family_map',
                    'kind': entity['entity_type'], 'parent_id': None, 'native_id': None})
        rows.append(row)
    return rows


def _validate_source_refs(catalog, org_revision, entities):
    org = catalog.snapshot(org_revision)
    available = {row['id'] for row in org['objects']}
    source_sha = org['source_sha256']
    for entity in entities:
        refs = entity.get('source_refs', [])
        require(isinstance(refs, list), 'INVALID_SOURCE_REFS')
        for ref in refs:
            require(isinstance(ref, dict), 'INVALID_SOURCE_REF')
            require(ref.get('source_revision') == org_revision, 'CROSS_REVISION_SOURCE_REF')
            object_id = ref.get('object_id')
            require(object_id in available, 'DANGLING_ORG_OBJECT_REF')
            require(object_id.startswith(source_sha + ':bytes:'), 'ORG_OBJECT_SOURCE_HASH_MISMATCH')
            require(isinstance(ref.get('role'), str) and ref['role'], 'SOURCE_REF_ROLE_REQUIRED')
    return {row['id']: row for row in org['objects']}


def _validate_recognition_reference_closure(org_rows, entities, org_revision):
    """Check that every nested recognition edge is revision-bound and indexed."""
    def check_ref(ref, *, role, kinds, layer):
        require(isinstance(ref, dict) and ref.get('role') == role,
                'RECOGNITION_SOURCE_REF_ROLE_MISMATCH')
        require(ref.get('source_revision') == org_revision,
                'RECOGNITION_SOURCE_REVISION_MISMATCH')
        row = org_rows.get(ref.get('object_id'))
        require(row is not None, 'DANGLING_RECOGNITION_SOURCE_REF')
        require(row.get('kind') in kinds and layer in row.get('layers', []),
                'RECOGNITION_SOURCE_KIND_LAYER_MISMATCH')
        require(bool(row.get('geometry_sha256')), 'RECOGNITION_SOURCE_GEOMETRY_MISSING')
        return (ref['source_revision'], ref['object_id'], role), row

    for entity in entities:
        if entity.get('entity_type') != 'candidate_member' or entity.get('status') != 'RESTRICTED_SEED_HYPOTHESIS':
            continue
        refs = entity.get('source_refs')
        require(isinstance(refs, list), 'RECOGNITION_SOURCE_REFS_REQUIRED')
        ref_keys = [(ref.get('source_revision'), ref.get('object_id'), ref.get('role'))
                    for ref in refs if isinstance(ref, dict)]
        require(len(ref_keys) == len(refs) and len(set(ref_keys)) == len(ref_keys),
                'DUPLICATE_OR_MALFORMED_RECOGNITION_SOURCE_REFS')
        expected_refs = set()
        seed_refs = [ref for ref in refs if ref.get('role') == 'local_land_candidate_seed']
        require(len(seed_refs) == 1, 'RECOGNITION_MEMBER_SEED_REF_COUNT')
        seed_key, seed_row = check_ref(seed_refs[0], role='local_land_candidate_seed',
                                       kinds={'gr_circle', 'gr_poly'}, layer='F.Cu')
        expected_refs.add(seed_key)
        geometry = entity.get('geometry') or {}
        require(geometry.get('geometry_sha256') == seed_row.get('geometry_sha256'),
                'RECOGNITION_SEED_GEOMETRY_BINDING_MISMATCH')
        require(geometry.get('source_kind') == seed_row.get('kind'),
                'RECOGNITION_SEED_KIND_BINDING_MISMATCH')

        trace_data = entity.get('trace_associations') or {}
        require(trace_data.get('predicate'), 'RECOGNITION_TRACE_PREDICATE_MISSING')
        for key, allowed_roles in (('nominal_contacts', {'incident_trace'}),
                                   ('uncertain_associations', {'incident_trace', 'uncertain_trace_contact'})):
            rows = trace_data.get(key)
            require(isinstance(rows, list), 'RECOGNITION_TRACE_ASSOCIATIONS_MISSING')
            for association in rows:
                role = association.get('role') if isinstance(association, dict) else None
                require(role in allowed_roles, 'RECOGNITION_TRACE_ROLE_INVALID')
                ref_key, _ = check_ref(association, role=role, kinds={'segment', 'arc'}, layer='F.Cu')
                require(ref_key in set(ref_keys), 'NESTED_TRACE_REF_NOT_INDEXED')
                distance = association.get('distance_mm')
                require(isinstance(distance, (int, float)) and math.isfinite(distance)
                        and 0 <= distance <= 0.00002, 'RECOGNITION_TRACE_DISTANCE_INVALID')
                if key == 'nominal_contacts':
                    require(distance == 0 and association.get('status') == 'NOMINAL_CONTACT',
                            'NOMINAL_TRACE_STATUS_MISMATCH')
                else:
                    require(association.get('status') == 'CONTACT_STATUS_UNCERTAIN',
                            'UNCERTAIN_TRACE_STATUS_MISMATCH')
                expected_refs.add(ref_key)

        reference_data = entity.get('reference_features') or {}
        for layer in ('F.Mask', 'F.Paste'):
            association = reference_data.get(layer)
            require(isinstance(association, dict), 'RECOGNITION_REFERENCE_LAYER_MISSING')
            supported = association.get('candidates')
            unsupported = association.get('unsupported_candidates')
            require(isinstance(supported, list) and isinstance(unsupported, list),
                    'RECOGNITION_REFERENCE_CANDIDATES_MISSING')
            for candidate in supported:
                ref_key, _ = check_ref(candidate, role=f'{layer}_geometric_feature_candidate',
                                       kinds={'gr_circle', 'gr_poly'}, layer=layer)
                require(ref_key in set(ref_keys), 'NESTED_REFERENCE_REF_NOT_INDEXED')
                expected_refs.add(ref_key)
            for candidate in unsupported:
                reason = candidate.get('reason') if isinstance(candidate, dict) else None
                require(isinstance(reason, str) and reason, 'UNSUPPORTED_REFERENCE_REASON_MISSING')
                ref_key, _ = check_ref(candidate, role=f'{layer}_unsupported_feature_candidate',
                                       kinds={'gr_circle', 'gr_poly'}, layer=layer)
                require(ref_key in set(ref_keys), 'NESTED_UNSUPPORTED_REF_NOT_INDEXED')
                expected_refs.add(ref_key)
            expected_status = ('UNIQUE_GEOMETRIC_CANDIDATE'
                               if len(supported) == 1 and not unsupported else
                               'AMBIGUOUS' if supported and (len(supported) > 1 or unsupported) else
                               'UNSUPPORTED' if unsupported else 'UNMATCHED')
            require(association.get('status') == expected_status,
                    'REFERENCE_ASSOCIATION_STATUS_MISMATCH')
        require(set(ref_keys) == expected_refs, 'RECOGNITION_SOURCE_REF_CLOSURE_MISMATCH')


def _validate_derived_closure(entities, relations, coverage=None):
    """Fail closed on dangling family/member keys and family-member links."""
    members = [row for row in entities if row.get('entity_type') == 'candidate_member']
    families = [row for row in entities if row.get('entity_type') == 'family']
    groups = [row for row in entities if row.get('entity_type') == 'physical_group']
    member_indexes = {}
    for index, member in enumerate(entities):
        if member.get('entity_type') != 'candidate_member':
            continue
        key = member.get('member_key')
        require(isinstance(key, str) and re.fullmatch(r'[0-9a-f]{64}', key) is not None,
                'INVALID_CANDIDATE_MEMBER_KEY')
        require(key not in member_indexes, 'DUPLICATE_CANDIDATE_MEMBER_KEY')
        member_indexes[key] = index
    family_indexes = set()
    expected_links = set()
    expected_family_keys = defaultdict(set)
    groups_by_key = {}
    group_source_ids = set()
    for index, group in enumerate(entities):
        if group.get('entity_type') != 'physical_group':
            continue
        key = group.get('physical_group_key')
        require(isinstance(key, str) and re.fullmatch(r'[0-9a-f]{64}', key) is not None,
                'INVALID_PHYSICAL_GROUP_KEY')
        require(key not in groups_by_key, 'DUPLICATE_PHYSICAL_GROUP_KEY')
        source_members = group.get('source_members')
        refs = group.get('source_refs')
        require(isinstance(source_members, list) and source_members
                and len(source_members) == len(set(source_members)),
                'INVALID_PHYSICAL_GROUP_MEMBERS')
        require(isinstance(refs, list), 'INVALID_PHYSICAL_GROUP_SOURCE_REFS')
        ref_ids = [ref.get('object_id') for ref in refs if isinstance(ref, dict)
                   and ref.get('role') == 'physical_group_member']
        require(len(ref_ids) == len(refs) and len(ref_ids) == len(set(ref_ids))
                and set(ref_ids) == set(source_members),
                'PHYSICAL_GROUP_SOURCE_REF_CLOSURE_MISMATCH')
        require(not (group_source_ids & set(source_members)),
                'SOURCE_OBJECT_IN_MULTIPLE_PHYSICAL_GROUPS')
        group_source_ids.update(source_members)
        groups_by_key[key] = index
    expected_group_links = set()
    for member_index, member in enumerate(entities):
        if member.get('entity_type') != 'candidate_member':
            continue
        group_key = member.get('physical_group_key')
        if group_key is None:
            continue
        require(group_key in groups_by_key, 'DANGLING_PHYSICAL_GROUP_KEY')
        group_index = groups_by_key[group_key]
        seed_refs = [ref for ref in member.get('source_refs', [])
                     if isinstance(ref, dict) and ref.get('role') == 'local_land_candidate_seed']
        require(len(seed_refs) == 1, 'PHYSICAL_GROUP_MEMBER_SEED_REF_MISSING')
        seed_id = seed_refs[0]['object_id']
        require(seed_id in entities[group_index]['source_members'],
                'CANDIDATE_SEED_NOT_IN_PHYSICAL_GROUP')
        expected_group_links.add((member_index, group_index))
    for index, family in enumerate(entities):
        if family.get('entity_type') != 'family':
            continue
        key = family.get('family_key')
        require(isinstance(key, str) and re.fullmatch(r'[0-9a-f]{64}', key) is not None,
                'INVALID_FAMILY_KEY')
        require(key not in family_indexes, 'DUPLICATE_FAMILY_KEY')
        family_indexes.add(key)
        keys = family.get('members')
        require(isinstance(keys, list) and len(keys) >= 3 and len(set(keys)) == len(keys),
                'INVALID_FAMILY_MEMBERS')
        require(all(member_key in member_indexes for member_key in keys),
                'DANGLING_FAMILY_MEMBER_KEY')
        pairs = family.get('support_pairs')
        require(isinstance(pairs, list) and len(pairs) >= 2, 'INSUFFICIENT_FAMILY_SUPPORT_PAIRS')
        supported = set()
        for pair in pairs:
            pair_keys = pair.get('member_keys') if isinstance(pair, dict) else None
            require(isinstance(pair_keys, list) and len(pair_keys) == 2
                    and pair_keys[0] != pair_keys[1], 'INVALID_FAMILY_SUPPORT_PAIR')
            normalized = tuple(sorted(pair_keys))
            require(normalized not in supported, 'DUPLICATE_FAMILY_SUPPORT_PAIR')
            require(set(normalized) <= set(keys), 'FAMILY_SUPPORT_MEMBER_OUTSIDE_FAMILY')
            supported.add(normalized)
        require({key for pair in supported for key in pair} == set(keys),
                'FAMILY_MEMBERSHIP_SUPPORT_CLOSURE_MISMATCH')
        expected_links.update((index, member_indexes[member_key]) for member_key in keys)
        for member_key in keys:
            expected_family_keys[member_key].add(key)
    for member in members:
        actual_keys = member.get('candidate_family_keys', [])
        require(isinstance(actual_keys, list) and len(actual_keys) == len(set(actual_keys)),
                'INVALID_MEMBER_FAMILY_BACKLINKS')
        require(set(actual_keys) == expected_family_keys.get(member['member_key'], set()),
                'MEMBER_FAMILY_BACKLINK_CLOSURE_MISMATCH')
    actual_links = set()
    actual_group_links = set()
    for relation in relations:
        if relation.get('type') == 'member_physical_group':
            source, target = relation.get('source_index'), relation.get('target_index')
            require(isinstance(source, int) and 0 <= source < len(entities)
                    and entities[source].get('entity_type') == 'candidate_member',
                    'INVALID_MEMBER_GROUP_RELATION_SOURCE')
            require(isinstance(target, int) and 0 <= target < len(entities)
                    and entities[target].get('entity_type') == 'physical_group',
                    'INVALID_MEMBER_GROUP_RELATION_TARGET')
            actual_group_links.add((source, target))
            continue
        if relation.get('type') != 'family_member':
            continue
        source, target = relation.get('source_index'), relation.get('target_index')
        require(isinstance(source, int) and 0 <= source < len(entities)
                and entities[source].get('entity_type') == 'family',
                'INVALID_FAMILY_RELATION_SOURCE')
        require(isinstance(target, int) and 0 <= target < len(entities)
                and entities[target].get('entity_type') == 'candidate_member',
                'INVALID_FAMILY_RELATION_TARGET')
        actual_links.add((source, target))
    require(len(actual_links) == sum(1 for row in relations if row.get('type') == 'family_member'),
            'DUPLICATE_FAMILY_MEMBER_RELATION')
    require(actual_links == expected_links, 'FAMILY_MEMBER_RELATION_CLOSURE_MISMATCH')
    require(len(actual_group_links) == sum(1 for row in relations
                                           if row.get('type') == 'member_physical_group'),
            'DUPLICATE_MEMBER_GROUP_RELATION')
    require(actual_group_links == expected_group_links, 'MEMBER_GROUP_RELATION_CLOSURE_MISMATCH')
    if coverage and 'physical_group_records' in coverage \
            and coverage.get('physical_topology', {}).get('status') == 'COMPLETE':
        topology = coverage['physical_topology']
        require(coverage.get('physical_group_records') == len(groups),
                'PHYSICAL_GROUP_COVERAGE_COUNT_MISMATCH')
        require(len(groups) == topology.get('physical_contact_components'),
                'PHYSICAL_GROUP_COUNT_MISMATCH')
        require(len(group_source_ids) == topology.get('source_objects'),
                'PHYSICAL_GROUP_SOURCE_COVERAGE_MISMATCH')


def clone_revision(source_store, target_catalog, revision):
    """Copy one exact artifact revision and only its required CAS payloads."""
    with RevisionCatalog(source_store, read_only=True) as source:
        manifest = source.snapshot(revision)
        payloads = {manifest['source_sha256']}
        payloads.update(row['geometry_sha256'] for row in manifest['objects']
                        if row.get('geometry_sha256'))
        data = {key: source.read_payload(key) for key in sorted(payloads)}
    for key, raw in data.items():
        require(target_catalog.put_payload(raw) == key, 'CLONED_PAYLOAD_HASH_MISMATCH')
    cloned = target_catalog.import_revision(data[manifest['source_sha256']], manifest['objects'],
                                           manifest['relations'], manifest['config'])
    require(cloned == revision, 'CLONED_REVISION_ID_MISMATCH')
    return manifest


def _map_content_digest(entities, relations, coverage, *, schema=MAP_SCHEMA):
    semantic_relations = [{'source_index': row['source_index'], 'target_index': row['target_index'],
                           'type': row['type'], 'witness': row.get('witness')}
                          for row in relations]
    semantic_relations.sort(key=canonical)
    return digest(canonical({'schema': schema, 'records': entities,
                             'relations': semantic_relations, 'coverage': coverage}))


def store_family_map(catalog, *, dataset_id, org_revision, input_id, input_spec,
                     entities, relations, coverage):
    """Store a derived map in the same catalog; no source rows are rewritten."""
    require(isinstance(coverage, dict), 'INVALID_MAP_COVERAGE')
    org_rows = _validate_source_refs(catalog, org_revision, entities)
    _validate_recognition_reference_closure(org_rows, entities, org_revision)
    _validate_derived_closure(entities, relations, coverage)
    org = catalog.snapshot(org_revision)
    content_hash = _map_content_digest(entities, relations, coverage)
    payload, spans = _map_bytes(input_id, entities)
    rows = _rows_for_entities(payload, spans, entities)
    relation_rows = _relation_rows(relations, [r['id'] for r in rows], input_id)
    config = {'kind': 'derived-org-family-map/1', 'schema': MAP_SCHEMA,
              'dataset_id': dataset_id, 'org_revision': org_revision,
              'org_source_sha256': org['source_sha256'], 'input_snapshot_id': input_id,
              'input_spec': input_spec, 'family_map_content_sha256': content_hash,
              'coverage': coverage}
    map_revision = catalog.import_revision(payload, rows, relation_rows, config)
    return {'revision': map_revision, 'source_sha256': digest(payload),
            'input_snapshot_id': input_id, 'content_sha256': content_hash,
            'record_count': len(rows), 'relation_count': len(relation_rows)}


def verify_family_map(catalog, *, org_revision, map_revision, expected=None):
    org = catalog.snapshot(org_revision)
    manifest = catalog.snapshot(map_revision)
    config = manifest['config']
    map_schema = config.get('schema')
    require(config.get('kind') == 'derived-org-family-map/1'
            and map_schema in (MAP_SCHEMA, LEGACY_MAP_SCHEMA),
            'INVALID_DERIVED_MAP_CONFIG')
    require(config.get('org_revision') == org_revision, 'MIXED_ORG_REVISION')
    require(config.get('org_source_sha256') == org['source_sha256'], 'MIXED_ORG_SOURCE_HASH')
    payload = catalog.read_payload(manifest['source_sha256'])
    doc = json.loads(payload)
    require(canonical(doc) == payload, 'NONCANONICAL_FAMILY_MAP')
    require(doc.get('schema') == map_schema and doc.get('input_snapshot_id') == config.get('input_snapshot_id'),
            'FAMILY_MAP_INPUT_BINDING_MISMATCH')
    records = doc.get('records')
    require(isinstance(records, list) and len(records) == len(manifest['objects']), 'FAMILY_MAP_RECORD_COUNT_MISMATCH')
    expected_payload, spans = _map_bytes(config['input_snapshot_id'], records, schema=map_schema)
    require(expected_payload == payload, 'FAMILY_MAP_CANONICAL_REENCODE_MISMATCH')
    rows_by_span = {tuple(row['source_span']): row for row in manifest['objects']}
    require(len(rows_by_span) == len(manifest['objects']), 'DUPLICATE_DERIVED_SOURCE_SPAN')
    require(set(rows_by_span) == {tuple(span) for span in spans}, 'FAMILY_MAP_SOURCE_SPANS_MISMATCH')
    for entity, span in zip(records, spans):
        row = rows_by_span[tuple(span)]
        a, b = row['source_span']
        require(payload[a:b] == canonical(entity), 'FAMILY_MAP_SOURCE_SPAN_MISMATCH')
        require(row['representation'] == 'derived_family_map' and row['kind'] == entity['entity_type'],
                'FAMILY_MAP_ROW_TYPE_MISMATCH')
        require(row.get('source_refs', []) == entity.get('source_refs', []), 'FAMILY_MAP_SOURCE_REF_MISMATCH')
    org_rows = _validate_source_refs(catalog, org_revision, records)
    _validate_recognition_reference_closure(org_rows, records, org_revision)
    rels = manifest['relations']
    rows_by_id = {row['id']: row for row in manifest['objects']}
    index_by_span = {tuple(span): index for index, span in enumerate(spans)}
    semantic_relations = []
    for rel in rels:
        require(rel['source'] in rows_by_id and rel['target'] in rows_by_id,
                'CROSS_REVISION_SQL_RELATION')
        source_span = tuple(rows_by_id[rel['source']]['source_span'])
        target_span = tuple(rows_by_id[rel['target']]['source_span'])
        require(source_span in index_by_span and target_span in index_by_span,
                'FAMILY_MAP_RELATION_ENDPOINT_SPAN_MISMATCH')
        semantic_relations.append({'source_index': index_by_span[source_span],
                                   'target_index': index_by_span[target_span],
                                   'type': rel['type'], 'witness': rel.get('witness')})
    _validate_derived_closure(records, semantic_relations, config.get('coverage'))
    require(config.get('family_map_content_sha256') == _map_content_digest(
        records, semantic_relations, config['coverage'], schema=map_schema),
        'FAMILY_MAP_CONTENT_DIGEST_MISMATCH')
    result = {'schema': MAP_SCHEMA, 'org_revision': org_revision, 'map_revision': map_revision,
              'source_sha256': manifest['source_sha256'],
              'input_snapshot_id': config['input_snapshot_id'],
              'content_sha256': config['family_map_content_sha256'],
              'record_count': len(records), 'relation_count': len(rels), 'records': manifest['objects']}
    if expected:
        for key, value in expected.items():
            require(result.get(key) == value, 'FAMILY_MAP_EXPECTATION_MISMATCH: ' + key)
    return result


def _bundle_hashes(bundle):
    return {p.relative_to(bundle).as_posix(): sha(p) for p in sorted(bundle.rglob('*'))
            if p.is_file() and p.name != 'acceptance.json'}


def verify_bundle(root, bundle):
    root = Path(root).resolve()
    bundle = Path(bundle).resolve()
    require(bundle.is_relative_to(root / 'out'), 'FAMILY_MAP_BUNDLE_OUTSIDE_CHECKOUT')
    manifest = json.loads((bundle / 'materialization.json').read_text())
    receipt = json.loads((bundle / 'acceptance.json').read_text())
    require(manifest.get('schema') == BUNDLE_SCHEMA and receipt.get('schema') == RECEIPT_SCHEMA,
            'INVALID_FAMILY_MAP_BUNDLE_SCHEMA')
    require(receipt.get('status') == 'PASS' and receipt.get('dataset_id') == manifest.get('dataset_id'),
            'INVALID_FAMILY_MAP_RECEIPT')
    outputs = receipt.get('outputs')
    require(isinstance(outputs, dict), 'MISSING_FAMILY_MAP_OUTPUT_HASHES')
    for rel, expected in outputs.items():
        p = (bundle / rel).resolve()
        require(p.is_relative_to(bundle) and p.is_file() and sha(p) == expected,
                'FAMILY_MAP_OUTPUT_HASH_MISMATCH')
    expected_files = set(outputs) | {'acceptance.json'}
    actual_files = {p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}
    require(actual_files == expected_files, 'FAMILY_MAP_BUNDLE_INVENTORY_MISMATCH')
    with RevisionCatalog(bundle / 'store', read_only=True) as catalog:
        row = manifest['org_artifact']
        org = catalog.snapshot(row['revision'])
        require(org['source_sha256'] == row['source_sha256'], 'ORG_ARTIFACT_BINDING_MISMATCH')
        expected_map = manifest['derived_map']
        require(expected_map['revision'] in {r['revision'] for r in catalog.db.execute('SELECT revision FROM revisions')},
                'DERIVED_MAP_REVISION_MISSING')
        result = verify_family_map(catalog, org_revision=row['revision'], map_revision=expected_map['revision'])
        for key in ('source_sha256', 'input_snapshot_id', 'content_sha256', 'record_count', 'relation_count'):
            manifest_key = 'content_sha256' if key == 'content_sha256' else key
            require(result.get(key) == expected_map.get(manifest_key), 'DERIVED_MAP_MANIFEST_MISMATCH: ' + key)
        all_manifests = [catalog.snapshot(r['revision']) for r in catalog.db.execute('SELECT revision FROM revisions')]
        expected_payloads = set()
        for rev in all_manifests:
            expected_payloads.add(rev['source_sha256'])
            expected_payloads.update(obj['geometry_sha256'] for obj in rev['objects'] if obj.get('geometry_sha256'))
        actual_payloads = {p.name for p in catalog.payloads.iterdir() if p.is_file()}
        require(actual_payloads == expected_payloads, 'FAMILY_MAP_CAS_INVENTORY_MISMATCH')
    return {'status': 'PASS', 'dataset_id': manifest['dataset_id'],
            'org_revision': manifest['org_artifact']['revision'],
            'map_revision': manifest['derived_map']['revision'],
            'content_sha256': manifest['derived_map']['content_sha256'],
            'record_count': manifest['derived_map']['record_count'],
            'reader_pid': os.getpid()}


def publish(root, *, base_store, org_revision, output_root, dataset_id,
            input_spec, entities, relations, coverage, fail_before_publish=False,
            fail_after_run_rename=False):
    """Stage an ORG-only catalog copy, validate it in a child, then publish."""
    root = Path(root).resolve()
    base_store = Path(base_store).resolve()
    output_root = Path(output_root).resolve()
    require(base_store.is_relative_to(root / 'out'), 'BASE_CATALOG_OUTSIDE_CHECKOUT')
    require(output_root.is_relative_to(root / 'out'), 'FAMILY_MAP_OUTPUT_OUTSIDE_CHECKOUT')
    input_id, normalized_input = input_snapshot_id(dataset_id=dataset_id, **input_spec)
    output_root.mkdir(parents=True, exist_ok=True)
    stage = output_root / ('.staging-' + uuid.uuid4().hex)
    (stage / 'store').mkdir(parents=True)
    try:
        with RevisionCatalog(stage / 'store') as catalog:
            org = clone_revision(base_store, catalog, org_revision)
            require(org['source_sha256'] == input_spec['org_source_sha256'], 'INPUT_ORG_HASH_MISMATCH')
            family = store_family_map(catalog, dataset_id=dataset_id, org_revision=org_revision,
                                      input_id=input_id, input_spec=normalized_input,
                                      entities=entities, relations=relations, coverage=coverage)
        manifest = {'schema': BUNDLE_SCHEMA, 'dataset_id': dataset_id,
                    'org_artifact': {'revision': org_revision, 'source_sha256': org['source_sha256']},
                    'derived_map': family, 'input_spec': normalized_input,
                    'coverage': coverage, 'qualification': 'NOT_RUN',
                    'engineering_acceptance': 'NOT_ESTABLISHED'}
        (stage / 'materialization.json').write_text(json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n')
        receipt = {'schema': RECEIPT_SCHEMA, 'status': 'PASS', 'dataset_id': dataset_id,
                   'writer_pid': os.getpid(), 'outputs': _bundle_hashes(stage)}
        (stage / 'acceptance.json').write_text(json.dumps(receipt, sort_keys=True, separators=(',', ':')) + '\n')
        command = [sys.executable, str(root / 'tools/family_map.py'), 'verify', '--bundle', str(stage)]
        run = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False,
                             env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        require(run.returncode == 0, 'FRESH_FAMILY_MAP_REOPEN_FAILED: ' + (run.stderr or run.stdout)[-1200:])
        reopened = json.loads(run.stdout)
        require(reopened.get('status') == 'PASS' and reopened.get('reader_pid') != os.getpid(),
                'FRESH_FAMILY_MAP_READER_NOT_ESTABLISHED')
        receipt['reader_pid'] = reopened['reader_pid']
        receipt['reopen_result_sha256'] = digest(canonical(reopened))
        (stage / 'acceptance.json').write_text(json.dumps(receipt, sort_keys=True, separators=(',', ':')) + '\n')
        if fail_before_publish:
            raise CatalogError('INJECTED_FAMILY_MAP_PUBLICATION_FAILURE')
        verify_bundle(root, stage)
        run_id = 'run-' + uuid.uuid4().hex
        target = output_root / run_id
        stage.rename(target)
        if fail_after_run_rename:
            raise CatalogError('INJECTED_FAILURE_AFTER_RUN_RENAME')
        pointer = output_root / ('.current-' + uuid.uuid4().hex)
        pointer.write_text(json.dumps({'run': run_id}, sort_keys=True, separators=(',', ':')) + '\n')
        os.replace(pointer, output_root / 'current.json')
        return target, receipt
    finally:
        if stage.exists():
            shutil.rmtree(stage)
