#!/usr/bin/env python3
"""One actual image-location gate against freshly qualified directory source."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.t01_operator_host import read
from src.u03_board.crop_roi import CropLocation,OPERATIONS

def main():
    p=argparse.ArgumentParser();p.add_argument('--session',required=True,type=Path);p.add_argument('--input',required=True,type=Path);a=p.parse_args();r={}
    try:
        from tools.pcb_workspace import WORK
        if not a.session.absolute().is_relative_to(WORK):raise ValueError('U03_LACIE_SESSION_REQUIRED')
        r=read(a.input)
        if set(r)!={'abi_version','request_id','operation'} or r['abi_version']!='pcb-u03-crop/1' or r['operation'] not in OPERATIONS:raise ValueError('U03_CROP_REQUEST_INVALID')
        service=CropLocation(a.session);result=service.locate() if r['operation']==OPERATIONS[0] else service.verify();error=None;code=0
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr);result=None;error=dict(code='U03_CROP_REJECTED',message=str(e));code=2
    print(json.dumps(dict(abi_version='pcb-u03-crop/1',request_id=r.get('request_id'),operation=r.get('operation'),status='OK' if error is None else 'REJECTED',result=result,error=error),sort_keys=True,allow_nan=False));return code

if __name__=='__main__':raise SystemExit(main())
