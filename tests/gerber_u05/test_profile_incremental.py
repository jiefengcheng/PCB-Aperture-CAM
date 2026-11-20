from pathlib import Path
import importlib.util
from shapely import to_wkb
from shapely.geometry import LineString
from shapely.ops import unary_union
from src.gerber_u05.profile_refinement import plan,body_at,contains_floor
from src.gerber_u05.limiting_math import GUARD,MARGIN
spec=importlib.util.spec_from_file_location('ref_test',Path(__file__).with_name('test_profile_refinement.py'));ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)


def test_corridor_supplement_fills_space_while_preserving_every_saved_outer_shape(tmp_path):
 rows,original,ctx,settings,rule=ref.example(tmp_path);rule['incremental_corridor_fill']=True
 chosen,data,cores,receipt=plan(rows,original,original,{'a':['a'],'b':['b']},{},ctx,settings,rule)
 assert receipt['incremental_corridor_fill'] and not receipt['baseline_reference']['proof_reuse']
 section=LineString([(.5,-.2),(.5,.2)])
 assert chosen['a']['body'].intersection(section).length>.06+1e-6
 for r in chosen:
  p=receipt['route_plans'][r];floor=data[r]['baseline_body']
  for f in (1.2,1.3,1.4,1.5):
   g=body_at(cores[r],.05,p,data[r],f);assert contains_floor(g,floor)
   assert g.difference(cores[r].buffer((.075-.05)/2,quad_segs=128)).area<1e-12
  assert body_at(cores[r],.05,p,data[r],1.2).equals_exact(floor,0)
 assert chosen['a']['body'].distance(chosen['b']['body'])>=GUARD+2*MARGIN-1e-12


def test_same_owner_does_not_hide_noncontact_parallel_branches(tmp_path):
 rows,original,ctx,settings,rule=ref.example(tmp_path);rule['incremental_corridor_fill']=True
 from shapely.affinity import translate
 import json,hashlib
 from src.gerber_u05.translated_profile import profile_body
 from shapely.geometry import Polygon
 original['b']=translate(original['b'],yoff=-.01);rows['b']['metadata']['route_points_mm']=[(x,y-.01) for x,y in rows['b']['metadata']['route_points_mm']]
 seed_path=Path(rule['baseline_seed']);seed=json.loads(seed_path.read_bytes());line=LineString(rows['b']['metadata']['route_points_mm']);body=profile_body(original['b'],.05,.06,.066,(0.,0.),line,Polygon());seed['routes']['b']['body_sha256']=hashlib.sha256(to_wkb(body)).hexdigest();seed_path.write_text(json.dumps(seed));rule['baseline_seed_sha256']=hashlib.sha256(seed_path.read_bytes()).hexdigest()
 ctx.ids={'a':('shared',),'b':('shared',)};ctx.cores={'shared':unary_union(list(original.values()))}
 chosen,data,cores,receipt=plan(rows,original,original,{'a':['a'],'b':['b']},{},ctx,settings,rule)
 assert receipt['protected_same_owner_reservations']>0
 assert chosen['a']['body'].distance(chosen['b']['body'])>=GUARD+2*MARGIN-1e-12
 assert all(contains_floor(chosen[r]['body'],data[r]['baseline_body']) for r in chosen)


def test_saved_10_floor_cannot_be_reduced_even_below_its_progress_rung(tmp_path,monkeypatch):
 import pytest,json
 from types import SimpleNamespace
 from shapely.geometry import box
 from src.gerber_u05.pipeline import Store
 import src.gerber_u05.motion_final_validation as gate
 old=box(0,0,.01,1);foreign=box(.06,0,.07,1)
 ctx=SimpleNamespace(cores={'A':old,'B':foreign},ids={'r':('A',),'fixed':('B',)},frame_ids=())
 monkeypatch.setattr(gate.sc,'ACTIVE',ctx);monkeypatch.setattr(gate.p,'operands',lambda *a:({}, {'r':old,'fixed':foreign},{}))
 obj=SimpleNamespace(before_owners={'A':old,'B':foreign},paths={'r':['member']},receipt={'route_owners':{'r':'A'}},chosen={'r':{'pose':(0.,0.)}},data={'r':{'baseline_body':old.buffer(.005)}},oldcores={'r':old},route=lambda *a:old,rows={},input_current={},original={},source_owner_ids={})
 store=Store(tmp_path/'runtime');result=dict(output_scene_ref=store.put_json('scene',{}),solution={'selected_scales':{'r':1.1}},limiting_construction={'source_sha256':'a'*64})
 with pytest.raises(ValueError,match='TRANSLATED_FULL_SCENE_REJECTED'):gate.verify(store,result,obj)
 proof=json.loads(next((store.root/'artifacts').glob('t04-motion-final-validation:*')).read_bytes())
 assert all(x['reason']=='REFERENCE_10_PERCENT_COPPER_REGRESSED' for x in proof['failures'])


