"""Selection uses exact committed bodies, including earlier snapshots and patches."""
import gzip
import json
from pathlib import Path
import pytest
from shapely.geometry import box
from src.viewer_abi import live
from src.viewer_abi.publisher import encode, digest, path_data, bounds, read_current
from src.viewer_abi.trace_selection import trace_response


def setup(tmp_path, *, members=1):
    legacy = tmp_path/'legacy'; folder = legacy/'runtime/artifacts'; folder.mkdir(parents=True)
    def artifact(kind, data):
        sha = digest(data); ref = dict(artifact_id=kind+':'+sha, sha256=sha)
        (folder/ref['artifact_id']).write_bytes(data); return ref
    raw = artifact('source', b'synthetic trace source'); sid = raw['sha256']+':bytes:1:2'
    original = box(0,0,5,.05); candidate = box(0,-.008,5,.067)
    geom = artifact('geometry',original.wkb)
    rows = [dict(source_id=sid,geometry_ref=geom,original_ref=geom,
                 metadata=dict(route_points_mm=[[0.,.025],[5.,.025]]))]
    objects = []
    bodies = {sid:dict(wkb_hex=candidate.wkb.hex())}
    if members == 2:
        other = raw['sha256']+':bytes:2:3'
        second = box(5,0,10,.05); second_ref = artifact('geometry', second.wkb)
        rows.append(dict(source_id=other,geometry_ref=second_ref,original_ref=second_ref,
                         metadata=dict(route_points_mm=[[5.,.025],[10.,.025]])))
        bodies[other] = dict(wkb_hex=box(5,-.008,10,.067).wkb.hex())
        objects.append(dict(id=other,sourceID=other,kind='Line',layer='artwork',path=path_data(second),bounds=bounds(second),attributes={}))
    scene_ref = artifact('scene',encode(dict(source_sha256=raw['sha256'],objects=rows)))
    (legacy/'source.json').write_bytes(encode(dict(source_ref=raw)))
    t03 = encode(dict(output_scene_ref=scene_ref)); (legacy/'t03.json').write_bytes(t03)
    obj = dict(id=sid,sourceID=sid,kind='Line',layer='artwork',path=path_data(original),bounds=bounds(original),attributes={})
    template = tmp_path/'template.json'; template.write_bytes(encode(dict(schema=1,job='old',revision='template',slice='context',status='Preview',bounds=bounds(box(0,0,5*members,.05)),affected=bounds(original),objects=[obj,*objects],sources=[dict(name='source',sha256=raw['sha256'],layer='artwork')],evidence=[],limitations=[])))
    stage = dict(input_binding=dict(source_sha256=raw['sha256'],t03_sha256=digest(t03),scene_ref=scene_ref),
                 hybrid_components=dict(continuous_source_bodies=bodies,changed_bulk_copper={}),
                 native_trace_source_ids_by_route={'route-one':[r['source_id'] for r in rows]})
    construction = tmp_path/'construction.json.gz'; construction.write_bytes(gzip.compress(encode(stage)))
    root = tmp_path/'link'; live.initialize(root,template=template,legacy=legacy,construction=construction,thread='test')
    config = live.load_connection(root); config['require_display_ack'] = False
    (root/'connection.json').write_bytes(encode(config))
    _, current = read_current(root/'session')
    selection = dict(job=current['job'],revision=current['revision'],object=current['objects'][0])
    return root, selection, sid, original, candidate, geom, folder


def test_arbitrary_source_and_exact_original_growth(tmp_path):
    root, selection, sid, original, candidate, _, _ = setup(tmp_path)
    answer = trace_response(root,selection)
    assert answer['objectID'] == sid
    assert answer['comparison']['addedAreaMM2'] == pytest.approx(.125)
    assert answer['comparison']['removedAreaMM2'] == 0
    assert 'route-one' in answer['text']
    assert answer['comparison']['currentWkbSHA256'] == digest(candidate.wkb)


def test_original_width_keep_does_not_show_superseded_growth_allocations():
    from src.viewer_abi.trace_selection import treatment_details
    stage = dict(native_trace_source_ids_by_route={'route':['kept']},
                 owner_nominal_width_keep_retraction=dict(source_ids=['kept']),
                 groups=[dict(catalogue_band_index=1, lanes=[dict(source_ids=['kept'],
                     source_width_mm=.249935, width_mm=.279935)])], hybrid_components={})
    details = treatment_details(stage, 'kept')
    assert any('Original source width retained' in text for text in details)
    assert not any('Recorded span width' in text for text in details)


