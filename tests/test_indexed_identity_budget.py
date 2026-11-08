import pytest
from shapely.geometry import Point
from shapely.affinity import translate
from shapely import from_wkb,to_wkb
from src.indexed_hausdorff import distance


def test_complete_identical_material_needs_no_oversized_segment_index():
 g=Point(0,0).buffer(1,quad_segs=150);clone=from_wkb(to_wkb(g));d,proof=distance(g,clone,budget_bytes=50000)
 assert d==0 and proof['method']=='Exact complete native WKB identity'
 assert proof['charged_identity_bytes']<=50000 and proof['tolerance_unchanged']


def test_same_vertex_count_and_area_cannot_hide_a_different_boundary():
 g=Point(0,0).buffer(1,quad_segs=150)
 with pytest.raises(ValueError,match='INDEX_BUDGET_EXCEEDED'):distance(g,translate(g,xoff=.001),budget_bytes=50000)


def test_identity_cannot_bypass_its_own_memory_budget():
 g=Point(0,0).buffer(1,quad_segs=150)
 with pytest.raises(ValueError,match='BUDGET_EXCEEDED'):distance(g,g,budget_bytes=100)
