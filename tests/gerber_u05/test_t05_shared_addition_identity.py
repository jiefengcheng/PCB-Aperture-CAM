"""Distinct route obligations can share one immutable copper geometry blob."""
import copy
import json
from pathlib import Path
import pytest
from shapely.geometry import box, Point, LineString
from shapely.ops import unary_union
from shapely import to_wkb
from src import component_clearance as cc
from src.stage_abi.store import ArtifactStore
from src.stage_abi.scene import validate_scene
from src.u05_board.coverage import CoverageAdapter, addition_source_id
from src.u05_board.junctions import parameters
from src.gerber_u05 import pipeline as p


def test_actual_failed_additions_have_distinct_source_bound_ids(monkeypatch, tmp_path):
    rows = json.loads(Path(__file__).with_name('fixtures').joinpath('t05_duplicate_additions.json').read_bytes())
    assert len(rows) == 14 and len({r['patch_ref']['sha256'] for r in rows}) == 4
    original = copy.deepcopy(rows)
    monkeypatch.setattr(cc, 'ACTIVE', object())
    identities = [addition_source_id(r) for r in rows]
    assert len(set(identities)) == len(rows)
    assert identities == list(reversed([addition_source_id(r) for r in reversed(rows)]))
    assert rows == original  # No geometry duplication, rewrite or loss of route provenance.
    store = p.Store(tmp_path / 'store')
    scene = dict(source_sha256='a' * 64, frame='fixture', units='mm', layer='F.Cu',
                 viewport_mm=[-1, -1, 1, 1], findings=[], lineage=[], acceptance={},
                 objects=[dict(source_id=sid, kind='junction_addition', geometry_ref=r['patch_ref'],
                               original_ref=r['patch_ref'], metadata={'owner_trace': r['source_id']})
                          for sid, r in zip(identities, rows)])
    assert validate_scene(store, store.put_json('scene', scene)) == scene
    scene['objects'][1]['source_id'] = scene['objects'][0]['source_id']
    with pytest.raises(ValueError):
        validate_scene(store, store.put_json('scene', scene))
    monkeypatch.setattr(cc, 'ACTIVE', None)
    assert all(addition_source_id(r) == 't05-addition:' + r['patch_ref']['sha256'] for r in rows)


@pytest.mark.parametrize('functional_legacy',[False,True])
def test_two_original_owner_routes_share_geometry_but_keep_both_obligations(tmp_path,monkeypatch,functional_legacy):
    store = p.Store(tmp_path / 'store')
    rows = []
    original = {}
    trace = LineString([(-.6, 0), (.6, 0)]).buffer(.025, quad_segs=64)
    def add(sid, kind, g, **metadata):
        ref = store.put('geometry', to_wkb(g))
        rows.append(dict(source_id=sid, kind=kind, geometry_ref=ref, original_ref=ref, metadata=metadata))
        original[sid] = g
    add('physical', 'fixed_source', trace, native_source_ids=['physical'])
    for sid, x in [('left', -.6), ('right', .6)]:
        add(sid, 'circle', Point(x, 0).buffer(.2, quad_segs=64), qualified_land=True, alias_source_ids=[sid])
    for sid in ['view1', 'view2']:
        attachments = [dict(id=sid + ':' + lid, land_id=lid, reference_land_id=lid, required_reference=True)
                       for lid in ['left', 'right']]
        add(sid, 'trace', trace, native_route_ref={'qualified': True}, reference_source_ids=['physical'],
            land_ids=['left', 'right'], attachments=attachments, reference_id=sid, reference_status='GROWN')
    context = cc.bind(unary_union(list(original.values())), 'a' * 64, original)
    context.reserved = dict(context.cores)
    if functional_legacy:
        from src import source_channel_scope
        monkeypatch.setattr(cc,'ACTIVE',None)
        monkeypatch.setattr(source_channel_scope,'ACTIVE',context)
    scene = dict(source_sha256='a' * 64, frame='fixture', units='mm', layer='F.Cu', viewport_mm=[-3, -3, 3, 3],
                 objects=rows, lineage=[], findings=[], acceptance={'owner': 'PENDING_USER'})
    adapter = CoverageAdapter(box(-2, -2, 2, 2))
    policy = dict(stage='t05', parameters=parameters())
    bounds = dict(max_source_objects=20, max_targets=2, max_evaluations=8, max_output_bytes=10000000, max_seconds=120)
    scene_ref = store.put_json('scene', scene)
    details = adapter.plan(store, scene, policy, dict(stage='t05', scene_ref=scene_ref, source_ids=['view1', 'view2']), bounds)
    plan = dict(stage='t05', scene_ref=scene_ref, policy_ref=store.put_json('policy', policy),
                implementation=adapter.describe()['implementation'], details=details)
    candidate = adapter.run(store, scene, policy, plan, lambda _: None)
    assert candidate['coverage']['grown'] == 2
    decisions = candidate['decisions']
    assert decisions[0]['patch_ref'] == decisions[1]['patch_ref']
    output = validate_scene(store, candidate['output_scene_ref'])
    added = output['objects'][len(rows):]
    assert len(added) == len({r['source_id'] for r in added}) == 2
    assert {r['metadata']['owner_trace'] for r in added} == {'view1', 'view2'}
    assert adapter.verify(store, scene, policy, plan, candidate, {'scope': 'complete-source-and-all-patches'}, lambda _: None)['passed']
    bad = copy.deepcopy(candidate)
    bad['decisions'][1]['attachment_outcomes'].pop()
    with pytest.raises(ValueError, match='MISSING_TREATMENT'):
        adapter.verify(store, scene, policy, plan, bad, {'scope': 'complete-source-and-all-patches'}, lambda _: None)
    adapter.close()


def test_functional_legacy_route_keeps_distinct_ids_with_shared_geometry(monkeypatch):
    from src import source_channel_scope
    rows=json.loads(Path(__file__).with_name('fixtures').joinpath('t05_duplicate_additions.json').read_bytes())
    monkeypatch.setattr(cc,'ACTIVE',None);monkeypatch.setattr(source_channel_scope,'ACTIVE',object())
    ids=[addition_source_id(r)for r in rows]
    assert len(ids)==len(set(ids))==14
    assert len({r['patch_ref']['sha256']for r in rows})==4
    assert ids==[addition_source_id(r)for r in rows]
