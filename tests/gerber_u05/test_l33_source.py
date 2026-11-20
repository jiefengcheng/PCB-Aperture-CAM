import pytest

from src.gerber_u05 import gerber_source_profile as profile


def l33_arc(end_y):
    return (
        b'%FSLAX33Y33*%\n%MOMM*%\n%ADD10C,0.0254*%\n%LPD*%\n'
        b'G75*\nD10*\nX100Y0D02*\nG03X0Y' + end_y + b'I-100J0D01*\nM02*\n'
    )


def test_l33_parses_on_its_source_grid_and_preserves_the_raw_span():
    raw = l33_arc(b'101')
    gerber, parser, proof = profile.parse_source(raw)
    shape, residual = profile.object_geometry(gerber.objects[0])
    assert proof['source_format'] == 'MM_L33_ABSOLUTE'
    assert proof['coordinate_grid_mm'] == .001
    assert shape.is_valid and not shape.is_empty
    assert residual == pytest.approx(.001)
    start, end = parser.spans[0]
    assert raw[start:end].endswith(b'G03X0Y101I-100J0D01*')


def test_l33_rejects_arc_residual_beyond_the_source_grid_bound():
    gerber, _, _ = profile.parse_source(l33_arc(b'104'))
    with pytest.raises(ValueError, match='ARC_RADIUS_EXCEEDS_SOURCE_COORDINATE_BOUND'):
        profile.object_geometry(gerber.objects[0])


@pytest.mark.parametrize('word', [b'', b'0000101'])
def test_l33_rejects_empty_and_overlong_coordinate_words(word):
    with pytest.raises(ValueError, match='L46_INTEGER_COORDINATE_REQUIRED|L33_COORDINATE_WORD_TOO_LONG'):
        profile.parse_source(l33_arc(word))
