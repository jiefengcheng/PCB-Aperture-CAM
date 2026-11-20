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

def test_owner_coverage_shortcut_and_positive_overlap_fallback(monkeypatch):
 from shapely import set_precision
 from shapely.geometry import LineString
 from shapely.geometry.base import BaseGeometry

 left=box(0,0,1,1)
 right=box(2,0,3,1)
 context=bind(dict(left=left,right=right))
 intersection=BaseGeometry.intersection
 calls=[]

 def record_intersection(owner,contribution,*args,**kwargs):
  calls.append(contribution)
  return intersection(owner,contribution,*args,**kwargs)

 monkeypatch.setattr(BaseGeometry,'intersection',record_intersection)
 tiny=Polygon([(0,0),(.000001,0),(0,.000001)])
 assert context.index.membership(tiny)==context.ids['left']
 assert not calls
 assert context.index.membership(LineString([(0,0),(1,0)]))==[]
 assert context.index.membership(box(1,0,2,1))==[]
 assert set(context.index.membership(box(.9,0,2.1,1)))==set(context.index.ids)
 fixed=set_precision(box(.1,.1,.2,.2),.01)
 assert context.index.membership(fixed)==context.ids['left']
 assert calls[-1] is fixed

def test_source_scalar_cap_remains_enforced():
 with pytest.raises(ValueError,match='SCALAR_OR_WIDTH_INVALID'):p.offset_part(box(0,0,1,.1),.1,1.500001)

def test_membership_batch_reuses_exact_operands_and_isolates_mutable_results(monkeypatch):
 from shapely import from_wkb,to_wkb
 from src.original_copper_owners import OriginalOwners
 a=box(0,0,1,1);b=box(2,0,3,1);source=MultiPolygon([a,b])
 donor=OriginalOwners(source);result=donor.memberships(dict(a=a,b=b))
 expected={sid:list(ids)for sid,ids in result.items()};result['a'].clear()
 fresh=OriginalOwners(from_wkb(to_wkb(source)))
 def forbidden(*args):raise AssertionError('identical membership recomputed')
 monkeypatch.setattr(fresh,'membership',forbidden)
 got=fresh.memberships(dict(a=from_wkb(to_wkb(a)),b=b),reuse=donor)
 assert got==expected
 got['b'].clear()
 assert fresh.memberships(dict(a=a,b=b),reuse=donor)==expected

def test_physical_bind_reuses_verified_functional_membership_batch(monkeypatch):
 from src.original_copper_owners import OriginalOwners
 from shapely import from_wkb,to_wkb
 a=box(0,0,1,1);b=box(2,0,3,1);source=MultiPolygon([a,b])
 originals=dict(a=a,b=b);donor=OriginalOwners(source)
 expected=donor.memberships(originals)
 def forbidden(*args):raise AssertionError('unchanged source batch recomputed')
 monkeypatch.setattr(OriginalOwners,'membership',forbidden)
 context=cc.bind(from_wkb(to_wkb(source)),'0'*64,originals,membership_from=donor)
 assert context.ids==expected and context.index is not donor
 context.ids['a'].clear()
 assert donor._source_memberships[1][0][1][1]  # Public maps do not own the cached witness.

@pytest.mark.parametrize('change',['operand','partition','precision','owner_order','owner_id'])
def test_membership_batch_invalidates_changed_geometry_or_partition(monkeypatch,change):
 from shapely import set_precision
 from src.original_copper_owners import OriginalOwners
 a=box(0,0,1,1);b=box(2,0,3,1);source=MultiPolygon([a,b]);originals=dict(a=a,b=b)
 donor=OriginalOwners(source);donor.memberships(originals)
 if change=='partition':source=box(0,0,3,1)
 if change=='precision':source=set_precision(source,.01)
 if change=='operand':originals=dict(a=box(.5,0,2.5,1),b=b)
 fresh=OriginalOwners(source)
 if change=='owner_order':fresh.ids.reverse();fresh.owners.reverse();from shapely import STRtree;fresh.tree=STRtree(fresh.owners)
 if change=='owner_id':fresh.ids[0]='different-owner'
 expected={sid:fresh.membership(g)for sid,g in originals.items()};calls=[];original=fresh.membership
 def record(g):calls.append(g);return original(g)
 monkeypatch.setattr(fresh,'membership',record)
 assert fresh.memberships(originals,reuse=donor)==expected
 assert len(calls)==(1 if change=='operand'else 2)

