import gzip
import json
from pathlib import Path

import pytest

from src import copper_phase_seal as seals
from src.large_copper_runner import run
from src.viewer_abi.publisher import encode,digest


def make_cleanup(tmp_path):
    # Supported positive source with a genuine boundary cap to trim.
    raw=('G04 seal fixture '+digest(str(tmp_path).encode())+'*\n'+'''%FSLAX46Y46*%
%MOMM*%
%IPPOS*%
%ADD10R,4X4*%
%ADD11C,0.0508*%
%LPD*%
D10*
X2000000Y2000000D03*
D11*
X10000Y2000000D02*
X2000000Y2000000D01*
M02*
''').encode()
    source=tmp_path/'source.gbr';source.write_bytes(raw)
    run(source,output=tmp_path/'cleanup')
    return tmp_path/'cleanup'


def test_cleanup_output_is_ordered_pinned_and_verifies_without_replaying_geometry(tmp_path,monkeypatch):
    job=make_cleanup(tmp_path);ref=seals.publish(job,tmp_path/'cleanup.output.json')
    monkeypatch.setattr(seals,'_inspect',lambda *a,**k:pytest.fail('verification replayed producer'))
    value=seals.verify(**dict(path=ref['path'],sha256=ref['sha256']),phase='large_copper')
    assert value['occurrence_count']==2 and value['parent']is None
    assert value['original_geometry_sha256']!=value['output_geometry_sha256']
    assert value['acceptance'].startswith('SAVED_PHASE_CUSTODY_ONLY')
    assert value['shared_preparation_key']
    binding=json.loads((job/'source.json').read_bytes())
    for name in('source_catalogue_ref','width_metadata_encoding_ref'):
        assert 'runtime/artifacts/'+binding[name]['artifact_id']in value['files']
    assert not (job/'t04').exists()
    with pytest.raises(FileExistsError):seals.publish(job,ref['path'])


@pytest.mark.parametrize('target',['RESULT.json','construction.json.gz','source.json','artifact','width_metadata'])
def test_mutated_producer_bytes_stop_consumer_and_remain_retained(tmp_path,target):
    job=make_cleanup(tmp_path);ref=seals.publish(job,tmp_path/'cleanup.output.json')
    value=json.loads(Path(ref['path']).read_bytes())
    if target=='artifact':name=next(k for k in value['files']if k.startswith('runtime/artifacts/geometry:'))
    elif target=='width_metadata':name='runtime/artifacts/'+json.loads((job/'source.json').read_bytes())['width_metadata_encoding_ref']['artifact_id']
    else:name=target
    path=job/name;path.write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='DEPENDENCY_CHANGED'):seals.verify(ref['path'],ref['sha256'])
    assert path.read_bytes()==b'corrupted'


def test_unpinned_changed_seal_and_wrong_phase_reject(tmp_path):
    job=make_cleanup(tmp_path);ref=seals.publish(job,tmp_path/'cleanup.output.json')
    with pytest.raises(ValueError,match='TYPE_CHANGED'):seals.verify(ref['path'],ref['sha256'],phase='t04')
    path=Path(ref['path']);path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError,match='DIGEST_CHANGED'):seals.verify(path,ref['sha256'])


def test_added_policy_file_cannot_silently_change_consumer_intake(tmp_path):
    job=make_cleanup(tmp_path);ref=seals.publish(job,tmp_path/'cleanup.output.json')
    (job/'PIN_SEPARATION_POLICY.json').write_text('{}')
    with pytest.raises(ValueError,match='POLICY_INVENTORY_CHANGED'):seals.verify(ref['path'],ref['sha256'])


def test_incorrect_source_order_cannot_be_sealed_even_with_new_byte_hashes(tmp_path):
    job=make_cleanup(tmp_path);result=json.loads((job/'RESULT.json').read_bytes())
    stage=json.loads(gzip.decompress((job/'construction.json.gz').read_bytes()))
    stage['ordered_source_ids'].reverse();raw=encode(stage)
    (job/'construction.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    result['stage'].update(sha256=seals.file_sha(job/'construction.json.gz'),stage_sha256=digest(raw))
    (job/'RESULT.json').write_bytes(encode(result))
    with pytest.raises(ValueError,match='SOURCE_ORDER_CHANGED'):seals.publish(job,tmp_path/'seal.json')
    assert not (tmp_path/'seal.json').exists()


def test_interrupted_publication_has_no_committed_seal_and_retains_partial(tmp_path,monkeypatch):
    job=make_cleanup(tmp_path)
    def interrupted(*a):raise OSError('publication interrupted')
    monkeypatch.setattr(seals.os,'link',interrupted)
    with pytest.raises(OSError):seals.publish(job,tmp_path/'seal.json')
    assert not (tmp_path/'seal.json').exists()
    assert len(list(tmp_path.glob('.seal.json.*.partial')))==1


def test_artifact_symlink_is_not_a_sealed_file(tmp_path):
    job=make_cleanup(tmp_path);ref=seals.publish(job,tmp_path/'seal.json')
    payload=json.loads(Path(ref['path']).read_bytes());name=next(k for k in payload['files']if k.startswith('runtime/artifacts/geometry:'))
    path=job/name;retained=tmp_path/'retained-geometry';path.rename(retained);path.symlink_to(retained)
    with pytest.raises(ValueError,match='LINK'):seals.verify(ref['path'],ref['sha256'])


def test_only_exact_sealed_trim_entry_avoids_an_unrelated_additive_reference(tmp_path):
    from src.gerber_u05 import pipeline as p,bounded_order as b
    from src.gerber_u05.profile_intake import EvidenceStore
    from src.gerber_u05.trimmed_entry import load_cleanup,bind_floor,sealed_subtractive_entry
    job=make_cleanup(tmp_path);ref=seals.publish(job,tmp_path/'cleanup.output.json')
    reader=EvidenceStore(job);binding=json.loads((job/'source.json').read_bytes())
    store=b.ExperimentStore(tmp_path/'consumer/runtime',reader)
    original=reader.get_json(binding['scene_ref'],kind='scene');rows,current,raw=p.operands(store,original)
    _,changes,custody=load_cleanup(job/'RESULT.json',binding['source_ref']['sha256'])
    current.update(changes);custody['seal']=ref;receipt=bind_floor(rows,current,raw,custody)
    scene=store.get_json(p.artifact_scene(store,original,current,'verified-large-copper-trim-entry'),kind='scene')
    scene['lineage'][-1]['receipt_ref']=store.put_json('t04-trimmed-entry',receipt)
    assert sealed_subtractive_entry(store,scene)
    altered=json.loads(json.dumps(scene));altered['objects'][1]['geometry_ref']=original['objects'][1]['geometry_ref']
    with pytest.raises(ValueError,match='SUBTRACTIVE_ENTRY_BINDING_CHANGED'):sealed_subtractive_entry(store,altered)
    altered=json.loads(json.dumps(scene));altered['lineage'].append(dict(stage='arbitrary-additive-predecessor'))
    assert not sealed_subtractive_entry(store,altered)
