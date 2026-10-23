"""Offline publication consistency, required artifacts and evidence bindings.
Unsigned local receipts do not prove authenticity or engineering acceptance.
"""
import base64
import copy
import gzip
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from .ingestion_files import local, verify
from .ingestion_contracts import (
    PUBLICATION_SCHEMA, digest_registry, intake_projection, require, validate_registry,
    verify_generation_review,
)



class SceneHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scenes = []
        self.digests = []
        self.active = False
        self.parts = []
        self.encoding = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name') == 'scene-sha256':
            self.digests.append(attrs.get('content'))
        if tag == 'script' and attrs.get('id') == 'scene-data':
            self.active = True
            self.parts = []
            self.encoding = attrs.get('data-encoding')

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.scenes.append((''.join(self.parts), self.encoding))
            self.active = False


def _verify_outputs(bundle, receipt):
    require(receipt.get('schema') == PUBLICATION_SCHEMA,
            'Unsupported/missing publication schema; legacy v1 is unqualified')
    require(receipt.get('status') == 'PASS', 'Publication status must be PASS')
    outputs = receipt.get('outputs')
    require(isinstance(outputs, dict) and outputs, 'Missing/empty publication outputs')
    require({'index.html', 'scene.json', 'registry.json'}.issubset(outputs),
            'Missing required workbench output bindings')
    for path, digest in outputs.items():
        require(isinstance(path, str) and not Path(path).is_absolute()
                and '..' not in Path(path).parts, 'Invalid output path')
        require(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest),
                'Invalid output hash')
    inventory = {
        str(path.relative_to(bundle)) for path in bundle.rglob('*')
        if path.is_file() and path != bundle / 'receipt.json'
    }
    require(inventory == set(outputs), 'Publication output inventory mismatch')
    verify(bundle, [{'path': path, 'sha256': digest} for path, digest in outputs.items()])
    return outputs


def _read_embedded_scene(bundle):
    raw = (bundle / 'scene.json').read_text()
    html = SceneHTML()
    html.feed((bundle / 'index.html').read_text())
    require(len(html.scenes) == 1 and len(html.digests) == 1,
            'Missing/ambiguous embedded scene')
    embedded, encoding = html.scenes[0]
    if encoding == 'gzip-base64':
        embedded = gzip.decompress(base64.b64decode(embedded, validate=True)).decode()
    else:
        require(encoding is None, 'Unsupported embedded scene encoding')
    require(embedded == raw, 'Embedded scene differs from scene.json')
    require(hashlib.sha256(raw.encode()).hexdigest() == html.digests[0],
            'Embedded scene checksum mismatch')
    scene = json.loads(raw)
    require(scene.get('integrity') == 'VERIFIED_AT_GENERATION', 'Scene is not verified')
    return scene


def _verify_dataset(bundle, registered, displayed, outputs):
    from .ingestion_visuals import comparison_specs, receipt_records

    stripped = copy.deepcopy(displayed)
    presentation = stripped.pop('qualification_data', None)
    require(isinstance(presentation, dict), 'Missing dataset qualification projection')
    snapshots = {}
    for ref in stripped.get('evidence', []):
        snapshot = ref.pop('snapshot', None)
        require(isinstance(snapshot, str) and outputs.get(snapshot) == ref['sha256'],
                'Missing/unbound evidence snapshot')
        snapshots[(ref['path'], ref['sha256'])] = snapshot
    require(stripped == registered, 'Displayed dataset differs from registered dataset')

    def read_snapshot(ref):
        path = local(bundle, snapshots[(ref['path'], ref['sha256'])])
        return json.loads(path.read_text())

    records = receipt_records(registered, read_snapshot)
    require(presentation.get('records') == records,
            'Displayed measurements differ from bound receipts')
    specs = comparison_specs(registered, records)
    comparisons = presentation.get('comparisons')
    require(isinstance(comparisons, list) and len(comparisons) == len(specs),
            'Missing/unexpected comparison views')
    for spec, view in zip(specs, comparisons):
        require(all(view.get(key) == value for key, value in spec.items()),
                'Comparison input/receipt binding mismatch')
        require(all(isinstance(view.get(key), str) for key in
                    ('source_path', 'native_path', 'source_only_path', 'native_only_path')),
                'Missing comparison geometry')
    return [{'dataset_id': registered['id'], **spec} for spec in specs]