def test_membership_batch_does_not_confuse_same_wkb_with_changed_precision(monkeypatch):
 from shapely import from_wkb,to_wkb,set_precision,get_precision
 from src.original_copper_owners import OriginalOwners
 source=box(0,0,1,1);fixed=set_precision(box(.1,.1,.2,.2),.01)
 floating=from_wkb(to_wkb(fixed))
 assert to_wkb(fixed)==to_wkb(floating) and get_precision(fixed)!=get_precision(floating)
 donor=OriginalOwners(source);donor.memberships(dict(a=fixed));fresh=OriginalOwners(source)
 calls=[];original=fresh.membership
 def record(g):calls.append(g);return original(g)
 monkeypatch.setattr(fresh,'membership',record)
 assert fresh.memberships(dict(a=floating),reuse=donor)==dict(a=original(floating))
 assert len(calls)==1

def test_retained_future_foreign_copper_constrains_new_growth():
 a=box(0,0,1,1);b=box(1.2,0,2.2,1);context=bind(dict(a=a,b=b));other=context.owner('b',b);context.reserved={other:box(1.1,0,2.2,1)}
 q=PreparedLandScene([land('a',a,a)],[fixed('b',b)]).check([land('a',a,box(0,0,1.08,1))])
 assert not q['passed']

def test_core_reference_tampering_cannot_change_original_ownership(tmp_path):
 a=box(0,0,1,1);context=bind(dict(a=a));store=p.Store(tmp_path/'r');wrong=p.geomref(store,box(0,0,2,1))
 scene=dict(objects=[dict(source_id='a',original_ref=wrong,metadata={})])
 with pytest.raises(ValueError,match='CORE_REFERENCE_CHANGED'):context.register_scene(store,scene)


def test_candidate_union_digest_reuses_identical_operands_and_invalidates(monkeypatch):
 from types import SimpleNamespace
 from shapely import from_wkb,set_precision,to_wkb
 from shapely.geometry import box
 from src import component_clearance as cc
 from src.stage_abi.store import digest

 parent=SimpleNamespace()
 pad=box(0,0,1,1);other=box(2,0,3,1)
 original_join=cc.joined;calls=[]
 def traced(values):
  calls.append(1)
  return original_join(values)
 monkeypatch.setattr(cc,'joined',traced)
 initial=dict(pad=pad,other=other)
 expected=digest(to_wkb(original_join(initial.values())))
 assert cc.candidate_union_sha256(parent,initial)==expected
 assert cc.candidate_union_sha256(parent,dict(pad=from_wkb(to_wkb(pad)),other=other))==expected
 assert len(calls)==1
 for value in (dict(other=other,pad=pad),dict(other=other,pad=set_precision(pad,.01)),
               dict(other=other,pad=box(0,0,1.1,1))):
  assert cc.candidate_union_sha256(parent,value)==digest(to_wkb(original_join(value.values())))
 assert len(calls)==4


def test_prepared_disjoint_owner_skips_overlay_inside_a_hole(monkeypatch):
 from shapely.geometry import box
 from shapely.geometry.base import BaseGeometry
 from src.original_copper_owners import OriginalOwners

 ring=box(0,0,4,4).difference(box(1,1,3,3))
 index=OriginalOwners(ring)
 intersection=BaseGeometry.intersection
 calls=[]
 def observed(owner,other,*args,**kwargs):
  calls.append(other)
  return intersection(owner,other,*args,**kwargs)
 monkeypatch.setattr(BaseGeometry,'intersection',observed)
 assert index.membership(box(1.5,1.5,2,2))==[]
 assert not calls
 assert index.membership(box(1,1.5,2,2))==[]
 assert len(calls)==1
 assert index.membership(box(.9,1.5,2,2))==index.ids
 assert len(calls)==2
