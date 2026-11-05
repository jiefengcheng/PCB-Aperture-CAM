import pytest
from shapely.geometry import box,MultiPolygon,Polygon
from shapely.ops import unary_union
from src.gerber_u05 import pipeline as p
from src import component_clearance as cc
from src.prepared_land_scene import PreparedLandScene

def land(s,g,c):return dict(id=s,original=g,candidate=c,native_source_kind='gr_poly',native_stroke_width_mm=0.)
def fixed(s,g):return dict(id=s,geometry=g,trace_width_mm=0.)
def bind(originals):return cc.bind(unary_union(list(originals.values())),'0'*64,originals)

def test_connected_original_copper_has_no_internal_clearance():
 a=box(0,0,2,.1);b=box(0,.13,2,.23);end=box(0,0,.1,.23);bind(dict(a=a,b=b,end=end))
 trial=land('a',a,box(0,0,2,.11));q=PreparedLandScene([land('a',a,a)],[fixed('b',b),fixed('end',end)]).check([trial],materialize_scene=True)
 assert q['passed']and q['internal_clearance']=='NOT_APPLICABLE_SAME_ORIGINAL_OWNER'

def test_foreign_original_component_still_enforces_the_floor():
 a=box(0,0,1,1);b=box(1.1,0,2.1,1);bind(dict(a=a,b=b));trial=land('a',a,box(0,0,1.08,1));q=PreparedLandScene([land('a',a,a)],[fixed('b',b)]).check([trial])
 assert not q['passed']and q['failures'][0]['reason']=='NEW_COPPER_BELOW_FOREIGN_COMPONENT_GAP'

def test_two_simultaneous_growths_cannot_reclassify_their_bridge():
 a=box(0,0,1,1);b=box(1.1,0,2.1,1);bind(dict(a=a,b=b));base=[land('a',a,a),land('b',b,b)]
 q=PreparedLandScene(base,[]).check([land('a',a,box(0,0,1.06,1)),land('b',b,box(1.04,0,2.1,1))])
 assert not q['passed']and any(r['gap_mm']==0 for r in q['failures'])

def test_same_gerber_occurrence_does_not_merge_disconnected_islands():
 a=box(0,0,1,1);b=box(2,0,3,1);both=MultiPolygon([a,b]);context=bind(dict(a=a,multi=both))
 assert len(context.ids['multi'])==2
 q=PreparedLandScene([land('a',a,a)],[fixed('multi',both)]).check([land('a',a,box(0,0,2.01,1))])
 assert not q['passed']

def test_even_tiny_positive_source_core_cannot_be_removed():
 tiny=Polygon([(0,0),(.000001,0),(0,.000001)]);a=box(1,1,2,2);context=bind(dict(tiny=tiny,a=a))
 assert tiny.area<1e-12 and len(context.index.ids)==2
 q=PreparedLandScene([land('tiny',tiny,tiny)],[fixed('a',a)]).check([land('tiny',tiny,box(0,0,.0000001,.0000001))])
 assert not q['passed']and any(r['reason']=='ORIGINAL_TRACE_CORE_REMOVED'for r in q['failures'])

def test_source_scalar_cap_remains_enforced():
 with pytest.raises(ValueError,match='SCALAR_OR_WIDTH_INVALID'):p.offset_part(box(0,0,1,.1),.1,1.500001)

def test_retained_future_foreign_copper_constrains_new_growth():
 a=box(0,0,1,1);b=box(1.2,0,2.2,1);context=bind(dict(a=a,b=b));other=context.owner('b',b);context.reserved={other:box(1.1,0,2.2,1)}
 q=PreparedLandScene([land('a',a,a)],[fixed('b',b)]).check([land('a',a,box(0,0,1.08,1))])
 assert not q['passed']

def test_core_reference_tampering_cannot_change_original_ownership(tmp_path):
 a=box(0,0,1,1);context=bind(dict(a=a));store=p.Store(tmp_path/'r');wrong=p.geomref(store,box(0,0,2,1))
 scene=dict(objects=[dict(source_id='a',original_ref=wrong,metadata={})])
 with pytest.raises(ValueError,match='CORE_REFERENCE_CHANGED'):context.register_scene(store,scene)
