"""Restore registered presentation from a qualified, sealed local package.

The selected directory supplies bytes/identity, not authority to execute scripts.
Profiles retain the reviewed evidence recipe independently of dropdown entries.
"""
import copy
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from .ingestion_contracts import require, validate_registry
from .ingestion_files import local, sha, verify

PROFILES = 'contracts/ingestion_packages_v1.json'


def remove_dataset(config, dataset_id):
    """Unregister one row. No filesystem deletion or source mutation."""
    validate_registry(config)
    require(isinstance(dataset_id, str) and dataset_id, 'Selected dataset identity is required')
    require(any(row['id'] == dataset_id for row in config['datasets']), 'Selected dataset is not registered')
    updated = copy.deepcopy(config)
    updated['datasets'] = [row for row in updated['datasets'] if row['id'] != dataset_id]
    if updated.get('directory_intake', {}).get('dataset_id') == dataset_id:
        updated.pop('directory_intake')
    updated['registration_change'] = {'action': 'REMOVE_DATASET', 'dataset_id': dataset_id,
                                      'inputs_and_history': 'RETAINED'}
    validate_registry(updated)
    return updated


def package_inventory(root, package, expected_seal):
    package = Path(package).resolve()
    require(package.is_relative_to(Path(root).resolve() / 'dataset'), 'Package must be under checkout/dataset')
    require(package.is_dir(), 'Selected package directory is missing')
    sums = package / 'SHA256SUMS'
    require(sha(sums) == expected_seal, 'Package checksum seal mismatch')
    checks = {}
    for line in sums.read_text().splitlines():
        digest, separator, name = line.partition('  ')
        path = PurePosixPath(name)
        require(separator and re.fullmatch('[0-9a-f]{64}', digest)
                and name and not path.is_absolute() and '..' not in path.parts
                and name not in checks and name != 'SHA256SUMS', 'Invalid package checksum entry')
        checks[name] = digest
    require(checks, 'Empty package checksum inventory')
    actual = {}
    for path in sorted(package.rglob('*')):
        require(not path.is_symlink(), 'Package symlinks are unsupported')
        if path.is_file():
            name = path.relative_to(package).as_posix()
            actual[name] = {'path': name, 'sha256': sha(path), 'bytes': path.stat().st_size}
    require(set(actual) == set(checks) | {'SHA256SUMS'}, 'Unlisted or missing package files')
    require(all(actual[name]['sha256'] == digest for name, digest in checks.items()), 'Package file hash mismatch')
    require(actual['SHA256SUMS']['sha256'] == expected_seal, 'Package changed during verification')
    manifest = json.loads((package / 'metadata/manifest.json').read_text())
    require(manifest.get('schema') == 'pcb-cam-dataset-manifest-v1', 'Unsupported package manifest')
    rows = manifest.get('files', [])
    require(len({row['path'] for row in rows}) == len(rows)
            and {row['path'] for row in rows} == set(checks) - {'metadata/manifest.json'}, 'Manifest coverage mismatch')
    require(all(all(actual[row['path']][key] == row[key] for key in ('path', 'sha256', 'bytes'))
                for row in rows), 'Manifest file metadata mismatch')
    return manifest, list(actual.values())


def restore_directory(root, config, directory, selected_files=None):
    root = Path(root).resolve()
    package = local(root, str(directory))
    profiles = json.loads(local(root, PROFILES).read_text())
    require(profiles.get('schema') == 'pcb-ingestion-package-profiles-v1', 'Unsupported package profile register')
    matches = [row for row in profiles['packages'] if local(root, row['package_root']) == package]
    require(len(matches) == 1, 'No qualified restoration profile for this project directory')
    profile = matches[0]
    require(local(root, profile['seal']['path']) == package / 'SHA256SUMS', 'Profile seal path mismatch')
    manifest, inventory = package_inventory(root, package, profile['seal']['sha256'])
    if selected_files is not None:
        require(isinstance(selected_files, list) and all(isinstance(row, dict) for row in selected_files), 'Invalid selected file inventory')
        require(len({row.get('path') for row in selected_files}) == len(selected_files), 'Duplicate selected file paths')
        require(sorted(selected_files, key=lambda row: row.get('path', '')) == inventory,
                'Selected directory bytes differ from the qualified project package')
    dataset = copy.deepcopy(profile['dataset'])
    require(manifest['dataset_id'] == dataset['id'], 'Package/profile dataset identity mismatch')
    sources = {(row['path'], row['sha256']) for row in dataset['sources']}
    require(all((str(package.relative_to(root) / row['path']), row['sha256']) in sources
                for row in inventory if row['path'].startswith('raw/')), 'Profile does not register every raw input')
    verify(root, dataset['sources'] + dataset['evidence'])
    restored = copy.deepcopy(config)
    index = next((i for i, row in enumerate(restored['datasets']) if row['id'] == dataset['id']), None)
    if index is None:
        restored['datasets'].append(dataset)
    else:
        require(restored['datasets'][index] == dataset, 'Existing dataset registration conflicts with the qualified profile')
    restored['dataset_seal'] = copy.deepcopy(profile['seal'])
    restored['directory_intake'] = {
        'mode': 'RESTORE_QUALIFIED_PACKAGE', 'dataset_id': dataset['id'],
        'package_root': profile['package_root'], 'files_verified': len(inventory),
        'inventory_sha256': hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'profile': {'path': PROFILES, 'sha256': sha(local(root, PROFILES))},
        'selected_bytes_checked': selected_files is not None,
        'scope': 'Preserved files, registration and recorded review; no native extraction or new CAM execution',
    }
    validate_registry(restored)
    return restored
