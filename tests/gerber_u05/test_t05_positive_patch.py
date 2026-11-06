import hashlib,json
from pathlib import Path
import pytest
from shapely import from_wkb,to_wkb
from shapely.geometry import Polygon,GeometryCollection,LineString,box
from src.u05_board.coverage import filled_patch
from src.stage_abi.loaded_geometry import valid
from src.stage_abi.contracts import StageABIError

FIXTURE=Path(__file__).parent/'fixtures/t05_zero_area_remnants'

def read(name):
 entries=json.loads((FIXTURE/'MANIFEST.json').read_bytes())['files'];expected=next(v for v in entries if v['name']==name)
 body=(FIXTURE/name).read_bytes();assert hashlib.sha256(body).hexdigest()==expected['sha256']
 return from_wkb(body)

@pytest.mark.parametrize('index,faces',[(0,49),(1,28)])
def test_actual_rejected_patch_keeps_every_positive_face(index,faces):
 raw=read(str(index)+'_patch.wkb');before=read(str(index)+'_context.wkb')
 with pytest.raises(StageABIError,match='finite valid filled copper'):valid(raw)
 result=filled_patch(raw,before);valid(result)
 originals=[g for g in raw.geoms if g.geom_type=='Polygon']
 assert len(originals)==len(result.geoms)==faces
 assert sorted(to_wkb(g)for g in originals)==sorted(to_wkb(g)for g in result.geoms)
 assert before.union(result).covers(next(g for g in raw.geoms if g.geom_type=='LineString'))

def test_ordinary_polygon_and_its_hole_are_unchanged():
 shape=Polygon([(0,0),(3,0),(3,3),(0,3)],holes=[[(1,1),(1,2),(2,2),(2,1)]])
 assert filled_patch(shape,box(-1,-1,4,4))is shape

def test_positive_faces_have_no_small_area_filter():
 tiny=Polygon([(2,2),(2+1e-8,2),(2,2+1e-8)]);large=box(0,0,1,1)
 raw=GeometryCollection([large,tiny,LineString([(0,0),(1,0)])]);result=filled_patch(raw,large)
 assert any(to_wkb(p)==to_wkb(tiny)for p in result.geoms)

def test_uncovered_line_cannot_be_silently_removed():
 raw=GeometryCollection([box(0,0,1,1),LineString([(5,5),(6,6)])])
 with pytest.raises(ValueError,match='NONAREAL_SCOPE_NOT_PROVED'):filled_patch(raw,box(0,0,1,1))

def test_invalid_positive_geometry_is_never_repaired():
 bowtie=Polygon([(0,0),(1,1),(0,1),(1,0)])
 with pytest.raises(ValueError,match='PATCH_INVALID'):filled_patch(GeometryCollection([bowtie]),box(-1,-1,2,2))
