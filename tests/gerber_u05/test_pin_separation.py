import copy
import pytest
from shapely.geometry import box,Point
from shapely.affinity import rotate
from shapely import to_wkb
from src import pin_separation as pin
from src.stage_abi.store import ArtifactStore

def fixture(monkeypatch,angle=0):
 left=box(.2,0,.3,2);right=box(.4,0,.5,2);joint=Point(.25,1.5).buffer(.08,quad_segs=128);source=left.union(right).union(box(.2,1.9,.5,2.1)).union(joint);domain=box(.25,-.1,.45,1.8)
 transform=lambda g:rotate(g,angle,origin=(0,0))
 slot=pin.Slot('a'*64,'pair',('left','right'),transform(domain),transform(source),(transform(left),transform(right)),('original-pad-to-left-trace',))
 rule=pin.Rule([slot],construction_gap=.0401,finished_gap=.04);monkeypatch.setattr(pin,'ACTIVE',rule)
 return rule,slot,source,left,right,joint

@pytest.mark.parametrize('angle',[0,17,90])
def test_normal_widening_preserves_same_net_separation(monkeypatch,angle):
 rule,slot,source,left,right,joint=fixture(monkeypatch,angle);grown=source.union(left.buffer(.025)).union(right.buffer(.025));grown=rotate(grown,angle,origin=(0,0))
 assert rule.check(grown)['passed']
 assert grown.area>slot.source.area
 assert slot.source.geom_type=='Polygon' # The two pins are already connected remotely.

def test_asymmetric_widening_is_not_limited_by_a_fixed_center_stripe(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch);grown=source.union(left.buffer(.04)).union(right.buffer(.005))
 assert rule.check(grown)['passed']

@pytest.mark.parametrize('y',[.001,1.,1.749])
def test_bridge_anywhere_along_finger_or_transition_rejects(monkeypatch,y):
 rule,slot,source,left,right,joint=fixture(monkeypatch);bad=source.union(box(.29,y,.41,y+.001));proof=rule.check(bad)
 assert not proof['passed'] and 'PIN_BRANCH_LOCAL_BRIDGE'in proof['checks'][0]['failures']
 assert source.geom_type==bad.geom_type=='Polygon'

def test_excessive_widening_rejected_before_a_bridge_forms(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch);bad=source.union(left.buffer(.035)).union(right.buffer(.035));proof=rule.check(bad)
 assert not proof['passed']and 'PIN_BRANCH_SPACING'in proof['checks'][0]['failures']

def test_integral_joint_does_not_get_artificial_internal_clearance(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch);own_joint=box(.18,1.3,.32,1.6).union(joint)
 assert rule.check(source.union(own_joint))['passed']

def test_twenty_percent_or_same_net_cannot_approve_slot_fill(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch);fill=box(.299,.8,.401,.801)
 assert fill.area/source.union(fill).area<.20
 proof=rule.remedy(fill,source)
 assert not proof['passed']and proof['status']=='REJECT_ENTIRE_LOGICAL_FILL'
 assert not proof['fragments_accepted']

def test_entire_proposal_rejects_before_clipping_or_splitting(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch);bad=box(.29,.7,.41,.71);outside=box(.7,.7,.8,.8);logical=bad.union(outside)
 assert not rule.remedy(logical,source)['passed']
 assert not rule.remedy(outside,source)['passed'] # The outside fragment cannot bypass rejection.
 assert rule.remedy(box(2,2,2.01,2.01),source)['passed'] # An unrelated repair can proceed.

def test_rejected_fill_state_survives_next_stage_and_radius(tmp_path,monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch);logical=box(.29,.7,.41,.71).union(box(.7,.7,.8,.8));assert not rule.remedy(logical,source)['passed'];store=ArtifactStore(tmp_path/'runtime');state=rule.state(store)
 other=pin.Rule([slot],construction_gap=.0401,finished_gap=.04);other.restore(store,state)
 assert not other.remedy(box(.72,.72,.78,.78),source)['passed']
 changed=copy.deepcopy(state);changed['binding']='forged'
 with pytest.raises(ValueError,match='STATE_SOURCE_CHANGED'):other.restore(store,changed)

def test_microscopic_positive_fill_is_protected(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch);hole=box(.35,1,.3500001,1.0000001)
 assert 0<hole.area<1e-12 and not rule.remedy(hole,source)['passed']

def test_retained_bridged_result_is_rejected(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch)
 with pytest.raises(ValueError,match='PIN_SEPARATION_PRIOR_FAILED'):rule.require(source.union(box(.29,1,.41,1.01)),scope='prior')

