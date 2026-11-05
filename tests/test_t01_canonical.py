"""Source-wide semantics, forbidden substitutes, permission and tamper guards."""
import copy
from unittest.mock import patch
import pytest
from src.stage_abi.contracts import StageABIError
from src.stage_abi.store import canonical
from src.t01_canonical import marker,require,allocate,specification
from src.t01_board.adapter import BoardAdapter,PORT_STORE
from src.t01_crop.adapter import CropAdapter
from src.t01_board.policy import compile_policy,english
from src.t01_board.source import context
from tests.test_t01_board import environment

def test_one_canonical_contract_uses_original_interaction_rules_and_numbers():
    s=specification()
    assert s['family']=='t01-priority-companion/4'
    assert s['view_dependency']=='NONE'
    assert s['settings']==dict(hard_factor=1.5,construction_gap=.04002,hard_gap=.040,safety=.00002,orientation=-45,qsegs=128,area_epsilon=1e-10,event_epsilon=1e-8)
    p=compile_policy(english(),dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64))
    assert len(p['clause_trace'])==16 and p['clause_trace'][14]['contract_field']=='verification'
    permission=s['permissions']['850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0']
    assert len(permission['ordinary_t02_recovery_source_ids'])==2
    assert permission['companion_evaluation_source_ids']==permission['blocked_full_circle_obligation_source_ids']
    assert len(permission['blocked_full_circle_obligation_source_ids'])==1

def test_permission_revision_preserves_frozen_contract_and_binds_owner_scope():
    import json
    from pathlib import Path
    from src.stage_abi.store import digest
    s=specification();revision=s['permission_revision']
    original=Path(revision['prior_contract_path']).read_bytes()
    assert digest(original)==revision['supersedes_sha256']
    old=json.loads(original)
    # Recovery authority stays exact in the archived 0.020 predecessor.
    revision40=s['clearance_revision']
    previous_raw=Path(revision40['prior_contract_path']).read_bytes()
    assert digest(previous_raw)==revision40['supersedes_sha256']
    previous=json.loads(previous_raw)
    for key in ['settings','diameter_classes_mm','full_surface_guard','source_directives']:
        assert previous[key]==old[key]
    assert all(previous['kernel_sha256'][name]==h for name,h in old['kernel_sha256'].items())
    assert s['permissions']==previous['permissions']
    assert s['diameter_classes_mm']==old['diameter_classes_mm']
    assert s['source_directives']==old['source_directives']
    assert s['contained_shape_keep']['action']=='KEEP_EXACT_PREDECESSOR'
    assert len(next(iter(old['permissions'].values()))['keep_original_source_ids'])==3
    authority=Path(revision['authority_path']).read_bytes()
    assert digest(authority)==revision['authority_sha256']
    assert json.loads(authority)['full_circle_obligation']=='C028_BLOCKED'

@pytest.mark.parametrize('fault',['missing_canonical','hash','palette','gap'])
def test_semantic_substitution_or_numeric_mutation_rejects(fault):
    p=compile_policy(english(),dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64))
    if fault=='missing_canonical':p.pop('canonical_t01')
    elif fault=='hash':p['canonical_t01']['contract_sha256']='0'*64
    elif fault=='palette':p['diameter_classes_mm'].append(.5)
    else:p['settings']['hard_gap']=.019
    with pytest.raises(StageABIError):require(p)

def test_view_bounds_uncertainty_names_do_not_change_allocation(tmp_path):
    store,service,req,host,scene,bref,bounds,scope=environment(tmp_path)
    policy=compile_policy(english(),bref);binding,raw,rows,shapes,sites=context(store,scene,policy)
    a=allocate(raw,rows,shapes,sites,policy,binding)
    other=dict(binding,viewport_mm=[100.,100.,101.,101.],location_uncertainty_mm=.05,view_label='arbitrary read-only view',u03_selection=dict(bounds_mm=[-999.,-999.,999.,999.]))
    b=allocate(raw,rows,shapes,sites,policy,other)
    assert canonical(a[1])==canonical(b[1])and a[2:]==b[2:]
    assert a[1]['priority_pool_source_ids']==sorted(s['source_id']for s in sites)