def _verify_ingestion(bundle, config, scene, receipt, outputs):
    ingestion = scene.get('ingestion', {})
    require(ingestion.get('schema') == config['schema']
            and ingestion.get('mode') == 'REPLAY', 'Missing/invalid ingestion scene')
    require(ingestion.get('registry_sha256') == receipt['registry_sha256'],
            'Scene registry binding mismatch')
    require(ingestion.get('common_object_catalogue') == 'DEFERRED',
            'Unexpected catalogue authority')
    verify_generation_review(receipt, ingestion)
    family_maps = config.get('org_family_maps', {})
    displayed_maps = ingestion.get('org_family_maps', {})
    require(set(displayed_maps) == set(family_maps), 'ORG_FAMILY_MAP_SCENE_BINDING_MISMATCH')
    for dataset_id, binding in family_maps.items():
        displayed = displayed_maps[dataset_id]
        snapshot = displayed.get('snapshot')
        require(isinstance(snapshot, str) and outputs.get(snapshot) == displayed.get('projection_sha256'),
                'ORG_FAMILY_REVIEW_PROJECTION_NOT_OUTPUT_BOUND')
        projection_path = local(bundle, snapshot)
        projection = json.loads(projection_path.read_text())
        projection_binding = projection.get('binding', {})
        schema = projection.get('schema')
        require(schema in ('pcb-org-family-review-projection/1', 'pcb-org-family-review-projection/2', 'pcb-org-family-review-projection/3'),
                'ORG_FAMILY_REVIEW_PROJECTION_SCHEMA_MISMATCH')
        require(projection_binding.get('dataset_id') == dataset_id,
                'ORG_FAMILY_REVIEW_PROJECTION_DATASET_MISMATCH')
        require(projection_binding.get('map_revision') == displayed.get('map_revision')
                and projection_binding.get('map_content_sha256') == displayed.get('map_content_sha256'),
                'ORG_FAMILY_REVIEW_PROJECTION_MAP_MISMATCH')
        require(projection_binding.get('org_revision') == displayed.get('org_revision')
                and projection_binding.get('org_source_sha256') == displayed.get('org_source_sha256'),
                'ORG_FAMILY_REVIEW_PROJECTION_SOURCE_MISMATCH')
        require(len(projection.get('members', [])) == displayed.get('member_count')
                and len(projection.get('families', [])) == displayed.get('family_count')
                and len(projection.get('physical_groups', [])) == displayed.get('physical_group_count'),
                'ORG_FAMILY_REVIEW_PROJECTION_COUNT_MISMATCH')
        if schema == 'pcb-org-family-review-projection/2':
            from .org_family_review import (
                require_org_family_resource_budget,
                validate_complete_physical_groups,
                validate_geometry_path_bindings,
            )
            require_org_family_resource_budget(
                'ORG family review publication', projection_path.stat().st_size)
            validate_complete_physical_groups(
                projection, validate_paths=schema == 'pcb-org-family-review-projection/3')
            require(len(projection.get('excluded_features', []))
                    == sum(projection.get('coverage', {}).get('seed_exclusions', {}).values()),
                    'ORG_FAMILY_EXCLUSION_PROJECTION_MISMATCH')
            stored_ref = projection.get('stored_geometry_paths_ref', {})
            stored_snapshot = stored_ref.get('snapshot')
            require(isinstance(stored_snapshot, str) and outputs.get(stored_snapshot) == stored_ref.get('sha256'),
                    'ORG_FAMILY_STORED_GEOMETRY_NOT_OUTPUT_BOUND')
            stored_path = local(bundle, stored_snapshot)
            require_org_family_resource_budget(
                'ORG stored-geometry publication', stored_path.stat().st_size)
            stored_paths = json.loads(stored_path.read_text())
            require(isinstance(stored_paths, dict)
                    and set(stored_paths) == set(projection.get('geometry_paths', {}))
                    and len(stored_paths) == stored_ref.get('geometry_count')
                    and all(isinstance(path, str) and path for path in stored_paths.values()),
                    'ORG_FAMILY_STORED_GEOMETRY_PATHS_INVALID')
            if schema == 'pcb-org-family-review-projection/3':
                try:
                    validate_geometry_path_bindings(projection, stored_paths)
                except ValueError as exc:
                    raise ValueError(str(exc)) from exc
        require(displayed.get('bundle_path') == binding.get('bundle_path')
                and displayed.get('materialization_sha256') == binding.get('materialization_sha256')
                and displayed.get('acceptance_sha256') == binding.get('acceptance_sha256'),
                'ORG_FAMILY_SOURCE_BUNDLE_BINDING_MISMATCH')
    g22_binding = config.get('g22_reconstruction')
    displayed_g22 = ingestion.get('g22_reconstruction')
    if g22_binding:
        require(isinstance(displayed_g22, dict), 'G22_RECONSTRUCTION_SCENE_MISSING')
        payload = displayed_g22.get('payload')
        require(displayed_g22.get('dataset_id') == g22_binding.get('dataset_id')
                and displayed_g22.get('slice_c_receipt_sha256') == g22_binding.get('slice_c_receipt_sha256'),
                'G22_RECONSTRUCTION_RECEIPT_BINDING_MISMATCH')
        require(displayed_g22.get('payload_sha256') == g22_binding.get('payload', {}).get('sha256'),
                'G22_RECONSTRUCTION_PAYLOAD_HASH_MISMATCH')
        review_receipt = displayed_g22.get('review_receipt', {})
        require(isinstance(review_receipt.get('snapshot'), str)
                and outputs.get(review_receipt['snapshot']) == review_receipt.get('sha256')
                and review_receipt.get('sha256') == g22_binding.get('chatgpt_audit_receipt', {}).get('sha256'),
                'G22_RECONSTRUCTION_REVIEW_RECEIPT_NOT_OUTPUT_BOUND')
        build_binding = g22_binding.get('slice_d_build_receipt')
        displayed_build = displayed_g22.get('slice_d_build_receipt')
        if build_binding:
            require(isinstance(displayed_build, dict)
                    and isinstance(displayed_build.get('snapshot'), str)
                    and outputs.get(displayed_build['snapshot']) == displayed_build.get('sha256')
                    and displayed_build.get('sha256') == build_binding.get('sha256'),
                    'G22_SLICE_D_BUILD_RECEIPT_NOT_OUTPUT_BOUND')
        require(payload.get('schema') == 'pcb-g22-family-reconstruction-visual-v1'
                and payload.get('dataset_id') == g22_binding.get('dataset_id')
                and payload.get('source_receipt_sha256') == g22_binding.get('slice_c_receipt_sha256')
                and [row.get('member') for row in payload.get('members', [])] == [1, 2, 3],
                'G22_RECONSTRUCTION_PAYLOAD_IDENTITY_MISMATCH')
        require(displayed_g22.get('dataset_id') in {row['id'] for row in config['datasets']},
                'G22_RECONSTRUCTION_DATASET_UNREGISTERED')
    else:
        require(displayed_g22 is None, 'UNREGISTERED_G22_RECONSTRUCTION_IN_SCENE')
    if 'intake' in ingestion:
        from pathlib import PurePosixPath
        package = PurePosixPath(config['dataset_seal']['path']).parent
        def read_intake(path):
            snapshot = 'intake/' + str(PurePosixPath(path).relative_to(package))
            require(snapshot in outputs, 'Missing intake metadata snapshot')
            return local(bundle, snapshot).read_bytes()
        expected = intake_projection(config, read_intake)
        require(expected is not None and ingestion['intake'] == expected,
                'Displayed intake differs from sealed metadata')
    shown = ingestion.get('datasets')
    require(isinstance(shown, list) and len(shown) == len(config['datasets']),
            'Dataset scene/registry mismatch')
    render_inputs = []
    for registered, displayed in zip(config['datasets'], shown):
        render_inputs.extend(_verify_dataset(bundle, registered, displayed, outputs))
    require(receipt.get('render_inputs') == render_inputs,
            'Publication render-input binding mismatch')
    return len(shown), len(render_inputs)


def verify_publication(bundle):
    bundle = Path(bundle).resolve()
    receipt = json.loads((bundle / 'receipt.json').read_text())
    require(isinstance(receipt, dict), 'Publication receipt must be an object')
    outputs = _verify_outputs(bundle, receipt)
    scene = _read_embedded_scene(bundle)
    config = json.loads((bundle / 'registry.json').read_text())
    validate_registry(config)
    require(digest_registry(config) == receipt.get('registry_sha256'),
            'Publication registry binding mismatch')
    dataset_count, comparison_count = _verify_ingestion(bundle, config, scene, receipt, outputs)
    from .catalogue_scene import verify_projection
    verify_projection(bundle,config,scene)
    require(isinstance(receipt.get('implementation'), dict) and receipt['implementation'],
            'Missing implementation hashes')
    return {
        'status': 'PASS',
        'schema': PUBLICATION_SCHEMA,
        'scope': ('Required files, exact inventory, embedded scene, registry, receipt-derived '
                  'measurements and evidence/render-input bindings; no engineering acceptance '
                  'or authorship claim'),
        'run': str(bundle),
        'outputs_verified': len(outputs),
        'datasets_verified': dataset_count,
        'comparisons_verified': comparison_count,
    }
