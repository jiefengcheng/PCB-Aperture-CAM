"""Producer seals, exact predecessor lineage, idempotency and selection binding."""
import json
from pathlib import Path
import pytest
from shapely.geometry import box
from shapely import to_wkb
from src.viewer_abi import live
from src.viewer_abi.publisher import encode, digest, path_data, bounds, read_current


def fixture(tmp_path):
    root=tmp_path/'link'
    root.mkdir()
    for name in ['queue','receipts','feedback','session/snapshots']:(root/name).mkdir(parents=True)
    source='a'*64; sid=source+':bytes:1:2'; g=box(0,0,1,1)
    o=dict(id=sid,sourceID=sid,layer='artwork',kind='Line',path=path_data(g),bounds=bounds(g),attributes={})
    snapshot=dict(schema=1,job='test',revision='r1',parentRevision=None,slice='baseline',status='Preview',bounds=bounds(g),affected=bounds(g),objects=[o],sources=[dict(name='test',sha256=source,layer='artwork')],evidence=[],limitations=[])
    config=dict(schema=1,connection_id='test',source_sha256=source)
    (root/'connection.json').write_bytes(encode(config));(root/'templates.json').write_bytes(encode({sid:o}))
    live.save_revision(root,snapshot,{sid:digest(g.wkb)},event='initial')
    report=tmp_path/'REPORT.json';report.write_bytes(encode(dict(status='BOUNDED_DIAGNOSTIC',input_binding=dict(source_sha256=source))))
    shapes=tmp_path/'SHAPES.json';shapes.write_bytes(encode({sid:dict(before_wkb_hex=g.wkb.hex(),after_wkb_hex=box(0,0,1.2,1).wkb.hex())}))
    return root,sid,g,report,shapes


def test_completed_event_publishes_once_and_binds_parent(tmp_path):
    root,sid,g,report,shapes=fixture(tmp_path);_,before=read_current(root/'session')
    live.enqueue(root,label='completed slice',report=report,shapes=shapes)
    assert live.tick(root)[0]['status']=='PUBLISHED'
    _,after=read_current(root/'session')
    assert after['parentRevision']==before['revision'] and after['status']=='Preview'
    assert after['objects'][0]['bounds']['width']==pytest.approx(1.2)
    assert after['evidence']==[str(report),str(shapes)]
    assert live.tick(root)==[]


def test_altered_sealed_geometry_is_retained_rejection(tmp_path):
    root,_,_,report,shapes=fixture(tmp_path);before=(root/'session/current.json').read_bytes()
    live.enqueue(root,label='sealed slice',report=report,shapes=shapes)
    shapes.write_text('{}')
    result=live.tick(root)
    assert result[0]['status']=='REJECTED' and 'LIVE_INPUT_CHANGED' in result[0]['error']
    assert (root/'session/current.json').read_bytes()==before
    assert live.tick(root)==[]  # no silent retry


def test_wrong_predecessor_and_source_fail_closed(tmp_path):
    root,sid,g,report,shapes=fixture(tmp_path);before=(root/'session/current.json').read_bytes()
    shapes.write_bytes(encode({sid:dict(before_wkb_hex=box(0,0,5,5).wkb.hex(),after_wkb_hex=g.wkb.hex())}))
    live.enqueue(root,label='wrong base',report=report,shapes=shapes)
    assert 'PREDECESSOR_MISMATCH' in live.tick(root)[0]['error']
    assert (root/'session/current.json').read_bytes()==before
    report.write_bytes(encode(dict(input_binding=dict(source_sha256='b'*64))))
    live.enqueue(root,label='wrong source',report=report,shapes=shapes)
    assert 'REPORT_SOURCE_MISMATCH' in live.tick(root)[0]['error']


