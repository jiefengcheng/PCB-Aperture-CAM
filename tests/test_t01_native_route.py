"""Native custody and macOS file transport controls; no geometry construction."""
import hashlib
import json
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace
import pytest
from tools import t01_native_route as core
from tools.t01_macos_adapter import MacOSAdapter
from tools.t01_route_client import Client, decode, encode, publish, verify_files


@pytest.fixture
def route(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'check', lambda session: None)
    r = core.NativeRoute.__new__(core.NativeRoute)
    r.session = tmp_path
    r.identity = dict(python='test-native', implementation='pinned')
    r.route_id = 'route-test'
    r.lock = threading.RLock()
    r.receipt_hashes = {}
    r.cap = dict(registry_path='fixed-registry', registry_sha256='pinned-digest', store_path='fixed-store')
    r.runner = lambda *a, **k: SimpleNamespace(stdout=b'{"status":"OK"}', stderr=b'', returncode=0)
    (tmp_path / 'START.json').write_text('{}')
    (tmp_path / 'attempts').mkdir()
    return r


def args(r, attempt='probe'):
    return dict(route_id=r.route_id, attempt_id=attempt)


def describe(r, attempt='probe'):
    return r.call('t01_describe', args(r, attempt), dict(name='test-agent'))


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


def test_duplicate_attempt_rejected_without_overwriting_bytes(route):
    first = describe(route)
    before = hashes(route.session / 'attempts')
    with pytest.raises(core.RouteError, match='Never overwrite'):
        describe(route)
    assert hashes(route.session / 'attempts') == before
    assert route.call('native_route.verify_receipt', args(route), {})['receipt_sha256'] == first['receipt_sha256']


@pytest.mark.parametrize('file', ['describe/stdout.json', 'receipt.json', 'unexpected.txt'])
def test_tampered_response_receipt_and_file_set_detected(route, file):
    result = describe(route)
    (route.session / 'attempts/probe' / file).write_bytes(b'{}')
    with pytest.raises(core.RouteError):
        route.call('native_route.verify_receipt', args(route), {})
    with pytest.raises(ValueError):
        verify_files(Path(result['receipt_path']), result['receipt_sha256'])


def test_failed_native_launch_retained_across_later_success(route):
    def fail(*a, **k):
        raise FileNotFoundError('missing qualified interpreter')
    route.runner = fail
    failed = describe(route, 'failed')
    assert failed['error']['code'] == 'NATIVE_CHANNEL_UNAVAILABLE'
    before = hashes(route.session / 'attempts/failed')
    route.runner = lambda *a, **k: SimpleNamespace(stdout=b'{"status":"OK"}', stderr=b'', returncode=0)
    assert describe(route, 'success')['error'] is None
    assert hashes(route.session / 'attempts/failed') == before
    meta = json.loads((route.session / 'attempts/failed/describe/execution.json').read_bytes())
    assert meta['launched'] is False and meta['returncode'] is None


def test_timeout_keeps_actual_partial_stdout_stderr(route):
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired('native', 120, output=b'partial', stderr=b'error')
    route.runner = timeout
    result = describe(route)
    assert result['error']['code'] == 'NATIVE_TIMEOUT'
    path = route.session / 'attempts/probe/describe'
    assert (path / 'stdout.json').read_bytes() == b'partial'
    assert (path / 'stderr.log').read_bytes() == b'error'
    route.call('native_route.verify_receipt', args(route), {})


def test_mutated_native_request_cannot_pass(route):
    def mutate(argv, **kwargs):
        Path(argv[argv.index('--input') + 1]).write_bytes(b'{}')
        return SimpleNamespace(stdout=b'{"status":"OK"}', stderr=b'', returncode=0)
    route.runner = mutate
    assert describe(route)['error']['code'] == 'OPERATOR_REQUEST_MUTATED'


def test_changed_registry_or_runtime_fails_before_native_invocation(route, monkeypatch):
    def changed(session):
        raise ValueError('PROTECTED_EVIDENCE_OR_RUNTIME_CHANGED')
    monkeypatch.setattr(core, 'check', changed)
    route.runner = lambda *a, **k: pytest.fail('Must not invoke with a failed binding check')
    result = describe(route)
    assert result['error']['message'] == 'PROTECTED_EVIDENCE_OR_RUNTIME_CHANGED'
    assert not (route.session / 'attempts/probe/describe').exists()


