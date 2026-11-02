"""Crop display sampling follows physical extent without relaxing any audit band."""
import json
from pathlib import Path
import pytest
from src.render_abi.crop_pixels import choose_pixels
ROOT=Path(__file__).resolve().parents[1]


def policy():return json.loads((ROOT/'contracts/render/crop.json').read_bytes())['pixel_policy']


def test_actual_wide_crop_gets_the_verified_high_resolution():
    b=[.7687751377751644,-13.019894410242872,7.026775137775164,-8.35282989411384]
    w,h=choose_pixels(b,policy());assert [w,h]==[3129,2334]
    assert (b[2]-b[0])/w<=.002 and (b[3]-b[1])/h<=.002


def test_small_crop_keeps_minimum_readable_width():
    assert choose_pixels([0,0,1,.5],policy())==[1280,640]


def test_large_display_budget_rejects_instead_of_coarsening_resolution():
    with pytest.raises(ValueError,match='PIXEL_BUDGET_EXCEEDED'):choose_pixels([0,0,25,25],policy())


@pytest.mark.parametrize('bounds',[[0,0,0,1],[0,0,1,float('nan')],[False,0,1,1]])
def test_invalid_bounds_are_not_fitted(bounds):
    with pytest.raises(ValueError):choose_pixels(bounds,policy())


def test_legacy_and_crop_fidelity_limits_and_controls_are_still_identical():
    a=json.loads((ROOT/'contracts/render/c01.json').read_bytes());b=json.loads((ROOT/'contracts/render/crop.json').read_bytes())
    assert a['raster_boundary_error_mm']==b['raster_boundary_error_mm']==dict(kicad=.001,gerber=.005)
    assert a['negative_controls']==b['negative_controls']
