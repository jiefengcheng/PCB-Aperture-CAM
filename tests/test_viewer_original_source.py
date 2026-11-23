"""Original-source presentation must never inherit retained T01/T03 copper."""
import gzip
import json
from pathlib import Path
import pytest
from shapely.geometry import box
from src.viewer_abi import live
from src.viewer_abi.publisher import encode, digest, path_data, bounds, read_current


def source_case(tmp_path, *, changed=False):
    legacy=tmp_path/'legacy'; folder=legacy/'runtime/artifacts'; folder.mkdir(parents=True)
    def artifact(kind, raw):
        ref=dict(artifact_id=kind+':'+digest(raw),sha256=digest(raw))
        (folder/ref['artifact_id']).write_bytes(raw); return ref
    raw=artifact('gerber-source',b'original source custody unit fixture')
    g=box(0,0,1,1); geom=artifact('geometry',g.wkb)
    grown=artifact('geometry',box(0,0,3,3).wkb)
    sid=raw['sha256']+':bytes:0:4'
    scene=dict(source_sha256=raw['sha256'],lineage=[dict(stage='gerber-source-intake')],
               objects=[dict(source_id=sid,geometry_ref=grown if changed else geom,original_ref=geom)])
    ref=artifact('scene',encode(scene))
    (legacy/'source.json').write_bytes(encode(dict(source_ref=raw,scene_ref=ref)))
    # There is deliberately no t03.json. The old display template has grown land copper.
    obj=dict(id=sid,sourceID=sid,layer='artwork',kind='Flash',path=path_data(box(0,0,3,3)),bounds=bounds(box(0,0,3,3)),attributes={})
    template=tmp_path/'template.json'
    template.write_bytes(encode(dict(schema=1,job='old',objects=[obj],sources=[dict(name='test',sha256=raw['sha256'],layer='artwork')])))
    binding=dict(source_sha256=raw['sha256'],scene_ref=ref,original_scene_ref=ref,context='original',accepted_t03=False)
    stage=dict(input_binding=binding,hybrid_components=dict(continuous_source_bodies={},changed_bulk_copper={}))
    construction=tmp_path/'stage.gz'; construction.write_bytes(gzip.compress(encode(stage)))
    return legacy,template,construction,stage,sid


def test_original_connection_drops_post_t01_template_geometry_without_any_t03(tmp_path):
    legacy,template,construction,stage,sid=source_case(tmp_path)
    root=tmp_path/'link'
    config=live.initialize(root,template=template,legacy=legacy,construction=construction,thread='case',context='original')
    assert 't03_sha256'not in config and config['context']=='original'
    assert read_current(root/'session')[1]['objects'][0]['bounds']['width']==1
    assert json.loads(Path(config['template']['path']).read_bytes())['objects'][0]['bounds']['width']==1
    report=tmp_path/'report.json'; report.write_bytes(encode(dict(input_binding=stage['input_binding'])))
    stage['hybrid_components']['continuous_source_bodies'][sid]=dict(wkb_hex=box(0,0,1.5,1).wkb.hex())
    construction.write_bytes(gzip.compress(encode(stage)))
    (root/'session/outbox').mkdir()
    (root/'session/outbox/display.json').write_bytes(encode(dict(payloadSHA256=read_current(root/'session')[0]['sha256'])))
    live.enqueue(root,label='source case',report=report,construction=construction)
    assert live.tick(root)[0]['status']=='PUBLISHED'
    assert read_current(root/'session')[1]['objects'][0]['bounds']['width']==1.5


@pytest.mark.parametrize('field,value',[('accepted_t03',True),('context','retained_t03'),('original_scene_ref',{}),('t03_sha256','a'*64)])
def test_original_connection_rejects_false_predecessor_and_acceptance(tmp_path,field,value):
    legacy,template,construction,stage,sid=source_case(tmp_path)
    root=tmp_path/'link'
    config=live.initialize(root,template=template,legacy=legacy,construction=construction,thread='case',context='original')
    stage['input_binding'][field]=value
    with pytest.raises(ValueError,match='LINEAGE_MISMATCH'):
        live.construction_map(stage,config)


def test_original_connection_cannot_accept_source_scene_with_grown_objects(tmp_path):
    legacy,template,construction,stage,sid=source_case(tmp_path,changed=True)
    with pytest.raises(ValueError,match='ORIGINAL_SOURCE_SCENE_REQUIRED'):
        live.initialize(tmp_path/'link',template=template,legacy=legacy,construction=construction,thread='case',context='original')
