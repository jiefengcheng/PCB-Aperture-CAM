"""Job-bound ordinary-hole acceptance; protected separation is never exempted."""
import hashlib
import json
from contextvars import ContextVar
from pathlib import Path

STRICT = 'PRESERVE_SOURCE_AND_REJECT_NEW_POCKETS'
RELAXED = 'ACCEPT_WITHOUT_SOURCE_ANCESTRY'
SNAPSHOT = 'HOLE_ACCEPTANCE_SNAPSHOT.json'
REGISTRY = Path(__file__).resolve().parents[1] / 'contracts/hole_acceptance/settings.json'
ACTIVE = ContextVar('ordinary_hole_acceptance', default=STRICT)


def decode(raw):
    value = json.loads(raw)
    if (set(value) != {'schema', 'status', 'ordinary_holes', 'protected_separation'}
            or value['schema'] != 'pcb-ordinary-hole-acceptance/1'
            or value['status'] != 'PROVISIONAL'
            or value['ordinary_holes'] not in (STRICT, RELAXED)
            or value['protected_separation'] != 'MANDATORY_UNCHANGED'):
        raise ValueError('HOLE_ACCEPTANCE_POLICY_INVALID')
    return value


def capture(run, registry=REGISTRY):
    raw = Path(registry).read_bytes()
    value = decode(raw)
    payload = dict(schema='pcb-hole-acceptance-job/1', registry_json=raw.decode(),
                   registry_sha256=hashlib.sha256(raw).hexdigest(), resolved=value)
    with (Path(run) / SNAPSHOT).open('x') as stream:
        json.dump(payload, stream, sort_keys=True, separators=(',', ':'))
    return payload


def bind(run):
    path = Path(run) / SNAPSHOT
    if not path.exists():
        ACTIVE.set(STRICT)
        return dict(ordinary_holes=STRICT, basis='HISTORICAL_JOB_WITHOUT_POLICY')
    value = json.loads(path.read_bytes())
    raw = value['registry_json'].encode()
    if (value['schema'] != 'pcb-hole-acceptance-job/1'
            or hashlib.sha256(raw).hexdigest() != value['registry_sha256']
            or decode(raw) != value['resolved']):
        raise ValueError('HOLE_ACCEPTANCE_SNAPSHOT_CHANGED')
    ACTIVE.set(value['resolved']['ordinary_holes'])
    return value['resolved']


def required():
    return ACTIVE.get() == STRICT
