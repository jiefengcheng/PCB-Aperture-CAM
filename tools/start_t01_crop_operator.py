#!/usr/bin/env python3
"""Prepare a fresh crop-driven native route and publish its project-local binding."""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import sys
import time
import uuid
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.t01_crop_route import initialize as initialize_workspace
from tools.t01_crop_route import CropRoute
from tools.t01_macos_adapter import MacOSAdapter
from tools.pcb_t01_operator import ACTIVE
from tools.pcb_c01_operator import scoped,sha
from tools.t01_route_client import encode,publish

def main():
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path);p.add_argument('--managed-worker',action='store_true');a=p.parse_args()
    if sys.platform!='darwin':p.error('macOS native adapter required')
    if a.managed_worker:
        return managed_worker(a.session)
    default=ROOT/'out/operator_sessions/t01_crop'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    session=initialize_workspace(a.session or default)
    adapter=MacOSAdapter(CropRoute(session))
    scoped(ACTIVE);ACTIVE.parent.mkdir(parents=True,exist_ok=True)
    if ACTIVE.exists():
        history=ACTIVE.parent/'history';history.mkdir(exist_ok=True)
        publish(history/(uuid.uuid4().hex+'.json'),ACTIVE.read_bytes())
    binding=dict(schema='pcb-c01-operator-binding/1',setup=str(session/'agent_setup.json'),setup_sha256=sha((session/'agent_setup.json').read_bytes()))
    publish(session/'operator_binding.json',encode(binding))
    temp=ACTIVE.with_name('.current-'+uuid.uuid4().hex);publish(temp,encode(binding));os.replace(temp,ACTIVE)
    print(encode(dict(status='READY_ORDINARY_ENGLISH_CROP_T01',session=str(session))).decode(),flush=True)
    try:
        while True:adapter.drain();time.sleep(.2)
    except KeyboardInterrupt:
        publish(session/'adapter_stopped.json',encode(dict(status='STOPPED',at=datetime.now(timezone.utc).isoformat())))


def managed_worker(session):
    """One automatically launched job; never restarts or replays an old route."""
    # Existing session launchers call this script from disk for each new job.
    # Dispatch the explicit whole-board scope without replacing the Mac bridge.
    from tools.t01_route_client import decode
    record=decode((Path(session).parent/'job.json').read_bytes())
    if record.get('task_scope')=='full-board-export-only':
        from tools.start_t01_board_export_operator import managed_worker as export_worker
        return export_worker(session)
    if record.get('task_scope')=='full-board':
        from tools.start_t01_board_operator import managed_worker as board_worker
        return board_worker(session)
    if record.get('task_scope') is not None:
        raise ValueError('UNSUPPORTED_MANAGED_TASK_SCOPE')
    from tools.t01_crop_jobs import output, digest
    session=output(session);job=session.parent;adapter=None
    try:
        initialize_workspace(session)
        adapter=MacOSAdapter(CropRoute(session))
        binding=dict(schema='pcb-c01-operator-binding/1',setup=str(session/'agent_setup.json'),setup_sha256=sha((session/'agent_setup.json').read_bytes()))
        path=session/'operator_binding.json';publish(path,encode(binding))
        publish(job/'ready.json',encode(dict(session=str(session),pid=os.getpid(),binding_sha256=digest(path.read_bytes()))))
        idle=time.monotonic()
        while not (job/'stop_requested.json').exists():
            if adapter.drain():idle=time.monotonic()
            if time.monotonic()-idle>1800:
                raise TimeoutError('CROP_RUNNER_IDLE_TIMEOUT: no automatic resume')
            time.sleep(.1)
        return 0
    except BaseException as e:
        if not (job/'worker_failed.json').exists():
            publish(job/'worker_failed.json',encode(dict(status='HALTED',error=str(e))))
        raise
    finally:
        if session.exists() and not (session/'adapter_stopped.json').exists():
            publish(session/'adapter_stopped.json',encode(dict(status='STOPPED',at=datetime.now(timezone.utc).isoformat())))

if __name__=='__main__':main()
