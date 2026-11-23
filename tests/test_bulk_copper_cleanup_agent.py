"""Synthetic byte-custody controls, not native geometry acceptance tests."""
import base64,gzip,json
from pathlib import Path
import pytest
from src.agent_abi import bulk_copper_cleanup as abi


def fixture(tmp_path,*,t03=False,rectangles=False):
    work=tmp_path;root=work/'connection';legacy=work/'legacy';art=legacy/'runtime/artifacts'
    art.mkdir(parents=True)
    def save(path,value):
        path.parent.mkdir(parents=True,exist_ok=True);data=value if isinstance(value,bytes)else abi.encoded(value);path.write_bytes(data);return data
    def artifact(name,data):
        save(art/name,data);return dict(artifact_id=name,sha256=abi.sha(data))
    raw=b'G04 Synthetic custody test only*';source_ref=artifact('source',raw);source_sha=abi.sha(raw);sid=source_sha+':bytes:1:2'
    geom=artifact('original',b'original geometry bytes');scene_ref=artifact('scene',abi.encoded(dict(objects=[dict(source_id=sid,geometry_ref=geom,original_ref=geom)])))
    source=save(legacy/'source.json',dict(source_ref=source_ref));cfg=dict(connection_id='connection',context='original',source_sha256=source_sha,
        scene_ref=scene_ref,legacy=str(legacy),source_binding_sha256=abi.sha(source));save(root/'connection.json',cfg)
    binding=dict(context='original',accepted_t03=t03,source_sha256=source_sha,scene_ref=scene_ref,original_scene_ref=scene_ref)
    proof=dict(passed=True,positive_copper_mm2=0,rectangular_bumps_considered=rectangles,source_bytes_changed=False,topology_before=[1,0],topology_after=[1,0])
    stage=dict(operation='TRIM_ONLY',input_binding=binding,trim_only_phase=proof,
        hybrid_components=dict(continuous_source_bodies={sid:dict(wkb_hex=b'candidate geometry bytes'.hex())},changed_bulk_copper={}))
    candidate=work/'candidate/construction.json.gz';compressed=gzip.compress(abi.encoded(stage),mtime=0);save(candidate,compressed)
    ref=dict(path=str(candidate),sha256=abi.sha(compressed));report_path=work/'candidate/RESULT.json';report=save(report_path,dict(stage=ref))
    event=dict(connection_id='connection',kind='construction',display_status='Preview',completion='PRODUCER_SEALED_AFTER_SLICE_COMPLETION',
        report=dict(path=str(report_path),sha256=abi.sha(report)),geometry=ref)
    event['event_id']=abi.sha(abi.encoded(dict(connection='connection',report=event['report'],geometry=ref,status='Preview')));save(root/'queue/event.ready.json',event)
    snapshot=dict(job='job',revision='rev1',sources=[dict(sha256=source_sha)]);data=abi.encoded(snapshot);snapsha=abi.sha(data)
    state=dict(revision='rev1',event=event['event_id'],fingerprints={sid:abi.sha(b'candidate geometry bytes')});state_data=save(root/'receipts'/(snapsha+'.state.json'),state)
    save(root/'session/snapshots'/(snapsha+'.json'),data)
    save(root/'session/current.json',dict(payload=snapsha+'.json',sha256=snapsha,producerStateSHA256=abi.sha(state_data)))
    cases=[dict(id='cleanup:'+str(i),kind='bump',status=status,sources=[dict(sourceID=sid)],reviewNumber=i+1,
                boundaryKind='circular'if i==0 else 'other',path='saved path',referencePath='saved reference')for i,status in enumerate(('corrected','unresolved','ignored'))]
    presentation=dict(schema=1,job='job',revision='rev1',sceneSHA256=snapsha,sourceSHA256=source_sha,constructionSHA256=ref['sha256'],
        addedAreaMM2=0,removedAreaMM2=.01,cleanup=dict(operation='TRIM_ONLY',cases=cases,areaLimitFraction=.1,
             areaComparison='STRICTLY_LESS_THAN',areaBasis='ORIGINAL_CAUSING_PAD_OR_TRACE'))
    def presentation_write(value):
        data=abi.encoded(value);save(root/'session/presentations'/(snapsha+'.json'),dict(schema=1,sha256=abi.sha(data),payloadBase64=base64.b64encode(data).decode()))
    presentation_write(presentation)
    save(root/'session/outbox/display.json',dict(revision='rev1',payloadSHA256=snapsha,presentation='BULK_COPPER_CLEANUP',status='DISPLAY_DOM_UPDATED'))
    expected=dict(connection_id='connection',source_sha256=source_sha,original_scene_ref=scene_ref,revision='rev1',construction_sha256=ref['sha256'],component_hole_counts=[1,0])
    return root,work,expected,presentation,presentation_write


