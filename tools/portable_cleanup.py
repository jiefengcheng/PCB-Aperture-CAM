"""Sealed-package entry; initialize an explicit workspace or run the same CLI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def verify_payload():
    manifest=json.loads((ROOT/'PAYLOAD_MANIFEST.json').read_bytes())
    if manifest.get('schema')!='portable-cleanup-payload/1':raise ValueError('PACKAGE_MANIFEST_CHANGED')
    for relative,sha in manifest['files'].items():
        path=ROOT/relative
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError('PORTABLE_PAYLOAD_CHANGED:'+relative)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('command',choices=['init','run','run-pipeline','status','prepare-display','self-check'])
    args,rest=parser.parse_known_args()
    from src.cleanup_runtime import initialize,is_portable,configure_portable
    if not is_portable():raise ValueError('SEALED_PORTABLE_PACKAGE_REQUIRED')
    verify_payload()
    if args.command=='init':
        if rest:parser.error('unexpected init arguments')
        print(json.dumps(initialize(args.workspace)));return
    os.environ['PCB_CLEANUP_WORKSPACE']=str(args.workspace)
    configure_portable()
    if args.command=='self-check':
        import platform,shapely,numpy,gerbonara
        from src.gerber_u05.pipeline import build_source
        from src.indexed_polygon_distance import Engine
        from shapely.geometry import box
        with_engine=Engine()
        try:distance=with_engine.measure(box(0,0,1,1),box(2,0,3,1))
        finally:with_engine.close()
        print(json.dumps(dict(status='PASS_BUNDLED_RUNTIME',python=sys.version,prefix=sys.prefix,
            architecture=platform.machine(),numpy=numpy.__version__,shapely=shapely.__version__,
            geos=shapely.geos_version_string,gerbonara=gerbonara.__version__,exact_distance_mm=distance,
            loaded_extensions=[m.__file__ for m in sys.modules.values() if (getattr(m,'__file__','') or '').endswith(('.so','.dylib'))])));return
    if args.command=='run-pipeline':
        from tools.run_copper_pipeline import main as run_cli
        command='run'
    else:
        from tools.run_large_copper import main as run_cli
        command=args.command
    sys.argv=[sys.argv[0],command,*rest]
    raise SystemExit(run_cli())


if __name__=='__main__':main()