def test_selection_feedback_current_and_stale(tmp_path):
    root,sid,g,report,shapes=fixture(tmp_path);_,current=read_current(root/'session')
    outbox=root/'session/outbox';outbox.mkdir()
    selection=dict(schema=1,job=current['job'],revision=current['revision'],object=current['objects'][0])
    (outbox/'selection.json').write_bytes(encode(selection));live.tick(root)
    assert json.loads((root/'feedback/latest.json').read_bytes())['status']=='CURRENT_SELECTION'
    selection['revision']='old-unknown';(outbox/'selection.json').write_bytes(encode(selection));live.tick(root)
    assert json.loads((root/'feedback/latest.json').read_bytes())['status']=='STALE_SELECTION'


def test_forged_selection_and_state_rejected(tmp_path):
    root,sid,g,report,shapes=fixture(tmp_path);m,current=read_current(root/'session')
    outbox=root/'session/outbox';outbox.mkdir()
    (outbox/'selection.json').write_bytes(encode(dict(job=current['job'],revision=current['revision'],object=dict(current['objects'][0],sourceID='forged'))))
    live.tick(root)
    assert json.loads((root/'feedback/latest.json').read_bytes())['status']=='REJECTED_SELECTION'
    state=root/'receipts'/(m['sha256']+'.state.json');state.write_text('{}')
    live.enqueue(root,label='state corruption',report=report,shapes=shapes)
    with pytest.raises(ValueError,match='LIVE_INPUT_CHANGED'):live.tick(root)


def test_orphan_state_not_treated_as_committed_event(tmp_path):
    root,sid,g,report,shapes=fixture(tmp_path)
    event=live.enqueue(root,label='not yet published',report=report,shapes=shapes)
    (root/'receipts/orphan.state.json').write_bytes(encode(dict(event=event['event_id'])))
    assert live.tick(root)[0]['status']=='PUBLISHED'


def test_duplicate_completion_is_idempotent(tmp_path):
    root,sid,g,report,shapes=fixture(tmp_path)
    first=live.enqueue(root,label='first',report=report,shapes=shapes)
    assert live.tick(root)[0]['status']=='PUBLISHED'
    again=live.enqueue(root,label='duplicate',report=report,shapes=shapes)
    assert again==first and live.tick(root)==[]
    assert len(list((root/'queue').glob('*.ready.json')))==1


def test_initialization_and_independent_construction_binding(tmp_path):
    import gzip
    legacy=tmp_path/'legacy';folder=legacy/'runtime/artifacts';folder.mkdir(parents=True)
    def artifact(kind,data):
        sha=digest(data);ref=dict(artifact_id=kind+':'+sha,sha256=sha)
        (folder/ref['artifact_id']).write_bytes(data);return ref
    raw=artifact('gerber-source',b'immutable source bytes')
    sid=raw['sha256']+':bytes:0:4';g=box(0,0,1,1)
    geometry=artifact('geometry',g.wkb)
    scene_ref=artifact('scene',encode(dict(source_sha256=raw['sha256'],objects=[dict(source_id=sid,geometry_ref=geometry)])))
    (legacy/'source.json').write_bytes(encode(dict(source_ref=raw)))
    t03=encode(dict(output_scene_ref=scene_ref));(legacy/'t03.json').write_bytes(t03)
    obj=dict(id=sid,sourceID=sid,layer='artwork',kind='Line',path=path_data(g),bounds=bounds(g),attributes={})
    template=tmp_path/'template.json';template.write_bytes(encode(dict(schema=1,job='test',objects=[obj],sources=[dict(name='test',sha256=raw['sha256'],layer='artwork')])))
    binding=dict(source_sha256=raw['sha256'],t03_sha256=digest(t03),scene_ref=scene_ref)
    stage=dict(input_binding=binding,hybrid_components=dict(continuous_source_bodies={sid:dict(wkb_hex=box(0,0,1.5,1).wkb.hex())},changed_bulk_copper={}))
    initial=tmp_path/'construction.gz';initial.write_bytes(gzip.compress(encode(stage)))
    root=tmp_path/'connection'
    live.initialize(root,template=template,legacy=legacy,construction=initial,thread='test-thread')
    assert read_current(root/'session')[1]['objects'][0]['bounds']['width']==1.5
    stage['hybrid_components']['continuous_source_bodies'][sid]['wkb_hex']=box(0,0,2,1).wkb.hex()
    next_stage=tmp_path/'next.gz';next_stage.write_bytes(gzip.compress(encode(stage)))
    report=tmp_path/'report.json';report.write_bytes(encode(dict(input_binding=binding)))
    (root/'session/outbox').mkdir()
    (root/'session/outbox/display.json').write_bytes(encode(dict(payloadSHA256=read_current(root/'session')[0]['sha256'])))
    live.enqueue(root,label='new construction',report=report,construction=next_stage)
    assert live.tick(root)[0]['status']=='PUBLISHED'
    assert read_current(root/'session')[1]['objects'][0]['bounds']['width']==2
    stage['input_binding']['source_sha256']='f'*64
    bad=tmp_path/'wrong.gz';bad.write_bytes(gzip.compress(encode(stage)))
    (root/'session/outbox/display.json').write_bytes(encode(dict(payloadSHA256=read_current(root/'session')[0]['sha256'])))
    live.enqueue(root,label='wrong construction',report=report,construction=bad)
    assert 'CONSTRUCTION_LINEAGE_MISMATCH' in live.tick(root)[0]['error']


