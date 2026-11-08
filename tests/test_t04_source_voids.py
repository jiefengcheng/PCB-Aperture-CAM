from types import SimpleNamespace
import pytest
from shapely import STRtree
from shapely.geometry import box
from shapely.ops import unary_union
from src.component_hole_lineage import classify
from src.t04_topology import SourceVoids,check,characteristic


def prepared(source,routes,*,before=None,limit=16*1024**2):
 ids=sorted(routes);d=SimpleNamespace(owners=dict.fromkeys(ids,'o'),route_ids=ids,route_tree=STRtree([routes[s].buffer(2)for s in ids]),before={'o':source if before is None else before},ids=['o'],foreign={'o':source},tree=STRtree([source]),context=SimpleNamespace(cores={'o':source}),memo=lambda key,compute:compute())
 d.source_voids=SourceVoids(d,limit);return d


def cancellation():
 source=box(0,0,10,6).difference(box(2,2,3,3)).difference(box(6,2,10,3));route=box(1.9,3.11,9.2,3.12)
 candidate=unary_union([box(1.9,1.9,3.1,3.3),box(1.9,3.1,9.2,3.3),box(9,1.9,9.2,3.3)])
 return source,route,candidate


def test_source_hole_loss_cannot_cancel_a_new_pocket_in_the_euler_fast_path():
 source,route,candidate=cancellation();d=prepared(source,{'r':route})
 assert characteristic(source.intersection(candidate))==characteristic(candidate)
 assert characteristic(source)==characteristic(source.union(candidate))
 assert any(not r['source_hole_survives']for r in classify(source,source.union(candidate))['source_holes'])
 q=check(d,'r',1.5,candidate,{'r':route},{'r':1.})
 assert not q['passed']and q['failures'][0]['reason']=='ORIGINAL_SOURCE_ROUTE_VOID_REMOVED'


def test_normal_integral_widening_and_partial_hole_narrowing_are_allowed():
 source=box(0,0,5,5).difference(box(2,2,3,3));route=box(1.7,1.7,1.9,3.3);d=prepared(source,{'r':route});candidate=box(1.6,1.6,2.5,3.4)
 q=check(d,'r',1.5,candidate,{'r':route},{'r':1.})
 assert q['passed'];assert d.source_voids.complete({'r':candidate},{'r':1.5})['passed']
 # An existing pad/trace overlap is part of the same baseline, with no internal gap.
 assert candidate.intersection(source).area>0


def test_accepted_neighbour_growth_is_included_and_invalidated_by_its_version():
 source=box(0,0,5,5).difference(box(2,2,3,3));routes={'r':box(3,1.9,3.1,3.1),'s':box(1.9,1.9,2,3.1)};d=prepared(source,routes);candidate=box(2.5,1.9,3.2,3.1);current=dict(routes,s=box(1.8,1.9,2.5,3.1))
 assert d.source_voids.check('r',candidate,current,{'r':1.,'s':1.})['passed']
 q=d.source_voids.check('r',candidate,current,{'r':1.,'s':1.5})
 assert not q['passed'];assert q['checked_holes']==1


def test_minimum_grid_source_hole_cannot_be_discarded_by_area_epsilon():
 source=box(0,0,1,1).difference(box(.5,.5,.500001,.500001));route=box(.49,.49,.5,.5);d=prepared(source,{'r':route});candidate=box(.49,.49,.51,.51)
 assert d.source_voids.records[0]['opening'].area<1.01e-12
 assert not d.source_voids.check('r',candidate,{'r':route},{'r':1.})['passed']


def test_complete_scene_rechecks_all_source_holes_without_a_proposal_fast_path():
 source,route,candidate=cancellation();d=prepared(source,{'r':route})
 q=d.source_voids.complete({'r':candidate},{'r':1.5})
 assert not q['passed']and q['checked_holes']==q['source_holes']==1


def test_missing_stage_entry_void_is_rejected_instead_of_normalized_away():
 source,route,candidate=cancellation()
 with pytest.raises(ValueError,match='SOURCE_VOID_MISSING_AT_STAGE_ENTRY'):
  prepared(source,{'r':route},before=source.union(candidate))


def test_prepared_source_hole_index_cannot_exceed_its_existing_dependency_budget():
 source,route,_=cancellation()
 with pytest.raises(ValueError,match='SOURCE_VOID_INDEX_MEMORY_BUDGET_EXCEEDED'):
  prepared(source,{'r':route},limit=1)
