"""The explanation overlay compares original copper, not the previous slice."""
import pytest
from shapely.geometry import Polygon, box
from src.viewer_abi.explanation import growth_comparison
from src.viewer_abi.live import display
from src.viewer_abi.publisher import path_data


def comparison(original, current, selected_path=None):
    return growth_comparison(original.wkb, current.wkb,
                             {'path': selected_path or path_data(display(current)[0])},
                             summary='Source versus growth', snapshot_note='Pinned snapshot')


def test_asymmetric_growth_and_unchanged_body():
    original, current = box(0, 0, 5, .05), box(0, -.008, 5, .067)
    result = comparison(original, current)
    assert result['addedAreaMM2'] == pytest.approx(5 * .025)
    assert result['removed'] is None and result['removedAreaMM2'] == 0
    assert result['added']['path'].count('M ') == 2  # both asymmetric bands
    assert result['original']['bounds']['height'] == .05
    unchanged = comparison(original, original)
    assert unchanged['added'] is None and unchanged['removed'] is None


def test_removal_and_holes_are_explicit():
    original = box(0, 0, 4, 4)
    current = Polygon(original.exterior.coords, [box(1, 1, 3, 3).exterior.coords])
    result = comparison(original, current)
    assert result['removedAreaMM2'] == 4 and result['added'] is None
    assert result['removed']['bounds'] == dict(x=1., y=1., width=2., height=2.)
    reversed_result = comparison(current, original)
    assert reversed_result['original']['path'].count('M ') == 2
    assert reversed_result['addedAreaMM2'] == 4


def test_different_candidate_cannot_be_explained_as_displayed():
    with pytest.raises(ValueError, match='CURRENT_BODY_NOT_DISPLAYED'):
        comparison(box(0, 0, 1, 1), box(0, 0, 2, 2), path_data(box(0, 0, 3, 3)))


def test_zero_area_difference_boundaries_are_not_filled():
    from shapely.geometry import GeometryCollection, LineString
    from src.viewer_abi.explanation import area_artwork
    area = box(0, 0, 1, 1)
    line = LineString([(10, 10), (11, 11)])
    result = area_artwork(GeometryCollection([area, line]))
    assert result['bounds'] == dict(x=0., y=0., width=1., height=1.)
    assert result['path'] == path_data(area)
    assert area_artwork(line) is None