def test_source_focus_uses_authenticated_native_points_and_cannot_change_copper(tmp_path):
    root,selection,sid,original,candidate,_,_=setup(tmp_path)
    config=live.load_connection(root);_,scene=read_current(root/'session')
    objects={o['id']:o for o in scene['objects']}
    focus=dict(source_id=sid,route_point_index=1,radius_mm=.2)
    assert live.source_focus(config,{'viewer_source_focus':focus},objects)==pytest.approx(dict(x=4.8,y=-.175,width=.4,height=.4))
    assert trace_response(root,selection)['comparison']['currentWkbSHA256']==digest(candidate.wkb)
    with pytest.raises(ValueError,match='POINT_REQUIRED'):
        live.source_focus(config,{'viewer_source_focus':dict(focus,route_point_index=2)},objects)
    with pytest.raises(ValueError,match='FOCUS_REQUIRED'):
        live.source_focus(config,{'viewer_source_focus':dict(focus,source_id='wrong')},objects)


def test_previous_snapshot_and_changed_patch_use_own_bodies(tmp_path):
    root, prior, sid, original, candidate, _, _ = setup(tmp_path)
    report = tmp_path/'CASE.json'; report.write_text('{}')
    grown = box(0,-.01,5,.07)
    shapes = tmp_path/'shapes.json'; shapes.write_bytes(encode({sid:dict(before_wkb_hex=candidate.wkb.hex(),after_wkb_hex=grown.wkb.hex())}))
    live.enqueue(root,label='next',report=report,shapes=shapes); assert live.tick(root)[0]['status'] == 'PUBLISHED'
    _, now = read_current(root/'session'); current = dict(job=now['job'],revision=now['revision'],object=now['objects'][0])
    assert trace_response(root,prior)['comparison']['currentWkbSHA256'] == digest(candidate.wkb)
    assert trace_response(root,current)['comparison']['currentWkbSHA256'] == digest(grown.wkb)
    # A patch for no occurrences inherits the previous committed source body.
    empty = tmp_path/'empty.json'; empty.write_text('{}')
    live.enqueue(root,label='same',report=report,shapes=empty); assert live.tick(root)[0]['status'] == 'PUBLISHED'
    _, now = read_current(root/'session'); current = dict(job=now['job'],revision=now['revision'],object=now['objects'][0])
    assert trace_response(root,current)['comparison']['currentWkbSHA256'] == digest(grown.wkb)
    with pytest.raises(ValueError,match='BINDING_MISMATCH'):
        trace_response(root,prior)  # now older than Current/Previous


def test_forged_selection_and_changed_source_fail_closed(tmp_path):
    root, selection, sid, _, _, geom, folder = setup(tmp_path)
    forged = dict(selection,object=dict(selection['object'],path=path_data(box(0,0,8,8))))
    with pytest.raises(ValueError,match='BINDING_MISMATCH'):trace_response(root,forged)
    (folder/geom['artifact_id']).write_bytes(b'changed source')
    with pytest.raises(ValueError,match='LIVE_INPUT_CHANGED'):trace_response(root,selection)


def test_missing_t04_body_is_explicit_context_not_substituted(tmp_path):
    root, selection, sid, original, candidate, _, _ = setup(tmp_path)
    config = live.load_connection(root); stage = json.loads(gzip.decompress(Path(config['construction']['path']).read_bytes()))
    stage['hybrid_components']['continuous_source_bodies'] = {}
    report = tmp_path/'CASE.json'; report.write_text('{}')
    construction = tmp_path/'context.json.gz'; construction.write_bytes(gzip.compress(encode(stage)))
    live.enqueue(root,label='context-only cohort',report=report,construction=construction);live.tick(root)
    _, now = read_current(root/'session'); selection = dict(job=now['job'],revision=now['revision'],object=now['objects'][0])
    answer = trace_response(root,selection)
    assert 'no constructed T04 body in this slice' in answer['text']
    assert answer['comparison']['currentWkbSHA256'] == digest(original.wkb)
    assert answer['comparison']['added'] is None


