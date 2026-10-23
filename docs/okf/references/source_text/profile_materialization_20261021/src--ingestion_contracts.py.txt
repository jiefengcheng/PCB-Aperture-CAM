"""Registration/publication metadata contracts, independent of file I/O."""
import hashlib
import json
import re
from pathlib import PurePosixPath

PUBLICATION_SCHEMA = 'pcb-ingestion-publication-v2'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest_registry(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def validate_registry(config):
    require(isinstance(config, dict), 'Registry must be an object')
    require(config.get('schema') == 'pcb-ingestion-registration-v1', 'Unsupported registry schema')
    datasets = config.get('datasets')
    require(isinstance(datasets, list), 'Dataset registration must be a list')
    require(all(isinstance(d, dict) for d in datasets), 'Dataset must be an object')
    ids = [d.get('id') for d in datasets]
    require(all(isinstance(i, str) and i for i in ids) and len(ids) == len(set(ids)), 'Invalid/duplicate dataset IDs')
    for dataset in datasets:
        for key in ('sources', 'evidence'):
            rows = dataset.get(key)
            require(isinstance(rows, list) and rows, 'Missing dataset ' + key)
            for row in rows:
                require(isinstance(row, dict), 'Binding must be an object')
                require(isinstance(row.get('path'), str) and bool(row['path']), 'Invalid binding path')
                require(isinstance(row.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'Invalid binding hash')


def generation_review():
    """A build cannot inherit a review of a different source/run snapshot."""
    return {
        'status': 'NOT_RUN',
        'reason': 'NO_REVIEW_ATTACHED_TO_THIS_PUBLICATION',
        'scope': 'AT_GENERATION',
    }


def intake_projection(config, read_bytes):
    """Describe retained intake metadata, bound through the registered external seal.

    read_bytes accepts checkout-relative paths. No source files are rewritten.
    Synthetic publisher fixtures without a sealed intake have no projection.
    """
    seal = config['dataset_seal']
    seal_path = PurePosixPath(seal['path'])
    if seal_path.name != 'SHA256SUMS':
        return None
    package = str(seal_path.parent)
    raw = read_bytes(seal['path'])
    require(hashlib.sha256(raw).hexdigest() == seal['sha256'], 'Intake seal mismatch')
    checksums = {}
    for line in raw.decode().splitlines():
        digest, separator, path = line.partition('  ')
        require(separator and re.fullmatch('[0-9a-f]{64}', digest) and path not in checksums,
                'Invalid intake checksum entry')
        checksums[path] = digest
    artifacts = {}
    manifest = None
    for name, relative in [('entry', 'index.md'), ('manifest', 'metadata/manifest.json'),
                           ('checksums', 'SHA256SUMS')]:
        path = str(seal_path.parent / relative)
        digest = seal['sha256'] if name == 'checksums' else checksums.get(relative)
        data = read_bytes(path)
        require(digest and hashlib.sha256(data).hexdigest() == digest,
                'Intake metadata does not match seal: ' + relative)
        artifacts[name] = {'path': path, 'sha256': digest, 'snapshot': 'intake/' + relative}
        if name == 'manifest':
            manifest = json.loads(data)
    dataset = next((d for d in config['datasets'] if d['id'] == manifest['dataset_id']), None)
    if dataset is None:
        return None
    registered = {(r['path'], r['sha256']) for r in dataset['sources']}
    files = [row for row in manifest['files'] if row['path'].startswith('raw/')]
    require(files, 'Missing intake raw file records')
    for row in files:
        path = str(seal_path.parent / row['path'])
        require((path, row['sha256']) in registered and checksums.get(row['path']) == row['sha256'],
                'Intake raw file is not registered/sealed: ' + path)
    if manifest.get('schema') == 'pcb-cam-general-intake-manifest-v1':
        profile_path = str(seal_path.parent / 'metadata/profile.json')
        profile_bytes = read_bytes(profile_path)
        profile_digest = checksums.get('metadata/profile.json')
        require(profile_digest and hashlib.sha256(profile_bytes).hexdigest() == profile_digest,
                'Generic intake profile does not match seal')
        profile = json.loads(profile_bytes)
        source_rows = [{key: value for key, value in row.items() if key != 'package_path'}
                       for row in manifest.get('source_files', [])]
        require(profile.get('schema') == 'pcb-cam-general-intake-profile-v1'
                and profile.get('dataset_id') == manifest.get('dataset_id') == dataset['id']
                and profile.get('files') == source_rows
                and profile.get('registration_recipe', {}).get('path') == 'metadata/registration_recipe.json'
                and profile.get('registration_recipe', {}).get('status') == 'GENERATED_AND_INCLUDED_IN_PACKAGE_SEAL'
                and profile.get('intake', {}).get('qualification') == 'NOT_RUN'
                and profile.get('intake', {}).get('workbench_registration') == 'NOT_RUN'
                and profile.get('intake', {}).get('engineering_or_manufacturing_acceptance') == 'NOT_ESTABLISHED',
                'Generic intake profile status or identity mismatch')
        artifacts['profile'] = {'path': profile_path, 'sha256': profile_digest,
                                 'snapshot': 'intake/metadata/profile.json'}
        recipe_path = str(seal_path.parent / 'metadata/registration_recipe.json')
        recipe_bytes = read_bytes(recipe_path)
        recipe_digest = checksums.get('metadata/registration_recipe.json')
        require(recipe_digest and hashlib.sha256(recipe_bytes).hexdigest() == recipe_digest,
                'Generic intake registration recipe does not match seal')
        recipe = json.loads(recipe_bytes)
        require(recipe.get('schema') == 'pcb-cam-general-intake-registration-recipe-v1'
                and recipe.get('package_root') == package
                and recipe.get('seal_path') == str(seal_path)
                and recipe.get('dataset') == dataset,
                'Published dataset differs from its sealed registration recipe')
        artifacts['recipe'] = {'path': recipe_path, 'sha256': recipe_digest,
                               'snapshot': 'intake/metadata/registration_recipe.json'}
        input_sets = {'preserved_directory': {
            'file_count': len(manifest.get('source_files', [])),
            'bytes': sum(row['bytes'] for row in manifest.get('source_files', [])),
            'tree_sha256': manifest.get('raw_tree_sha256'),
            'source_tree_identity_algorithm': manifest.get('raw_tree_identity_algorithm'),
        }}
        profile_kind = manifest['schema']
    else:
        input_sets = manifest['input_sets']
        profile_kind = None
    projection = {'dataset_id': dataset['id'], 'package_root': package,
                  'artifacts': artifacts, 'input_sets': input_sets, 'raw_files': files}
    if profile_kind:
        projection['profile_kind'] = profile_kind
    return projection


def verify_generation_review(receipt, ingestion):
    review = receipt.get('cursor_review')
    if isinstance(review, dict):
        require(review == generation_review(), 'Invalid generation-time review status')
        require(ingestion.get('cursor_review') == review, 'Scene/receipt review status mismatch')
    else:
        require(review == 'NOT_RUN: CHANNEL_UNAVAILABLE', 'Missing/invalid legacy generation review')
        require('cursor_review' not in ingestion, 'Structured scene review requires a structured receipt review')
    # Earlier v2 publications retain their frozen string metadata. An external
    # review addendum remains separate from generation-time publication evidence.
