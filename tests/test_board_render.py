"""Board tiling covers the full source window at unchanged physical fidelity."""
import copy,json,math
from pathlib import Path
import pytest
from PIL import Image
from shapely.geometry import box,GeometryCollection
from shapely.ops import unary_union
from src.render_abi.board_tiles import tile_plan
from src.render_abi.board import audit_tile
from src.render_abi.view import BACKGROUND,FOREGROUND

POLICY=json.loads(Path('contracts/render/board.json').read_bytes())['tile_policy']

def test_tiles_partition_whole_source_window_without_coarsening():
    bounds=[-.3,-16.8,58.1,73.7];plan=tile_plan(bounds,POLICY);parts=[box(*t['bounds_mm'])for t in plan['tiles']]
    assert unary_union(parts).symmetric_difference(box(*bounds)).area<1e-10
    assert abs(sum(p.area for p in parts)-box(*bounds).area)<1e-9
    assert plan['total_pixels_per_panel']==sum(math.prod(t['pixels'])for t in plan['tiles'])
    for tile in plan['tiles']:
        b=tile['bounds_mm'];assert all(v<=.002+1e-15 for v in[(b[2]-b[0])/tile['pixels'][0],(b[3]-b[1])/tile['pixels'][1]])


def test_excessive_display_budget_rejects_without_truncating_tiles():
    p=copy.deepcopy(POLICY);p['maximum_total_pixels_per_panel']=1000
    with pytest.raises(ValueError,match='BUDGET'):tile_plan([0,0,60,90],p)

@pytest.mark.parametrize('bounds',[[0,0,0,1],[0,0,True,1],[0,0,float('nan'),1]])
def test_invalid_board_tile_window_rejects(bounds):
    with pytest.raises(ValueError):tile_plan(bounds,POLICY)


def test_uniform_native_tiles_require_analytic_empty_or_solid_proof(tmp_path):
    size=[64,64];b=[0,0,1,1];p=tmp_path/'empty.png';Image.new('RGB',size,BACKGROUND).save(p)
    assert audit_tile(p,GeometryCollection(),b,size,.001)['pixels_checked']==4096
    with pytest.raises(ValueError,match='RASTER_EMPTY_OR_SOLID'):audit_tile(p,box(.2,.2,.5,.5),b,size,.001)
    Image.new('RGB',size,FOREGROUND).save(p)
    assert audit_tile(p,box(*b),b,size,.001)['uniform_tile_analytic_proof']
    with pytest.raises(ValueError):audit_tile(p,GeometryCollection(),b,size,.001)


def test_mixed_foreground_cannot_pass_against_empty_analytic_copper(tmp_path):
    from PIL import ImageDraw
    p=tmp_path/'unexpected.png';image=Image.new('RGB',(64,64),BACKGROUND);ImageDraw.Draw(image).rectangle((10,10,30,30),fill=FOREGROUND);image.save(p)
    with pytest.raises(ValueError,match='RASTER_FIDELITY_EXCEEDED'):audit_tile(p,GeometryCollection(),[0,0,1,1],[64,64],.001)


def test_blank_window_can_have_nonempty_copper_outside_its_bounds(tmp_path):
    p=tmp_path/'blank.png';Image.new('RGB',(64,64),BACKGROUND).save(p)
    assert audit_tile(p,box(2,2,3,3),[0,0,1,1],[64,64],.001)['pixels_checked']==4096


def test_zero_area_context_cannot_mask_unexpected_foreground(tmp_path):
    from shapely.geometry import LineString
    from PIL import ImageDraw
    p=tmp_path/'unexpected.png';image=Image.new('RGB',(64,64),BACKGROUND);ImageDraw.Draw(image).rectangle((10,10,30,30),fill=FOREGROUND);image.save(p)
    with pytest.raises(ValueError,match='RASTER_FIDELITY_EXCEEDED'):audit_tile(p,LineString([(2,2),(2,3)]),[0,0,1,1],[64,64],.001)


def test_mixed_dimension_context_cannot_hide_distant_foreground(tmp_path):
    from shapely.geometry import LineString,GeometryCollection
    from PIL import ImageDraw
    p=tmp_path/'bad_context.png';image=Image.new('RGB',(64,64),BACKGROUND);draw=ImageDraw.Draw(image);draw.rectangle((16,16,31,31),fill=FOREGROUND);draw.rectangle((45,45,50,50),fill=FOREGROUND);image.save(p)
    mixed=GeometryCollection([box(.25,.25,.5,.5),LineString([(2,2),(3,3)])])
    with pytest.raises(ValueError,match='RASTER_FIDELITY_EXCEEDED'):audit_tile(p,mixed,[0,0,1,1],[64,64],.001)


def test_zero_area_context_removal_preserves_correct_polygon_raster(tmp_path):
    from shapely.geometry import LineString,GeometryCollection
    from PIL import ImageDraw
    p=tmp_path/'good_context.png';image=Image.new('RGB',(64,64),BACKGROUND);ImageDraw.Draw(image).rectangle((16,16,31,31),fill=FOREGROUND);image.save(p)
    mixed=GeometryCollection([box(.25,.25,.5,.5),LineString([(2,2),(3,3)])])
    assert audit_tile(p,mixed,[0,0,1,1],[64,64],.001)['mismatch_pixels']==0