def test_maintained_route_assembles_all_members_and_reuses_display_cache(tmp_path):
    root, selection, sid, _, _, _, _ = setup(tmp_path, members=2)
    from shapely.ops import unary_union
    from src.viewer_abi.live import display
    first = trace_response(root,selection)['route']
    assert first['routeID'] == 'route-one' and len(first['members']) == 2
    assert first['assembled']['path'] == path_data(display(unary_union([box(0,-.008,5,.067),box(5,-.008,10,.067)]))[0])
    assert first['members'][0]['points'] == [[0.,.025],[5.,.025]]
    assert first['comparison']['addedAreaMM2'] == pytest.approx(.25)
    assert first['comparison']['removedAreaMM2'] == 0
    assert first['comparison']['currentWkbSHA256'] == first['currentWkbSHA256']
    assert first['comparison']['selectedPathSHA256'] == digest(first['assembled']['path'].encode())
    _, scene = read_current(root/'session')
    sibling = dict(selection, object=next(o for o in scene['objects'] if o['sourceID'] != sid))
    assert trace_response(root,sibling)['route'] == first
    assert len([p for p in (root/'route-cache').glob('*.json') if not p.name.startswith('index-')]) == 1
    assert len(list((root/'route-cache').glob('index-*.json'))) == 1


def test_route_growth_uses_union_difference_not_overlapping_member_changes(tmp_path):
    root, selection, sid, _, candidate, _, _ = setup(tmp_path, members=2)
    before = trace_response(root, selection)['route']
    other = before['members'][1]['sourceID']
    # Move ownership of the shared span between members without changing the
    # complete copper area. Source-level added/removed areas are both nonzero.
    report = tmp_path/'CASE.json'; report.write_text('{}')
    shapes = tmp_path/'joint-ownership.json'
    shapes.write_bytes(encode({
        sid: dict(before_wkb_hex=candidate.wkb.hex(), after_wkb_hex=box(0,0,6,.05).wkb.hex()),
        other: dict(before_wkb_hex=box(5,-.008,10,.067).wkb.hex(), after_wkb_hex=box(6,0,10,.05).wkb.hex())}))
    live.enqueue(root, label='same route area, changed member overlap', report=report, shapes=shapes)
    assert live.tick(root)[0]['status'] == 'PUBLISHED'
    _, scene = read_current(root/'session')
    now = dict(job=scene['job'], revision=scene['revision'], object=next(o for o in scene['objects'] if o['id']==sid))
    answer = trace_response(root, now)
    assert answer['comparison']['addedAreaMM2'] > 0
    assert answer['route']['comparison']['added'] is None
    assert answer['route']['comparison']['removed'] is None
    assert answer['route']['comparison']['addedAreaMM2'] == 0
    assert answer['route']['comparison']['removedAreaMM2'] == 0
    assert trace_response(root, selection)['route'] == before


def test_route_cache_corruption_and_other_member_source_corruption_fail_closed(tmp_path):
    root, selection, sid, _, _, _, folder = setup(tmp_path, members=2)
    route = trace_response(root,selection)['route']
    target = root/'route-cache'/(route['bindingSHA256']+'.json')
    saved = target.read_bytes(); envelope = json.loads(saved)
    envelope['route']['routeID'] = 'forged-route'; target.write_bytes(encode(envelope))
    with pytest.raises(ValueError,match='ROUTE_CACHE_CHANGED'):trace_response(root,selection)
    target.write_bytes(saved)
    original = route['members'][1]['originalWkbSHA256']
    (folder/('geometry:'+original)).write_bytes(b'altered neighbor')
    with pytest.raises(ValueError,match='LIVE_INPUT_CHANGED'):trace_response(root,selection)


def test_route_patch_resolves_other_members_without_reusing_an_old_route(tmp_path):
    root, selection, sid, _, candidate, _, _ = setup(tmp_path, members=2)
    before = trace_response(root,selection)['route']
    report=tmp_path/'CASE.json'; report.write_text('{}')
    shapes=tmp_path/'patch.json'; shapes.write_bytes(encode({sid:dict(before_wkb_hex=candidate.wkb.hex(),after_wkb_hex=box(0,-.01,5,.08).wkb.hex())}))
    live.enqueue(root,label='partial route patch',report=report,shapes=shapes);live.tick(root)
    _, scene=read_current(root/'session'); current=dict(job=scene['job'],revision=scene['revision'],object=next(o for o in scene['objects']if o['id']==sid))
    after=trace_response(root,current)['route']
    assert after['bindingSHA256'] != before['bindingSHA256'] and len(after['members']) == 2
    assert after['members'][1]['currentWkbSHA256'] == before['members'][1]['currentWkbSHA256']
    assert trace_response(root,selection)['route'] == before


