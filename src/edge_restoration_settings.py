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
    maximum_noise_area_fraction: float = .10

    def __post_init__(self):
        if (type(self.maximum_depth_mm) not in (float, int) or
                not math.isfinite(self.maximum_depth_mm) or self.maximum_depth_mm <= 0):
            raise ValueError('INVALID_EDGE_RESTORATION_DEPTH')
        if (type(self.maximum_noise_area_fraction) not in (float,int) or
                not math.isfinite(self.maximum_noise_area_fraction) or
                not 0<self.maximum_noise_area_fraction<1):
            raise ValueError('INVALID_NOISE_AREA_FRACTION')

    def resolved(self):
        return dict(status='PROVISIONAL', maximum_depth_mm=self.maximum_depth_mm,
                    source_sha256=self.source_sha256,
                    depth_basis='DISTANCE_TO_SUPPORTED_SMOOTH_EDGE',
                    maximum_noise_area_fraction=self.maximum_noise_area_fraction,
                    noise_area_basis='ORIGINAL_CAUSING_PAD_OR_TRACE',
                    noise_area_comparison='STRICTLY_LESS_THAN',
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
    base={'schema','status','maximum_depth_mm'}
    old=isinstance(value,dict) and value.get('schema')=='pcb-edge-restoration-settings/1' and set(value)==base
    new=(isinstance(value,dict) and value.get('schema')=='pcb-edge-restoration-settings/2' and
         set(value)==base|{'maximum_noise_area_fraction','noise_area_basis'} and
         value.get('noise_area_basis')=='ORIGINAL_CAUSING_PAD_OR_TRACE')
    if not (old or new) or value['status'] != 'PROVISIONAL':
        raise ValueError('EDGE_RESTORATION_SETTINGS_SCHEMA_CHANGED')
    return EdgeRestorationPolicy(value['maximum_depth_mm'], sha256(raw).hexdigest(),
                                 value.get('maximum_noise_area_fraction',.10))


def classify_protrusion(protrusion, original_feature, *, source_id, policy=None):
    """Apply the owner-defined area rule to the original causing pad/trace.

    Connectivity, supported boundary, depth, pins and final geometry checks
    remain separate prerequisites. A large connected fill is never the area
    denominator. The caller binds source_id and geometry to immutable input.
    """
    policy=capture()if policy is None else policy
    if (not source_id or any(not g.is_valid or g.geom_type not in ('Polygon','MultiPolygon')
                             for g in (protrusion,original_feature)) or
            original_feature.is_empty or original_feature.area<=0):
        raise ValueError('ORIGINAL_CAUSING_PAD_OR_TRACE_REQUIRED')
    from src.gerber_u05.pipeline import EPS
    from src.native_inventory import ERROR_MM
    outside=protrusion.difference(original_feature)
    if (outside.area>EPS or
            not outside.difference(original_feature.buffer(ERROR_MM,quad_segs=128)).is_empty):
        raise ValueError('PROTRUSION_OUTSIDE_CAUSING_SOURCE_FEATURE')
    area=protrusion.area;fraction=area/original_feature.area
    qualifies=area>0 and area<policy.maximum_noise_area_fraction*original_feature.area
    return dict(source_id=source_id,protrusion_area_mm2=area,
                original_feature_area_mm2=original_feature.area,area_fraction=fraction,
                is_noise=qualifies,disposition='TRIM_CANDIDATE_REQUIRES_GEOMETRY_CHECKS'if qualifies else 'KEEP_FOR_REVIEW',
                original_feature_sha256=sha256(original_feature.wkb).hexdigest(),
                source_containment_residual_mm2=outside.area,
                native_area_error_mm2=EPS,native_coordinate_error_mm=ERROR_MM,
                protrusion_sha256=sha256(protrusion.wkb).hexdigest(),policy=policy.resolved())
