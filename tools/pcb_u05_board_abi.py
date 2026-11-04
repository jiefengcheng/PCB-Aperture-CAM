#!/usr/bin/env python3
"""Execute one qualified U05 continuation operation; no historical job writes."""
import sys,json,argparse,traceback
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.pcb_workspace import configure
from tools.t01_operator_host import read,fresh
from src.u05_board.custody import session,verify_u04,T05,FILES,require_operation

def execute(root,op):
    start=session(root);require_operation(root,op)
    if op=='u04_predecessor_verify':
        value=dict(facts=verify_u04(start['predecessor']));fresh(root/'u04_predecessor_verify.json',value);return value
    if op in T05:
        from src.u05_board.junctions import make_gates
        return make_gates(root).dispatch(op)
    if op in FILES:
        from src.u05_board.export import U05DataService
        return U05DataService(root).dispatch(op)
    raise ValueError('U05_OPERATION_NOT_EXPOSED')

def main():
    p=argparse.ArgumentParser();p.add_argument('--session',required=True,type=Path);p.add_argument('--input',required=True,type=Path);a=p.parse_args();request={}
    try:
        configure();from tools.t01_native_route import require_native
        require_native();request=read(a.input)
        if set(request)!={'abi_version','request_id','operation'} or request['abi_version']!='pcb-u05-board/1':raise ValueError('U05_REQUEST_INVALID')
        result=execute(a.session,request['operation']);error=None;code=0
    except Exception as e:
        traceback.print_exc(file=sys.stderr);result=None;error=dict(code='U05_NATIVE_REJECTED',message=str(e));code=2
    print(json.dumps(dict(abi_version='pcb-u05-board/1',request_id=request.get('request_id'),operation=request.get('operation'),status='OK' if error is None else 'REJECTED',result=result,error=error),sort_keys=True,allow_nan=False));return code
if __name__=='__main__':raise SystemExit(main())
