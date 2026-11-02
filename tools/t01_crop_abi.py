"""One closed JSON request. All host paths are project-local command arguments."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.stage_abi import ABI_VERSION
from src.stage_abi.store import ArtifactStore, digest
from src.stage_abi.contracts import StageABIError
from src.stage_abi.cli import unique_object
from src.t01_crop.service import CropService as InteractionService

ROOT=Path(__file__).resolve().parents[1]

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registry',type=Path,required=True)
    p.add_argument('--registry-sha256',required=True)
    p.add_argument('--store',type=Path,required=True)
    p.add_argument('--input',type=Path)
    args=p.parse_args(argv)
    request=None
    try:
        path=args.registry.resolve();store_path=args.store.resolve()
        if not path.is_relative_to(ROOT) or not store_path.is_relative_to(ROOT/'out'):
            raise StageABIError('HOST_SCOPE_INVALID','Project-local registry and out/ store required')
        raw=path.read_bytes()
        if digest(raw)!=args.registry_sha256:raise StageABIError('REGISTRY_BINDING_MISMATCH','trusted host catalogue digest')
        host=json.loads(raw,object_pairs_hook=unique_object)
        wire=args.input.read_bytes() if args.input else sys.stdin.buffer.read(2_000_001)
        if len(wire)>2_000_000:raise StageABIError('REQUEST_TOO_LARGE','2 MB local limit')
        request=json.loads(wire,object_pairs_hook=unique_object)
        response=InteractionService(ArtifactStore(store_path),host).dispatch(request)
    except (StageABIError,ValueError,TypeError,OSError,RecursionError) as e:
        response=dict(abi_version=ABI_VERSION,request_id=None,operation=None,status='REJECTED',result=None,error=dict(code=e.code if isinstance(e,StageABIError) else 'T01_INPUT_OR_HOST_CONFIG_INVALID',message=str(e)))
    print(json.dumps(response,sort_keys=True,separators=(',',':'),allow_nan=False))
    return 0 if response['status']=='OK' else 2

if __name__=="__main__":raise SystemExit(main())
