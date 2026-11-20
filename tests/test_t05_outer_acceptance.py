"""Real source-kernel positive and adversarial public-only outer acceptance.

The tiny Gerber fixture is freshly parsed/constructed using the actual physical
checker. It is source-kernel integration evidence, not client-board qualification.
No fixture manufactures a physical PASS or exports an inner HMAC key.
"""
from copy import deepcopy
import json,os,subprocess,sys
from pathlib import Path
import pytest
from shapely import to_wkb
from shapely.geometry import box
from src.t05_outer_crypto import Signer,verify
from src.t05_outer_acceptance import expected_binding,execute_once,publish,consume
from src.t05_outer_observer import Capture
from src.stage_abi.store import canonical


def build(tmp_path,monkeypatch):
    from tests.gerber_u05.test_gerber_source import source_circle
    from src.gerber_u05 import pipeline as p,performance,guard
    from src.t04_settings import capture_job
    run=tmp_path/'legacy';store=p.Store(run/'runtime');capture_job(run)
    raw=source_circle();source=p.build_source(store,raw);p.save(run/'source.json',source)
    (run/'source_snapshot').mkdir();(run/'source_snapshot/top.art.gbr').write_bytes(raw)
    p.save(run/'LEGACY_REFERENCE_JOB.json',dict(schema='fresh-legacy-reservation-reference/1'))
    scene=store.get_json(source['scene_ref'],kind='scene')
    t04=p.run_t04(store,scene);p.save(run/'t04.json',t04)
    t02=p.run_t02(store,store.get_json(t04['output_scene_ref'],kind='scene'));p.save(run/'t02.json',t02)
    performance.capture_t05(run);guard.seal(run,'outer-source-kernel-qualification/1')
    expected=expected_binding(run,'qualification-nonce-'+os.urandom(24).hex())
    capture=Capture(run,tmp_path/'actual_reads.sqlite')
    monkeypatch.setenv('U05_WORKER_MODE','construct')
    result=execute_once(run,capture)
    signer=Signer.generate();package,timing=publish(run,capture,result,signer,expected)
    return run,store,result,package,signer,expected,capture,timing


def test_native_signature_authentication_and_no_self_declared_anchor():
    signer=Signer.generate();signature=signer.sign(b'actual bytes')
    verify(signer.public,b'actual bytes',signature)
    for public,payload,sig in ((signer.public,b'changed',signature),(Signer.generate().public,b'actual bytes',signature),(signer.public,b'actual bytes','???')):
        with pytest.raises(ValueError):verify(public,payload,sig)
    assert 'PRIVATE'not in repr(signer)


def test_real_source_worker_then_public_only_consumer_without_reconstruction(tmp_path,monkeypatch):
    run,store,result,package,signer,expected,capture,timing=build(tmp_path,monkeypatch)
    from src.u05_board.coverage import CoverageAdapter
    from src.stage_abi.loaded_geometry import GeometrySnapshot
    from src.gerber_u05 import worker,pipeline
    for method in('_operands','_blend_addition','needs','outcomes','_check','execution','run','verify'):
        monkeypatch.setattr(CoverageAdapter,method,lambda *_a,**_k:pytest.fail('outer reader reconstructed'))
    monkeypatch.setattr(GeometrySnapshot,'composed',lambda *_a,**_k:pytest.fail('outer reader composed'))
    monkeypatch.setattr(worker,'compute',lambda *_:pytest.fail('outer reader called worker'))
    monkeypatch.setattr(pipeline,'build_source',lambda *_:pytest.fail('outer reader reparsed source'))
    proof=consume(run,package,signer.public,expected)
    assert proof['status']=='PASS'and not proof['reconstruction_performed']
    assert proof['counts']['local_containments']==result['candidate']['coverage']['grown']>0
    assert capture.worker is result and timing['unique_reads']>0
    assert proof['reader_metadata_accounted_bytes']<=64*1024**2


