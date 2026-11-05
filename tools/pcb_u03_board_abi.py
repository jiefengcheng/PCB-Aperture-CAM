#!/usr/bin/env python3
"""One U03 native stage or data operation; no renderer, source discovery or retry."""
import sys,argparse,json
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.pcb_workspace import configure
from tools.t01_operator_host import read
from src.stage_abi.store import digest
from src.u03_board.custody import T03,T04,export_root,width_root
from src.u02_board.adapter import RetainPathsAdapter
from src.u03_board.adapter import WidthGates
from src.pcb_data_abi.board_export import BoardDataService

from src.u03_board.export import U03DataService
from src.u03_board.selection import retain_paths


from src.stage_abi.preparation import native_operation

@native_operation
def execute(session,request,registry=None,registry_sha256=None):
    if set(request)!={'abi_version','request_id','operation'} or request['abi_version']!='pcb-u03-board/1':raise ValueError('U03_REQUEST_INVALID')
    op=request['operation']
    if op in T03:return retain_paths(session).dispatch(op)
    if op in T04:return WidthGates(width_root(session)).dispatch(op)
    if op not in ('pcb_kicad_write','pcb_kicad_verify','pcb_gerber_export','pcb_gerber_verify','pcb_export_controls'):raise ValueError('U03_OPERATION_NOT_EXPOSED')
    if digest(registry.read_bytes())!=registry_sha256:raise ValueError('U03_EXPORT_REGISTRY_CHANGED')
    return U03DataService(read(registry)).dispatch(op)


def main():
    p=argparse.ArgumentParser();p.add_argument('--session',required=True,type=Path);p.add_argument('--input',required=True,type=Path);p.add_argument('--registry',type=Path);p.add_argument('--registry-sha256');a=p.parse_args();request={}
    try:
        work=configure();session=a.session.absolute()
        if '..' in session.parts or not session.is_relative_to(work):raise ValueError('U03_LACIE_SESSION_REQUIRED')
        from src.pcb_data_abi.roi import local
        session=local(session,True);request=read(a.input)
        result=execute(session,request,a.registry,a.registry_sha256);error=None;code=0
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        result=None;error=dict(code='U03_NATIVE_REJECTED',message=str(e));code=2
    print(json.dumps(dict(abi_version='pcb-u03-board/1',request_id=request.get('request_id'),operation=request.get('operation'),status='OK'if not error else'REJECTED',result=result,error=error),sort_keys=True,allow_nan=False));return code
if __name__=='__main__':raise SystemExit(main())
