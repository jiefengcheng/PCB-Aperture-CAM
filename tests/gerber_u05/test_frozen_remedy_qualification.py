from dataclasses import asdict
import pytest
from shapely.geometry import box
from src.gerber_u05 import pipeline as p
from src.gerber_u05.qualification_tail import required_coverage
from src.component_voids import RemedyContract

def case(tmp_path):
 store=p.Store(tmp_path/'runtime');contracts=[RemedyContract(notch_radius_mm=r)for r in(.04,.08,.16,.32)]
 logical=box(0,0,1,1);fill=dict(source_id='selected-owner-update',original_owner_id='owner',logical_patch_ref=p.geomref(store,logical))
 value=dict(intra=dict(rounds=[dict(radius_mm=c.notch_radius_mm,plan=dict(contract=asdict(c)))for c in contracts],fills=[fill]))
 return store,contracts,logical,value

def test_all_selected_repairs_are_covered_without_demanding_further_growth(tmp_path):
 store,contracts,logical,value=case(tmp_path)
 result=required_coverage(store,{'t04':value,'t05':value},{'owner':logical},contracts)
 assert result['passed'] and result['planned_owner_surface_updates']==2
 assert all(r['missing_area_mm2']==0 for r in result['records'])

def test_a_real_missing_pocket_still_fails(tmp_path):
 store,contracts,logical,value=case(tmp_path)
 actual=logical.difference(box(.4,.4,.6,.6))
 with pytest.raises(ValueError,match='NATIVE_REQUIRED_POCKET_OR_NOTCH_MISSING'):
  required_coverage(store,{'t05':value},{'owner':actual},contracts)

def test_foreign_copper_cannot_substitute_for_the_selected_owner(tmp_path):
 store,contracts,logical,value=case(tmp_path)
 with pytest.raises(ValueError,match='ORIGINAL_OWNER_MISSING'):
  required_coverage(store,{'t05':value},{'foreign':logical},contracts)

def test_repeated_or_missing_round_is_not_the_frozen_policy(tmp_path):
 store,contracts,logical,value=case(tmp_path)
 value['intra']['rounds'].append(value['intra']['rounds'][0])
 with pytest.raises(ValueError,match='FROZEN_ROUND_ORDER_CHANGED'):
  required_coverage(store,{'t05':value},{'owner':logical},contracts)
