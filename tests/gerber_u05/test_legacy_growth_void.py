import sys
from pathlib import Path
import pytest
from src.gerber_u05 import pipeline
from src.growth_void_remedy_v09 import plan,parts,holes,RemedyContract
from shapely.geometry import box
from shapely.ops import unary_union

def ring():return box(0,0,2,2).difference(box(.8,.8,1.2,1.2))
def open_ring():return ring().difference(box(.96,1.1,1.04,2.1))
def count(report,kind,status):return sum(r['kind']==kind and r['status']==status for r in report['records'])

def test_growth_closed_source_opening_is_filled():
 report,_,after=plan(open_ring(),ring())
 assert count(report,'hole','FILL')==1
 assert not holes(after)
 assert ring().difference(after).area<1e-12

def test_inherited_source_hole_is_retained_even_when_smaller():
 source=ring();grown=ring().buffer(.01)
 report,_,after=plan(source,grown)
 assert count(report,'hole','KEEP_SOURCE_VOID')==1
 assert count(report,'hole','FILL')==0
 assert after.difference(grown).intersection(box(.8,.8,1.2,1.2)).area<1e-12

def test_unchanged_source_notch_is_retained():
 source=open_ring();report,fills,after=plan(source,source)
 assert not fills
 assert after.equals(source)

def test_foreign_copper_in_pocket_is_not_bridged():
 island=box(.94,.94,1.06,1.06)
 source=unary_union([open_ring(),island]);current=unary_union([ring(),island])
 report,_,after=plan(source,current)
 assert count(report,'hole','FILL')==0
 assert any('FOREIGN_CLEARANCE_FAILED' in r.get('check',{}).get('reasons',[]) for r in report['records'])
 assert len(parts(after))==2

def test_preexisting_component_merge_is_rejected():
 source=box(0,0,1,1).union(box(1.2,0,2.2,1))
 with pytest.raises(ValueError,match='SOURCE_COMPONENT_MERGED_OR_UNBOUND'):plan(source,box(0,0,2.2,1))

def test_removed_source_is_rejected():
 with pytest.raises(ValueError,match='PREDECESSOR_SOURCE_COPPER_REMOVED'):plan(box(0,0,2,2),box(0,0,1,1))

def test_local_twenty_percent_shortage_is_enforced():
 # A thin outline must not become a solid sheet by treating its large void as
 # a small defect. Source gap is closed by growth but the pocket is too large.
 current=box(0,0,2,2).difference(box(.01,.01,1.99,1.99));source=current.difference(box(.9,1.9,1.1,2.1))
 report,_,after=plan(source,current)
 assert count(report,'hole','FILL')==0
 assert any('SHORTAGE_ABOVE_20_PERCENT' in r.get('check',{}).get('reasons',[]) for r in report['records'])
 assert holes(after)

def test_frozen_policy_rejects_gap_or_shortage_relaxation():
 with pytest.raises(ValueError,match='REMEDY_POLICY_OUT_OF_BOUND'):RemedyContract(maximum_shortage=.21).validate()
 with pytest.raises(ValueError,match='REMEDY_POLICY_OUT_OF_BOUND'):RemedyContract(construction_gap_mm=.039).validate()
 with pytest.raises(ValueError,match='INVALID_REMEDY_CONTRACT'):RemedyContract(notch_radius_mm=float('nan')).validate()

def test_reconstruction_is_deterministic():
 one,fills,a=plan(open_ring(),ring());two,other,b=plan(open_ring(),ring())
 assert one==two and a.equals_exact(b,0)
 assert [r['record_sha256']for r in fills]==[r['record_sha256']for r in other]


def test_context_collection_retains_all_surfaces_and_only_ignores_zero_area():
 from shapely.geometry import GeometryCollection,LineString
 from src.growth_void_remedy_v09 import surface_parts
 a=box(0,0,1,1);b=box(2,0,3,1)
 context=GeometryCollection([a,GeometryCollection([b,LineString([(1,0),(2,0)])])])
 assert sum(g.area for g in surface_parts(context))==2


def test_enclosed_pocket_has_boundary_authority_without_open_notch_permission():
 class NoOpenNotchPermission:
  def check(self,g):return dict(passed=False,missing_source_contact_support_mm2=g.area)
 report,_,after=plan(open_ring(),ring(),source_support=NoOpenNotchPermission())
 assert count(report,'hole','FILL')==1
 assert not holes(after)
 assert all(r['status']!='FILL'for r in report['records']if r['kind']=='notch')
