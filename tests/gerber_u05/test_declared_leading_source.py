"""Declared leading-zero formats share intake without changing source values."""
import hashlib

import pytest
from shapely import to_wkb

from src.gerber_u05 import gerber_source_profile as profile
from src.gerber_u05 import pipeline


def source(integer=3, fraction=5, body=b'X1Y-2D03*\n'):
    return (f'%FSLAX{integer}{fraction}Y{integer}{fraction}*%\n'.encode()
            + b'%MOMM*%\n%ADD10C,0.2*%\n%LPD*%\nD10*\n'
            + body + b'M02*\n')


@pytest.mark.parametrize('integer', range(1, 7))
@pytest.mark.parametrize('fraction', range(1, 7))
def test_declared_leading_formats_use_integer_source_grid_values(integer, fraction):
    raw = source(integer, fraction)
    gerber, parser, proof = profile.parse_source(raw)
    assert gerber.objects[0].x == 1 / 10**fraction
    assert gerber.objects[0].y == -2 / 10**fraction
    assert parser.file_settings.number_format == (integer, fraction)
    assert proof['coordinate_grid_mm'] == 10.**-fraction
    assert proof['source_format'] == f'MM_L{integer}{fraction}_ABSOLUTE'
    assert proof['legacy_empty_zero_fields'] == 0
    start, end = parser.spans[0]
    assert raw[start:end] == b'X1Y-2D03*'


def test_l35_and_equivalent_l46_preserve_identical_geometry_and_modal_coordinates():
    body = (b'G75*\nX-737000Y1715000D02*\nX-706020D01*\n'
            b'Y1571850D01*\nG03X-696020Y1561850I10000J0D01*\n')
    raw = source(body=body)
    before = hashlib.sha256(raw).hexdigest()
    control = source(4, 6, profile.FIELD.sub(
        lambda m: m[1] + str(int(m[2]) * 10), body.decode()).encode())
    parsed, parser, _ = profile.parse_source(raw)
    reference, _, _ = profile.parse_source(control)
    assert len(parsed.objects) == len(reference.objects) == 3
    for index, (actual, expected) in enumerate(zip(parsed.objects, reference.objects)):
        assert to_wkb(profile.object_geometry(actual)[0]) == to_wkb(profile.object_geometry(expected)[0])
        start, end = parser.spans[index]
        assert raw[start:end].endswith(b'D01*')
    assert hashlib.sha256(raw).hexdigest() == before


def test_l35_source_binding_keeps_original_bytes_order_and_spans(tmp_path):
    raw = source(body=b'X-737000Y1715000D03*\nX1D03*\n')
    store = pipeline.Store(tmp_path / 'runtime')
    binding = pipeline.build_source(store, raw)
    scene = store.get_json(binding['scene_ref'], kind='scene')
    assert store.get(binding['source_ref'], kind='gerber-source') == raw
    assert binding['source_objects'] == len(scene['objects']) == 2
    assert binding['coordinate_oracle']['source_format'] == 'MM_L35_ABSOLUTE'
    for row in scene['objects']:
        start, end = row['metadata']['source_span']
        assert row['source_id'] == f'{profile.digest(raw)}:bytes:{start}:{end}'
        assert row['metadata']['prefix_sha256'] == profile.digest(raw[:end])


@pytest.mark.parametrize('mutation,reason', [
    (lambda raw: raw.replace(b'X1Y-2', b'XY-2'), 'DECLARED_LEADING_INTEGER_COORDINATE_REQUIRED'),
    (lambda raw: raw.replace(b'X1Y-2', b'X123456789Y-2'), 'DECLARED_LEADING_INTEGER_COORDINATE_REQUIRED'),
    (lambda raw: raw.replace(b'FSLAX35Y35', b'FSLIX35Y35'), 'GERBER_ONLY_PROFILE_REQUIRES_MM_T35_ABSOLUTE'),
    (lambda raw: raw.replace(b'FSLAX35Y35', b'FSLAX35Y34'), 'GERBER_ONLY_PROFILE_REQUIRES_MM_T35_ABSOLUTE'),
    (lambda raw: raw.replace(b'MOMM', b'MOIN'), 'GERBER_ONLY_DECLARED_LEADING_PROFILE_REQUIRES_MM_ABSOLUTE'),
    (lambda raw: raw.replace(b'%MOMM*%', b'%MOMM*%\n%MOMM*%'), 'GERBER_ONLY_DECLARED_LEADING_PROFILE_REQUIRES_MM_ABSOLUTE'),
    (lambda raw: raw.replace(b'%MOMM*%', b'%FSLAX35Y35*%\n%MOMM*%'), 'GERBER_ONLY_DECLARED_LEADING_PROFILE_REQUIRES_MM_ABSOLUTE'),
    (lambda raw: raw.replace(b'%LPD*%', b'%IPNEG*%\n%LPD*%'), 'POSITIVE_IMAGE_POLARITY_REQUIRED'),
    (lambda raw: raw.replace(b'M02*', b''), 'missing mandatory M02 EOF marker'),
])
def test_declared_format_does_not_admit_ambiguous_or_corrupt_sources(mutation, reason):
    with pytest.raises(Exception, match=reason):
        profile.parse_source(mutation(source()))


def test_new_declared_grid_bounds_only_source_arc_recognition():
    raw = source(3, 4, b'G75*\nX1000Y0D02*\nG03X0Y1001I-1000J0D01*\n')
    gerber, _, proof = profile.parse_source(raw)
    assert profile.source_arc_grid(gerber.objects[0]) == proof['coordinate_grid_mm'] == .0001
    assert profile.object_geometry(gerber.objects[0])[1] == pytest.approx(.0001)
    bad, _, _ = profile.parse_source(raw.replace(b'Y1001', b'Y1004'))
    with pytest.raises(ValueError, match='ARC_RADIUS_EXCEEDS_SOURCE_COORDINATE_BOUND'):
        profile.object_geometry(bad.objects[0])
