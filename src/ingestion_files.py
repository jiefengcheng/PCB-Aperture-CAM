"""Checkout-contained file bindings shared by ingestion producers and verifiers."""
import hashlib
import json
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def local(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Path escapes checkout: ' + str(relative))
    return path


def verify(root, bindings):
    for binding in bindings:
        path = local(root, binding['path'])
        if not path.is_file():
            raise ValueError('MISSING: ' + binding['path'])
        if sha(path) != binding['sha256']:
            raise ValueError('STALE: ' + binding['path'])


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')
