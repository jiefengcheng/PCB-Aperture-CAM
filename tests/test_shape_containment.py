"""Uniform contained-shape KEEP, aliases, complete unions and tamper controls."""
import copy,subprocess,sys
from pathlib import Path
from unittest.mock import patch
import pytest
from shapely import to_wkb,STRtree
from shapely.geometry import Point,box
from src.shape_containment import ContainmentIndex
from src.stage_abi.contracts import StageABIError
from src.stage_abi.lands import LandAdapter,land_parameters
from src.stage_abi.store import ArtifactStore
from src.u04_board.search import FastRectangleAdapter


@pytest.mark.parametrize('core,parent',[(Point(0,0).buffer(.1),box(-1,-1,1,1)),(box(-.1,-.1,.1,.1),Point(0,0).buffer(1))])
def test_circle_and_rectangle_containment_use_same_rule(core,parent):
    assert ContainmentIndex({'shape':core,'parent':parent}).assess('shape')['contained']


def test_union_coverage_excludes_self_and_exact_aliases_and_detects_partial_gap():
    core=box(0,0,1,1)
    assert not ContainmentIndex({'s':core,'alias':core}).assess('s')['contained']
    objects={'s':core,'alias':core,'left':box(-1,-1,.5,2),'right':box(.5,-1,2,2)}
    q=ContainmentIndex(objects).assess('s')
    assert q['contained']and q['excluded_aliases']==['alias','s']
    assert q==ContainmentIndex(dict(reversed(list(objects.items())))).assess('s')
    objects['right']=box(.50001,-1,2,2)
    assert not ContainmentIndex(objects).assess('s')['contained']
    assert not ContainmentIndex({'s':core,'touch':box(1,0,2,1)}).assess('s')['contained']


def test_stage_entry_snapshot_cannot_be_replaced_by_later_trial_growth():
    objects={'s':box(0,0,1,1),'parent':box(0,0,.5,1)};index=ContainmentIndex(objects)
    objects['parent']=box(-1,-1,2,2)
    assert not index.assess('s')['contained']


def environment(tmp_path,adapter):
    store=ArtifactStore(tmp_path/'runtime');objects=[]
    for sid,g,kind in [('r',box(0,0,1,1),'rectangle'),('alias',box(0,0,1,1),'rectangle'),('parent',box(-1,-1,2,2),'fixed_source')]:
        ref=store.put('geometry',to_wkb(g,byte_order=0))
        objects.append(dict(source_id=sid,kind=kind,original_ref=ref,geometry_ref=ref,metadata={}))
    scene=dict(source_sha256='a'*64,frame='native',units='mm',layer='F.Cu',viewport_mm=[-2,-2,3,3],objects=objects,findings=[],lineage=[],acceptance={})
    sr=store.put_json('scene',scene);policy=dict(stage='t02',parameters=land_parameters('t02'));pr=store.put_json('policy',policy)
    bounds=dict(max_source_objects=3,max_targets=2,max_evaluations=1000,max_output_bytes=10000000,max_seconds=120)
    details=adapter.plan(store,scene,policy,dict(stage='t02',scene_ref=sr,source_ids=['r','alias']),bounds)
    plan=dict(stage='t02',scene_ref=sr,policy_ref=pr,implementation=adapter.describe()['implementation'],details=details)
    return store,scene,policy,plan


@pytest.mark.parametrize('factory',[lambda:LandAdapter('t02'),lambda:FastRectangleAdapter('t02')])
def test_contained_rectangles_keep_exact_refs_and_cannot_create_inclusive_fill(tmp_path,factory):
    a=factory();store,scene,p,plan=environment(tmp_path,a)
    with patch('src.stage_abi.lands.fit_joint_rectangle',side_effect=AssertionError('contained shape searched')),patch('src.u04_board.search.fit_joint_rectangle',side_effect=AssertionError('contained shape searched')):
        c=a.run(store,scene,p,plan,lambda _:None)
    originals={r['source_id']:r for r in scene['objects']}
    assert all(d['status']=='COVERED_SKIP'and d['candidate_ref']==originals[d['source_id']]['geometry_ref']for d in c['decisions'])
    assert c['inclusive_candidates']==[]
    assert a.verify(store,scene,p,plan,c,{'scope':'complete-source-land-and-inclusive'},lambda _:None)['passed']
    bad=copy.deepcopy(c);bad['decisions'][0]['status']='GROWN';bad['decisions'][0]['shape']={'factors':[1.25,1.25]}
    with pytest.raises(StageABIError)as caught:a.verify(store,scene,p,plan,bad,{'scope':'complete-source-land-and-inclusive'},lambda _:None)
    assert caught.value.code=='CONTAINED_SHAPE_CHANGED'
    badplan=copy.deepcopy(plan);badplan['details']['containment']['r']['contained']=False
    with pytest.raises(StageABIError)as caught:a.run(store,scene,p,badplan,lambda _:None)
    assert caught.value.code=='CONTAINMENT_PLAN_CHANGED'


