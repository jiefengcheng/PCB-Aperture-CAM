import pytest
from shapely.geometry import box
from shapely.ops import unary_union
from src.component_voids import plan,RemedyContract,holes,parts

def ring():return box(0,0,2,2).difference(box(.8,.8,1.2,1.2))
def opening():return ring().difference(box(.96,1.1,1.04,2.1))

def test_new_enclosed_pocket_is_filled_and_original_hole_is_kept():
 report,_,after=plan(opening(),ring())
 assert not holes(after)
 _,_,kept=plan(ring(),ring())
 assert len(holes(kept))==1

def test_unchanged_original_notch_is_preserved_without_clearance_ports():
 source=opening();_,fills,after=plan(source,source,RemedyContract(notch_radius_mm=.16))
 assert not fills and after.equals(source)

def test_geometry_radius_is_independent_of_universal_clearance():
 RemedyContract(notch_radius_mm=.16).validate()
 RemedyContract(notch_radius_mm=.64,maximum_notch_radius_mm=.64).validate()
 with pytest.raises(ValueError,match='POLICY_OUT_OF_BOUND'):RemedyContract(notch_radius_mm=.321).validate()

def test_foreign_copper_in_new_pocket_blocks_fill():
 island=box(.94,.94,1.06,1.06);source=unary_union([opening(),island]);current=unary_union([ring(),island]);r,_,after=plan(source,current)
 assert len(parts(after))==2 and any('FOREIGN_CLEARANCE_FAILED'in x.get('check',{}).get('reasons',[])for x in r['records'])

def test_twenty_percent_shortage_and_file_tolerances_remain_fixed():
 with pytest.raises(ValueError,match='POLICY_OUT_OF_BOUND'):RemedyContract(maximum_shortage=.21).validate()
 with pytest.raises(ValueError,match='FILE_POLICY_CHANGED'):RemedyContract(file_uncertainty_mm=.001).validate()

@pytest.mark.parametrize('foreign', [False, True])
def test_completion_memo_capacity_preserves_full_proof_and_geometry(foreign):
 from shapely import to_wkb
 island=box(.94,.94,1.06,1.06)
 source=unary_union([opening(),island])if foreign else opening()
 current=unary_union([ring(),island])if foreign else ring()
 reference,reference_fills,reference_after=plan(source,current,memo_bytes=0)
 for capacity in (None,64*1024**2,512*1024**2):
  report,fills,after=plan(source,current,memo_bytes=capacity)
  assert report==reference
  assert [to_wkb(r['geometry'])for r in fills]==[to_wkb(r['geometry'])for r in reference_fills]
  assert to_wkb(after)==to_wkb(reference_after)
  if foreign:
   assert any('FOREIGN_CLEARANCE_FAILED'in r.get('check',{}).get('reasons',[])for r in report['records'])
  else:assert fills and not holes(after)

def test_completion_rejects_invalid_memo_budget():
 with pytest.raises(ValueError,match='INVALID_BUDGET'):
  plan(opening(),ring(),memo_bytes=-1)