def test_case_cannot_override_source_specific_directives(tmp_path):
    store,service,req,host,scene,bref,bounds,scope=environment(tmp_path)
    p=compile_policy(english(),bref);b,raw,rows,shapes,sites=context(store,scene,p);bad=dict(b,recess_source_ids=[sites[0]['source_id']])
    with pytest.raises(StageABIError,match='Binding must match'):allocate(raw,rows,shapes,sites,p,bad)

def test_explicit_source_keep_stays_a_fixed_source_operand(tmp_path):
    store,service,req,host,scene,bref,bounds,scope=environment(tmp_path);p=compile_policy(english(),bref);b,raw,rows,shapes,sites=context(store,scene,p)
    from src.stage_abi.store import digest
    spec=copy.deepcopy(specification());sid=sites[-1]['source_id'];spec['permissions'][digest(raw)]=dict(keep_original_source_ids=[sid])
    with patch('src.t01_canonical.specification',return_value=spec):
        settings,a,targets,square=allocate(raw,rows,shapes,sites,p,b)
    assert targets[sid]==sites[-1]['radius']and sid in a['permission_keep_source_ids']
    assert sid not in a['priorities_by_physical_component'].values()
    assert a['size_classes'][sid]['limits'][-1]['reason']=='IMMUTABLE_SOURCE_PERMISSION_KEEP'

@pytest.mark.parametrize('factory',[('src.c03_round_adapter','NativeRoundAdapter','T01_C03_SUBSTITUTE_RETIRED'),('src.c03_round_service','C03RoundService','T01_C03_SUBSTITUTE_RETIRED'),('src.t01_abi.service','InteractionService','T01_LEGACY_CASE_WRITE_RETIRED'),('src.t01_crop.service','CropService','T01_CROP_WRITE_RETIRED'),('src.u03_board.crop_t01','ImageCropService','T01_CROP_WRITE_RETIRED')])
def test_no_historical_or_crop_bound_service_can_write_new_T01(factory,tmp_path):
    import importlib
    module,name,code=factory;cls=getattr(importlib.import_module(module),name)
    with pytest.raises(StageABIError)as caught:cls(None,{})
    assert caught.value.code==code and list(tmp_path.iterdir())==[]

def test_retired_C03_route_refuses_before_making_a_job(tmp_path):
    from tools.c03_recovery_route import initialize
    with pytest.raises(ValueError,match='T01_C03_SUBSTITUTE_RETIRED'):initialize(tmp_path/'new')
    assert not(tmp_path/'new').exists()

def test_whole_source_adapter_uses_exact_same_allocator(tmp_path):
    store,service,req,host,scene,bref,bounds,scope=environment(tmp_path);p=compile_policy(english(),bref);b,raw,rows,shapes,sites=context(store,scene,p)
    raw_allocation=CropAdapter()._allocate(raw,rows,shapes,sites,p,b)
    token=PORT_STORE.set(store)
    try:board_allocation=BoardAdapter()._allocate(raw,rows,shapes,sites,p,b)
    finally:PORT_STORE.reset(token)
    assert raw_allocation[2:]==board_allocation[2:]
    assert raw_allocation[1]['groups']==board_allocation[1]['groups']
    assert raw_allocation[1]['canonical_t01']==board_allocation[1]['canonical_t01']==marker()

def test_full_surface_guard_rejects_bridge_preserves_core_and_complete_round():
    from shapely.geometry import Point
    from src.crop_balanced_t01 import WorkingScene,CropSettings
    from src.t01_canonical_surface import SurfaceGuard
    from src.prepared_land_scene import PreparedLandScene
    cores=[Point(0,0).buffer(.1,quad_segs=128),Point(.27,0).buffer(.1,quad_segs=128)]
    sites=[dict(source_id=str(i),aliases=[str(i)],indexes=[i],core=g,center=(i*.27,0),radius=.1)for i,g in enumerate(cores)]
    rows=[dict(id=str(i),kind='gr_circle',trace_width_mm=0.)for i in range(2)]
    scene=WorkingScene(b'',rows,cores,sites,CropSettings());guard=SurfaceGuard(rows,cores,sites)
    bridge=Point(0,0).buffer(.15,quad_segs=128)
    clipped=guard.limit(sites[0],bridge,scene)
    assert clipped.covers(cores[0])and clipped.difference(cores[0]).area>0
    assert guard.limit(sites[0],bridge,scene,priority=True).equals_exact(cores[0],0)
    lands=[dict(id='0',original=cores[0],candidate=clipped,native_source_kind='gr_circle',native_stroke_width_mm=0.)]
    fixed=[dict(id='1',geometry=cores[1],trace_width_mm=0.)]
    assert PreparedLandScene(lands,fixed).check(lands)['passed']
    lands[0]['candidate']=bridge
    assert not PreparedLandScene(lands,fixed).check(lands)['passed']

