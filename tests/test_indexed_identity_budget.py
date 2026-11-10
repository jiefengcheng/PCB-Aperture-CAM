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


def test_sharded_query_retains_exact_metric_with_same_memory_ceiling():
 g=Point(0,0).buffer(1,quad_segs=150)
 shifted=translate(g,xoff=.001,yoff=-.0007)
 limit=195000
 with pytest.raises(ValueError,match='QUERY_BUDGET_EXCEEDED'):
  distance(g,shifted,budget_bytes=limit,batch=16)
 observed,proof=distance(g,shifted,budget_bytes=limit,batch=16,shard_queries=True)
 exact,_=distance(g,shifted,batch=16)
 assert observed==exact==g.hausdorff_distance(shifted)
 for direction in ('forward','reverse'):
  p=proof[direction]
  assert p['vertices']==len(g.exterior.coords)
  assert p['target_index_shards']>1
  assert p['charged_index_bytes']+p['vertices']*16+p['batch_vertices']*p['maximum_shard_targets']*32<=limit


def test_target_index_streams_without_changing_full_distance():
 from shapely.geometry import GeometryCollection, LineString
 a=GeometryCollection([Point(0,0).buffer(1,quad_segs=150),Point(8,4)])
 b=GeometryCollection([translate(a.geoms[0],xoff=.001),LineString([(8,4),(8.25,4)])])
 limit=85000
 with pytest.raises(ValueError,match='INDEX_BUDGET_EXCEEDED'):
  distance(a,b,budget_bytes=limit,batch=16)
 observed,proof=distance(a,b,budget_bytes=limit,batch=16,shard_queries=True)
 exact,_=distance(a,b,batch=16)
 assert observed==pytest.approx(exact,abs=1e-12)
 assert observed==pytest.approx(a.hausdorff_distance(b),abs=1e-12)
 for direction in ('forward','reverse'):
  assert proof[direction]['target_index_shards']>1
  assert proof[direction]['charged_index_bytes']<=limit
  assert proof[direction]['target_index_mode']=='ONE_RESIDENT_SHARD_COMPLETE_GEOS_NEAREST_REDUCTION'
