"""Replaceable provisional T04 limits, frozen at the job boundary.

The factor ladder and total-width cap are simultaneous limits. A capped rung
is blocked, never clamped to an off-ladder width. Original width is always the
source width; neither preceding growth nor the last accepted rung compounds it.
"""
from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

DEFAULT_REGISTRY = Path(__file__).resolve().parents[1] / 'contracts/t04/settings.json'
SNAPSHOT_NAME = 'T04_SETTINGS_SNAPSHOT.json'


def _pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            raise ValueError('DUPLICATE_T04_SETTING:' + key)
        result[key] = value
    return result


def _decode(raw):
    def nonfinite(token):
        raise ValueError('NONFINITE_T04_SETTING:' + token)
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=nonfinite)


def _number(value, name, *, positive=False):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < 0 or (positive and value == 0)):
        raise ValueError('INVALID_T04_SETTING:' + name)
    return Decimal(str(value))


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@dataclass(frozen=True)
class T04Settings:
    maximum_factor: float
    step_count: int
    maximum_total_width_increase_mm: float
    source_sha256: str
    _raw: bytes = field(repr=False)

    @property
    def factor_increment(self):
        return float((Decimal(str(self.maximum_factor)) - 1) / self.step_count)

    def rung(self, original_width_mm, rung):
        """Describe a source-relative candidate without doing geometry work.

        Rung zero is KEEP. Spacing, separation, joint, geometry and export checks
        still have to pass before accepting any parameter-eligible candidate.
        Decimal arithmetic prevents binary rounding from rejecting exactly 30um.
        """
        width = _number(original_width_mm, 'original_width_mm', positive=True)
        if type(rung) is not int or not 0 <= rung <= self.step_count:
            raise ValueError('T04_RUNG_OUT_OF_RANGE')
        factor = 1 + (Decimal(str(self.maximum_factor)) - 1) * rung / self.step_count
        increase = width * (factor - 1)
        allowed = increase <= Decimal(str(self.maximum_total_width_increase_mm))
        return dict(rung=rung, factor=float(factor), original_width_mm=float(width),
                    resulting_width_mm=float(width + increase),
                    total_width_increase_mm=float(increase),
                    per_side_offset_mm=float(increase / 2),
                    percentage_growth=float((factor - 1) * 100),
                    within_growth_limits=allowed,
                    blocking_reason=None if allowed else 'TOTAL_WIDTH_INCREASE_LIMIT')

    def resolved(self):
        return dict(status='PROVISIONAL', maximum_factor=self.maximum_factor,
                    step_count=self.step_count, factor_increment=self.factor_increment,
                    maximum_total_width_increase_mm=self.maximum_total_width_increase_mm,
                    absolute_limit_basis='TOTAL_WIDTH_INCREASE_FROM_ORIGINAL_SOURCE',
                    candidate_basis='ORIGINAL_SOURCE_GEOMETRY_AND_WIDTH',
                    cap_behavior='REJECT_RUNG_WITHOUT_CLAMPING')

    def write_snapshot(self, path):
        payload = dict(schema='pcb-t04-ladder-job-snapshot/1',
                       source_sha256=self.source_sha256,
                       source_json=self._raw.decode('utf-8'), resolved=self.resolved())
        body = _json(payload)
        with Path(path).open('xb') as stream:
            stream.write(body)
        return hashlib.sha256(body).hexdigest()


def from_bytes(raw):
    value = _decode(raw)
    keys = {'schema', 'revision', 'status', 'maximum_factor', 'step_count',
            'maximum_total_width_increase_mm', 'scope'}
    if (type(value) is not dict or set(value) != keys
            or value['schema'] != 'pcb-t04-ladder-settings/1'
            or type(value['revision']) is not int or value['revision'] < 1
            or value['status'] != 'PROVISIONAL' or type(value['scope']) is not str):
        raise ValueError('T04_REGISTRY_SCHEMA_CHANGED')
    factor = _number(value['maximum_factor'], 'maximum_factor', positive=True)
    # The existing source-offset geometry family is qualified only through 1.5x.
    if not Decimal(1) < factor <= Decimal('1.5'):
        raise ValueError('T04_FACTOR_OUTSIDE_QUALIFIED_FAMILY')
    if type(value['step_count']) is not int or value['step_count'] != 10:
        raise ValueError('T04_TEN_STEP_PROCESS_REQUIRED')
    cap = _number(value['maximum_total_width_increase_mm'],
                  'maximum_total_width_increase_mm')
    return T04Settings(float(factor), value['step_count'], float(cap),
                       hashlib.sha256(raw).hexdigest(), raw)


def capture(path=DEFAULT_REGISTRY):
    return from_bytes(Path(path).read_bytes())


def read_snapshot(path):
    payload = _decode(Path(path).read_bytes())
    if (type(payload) is not dict
            or set(payload) != {'schema', 'source_sha256', 'source_json', 'resolved'}
            or payload['schema'] != 'pcb-t04-ladder-job-snapshot/1'):
        raise ValueError('T04_SNAPSHOT_SCHEMA_CHANGED')
    policy = from_bytes(payload['source_json'].encode('utf-8'))
    if (policy.source_sha256 != payload['source_sha256']
            or policy.resolved() != payload['resolved']):
        raise ValueError('T04_JOB_SNAPSHOT_CHANGED')
    return policy


def capture_job(run, path=DEFAULT_REGISTRY):
    """Write once; callers must include this file in their immutable job seal."""
    settings = capture(path)
    settings.write_snapshot(Path(run) / SNAPSHOT_NAME)
    return settings