@pytest.mark.parametrize('target',['nonce','policy','source','producer','stage','dependency','patch','region','window','manifest','group','result'])
def test_actual_corruption_or_stale_job_cannot_be_accepted(tmp_path,monkeypatch,target):
    run,store,result,package,signer,expected,capture,timing=build(tmp_path,monkeypatch)
    if target=='nonce':expected=dict(expected,job_nonce='other-job-'+os.urandom(24).hex())
    elif target in('policy','source','producer','stage'):
        name={'policy':'T05_CERTIFICATE_EXECUTION.json','source':'source_snapshot/top.art.gbr','producer':'PRODUCER_BINDING.json','stage':'t05.json'}[target]
        path=run/name;path.write_bytes(path.read_bytes()+b' ')
    else:
        group=store.get_json(package['body']['group_ref']);manifest=store.get_json(group['seal']['body']['manifest_ref'])
        cert=store.get_json(manifest['certificates'][0]['receipt_ref'])
        ref={'dependency':manifest['dependencies'][0],'patch':cert['body']['patch_ref'],
            'region':cert['body']['region_ref'],'window':cert['body']['window_ref'],
            'manifest':group['seal']['body']['manifest_ref'],'group':package['body']['group_ref'],
            'result':package['body']['result_ref']}[target]
        (store.root/'artifacts'/ref['artifact_id']).write_bytes(b'corrupted actual bytes')
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):
        consume(run,package,signer.public,expected)


@pytest.mark.parametrize('field',['schema','completion','expected','group_ref','result_ref','dependencies_ref'])
def test_rebound_signed_packet_rejects_without_coordinator_private_key(tmp_path,monkeypatch,field):
    run,store,result,package,signer,expected,capture,timing=build(tmp_path,monkeypatch)
    package=deepcopy(package);package['body'][field]='forged'
    with pytest.raises(ValueError,match='SIGNATURE_REJECTED'):consume(run,package,signer.public,expected)


def test_no_retained_result_blessing_or_post_guard_substitution(tmp_path,monkeypatch):
    run,store,result,package,signer,expected,capture,timing=build(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='FRESH_CONSTRUCTION'):execute_once(run,capture)
    changed=deepcopy(result);changed['candidate']['decisions'].pop()
    with pytest.raises(ValueError,match='REAL_COMPLETE_WORKER'):publish(run,capture,changed,signer,expected)
    capture.worker=None
    with pytest.raises(ValueError,match='REAL_COMPLETE_WORKER'):publish(run,capture,result,signer,expected)


def test_public_only_fresh_processes_need_no_issuer_or_inner_keys(tmp_path,monkeypatch):
    run,store,result,package,signer,expected,capture,timing=build(tmp_path,monkeypatch)
    packet=tmp_path/'packet.json';packet.write_bytes(canonical(dict(package=package,expected=expected)))
    public=tmp_path/'PUBLIC.pem';public.write_bytes(signer.public)
    code='''
import json,sys
from pathlib import Path
from src.t05_outer_acceptance import consume
from src.u05_board.coverage import CoverageAdapter
from src.gerber_u05 import worker,pipeline
def forbidden(*a,**k):raise AssertionError('OUTER_CONSTRUCTION_FORBIDDEN')
for name in ('_operands','_blend_addition','needs','outcomes','_check','execution','run','verify'):setattr(CoverageAdapter,name,forbidden)
worker.compute=forbidden;pipeline.stage=forbidden;pipeline.build_source=forbidden
packet=json.loads(Path(sys.argv[1]).read_bytes())
print(json.dumps(consume(sys.argv[3],packet['package'],Path(sys.argv[2]).read_bytes(),packet['expected'])))
'''
    proofs=[]
    for _ in range(2):
        process=subprocess.run([sys.executable,'-B','-c',code,str(packet),str(public),str(run)],check=True,capture_output=True,text=True)
        proofs.append(json.loads(process.stdout))
    assert all(p['status']=='PASS'for p in proofs)
    assert proofs[0]['stage_sha256']==proofs[1]['stage_sha256']


