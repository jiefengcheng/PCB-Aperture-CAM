import json,hashlib
from types import SimpleNamespace
import pytest
from shapely import to_wkb
from shapely.geometry import LineString,Polygon
from src.gerber_u05.translated_profile import profile_body
from src.gerber_u05.profile_refinement import band_at,body_at,plan

def test_band_reaches_frozen_profile_before_extending_and_respects_non_15_cap():
 p=dict(source_width_mm=.1,corridor_width_mm=.11,outer_width_ceiling_mm=.13,progress_cap=1.3,baseline_profile=dict(factor=1.2,corridor_width_mm=.11,outer_width_ceiling_mm=.121))
 assert band_at(p,1)==(.1,.1)
 assert band_at(p,1.2)==(.11,.121)
 assert band_at(p,1.3)==(.11,.13)

def test_every_extension_retains_the_complete_frozen_shape():
 line=LineString([(0,0),(1,0)]);core=line.buffer(.025,quad_segs=128);pose=(0.,.015)
 base=profile_body(core,.05,.06,.066,pose,line,Polygon());target=profile_body(core,.05,.06,.075,pose,line,Polygon())
 p=dict(source_width_mm=.05,corridor_width_mm=.06,outer_width_ceiling_mm=.075,translation_mm=list(pose),progress_cap=1.5,baseline_profile=dict(factor=1.2,corridor_width_mm=.06,outer_width_ceiling_mm=.066))
 d=dict(line=line,forbidden=Polygon(),baseline_body=base,maximum_body=target,allowed_extension=target.difference(base))
 for f in (1.2,1.3,1.4,1.5):
  body=body_at(core,.05,p,d,f);assert body.covers(base)
  assert body_at(core,.05,p,d,f,envelope=True).covers(body)
 assert to_wkb(body_at(core,.05,p,d,1.2))==to_wkb(base)
 assert to_wkb(body_at(core,.05,p,d,1.5))==to_wkb(target)

def example(tmp_path):
 rows={};original={};seeds={};ids={};owners={}
 for sid,y in [('a',0.),('b',.12)]:
  line=LineString([(0,y),(1,y)]);g=line.buffer(.025,quad_segs=128);original[sid]=g;ids[sid]=(sid,);owners[sid]=g
  rows[sid]=dict(metadata=dict(minimum_caliper_mm=.05,route_points_mm=list(map(list,line.coords)),route_kind='segment'))
  body=profile_body(g,.05,.06,.066,(0.,0.),line,Polygon())
  seeds[sid]=dict(source_width_mm=.05,translation_mm=[0.,0.],corridor_width_mm=.06,outer_width_ceiling_mm=.066,body_sha256=hashlib.sha256(to_wkb(body)).hexdigest(),source_ids=[sid])
 seed=dict(schema='t04-profile-refinement-reference/1',source_sha256='a'*64,input_scene_sha256='b'*64,reference_only=True,proof_reuse=False,source_stage_sha256='c'*64,routes=seeds);path=tmp_path/'reference.json';path.write_text(json.dumps(seed))
 rule=dict(baseline_seed=str(path),baseline_seed_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),input_binding=dict(source_sha256='a'*64,scene_ref=dict(sha256='b'*64)),width_variation_limit=.25)
 settings=SimpleNamespace(maximum_factor=1.5,maximum_total_width_increase_mm=.03,rung=lambda w,k:dict(factor=1+k*.05,within_growth_limits=True))
 return rows,original,SimpleNamespace(ids=ids,cores=owners),settings,rule

def test_refinement_reserves_both_reference_routes_before_growing(tmp_path):
 rows,original,ctx,settings,rule=example(tmp_path)
 chosen,data,cores,receipt=plan(rows,original,original,{'a':['a'],'b':['b']},{},ctx,settings,rule)
 for r in chosen:assert chosen[r]['body'].covers(data[r]['baseline_body']) and chosen[r]['high']==.075
 assert chosen['a']['body'].distance(chosen['b']['body'])>=.0401
 assert receipt['baseline_reference']['proof_reuse'] is False

def test_reference_shape_is_reconstructed_not_trusted_as_a_cached_proof(tmp_path):
 rows,original,ctx,settings,rule=example(tmp_path);path=tmp_path/'reference.json';seed=json.loads(path.read_bytes());seed['routes']['a']['body_sha256']='0'*64;path.write_text(json.dumps(seed));rule['baseline_seed_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
 with pytest.raises(ValueError,match='REFERENCE_RECONSTRUCTION_CHANGED'):plan(rows,original,original,{'a':['a'],'b':['b']},{},ctx,settings,rule)

def test_profile_progress_matches_actual_caller_not_physical_width_rungs(tmp_path):
 rows,original,ctx,settings,rule=example(tmp_path)
 def forbidden(*args):pytest.fail('physical width rungs do not define bounded profile progress')
 settings.rung=forbidden
 _,_,_,receipt=plan(rows,original,original,{'a':['a'],'b':['b']},{},ctx,settings,rule)
 assert all(p['progress_cap']==1.5 and p['baseline_profile']['factor']==1.2 for p in receipt['route_plans'].values())

def test_clearance_barrier_reserves_euclidean_distance_between_arc_vertices():
 from shapely.geometry import box,Point
 from src.gerber_u05.profile_refinement import clearance_barrier
 from src.gerber_u05.limiting_math import GUARD,MARGIN
 source=box(0,0,1,1);required=GUARD+2*MARGIN;barrier=clearance_barrier(source,required);coords=list(barrier.exterior.coords)
 samples=[Point((a[0]+b[0])/2,(a[1]+b[1])/2) for a,b in zip(coords,coords[1:])]
 assert min(p.distance(source) for p in samples)>=required-1e-12
