import copy,hashlib,math
import numpy as np
import pytest
from shapely import to_wkb
from shapely.geometry import LineString,box
from src.gerber_u05.side_profile import allocate,taper,build as upper_mask,retain,verify_recipe,actual_widths,SCHEMA


def build(floor,recipe,progress):
 # An upper proposal is deliberately untrusted until exact floor inclusion.
 upper=upper_mask(floor,recipe,progress)
 return retain(floor,upper.difference(floor))[0]


def example():
 core=LineString([(0,0),(1,0)]).buffer(.025,quad_segs=128);floor=LineString([(0,0),(1,0)]).buffer(.03,quad_segs=128)
 cell=dict(source_id='stroke',a=[.1,0],b=[.9,0],normal=[0,1],base=[.03,.03,.03,.03],extra=[0,.0145,0,.0145])
 recipe=dict(schema=SCHEMA,source_core_sha256=hashlib.sha256(to_wkb(core)).hexdigest(),baseline_body_sha256=hashlib.sha256(to_wkb(floor)).hexdigest(),source_width_mm=.05,maximum_width_mm=.075,cells=[cell]);return core,floor,recipe


def test_crowded_face_stays_and_open_face_uses_shared_total_budget():
 core,floor,recipe=example();body=build(floor,recipe,1)
 assert body.covers(floor) and body.covers(core)
 section=body.intersection(LineString([(.5,-.1),(.5,.1)]))
 assert section.bounds[3]==pytest.approx(.03) and section.bounds[1]==pytest.approx(-.0445)
 assert section.length==pytest.approx(.0745)
 assert verify_recipe(recipe,core,.05,.06,.075,floor,body,1)['passed']
 assert actual_widths(floor,body,recipe,.075)['passed']


def test_progress_never_spends_retained_copper():
 core,floor,recipe=example();last=floor
 for t in (0,.2,.4,.6,.8,1):
  body=build(floor,recipe,t);assert body.covers(floor) and body.covers(last);last=body


def test_two_faces_share_one_cap_and_cannot_each_take_the_full_budget():
 core,floor,recipe=example();recipe['cells'][0]['extra']=[.0145,.0145,.0145,.0145];body=build(floor,recipe,1)
 with pytest.raises(ValueError,match='TWO_FACE_WIDTH_CAP'):verify_recipe(recipe,core,.05,.06,.075,floor,body,1)
 assert not actual_widths(floor,body,recipe,.075)['passed']


def test_removed_floor_and_added_outside_recipe_are_both_rejected():
 core,floor,recipe=example();body=build(floor,recipe,1)
 with pytest.raises(ValueError,match='ACCEPTED_COPPER_REMOVED'):verify_recipe(recipe,core,.05,.06,.075,floor,body.difference(box(.3,.028,.4,.04)),1)
 with pytest.raises(ValueError,match='OUTSIDE_CERTIFIED_CELLS'):verify_recipe(recipe,core,.05,.06,.075,floor,body.union(box(.4,-.05,.5,-.04)),1)


def test_source_centerline_binding_and_cell_normal_cannot_drift():
 core,floor,recipe=example();body=build(floor,recipe,1);recipe['source_core_sha256']='0'*64
 with pytest.raises(ValueError,match='INPUT_BINDING_CHANGED'):verify_recipe(recipe,core,.05,.06,.075,floor,body,1)
 core,floor,recipe=example();recipe['cells'][0]['normal']=[1,0]
 with pytest.raises(ValueError,match='CENTERLINE_CELL_CHANGED'):verify_recipe(recipe,core,.05,.06,.075,floor,body,1)


def test_larger_gap_gets_the_extra_and_transitions_do_not_raise_any_allowance():
 assert allocate(.015,0,.04)==pytest.approx((0,.015))
 assert allocate(.015,.04,0)==pytest.approx((.015,0))
 values=np.full(21,.015);values[10]=.001;s=np.linspace(0,.2,21);v=taper(values,s,.025)
 assert v[0]==v[-1]==0 and np.all(v<=values) and v[10]==.001
 assert np.max(np.abs(np.diff(v))/np.diff(s))<=.5+1e-12