def test_native_whole_source_construction_is_reconstructed_with_guard(tmp_path):
    store,service,req,host,scene,bref,bounds,scope=environment(tmp_path)
    adapter=BoardAdapter();p=compile_policy(english(),bref)
    binding,raw,rows,shapes,sites=context(store,scene,p)
    selection=dict(stage='t01',scene_ref=req('x',{})['scene_ref'],source_ids=[s['source_id']for s in sites])
    bound=store.get_json(bounds,kind='bounds');plan=dict(details=adapter.plan(store,scene,p,selection,bound))
    a=adapter._compute(store,scene,p,plan,lambda _:None)
    b=adapter._compute(store,scene,p,plan,lambda _:None)
    assert a['canonical_result_sha256']==b['canonical_result_sha256']
    assert a['full_surface_check']['passed']and a['full_surface_check']['checked_land_count']==len(sites)
    assert canonical(a)==canonical(b)

def test_guard_only_difference_cannot_count_as_square_control_effect(tmp_path):
    store,service,req,host,scene,bref,bounds,scope=environment(tmp_path)
    adapter=BoardAdapter();p=compile_policy(english(),bref)
    binding,raw,rows,shapes,sites=context(store,scene,p)
    selection=dict(stage='t01',scene_ref=req('x',{})['scene_ref'],source_ids=[s['source_id']for s in sites])
    details=adapter.plan(store,scene,p,selection,store.get_json(bounds,kind='bounds'))
    a=copy.deepcopy(details['allocation']);a['priorities_by_physical_component']={}
    targets={sid:r['proposed_radius_mm']for sid,r in a['size_classes'].items()}
    sid=next(s['source_id']for s in sites if targets[s['source_id']]>s['radius'])
    from src.crop_balanced_t01 import CropSettings
    def square_allocation(*args):return CropSettings(**p['settings']),copy.deepcopy(a),targets,{sid}
    # A guard that holds everything makes square-on and square-off identical.
    # Comparing guarded square-on to unguarded square-off would falsely pass.
    with patch.object(adapter,'_allocate',side_effect=square_allocation),patch('src.t01_canonical_surface.SurfaceGuard.limit',side_effect=lambda site,proposal,scene,**kw:site['core']):
        plan=dict(details=adapter.plan(store,scene,p,selection,store.get_json(bounds,kind='bounds')))
        with pytest.raises(StageABIError)as caught:adapter._compute(store,scene,p,plan,lambda _:None)
    assert caught.value.code=='T01_RECESS_CONTROL_NOT_ESTABLISHED'

def test_round_class_selection_and_promotion_both_obey_stronger_guard():
    from shapely.geometry import Point
    from src.crop_balanced_t01 import WorkingScene,CropSettings
    from src.crop_diameter_selection import select_targets,promote_round_priorities
    core=Point(0,0).buffer(.14999,quad_segs=128)
    s=dict(source_id='a',aliases=['a'],indexes=[0],core=core,center=(0,0),radius=.14999,physical_contact_group='one')
    settings=CropSettings();scene=WorkingScene(b'',[dict(id='a',kind='gr_circle')],[core],[s],settings)
    groups=[dict(group_id='G01',site_ids=['a'])];priorities={'one':'a'}
    guard=lambda site,g:dict(passed=max(g.bounds[2]-g.bounds[0],g.bounds[3]-g.bounds[1])<=.3749+1e-12)
    targets,records,_=select_targets([s],groups,priorities,scene,settings,[.3374,.3749,.4499],round_guard=guard,round_separation_gap_mm=.02012)
    assert targets['a']==.3749/2
    assert records['a']['limits'][0]['rejected_diameter_mm']==.4499
    assert not promote_round_priorities([s],groups,priorities,scene,settings,targets,records,round_guard=guard,round_separation_gap_mm=.02012)
    assert records['a']['round_opportunity']['status']=='BLOCKED_NEXT_CLASS'
    assert records['a']['round_opportunity']['blockers'][0]['reason']=='FULL_SOURCE_VISIBLE_SURFACE_GUARD'
