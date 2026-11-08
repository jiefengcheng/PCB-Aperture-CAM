from shapely.geometry import box
from src.t05_trapped_voids import check


def shapes():
 slot=box(1,1,4,2);owner=box(0,0,5,3).difference(box(1,1,6,2));candidate=owner.union(box(4,0,5,3));return owner,candidate,slot


def test_new_closed_pocket_rejects_complete_proposal_when_fill_is_frozen():
 owner,candidate,slot=shapes();calls=[]
 def rule(hole,before):
  calls.append(hole);assert hole.equals(slot) and before.equals(owner)
  return dict(passed=False,reason='T04_FROZEN_WIDENING_DECISION')
 result=check(owner,candidate,rule,area_epsilon_mm2=1e-12)
 assert not result['passed'] and len(calls)==1 and len(result['blocked_pockets'])==1


def test_existing_hole_is_not_a_new_junction_closure():
 owner,candidate,_=shapes()
 def forbidden(*args):raise AssertionError('Existing hole must not be reclassified')
 assert check(candidate,candidate,forbidden,area_epsilon_mm2=1e-12)['passed']


def test_fillable_closure_does_not_disable_normal_junction_growth():
 owner,candidate,_=shapes();result=check(owner,candidate,lambda h,b:dict(passed=True),area_epsilon_mm2=1e-12)
 assert result['passed'] and len(result['new_resolvable_pockets'])==1
