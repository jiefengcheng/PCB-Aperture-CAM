"""Stage a source-bound replay bundle, verify it, then publish its local entry.

Registration does not extract a common object catalogue or run a CAM operation.
Previous publications remain immutable. Rename is not a power-loss guarantee.
"""
import base64
import copy
import gzip
import hashlib
import importlib.metadata
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

from .ingestion_contracts import (
    PUBLICATION_SCHEMA, digest_registry, generation_review, intake_projection, validate_registry,
)
from .ingestion_files import local, sha, verify, write_json
from .ingestion_verification import verify_publication
from .ingestion_visuals import comparison_views

# Keep every producer/render dependency in the captured implementation snapshot.
APP_SOURCES = (
    'web/replay_model.js', 'web/backend_model.js', 'web/org_family_review.js', 'web/pipeline_views.js',
    'web/directory_intake.js', 'web/ingestion_views.js', 'web/catalogue_themes.js', 'web/catalogue_views.js', 'web/workbench.js',
)
IMPLEMENTATION_SOURCES = (
    'src/ingestion_files.py', 'src/ingestion_contracts.py',
    'src/ingestion_registry.py', 'src/ingestion_verification.py',
    'src/dataset_profiler.py',
    'src/profile_materialization.py', 'tools/materialize_profile.py',
    'tools/build_identity_review.py', 'tools/build_copper_group_review.py',
    'src/ingestion_visuals.py', 'src/client_gerber.py', 'src/gerber_image.py',
    'src/visual_scene.py', 'tools/visual_report.py', 'tools/ingestion.py',
    'web/workbench.html', *APP_SOURCES,
    'src/directory_intake.py', 'tools/ingestion_server.py',
    'src/catalogue_scene.py', 'src/common_catalogue.py','src/revision_catalog.py',
    'src/catalog_selection.py','src/spatial_context.py',
    'src/catalogue_qualifications.py',
    'src/catalogue_selection.py',
    'src/org_family_review.py',
    'tools/build_g22_slice_d.py', 'tools/run_g22_slice_c.py', 'tools/run_g22_reconstruction.py', 'src/visual_scene.py',
)
REPLAY_ENTRY_FILES = {'index.html', 'scene.json', 'build_receipt.json'}


def _publication_directory(root, destination):
    destination = Path(destination).resolve()
    if not destination.is_relative_to(root / 'out'):
        raise ValueError('Publication must stay under checkout/out')
    immutable_markers = {'receipt.json', 'build_receipt.json', 'scene.json', 'registry.json'}
    if any((destination / name).exists() for name in immutable_markers):
        raise ValueError('Publication destination is an immutable bundle; choose an entry directory')
    return destination


def _input_bindings(config):
    bindings = [config['dataset_seal'], *config['replay_bindings']]
    if config.get('directory_intake'):
        bindings.append(config['directory_intake']['profile'])
    if config.get('common_context'):
        bindings.append(config['common_context'])
    for bundle in config.get('record_materializations', {}).values():
        bindings.extend(bundle.get('files', []))
    for family_map in config.get('org_family_maps', {}).values():
        prefix = family_map['bundle_path'].rstrip('/')
        bindings.extend([
            {'path': prefix + '/materialization.json', 'sha256': family_map['materialization_sha256']},
            {'path': prefix + '/acceptance.json', 'sha256': family_map['acceptance_sha256']},
        ])
    if config.get('g22_reconstruction'):
        bindings.append(config['g22_reconstruction']['payload'])
        for key in ('slice_c_receipt', 'slice_b_report', 'experiment_contract', 'slice_d_build_receipt'):
            if config['g22_reconstruction'].get(key):
                bindings.append(config['g22_reconstruction'][key])
        if config['g22_reconstruction'].get('chatgpt_audit_receipt'):
            bindings.append(config['g22_reconstruction']['chatgpt_audit_receipt'])
    for review in config.get('identity_reviews', {}).values():
        bindings.append(review['manifest'])
        bindings.extend(review.get('images', []))
        if review.get('groups_manifest'):
            bindings.append(review['groups_manifest'])
            bindings.extend(review.get('group_images', []))
        bindings.extend(review.get('screenshot_evidence', []))
        if review.get('context'):
            bindings.append(review['context'])
    for dataset in config['datasets']:
        bindings.extend(dataset['sources'] + dataset['evidence'])
    return bindings


