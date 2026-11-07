import copy
import pytest
from shapely.geometry import box
from shapely.ops import unary_union
from shapely import to_wkb
from src import component_clearance as cc
from src.stage_abi.lands import land_parameters
from src.stage_abi.store import canonical
from src.gerber_u05.component_rectangles import ComponentRectangleAdapter
from src.gerber_u05.land_reconstruction import reconstruct
from test_t02_shared_gaps import fixture,contexts


def prepare(tmp_path,monkeypatch):
    source,scene,store=fixture(tmp_path)
    source['b']=box(0,1.3,1,2.3);source['joint']=box(.45,.9,.55,1.4)
    ref=lambda geometry:store.put('geometry',to_wkb(geometry))
    for row in scene['objects']:
        row['original_ref']=row['geometry_ref']=ref(source[row['source_id']])
    scene['objects'].append(dict(source_id='joint',kind='trace',original_ref=ref(source['joint']),
                                 geometry_ref=ref(source['joint']),metadata=dict(original_width_mm=.1)))
    physical=unary_union(list(source.values()))
    def fresh():monkeypatch.setattr(cc,'ACTIVE',cc.Context(physical,scene['source_sha256'],source))
    fresh();adapter=ComponentRectangleAdapter('t02');scene_ref=store.put_json('scene',scene)
    policy=dict(stage='t02',parameters=land_parameters('t02'))
    limits=dict(max_source_objects=100,max_targets=100,max_evaluations=10000,max_output_bytes=10**7,max_seconds=60)
    details=adapter.plan(store,scene,policy,dict(stage='t02',scene_ref=scene_ref,source_ids=['a','b']),limits)
    plan=dict(stage='t02',scene_ref=scene_ref,policy_ref=store.put_json('policy',policy),
              implementation=adapter.describe()['implementation'],details=details)
    candidate=adapter.run(store,scene,policy,plan,lambda _:None)
    assert any(row['status']=='MERGED'for row in candidate['inclusive_candidates'])
    fresh()
    return scene,store,policy,plan,dict(plan=plan,candidate=candidate)


def test_accepted_integral_fill_is_reconstructed_and_rechecked(tmp_path,monkeypatch):
    scene,store,policy,plan,recorded=prepare(tmp_path,monkeypatch)
    adapter=ComponentRectangleAdapter('t02')
    value=reconstruct(adapter,store,scene,policy,plan,recorded)
    assert canonical(value)==canonical(recorded['candidate'])
    checked=adapter.verify(store,scene,policy,plan,value,{'scope':'complete-source-land-and-inclusive'},lambda _:None)
    assert checked['passed']and checked['inclusive_fills']>=1


def test_changed_accepted_fill_cannot_be_carried_as_verified(tmp_path,monkeypatch):
    scene,store,policy,plan,recorded=prepare(tmp_path,monkeypatch)
    bad=copy.deepcopy(recorded)
    row=next(r for r in bad['candidate']['inclusive_candidates']if r['status']=='MERGED')
    row['candidate_ref']=bad['candidate']['decisions'][0]['candidate_ref']
    with pytest.raises(ValueError,match='FIXED_CANDIDATE_RECONSTRUCTION_CHANGED'):
        reconstruct(ComponentRectangleAdapter('t02'),store,scene,policy,plan,bad)
