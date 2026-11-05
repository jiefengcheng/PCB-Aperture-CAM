"""Nested concentric sources have no facing side; no source or clearance waiver."""
from pathlib import Path
import copy,math
import pytest
from shapely import to_wkb
from shapely.geometry import Point
from src.t01_crop.adapter import groups_for,CropAdapter
from src.t01_crop.policy import english,compile_policy,CONCENTRIC_CENTER_EPS_MM
from src.crop_square_neighbor_experiment import facing_square_side,inscribed_square,verify_addition
from src.crop_balanced_t01 import WorkingScene,CropSettings,choose_priorities,execute
from src.crop_diameter_selection import select_targets,promote_round_priorities
from src.stage_abi.contracts import StageABIError
from src.stage_abi.store import digest


def site(sid,x,y,r):
    core=Point(x,y).buffer(r,quad_segs=128)
    return dict(source_id=sid,center=[core.centroid.x,core.centroid.y],radius=(core.bounds[2]-core.bounds[0]+core.bounds[3]-core.bounds[1])/4,core=core,enlarged_radius=1.5*r,geometry_sha256=digest(to_wkb(core,byte_order=1)),aliases=[sid],indexes=[],physical_contact_group='same')


def test_actual_nested_radii_reproduce_old_undefined_facing_guard():
    a=site('outer',7.089,-8.796,.25006);b=site('inner',7.089,-8.796,.12497)
    assert math.dist(a['center'],b['center'])<CONCENTRIC_CENTER_EPS_MM
    with pytest.raises(ValueError,match='COINCIDENT_NEIGHBOR_CENTERS'):
        facing_square_side(inscribed_square(a['center'],a['radius']),a['center'],b['center'])
    group=groups_for([a,b],[],set(),.02002)[0]
    assert group['apply_square_bound'] is False
    proof=group['concentric_source_proof']
    assert proof['outer_source_id']=='outer' and proof['inner_source_id']=='inner'
    assert proof['original_containment'] and proof['outer_core_sha256']==digest(to_wkb(a['core'],byte_order=1))
    assert sorted(group['site_ids'])==['inner','outer'] # no alias merge/omission


def test_compilation_expresses_exception_without_changing_numeric_clearance():
    p=compile_policy(english(),dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64))
    assert len(p['clause_trace'])==16 and 'strictly nested' in p['clause_trace'][8]['english']
    assert 'complete visible-copper guard' in p['clause_trace'][14]['english']
    assert p['rules']['pair_interaction']['center_epsilon_mm']==1e-12
    assert p['settings']['hard_gap']==.020 and p['settings']['construction_gap']==.02002
    assert p['settings']['safety']==.00002


def test_ordinary_directional_pairs_keep_existing_bound_and_record_shape():
    a=site('a',0,0,.12497);b=site('b',.3,0,.12497)
    group=groups_for([a,b],[],set(),.02002)[0]
    assert group==dict(group_id='G01',site_ids=['a','b'],rule='nearest available competing pair')
    groups=groups_for([a,b],[['b','a']],set(),.02002)
    assert groups[0]['site_ids']==['b','a'] and 'apply_square_bound' not in groups[0]


def test_same_center_without_strict_source_containment_stays_rejected():
    a=site('a',0,0,.125);b=site('b',0,0,.125)
    # Equal geometry should already have been canonicalized by exact alias discovery.
    with pytest.raises(StageABIError,match='strictly nested'):groups_for([a,b],[],set(),.02002)
    b['core']=Point(0,0).buffer(.2,quad_segs=128).difference(Point(0,0).buffer(.05,quad_segs=128))
    b['radius']=.2
    with pytest.raises(StageABIError):groups_for([a,b],[],set(),.02002)


def test_offset_nested_centers_do_not_disable_directional_rule():
    a=site('outer',0,0,.25);b=site('inner',1e-8,0,.125)
    group=groups_for([a,b],[],set(),.02002)[0]
    assert 'apply_square_bound' not in group and 'concentric_source_proof' not in group


def test_boundary_keep_and_source_reviewed_pair_rules_are_preserved():
    a=site('outer',0,0,.25);b=site('inner',0,0,.125)
    groups=groups_for([a,b],[['outer','inner']],{'outer','inner'},.02002)
    assert len(groups)==2 and all(len(g['site_ids'])==1 for g in groups)
    groups=groups_for([a,b],[['inner','outer']],set(),.02002)
    assert groups[0]['site_ids']==['inner','outer'] and groups[0]['apply_square_bound'] is False


