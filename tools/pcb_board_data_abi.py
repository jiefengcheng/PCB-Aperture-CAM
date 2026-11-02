#!/usr/bin/env python3
"""One bounded PCB-data operation with a digest-bound native host registry."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.stage_abi.store import digest
from src.pcb_data_abi import ABI_VERSION
from src.pcb_data_abi.service import DataService,OPERATIONS
from src.pcb_data_abi.board_scope import BoardScopeService as ROIService, OPERATIONS as ROI_OPERATIONS
from tools.t01_route_client import decode


def main():
    p=argparse.ArgumentParser();p.add_argument('--registry',type=Path,required=True);p.add_argument('--registry-sha256',required=True);p.add_argument('--input',type=Path,required=True);a=p.parse_args()
    req={}
    try:
        blob=a.input.read_bytes()
        if len(blob)>65536:raise ValueError('PCB_DATA_REQUEST_TOO_LARGE')
        req=decode(blob)
        if type(req)is not dict or set(req)!={'abi_version','request_id','operation'} or req['abi_version']!=ABI_VERSION or req['operation'] not in (*OPERATIONS,*ROI_OPERATIONS) or type(req['request_id'])is not str:raise ValueError('PCB_DATA_REQUEST_INVALID')
        raw=a.registry.read_bytes()
        if digest(raw)!=a.registry_sha256:raise ValueError('PCB_DATA_HOST_HASH_MISMATCH')
        host=json.loads(raw)
        if req['operation'] in ROI_OPERATIONS:
            result=ROIService(host).dispatch(req['operation'])
            response=dict(abi_version=ABI_VERSION,request_id=req['request_id'],operation=req['operation'],status='OK',result=result,error=None)
            print(json.dumps(response,sort_keys=True,allow_nan=False));return 0
        if host.get('schema')=='pcb-board-data-host/1':
            from src.pcb_data_abi.board_export import BoardDataService
            service=BoardDataService(host)
        else:raise ValueError('PCB_BOARD_DATA_HOST_SCOPE_INVALID')
        result=service.dispatch(req['operation'])
        response=dict(abi_version=ABI_VERSION,request_id=req['request_id'],operation=req['operation'],status='OK',result=result,error=None);code=0
    except Exception as e:
        safe=req if type(req)is dict else {}
        response=dict(abi_version=ABI_VERSION,request_id=safe.get('request_id') if type(safe.get('request_id'))is str else None,operation=safe.get('operation') if type(safe.get('operation'))is str else None,status='REJECTED',result=None,error=dict(code='PCB_DATA_REJECTED',message=str(e)));code=2
    print(json.dumps(response,sort_keys=True,allow_nan=False));return code

if __name__=='__main__':raise SystemExit(main())
