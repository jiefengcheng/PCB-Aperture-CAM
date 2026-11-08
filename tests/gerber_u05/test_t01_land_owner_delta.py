"""Connected T01 keeps real positive material and rejects numerical old-boundary spurs."""
import pytest
from shapely.affinity import translate
from shapely.geometry import box,Polygon,MultiPolygon
from src import component_clearance as cc,source_channel_scope,pin_separation
from src.gerber_u05 import pipeline as p
from src.gerber_u05.component_stages import t01_land_checker
from src.prepared_land_scene import PreparedLandScene
from test_width_owner_delta import numerical_case

@pytest.fixture(autouse=True)
def isolated(monkeypatch):
 for module in(cc,source_channel_scope,pin_separation):monkeypatch.setattr(module,'ACTIVE',None)

def evaluate(before,candidate,foreign,*,corrected=True):
 core=box(.69,-.455,.73,-.448)
 cc.bind(cc.joined([before,core,foreign]),'0'*64,dict(land=core,body=before,foreign=foreign))
 row=dict(id='land',original=core,candidate=candidate,native_source_kind='gr_poly',native_stroke_width_mm=0.)
 fixed=[dict(id='body',geometry=before),dict(id='foreign',geometry=foreign)]
 factory=t01_land_checker if corrected else PreparedLandScene
 checker=factory([row],fixed)
 return checker.check([row],materialize_scene=True)

def test_connected_t01_does_not_count_old_boundary_as_growth():
 before,candidate,foreign=numerical_case()
 assert not evaluate(before,candidate,foreign,corrected=False)['passed']
 result=evaluate(before,candidate,foreign)
 assert result['passed']and result['evaluation_complete']
 assert result['required_gap_mm']==.0401
 assert result['scene_union_materialized']

@pytest.mark.parametrize('approach,passed',[(0.,True),(.003408,True),(.003409,True),(.003410,False),(.004,False)])
def test_exact_existing_guard_still_rejects_real_positive_intrusion(approach,passed):
 before,candidate,foreign=numerical_case();result=evaluate(before,candidate,translate(foreign,yoff=-approach))
 assert result['passed']is passed
 assert result['required_gap_mm']==.0401


def test_tiny_positive_island_is_not_discarded():
 before,_,foreign=numerical_case();tiny=Polygon([(.685,-.385),(.6850001,-.385),(.685,-.3849999)])
 assert 0<tiny.area<1e-12
 result=evaluate(before,MultiPolygon([box(.69,-.455,.73,-.448),tiny]),foreign)
 assert not result['passed']
 assert any(r.get('gap_mm')==0. for r in result['failures'])


def test_original_land_core_still_required():
 before,_,foreign=numerical_case();result=evaluate(before,box(.70,-.454,.72,-.449),foreign)
 assert not result['passed']
 assert any(r['reason']=='ORIGINAL_TRACE_CORE_REMOVED'for r in result['failures'])