def test_concentric_growth_still_obeys_outer_source_obstacle():
    outer=site('outer',0,0,.25006);inner=site('inner',0,0,.12497);sites=[outer,inner]
    for i,s in enumerate(sites):s['indexes']=[i]
    rows=[dict(id=s['source_id'],kind='gr_circle') for s in sites]
    shapes=[s['core'] for s in sites];settings=CropSettings();scene=WorkingScene(b'',rows,shapes,sites,settings)
    groups=groups_for(sites,[],set(),settings.construction_gap);priorities,_=choose_priorities(sites,scene)
    from src.t01_abi.contract import PALETTE
    targets,records,limits=select_targets(sites,groups,priorities,scene,settings,PALETTE)
    promote_round_priorities(sites,groups,priorities,scene,settings,targets,records)
    assert targets['outer']==outer['radius'] and targets['inner']>inner['radius']
    grown=Point(*inner['center']).buffer(targets['inner'],quad_segs=128)
    # Disabling only the undefined angular bound does not permit this added contact.
    assert not verify_addition(inner['core'],grown,grown,scene.obstacles(inner,0),settings=settings.kernel())['passed']
    result=execute(b'',rows,shapes,sites,groups,priorities,settings=settings,targets=targets,counterfactuals=True)
    assert not result['failed_patches'] and len(result['decisions'])==2
    for s in sites:
        candidate=result['scene'].accepted[s['source_id']]
        assert to_wkb(candidate,byte_order=1)==to_wkb(s['core'],byte_order=1)
    assert {d['source_id']:d['decision'] for d in result['decisions']}=={'outer':'KEEP_PRIORITY','inner':'KEEP_CONSTRAINED'}


@pytest.mark.parametrize('mutation',['ordinary-disable','false-core-hash'])
def test_allocation_reconstruction_rejects_unauthorized_directional_changes(tmp_path,monkeypatch,mutation):
    from src.stage_abi.store import ArtifactStore
    sites=[site('outer',0,0,.25006),site('inner',0,0,.12497),site('a',1,0,.12497),site('b',1.3,0,.12497)]
    for i,s in enumerate(sites):s['indexes']=[i];s['physical_contact_group']='nested' if i<2 else 'ordinary'
    rows=[dict(id=s['source_id'],kind='gr_circle') for s in sites];shapes=[s['core'] for s in sites]
    binding=dict(location_uncertainty_mm=.005,viewport_mm=[-1,-1,2,1],reviewed_pairs=[],recess_source_ids=[])
    adapter=CropAdapter();monkeypatch.setattr(adapter,'_context',lambda *args:(binding,b'',rows,shapes,sites))
    policy=compile_policy(english(),dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64))
    store=ArtifactStore(tmp_path/'runtime');scene=dict(objects=[dict(source_id=s['source_id']) for s in sites]);selection=dict(stage='t01',scene_ref={},source_ids=[s['source_id'] for s in sites])
    bounds=dict(max_source_objects=4,max_targets=4,max_evaluations=1000,max_output_bytes=200000000,max_seconds=120)
    details=adapter.plan(store,scene,policy,selection,bounds)
    groups=details['allocation']['groups']
    if mutation=='ordinary-disable':next(g for g in groups if set(g['site_ids'])=={'a','b'})['apply_square_bound']=False
    else:details['allocation']['containment']['inner']['source_geometry_sha256']='0'*64
    with pytest.raises(StageABIError,match='source-computed allocation'):
        adapter._compute(store,scene,policy,dict(details=details),None)


def test_unreviewed_english_change_cannot_reinterpret_concentric_rule():
    ref=dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64)
    with pytest.raises(StageABIError):compile_policy(english().replace('0.000000000001 mm','0.001 mm'),ref)


def test_concentric_exception_does_not_force_keep_when_outer_growth_is_feasible():
    outer=site('outer',0,0,.12497);inner=site('inner',0,0,.05);sites=[outer,inner]
    for i,s in enumerate(sites):s['indexes']=[i]
    rows=[dict(id=s['source_id'],kind='gr_circle') for s in sites];shapes=[s['core'] for s in sites]
    settings=CropSettings();scene=WorkingScene(b'',rows,shapes,sites,settings)
    groups=groups_for(sites,[],set(),settings.construction_gap);priorities,_=choose_priorities(sites,scene)
    from src.t01_abi.contract import PALETTE
    targets,records,_=select_targets(sites,groups,priorities,scene,settings,PALETTE)
    promote_round_priorities(sites,groups,priorities,scene,settings,targets,records)
    result=execute(b'',rows,shapes,sites,groups,priorities,settings=settings,targets=targets,counterfactuals=True)
    assert not result['failed_patches'] and targets['outer']>outer['radius']
    assert result['scene'].accepted['outer'].difference(outer['core']).area>settings.area_epsilon
    assert all(d['verification']['passed'] for d in result['decisions'])
    assert to_wkb(result['scene'].accepted['inner'],byte_order=1)==to_wkb(inner['core'],byte_order=1)
