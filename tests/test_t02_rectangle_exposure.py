"""Global T02 perimeter rule, exact KEEP and independent source reconstruction."""
import copy,json
from unittest.mock import patch
import pytest
from shapely import to_wkb
from shapely.geometry import box
from shapely.affinity import scale
from src.shape_containment import ContainmentIndex
from src.t02_rectangle_exposure import capture,from_bytes,assess,records
from src.stage_abi.store import ArtifactStore
from src.stage_abi.contracts import StageABIError
from src.stage_abi.lands import LandAdapter,land_parameters
from src.u04_board.search import FastRectangleAdapter
from src.gerber_u05.component_rectangles import ComponentRectangleAdapter
from src import component_clearance as cc,pin_separation as pin,source_channel_scope,t04_width_fence

@pytest.fixture(autouse=True)
def contexts(monkeypatch):
 for module in (cc,pin,source_channel_scope,t04_width_fence):monkeypatch.setattr(module,'ACTIVE',None)

@pytest.mark.parametrize('threshold',[.5,.6])
@pytest.mark.parametrize('tolerance',[0.,.01])
@pytest.mark.parametrize('fraction',[.49,.49499999,.495,.49500001,.49999999,.5,.50000001,.59399999,.594,.59400001,.59999999,.6,.60000001,.7,.74])
def test_exposed_edge_lengths_and_global_boundary(fraction,threshold,tolerance):
 core=box(0,0,1,1);cutoff=(3-4*fraction)/2;other=box(-2,-2,cutoff,2)
 value=json.loads(capture().raw_json);value['minimum_exposed_perimeter_fraction_for_growth']=threshold
 value['relative_exposure_tolerance']=tolerance
 q=assess('pad',ContainmentIndex(dict(pad=core,other=other)),from_bytes(json.dumps(value).encode()))
 assert q['exposed_perimeter_fraction']==pytest.approx(fraction,abs=1e-14)
 floor={(0.5,0.):.5,(0.6,0.):.6,(0.5,.01):.495,(0.6,.01):.594}[(threshold,tolerance)]
 assert q['growth_eligible']is(fraction>=floor)
 assert q['perimeter_mm']==4 and q['exposed_perimeter_mm']==pytest.approx(4*fraction)

def test_area_does_not_decide_exposure_and_coincident_outer_edges_are_visible():
 core=box(0,0,1,1)
 for other in (box(.01,.01,.99,.99),box(0,0,.99,.99)):
  q=assess('pad',ContainmentIndex(dict(pad=core,other=other)),capture())
  assert q['exposed_perimeter_fraction']==1 and q['growth_eligible']
 adjacent=assess('pad',ContainmentIndex(dict(pad=core,other=box(1,0,2,1))),capture())
 assert adjacent['exposed_perimeter_fraction']==.75

def test_nominal_half_perimeter_is_eligible_despite_binary_coordinate_ulps():
 from shapely.ops import unary_union
 core=box(4.9491,-14.544,5.5991,-13.894);x0,y0,x1,y1=core.bounds
 other=unary_union([box(x0-1,y0,x0,y1),box(x1,y0,x1+1,y1)])
 q=assess('pad',ContainmentIndex(dict(pad=core,other=other)),capture())
 assert q['exposed_perimeter_fraction']==pytest.approx(.5,abs=1e-14)
 assert q['growth_eligible']
 from src.trace_width_clearance import TraceWidthContract
 assert q['length_comparison_epsilon_mm']==TraceWidthContract().comparison_epsilon_mm

def test_exact_aliases_tangencies_containment_and_combined_source():
 core=box(0,0,1,1)
 q=assess('pad',ContainmentIndex(dict(pad=core,alias=core,tangent=box(1,1,2,2))),capture())
 assert q['growth_eligible']and q['exposed_perimeter_fraction']==1 and 'alias'in q['excluded_aliases']
 q=assess('pad',ContainmentIndex(dict(pad=core,left=box(-1,-1,.5,2),right=box(.5,-1,2,2))),capture())
 assert not q['growth_eligible']and q['fully_contained']and q['exposed_perimeter_mm']==0

@pytest.mark.parametrize('bad',[True,-.01,1.01,float('nan'),float('inf'),'0.6'])
def test_invalid_global_parameter_rejects(bad):
 value=json.loads(capture().raw_json);value['minimum_exposed_perimeter_fraction_for_growth']=bad
 with pytest.raises(ValueError):from_bytes(json.dumps(value).encode())

def test_duplicate_parameter_rejects_and_T01_stays_at_58_percent():
 with pytest.raises(ValueError,match='DUPLICATE'):
  from_bytes(capture().raw_json.replace('"revision": 2','"revision": 2, "revision": 2').encode())
 from src.t01_circle_exposure import capture as circle
 assert circle().minimum_exposed_circumference_fraction_for_growth==.58
 assert capture().minimum_exposed_perimeter_fraction_for_growth==.5
 assert capture().relative_exposure_tolerance==.01 and capture().effective_floor_fraction==.495

@pytest.mark.parametrize('bad',[True,-.01,1.,1.01,float('nan'),float('inf'),'0.01'])
def test_invalid_global_exposure_tolerance_rejects(bad):
 value=json.loads(capture().raw_json);value['relative_exposure_tolerance']=bad
 with pytest.raises(ValueError):from_bytes(json.dumps(value).encode())