def test_byte_custody_status_and_filtered_places_are_read_only(tmp_path):
    root,work,expected,_,_=fixture(tmp_path);before={str(p):p.read_bytes()for p in work.rglob('*')if p.is_file()}
    v=abi.SavedCleanup(root,work,expected);assert v.status()['counts']==dict(corrected=1,unresolved=1,ignored=1)
    assert v.status()['display_current'] and v.status()['checkpoint_match']
    assert len(v.places('all'))==3 and len(v.places('circular'))==1 and len(v.places('reviewed'))==3
    assert [c['status']for c in v.places('ignored')]==['ignored'] and 'path'not in v.places('all')[0]
    checked=v.check_saved();assert checked['source_occurrences']==1 and checked['original_geometry_artifacts_checked']==1
    assert checked['geometry_verification']=='SAVED_ONLY_NOT_RERUN'
    assert before=={str(p):p.read_bytes()for p in work.rglob('*')if p.is_file()}


@pytest.mark.parametrize('change',['snapshot','presentation','construction','source_geometry'])
def test_corruption_stops_without_fallback(tmp_path,change):
    root,work,e,_,_=fixture(tmp_path)
    if change=='snapshot':
        p=next((root/'session/snapshots').iterdir());p.write_bytes(p.read_bytes()+b' ')
        with pytest.raises(ValueError,match='CHECKSUM'):abi.SavedCleanup(root,work,e)
    elif change=='presentation':
        p=next((root/'session/presentations').iterdir());v=json.loads(p.read_bytes());v['sha256']='0'*64;p.write_bytes(abi.encoded(v))
        with pytest.raises(ValueError,match='CHECKSUM'):abi.SavedCleanup(root,work,e)
    else:
        v=abi.SavedCleanup(root,work,e);p=work/('candidate/construction.json.gz'if change=='construction'else 'legacy/runtime/artifacts/original')
        p.write_bytes(p.read_bytes()+b'corrupt')
        with pytest.raises(ValueError,match='CHECKSUM'):v.check_saved()


@pytest.mark.parametrize('bad',['t03','rectangles','wrong_revision','wrong_source'])
def test_rebound_wrong_semantics_still_reject(tmp_path,bad):
    root,work,e,p,write=fixture(tmp_path,t03=bad=='t03',rectangles=bad=='rectangles')
    if bad=='wrong_revision':p['revision']='stale';write(p)
    if bad=='wrong_source':p['cleanup']['cases'][0]['sources'][0]['sourceID']='other:source';write(p)
    with pytest.raises(ValueError,match='LINEAGE|POLICY|REVISION|SOURCE'):
        abi.SavedCleanup(root,work,e).check_saved()


def test_revision_change_and_path_escape_reject(tmp_path):
    root,work,e,_,_=fixture(tmp_path);v=abi.SavedCleanup(root,work,e)
    with pytest.raises(ValueError,match='OUTSIDE_LACIE'):v.path(Path(__file__).resolve())
    m=root/'session/current.json';m.write_bytes(m.read_bytes()+b' ')
    with pytest.raises(ValueError,match='REVISION_CHANGED'):v.stable()


def test_dispatch_requires_current_place_revision_and_exposes_no_run(tmp_path,monkeypatch):
    from tools import pcb_workspace
    root,work,e,_,_=fixture(tmp_path);contract=work/'contract.json';contract.write_bytes(abi.encoded(dict(connection='connection',checkpoint=e)))
    monkeypatch.setattr(abi,'ROOT',work);monkeypatch.setattr(abi,'CONTRACT',contract);monkeypatch.setattr(pcb_workspace,'require_storage',lambda:work)
    result=abi.execute(abi.request('inspect_place',place_id='cleanup:1',revision='rev1'))
    assert result['result']['place']['status']=='unresolved' and not result['geometry_execution'] and not result['writes']
    with pytest.raises(ValueError,match='STALE'):abi.execute(abi.request('inspect_place',place_id='cleanup:1',revision='old'))
    with pytest.raises(ValueError,match='INVALID_CLEANUP_REQUEST'):abi.execute(abi.request('run'))
    wrong=abi.request('status');wrong['overrides']={}
    with pytest.raises(ValueError,match='INVALID_CLEANUP_REQUEST'):abi.execute(wrong)
    with pytest.raises(ValueError,match='IRRELEVANT'):abi.execute(abi.request('status',place_id='cleanup:0'))


def test_head_drift_is_reported_and_is_not_substituted(tmp_path):
    root,work,e,_,_=fixture(tmp_path);e['revision']='historical'
    v=abi.SavedCleanup(root,work,e);assert not v.status()['checkpoint_match'] and v.status()['revision']=='rev1'
