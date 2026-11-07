"""Reference remedy must inherit T04 even in a fresh worker process."""
import pytest
from shapely.geometry import box
from src.gerber_u05 import pipeline as p
from src.gerber_u05.reference_recipe import initialize_reference_constraints
from src import t04_width_fence as width,pin_separation as pin
from src.growth_void_remedy_v09 import plan


@pytest.fixture(autouse=True)
def isolated_rules(monkeypatch):
 monkeypatch.setattr(width,'ACTIVE',None);monkeypatch.setattr(pin,'ACTIVE',None)


def fixture(store,*,frozen=True):
 # One original owner, two newly created notches. One is denied widening;
 # the unrelated other notch remains a permissible local repair.
 source=box(0,0,4,.1)
 first=box(0,0,1,.2).difference(box(.48,.18,.52,.21))
 second=box(3,0,4,.2).difference(box(3.48,.18,3.52,.21))
 current=source.union(first).union(second)
 forbidden=box(.479,.179,.521,.201)
 rule=width.Rule(forbidden,source,'bound-original-route-decisions')
 scene=dict(lineage=[dict(stage='t04',**({'t04_width_fence':rule.state(store)}if frozen else{}))])
 binding=dict(source_ref={'artifact_id':'gerber-source:'+'0'*64,'sha256':'0'*64})
 return source,current,scene,binding


def test_fresh_reference_rejects_entire_denied_fill_and_keeps_unrelated_repair(tmp_path):
 store=p.Store(tmp_path/'runtime');source,current,scene,binding=fixture(store)
 # Reproduce the omission: fresh worker has no active width rule.
 old_report,old_fills,_=plan(source,current)
 assert any(f['geometry'].centroid.x<1 for f in old_fills)
 receipt=initialize_reference_constraints(store,binding,source,{'objects':[]},scene)
 assert receipt['frozen_t04_width_binding']=='bound-original-route-decisions'
 report,fills,result=plan(source,current)
 assert not any(f['geometry'].centroid.x<1 for f in fills)
 assert any(f['geometry'].centroid.x>3 for f in fills)
 rejected=[r for r in report['records']if r['status']=='KEEP_PROTECTED_PIN_SEPARATION']
 assert rejected and any(not r['check']['t04_width_decision']['passed']for r in rejected)
 assert result.intersection(box(.48,.18,.52,.21)).area==0


def test_reference_without_source_bound_frozen_rule_halts(tmp_path):
 store=p.Store(tmp_path/'runtime');source,current,scene,binding=fixture(store,frozen=False)
 with pytest.raises(ValueError,match='REFERENCE_FROZEN_T04_WIDTH_RULE_REQUIRED'):
  initialize_reference_constraints(store,binding,source,{'objects':[]},scene)


def test_independently_qualified_existing_joint_is_not_new_remedy_growth(tmp_path):
 store=p.Store(tmp_path/'runtime');source,current,scene,binding=fixture(store)
 initialize_reference_constraints(store,binding,source,{'objects':[]},scene)
 existing_joint=current.union(box(.48,.18,.52,.195))
 # Re-encoding that same already-qualified predecessor adds no material.
 assert width.ACTIVE.remedy(existing_joint,existing_joint)['passed']
 assert not width.ACTIVE.remedy(existing_joint,current)['passed']
