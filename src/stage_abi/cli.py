"""Host-configured local JSON CLI; no request-supplied paths or executable code."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from . import ABI_VERSION
from .contracts import StageABIError
from .store import ArtifactStore
from .registry import TrustedRegistry
from .service import StageService
from .spindle import SpindleAdapter
from .lands import LandAdapter
from .width import WidthAdapter
from .routes import RouteAdapter
ROOT=Path(__file__).resolve().parents[2]

def unique_object(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('Duplicate JSON key: '+key)
  result[key]=value
 return result

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--registry',type=Path,required=True,help='Trusted host catalogue under this checkout');p.add_argument('--registry-sha256',required=True);p.add_argument('--store',type=Path,required=True,help='Project-local output artifact store');p.add_argument('--input',type=Path)
 args=p.parse_args(argv)
 try:
  registry_path=args.registry.resolve();store_path=args.store.resolve()
  if not registry_path.is_relative_to(ROOT) or not store_path.is_relative_to(ROOT/'out'):raise StageABIError('HOST_SCOPE_INVALID','registry must be project-local; store must be under out/')
  raw=registry_path.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=args.registry_sha256:raise StageABIError('REGISTRY_BINDING_MISMATCH','trusted catalogue digest')
  doc=json.loads(raw,object_pairs_hook=unique_object)
  request_raw=args.input.read_bytes() if args.input else sys.stdin.buffer.read(2_000_001)
  if len(request_raw)>2_000_000:raise StageABIError('REQUEST_TOO_LARGE','2 MB local wire limit')
  request=json.loads(request_raw,object_pairs_hook=unique_object);store=ArtifactStore(store_path);registry=TrustedRegistry(store,doc);service=StageService(store,registry,{'spindle-v1':SpindleAdapter(),'round-class-v1':LandAdapter('t01'),'rectangle-inclusive-v1':LandAdapter('t02'),'native-width-v1':WidthAdapter(),'parallel-route-v1':RouteAdapter()})
  response=service.dispatch(request)
 except (OSError,ValueError,TypeError,RecursionError) as error:
  response=dict(abi_version=ABI_VERSION,request_id=None,operation=None,status='REJECTED',result=None,error=dict(code=error.code if isinstance(error,StageABIError) else 'INPUT_OR_HOST_CONFIG_INVALID',message=str(error)))
 print(json.dumps(response,sort_keys=True,separators=(',',':'),allow_nan=False))
 return 0 if response['status']=='OK' else 2
if __name__=='__main__':raise SystemExit(main())