@pytest.mark.parametrize('change',['missing','duplicated','wrong_head','foreign_prefix','outside_region','tiny_outside_region','window_epsilon','nonfinite_window','missing_keep'])
def test_signed_but_inconsistent_local_proofs_still_reject(tmp_path,monkeypatch,change):
    # Use a trusted test key to exercise semantic checks behind authentication.
    # This is deliberately NOT an accepted constructor output or a safe patch.
    run,store,result,package,signer,expected,capture,timing=build(tmp_path,monkeypatch)
    group=store.get_json(package['body']['group_ref']);manifest=store.get_json(group['seal']['body']['manifest_ref'])
    if change=='missing':group['accepted'].pop()
    elif change=='duplicated':group['accepted'].append(group['accepted'][0])
    elif change=='wrong_head':group['ledger_head']='0'*64
    elif change=='missing_keep':group['candidate']['decisions'].pop()
    else:
        row=manifest['certificates'][0];receipt=store.get_json(row['receipt_ref'])
        if change in('outside_region','tiny_outside_region'):
            # Even arbitrarily small outside copper cannot use the window
            # epsilon as an enclosure waiver.
            from shapely import from_wkb
            patch=from_wkb(store.get(row['patch_ref']));tiny=1e-10 if change=='tiny_outside_region'else .01
            x,y,*_=patch.bounds
            region=patch.difference(box(x-1,y-1,x+tiny,y+tiny))
            receipt['body']['region_ref']=store.put('geometry',to_wkb(region))
        elif change=='foreign_prefix':receipt['body']['prefix_count']=7
        elif change=='window_epsilon':receipt['body']['window_policy']['area_epsilon_mm2']=1.
        elif change=='nonfinite_window':receipt['body']['window_policy']['outside_area_mm2']=-1.
        row['receipt_ref']=store.put_json('t05-certificate',receipt)
        group['accepted'][0]['receipt_sha256']=__import__('src.t05_certificate_verifier',fromlist=['body_hash']).body_hash(receipt)
        group['seal']['body']['manifest_ref']=store.put_json('t05-stage-manifest',manifest)
    # Repair input/hash bindings only to reach the intended individual check;
    # no constructor guards or geometry proof are bypassed in real execution.
    from src.t05_certificate_verifier import body_hash
    from src.t05_stage_certificate_consumer import StageCertificateConsumer
    group['seal']['body']['accepted_sha256']=body_hash(group['accepted'])
    group['seal']['body']['input_sha256']=StageCertificateConsumer._input_hash(group['scene'],group['policy'],group['plan'],group['candidate'],group['execution_binding'])
    package=deepcopy(package);package['body']['group_ref']=store.put_json('t05-outer-group',group)
    package['signature']=signer.sign(canonical(package['body']))
    with pytest.raises(ValueError):consume(run,package,signer.public,expected)


@pytest.mark.parametrize('change',[None,'stage_bytes','source','producer','missing_receipt','different_pair'])
def test_saved_checkpoint_guard_binds_each_actual_receipt_and_named_producer(tmp_path,monkeypatch,change):
    # Synthetic custody fixture only: the actual current-code T05 source kernel
    # above remains freshly executed. No simulated old-stage receipt is used in
    # the client sample; its originals come from the completed frozen run.
    from src.t05_outer_acceptance import verify_checkpoint_custody,expected_binding
    from src.t05_certificate_verifier import hash_bytes
    from src.gerber_u05 import pipeline as p
    run,store,result,package,signer,expected,capture,timing=build(tmp_path,monkeypatch)
    for stage in('t01','t03'):(run/(stage+'.json')).write_bytes(canonical(dict(scope='custody-unit-fixture-only')))
    stage_hashes={};producers={}
    for stage in('t01','t03','t04','t02'):
        h=hash_bytes((run/(stage+'.json')).read_bytes());stage_hashes[stage]=h;producers[stage]='fixture-'+stage
        for mode in('construct','1','2'):
            p.save(run/'audits'/stage/(mode+'.json'),dict(status='PASS',stage=stage,candidate_sha256=h,producer_binding_sha256=producers[stage],source_sha256=expected['source_sha256']))
    if change=='stage_bytes':(run/'t02.json').write_bytes(b'changed')
    elif change=='missing_receipt':(run/'audits/t02/2.json').unlink()
    elif change in('source','producer','different_pair'):
        file=run/'audits/t02/2.json';value=json.loads(file.read_bytes())
        value[{'source':'source_sha256','producer':'producer_binding_sha256','different_pair':'candidate_sha256'}[change]]='changed'
        file.write_bytes(canonical(value))
    # Rebind ordinary file hashes to ensure the semantic custody guard itself
    # rejects changed receipts, rather than relying on the outside hash check.
    expected=expected_binding(run,'synthetic-custody-control-nonce-00000000000000000000')
    expected['checkpoint_custody']=dict(schema='verified-saved-t04-t02-custody/1',stage_producers=producers,stage_sha256=stage_hashes)
    if change is None:verify_checkpoint_custody(run,expected)
    else:
        with pytest.raises((ValueError,FileNotFoundError)):verify_checkpoint_custody(run,expected)
