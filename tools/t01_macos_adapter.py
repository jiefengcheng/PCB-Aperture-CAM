#!/usr/bin/env python3
"""Local macOS file mailbox over the native T01 runner; no network or MCP.

Start once in the project venv; file-capable agents use the emitted descriptor.
Only the native runner imports the qualified geometry environment.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.t01_route_client import SCHEMA, REQUEST, child, decode, encode, publish, safe_id

MAX_BYTES = 65536


class MacOSAdapter:
    """Single consumer, same-user mailbox. Not a sandbox or caller authentication."""
    def __init__(self, route):
        self.route = route
        self.session = route.session
        for name in ('inbox', 'replies', 'calls'):
            (self.session / name).mkdir(mode=0o700)
        self.descriptor = dict(schema=SCHEMA, route_id=route.route_id, native=route.identity,
            platform='macOS', transport='same-user-local-files', network=False,
            inbox=str(self.session / 'inbox'), replies=str(self.session / 'replies'),
            calls=str(self.session / 'calls'), tools=route.tools(),
            contract=str(ROOT / 'contracts/t01/macos_adapter.json'),
            source_snapshot_sha256=hashlib.sha256((self.session / 'START.json').read_bytes()).hexdigest(),
            scope=route.info()['scope'],
            agent_identity='Self-reported label; not authenticated',
            interrupted_calls='Retain evidence; do not replay. Start a fresh session.')
        publish(self.session / 'agent_setup.json', encode(self.descriptor))

    def process(self, path):
        rid = safe_id(path.stem)
        call = self.session / 'calls' / rid
        try:
            call.mkdir(mode=0o700)
        except FileExistsError:
            return False  # Includes interrupted calls: never re-execute them.
        request_blob = b''
        output = error = None
        try:
            path = child(self.session, path)
            with path.open('rb') as stream:
                request_blob = stream.read(MAX_BYTES + 1)
            publish(call / 'submitted.json', request_blob)
            publish(call / 'started.json', encode(dict(at=datetime.now(timezone.utc).isoformat())))
            if len(request_blob) > MAX_BYTES:
                raise ValueError('REQUEST_TOO_LARGE')
            request = decode(request_blob)
            keys = {'schema', 'request_id', 'route_id', 'agent', 'operation', 'arguments'}
            if type(request) is not dict or set(request) != keys:
                raise ValueError('CLOSED_REQUEST_REQUIRED')
            if request['schema'] != REQUEST or request['request_id'] != rid or request['route_id'] != self.route.route_id:
                raise ValueError('REQUEST_ID_OR_ROUTE_MISMATCH')
            safe_id(request['agent'])
            if type(request['operation']) is not str or type(request['arguments']) is not dict:
                raise ValueError('TYPED_OPERATION_REQUIRED')
            output = self.route.call(request['operation'], request['arguments'],
                                     dict(name=request['agent'], adapter=SCHEMA))
            if path.read_bytes() != request_blob:
                raise ValueError('SUBMITTED_REQUEST_MUTATED')
        except Exception as e:
            error = dict(code=getattr(e, 'code', 'ADAPTER_INPUT_OR_EXECUTION_FAILED'), message=str(e))
        response = dict(schema='pcb-native-reply/1', request_id=rid, route_id=self.route.route_id,
                        request_sha256=hashlib.sha256(request_blob).hexdigest(),
                        output=output, error=error, completed_at=datetime.now(timezone.utc).isoformat())
        publish(call / 'response.json', encode(response))
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in call.iterdir() if p.is_file()}
        publish(call / 'receipt.json', encode(dict(schema='pcb-native-adapter-receipt/1', files=files)))
        publish(self.session / 'replies' / (rid + '.json'), encode(response))
        return True

    def drain(self):
        count = 0
        for path in sorted((self.session / 'inbox').glob('*.json')):
            try:
                safe_id(path.stem)
            except ValueError:
                continue  # Malformed names cannot select an execution or output path.
            count += self.process(path)
        return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--profile', choices=['setup', 'c01', 'c01-files', 'c01-render'], default='setup',
                        help='C01 exposes one audited T01 operation at a time; default remains setup only')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('This adapter is qualified for local macOS only')
    from tools.t01_native_route import NativeRoute, initialize_workspace
    session = initialize_workspace(args.session)
    session.chmod(0o700)
    if args.profile == 'c01-render':
        from tools.t01_c01_render_route import C01RenderRoute
        route = C01RenderRoute(session)
    elif args.profile == 'c01-files':
        from tools.t01_c01_files_route import C01FilesRoute
        route = C01FilesRoute(session)
    elif args.profile == 'c01':
        from tools.t01_c01_route import C01Route
        route = C01Route(session)
    else:
        route = NativeRoute(session)
    adapter = MacOSAdapter(route)
    print(json.dumps(dict(status='READY_LOCAL_MACOS_FILES', setup=str(session / 'agent_setup.json'))), flush=True)
    try:
        while True:
            adapter.drain()
            time.sleep(0.2)
    except KeyboardInterrupt:
        publish(session / 'adapter_stopped.json', encode(dict(status='STOPPED', at=datetime.now(timezone.utc).isoformat())))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