def test_curved_source_keeps_its_centerline_with_an_outer_face_supplement():
 theta=np.linspace(0,math.pi/2,80);pts=np.column_stack([.5*np.cos(theta),.5*np.sin(theta)]);line=LineString(pts);core=line.buffer(.025,quad_segs=128);floor=line.buffer(.03,quad_segs=128);cells=[]
 for a,b in zip(pts,pts[1:]):
  d=b-a;n=np.array([-d[1],d[0]])/np.linalg.norm(d);cells.append(dict(source_id='arc',a=a.tolist(),b=b.tolist(),normal=n.tolist(),base=[.03]*4,extra=[0,.014,0,.014]))
 recipe=dict(schema=SCHEMA,source_core_sha256=hashlib.sha256(to_wkb(core)).hexdigest(),baseline_body_sha256=hashlib.sha256(to_wkb(floor)).hexdigest(),source_width_mm=.05,maximum_width_mm=.075,cells=cells);body=build(floor,recipe,1)
 assert verify_recipe(recipe,core,.05,.06,.075,floor,body,1)['passed'] and actual_widths(floor,body,recipe,.075)['passed']


def test_side_progress_does_not_reinterpret_the_total_width_cap_as_a_radius():
 from src.gerber_u05.profile_refinement import band_at
 plan=dict(side_specific_profile=True,corridor_width_mm=.06,outer_width_ceiling_mm=.075)
 assert all(band_at(plan,f)==(.06,.075)for f in (1,1.1,1.2,1.3,1.4,1.5))


def test_cached_width_witness_is_invalidated_by_changed_copper_or_cap():
 core,floor,recipe=example();body=build(floor,recipe,1)
 assert actual_widths(floor,body,recipe,.075)['passed']
 assert verify_recipe(recipe,core,.05,.06,.075,floor,body,1)['passed']
 corrupted=body.union(box(.4,-.06,.6,-.04))
 assert not actual_widths(floor,corrupted,recipe,.075)['passed']
 with pytest.raises(ValueError,match='OUTSIDE_CERTIFIED_CELLS'):verify_recipe(recipe,core,.05,.06,.075,floor,corrupted,1)
 assert not actual_widths(floor,body,recipe,.065)['passed']


def test_untrusted_upper_is_never_the_accepted_floor_authority():
 core,floor,recipe=example();raw=upper_mask(floor,recipe,1)
 accepted,_=retain(floor,raw.difference(floor))
 assert accepted.covers(floor)
 # Damaging a boundary remains a rejection after a positive cached witness.
 verify_recipe(recipe,core,.05,.06,.075,floor,accepted,1)
 with pytest.raises(ValueError,match='ACCEPTED_COPPER_REMOVED'):
  verify_recipe(recipe,core,.05,.06,.075,floor,accepted.difference(box(.2,.029,.3,.04)),1)


def test_unbound_inherited_sections_must_receive_no_added_material():
 from shapely.geometry import MultiPolygon
 floor=box(0,-.03,.4,.03).union(box(.6,-.03,1,.03))
 recipe=dict(cells=[dict(a=[.1,0],b=[.9,0],normal=[0,1],base=[.03]*4,extra=[0,.014,0,.014])])
 safe=floor.union(box(.1,-.04,.2,-.02))
 assert actual_widths(floor,safe,recipe,.075)['passed']
 unsafe=safe.union(box(.48,-.02,.52,.02))
 q=actual_widths(floor,unsafe,recipe,.075)
 assert not q['passed'] and any(x['reason']=='SIDE_PROFILE_NORMAL_SECTION_MISSING'for x in q['failures'])