def test_route_selection_feedback_cannot_claim_another_membership(tmp_path):
    root, selection, _, _, _, _, _ = setup(tmp_path, members=2)
    route = trace_response(root,selection)['route']
    selection = dict(selection,selectionMode='route',route=dict(routeID=route['routeID'],bindingSHA256=route['bindingSHA256'],
        catalogueSHA256=route['catalogueSHA256'],memberSourceIDs=[m['sourceID']for m in route['members']]))
    target=root/'session/outbox/selection.json';target.parent.mkdir(exist_ok=True);target.write_bytes(encode(selection))
    assert live.feedback(root)['status']=='CURRENT_SELECTION'
    selection['route']['memberSourceIDs'].pop();target.write_bytes(encode(selection))
    with pytest.raises(ValueError,match='ROUTE_FEEDBACK_MISMATCH'):live.feedback(root)


def test_route_catalogue_keeps_covered_members_and_group_references(tmp_path):
    root, selection, sid, _, _, _, _ = setup(tmp_path,members=2)
    config=live.load_connection(root);stage=json.loads(gzip.decompress(Path(config['construction']['path']).read_bytes()))
    members=stage['native_trace_source_ids_by_route']['route-one'];covered=members[1]
    del stage['hybrid_components']['continuous_source_bodies'][covered]
    stage['groups']=[dict(maximal_group_id='PGS-saved',catalogue_band_index='saved-band',lanes=[dict(source_ids=[sid],source_width_mm=.05,width_mm=.075)])]
    report=tmp_path/'CASE.json';report.write_text('{}');path=tmp_path/'covered.json.gz';path.write_bytes(gzip.compress(encode(stage)))
    live.enqueue(root,label='covered context',report=report,construction=path);live.tick(root)
    _,scene=read_current(root/'session');selected=dict(job=scene['job'],revision=scene['revision'],object=next(o for o in scene['objects']if o['id']==sid))
    answer=trace_response(root,selected)['route'];assert len(answer['members'])==2
    assert answer['members'][1]['currentWkbSHA256']==answer['members'][1]['originalWkbSHA256']
    assert answer['groups']==[dict(kind='straight',id='PGS-saved')]


def test_route_loads_construction_once_per_request_and_cache_hit_skips_union(tmp_path,monkeypatch):
    root, selection, _, _, _, _, _ = setup(tmp_path,members=2)
    from src.viewer_abi import trace_selection as trace,route_presentation as route
    construction=live.load_connection(root)['construction']['path'];calls=[];read=trace.read_bound
    def observe(path,sha):
        if str(path)==construction:calls.append(str(path))
        return read(path,sha)
    monkeypatch.setattr(trace,'read_bound',observe)
    before=trace_response(root,selection)['route'];assert len(calls)==1
    def unexpected(*a,**k):raise AssertionError('A cached route must not rebuild its union')
    monkeypatch.setattr(route,'unary_union',unexpected)
    assert trace_response(root,selection)['route']==before


def test_compact_route_catalogue_uses_recorded_roles_and_pins_source(tmp_path):
    from src.viewer_abi.route_presentation import bind_catalogue
    root, selection, sid, _, _, _, _ = setup(tmp_path,members=2)
    config=live.load_connection(root);prepared=tmp_path/'prepared';prepared.mkdir()
    other=sid.replace(':1:2',':2:3')
    admission=gzip.compress(encode(dict(admitted=[dict(path_id='route-one',source_ids=[sid,other]),dict(path_id='bulk-route',source_ids=['bulk'])])))
    roles=gzip.compress(encode(dict(roles={'bulk':{}},classes={})))
    (prepared/'admission.json.gz').write_bytes(admission);(prepared/'ROLES.json.gz').write_bytes(roles)
    binding=dict(schema='t04-source-role-preparation/1',source_sha256=config['source_sha256'],scene_sha256=config['scene_ref']['sha256'],files={'admission.json.gz':digest(admission),'ROLES.json.gz':digest(roles)})
    (prepared/'BINDING.json').write_bytes(encode(binding))
    result=bind_catalogue(root,prepared);assert result['routes']==1 and result['members']==2
    answer=trace_response(root,selection)
    assert len(answer['routeIndex']['entries'])==1 and answer['routeIndex']['entries'][0]['objectIndices']==[0,1]
    pinned=(root/'connection.json').read_bytes();(prepared/'admission.json.gz').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='LIVE_INPUT_CHANGED'):bind_catalogue(root,prepared)
    assert (root/'connection.json').read_bytes()==pinned
