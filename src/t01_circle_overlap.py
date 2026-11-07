"""Replaceable source-bound T01 circle eligibility; never deletes source copper."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / 'contracts/t01_circle_overlap/settings.json'
SCHEMA = 't01-circle-overlap-settings/1'


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_T01_CIRCLE_OVERLAP_SETTING:' + key)
        result[key] = value
    return result


@dataclass(frozen=True)
class Settings:
    maximum_other_copper_coverage_fraction_for_growth: float
    source_sha256: str
    raw_json: str

    def snapshot(self):
        return dict(schema=SCHEMA, status='PROVISIONAL',
                    maximum_other_copper_coverage_fraction_for_growth=self.maximum_other_copper_coverage_fraction_for_growth,
                    comparison='KEEP_WHEN_STRICTLY_GREATER',
                    context='COMPLETE_STAGE_ENTRY_COPPER',
                    exclude='SELF_AND_EXACT_GEOMETRIC_ALIASES',
                    action='KEEP_EXACT_PREDECESSOR',
                    registry_sha256=self.source_sha256, registry_json=self.raw_json)


def from_bytes(raw):
    def invalid_number(value):
        raise ValueError('NONFINITE_T01_CIRCLE_OVERLAP_SETTING:' + value)
    value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=invalid_number)
    fixed = dict(schema=SCHEMA, status='PROVISIONAL',
                 comparison='KEEP_WHEN_STRICTLY_GREATER',
                 context='COMPLETE_STAGE_ENTRY_COPPER',
                 exclude='SELF_AND_EXACT_GEOMETRIC_ALIASES',
                 action='KEEP_EXACT_PREDECESSOR',
                 scope='T01_CIRCLES_ONLY; existing full-containment KEEP remains unchanged')
    key = 'maximum_other_copper_coverage_fraction_for_growth'
    if (type(value) is not dict or set(value) != {*fixed, 'revision', key}
            or any(value[k] != v for k, v in fixed.items())
            or type(value['revision']) is not int or value['revision'] < 1):
        raise ValueError('T01_CIRCLE_OVERLAP_SETTINGS_SCHEMA_CHANGED')
    limit = value[key]
    if type(limit) not in (int, float) or not math.isfinite(limit) or not 0 <= limit <= 1:
        raise ValueError('T01_CIRCLE_OVERLAP_FRACTION_OUT_OF_RANGE')
    return Settings(float(limit), hashlib.sha256(raw).hexdigest(), raw.decode('utf-8'))


def capture(path=REGISTRY):
    return from_bytes(Path(path).read_bytes())


def assess(core, containment, settings):
    """Reuse the complete alias-excluding source union, not trial-grown copper.

    Full containment keeps its existing epsilon and separate meaning. A
    partially overlapping circle is not relabelled as geometrically contained.
    """
    area = core.area
    missing = containment['uncovered_area_mm2']
    from src.shape_containment import policy
    epsilon=policy()['area_epsilon_mm2']
    if (not math.isfinite(area) or area <= 0 or not math.isfinite(missing)
            or missing < -epsilon or missing > area+epsilon):
        raise ValueError('T01_CIRCLE_OVERLAP_AREA_INVALID')
    # An exact set difference can reorder identical polygon summation and
    # report area a few floating-point ulps larger than the source. Normalize
    # only this impossible range, using the existing containment area epsilon.
    # The 70% comparison itself receives no added tolerance.
    normalized_missing=max(0.,min(area,missing))
    covered = area - normalized_missing
    fraction = covered / area
    keep_overlap = fraction > settings.maximum_other_copper_coverage_fraction_for_growth
    keep = containment['contained'] or keep_overlap
    reason = ('KEEP_CONTAINED' if containment['contained'] else
              'KEEP_OTHER_COPPER_COVERAGE_ABOVE_LIMIT' if keep_overlap else
              'ELIGIBLE_FOR_ORDINARY_T01_CHECKS')
    return dict(source_id=containment['source_id'],
                source_geometry_sha256=containment['source_geometry_sha256'],
                excluded_aliases=containment['excluded_aliases'],
                covering_context_source_ids=containment['covering_context_source_ids'],
                source_area_mm2=area, other_copper_covered_area_mm2=covered,
                uncovered_area_mm2=missing, area_range_roundoff_mm2=missing-normalized_missing,
                other_copper_coverage_fraction=fraction,
                maximum_other_copper_coverage_fraction_for_growth=settings.maximum_other_copper_coverage_fraction_for_growth,
                comparison='STRICTLY_GREATER', fully_contained=containment['contained'],
                keep=keep, disposition=reason, settings_sha256=settings.source_sha256)
