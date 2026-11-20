"""Shared, adjustable edge-restoration limit; independent of trace growth.

Capture once per bounded job and retain ``resolved()`` in its evidence. Changing
the registry affects future captures, never a captured policy or old result.
This setting grants no exemption from contact, clearance or pin protection.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path

DEFAULT_REGISTRY = Path(__file__).resolve().parents[1] / 'contracts/edge_restoration/settings.json'


@dataclass(frozen=True)
class EdgeRestorationPolicy:
    maximum_depth_mm: float
    source_sha256: str

    def __post_init__(self):
        if (type(self.maximum_depth_mm) not in (float, int) or
                not math.isfinite(self.maximum_depth_mm) or self.maximum_depth_mm <= 0):
            raise ValueError('INVALID_EDGE_RESTORATION_DEPTH')

    def resolved(self):
        return dict(status='PROVISIONAL', maximum_depth_mm=self.maximum_depth_mm,
                    source_sha256=self.source_sha256,
                    depth_basis='DISTANCE_TO_SUPPORTED_SMOOTH_EDGE',
                    over_limit_behavior='REJECT_WHOLE_FEATURE')


def capture(path=DEFAULT_REGISTRY):
    """Read the shared default or an explicit job-specific registry, strictly."""
    raw = Path(path).read_bytes()
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('DUPLICATE_EDGE_RESTORATION_SETTING:' + key)
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    if (not isinstance(value, dict) or
            set(value) != {'schema', 'status', 'maximum_depth_mm'} or
            value['schema'] != 'pcb-edge-restoration-settings/1' or
            value['status'] != 'PROVISIONAL'):
        raise ValueError('EDGE_RESTORATION_SETTINGS_SCHEMA_CHANGED')
    return EdgeRestorationPolicy(value['maximum_depth_mm'], sha256(raw).hexdigest())
