#!/usr/bin/env python3
"""Managed export-only worker dispatched by the existing project Mac launcher."""
import argparse,os,sys,time
from pathlib import Path
from datetime import datetime,timezone
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.t01_board_export_route import initialize as initialize_workspace,ExportOnlyRoute as BoardRoute
from tools.t01_macos_adapter import MacOSAdapter
from tools.t01_route_client import encode,publish,decode
from tools.pcb_c01_operator import sha


def managed_worker(session):
    from tools.t01_crop_jobs import output,digest
    session=output(session);job=session.parent
    if decode((job/'job.json').read_bytes()).get('task_scope')!='full-board-export-only':raise ValueError('EXPORT_ONLY_MANAGED_JOB_REQUIRED')
    try:
        initialize_workspace(session);adapter=MacOSAdapter(BoardRoute(session))
        binding=dict(schema='pcb-c01-operator-binding/1',setup=str(session/'agent_setup.json'),setup_sha256=sha((session/'agent_setup.json').read_bytes()))
        path=session/'operator_binding.json';publish(path,encode(binding));publish(job/'ready.json',encode(dict(session=str(session),pid=os.getpid(),binding_sha256=digest(path.read_bytes()))))
        idle=time.monotonic()
        while not(job/'stop_requested.json').exists():
            if adapter.drain():idle=time.monotonic()
            if time.monotonic()-idle>1800:raise TimeoutError('EXPORT_RUNNER_IDLE_TIMEOUT: no automatic resume')
            time.sleep(.1)
        return 0
    except BaseException as error:
        if not(job/'worker_failed.json').exists():publish(job/'worker_failed.json',encode(dict(status='HALTED',error=str(error))))
        raise
    finally:
        if session.exists()and not(session/'adapter_stopped.json').exists():publish(session/'adapter_stopped.json',encode(dict(status='STOPPED',at=datetime.now(timezone.utc).isoformat())))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--managed-worker',action='store_true',required=True);parser.add_argument('--session',type=Path,required=True);args=parser.parse_args()
    if sys.platform!='darwin':parser.error('macOS native adapter required')
    return managed_worker(args.session)

if __name__=='__main__':raise SystemExit(main())