def test_width_witness_refuses_missing_floor_and_handles_identical_sections():
 core,floor,recipe=example();body=build(floor,recipe,1)
 assert actual_widths(floor,body,recipe,.075)['passed']
 damaged=body.difference(box(.2,.02,.3,.04))
 assert not actual_widths(floor,damaged,recipe,.075)['passed']
 assert actual_widths(floor,body,recipe,.075)['passed']


def test_overlapping_legal_one_face_cells_cannot_spend_the_cap_twice():
 from src.gerber_u05.side_profile import finish_supplement
 core,floor,recipe=example()
 recipe['cells'][0]['extra']=[.0145,0,.0145,0]
 other=copy.deepcopy(recipe['cells'][0]);other.update(a=[.9,0],b=[.1,0],normal=[0,-1])
 recipe['cells'].append(other)
 upper=upper_mask(floor,recipe,1.)
 assert not actual_widths(floor,upper,recipe,.075)['passed']
 body,extension,method,proof,rejected=finish_supplement(floor,upper.difference(floor),recipe,.075)
 assert proof['passed'] and rejected and body.covers(floor)
 assert actual_widths(floor,body,recipe,.075)['passed']


def test_a_second_optional_rejection_falls_back_to_the_exact_floor(monkeypatch):
 import src.gerber_u05.side_profile as profile
 core,floor,recipe=example();upper=upper_mask(floor,recipe,1.)
 original=profile.actual_widths
 def reject_optional(base,body,recipe,high):
  if body.equals_exact(base,0):return original(base,body,recipe,high)
  return dict(passed=False,failures=[dict(reason='SIDE_PROFILE_ACTUAL_SECTION_OVER_CAP')],sections=1)
 monkeypatch.setattr(profile,'actual_widths',reject_optional)
 body,extension,method,proof,rejected=profile.finish_supplement(floor,upper.difference(floor),recipe,.075)
 assert body.equals_exact(floor,0) and extension.is_empty and proof['passed']
 assert method=='EXACT_FLOOR_AFTER_FINITE_CAP_REJECTION' and len(rejected)==2
 monkeypatch.setattr(profile,'actual_widths',lambda *a:dict(passed=False,failures=[dict(reason='CORRUPT_FLOOR')]))
 with pytest.raises(ValueError,match='ACCEPTED_FLOOR_WIDTH_REJECTED'):
  profile.finish_supplement(floor,extension,recipe,.075)


def test_original_keep_does_not_invent_copper_in_the_checking_envelope():
 from shapely.geometry import Polygon
 from src.gerber_u05.side_profile import body_at
 core,floor,recipe=example()
 plan=dict(progress_cap=1.5)
 data=dict(baseline_body=core,maximum_body=core,allowed_extension=Polygon(),side_recipe=recipe,unchanged_source_keep=True)
 assert body_at(core,.05,plan,data,1.,envelope=True).equals_exact(core,0)
 assert body_at(core,.05,plan,data,1.5,envelope=True).equals_exact(core,0)
 # A grown/translated floor still needs the complete halo even at progress 1.
 data.update(baseline_body=floor,maximum_body=floor,unchanged_source_keep=False)
 assert body_at(core,.05,plan,data,1.,envelope=True).covers(floor)
 assert not body_at(core,.05,plan,data,1.,envelope=True).equals_exact(floor,0)


def test_actual_side_growth_never_inherits_the_keep_envelope_exemption():
 from src.gerber_u05.side_profile import body_at
 core,floor,recipe=example();upper=upper_mask(floor,recipe,1.);body=retain(floor,upper.difference(floor))[0]
 data=dict(baseline_body=floor,maximum_body=body,allowed_extension=body.difference(floor),side_recipe=recipe,unchanged_source_keep=True)
 envelope=body_at(core,.05,dict(progress_cap=1.5),data,1.5,envelope=True)
 assert envelope.covers(body) and not envelope.equals_exact(body,0)
