"""Restricted ORG-only candidate-member and repeat-pattern recognition.

This module consumes one immutable ORG catalogue revision. It deliberately has
no EDIT, Gerber, or workspace-discovery input. Results are geometric hypotheses,
not pads, nets, manufacturing interpretations, or edit instructions.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import math
from pathlib import Path
import sexpdata
from shapely import from_wkb

from .native_reference import children, one
from .revision_catalog import CatalogError, canonical, digest
from .spatial_context import SpatialContext

RECOGNIZER_VERSION = 'org-family-recognition/1'
SEED_KINDS = {'gr_circle', 'gr_poly'}
TRACE_KINDS = {'segment', 'arc'}
REFERENCE_LAYERS = ('F.Mask', 'F.Paste')
FILL_TOKENS = {'yes', 'solid'}
COORDINATE_MM_DIGITS = 5
ARRANGEMENT_VECTOR_TOLERANCE_MM = 0.005
ARRANGEMENT_LOCALITY_MM = 1.0
GEOMETRY_ERROR_MM = 0.00001
CONTACT_UNCERTAINTY_MM = 2 * GEOMETRY_ERROR_MM
CENTER_QUANTIZATION_MM = 0.00001


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('NONFINITE_COORDINATE')
    return result


def _center_key(center, quantum=CENTER_QUANTIZATION_MM):
    return tuple(int(math.floor(value / quantum + 0.5)) for value in center)


def _source_node(source_text, row, source_sha256):
    start, end = row['source_span']
    if not (0 <= start < end <= len(source_text)):
        raise CatalogError('INVALID_ORG_SOURCE_SPAN')
    expected = f'{source_sha256}:bytes:{start}:{end}'
    if row.get('id') != expected:
        raise CatalogError('ORG_SOURCE_IDENTITY_MISMATCH')
    node = sexpdata.loads(source_text[start:end])
    if not isinstance(node, list) or not node:
        raise CatalogError('ORG_SOURCE_NODE_INVALID')
    return node


def _supported_feature(row, node, geometry):
    """Return an exact supported seed/reference descriptor or a reason."""
    fill = str((one(node, 'fill', ['none']) or ['none'])[0])
    if fill not in FILL_TOKENS:
        return None, 'UNFILLED'
    if row['kind'] == 'gr_circle':
        center = one(node, 'center')
        end = one(node, 'end')
        if center is None or end is None or len(center) < 2 or len(end) < 2:
            return None, 'MALFORMED_CIRCLE'
        x, y = _float(center[0]), _float(center[1])
        radius = math.dist((x, y), (_float(end[0]), _float(end[1])))
        if not math.isfinite(radius) or radius <= 0:
            return None, 'NON_POSITIVE_RADIUS'
        signature = {'primitive': 'filled_circle',
                     'radius_mm': round(radius, COORDINATE_MM_DIGITS)}
        return {'center_mm': [x, y], 'shape_signature': signature}, None
    if row['kind'] != 'gr_poly':
        return None, 'UNSUPPORTED_PRIMITIVE'
    point_sets = children(node, 'pts')
    if len(point_sets) != 1:
        return None, 'MALFORMED_POLYGON_POINTS'
    vertices = []
    for item in children(point_sets[0], 'xy'):
        if len(item) < 3:
            return None, 'MALFORMED_POLYGON_VERTEX'
        vertices.append((_float(item[1]), _float(item[2])))
    if len(vertices) > 1 and vertices[0] == vertices[-1]:
        vertices.pop()
    distinct = set(vertices)
    if len(distinct) != 4:
        return None, 'NOT_FOUR_DISTINCT_RECTANGLE_VERTICES'
    xs = [point[0] for point in distinct]
    ys = [point[1] for point in distinct]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if x1 <= x0 or y1 <= y0:
        return None, 'DEGENERATE_RECTANGLE'
    corners = {(x0, y0), (x1, y0), (x1, y1), (x0, y1)}
    if distinct != corners:
        return None, 'NON_AXIS_ALIGNED_RECTANGLE'
    if geometry.is_empty or not geometry.is_valid:
        return None, 'INVALID_RECTANGLE_GEOMETRY'
    bbox_area = (x1 - x0) * (y1 - y0)
    if abs(geometry.area - bbox_area) > max(1e-12, bbox_area * 1e-10):
        return None, 'RECTANGLE_AREA_MISMATCH'
    width, height = sorted((x1 - x0, y1 - y0))
    return {
        'center_mm': [(x0 + x1) / 2, (y0 + y1) / 2],
        'shape_signature': {'primitive': 'filled_axis_aligned_rectangle',
                            'dimensions_mm': [round(width, COORDINATE_MM_DIGITS),
                                              round(height, COORDINATE_MM_DIGITS)]},
    }, None


def _fallback_reference_center(row, node, geometry):
    """Locate unsupported layer features without treating them as matches."""
    if row['kind'] == 'gr_circle':
        center = one(node, 'center')
        if center is not None and len(center) >= 2:
            return [_float(center[0]), _float(center[1])]
    if row['kind'] == 'gr_poly' and not geometry.is_empty:
        centroid = geometry.centroid
        if not centroid.is_empty and math.isfinite(centroid.x) and math.isfinite(centroid.y):
            return [float(centroid.x), float(centroid.y)]
    return None


def _signature_key(signature):
    return canonical(signature).decode('utf-8')


def _member_key(org_revision, object_id):
    return digest(canonical([RECOGNIZER_VERSION, org_revision, object_id,
                             'local_land_candidate_seed']))


def _positive_contact(seed_shape, trace_shape):
    intersection = seed_shape.intersection(trace_shape)
    if intersection.is_empty:
        return False, 0.0
    # A nominal overlap that survives conservative erosion by each operand's
    # curve approximation bound is separated from a boundary-only/tiny contact.
    seed_inner = seed_shape.buffer(-GEOMETRY_ERROR_MM)
    trace_inner = trace_shape.buffer(-GEOMETRY_ERROR_MM)
    stable = (not seed_inner.is_empty and not trace_inner.is_empty
              and seed_inner.intersects(trace_inner))
    return stable, float(intersection.area)


def _component_membership(context):
    fcu_sources = [row for row in context.objects.values()
                   if 'F.Cu' in row.get('layers', [])]
    unavailable = [row['id'] for row in fcu_sources
                   if not row.get('geometry_sha256') or row['id'] not in context.shapes]
    if unavailable:
        return {}, {'status': 'INCOMPLETE', 'fcu_source_objects': len(fcu_sources),
                    'fcu_geometry_objects': len(context.layers.get('F.Cu', [])),
                    'unavailable_ids': sorted(unavailable)}, []
    if len(context.layers.get('F.Cu', [])) != len(fcu_sources):
        raise CatalogError('F_CU_TOPOLOGY_SOURCE_COVERAGE_MISMATCH')
    topology = context.topology()
    fcu_components = [component for component in topology['components']
                      if component['layer'] == 'F.Cu']
    member_to_group = {object_id: component['id'] for component in fcu_components
                       for object_id in component['members']}
    if set(member_to_group) != set(context.layers.get('F.Cu', [])):
        raise CatalogError('F_CU_TOPOLOGY_COMPONENT_CLOSURE_MISMATCH')
    return member_to_group, {
        'status': 'COMPLETE', 'layer': 'F.Cu',
        'source_objects': len(fcu_sources),
        'geometry_objects': len(context.layers.get('F.Cu', [])),
        'physical_contact_components': len(fcu_components),
        'physical_contact_relations': len(topology['relations']),
        'predicate': 'same-layer GEOS intersects over stored geometry',
        'snapshot': topology['snapshot'],
        'scope': 'nominal stored geometry; topology is separate from candidate members and families',
    }, fcu_components


def _family_hypotheses(members):
    """Build local, shape- and trace-context-bounded repeated-vector hypotheses."""
    groups = defaultdict(list)
    for member in members:
        sig = member['geometry']['shape_signature']
        trace_count = len(member['trace_associations']['nominal_contacts'])
        groups[(_signature_key(sig), trace_count)].append(member)
    families = {}
    tol = ARRANGEMENT_VECTOR_TOLERANCE_MM
    radius = ARRANGEMENT_LOCALITY_MM
    for (signature_key, trace_count), rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda member: member['member_key'])
        points = [member['geometry']['center_mm'] for member in rows]
        adjacency = [set() for _ in rows]
        for i, (x, y) in enumerate(points):
            for j in range(i + 1, len(points)):
                a, b = points[j]
                if math.hypot(a - x, b - y) <= radius:
                    adjacency[i].add(j)
                    adjacency[j].add(i)
        unseen = set(range(len(rows)))
        while unseen:
            start = min(unseen)
            pending = [start]
            component = set()
            while pending:
                i = pending.pop()
                if i in component:
                    continue
                component.add(i)
                pending.extend(adjacency[i] - component)
            unseen.difference_update(component)
            if len(component) < 3:
                continue
            indices = sorted(component)
            vector_pairs = defaultdict(list)
            for offset, i in enumerate(indices):
                x, y = points[i]
                for j in indices[offset + 1:]:
                    a, b = points[j]
                    dx, dy = a - x, b - y
                    if dx < 0 or (dx == 0 and dy < 0):
                        dx, dy = -dx, -dy
                    if math.hypot(dx, dy) < tol / 2:
                        continue
                    # Same fixed-width tolerance bucket is a conservative,
                    # deterministic equivalence predicate (it never bridges bins).
                    vector_bin = (int(math.floor(dx / tol + 0.5)),
                                  int(math.floor(dy / tol + 0.5)))
                    vector_pairs[vector_bin].append((i, j, dx, dy))
            for vector_bin, pairs in sorted(vector_pairs.items()):
                unique_pairs = {(min(i, j), max(i, j)): (dx, dy)
                                for i, j, dx, dy in pairs}
                if len(unique_pairs) < 2:
                    continue
                edge_indexes = {index for pair in unique_pairs for index in pair}
                member_keys = sorted(rows[i]['member_key'] for i in edge_indexes)
                support = []
                for (i, j), (dx, dy) in sorted(unique_pairs.items()):
                    support.append({
                        'member_keys': sorted([rows[i]['member_key'], rows[j]['member_key']]),
                        'center_delta_mm': [round(dx, 8), round(dy, 8)],
                    })
                if len(member_keys) < 3 or len(support) < 2:
                    continue
                family_key = digest(canonical([
                    RECOGNIZER_VERSION, signature_key, trace_count,
                    vector_bin, member_keys,
                ]))
                families[family_key] = {
                    'entity_type': 'family',
                    'family_key': family_key,
                    'status': 'PROVISIONAL_PATTERN_HYPOTHESIS',
                    'family_rule': 'same shape signature + same nominal trace-contact count + '
                                   'local repeated center-displacement bucket',
                    'shape_signature': rows[0]['geometry']['shape_signature'],
                    'nominal_trace_contact_count': trace_count,
                    'locality_radius_mm': radius,
                    'vector_tolerance_mm': tol,
                    'vector_bucket': list(vector_bin),
                    'canonical_displacement_mm': [round(vector_bin[0] * tol, 8),
                                                  round(vector_bin[1] * tol, 8)],
                    'members': member_keys,
                    'support_pairs': support,
                    'source_refs': [],
                }
    return [families[key] for key in sorted(families)]


def recognize_org_records(*, org_revision, source_sha256, source_bytes,
                          objects, geometry_payloads):
    """Recognize restricted candidate members and repeat patterns from ORG only."""
    if hashlib.sha256(source_bytes).hexdigest() != source_sha256:
        raise CatalogError('ORG_SOURCE_BYTES_HASH_MISMATCH')
    text = source_bytes.decode('utf-8')
    rows = sorted(objects, key=lambda row: row['id'])
    row_by_id = {row['id']: row for row in rows}
    shapes = {key: from_wkb(payload) for key, payload in geometry_payloads.items()}
    context = SpatialContext(org_revision, rows, geometry_payloads)

    seed_exclusion_counts = defaultdict(int)
    reference_exclusion_counts = {layer: defaultdict(int) for layer in REFERENCE_LAYERS}
    reference_features = {layer: defaultdict(list) for layer in REFERENCE_LAYERS}
    unsupported_reference_features = {layer: defaultdict(list) for layer in REFERENCE_LAYERS}
    seeds = []
    for row in rows:
        relevant_layer = 'F.Cu' in row.get('layers', []) or any(
            layer in row.get('layers', []) for layer in REFERENCE_LAYERS)
        if not relevant_layer or row['kind'] not in SEED_KINDS:
            continue
        if not row.get('geometry_sha256') or row['geometry_sha256'] not in shapes:
            if 'F.Cu' in row.get('layers', []):
                seed_exclusion_counts['GEOMETRY_UNAVAILABLE'] += 1
            for layer in REFERENCE_LAYERS:
                if layer in row.get('layers', []):
                    reference_exclusion_counts[layer]['GEOMETRY_UNAVAILABLE'] += 1
            continue
        node = _source_node(text, row, source_sha256)
        geometry = shapes[row['geometry_sha256']]
        feature, reason = _supported_feature(row, node, geometry)
        if reason:
            if 'F.Cu' in row.get('layers', []):
                seed_exclusion_counts[reason] += 1
            for layer in REFERENCE_LAYERS:
                if layer in row.get('layers', []):
                    reference_exclusion_counts[layer][reason] += 1
                    fallback = _fallback_reference_center(row, node, geometry)
                    if fallback is not None:
                        unsupported_reference_features[layer][_center_key(fallback)].append({
                            'row': row, 'reason': reason,
                        })
            continue
        if 'F.Cu' in row.get('layers', []):
            seeds.append((row, feature, geometry))
        for layer in REFERENCE_LAYERS:
            if layer in row.get('layers', []):
                reference_features[layer][_center_key(feature['center_mm'])].append(row)

    member_to_physical_group, physical_topology, physical_components = _component_membership(context)
    members = []
    contact_totals = defaultdict(int)
    for row, feature, geometry in seeds:
        object_id = row['id']
        member_key = _member_key(org_revision, object_id)
        nominal_contacts = []
        uncertain_contacts = []
        for hit in context.query(object_id, 'F.Cu')['matches']:
            trace = row_by_id[hit['id']]
            if trace['kind'] not in TRACE_KINDS:
                continue
            stable, area = _positive_contact(geometry, shapes[trace['geometry_sha256']])
            status = 'NOMINAL_CONTACT' if stable else 'CONTACT_STATUS_UNCERTAIN'
            association = {
                'source_revision': org_revision, 'object_id': trace['id'],
                'role': 'incident_trace', 'predicate': 'GEOS intersects (zero contact)',
                'distance_mm': 0.0, 'intersection_area_mm2': round(area, 12),
                'status': status,
            }
            (nominal_contacts if stable else uncertain_contacts).append(association)
        for hit in context.query(object_id, 'F.Cu', distance_mm=CONTACT_UNCERTAINTY_MM)['matches']:
            trace = row_by_id[hit['id']]
            if trace['kind'] not in TRACE_KINDS or hit['distance_mm'] == 0:
                continue
            uncertain_contacts.append({
                'source_revision': org_revision, 'object_id': trace['id'],
                'role': 'uncertain_trace_contact',
                'predicate': f'GEOS distance <= {CONTACT_UNCERTAINTY_MM:.8f} mm',
                'distance_mm': round(hit['distance_mm'], 12),
                'status': 'CONTACT_STATUS_UNCERTAIN',
            })
        nominal_contacts.sort(key=lambda item: item['object_id'])
        uncertain_contacts.sort(key=lambda item: (item['object_id'], item['distance_mm']))
        contact_totals['nominal_trace_contacts'] += len(nominal_contacts)
        contact_totals['uncertain_trace_associations'] += len(uncertain_contacts)

        refs_by_layer = {}
        source_refs = [{'source_revision': org_revision, 'object_id': object_id,
                        'role': 'local_land_candidate_seed'}]
        for association in nominal_contacts + uncertain_contacts:
            source_refs.append({key: association[key] for key in
                                ('source_revision', 'object_id', 'role')})
        center_key = _center_key(feature['center_mm'])
        for layer in REFERENCE_LAYERS:
            candidates = sorted(reference_features[layer].get(center_key, []),
                                key=lambda candidate: candidate['id'])
            unsupported = sorted(unsupported_reference_features[layer].get(center_key, []),
                                 key=lambda entry: entry['row']['id'])
            if len(candidates) == 1 and not unsupported:
                status = 'UNIQUE_GEOMETRIC_CANDIDATE'
            elif candidates and (len(candidates) > 1 or unsupported):
                status = 'AMBIGUOUS'
            elif unsupported:
                status = 'UNSUPPORTED'
            else:
                status = 'UNMATCHED'
            refs_by_layer[layer] = {
                'status': status,
                'predicate': f'same center after {CENTER_QUANTIZATION_MM:.8f} mm quantization',
                'center_quantization_mm': CENTER_QUANTIZATION_MM,
                'candidates': [{'source_revision': org_revision,
                                'object_id': candidate['id'],
                                'role': f'{layer}_geometric_feature_candidate'}
                               for candidate in candidates],
                'unsupported_candidates': [
                    {'source_revision': org_revision,
                     'object_id': entry['row']['id'],
                     'role': f'{layer}_unsupported_feature_candidate',
                     'reason': entry['reason']}
                    for entry in unsupported],
            }
            source_refs.extend(refs_by_layer[layer]['candidates'])
            source_refs.extend(refs_by_layer[layer]['unsupported_candidates'])
        source_refs.sort(key=lambda ref: (ref['object_id'], ref['role']))
        source_refs = [dict(item) for item in {
            (ref['source_revision'], ref['object_id'], ref['role']): ref
            for ref in source_refs
        }.values()]
        members.append({
            'entity_type': 'candidate_member', 'member_key': member_key,
            'status': 'RESTRICTED_SEED_HYPOTHESIS',
            'source_refs': source_refs,
            'geometry': {
                'basis': 'single source primitive; no geometric union or trace merge',
                'units': 'mm', 'coordinate_frame': 'KiCad board coordinates; Y down',
                'source_kind': row['kind'], 'shape_signature': feature['shape_signature'],
                'center_mm': [round(value, COORDINATE_MM_DIGITS)
                              for value in feature['center_mm']],
                'bounds_mm': row.get('bounds_mm'),
                'geometry_sha256': row['geometry_sha256'],
                'geometry_error_mm': GEOMETRY_ERROR_MM,
            },
            'physical_group_key': member_to_physical_group.get(object_id),
            'trace_associations': {
                'predicate': 'same-layer F.Cu geometry intersection; uncertain near-contact retained separately',
                'nominal_contacts': nominal_contacts,
                'uncertain_associations': uncertain_contacts,
            },
            'reference_features': refs_by_layer,
            'candidate_family_keys': [],
            'family_membership_status': 'NO_FAMILY_HYPOTHESIS',
        })
    members.sort(key=lambda member: member['member_key'])
    families = _family_hypotheses(members)
    member_by_key = {member['member_key']: member for member in members}
    for family in families:
        for key in family['members']:
            member_by_key[key]['candidate_family_keys'].append(family['family_key'])
    for member in members:
        member['candidate_family_keys'].sort()
        count = len(member['candidate_family_keys'])
        member['family_membership_status'] = ('NO_FAMILY_HYPOTHESIS' if count == 0 else
                                              'ONE_PROVISIONAL_FAMILY_HYPOTHESIS' if count == 1 else
                                              'AMBIGUOUS_MULTIPLE_FAMILY_HYPOTHESES')

    physical_groups = [{
        'entity_type': 'physical_group',
        'physical_group_key': component['id'],
        'layer': component['layer'],
        'predicate': 'same-layer GEOS intersects over stored geometry',
        'topology_snapshot': context.snapshot,
        'source_members': component['members'],
        'source_refs': [
            {'source_revision': org_revision, 'object_id': object_id,
             'role': 'physical_group_member'}
            for object_id in component['members']
        ],
    } for component in physical_components]
    entities = members + families + physical_groups
    member_index = {member['member_key']: index for index, member in enumerate(members)}
    family_base = len(members)
    group_base = family_base + len(families)
    group_index = {group['physical_group_key']: group_base + index
                   for index, group in enumerate(physical_groups)}
    relations = []
    for family_offset, family in enumerate(families):
        family_index = family_base + family_offset
        for member_key in family['members']:
            relations.append({'source_index': family_index,
                              'target_index': member_index[member_key],
                              'type': 'family_member',
                              'witness': {'family_key': family['family_key'],
                                          'support_pair_count': len(family['support_pairs'])}})
    for member_offset, member in enumerate(members):
        group_key = member.get('physical_group_key')
        if group_key is not None:
            relations.append({'source_index': member_offset,
                              'target_index': group_index[group_key],
                              'type': 'member_physical_group',
                              'witness': {'layer': 'F.Cu',
                                          'predicate': physical_topology['predicate'],
                                          'topology_snapshot': physical_topology['snapshot']}})

    associations = defaultdict(int)
    reference_candidate_counts = defaultdict(int)
    for member in members:
        for layer in REFERENCE_LAYERS:
            associations[f"{layer}:{member['reference_features'][layer]['status']}"] += 1
            reference_candidate_counts[f"{layer}:supported"] += len(
                member['reference_features'][layer]['candidates'])
            reference_candidate_counts[f"{layer}:unsupported"] += len(
                member['reference_features'][layer]['unsupported_candidates'])
    coverage = {
        'scope': 'pinned ORG revision only; restricted single-primitive hypotheses',
        'source_object_count': len(rows),
        'candidate_seed_count': len(seeds),
        'candidate_members': len(members),
        'seed_exclusions': dict(sorted(seed_exclusion_counts.items())),
        'reference_feature_exclusions': {
            layer: dict(sorted(counts.items()))
            for layer, counts in sorted(reference_exclusion_counts.items()) if counts
        },
        'trace_associations': dict(sorted(contact_totals.items())),
        'reference_association_statuses': dict(sorted(associations.items())),
        'reference_candidate_counts': dict(sorted(reference_candidate_counts.items())),
        'physical_topology': physical_topology,
        'physical_group_records': len(physical_components),
        'family_hypotheses': len(families),
        'physical_group_records': len(physical_groups),
        'members_in_multiple_family_hypotheses': sum(
            member['family_membership_status'] == 'AMBIGUOUS_MULTIPLE_FAMILY_HYPOTHESES'
            for member in members),
        'arrangement_config': {
            'shape_signature_coordinate_precision_mm': 10 ** -COORDINATE_MM_DIGITS,
            'center_quantization_mm': CENTER_QUANTIZATION_MM,
            'vector_tolerance_mm': ARRANGEMENT_VECTOR_TOLERANCE_MM,
            'locality_radius_mm': ARRANGEMENT_LOCALITY_MM,
            'same_nominal_trace_contact_count_required': True,
            'minimum_distinct_members': 3,
            'minimum_distinct_pair_witnesses': 2,
            'bucket_semantics': 'fixed-width bins; conservative and deterministic; no cross-bin bridging',
        },
        'status': 'DESCRIPTIVE_HYPOTHESES_ONLY',
        'engineering_acceptance': 'NOT_ESTABLISHED',
        'manufacturing_acceptance': 'NOT_ESTABLISHED',
    }
    return {'entities': entities, 'relations': relations, 'coverage': coverage,
            'org_revision': org_revision, 'source_sha256': source_sha256,
            'spatial_snapshot': context.snapshot,
            'recognizer_version': RECOGNIZER_VERSION}


def recognize_catalogue(catalog, org_revision, *, geometry_materialization_sha256):
    """Load only the pinned ORG catalogue revision and return publication inputs."""
    manifest = catalog.snapshot(org_revision)
    if manifest['config'].get('kind') != 'org-native-geometry-materialization/1':
        raise CatalogError('NOT_AN_ORG_GEOMETRY_REVISION')
    if manifest['config'].get('coverage') is None:
        raise CatalogError('ORG_GEOMETRY_POLICY_MISSING')
    source_bytes = catalog.read_payload(manifest['source_sha256'])
    payloads = {key: catalog.read_payload(key) for key in sorted({
        row['geometry_sha256'] for row in manifest['objects'] if row.get('geometry_sha256')
    })}
    result = recognize_org_records(org_revision=org_revision,
                                   source_sha256=manifest['source_sha256'],
                                   source_bytes=source_bytes,
                                   objects=manifest['objects'],
                                   geometry_payloads=payloads)
    result['input_spec'] = {
        'org_revision': org_revision,
        'org_source_sha256': manifest['source_sha256'],
        'geometry_materialization_sha256': geometry_materialization_sha256,
        'parser_version': manifest['config']['extractor'],
        'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'config': result['coverage']['arrangement_config'] | {
            'seed_rule': 'filled F.Cu circle or valid axis-aligned filled F.Cu rectangle',
            'reference_rule': 'same-center supported filled F.Mask/F.Paste circle or rectangle; purpose-neutral',
            'contact_rule': 'GEOS intersection, with GEOS distance <= two geometry-error bounds retained as uncertain',
            'recognizer_version': RECOGNIZER_VERSION,
        },
        'predicate_versions': {
            'spatial_context': SpatialContext.VERSION,
            'contact': 'GEOS intersects / erosion by native geometry error /1',
            'reference_center': f'quantized-center/{CENTER_QUANTIZATION_MM:.8f}mm/1',
            'arrangement': 'shape+trace-degree+local repeated vector buckets/1',
        },
    }
    return result