def _copy_replay(root, config, stage):
    """Copy only declared replay files, retaining its original envelope separately."""
    replay = local(root, config['replay_bundle'])
    retained = stage / 'historical_replay'
    bindings = []
    for binding in config['replay_bindings']:
        source = local(root, binding['path'])
        relative = source.relative_to(replay)
        target = retained / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        bindings.append({'path': str(relative), 'sha256': binding['sha256']})
        if str(relative) not in REPLAY_ENTRY_FILES:
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    verify(retained, bindings)
    return json.loads((retained / 'scene.json').read_text())


def _add_ingestion(root, config, scene):
    ingestion = {
        'schema': config['schema'],
        'registry_sha256': digest_registry(config),
        'datasets': copy.deepcopy(config['datasets']),
        'mode': 'REPLAY',
        'common_object_catalogue': 'DEFERRED',
        'cursor_review': generation_review(),
    }
    render_inputs = []
    for dataset in ingestion['datasets']:
        dataset['qualification_data'] = comparison_views(root, dataset)
        for view in dataset['qualification_data']['comparisons']:
            render_inputs.append({
                'dataset_id': dataset['id'],
                **{key: view[key] for key in ('label', 'roi_mm', 'receipt_role', 'inputs')},
            })
    scene['ingestion'] = ingestion
    ingestion['identity_reviews'] = {}
    for dataset_id, review in config.get('identity_reviews', {}).items():
        ingestion['identity_reviews'][dataset_id] = {
            'manifest': dict(review['manifest']),
            'summary': copy.deepcopy(review.get('summary', {})),
        }
        if review.get('groups_manifest'):
            ingestion['identity_reviews'][dataset_id]['groups_manifest'] = dict(review['groups_manifest'])
            ingestion['identity_reviews'][dataset_id]['group_summary'] = copy.deepcopy(review.get('group_summary', {}))
        if review.get('screenshot_evidence'):
            ingestion['identity_reviews'][dataset_id]['screenshot_evidence'] = copy.deepcopy(review['screenshot_evidence'])
        if review.get('context'):
            ingestion['identity_reviews'][dataset_id]['context'] = dict(review['context'])
    return render_inputs


def _copy_evidence(root, scene, stage):
    for dataset in scene['ingestion']['datasets']:
        for binding in dataset['evidence']:
            source = local(root, binding['path'])
            target = stage / 'ingestion_evidence' / binding['sha256'] / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            verify(stage, [{'path': str(target.relative_to(stage)), 'sha256': binding['sha256']}])
            binding['snapshot'] = str(target.relative_to(stage))


