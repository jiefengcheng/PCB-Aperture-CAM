"""Add a sealed profiled intake or restore a qualified local package.

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
from .dataset_profiler import verify_profile

PROFILES = 'contracts/ingestion_packages_v1.json'


def _picker_inventory(files):
    """Normalize the one macOS Finder metadata file that directory pickers may omit.

    The server separately verifies the complete package seal, including this file.
    All other names, sizes and hashes must still match the selected directory.
    """
    return [row for row in files
            if '.DS_Store' not in PurePosixPath(row.get('path', '')).parts]


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
    if not matches:
        return _restore_profiled_intake(root, config, package, selected_files)
    require(len(matches) == 1, 'Ambiguous qualified restoration profile for this project directory')
    profile = matches[0]
    require(local(root, profile['seal']['path']) == package / 'SHA256SUMS', 'Profile seal path mismatch')
    manifest, inventory = package_inventory(root, package, profile['seal']['sha256'])
    if selected_files is not None:
        require(isinstance(selected_files, list) and all(isinstance(row, dict) for row in selected_files), 'Invalid selected file inventory')
        require(len({row.get('path') for row in selected_files}) == len(selected_files), 'Duplicate selected file paths')
        require(sorted(_picker_inventory(selected_files), key=lambda row: row.get('path', '')) ==
                _picker_inventory(inventory),
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


def _restore_profiled_intake(root, config, package, selected_files):
    """Register a sealed generic intake profile without claiming qualification."""
    require(package.is_relative_to(root / 'dataset'), 'Profiled intake must be under checkout/dataset')
    require(package.is_dir(), 'Selected directory has no qualified restore recipe or sealed intake profile')
    result = verify_profile(package)
    profile_path = package / 'metadata/profile.json'
    profile = json.loads(profile_path.read_text())
    recipe_path = package / 'metadata/registration_recipe.json'
    require(profile.get('schema') == 'pcb-cam-general-intake-profile-v1' and recipe_path.is_file(),
            'No qualified restore recipe or supported general intake profile for this directory')
    recipe = json.loads(recipe_path.read_text())
    package_root = package.relative_to(root).as_posix()
    require(recipe.get('schema') == 'pcb-cam-general-intake-registration-recipe-v1'
            and recipe.get('package_root') == package_root
            and recipe.get('seal_path') == f'{package_root}/SHA256SUMS',
            'Sealed registration recipe does not match the selected package directory')
    inventory = []
    for path in sorted(package.rglob('*')):
        require(not path.is_symlink(), 'Profiled package symlinks are unsupported')
        if path.is_file():
            inventory.append({'path': path.relative_to(package).as_posix(),
                              'sha256': sha(path), 'bytes': path.stat().st_size})
    if selected_files is not None:
        require(isinstance(selected_files, list) and all(isinstance(row, dict) for row in selected_files),
                'Invalid selected file inventory')
        require(len({row.get('path') for row in selected_files}) == len(selected_files),
                'Duplicate selected file paths')
        require(sorted(_picker_inventory(selected_files), key=lambda row: row.get('path', '')) ==
                _picker_inventory(inventory),
                'Selected directory bytes differ from the sealed intake profile')

    dataset = copy.deepcopy(recipe.get('dataset'))
    require(isinstance(dataset, dict) and dataset.get('id') == profile['dataset_id']
            and dataset.get('intake_status') == 'PROFILED_NOT_QUALIFIED',
            'Invalid profiled-intake registration recipe')
    sources, evidence = dataset.get('sources'), dataset.get('evidence')
    require(isinstance(sources, list) and isinstance(evidence, list) and evidence,
            'Registration recipe has no source/evidence bindings')
    verify(root, sources + evidence)
    restored = copy.deepcopy(config)
    index = next((i for i, row in enumerate(restored['datasets']) if row['id'] == dataset['id']), None)
    if index is None:
        restored['datasets'].append(dataset)
    else:
        require(restored['datasets'][index] == dataset,
                'Existing dataset registration conflicts with this profiled intake')
    seal = {'path': f'{package_root}/SHA256SUMS', 'sha256': result['seal_sha256']}
    restored['dataset_seal'] = seal
    restored['directory_intake'] = {
        'mode': 'RESTORE_PROFILED_INTAKE', 'dataset_id': dataset['id'],
        'package_root': package_root, 'files_verified': len(inventory),
        'inventory_sha256': hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'profile': {'path': f'{package_root}/metadata/profile.json', 'sha256': sha(profile_path)},
        'selected_bytes_checked': selected_files is not None,
        'scope': 'Sealed file custody profile only; content qualification NOT_RUN; no native extraction or CAM execution',
    }
    validate_registry(restored)
    return restored
