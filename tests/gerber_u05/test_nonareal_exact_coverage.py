from pathlib import Path
import hashlib,json
from shapely import from_wkb,to_wkb
from shapely.geometry import Polygon,box,Point,LineString,GeometryCollection
import pytest
from src.u05_board.coverage import filled_patch

def test_actual_covered_collinear_line_keeps_every_positive_face():
 root=Path(__file__).parent/'fixtures/nonareal_containment';values={}
 for name,expected in json.loads((root/'MANIFEST.json').read_text()).items():
  raw=(root/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==expected;values[name]=from_wkb(raw)
 shape,before=values['shape.wkb'],values['before.wkb'];face=next(g for g in shape.geoms if g.geom_type=='Polygon');line=next(g for g in shape.geoms if g.geom_type=='LineString');context=before.union(face)
 assert not context.covers(line) and line.difference(context).is_empty
 assert to_wkb(filled_patch(shape,before))==to_wkb(face)

@pytest.mark.parametrize('uncovered',[Point(2,2),LineString([(0,0),(2,2)])])
def test_uncovered_zero_area_remainder_still_fails(uncovered):
 with pytest.raises(ValueError,match='NONAREAL_SCOPE_NOT_PROVED'):filled_patch(GeometryCollection([box(0,0,1,1),uncovered]),Polygon())