def _copy_identity_reviews(root, config, scene, stage):
    """Stage read-only, source-bound identity-review manifests and images."""
    linked = scene['ingestion'].get('identity_reviews', {})
    for dataset_id, review in config.get('identity_reviews', {}).items():
        prefix = 'identity_reviews/' + hashlib.sha256(dataset_id.encode()).hexdigest()[:16]
        bindings = [review['manifest'], *review.get('images', [])]
        for binding in bindings:
            source = local(root, binding['path'])
            if sha(source) != binding['sha256']:
                raise ValueError('Identity review artifact hash mismatch: ' + binding['path'])
            role = 'manifest.json' if binding is review['manifest'] else 'images/' + source.name
            target = local(stage, prefix + '/' + role)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            verify(stage, [{'path': str(target.relative_to(stage)), 'sha256': binding['sha256']}])
        linked[dataset_id]['manifest']['snapshot'] = prefix + '/manifest.json'
        linked[dataset_id]['manifest']['sha256'] = review['manifest']['sha256']
        linked[dataset_id]['image_count'] = len(review.get('images', []))
        linked[dataset_id]['images_root'] = prefix + '/images'
        if review.get('groups_manifest'):
            groups_bindings = [review['groups_manifest'], *review.get('group_images', [])]
            for binding in groups_bindings:
                source = local(root, binding['path'])
                if sha(source) != binding['sha256']:
                    raise ValueError('Copper group review artifact hash mismatch: ' + binding['path'])
                role = 'groups.json' if binding is review['groups_manifest'] else 'groups/' + source.name
                target = local(stage, prefix + '/' + role)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                verify(stage, [{'path': str(target.relative_to(stage)), 'sha256': binding['sha256']}])
            linked[dataset_id]['groups_manifest']['snapshot'] = prefix + '/groups.json'
            linked[dataset_id]['groups_manifest']['sha256'] = review['groups_manifest']['sha256']
            linked[dataset_id]['group_images_root'] = prefix + '/groups'
            linked[dataset_id]['group_image_count'] = len(review.get('group_images', []))
        if review.get('screenshot_evidence'):
            evidence_rows = []
            for binding in review['screenshot_evidence']:
                source = local(root, binding['path'])
                if sha(source) != binding['sha256']:
                    raise ValueError('Screenshot review artifact hash mismatch: ' + binding['path'])
                target = local(stage, prefix + '/screenshot_evidence/' + source.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                verify(stage, [{'path': str(target.relative_to(stage)), 'sha256': binding['sha256']}])
                evidence_rows.append({key: value for key, value in binding.items() if key not in ('path', 'sha256')} |
                                     {'snapshot': str(target.relative_to(stage)), 'sha256': binding['sha256']})
            linked[dataset_id]['screenshot_evidence'] = evidence_rows
        if review.get('context'):
            binding = review['context']
            source = local(root, binding['path'])
            if sha(source) != binding['sha256']:
                raise ValueError('Copper domain context artifact hash mismatch: ' + binding['path'])
            target = local(stage, prefix + '/DOMAIN_QUESTIONS.md')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            verify(stage, [{'path': str(target.relative_to(stage)), 'sha256': binding['sha256']}])
            linked[dataset_id]['context']['snapshot'] = prefix + '/DOMAIN_QUESTIONS.md'


def _copy_intake(root, config, scene, stage):
    intakes = {}
    candidates = [dataset for dataset in config['datasets']
                  if dataset.get('intake_status') == 'PROFILED_NOT_QUALIFIED'
                  and any(row['path'].endswith('/metadata/profile.json') for row in dataset['evidence'])]
    preferred = config.get('directory_intake', {}).get('dataset_id')
    primary_id = preferred if any(dataset['id'] == preferred for dataset in candidates) else (
        candidates[0]['id'] if candidates else None)
    for dataset in candidates:
        profile = next((row for row in dataset['evidence']
                        if row['path'].endswith('/metadata/profile.json')), None)
        if not profile or dataset.get('intake_status') != 'PROFILED_NOT_QUALIFIED':
            continue
        package = Path(profile['path']).parent.parent.as_posix()
        seal_path = package + '/SHA256SUMS'
        seal_binding = {'path': seal_path, 'sha256': sha(local(root, seal_path))}
        projected_config = dict(config)
        projected_config['dataset_seal'] = seal_binding
        intake = intake_projection(projected_config, lambda path: local(root, path).read_bytes())
        if intake is None or intake['dataset_id'] != dataset['id']:
            raise ValueError('Profile intake projection does not match registered dataset: ' + dataset['id'])
        prefix = 'intake' if dataset['id'] == primary_id else (
            'intake/profiles/' + hashlib.sha256(dataset['id'].encode()).hexdigest()[:16])
        for binding in intake['artifacts'].values():
            relative = binding['snapshot'].removeprefix('intake/')
            binding['snapshot'] = prefix + '/' + relative
        intakes[dataset['id']] = intake
        for binding in intake['artifacts'].values():
            target = local(stage, binding['snapshot'])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local(root, binding['path']), target)
            verify(stage, [{'path': binding['snapshot'], 'sha256': binding['sha256']}])
    if not intakes:
        legacy = intake_projection(config, lambda path: local(root, path).read_bytes())
        if legacy is not None:
            for binding in legacy['artifacts'].values():
                target = local(stage, binding['snapshot'])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(local(root, binding['path']), target)
                verify(stage, [{'path': binding['snapshot'], 'sha256': binding['sha256']}])
            scene['ingestion']['intake'] = legacy
            bindings = list(legacy['artifacts'].values())
        else:
            bindings = []
    else:
        bindings = [binding for intake in intakes.values() for binding in intake['artifacts'].values()]
    if intakes:
        scene['ingestion']['intakes'] = intakes
        scene['ingestion']['intake'] = intakes[primary_id]
    linked = {}
    for dataset_id, bundle in config.get('record_materializations', {}).items():
        from .profile_materialization import _read_materialization
        receipt, _, bundle_root = _read_materialization(root, local(root, bundle['path']))
        declared = {row['path']: row['sha256'] for row in bundle.get('files', [])}
        required = {'materialization.json', 'reopened.json', 'acceptance.json'}
        actual = {path: sha(local(root, bundle['path'] + '/' + path)) for path in required}
        expected = {bundle['path'] + '/' + path: digest for path, digest in actual.items()}
        if not receipt or receipt.get('status') != 'PASS' or declared != expected:
            raise ValueError('Profile materialization is not a complete accepted bundle: ' + dataset_id)
        materialization = json.loads(local(root, bundle['path'] + '/materialization.json').read_text())
        receipt = json.loads(local(root, bundle['path'] + '/acceptance.json').read_text())
        evidence = {}
        prefix = 'record_materializations/' + hashlib.sha256(dataset_id.encode()).hexdigest()[:16]
        for source_binding in bundle['files']:
            source = local(root, source_binding['path'])
            relative = source.relative_to(local(root, bundle['path']))
            snapshot = prefix + '/' + relative.as_posix()
            target = local(stage, snapshot)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            verify(stage, [{'path': snapshot, 'sha256': source_binding['sha256']}])
            evidence[relative.as_posix()] = {'path': source_binding['path'],
                                             'sha256': source_binding['sha256'],
                                             'snapshot': snapshot}
            bindings.append(source_binding)
        linked[dataset_id] = {'status': 'PASS' if receipt.get('status') == 'PASS' else 'FAIL',
                              'materialization': materialization, 'acceptance': receipt,
                              'evidence': evidence, 'snapshot_root': prefix,
                              'bundle_root': bundle['path']}
    scene['ingestion']['record_materializations'] = linked
    return bindings


