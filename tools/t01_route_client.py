#!/usr/bin/env python3
"""macOS local-file adapter client. Standard library only; no native kernel imports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

SCHEMA = 'pcb-macos-file-adapter/1'
REQUEST = 'pcb-native-call/1'
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def decode(blob):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Non-finite JSON value: ' + value)
    return json.loads(blob, object_pairs_hook=pairs, parse_constant=invalid)


def publish(path, blob):
    """Publish complete bytes without replacing an existing name, on one filesystem."""
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def safe_id(value):
    if type(value) is not str or not ID.fullmatch(value):
        raise ValueError('Safe unique ID required')
    return value


def child(root, path):
    path = Path(path)
    # Reject symlinks in every component, even those resolving inside the root.
    if not path.is_absolute() or not path.is_relative_to(root):
        raise ValueError('Adapter path outside session')
    current = root
    if root.is_symlink():
        raise ValueError('Symlink session')
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlink adapter path')
    return path


def verify_files(receipt_path, expected):
    receipt_path = Path(receipt_path)
    root = receipt_path.parent
    blob = child(root, receipt_path).read_bytes()
    if hashlib.sha256(blob).hexdigest() != expected:
        raise ValueError('Receipt digest mismatch')
    receipt = decode(blob)
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p != receipt_path}
    if actual != set(receipt['files']):
        raise ValueError('Changed attempt file set')
    for name, expected_hash in receipt['files'].items():
        path = child(root, root / name)
        if '..' in Path(name).parts or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError('Actual attempt file mismatch: ' + name)
    return receipt


class Client:
    def __init__(self, setup_path, agent):
        setup_path = Path(setup_path).absolute()
        self.root = setup_path.parent
        self.setup = decode(child(self.root, setup_path).read_bytes())
        if self.setup['schema'] != SCHEMA:
            raise ValueError('Unsupported adapter contract')
        self.agent = safe_id(agent)
        self.inbox = child(self.root, self.setup['inbox'])
        self.replies = child(self.root, self.setup['replies'])

    def submit(self, name, arguments, request_id=None):
        rid = safe_id(request_id or 'request-' + uuid.uuid4().hex)
        request = dict(schema=REQUEST, request_id=rid, route_id=self.setup['route_id'],
                       agent=self.agent, operation=name, arguments=arguments)
        publish(self.inbox / (rid + '.json'), encode(request))
        return rid

    def receive(self, rid):
        safe_id(rid)
        response = decode(child(self.root, self.replies / (rid + '.json')).read_bytes())
        if response['request_id'] != rid or response['route_id'] != self.setup['route_id']:
            raise ValueError('Response correlation mismatch')
        request_blob = child(self.root, self.inbox / (rid + '.json')).read_bytes()
        if response['request_sha256'] != hashlib.sha256(request_blob).hexdigest():
            raise ValueError('Submitted request changed')
        if response.get('error'):
            raise ValueError(json.dumps(response['error'], sort_keys=True))
        return response['output']

    def call(self, name, arguments, *, timeout=180):
        rid = self.submit(name, arguments)
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if (self.replies / (rid + '.json')).exists():
                return self.receive(rid)
            time.sleep(0.1)
        raise TimeoutError('NATIVE_CHANNEL_UNAVAILABLE_OR_INCOMPLETE: retained request ' + rid)

    def acquire(self, attempt):
        safe_id(attempt)
        info = self.call('native_route.info', {})
        if info['native'] != self.setup['native']:
            raise ValueError('Native identity mismatch')
        arguments = dict(route_id=self.setup['route_id'], attempt_id=attempt)
        result = self.call('native_route.conformance', arguments)
        if result.get('error') or result['result']['status'] != 'PASS_NATIVE_SETUP_CONFORMANCE':
            raise ValueError('Native setup failed: ' + json.dumps(result.get('error')))
        if result['native'] != self.setup['native']:
            raise ValueError('Native identity mismatch')
        verified = self.call('native_route.verify_receipt', arguments)
        if verified['receipt_sha256'] != result['receipt_sha256']:
            raise ValueError('Receipt digest mismatch')
        path = child(self.root, result['receipt_path'])
        verify_files(path, result['receipt_sha256'])
        return dict(status='PASS_NATIVE_ROUTE_SETUP_ONLY', agent=self.agent,
                    route_id=self.setup['route_id'], native=result['native'],
                    proof=result['result'], receipt_path=str(path),
                    receipt_sha256=result['receipt_sha256'],
                    client_file_integrity='PASS', geometry='NOT_RUN',
                    operator_autonomy='NOT_QUALIFIED_BY_SETUP')

    def invoke(self, operation, attempt, audit=None):
        if operation == 'native_route.info':
            return self.call(operation, {})
        safe_id(attempt)
        arguments = dict(route_id=self.setup['route_id'], attempt_id=attempt)
        if audit is not None:
            arguments['audit'] = audit
        output = self.call(operation, arguments)
        if output.get('error'):
            return output
        if output['native'] != self.setup['native']:
            raise ValueError('Native identity mismatch')
        if 'receipt_path' in output:
            verified = self.call('native_route.verify_receipt', dict(route_id=self.setup['route_id'], attempt_id=attempt))
            if verified['receipt_sha256'] != output['receipt_sha256']:
                raise ValueError('Native receipt digest mismatch')
            verify_files(child(self.root, output['receipt_path']), output['receipt_sha256'])
        return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', type=Path, required=True)
    parser.add_argument('--agent', required=True)
    parser.add_argument('--attempt', default=None)
    parser.add_argument('--operation', default=None, help='One exposed operation, never a workflow loop')
    parser.add_argument('--audit-file', type=Path, default=None)
    args = parser.parse_args()
    client = Client(args.setup, args.agent)
    if args.operation:
        audit = decode(child(client.root, args.audit_file.absolute()).read_bytes()) if args.audit_file else None
        if (args.operation == 'native_route.audit') != (audit is not None):
            parser.error('native_route.audit requires --audit-file; other operations do not accept it')
        result = client.invoke(args.operation, args.attempt, audit)
    else:
        if args.audit_file:
            parser.error('--audit-file requires --operation native_route.audit')
        # Bound profiles deliberately exclude setup conformance. Their standard
        # entry point discovers current state rather than calling an absent tool.
        if 'native_route.conformance' not in {t['name'] for t in client.setup['tools']}:
            result = client.invoke('native_route.info', None)
            if result['native'] != client.setup['native']:
                raise ValueError('Native identity mismatch')
        else:
            result = client.acquire(args.attempt or 'setup-' + uuid.uuid4().hex)
    print(json.dumps(result, sort_keys=True))
    return 2 if result.get('error') else 0


if __name__ == '__main__':
    raise SystemExit(main())
