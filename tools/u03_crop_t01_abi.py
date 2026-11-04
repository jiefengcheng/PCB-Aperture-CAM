#!/usr/bin/env python3
"""Closed U03 image-crop T01/handoff transport; no input discovery or rendering."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.stage_abi.store import ArtifactStore,digest
from src.stage_abi.contracts import StageABIError
from src.stage_abi.cli import unique_object
from src.t01_board.service import BoardService
from tools.t01_operator_host import read


from src.stage_abi.preparation import prepared_dispatch

def main():
    p=argparse.ArgumentParser();p.add_argument('--registry',type=Path);p.add_argument('--registry-sha256');p.add_argument('--store',type=Path);p.add_argument('--session',required=True,type=Path);p.add_argument('--input',required=True,type=Path);a=p.parse_args();request={}
    try:
        blob=a.input.read_bytes()
        if len(blob)>2_000_000:raise ValueError('U03_CROP_REQUEST_TOO_LARGE')
        request=json.loads(blob,object_pairs_hook=unique_object)
        from tools.pcb_workspace import WORK
        if not a.session.absolute().is_relative_to(WORK):raise ValueError('U03_LACIE_SESSION_REQUIRED')
        if request.get('operation')=='board_candidate_check':
            if set(request)!={'abi_version','request_id','operation'} or request['abi_version']!='pcb-board-handoff/1':raise ValueError('U03_CROP_HANDOFF_REQUEST_INVALID')
            from src.u03_board.crop_handoff import execute
            response=dict(abi_version=request['abi_version'],request_id=request['request_id'],operation=request['operation'],status='OK',result=execute(a.session),error=None)
        else:
            if not a.registry.is_relative_to(a.session) or not a.store.is_relative_to(a.session) or digest(a.registry.read_bytes())!=a.registry_sha256:raise ValueError('U03_CROP_HOST_CHANGED')
            service=BoardService
            response=prepared_dispatch(lambda:service(ArtifactStore(a.store),read(a.registry)),request)
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        response=dict(abi_version=request.get('abi_version'),request_id=request.get('request_id'),operation=request.get('operation'),status='REJECTED',result=None,error=dict(code=e.code if isinstance(e,StageABIError) else 'U03_CROP_INPUT_INVALID',message=str(e)))
    print(json.dumps(response,sort_keys=True,allow_nan=False));return 0 if response['status']=='OK' else 2

if __name__=='__main__':raise SystemExit(main())
