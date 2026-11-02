#!/usr/bin/env python3
"""Project-native foreground launcher; emits a reusable ordinary-English route."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import os
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.t01_native_route import initialize_workspace
from tools.t01_c01_render_route import C01RenderRoute
from tools.t01_macos_adapter import MacOSAdapter
from tools.pcb_c01_operator import ACTIVE, scoped, sha
from tools.t01_route_client import encode, publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path)
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('macOS native adapter required')
    default = ROOT/'out/operator_sessions/c01_render'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    session = initialize_workspace(args.session or default)
    adapter = MacOSAdapter(C01RenderRoute(session))
    scoped(ACTIVE); ACTIVE.parent.mkdir(parents=True, exist_ok=True)
    if ACTIVE.exists():
        history = ACTIVE.parent/'history'; history.mkdir(exist_ok=True)
        publish(history/(uuid.uuid4().hex+'.json'), ACTIVE.read_bytes())
    binding = dict(schema='pcb-c01-operator-binding/1', setup=str(session/'agent_setup.json'),
                   setup_sha256=sha((session/'agent_setup.json').read_bytes()))
    publish(session/'operator_binding.json', encode(binding))
    temporary = ACTIVE.with_name('.current-'+uuid.uuid4().hex)
    publish(temporary, encode(binding)); os.replace(temporary, ACTIVE)
    print(encode(dict(status='READY_ORDINARY_ENGLISH_C01_RENDER', session=str(session))).decode(), flush=True)
    try:
        while True:
            adapter.drain(); time.sleep(.2)
    except KeyboardInterrupt:
        publish(session/'adapter_stopped.json', encode(dict(status='STOPPED', at=datetime.now(timezone.utc).isoformat())))


if __name__ == '__main__':
    main()