def test_relative_tolerance_is_reported_without_changing_clearance_or_T01():
 core=box(0,0,1,1);other=box(-2,-2,(3-4*.498)/2,2)
 q=assess('pad',ContainmentIndex(dict(pad=core,other=other)),capture())
 assert q['growth_eligible']and q['tolerance_consumed']and q['effective_floor_fraction']==.495
 from src.clearance_policy import HARD_GAP_MM,CONSTRUCTION_GAP_MM
 from src.t01_circle_exposure import capture as circle
 assert(HARD_GAP_MM,CONSTRUCTION_GAP_MM)==(.04,.0401)
 assert circle().minimum_exposed_circumference_fraction_for_growth==.58

def fixture(tmp_path):
 store=ArtifactStore(tmp_path/'runtime');ref=lambda g:store.put('geometry',to_wkb(g))
 core=box(0,0,1,1);current=scale(core,1.01,1.01,origin=core.centroid);other=box(-1,-1,.6,2)
 rows=[dict(source_id='pad',kind='rectangle',original_ref=ref(core),geometry_ref=ref(current),metadata={'alias_source_ids':['pad']}),dict(source_id='other',kind='fixed',original_ref=ref(other),geometry_ref=ref(other),metadata={})]
 scene=dict(source_sha256='a'*64,frame='test',units='mm',layer='F.Cu',viewport_mm=[-2,-2,3,3],objects=rows,lineage=[],findings=[],acceptance={})
 scene_ref=store.put_json('scene',scene);policy=dict(stage='t02',parameters=land_parameters('t02'))
 return store,scene,scene_ref,policy,core,current,other

@pytest.mark.parametrize('implementation',[LandAdapter,FastRectangleAdapter,ComponentRectangleAdapter])
def test_all_rectangle_adapters_keep_exact_stage_entry_and_exclude_fill_members(tmp_path,implementation):
 store,scene,ref,policy,core,current,other=fixture(tmp_path);adapter=implementation('t02')
 details=adapter.plan(store,scene,policy,dict(stage='t02',scene_ref=ref,source_ids=['pad']),dict(max_source_objects=100,max_targets=100,max_evaluations=1000,max_output_bytes=10**7,max_seconds=60))
 assert details['rectangle_exposure']['pad']['exposed_perimeter_fraction']==pytest.approx(.45)
 plan=dict(stage='t02',scene_ref=ref,policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details)
 candidate=adapter.run(store,scene,policy,plan,lambda _:None);d=candidate['decisions'][0]
 assert d['status']=='KEEP'and d['candidate_ref']==scene['objects'][0]['geometry_ref']
 assert d['keep_reason']=='EXPOSED_PERIMETER_BELOW_LIMIT'
 assert not candidate['inclusive_candidates']
 assert adapter.verify(store,scene,policy,plan,candidate,{'scope':'complete-source-land-and-inclusive'},lambda _:None)['passed']

@pytest.mark.parametrize('mutation',['plan','candidate'])
def test_forged_exposure_or_grown_KEEP_is_rejected(tmp_path,mutation):
 store,scene,ref,policy,*_=fixture(tmp_path);adapter=FastRectangleAdapter('t02')
 details=adapter.plan(store,scene,policy,dict(stage='t02',scene_ref=ref,source_ids=['pad']),dict(max_source_objects=100,max_targets=100,max_evaluations=1000,max_output_bytes=10**7,max_seconds=60))
 plan=dict(stage='t02',scene_ref=ref,policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details)
 candidate=adapter.run(store,scene,policy,plan,lambda _:None)
 if mutation=='plan':details['rectangle_exposure']['pad']['growth_eligible']=True
 else:candidate['decisions'][0].update(status='GROWN',shape={'factors':[1.1,1.1]})
 with pytest.raises(StageABIError)as error:adapter.verify(store,scene,policy,plan,candidate,{'scope':'complete-source-land-and-inclusive'},lambda _:None)
 assert error.value.code in('RECTANGLE_EXPOSURE_PLAN_CHANGED','RECTANGLE_EXPOSURE_KEEP_CHANGED')

def test_parameter_snapshot_rejects_stale_policy(tmp_path):
 store,scene,ref,old,*_=fixture(tmp_path);value=json.loads(capture().raw_json);value['minimum_exposed_perimeter_fraction_for_growth']=.4
 replacement=from_bytes(json.dumps(value).encode())
 with patch('src.stage_abi.lands.exposure_settings',return_value=replacement):
  with pytest.raises(StageABIError)as error:
   LandAdapter('t02').plan(store,scene,old,dict(stage='t02',scene_ref=ref,source_ids=['pad']),dict(max_source_objects=100,max_targets=100,max_evaluations=1000,max_output_bytes=10**7,max_seconds=60))
 assert error.value.code=='POLICY_UNSUPPORTED'

def test_owner_witnesses_and_current_growth_are_not_original_exposure_operands(tmp_path,monkeypatch):
 store,scene,ref,policy,core,current,other=fixture(tmp_path)
 ctx=cc.Context(core.union(other),scene['source_sha256'],dict(pad=core,other=other));monkeypatch.setattr(cc,'ACTIVE',ctx)
 originals=dict(pad=core,other=other,witness=box(-2,-2,3,3));scene['objects'].append(dict(source_id='witness',kind='component_remedy',metadata={'original_owner_id':'derived'},original_ref={},geometry_ref={}))
 q=records(scene,originals,['pad'],capture())['pad']
 assert q['exposed_perimeter_fraction']==pytest.approx(.45)
 assert 'witness'not in q['context_source_ids']