import pytest

def test_unaccepted_source_corridor_can_be_reduced_before_becoming_a_floor(tmp_path,monkeypatch):
 from types import SimpleNamespace
 from shapely.geometry import box
 from src.gerber_u05.pipeline import Store
 import src.gerber_u05.motion_final_validation as gate
 old=box(0,0,.01,1);foreign=box(.06,0,.07,1)
 ctx=SimpleNamespace(cores={'A':old,'B':foreign},ids={'r':('A',),'fixed':('B',)},frame_ids=())
 monkeypatch.setattr(gate.sc,'ACTIVE',ctx)
 monkeypatch.setattr(gate.p,'operands',lambda *a:({}, {'r':old,'fixed':foreign},{}))
 proposal=dict(construction_floor_profile=dict(factor=1.2))
 obj=SimpleNamespace(before_owners={'A':old,'B':foreign},paths={'r':['member']},
   receipt={'route_owners':{'r':'A'},'standalone_profile':True,'route_plans':{'r':proposal}},
   chosen={'r':{'pose':(0.,0.)}},data={'r':{'baseline_body':old.buffer(.005)}},
   oldcores={'r':old},route=lambda *a:old,rows={},input_current={},original={},source_owner_ids={})
 store=Store(tmp_path/'runtime')
 result=dict(output_scene_ref=store.put_json('scene',{}),solution={'selected_scales':{'r':1.1}},limiting_construction={'source_sha256':'a'*64})
 proof=gate.verify(store,result,obj)
 assert proof['passed'] and len(proof['source_corridor_proposals_reduced_by_native_ladder'])==1
 # Once accepted, that same geometry becomes unconditional, even below a rung.
 obj.receipt['standalone_profile']=False
 with pytest.raises(ValueError,match='TRANSLATED_FULL_SCENE_REJECTED'):gate.verify(store,result,obj)

@pytest.mark.skipif(not __import__('os').environ.get('T04_PROFILE_OVERLAY_FIXTURES'), reason='saved GEOS overlays require an explicit external fixture directory')
@pytest.mark.parametrize('name',['JR-a4ee6940ca532acb_1.5','JR-a68daff19410fc4f_1.5'])
def test_real_saved_mixed_overlay_becomes_finite_copper_without_losing_the_floor(name):
 from shapely import from_wkb
 from src.gerber_u05.finite_profile_union import certified_union,polygonal
 root=Path(__import__('os').environ['T04_PROFILE_OVERLAY_FIXTURES']);old=from_wkb((root/(name+'.wkb')).read_bytes());floor=from_wkb((root/(name+'_floor.wkb')).read_bytes());ext=from_wkb((root/(name+'_extension.wkb')).read_bytes())
 assert old.geom_type=='GeometryCollection' and old.is_valid
 assert polygonal(old).area==old.area
 new,method=certified_union(floor,ext)
 assert new.geom_type in ('Polygon','MultiPolygon') and new.is_valid and contains_floor(new,floor)
 assert new.area>floor.area and method!='EXACT_FLOOR_FALLBACK'


def test_finite_extraction_preserves_holes_and_discards_only_lines_and_points():
 from shapely.geometry import Point,GeometryCollection,Polygon
 from src.gerber_u05.finite_profile_union import polygonal
 copper=Polygon([(0,0),(3,0),(3,3),(0,3)],holes=[[(1,1),(1,2),(2,2),(2,1)]])
 mixed=GeometryCollection([copper,LineString([(4,4),(5,5)]),Point(6,6)]);finite=polygonal(mixed)
 assert finite.equals_exact(copper,0) and len(finite.interiors)==1 and finite.area==mixed.area
