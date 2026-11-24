"""Provisional global limits, total-width semantics and immutable job custody."""
import json
from dataclasses import FrozenInstanceError

import pytest

from src.t04_settings import capture, capture_job, from_bytes, read_snapshot, SNAPSHOT_NAME


def modified(**changes):
    value = json.loads(capture()._raw)
    return json.dumps(dict(value, **changes)).encode()


def test_ladder_uses_existing_factor_and_simultaneous_absolute_cap():
    settings = capture()
    assert settings.maximum_factor == 1.5
    assert settings.maximum_total_width_increase_mm == .030
    assert [settings.rung(.05, rung)['factor'] for rung in range(1, 11)] == [
        1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.40, 1.45, 1.50]
    assert settings.rung(.05, 10)['total_width_increase_mm'] == .025
    assert settings.rung(.05, 10)['within_growth_limits']
    assert settings.rung(.065, 9)['within_growth_limits']
    blocked = settings.rung(.065, 10)
    assert blocked['total_width_increase_mm'] == .0325
    assert not blocked['within_growth_limits']
    assert blocked['blocking_reason'] == 'TOTAL_WIDTH_INCREASE_LIMIT'
    # No off-ladder clamping to .095mm when the tenth rung proposes .0975mm.
    assert blocked['resulting_width_mm'] == .0975


def test_thirty_um_is_total_width_increase_with_exact_boundary():
    # Exercise historical ladder arithmetic separately from the new global width exclusion.
    settings = from_bytes(capture()._raw)
    boundary = settings.rung(.3, 2)
    assert boundary['within_growth_limits']
    assert boundary['total_width_increase_mm'] == .030
    assert boundary['per_side_offset_mm'] == .015
    assert boundary['resulting_width_mm'] == .33
    assert not settings.rung(.3, 3)['within_growth_limits']
    # Detects an erroneous 30um-per-side interpretation.
    assert not settings.rung(.1, 10)['within_growth_limits']
    # A tiny excess is not allowed to consume finished-clearance tolerance.
    assert not settings.rung(.300000001, 2)['within_growth_limits']


def test_widths_are_source_relative_and_settings_are_immutable():
    settings = capture()
    assert settings.rung(.1, 2)['resulting_width_mm'] == .11
    assert settings.rung(.1, 3)['resulting_width_mm'] == .115
    assert settings.rung(.1, 0)['resulting_width_mm'] == .1
    with pytest.raises(FrozenInstanceError):
        settings.maximum_total_width_increase_mm = .060


def test_registry_replacement_affects_only_next_capture(tmp_path):
    registry = tmp_path / 'registry.json'
    registry.write_bytes(capture()._raw)
    first = tmp_path / 'first'; first.mkdir()
    second = tmp_path / 'second'; second.mkdir()
    old = capture_job(first, registry)
    registry.write_bytes(modified(revision=2, maximum_total_width_increase_mm=.020))
    new = capture_job(second, registry)
    assert old.maximum_total_width_increase_mm == .030
    assert new.maximum_total_width_increase_mm == .020
    assert old.source_sha256 != new.source_sha256
    assert read_snapshot(first / SNAPSHOT_NAME) == old
    assert read_snapshot(second / SNAPSHOT_NAME) == new
    with pytest.raises(FileExistsError):
        capture_job(first, registry)


@pytest.mark.parametrize('field,value', [
    ('maximum_factor', 1), ('maximum_factor', 1.500001),
    ('maximum_factor', True), ('maximum_factor', float('inf')),
    ('maximum_total_width_increase_mm', -.001),
    ('maximum_total_width_increase_mm', '0.030'),
    ('maximum_total_width_increase_mm', False),
    ('maximum_total_width_increase_mm', float('nan')),
    ('step_count', 9), ('step_count', 10.0), ('step_count', True),
])
def test_invalid_settings_fail_closed(field, value):
    with pytest.raises(ValueError):
        from_bytes(modified(**{field: value}))


@pytest.mark.parametrize('mutation', ['resolved_cap', 'source_cap', 'hash'])
def test_altered_job_limits_are_rejected(tmp_path, mutation):
    snapshot = tmp_path / SNAPSHOT_NAME
    capture().write_snapshot(snapshot)
    value = json.loads(snapshot.read_bytes())
    if mutation == 'resolved_cap':
        value['resolved']['maximum_total_width_increase_mm'] = .060
    elif mutation == 'source_cap':
        original = json.loads(value['source_json'])
        original['maximum_total_width_increase_mm'] = .060
        value['source_json'] = json.dumps(original)
    else:
        value['source_sha256'] = '0' * 64
    snapshot.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='T04_JOB_SNAPSHOT_CHANGED'):
        read_snapshot(snapshot)


def test_duplicate_registry_key_rejected():
    raw = capture()._raw.replace(b'"maximum_factor": 1.5,',
                                b'"maximum_factor": 1.5, "maximum_factor": 1.25,')
    with pytest.raises(ValueError, match='DUPLICATE_T04_SETTING'):
        from_bytes(raw)
