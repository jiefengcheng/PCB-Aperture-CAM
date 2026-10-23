"""Build or verify a local ingestion replay without executing PCB operations."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion_registry import publish
from src.ingestion_verification import verify_publication


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, help='Explicit registration recipe; otherwise retain the current published registry')
    parser.add_argument('--output', type=Path, default=ROOT / 'out/ingestion/workbench')
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--fail-before-publish', action='store_true')
    parser.add_argument('--common-context', type=Path, help='Bind a completed common-catalogue acceptance.json')
    parser.add_argument('--storage-themes', action='store_true', help='Show the recorded discovery/grouping/storage/export visualization')
    parser.add_argument('--org-family-map-bundle', type=Path,
                        help='Bind a verified ORG-only family map for read-only review under Storage & indexes')
    parser.add_argument('--add-directory', type=Path, help='Add a sealed general intake profile or restore a qualified package under checkout/dataset')
    parser.add_argument('--serve', action='store_true', help='Serve the workbench and local directory intake')
    parser.add_argument('--port', type=int, default=8769)
    args = parser.parse_args(argv)
    if args.verify:
        result = verify_publication(args.verify)
    else:
        default_registry = ROOT / 'contracts/ingestion_registry_v1.json'
        if args.registry:
            config = json.loads(args.registry.read_text())
        else:
            from tools.ingestion_server import published_config
            config = published_config(args.output, None)
            if config is None:
                config = json.loads(default_registry.read_text())
        if args.serve:
            if args.add_directory:
                parser.error('--add-directory and --serve are separate actions')
            from tools.ingestion_server import serve
            serve(ROOT, args.output, config, args.port)
            return 0
        if args.add_directory:
            from src.directory_intake import restore_directory
            config = restore_directory(ROOT, config, args.add_directory)
        if args.common_context:
            from src.ingestion_files import local,sha
            path=local(ROOT,str(args.common_context))
            config['common_context']={'path':str(path.relative_to(ROOT)),'sha256':sha(path)}
        if args.storage_themes:
            if not config.get('common_context'):parser.error('--storage-themes requires a bound common context')
            config['common_context_presentation']='storage-themes-v1'
        if args.org_family_map_bundle:
            from src.ingestion_files import sha
            bundle = args.org_family_map_bundle.resolve() if args.org_family_map_bundle.is_absolute() else (ROOT / args.org_family_map_bundle).resolve()
            if not bundle.is_relative_to(ROOT / 'out'):
                parser.error('--org-family-map-bundle must be under checkout/out')
            materialization = json.loads((bundle / 'materialization.json').read_text())
            dataset_id = materialization.get('dataset_id')
            if not isinstance(dataset_id, str) or not dataset_id:
                parser.error('Family map bundle has no dataset identity')
            config.setdefault('org_family_maps', {})[dataset_id] = {
                'bundle_path': bundle.relative_to(ROOT).as_posix(),
                'materialization_sha256': sha(bundle / 'materialization.json'),
                'acceptance_sha256': sha(bundle / 'acceptance.json'),
            }
        run = publish(ROOT, config, args.output, args.fail_before_publish)
        result = {'status': 'PASS', 'run': str(run), 'entry': str(args.output / 'index.html')}
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)}))
        sys.exit(1)
