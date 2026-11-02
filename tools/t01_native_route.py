#!/usr/bin/env python3
"""Transport-independent native T01 runner with pinned runtime and attempt receipts.

Setup only: compile controls and describe, never construction or later stages.
System-specific adapters call NativeRoute.call; this module opens no listener.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.stage_abi.store import ArtifactStore, canonical, digest
from src.stage_abi.service import runtime_fingerprint
from src.crop_circle_sources import verify_assets
from src.trace_first_pipeline import frozen_fingerprint
from src.t01_abi.adapter import InteractionAdapter
from tools.t01_operator_host import HANDOFF, check, prepare, register, read, fresh
import shapely

ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


class RouteError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def closed(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise RouteError('CLOSED_INPUT_REQUIRED', 'Unexpected or missing fields')


def native_identity():
    return dict(python=sys.version.split()[0], interpreter=sys.executable,
                prefix=sys.prefix, shapely=shapely.__version__,
                geos=shapely.geos_version_string,
                implementation=InteractionAdapter().describe()['implementation'],
                shared_runtime=runtime_fingerprint())


def require_native():
    identity = native_identity()
    if Path(sys.prefix).resolve() != (ROOT / '.venv').resolve():
        raise RouteError('UNQUALIFIED_INTERPRETER', 'Start with project .venv/bin/python')
    expected = dict(python='3.14.5', shapely='2.1.2', geos='3.13.1')
    if any(identity[k] != v for k, v in expected.items()):
        raise RouteError('NATIVE_VERSION_MISMATCH', str(expected))
    return identity


def producer_files():
    return [*sorted((ROOT / 'src/t01_abi').glob('*.py')),
            *sorted((ROOT / 'src/c01_pipeline').glob('*.py')),
            *sorted((ROOT / 'src/pcb_data_abi').glob('*.py')),
            *sorted((ROOT / 'src/render_abi').glob('*.py')),
            *sorted((ROOT / 'contracts/render').glob('*.json')),
            *sorted((ROOT / 'contracts/operator').glob('*.json')),
            ROOT / 'AGENTS.md',
            *[ROOT / 'contracts/t01' / n for n in
              ('c01.binding.json', 'c01.english.txt', 'policy.schema.json',
               'request.schema.json', 'response.schema.json', 'compile_gate.json',
               'macos_adapter.json', 'c01_route.json', 'c01_files.json')],
            *[ROOT / 'tools' / n for n in
              ('t01_agent_abi.py', 't01_operator_host.py',
               't01_native_route.py', 't01_route_client.py', 't01_macos_adapter.py',
               't01_c01_route.py', 'pcb_data_abi.py', 't01_c01_files_route.py',
               'pcb_render_abi.py', 't01_c01_render_route.py',
               'pcb_c01_operator.py', 'start_c01_render_operator.py',
               'pcb_c01_full_operator.py', 'start_c01_full_operator.py',
               't01_c01_full_route.py', 'pcb_c01_reproduction_check.py')]]


def initialize_workspace(session):
    session = session.resolve()
    if not session.is_relative_to(ROOT / 'out') or session.exists():
        raise RouteError('FRESH_PROJECT_OUTPUT_REQUIRED', str(session))
    identity = require_native()
    session.mkdir(parents=True)
    start = dict(status='NATIVE_ROUTE_SOURCE_ONLY_SETUP', assets=verify_assets(),
                 protected_freezes=[frozen_fingerprint(ROOT, e) for e in
                                    read(HANDOFF / 'PROTECTED_FREEZES.json')],
                 T01_delivery_files={str(p.relative_to(ROOT)): digest(p.read_bytes())
                                     for p in producer_files()},
                 runtime_fingerprint=identity['shared_runtime'],
                 T01_implementation=identity['implementation'])
    fresh(session / 'START.json', start)
    prepare(session)
    (session / 'attempts').mkdir()
    return session


def verify_attempt(path, expected_sha256=None):
    rp = path / 'receipt.json'
    if rp.is_symlink() or not rp.is_file() or (expected_sha256 and digest(rp.read_bytes()) != expected_sha256):
        raise RouteError('RECEIPT_HASH_MISMATCH', 'receipt.json')
    receipt = read(rp)
    actual = {str(p.relative_to(path)) for p in path.rglob('*') if p.is_file() and p != rp}
    if actual != set(receipt['files']):
        raise RouteError('RECEIPT_HASH_MISMATCH', 'Changed attempt file set')
    for name, expected in receipt['files'].items():
        p = path / name
        if not p.resolve().is_relative_to(path.resolve()) or p.is_symlink() or not p.is_file() or digest(p.read_bytes()) != expected:
            raise RouteError('RECEIPT_HASH_MISMATCH', name)
    return dict(status='PASS_RECEIPT_INTEGRITY', receipt_sha256=digest((path / 'receipt.json').read_bytes()),
                file_count=len(receipt['files']))


class NativeRoute:
    def __init__(self, session, *, runner=subprocess.run):
        self.session = session.resolve()
        self.identity = require_native()
        self.route_id = 'route-' + uuid.uuid4().hex
        self.lock = threading.RLock()
        self.receipt_hashes = {}
        self.runner = runner
        self.cap = read(self.session / 'capsule_00.json')
        self.store = ArtifactStore(Path(self.cap['store_path']))
        original = (ROOT / 'contracts/t01/c01.english.txt').read_bytes()
        altered = original.replace(b'hard gap 0.020 mm', b'hard gap 0.001 mm')
        if original == altered:
            raise RouteError('NEGATIVE_OPERAND_NOT_CHANGED', 'R14 control')
        self.negative = self.store.put('english-spec', altered)

    def tools(self):
        def schema():
            props = dict(route_id=dict(type='string'), attempt_id=dict(type='string', pattern=ID.pattern))
            return dict(type='object', additionalProperties=False,
                        properties=props, required=list(props))
        return [dict(name='native_route.info', description='Native identity and setup-only scope; no construction authority.',
                     input_schema=dict(type='object', additionalProperties=False)),
                dict(name='native_route.conformance', description='Standard native describe/compile/R14-negative checks with immutable per-attempt evidence. No geometry construction.',
                     input_schema=schema()),
                dict(name='native_route.verify_receipt', description='Recheck native attempt file hashes; cannot modify them.',
                     input_schema=schema()),
                dict(name='t01_describe', description='Actual read-only T01 ABI describe using the pinned native interpreter.',
                     input_schema=schema())]

    def info(self):
        return dict(route_id=self.route_id, native=self.identity,
                    scope='C01 source-bound setup only; no run/verify/construction or T02-T05',
                    setup_status='CONFORMANCE_REQUIRED',
                    source_snapshot_sha256=digest((self.session / 'START.json').read_bytes()))

    def _request(self, verb, payload, rid):
        return dict(abi_version='stage-agent-abi/1.0', request_id=rid, operation='t01_' + verb,
                    profile_id=None, scene_ref=None, policy_ref=None, plan_ref=None,
                    authorization_ref=None, idempotency_key=None, payload=payload)

    def _invoke(self, directory, name, request):
        directory.mkdir()
        ip = directory / 'request.json'
        ip.write_bytes(canonical(request))
        before = digest(ip.read_bytes())
        fresh(directory / 'started.json', dict(operation=name, at=datetime.now(timezone.utc).isoformat()))
        argv = self._argv(ip)
        try:
            completed = self.runner(argv, cwd=ROOT, capture_output=True, timeout=120)
        except subprocess.TimeoutExpired as e:
            (directory / 'stdout.json').write_bytes(e.stdout or b'')
            (directory / 'stderr.log').write_bytes(e.stderr or b'')
            fresh(directory / 'execution.json', dict(argv=argv, returncode=None, timed_out=True,
                  request_sha256=before, registry_sha256=self.cap['registry_sha256']))
            raise RouteError('NATIVE_TIMEOUT', 'Partial native stdout/stderr preserved') from e
        except OSError as e:
            (directory / 'stdout.json').write_bytes(b'')
            (directory / 'stderr.log').write_bytes(b'')
            fresh(directory / 'execution.json', dict(argv=argv, returncode=None,
                  launched=False, launch_error=str(e), request_sha256=before,
                  registry_sha256=self.cap['registry_sha256']))
            raise RouteError('NATIVE_CHANNEL_UNAVAILABLE', str(e)) from e
        (directory / 'stdout.json').write_bytes(completed.stdout)
        (directory / 'stderr.log').write_bytes(completed.stderr)
        fresh(directory / 'execution.json', dict(argv=argv, returncode=completed.returncode,
              request_sha256=before, response_sha256=digest(completed.stdout),
              stderr_sha256=digest(completed.stderr), registry_sha256=self.cap['registry_sha256']))
        fresh(directory / 'completed.json', dict(operation=name, at=datetime.now(timezone.utc).isoformat(), returncode=completed.returncode))
        if digest(ip.read_bytes()) != before:
            raise RouteError('OPERATOR_REQUEST_MUTATED', name)
        try:
            response = json.loads(completed.stdout)
        except ValueError as e:
            raise RouteError('NATIVE_RESPONSE_INVALID', str(e)) from e
        return response, completed.returncode

    def _argv(self, input_path):
        return [sys.executable, '-B', str(ROOT / 'tools/t01_agent_abi.py'),
                '--registry', self.cap['registry_path'], '--registry-sha256', self.cap['registry_sha256'],
                '--store', self.cap['store_path'], '--input', str(input_path)]

    def _attempt(self, name, args, caller):
        closed(args, {'route_id', 'attempt_id'})
        if args['route_id'] != self.route_id or type(args['attempt_id']) is not str or not ID.fullmatch(args['attempt_id']):
            raise RouteError('ROUTE_OR_ATTEMPT_INVALID', 'Explicit current route and safe attempt ID required')
        path = self.session / 'attempts' / args['attempt_id']
        try:
            path.mkdir()
        except FileExistsError as e:
            raise RouteError('ATTEMPT_EXISTS', 'Never overwrite/reuse a previous attempt ID') from e
        fresh(path / 'invocation.json', dict(tool=name, arguments=args, caller=caller,
                                            started_at=datetime.now(timezone.utc).isoformat()))
        result = None
        error = None
        try:
            check(self.session)
            if name == 't01_describe':
                response, code = self._invoke(path / 'describe', 'describe',
                    self._request('describe', dict(requested_contract_version='stage-agent-abi/1.0'), args['attempt_id']))
                if code != 0 or response['status'] != 'OK':
                    raise RouteError('DESCRIBE_NOT_ESTABLISHED', str(response.get('error')))
                result = dict(status='PASS_NATIVE_DESCRIBE_ONLY', response=response)
            else:
                good, gc = self._invoke(path / 'positive', 'positive', self._request('compile',
                    dict(english_ref=self.cap['english_ref'], binding_ref=self.cap['binding_ref']), args['attempt_id'] + '-positive'))
                bad, bc = self._invoke(path / 'negative', 'negative', self._request('compile',
                    dict(english_ref=self.negative, binding_ref=self.cap['binding_ref']), args['attempt_id'] + '-negative'))
                if gc != 0 or good['status'] != 'OK' or good['result']['construction_status'] != 'NOT_RUN':
                    raise RouteError('POSITIVE_CONTROL_FAILED', str(good.get('error')))
                policy = good['result']['policy']
                expected = read(ROOT / 'contracts/t01/compile_gate.json')['expected']
                if good['result']['policy_ref']['sha256'] != expected['policy_sha256_for_c01_binding'] or len(policy['clause_trace']) != 15 or policy['binding_ref'] != self.cap['binding_ref']:
                    raise RouteError('POLICY_BINDING_FAILED', '15 clauses/source binding')
                if bc != 2 or bad['status'] != 'REJECTED' or bad['result'] is not None or bad['error']['code'] != 'T01_ENGLISH_UNSUPPORTED' or not bad['error']['message'].startswith('R14:'):
                    raise RouteError('SEMANTIC_NEGATIVE_FAILED', str(bad))
                if self.cap['capsule_revision'] == 0:
                    self.cap = register(self.session, path / 'positive/stdout.json')
                describe, dc = self._invoke(path / 'describe', 'describe',
                    self._request('describe', dict(requested_contract_version='stage-agent-abi/1.0'), args['attempt_id'] + '-describe'))
                support = describe.get('result', {}).get('profiles', {}).get('c01-interaction-v1', {}).get('support', {})
                if dc != 0 or support.get('implementation') != self.identity['implementation']:
                    raise RouteError('NATIVE_IMPLEMENTATION_MISMATCH', 'Registered T01 adapter')
                result = dict(status='PASS_NATIVE_SETUP_CONFORMANCE', positive_exit=gc,
                              negative_exit=bc, negative_code=bad['error']['code'],
                              policy_ref=good['result']['policy_ref'], clauses=15,
                              describe_implementation=support['implementation'],
                              geometry='NOT_RUN', operator_autonomy='NOT_QUALIFIED_BY_SETUP')
            check(self.session)
        except Exception as e:
            error = dict(code=getattr(e, 'code', 'NATIVE_SETUP_FAILURE'), message=str(e))
        fresh(path / 'result.json', dict(result=result, error=error))
        files = {str(p.relative_to(path)): digest(p.read_bytes())
                 for p in sorted(path.rglob('*')) if p.is_file()}
        receipt = dict(schema='pcb-native-attempt-receipt/1', attempt_id=args['attempt_id'],
                       tool=name, caller=caller, native=self.identity, files=files,
                       status='FAIL' if error else result['status'],
                       completed_at=datetime.now(timezone.utc).isoformat(),
                       authority='Setup only; no geometry or owner/independent/manufacturing acceptance')
        fresh(path / 'receipt.json', receipt)
        integrity = verify_attempt(path)
        self.receipt_hashes[args['attempt_id']] = integrity['receipt_sha256']
        output = dict(result=result, error=error, receipt_path=str(path / 'receipt.json'),
                      receipt_sha256=integrity['receipt_sha256'], native=self.identity,
                      route_id=self.route_id)
        return output

    def call(self, name, args, caller):
        with self.lock:
            if name == 'native_route.info':
                closed(args, set())
                return self.info()
            if name == 'native_route.verify_receipt':
                closed(args, {'route_id', 'attempt_id'})
                if args['route_id'] != self.route_id or type(args['attempt_id']) is not str or not ID.fullmatch(args['attempt_id']):
                    raise RouteError('ROUTE_OR_ATTEMPT_INVALID', 'route/attempt')
                if args['attempt_id'] not in self.receipt_hashes:
                    raise RouteError('ATTEMPT_NOT_CURRENT', args['attempt_id'])
                return verify_attempt(self.session / 'attempts' / args['attempt_id'],
                                      self.receipt_hashes[args['attempt_id']])
            if name not in {'native_route.conformance', 't01_describe'}:
                raise RouteError('TOOL_NOT_EXPOSED', name)
            return self._attempt(name, args, caller)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--attempt', default='native-setup')
    args = parser.parse_args()
    session = initialize_workspace(args.session)
    route = NativeRoute(session)
    output = route.call('native_route.conformance',
                        dict(route_id=route.route_id, attempt_id=args.attempt),
                        dict(name='native-local-runner', version='1.0'))
    print(json.dumps(output, sort_keys=True), flush=True)
    return 2 if output.get('error') else 0


if __name__ == '__main__':
    raise SystemExit(main())