def test_canonical_contained_circle_is_not_allocated_or_allowed_to_change(tmp_path):
    from tests.test_t01_board import environment as board_environment
    from src.t01_board.adapter import BoardAdapter
    from src.t01_board.policy import compile_policy,english
    from src.t01_board.source import context
    store,_,req,_,scene,bref,bounds,_=board_environment(tmp_path)
    adapter=BoardAdapter();p=compile_policy(english(),bref);sites=context(store,scene,p)[-1]
    details=adapter.plan(store,scene,p,dict(stage='t01',scene_ref=req('x',{})['scene_ref'],source_ids=[s['source_id']for s in sites]),store.get_json(bounds,kind='bounds'))
    contained=details['allocation']['contained_keep_source_ids'];assert len(contained)==1
    sid=contained[0];site=next(s for s in sites if s['source_id']==sid)
    assert details['allocation']['size_classes'][sid]['proposed_radius_mm']==site['radius']
    assert sid not in details['allocation']['priorities_by_physical_component'].values()
    candidate=adapter._compute(store,scene,p,{'details':details},lambda _:None)
    row=next(r for r in candidate['decisions']if r['source_id']==sid)
    assert row['keep_reason']=='KEEP_CONTAINED'and row['added_area_mm2']==0
    assert row['candidate_ref']==next(r['geometry_ref']for r in scene['objects']if r['source_id']==sid)
    import src.t01_abi.adapter as module
    original_execute=module.execute
    def changed(*args,**kwargs):
        result=original_execute(*args,**kwargs);result['scene'].accepted[sid]=site['core'].buffer(.001);return result
    with patch.object(module,'execute',side_effect=changed):
        with pytest.raises(StageABIError)as caught:adapter._compute(store,scene,p,{'details':details},lambda _:None)
        assert caught.value.code=='T01_CONTAINED_SOURCE_CHANGED'


def test_legacy_latent_growth_writer_rejects_before_any_artifact(tmp_path):
    root=Path(__file__).resolve().parents[1];out=tmp_path/'not_created'
    p=subprocess.run([sys.executable,'-B',str(root/'tools/run_crop_rect_t02.py'),'--output',str(out)],capture_output=True,text=True,cwd=root)
    assert p.returncode!=0 and 'T02_LEGACY_LATENT_GROWTH_ROUTE_RETIRED'in p.stderr
    assert not out.exists()


def test_containment_recovery_retained_across_production_clearance_revision():
    import json
    from src.shape_containment import policy
    from src.t01_canonical import specification
    from src.t01_board.policy import english
    root=Path(__file__).resolve().parents[1]
    current=json.loads((root/'contracts/operator/u04_board.json').read_text())
    prior=json.loads((root/'contracts/operator/revisions/u04_board_cb529f1c8d4fc824a352498e467d3a269df4ed3c545e2f280f7a5ec8a6f6767e.json').read_text())
    assert current['land_policy']==land_parameters('t02')
    # Verify the unchanged recovery revision at its original 0.020 policy,
    # then require current 0.040 defaults without weakening containment.
    archived=json.loads((root/'contracts/clearance/revisions/u04_board_fd6abbafdc9c6191afbebb6220d56ed10858412d97e964dbb929b1cbfcad7bd8.json').read_text())
    assert {k:v for k,v in archived.items()if k!='land_policy'}=={k:v for k,v in prior.items()if k!='land_policy'}
    assert current['policy']['hard_gap_mm']==.040
    assert current['land_policy']['contained_shape_keep']==archived['land_policy']['contained_shape_keep']
    assert specification()['contained_shape_keep']==policy()
    assert (root/'contracts/t01_board/english.txt').read_text()==english()
