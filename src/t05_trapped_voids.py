"""Reject junction closures whose complete pocket cannot satisfy frozen rules."""
from .growth_void_remedy_v09 import holes,joined
from .pcb_data_abi.geometry import POLYGON_TOLERANCE_MM
from .stage_abi.store import digest
from shapely import to_wkb


def check(owner,candidate,remedy_rule,*,area_epsilon_mm2):
 old=joined(holes(owner));records=[];failed=[]
 for hole in holes(candidate):
  if hole.intersection(old).area>area_epsilon_mm2:continue
  if hole.buffer(-POLYGON_TOLERANCE_MM).is_empty:continue
  proof=remedy_rule(hole,owner)
  row=dict(hole_sha256=digest(to_wkb(hole)),area_mm2=hole.area,bounds_mm=list(hole.bounds),complete_fill_constraint=proof)
  records.append(row)
  if proof is not None and not proof['passed']:failed.append(row)
 return dict(passed=not failed,new_resolvable_pockets=records,blocked_pockets=failed,
             basis='Whole candidate closure and whole logical pocket; no clipped fill, radius retry or representation exemption')