def test_selection_clear_feedback(tmp_path):
    root,sid,g,report,shapes=fixture(tmp_path);_,current=read_current(root/'session')
    outbox=root/'session/outbox';outbox.mkdir()
    (outbox/'selection.json').write_bytes(encode(dict(job=current['job'],revision=current['revision'],object=None)))
    live.tick(root)
    assert json.loads((root/'feedback/latest.json').read_bytes())['status']=='SELECTION_CLEARED'


def test_live_queue_waits_for_native_display_ack(tmp_path):
    root,sid,g,report,shapes=fixture(tmp_path)
    config=json.loads((root/'connection.json').read_bytes());config['require_display_ack']=True
    (root/'connection.json').write_bytes(encode(config))
    live.enqueue(root,label='await native canvas',report=report,shapes=shapes)
    assert live.tick(root)==[]
    m,_=read_current(root/'session');outbox=root/'session/outbox';outbox.mkdir()
    (outbox/'display.json').write_bytes(encode(dict(payloadSHA256='wrong')))
    assert live.tick(root)==[]
    (outbox/'display.json').write_bytes(encode(dict(payloadSHA256=m['sha256'])))
    assert live.tick(root)[0]['status']=='PUBLISHED'


def test_benchmark_feed_requires_terminal_marker_and_sealed_construction(tmp_path):
    root,sid,g,report,shapes=fixture(tmp_path)
    q=tmp_path/'qualification';case=q/'hard_baseline';case.mkdir(parents=True)
    script=tmp_path/'producer.py';script.write_text('# known immutable producer')
    log=tmp_path/'producer.log';log.write_text('{"event":"PROGRESS"}\n')
    construction=case/'construction.json.gz';construction.write_bytes(b'finished construction')
    receipt=dict(kind='hard',enabled=False,stage_wall_s=2.5,checks=dict(native_connections=dict(checked=41,passed=41)),stage=dict(path=str(construction),sha256=digest(construction.read_bytes())))
    (case/'CASE.json').write_bytes(encode(receipt))
    live.attach_benchmark(root,log=log,qualification=q,script=script)
    live.ingest_benchmark(root);assert not list((root/'queue').glob('*.ready.json'))
    marker=dict(event='CASE_DONE',kind='hard',enabled=False,stage_wall_s=2.5,connections=receipt['checks']['native_connections'])
    with log.open('ab') as f:f.write(encode(marker))
    live.ingest_benchmark(root);assert not list((root/'queue').glob('*.ready.json'))  # partial line
    with log.open('ab') as f:f.write(b'\n')
    live.ingest_benchmark(root);assert len(list((root/'queue').glob('*.ready.json')))==1
    live.ingest_benchmark(root);assert len(list((root/'queue').glob('*.ready.json')))==1
    log.write_text('rewritten\n')
    with pytest.raises(ValueError,match='LOG_REWRITTEN'):live.ingest_benchmark(root)