def _copy_org_family_maps(root, config, scene, stage):
    """Bind verified ORG-only maps as read-only inspection projections."""
    from .org_family_review import build_review_projection, require_org_family_resource_budget

    linked = {}
    datasets = {row['id'] for row in config['datasets']}
    for dataset_id, binding in sorted(config.get('org_family_maps', {}).items()):
        if dataset_id not in datasets:
            raise ValueError('ORG family map dataset is not registered: ' + dataset_id)
        bundle = local(root, binding['bundle_path'])
        materialization_path = bundle / 'materialization.json'
        acceptance_path = bundle / 'acceptance.json'
        if sha(materialization_path) != binding['materialization_sha256'] or sha(acceptance_path) != binding['acceptance_sha256']:
            raise ValueError('ORG family map receipt binding mismatch: ' + dataset_id)
        materialization = json.loads(materialization_path.read_text())
        if materialization.get('dataset_id') != dataset_id:
            raise ValueError('ORG family map dataset identity mismatch: ' + dataset_id)
        projection = build_review_projection(root, bundle)
        if projection['binding']['dataset_id'] != dataset_id:
            raise ValueError('ORG family map projection identity mismatch: ' + dataset_id)
        stored_geometry_paths = projection.pop('stored_geometry_paths')
        prefix = 'org_family_maps/' + hashlib.sha256(dataset_id.encode()).hexdigest()[:16]
        stored_target = stage / prefix / 'stored-geometry.json'
        stored_target.parent.mkdir(parents=True, exist_ok=True)
        stored_encoded = (json.dumps(stored_geometry_paths, sort_keys=True,
                                      separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
        require_org_family_resource_budget('ORG stored-geometry publication', len(stored_encoded))
        stored_target.write_bytes(stored_encoded)
        projection['stored_geometry_paths_ref'] = {
            'snapshot': str(stored_target.relative_to(stage)),
            'sha256': sha(stored_target),
            'geometry_count': len(stored_geometry_paths),
        }
        projection_without_digest = dict(projection)
        projection_without_digest.pop('projection_sha256', None)
        projection['projection_sha256'] = hashlib.sha256(json.dumps(
            projection_without_digest, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        encoded = (json.dumps(projection, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
        require_org_family_resource_budget('ORG family review publication', len(encoded))
        target = stage / prefix / 'review.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded)
        digest = sha(target)
        linked[dataset_id] = {
            'bundle_path': binding['bundle_path'],
            'materialization_sha256': binding['materialization_sha256'],
            'acceptance_sha256': binding['acceptance_sha256'],
            'snapshot': str(target.relative_to(stage)),
            'projection_sha256': digest,
            'map_revision': projection['binding']['map_revision'],
            'map_content_sha256': projection['binding']['map_content_sha256'],
            'org_revision': projection['binding']['org_revision'],
            'org_source_sha256': projection['binding']['org_source_sha256'],
            'member_count': len(projection['members']),
            'family_count': len(projection['families']),
            'physical_group_count': len(projection['physical_groups']),
        }
    scene['ingestion']['org_family_maps'] = linked
    return []


def _validate_g22_reconstruction_payload(payload, slice_receipt, fit, dataset_id):
    if (payload.get('schema') != 'pcb-g22-family-reconstruction-visual-v1'
            or payload.get('dataset_id') != dataset_id
            or [row.get('member') for row in payload.get('members', [])] != [1, 2, 3]):
        raise ValueError('G22 reconstruction payload identity or member set mismatch')
    for member in payload['members']:
        number = member['member']
        key = str(number)
        transfer = next((row for row in fit.get('transfer', []) if row.get('member') == number), None)
        recorded = slice_receipt.get('windows', {}).get(key)
        candidate_case = slice_receipt.get('cases', {}).get(f'candidate_member_{number}', {})
        if not transfer or not recorded or not candidate_case:
            raise ValueError('G22 reconstruction member has no bound experiment receipt')
        exported = recorded.get('exported_copper_comparison', {})
        measurements = member.get('measurements', {})
        for field in ('candidate_vs_org', 'candidate_vs_edit', 'unchanged_org_vs_edit', 'local_neighbor_interaction'):
            if measurements.get(field) != exported.get(field):
                raise ValueError(f'G22 reconstruction measurement differs from Slice C receipt: {number}:{field}')
        if (measurements.get('native_to_gerber_fidelity') != recorded.get('native_export_fidelity')
                or measurements.get('reference_layer_preservation_vs_org') != candidate_case.get('reference_layer_preservation_vs_org')
                or measurements.get('edit_target_qualification') != transfer.get('target_composition_status')
                or measurements.get('whole_target_fit') != transfer.get('whole_target_fit_status')
                or member.get('candidate_board_sha256') != candidate_case.get('source_sha256')
                or member.get('member_key') != transfer.get('member_key')):
            raise ValueError(f'G22 reconstruction qualification differs from bound receipts: {number}')
        display_binding = member.get('display_binding', {})
        expected_panel_sources = {
            'org': ['ORG'], 'candidate': [f'candidate_member_{number}'], 'edit': ['EDIT'],
            'candidate_added_vs_org': [f'candidate_member_{number}', 'ORG'],
            'candidate_removed_vs_org': ['ORG', f'candidate_member_{number}'],
            'edit_missing_vs_candidate': ['EDIT', f'candidate_member_{number}'],
            'candidate_extra_vs_edit': [f'candidate_member_{number}', 'EDIT'],
        }
        expected_source_hashes = {
            case: slice_receipt.get('cases', {}).get(case, {}).get('gerbers', {}).get('F.Cu', {}).get('sha256')
            for case in {source for sources in expected_panel_sources.values() for source in sources}
        }
        if any(not isinstance(digest, str) or len(digest) != 64
               or any(character not in '0123456789abcdef' for character in digest)
               for digest in expected_source_hashes.values()):
            raise ValueError(f'G22 reconstruction source Gerber hash missing or invalid: {number}')
        expected_analysis_bounds = exported.get('local_neighbor_interaction', {}).get('window_bounds_mm')
        expected_view_box = ([expected_analysis_bounds[0], expected_analysis_bounds[1],
                              expected_analysis_bounds[2] - expected_analysis_bounds[0],
                              expected_analysis_bounds[3] - expected_analysis_bounds[1]]
                             if isinstance(expected_analysis_bounds, list) and len(expected_analysis_bounds) == 4
                             else None)
        if (display_binding.get('member') != number
                or display_binding.get('member_key') != transfer.get('member_key')
                or display_binding.get('fixed_window_mm') != recorded.get('bounds_org_mm')
                or display_binding.get('analysis_window_mm') != expected_analysis_bounds
                or display_binding.get('view_box_mm') != expected_view_box
                or member.get('view_box_mm') != expected_view_box
                or display_binding.get('panel_source_cases') != expected_panel_sources
                or display_binding.get('source_gerber_sha256_by_case') != expected_source_hashes):
            raise ValueError(f'G22 reconstruction display/source binding mismatch: {number}')
        panel_hashes = display_binding.get('panel_sha256', {})
        panels = member.get('panels', {})
        if (set(panel_hashes) != set(expected_panel_sources)
                or set(panels) != set(expected_panel_sources)
                or any(panel_hashes.get(panel) != hashlib.sha256(panels[panel].encode('utf-8')).hexdigest()
                       for panel in expected_panel_sources)):
            raise ValueError(f'G22 reconstruction displayed panel content hash mismatch: {number}')
        if number == 2 and measurements.get('B_alternatives_retained') != transfer.get('edit_candidate_alternatives_retained'):
            raise ValueError('G22 reconstruction changed B correspondence alternatives')
        if number == 3 and measurements.get('whole_target_fit') != 'NOT_ESTABLISHED':
            raise ValueError('G22 reconstruction falsely qualifies incomplete C target')


def _copy_g22_reconstruction(root, config, scene, stage):
    """Attach a verified Slice D payload to its registered client family map."""
    binding = config.get('g22_reconstruction')
    if not binding:
        return
    payload_binding = binding['payload']
    payload_path = local(root, payload_binding['path'])
    payload = json.loads(payload_path.read_text())
    if payload.get('schema') != 'pcb-g22-family-reconstruction-visual-v1':
        raise ValueError('G22 reconstruction visual payload schema mismatch')
    dataset_id = binding['dataset_id']
    if dataset_id not in {row['id'] for row in config['datasets']}:
        raise ValueError('G22 reconstruction dataset is not registered')
    if dataset_id not in scene['ingestion'].get('org_family_maps', {}):
        raise ValueError('G22 reconstruction requires the matching ORG family map in this publication')
    if payload.get('dataset_id') != dataset_id or payload.get('source_receipt_sha256') != binding['slice_c_receipt_sha256']:
        raise ValueError('G22 reconstruction payload/receipt identity mismatch')
    receipt_binding = binding.get('slice_c_receipt')
    fit_binding = binding.get('slice_b_report')
    contract_binding = binding.get('experiment_contract')
    if not receipt_binding or not fit_binding or not contract_binding:
        raise ValueError('G22 reconstruction requires bound contract, fit report, and Slice C receipt')
    receipt_path, fit_path, contract_path = (local(root, receipt_binding['path']), local(root, fit_binding['path']),
                                             local(root, contract_binding['path']))
    if (sha(receipt_path) != binding['slice_c_receipt_sha256']
            or payload.get('slice_b_report_sha256') != sha(fit_path)
            or payload.get('experiment_contract_sha256') != sha(contract_path)):
        raise ValueError('G22 reconstruction evidence hashes do not match payload')
    audit_binding = binding.get('chatgpt_audit_receipt')
    if not audit_binding or payload.get('review', {}).get('chatgpt_audit_receipt_sha256') != audit_binding.get('sha256'):
        raise ValueError('G22 reconstruction summary audit receipt is not bound')
    audit_path = local(root, audit_binding['path'])
    audit_snapshot = Path('g22_reconstruction/chatgpt_audit_receipt.md')
    target = stage / audit_snapshot
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(audit_path, target)
    build_binding = binding.get('slice_d_build_receipt')
    build_snapshot = None
    if build_binding:
        build_path = local(root, build_binding['path'])
        build_data = json.loads(build_path.read_text())
        if (sha(build_path) != build_binding.get('sha256')
                or build_data.get('schema') != 'g22-slice-d-build-receipt/1'
                or build_data.get('status') != 'SOURCE_BOUND_VISUAL_PAYLOAD_BUILT'
                or build_data.get('output_payload_sha256') != sha(payload_path)):
            raise ValueError('G22 Slice D build receipt is invalid or unbound')
        build_snapshot = Path('g22_reconstruction/slice_d_build_receipt.json')
        build_target = stage / build_snapshot
        build_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(build_path, build_target)
    slice_receipt = json.loads(receipt_path.read_text())
    fit = json.loads(fit_path.read_text())
    _validate_g22_reconstruction_payload(payload, slice_receipt, fit, dataset_id)
    if not payload.get('members') or [row.get('member') for row in payload['members']] != [1, 2, 3]:
        raise ValueError('G22 reconstruction payload member set mismatch')
    if not any(row.get('member_key') for row in payload['members']):
        raise ValueError('G22 reconstruction member identities are missing')
    scene['ingestion']['g22_reconstruction'] = {
        'dataset_id': dataset_id,
        'payload_sha256': sha(payload_path),
        'slice_c_receipt_sha256': binding['slice_c_receipt_sha256'],
        'payload': payload,
        'review_receipt': {'snapshot': audit_snapshot.as_posix(), 'sha256': sha(target)},
        'slice_d_build_receipt': ({'snapshot': build_snapshot.as_posix(), 'sha256': sha(stage / build_snapshot)}
                                  if build_snapshot else None),
    }


def _write_workbench(stage, scene, config, sources):
    from tools.visual_report import embed_scene

    raw = embed_scene(scene)
    template = sources['web/workbench.html'].decode()
    embedded = raw
    if len(raw.encode()) > 32 * 1024 * 1024:
        embedded = base64.b64encode(gzip.compress(raw.encode(), mtime=0)).decode()
        template = template.replace('id="scene-data"', 'id="scene-data" data-encoding="gzip-base64"')
    app = '\n'.join(sources[path].decode() for path in APP_SOURCES)
    page = (template.replace('__SCENE__', embedded)
            .replace('__DIGEST__', hashlib.sha256(raw.encode()).hexdigest())
            .replace('__APP__', app))
    (stage / 'index.html').write_text(page)
    (stage / 'scene.json').write_text(raw)
    write_json(stage / 'registry.json', config)


def _receipt(stage, config, render_inputs, implementation):
    return {
        'schema': PUBLICATION_SCHEMA,
        'status': 'PASS',
        'scope': 'Source/evidence consistency and read-only registration; historical engineering outcomes not rerun',
        'registry_sha256': digest_registry(config),
        'render_inputs': render_inputs,
        'outputs': {str(p.relative_to(stage)): sha(p) for p in sorted(stage.rglob('*')) if p.is_file()},
        'implementation': implementation,
        'runtime': {
            'python': sys.version,
            'packages': {p: importlib.metadata.version(p) for p in ('gerbonara', 'shapely')},
        },
        'cursor_review': generation_review(),
        'power_loss_durability': 'NOT_ESTABLISHED',
    }


def _replace_entry(destination, revision):
    temporary = destination / ('.entry-' + uuid.uuid4().hex)
    redirect = (
        '<!doctype html><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0;url={revision.name}/index.html">'
        f'<a href="{revision.name}/index.html">Open verified ingestion workbench</a>'
    )
    try:
        temporary.write_text(redirect)
        os.replace(temporary, destination / 'index.html')
    finally:
        temporary.unlink(missing_ok=True)


def publish(root, config, destination, fail_before_publish=False):
    """Single-writer publication; failure never replaces the prior entry."""
    validate_registry(config)
    root = Path(root).resolve()
    destination = _publication_directory(root, destination)
    bindings = _input_bindings(config)
    verify(root, bindings)
    sources = {path: (root / path).read_bytes() for path in IMPLEMENTATION_SOURCES}
    implementation = {path: hashlib.sha256(data).hexdigest() for path, data in sources.items()}
    destination.mkdir(parents=True, exist_ok=True)
    stage = destination / ('.staging-' + uuid.uuid4().hex)
    stage.mkdir()
    try:
        scene = _copy_replay(root, config, stage)
        render_inputs = _add_ingestion(root, config, scene)
        _copy_evidence(root, scene, stage)
        _copy_identity_reviews(root, config, scene, stage)
        bindings.extend(_copy_intake(root, config, scene, stage))
        bindings.extend(_copy_org_family_maps(root, config, scene, stage))
        _copy_g22_reconstruction(root, config, scene, stage)
        from .catalogue_scene import copy_projection
        bindings.extend(copy_projection(root,config,scene,stage))
        _write_workbench(stage, scene, config, sources)
        verify(root, bindings)
        verify(root, [{'path': p, 'sha256': h} for p, h in implementation.items()])
        write_json(stage / 'receipt.json', _receipt(stage, config, render_inputs, implementation))
        verify_publication(stage)
        if fail_before_publish:
            raise RuntimeError('Injected failure before publication')
        revision = destination / ('run-' + uuid.uuid4().hex)
        stage.rename(revision)
        _replace_entry(destination, revision)
        return revision
    finally:
        if stage.exists():
            shutil.rmtree(stage)