@pytest.mark.parametrize('tool', ['t02_run', 't01_run', 'native_route.shell'])
def test_no_geometry_other_stage_or_shell_surface(route, tool):
    with pytest.raises(core.RouteError, match=tool):
        route.call(tool, args(route), {})
    assert not list((route.session / 'attempts').iterdir())


@pytest.mark.parametrize('attempt', ['../escape', None, '', '/tmp/escape'])
def test_unsafe_attempt_rejected(route, attempt):
    with pytest.raises(core.RouteError):
        route.call('t01_describe', args(route, attempt), {})


def test_mac_mailbox_real_dispatch_and_receipt_correlation(route):
    adapter = MacOSAdapter(route)
    client = Client(route.session / 'agent_setup.json', 'LocalCode')
    rid = client.submit('t01_describe', args(route), 'first')
    assert adapter.drain() == 1
    result = client.receive(rid)
    verify_files(Path(result['receipt_path']), result['receipt_sha256'])
    assert result['result']['status'] == 'PASS_NATIVE_DESCRIBE_ONLY'
    before = hashes(route.session)
    assert adapter.drain() == 0
    assert hashes(route.session) == before
    with pytest.raises(FileExistsError):
        client.submit('t01_describe', args(route), 'first')
    assert hashes(route.session) == before


def test_second_agent_same_descriptor_needs_no_custom_environment(route):
    adapter = MacOSAdapter(route)
    for agent in ('LocalCode', 'another-agent'):
        client = Client(route.session / 'agent_setup.json', agent)
        rid = client.submit('native_route.info', {})
        assert adapter.drain() == 1
        assert client.receive(rid)['native'] == route.identity


def test_interrupted_claim_is_not_automatically_replayed(route):
    adapter = MacOSAdapter(route)
    client = Client(route.session / 'agent_setup.json', 'LocalCode')
    rid = client.submit('t01_describe', args(route))
    (route.session / 'calls' / rid).mkdir()
    assert adapter.drain() == 0
    assert not (route.session / 'replies' / (rid + '.json')).exists()
    assert not list((route.session / 'attempts').iterdir())


def test_mailbox_rejects_duplicate_keys_and_retains_raw_failure(route):
    adapter = MacOSAdapter(route)
    blob = b'{"schema":"pcb-native-call/1","schema":"bad"}'
    publish(route.session / 'inbox/malformed.json', blob)
    assert adapter.drain() == 1
    reply = decode((route.session / 'replies/malformed.json').read_bytes())
    assert 'Duplicate JSON key' in reply['error']['message']
    assert (route.session / 'calls/malformed/submitted.json').read_bytes() == blob
    assert not list((route.session / 'attempts').iterdir())


def test_mismatched_route_is_not_executed(route):
    adapter = MacOSAdapter(route)
    client = Client(route.session / 'agent_setup.json', 'LocalCode')
    rid = client.submit('t01_describe', args(route))
    p = route.session / 'inbox' / (rid + '.json')
    value = decode(p.read_bytes()); value['route_id'] = 'other-route'; p.write_bytes(encode(value))
    adapter.drain()
    with pytest.raises(ValueError, match='REQUEST_ID_OR_ROUTE_MISMATCH'):
        client.receive(rid)
    assert not list((route.session / 'attempts').iterdir())


def test_client_detects_later_mailbox_mutation(route):
    adapter = MacOSAdapter(route)
    client = Client(route.session / 'agent_setup.json', 'LocalCode')
    rid = client.submit('native_route.info', {})
    adapter.drain()
    (route.session / 'inbox' / (rid + '.json')).write_bytes(b'{}')
    with pytest.raises(ValueError, match='Submitted request changed'):
        client.receive(rid)


def test_missing_runner_reports_incomplete_and_keeps_request(route):
    MacOSAdapter(route)
    client = Client(route.session / 'agent_setup.json', 'LocalCode')
    with pytest.raises(TimeoutError, match='NATIVE_CHANNEL_UNAVAILABLE_OR_INCOMPLETE'):
        client.call('native_route.info', {}, timeout=0.01)
    assert len(list((route.session / 'inbox').glob('*.json'))) == 1


def test_symlink_mailbox_not_followed(route, tmp_path):
    adapter = MacOSAdapter(route)
    target = route.session / 'outside.json'; target.write_bytes(b'{}')
    (route.session / 'inbox/link.json').symlink_to(target)
    assert adapter.drain() == 1
    reply = decode((route.session / 'replies/link.json').read_bytes())
    assert 'Symlink adapter path' in reply['error']['message']
    assert target.read_bytes() == b'{}'
