"""Exact approved source revisions; immutable treatment contracts stay pinned."""
import json,hashlib
from pathlib import Path
MANIFEST_SHA256='668d517a3553e6658a35245c0358cc47501b5850d1401bbee02113cdd4f2bb8f'
def matches(root,name,expected):
    raw=(root/name).read_bytes();actual=hashlib.sha256(raw).hexdigest()
    if actual==expected:return True
    body=(root/'contracts/runtime_preparation/kernel_binding.json').read_bytes()
    if hashlib.sha256(body).hexdigest()!=MANIFEST_SHA256:raise ValueError('PREPARED_KERNEL_BINDING_CHANGED')
    spec=json.loads(body)
    row=spec['kernels'].get(name)
    return row is not None and row['original_sha256']==expected and row['prepared_sha256']==actual
