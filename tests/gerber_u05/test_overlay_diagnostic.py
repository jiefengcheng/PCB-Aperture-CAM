"""A mixed-dimension diagnostic must retain every positive copper face."""
import pytest,json,hashlib
from pathlib import Path
from shapely import from_wkb
from shapely.geometry import box,Polygon,GeometryCollection,LineString,Point
from shapely.ops import unary_union
from src.component_voids import _overlay_diagnostic,parts


def test_valid_polygon_diagnostic_report_is_unchanged():
 body=box(0,0,1,1)
 assert _overlay_diagnostic(body,body)==dict(legacy_global_overlay_components=1,global_overlay_symmetric_difference_mm2=0.)


def test_zero_area_overlay_remnants_are_recorded_without_changing_material():
 body=box(0,0,1,1);legacy=GeometryCollection([body,LineString([(2,0),(3,0)]),Point(4,0)])
 report=_overlay_diagnostic(legacy,body)
 assert report['legacy_global_overlay_components']==1
 assert report['global_overlay_symmetric_difference_mm2']==0.
 assert report['legacy_global_overlay_representation']['raw_type']=='GeometryCollection'
 assert body.equals(box(0,0,1,1))
 # Actual candidate copper still uses the original strict polygon guard.
 with pytest.raises(ValueError,match='VALID_POLYGONAL_COPPER_REQUIRED'):parts(legacy)


def test_minimum_grid_positive_face_is_never_filtered_as_remnant():
 body=box(0,0,1,1);minimum=box(2,0,2.000001,.000001)
 expected=unary_union([body,minimum]);legacy=GeometryCollection([body,minimum,Point(4,0)])
 report=_overlay_diagnostic(legacy,expected)
 assert report['legacy_global_overlay_components']==2
 assert report['global_overlay_symmetric_difference_mm2']==0.


def test_invalid_positive_geometry_cannot_use_diagnostic_extraction():
 invalid=Polygon([(0,0),(1,1),(0,1),(1,0),(0,0)])
 with pytest.raises(ValueError,match='INVALID_CANDIDATE_CONTEXT'):_overlay_diagnostic(GeometryCollection([invalid]),box(0,0,1,1))


def test_exact_retained_zero_area_line_no_longer_rejects_diagnostic_count():
 folder=Path(__file__).with_name('fixtures')/'overlay_remnant';manifest=json.loads((folder/'MANIFEST.json').read_bytes());values={}
 for name,expected in manifest['files'].items():
  body=(folder/(name+'.wkb')).read_bytes();assert hashlib.sha256(body).hexdigest()==expected;values[name]=from_wkb(body)
 legacy=GeometryCollection([values['body'],values['line']])
 assert values['line'].area==0 and values['line'].length==manifest['line_length_mm']
 with pytest.raises(ValueError,match='VALID_POLYGONAL_COPPER_REQUIRED'):parts(legacy)
 report=_overlay_diagnostic(legacy,values['body'])
 assert report['global_overlay_symmetric_difference_mm2']==0.
 assert report['legacy_global_overlay_components']==len(parts(values['body']))
