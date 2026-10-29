from dataclasses import replace
import pytest
from shapely.geometry import Point,LineString,box
from src.junction_spindle_stage import (CONTRACT,prepare_spindle_context,
 fit_spindle_blend,verify_spindle_batch,assemble_spindle_scene)


def context():
 trace=LineString([(0,0),(.5,0)]).buffer(.025)
 lands=[Point(0,0).buffer(.2,quad_segs=64),Point(.5,0).buffer(.2,quad_segs=64)]
 return prepare_spindle_context(trace,lands,box(-1,-1,2,1))


def test_land_sized_fit_and_assembly_preserve_exact_predecessor():
 owner,radius,window=context();snapshot=owner.wkb
 best,attempts=fit_spindle_blend(owner,radius,window,[])
 assert best is not None and best['scale']==1. and len(attempts)==1
 item=dict(id='first',owner=owner,addition=best['addition'],window=window,foreign=[])
 assert verify_spindle_batch([item])[0]['check']['passed']
 after=assemble_spindle_scene(owner,[item]);assert after.is_valid
 assert owner.wkb==snapshot and owner.difference(after).area<=1e-12
 assert after.area>owner.area+.01


def test_blocked_growth_retains_original_and_finite_attempts():
 owner,radius,window=context();snapshot=owner.wkb
 best,attempts=fit_spindle_blend(owner,radius,window,[('blocked',window)])
 assert best is None and len(attempts)==4 and owner.wkb==snapshot
 assert assemble_spindle_scene(owner,[]).equals(owner)


def test_final_repeat_rejects_later_patch_collision():
 owner,radius,window=context();best,_=fit_spindle_blend(owner,radius,window,[])
 a=dict(id='first',owner=owner,addition=best['addition'],window=window,foreign=[])
 b=dict(a,id='second')
 assert verify_spindle_batch([a])[0]['check']['passed']
 with pytest.raises(ValueError,match='FINAL_SPINDLE_CHECK_FAILED'):
  verify_spindle_batch([a,b])


def test_disconnected_owner_never_becomes_bridge():
 owner=Point(0,0).buffer(.1).union(Point(1,0).buffer(.1))
 best,attempts=fit_spindle_blend(owner,.5,box(-1,-1,2,1),[])
 assert best is None and all(a['error']=='ONE_CONNECTED_QUALIFIED_OWNER_REQUIRED' for a in attempts)


def test_policy_change_cannot_silently_weaken_clearance():
 owner,radius,window=context()
 with pytest.raises(ValueError,match='CONTRACT_CHANGED'):
  fit_spindle_blend(owner,radius,window,[],contract=replace(CONTRACT,construction_gap_mm=0))


def test_missing_qualified_land_rejected():
 with pytest.raises(ValueError,match='QUALIFIED_LANDS_REQUIRED'):
  prepare_spindle_context(box(0,0,1,1),[],box(-1,-1,2,2))
