#!/usr/bin/env python3
"""One U02 native stage or data operation; no renderer, source discovery or retry."""
import sys,argparse,json
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.pcb_workspace import configure
from tools.t01_operator_host import read
from src.stage_abi.store import digest
from src.u02_board.custody import T03,export_root
from src.u02_board.adapter import RetainPathsAdapter
from src.pcb_data_abi.board_export import BoardDataService

class U02DataService(BoardDataService):
    def predecessor_root(self,host):return export_root(host)


def execute(session,request,registry=None,registry_sha256=None):
    if set(request)!={'abi_version','request_id','operation'} or request['abi_version']!='pcb-u02-board/1':raise ValueError('U02_REQUEST_INVALID')
    op=request['operation']
    if op in T03:return RetainPathsAdapter(session).dispatch(op)
    if op not in ('pcb_kicad_write','pcb_kicad_verify','pcb_gerber_export','pcb_gerber_verify','pcb_export_controls'):raise ValueError('U02_OPERATION_NOT_EXPOSED')
    if digest(registry.read_bytes())!=registry_sha256:raise ValueError('U02_EXPORT_REGISTRY_CHANGED')
    return U02DataService(read(registry)).dispatch(op)


def main():
    p=argparse.ArgumentParser();p.add_argument('--session',required=True,type=Path);p.add_argument('--input',required=True,type=Path);p.add_argument('--registry',type=Path);p.add_argument('--registry-sha256');a=p.parse_args();request={}
    try:
        work=configure();session=a.session.absolute()
        if '..' in session.parts or not session.is_relative_to(work):raise ValueError('U02_LACIE_SESSION_REQUIRED')
        from src.pcb_data_abi.roi import local
        session=local(session,True);request=read(a.input)
        result=execute(session,request,a.registry,a.registry_sha256);error=None;code=0
    except Exception as e:result=None;error=dict(code='U02_NATIVE_REJECTED',message=str(e));code=2
    print(json.dumps(dict(abi_version='pcb-u02-board/1',request_id=request.get('request_id'),operation=request.get('operation'),status='OK'if not error else'REJECTED',result=result,error=error),sort_keys=True,allow_nan=False));return code
if __name__=='__main__':raise SystemExit(main())