def test_prepared_full_and_incremental_checks_agree(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch)
 class Parent:original=dict(left=left,right=right,fixed=source.difference(left.union(right)))
 parent=Parent();prepared=pin.Prepared(parent,rule)
 for amount in [0,.01,.02,.03,.04]:
  rows=[dict(id='left',candidate=left.buffer(amount)),dict(id='right',candidate=right.buffer(amount))]
  incremental=prepared.check(rows);complete=prepared.check(rows,materialize_scene=True)
  assert incremental['passed']==complete['passed']and incremental['checks']==complete['checks']
  assert incremental['complete_protected_slot_coverage']and prepared.weight<=prepared.limit

def test_prepared_context_cannot_be_reused_with_changed_source_rule(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch)
 class Parent:original=dict(left=left,right=right,fixed=source.difference(left.union(right)))
 prepared=pin.Prepared(Parent(),rule);monkeypatch.setattr(pin,'ACTIVE',None)
 with pytest.raises(ValueError,match='CONTEXT_CHANGED'):prepared.check([])

def test_prepared_eviction_retains_exact_pin_verdicts(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch)
 class Parent:original=dict(left=left,right=right,fixed=source.difference(left.union(right)))
 prepared=pin.Prepared(Parent(),rule)
 prepared.check([dict(id='left',candidate=left.buffer(.001)),dict(id='right',candidate=right)])
 prepared.limit=prepared.weight*2+32
 for i in range(2,24):
  rows=[dict(id='left',candidate=left.buffer(i*.001)),dict(id='right',candidate=right)]
  cached=prepared.check(rows);fresh=pin.Prepared(Parent(),rule).check(rows,materialize_scene=True)
  assert cached['passed']==fresh['passed'] and cached['checks']==fresh['checks']
  assert 0<=prepared.weight<=prepared.limit
 assert len(prepared.cache)<23

def test_source_domain_must_distinguish_original_branches(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch)
 with pytest.raises(ValueError,match='NOT_LOCALLY_DISTINCT'):
  pin.Slot('a'*64,'invalid',('left','right'),box(.25,0,.45,2.1),source,(left,right))

def test_native_prior_above_finished_floor_is_not_required_to_regrow_guard(monkeypatch):
 rule,slot,source,left,right,joint=fixture(monkeypatch);a=left.buffer(.02998);b=right.buffer(.02998);fixed=source.difference(left.union(right))
 class Parent:original=dict(left=a,right=b,fixed=fixed)
 prepared=pin.Prepared(Parent(),rule)
 assert prepared.check([dict(id='left',candidate=a),dict(id='right',candidate=b)],materialize_scene=True)['passed']
 assert not prepared.check([dict(id='left',candidate=left.buffer(.02999)),dict(id='right',candidate=b)])['passed']

@pytest.mark.parametrize('implementation',['incremental','dependency'])
def test_incremental_width_search_checks_pin_dependencies_before_accepting(monkeypatch,implementation):
 from src.u03_board.checker import IncrementalWidthScene
 from src.u03_board.dependency import DependencyWidthScene
 rule,slot,source,left,right,joint=fixture(monkeypatch)
 traces=[dict(id=s,original=g,candidate=g,verified_original_width_mm=.1)for s,g in [('left',left),('right',right)]]
 fixed=[dict(id='fixed',geometry=source.difference(left.union(right)),trace_width_mm=0.)]
 checker=(IncrementalWidthScene if implementation=='incremental'else DependencyWidthScene)(traces,fixed)
 for amount in [0,.02,.035,.02]:
  rows=[dict(r,candidate=r['original'].buffer(amount))for r in traces]
  incremental=checker.check(rows,fail_fast=True);complete=checker.check(rows,materialize_scene=True)
  assert incremental['passed']==complete['passed']
  assert incremental['pin_separation']['passed']==complete['pin_separation']['passed']
  if amount==.035:assert incremental['passing_state_sha256']is None


def test_joint_guard_shares_delta_without_sharing_rejection_verdict(monkeypatch):
 from src import t04_width_fence as width
 from src.growth_remedy_constraints import remedy

 pin_rule,slot,source,*_=fixture(monkeypatch)
 width_rule=width.Rule(slot.domain,source,'test')
 monkeypatch.setattr(width,'ACTIVE',width_rule)
 proposal=box(.28,.9,.42,1.0)
 first=remedy(proposal,source)
 assert not first['passed']
 assert pin_rule.rejected_count==1
 assert width_rule._overlays.stats['hits_difference']==1
 again=remedy(proposal,source)
 assert not again['passed']
 assert pin_rule.rejected_count==2
 assert any(row['reason']=='PREVIOUSLY_REJECTED_LOGICAL_FILL_FRAGMENT'
            for row in again['pin_separation']['reasons'])
 changed=source.union(box(.30,.9,.32,1.0))
 observed=remedy(proposal,changed)
 cold=width.Rule(slot.domain,source,'test').remedy(proposal,changed)
 assert observed['t04_width_decision']==cold
