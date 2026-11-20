"""Opt-in cross-process acceptance of ONE freshly completed legacy T05 worker.

The coordinator pins a per-job public anchor, nonce, source/producer/input
binding. Only the trusted construction process receives signing capability.
Signing requires the live completed inner authority AND the real worker's
post-guard observation. Public-only readers hash actual inputs/output and
consume exact local proofs; they do not reconstruct or measure clearance.

This replaces repeat-build acceptance, not independent implementation review.
Repeated-build determinism remains an explicit audit mode. Connected finishing,
post-junction pocket remedies and arbitrary prior unsigned results are excluded.
"""
from collections import Counter
from hmac import compare_digest, digest as mac
from math import isfinite
from pathlib import Path
import json,os,sqlite3,stat
from time import perf_counter
from shapely import from_wkb
from src.stage_abi.store import canonical
from src.stage_abi.contracts import ref as validate_ref,finite_json
from src.t05_certificate_verifier import body_hash,hash_bytes,require,SCHEMA as LOCAL_SCHEMA
from src.t05_certified_enclosure import WINDOW_SCHEMA
from src.t05_stage_certificate_consumer import SCHEMA as STAGE_SCHEMA,artifact_refs,StageCertificateConsumer
from src.t05_outer_crypto import verify,backend_identity
from src.u05_board.store import ReadOnlyStore

SCHEMA='pcb-cam/t05-outer-certified-acceptance/1'
PROFILE='legacy-t05-completed-worker/1'
READER_METADATA_LIMIT=64*1024**2


def file_bytes(path):
    """No symlink/fifo leaf; actual bytes, never a stat cache."""
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb')as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode),'OUTER_FILE_UNSAFE')
        return stream.read()


def producer_projection():
    from src.gerber_u05.guard import ROOT,producer_files
    return body_hash({str(p.relative_to(ROOT)):hash_bytes(file_bytes(p))for p in producer_files()})


def input_files(run):
    """Actual source, frozen options, predecessors and their complete receipts."""
    run=Path(run);seal=json.loads(file_bytes(run/'PRODUCER_BINDING.json'))
    paths={run/'source.json',run/'PRODUCER_BINDING.json'}
    paths.update(run/name for name in('t01.json','t03.json','t04.json','t02.json')if(run/name).exists())
    for directory in('source_snapshot','audits/t01','audits/t03','audits/t04','audits/t02'):
        folder=run/directory
        if folder.exists():paths.update(p for p in folder.rglob('*')if p.is_file())
    for name in seal.get('job_inputs',{}):
        path=Path(name)
        require(path.resolve().is_relative_to(run.resolve()),'OUTER_INPUT_OUTSIDE_JOB')
        paths.add(path)
    require(not any(p.is_symlink()for p in paths),'OUTER_INPUT_SYMLINK')
    return {str(p.relative_to(run)):hash_bytes(file_bytes(p))for p in sorted(paths)}


def expected_binding(run,nonce,*,inputs=None):
    """Called by the trusted coordinator BEFORE construction; caller pins it."""
    run=Path(run).resolve();source=json.loads(file_bytes(run/'source.json'))
    return dict(schema=SCHEMA,profile=PROFILE,stage='t05',job_nonce=nonce,
        run=str(run),source_sha256=source['source_ref']['sha256'],
        producer_projection_sha256=producer_projection(),
        input_files=input_files(run)if inputs is None else inputs,memo_limit_bytes=512*1024**2)


def check_binding(run,expected):
    from importlib.metadata import version
    import shapely
    from src.gerber_u05.guard import ROOT
    runtime=json.loads(file_bytes(ROOT/'contracts/gerber_u05/runtime.json'))
    require({name:version(name)for name in runtime['packages']}==runtime['packages']and shapely.geos_version_string==runtime['geos'],'OUTER_PINNED_RUNTIME_CHANGED')
    require(expected['schema']==SCHEMA and expected['profile']==PROFILE and expected['stage']=='t05','OUTER_PROFILE')
    require(Path(run).resolve()==Path(expected['run'])and len(expected['job_nonce'])>=32,'OUTER_JOB_BINDING')
    require(expected['memo_limit_bytes']==512*1024**2,'OUTER_BUDGET_BINDING')
    require((Path(run)/'LEGACY_REFERENCE_JOB.json').is_file(),'OUTER_CONNECTED_COMPLETION_UNQUALIFIED')
    require(producer_projection()==expected['producer_projection_sha256'],'OUTER_PRODUCER_CHANGED')
    require(input_files(run)==expected['input_files'],'OUTER_FROZEN_INPUT_CHANGED')
    for name,h in expected.get('issuer_capsule_files',{}).items():
        require(hash_bytes(file_bytes(name))==h,'OUTER_ISSUER_CAPSULE_CHANGED')
    for name,h in expected.get('extra_reference_inputs',{}).items():
        require(hash_bytes(file_bytes(name))==h,'OUTER_REFERENCE_INPUT_CHANGED')
    source=json.loads(file_bytes(Path(run)/'source.json'))
    require(source['source_ref']['sha256']==expected['source_sha256'],'OUTER_SOURCE_CHANGED')


def verify_checkpoint_custody(run,expected):
    """The existing saved-T04/T02 route's custody, not fresh assembly adoption.

Historical assembly/source receipts remain immutable named inputs. Their code
version is not silently relabelled as a current live assembly worker. This
preserves the diagnostic checkpoint route's original checks and limitations.
The coordinator independently validates the completed checkpoint before copying
its exact stage bytes and receipts; every expected producer is explicit.
"""
    from src.gerber_u05.guard import producer_files
    from src import hole_acceptance
    check_binding(run,expected);run=Path(run);custody=expected['checkpoint_custody']
    require(custody['schema']=='verified-saved-t04-t02-custody/1','OUTER_CHECKPOINT_CUSTODY_SCHEMA')
    producer=json.loads(file_bytes(run/'PRODUCER_BINDING.json'))
    require(producer['files']=={str(p):hash_bytes(file_bytes(p))for p in producer_files()},'OUTER_CURRENT_PRODUCER_BINDING')
    require(producer['source_binding_sha256']==hash_bytes(file_bytes(run/'source.json')),'OUTER_SOURCE_BINDING')
    for name,h in producer.get('job_inputs',{}).items():
        require(hash_bytes(file_bytes(name))==h,'OUTER_JOB_OPTION_CHANGED')
    for stage in('t01','t03','t04','t02'):
        proofs=[json.loads(file_bytes(run/'audits'/stage/(m+'.json')))for m in('construct','1','2')]
        proof=proofs[0]
        require(proofs[0]==proofs[1]==proofs[2]and proof['status']=='PASS'and proof['stage']==stage,'OUTER_PREDECESSOR_PAIRED_PROOFS')
        require(proof['source_sha256']==expected['source_sha256']and proof['producer_binding_sha256']==custody['stage_producers'][stage],'OUTER_PREDECESSOR_PRODUCER_OR_SOURCE')
        require(proof['candidate_sha256']==custody['stage_sha256'][stage]==hash_bytes(file_bytes(run/(stage+'.json'))),'OUTER_PREDECESSOR_STAGE_CHANGED')
    store=ReadOnlyStore(run/'runtime');source=json.loads(file_bytes(run/'source.json'))
    require(store.get(source['source_ref'],kind='gerber-source')==file_bytes(run/'source_snapshot/top.art.gbr'),'OUTER_RAW_SOURCE_CHANGED')
    if(run/'SOURCE_ASSEMBLY_BINDING.json').exists():
        assembly=json.loads(file_bytes(run/'SOURCE_ASSEMBLY_BINDING.json'))
        require(assembly['assembled_source_sha256']==expected['source_sha256'],'OUTER_ASSEMBLY_WORKING_SOURCE')
        for name,h in assembly['files'].items():
            require(expected['extra_reference_inputs'].get(name)==h and hash_bytes(file_bytes(name))==h,'OUTER_HISTORICAL_ASSEMBLY_CUSTODY_CHANGED')
    hole_acceptance.bind(run)


def execute_once(run,capture,expected=None):
    """Trusted issuer entry: full original worker plus its closing source guards."""
    from src.gerber_u05.guard import verify_sources
    from src.gerber_u05.worker import compute
    run=Path(run)
    require(not(run/'t05.json').exists(),'OUTER_FRESH_CONSTRUCTION_REQUIRED')
    require(os.environ.get('U05_WORKER_MODE')=='construct','OUTER_CONSTRUCT_MODE_REQUIRED')
    guard=(lambda:verify_checkpoint_custody(run,expected))if expected is not None and 'checkpoint_custody'in expected else(lambda:verify_sources(run))
    guard()
    with capture.observe():result=compute(run,'t05')
    guard()
    capture.closed_sources_verified=True
    (run/'t05.json').write_bytes(canonical(result))
    return result


def _actual_group(group):
    authority,scene,policy,plan,candidate,binding=group
    require(type(authority)is StageCertificateConsumer,'OUTER_LIVE_AUTHORITY_REQUIRED')
    seal=authority._seal;ledger=authority.ledger;store=authority.store
    require(seal is not None and authority.counts['verifications']>=1,'OUTER_COMPLETED_INNER_REQUIRED')
    require(compare_digest(seal['authentication'],mac(authority._key,canonical(seal['body']),'sha256').hex()),'OUTER_INNER_AUTHENTICATION')
    require(seal['body']['input_sha256']==authority._input_hash(scene,policy,plan,candidate,binding),'OUTER_INNER_INPUT_CHANGED')
    require(seal['body']['ledger_head']==ledger.head and seal['body']['accepted_sha256']==body_hash(ledger.accepted),'OUTER_INNER_CHAIN_CHANGED')
    manifest=store.get_json(seal['body']['manifest_ref'],kind='t05-stage-manifest')
    require(len(manifest['certificates'])==len(ledger.accepted),'OUTER_INNER_COMMIT_COVERAGE')
    for entry,row in zip(ledger.accepted,manifest['certificates']):
        receipt=store.get_json(row['receipt_ref'],kind='t05-certificate')
        require(compare_digest(receipt['authentication'],ledger._sign(receipt['body'])),'OUTER_LOCAL_AUTHENTICATION')
        require(body_hash(receipt)==entry['receipt_sha256'],'OUTER_LOCAL_RECEIPT_CHANGED')
    # Public signature attests these exact bytes AFTER their live HMAC was
    # checked. It does not export inner keys or treat unsigned JSON as authority.
    return dict(scene=scene,policy=policy,plan=plan,candidate=candidate,
        execution_binding=binding,seal=seal,accepted=ledger.accepted,
        ledger_binding=ledger.binding,ledger_head=ledger.head,
        area_epsilon_mm2=ledger.area_epsilon_mm2)


def _unchanged_final_scene(store,result,candidate):
    require('intra'not in result,'OUTER_POST_JUNCTION_COMPLETION_UNQUALIFIED')
    require(result['candidate']==candidate,'OUTER_FINAL_CANDIDATE_CHANGED')
    original=store.get_json(candidate['output_scene_ref'],kind='scene')
    final=store.get_json(result['output_scene_ref'],kind='scene')
    # A final pin-state annotation is allowed; no leaf/copper change is allowed.
    a=dict(original);b=dict(final)
    a['lineage']=[{k:v for k,v in row.items()if k!='pin_separation_state'}for row in a['lineage']]
    b['lineage']=[{k:v for k,v in row.items()if k!='pin_separation_state'}for row in b['lineage']]
    require(a==b,'OUTER_FINAL_COPPER_OR_SCOPE_CHANGED')


def publish(run,capture,result,signer,expected):
    """Fresh issuer only. Not a facility for blessing retained PASS files."""
    began=perf_counter();run=Path(run)
    check_binding(run,expected)
    require(capture.worker is result and len(capture.groups)==1,'OUTER_REAL_COMPLETE_WORKER_REQUIRED')
    require(capture.closed_sources_verified and capture.worker_sha256==body_hash(result),'OUTER_WORKER_CLOSING_GUARDS_OR_RESULT_CHANGED')
    require(capture.run==run.resolve(),'OUTER_CAPTURE_JOB_CHANGED')
    require(file_bytes(run/'t05.json')==canonical(result),'OUTER_ACTUAL_STAGE_FILE_CHANGED')
    group=_actual_group(capture.groups[0]);store=capture.groups[0][0].store
    _unchanged_final_scene(store,result,group['candidate'])
    require(result['verification']==group['seal']['body']['result'],'OUTER_FINAL_VERDICT_CHANGED')
    # Bind all output refs, including actual post-worker pin/source state.
    for reference in artifact_refs([result,group]):store.get(reference)
    group_ref=store.put_json('t05-outer-group',group)
    result_ref=store.put_json('t05-outer-result',result)
    database=file_bytes(capture.path)
    dependencies_ref=store.put('t05-outer-reads',database)
    body=dict(schema=SCHEMA,expected=expected,backend=backend_identity(),
        group_ref=group_ref,result_ref=result_ref,dependencies_ref=dependencies_ref,
        capture=dict(read_requests=capture.requests,unique_reads=capture.count()),
        inner_authority='LIVE_HMAC_AUTHENTICATED_BEFORE_PUBLIC_SIGNATURE',
        completion='REAL_WORKER_RETURNED_THROUGH_FINAL_GUARDS')
    package=dict(body=body,signature=signer.sign(canonical(body)))
    return package,dict(publication_seconds=perf_counter()-began,
        read_requests=capture.requests,unique_reads=capture.count(),journal_bytes=len(database))


def _local_chain(store,group,counts):
    seal=group['seal']['body'];manifest=store.get_json(seal['manifest_ref'],kind='t05-stage-manifest')
    require(manifest['schema']==STAGE_SCHEMA,'OUTER_MANIFEST_SCHEMA')
    require(seal['input_sha256']==StageCertificateConsumer._input_hash(group['scene'],group['policy'],group['plan'],group['candidate'],group['execution_binding']),'OUTER_GROUP_INPUT_CHANGED')
    accepted=group['accepted'];require(body_hash(accepted)==seal['accepted_sha256'],'OUTER_ACCEPTED_CHANGED')
    require(group['ledger_binding']==seal['ledger_binding'],'OUTER_LEDGER_BINDING')
    head=body_hash([LOCAL_SCHEMA,group['ledger_binding']]);seen=set()
    require(len(accepted)==len(manifest['certificates']),'OUTER_CHAIN_COVERAGE')
    for index,(entry,row)in enumerate(zip(accepted,manifest['certificates'])):
        receipt=store.get_json(row['receipt_ref'],kind='t05-certificate');body=receipt['body'];sid=row['source_id']
        require(sid not in seen,'OUTER_DUPLICATE_ACCEPTANCE')
        require(entry==dict(source_id=sid,patch_ref=row['patch_ref'],receipt_sha256=body_hash(receipt)),'OUTER_RECEIPT_CHANGED')
        require(body['schema']==LOCAL_SCHEMA and body['binding']==group['ledger_binding'],'OUTER_LOCAL_BINDING')
        require(body['prefix_head']==head and body['prefix_count']==index and body['source_id']==sid,'OUTER_STALE_OR_REORDERED_PREFIX')
        require(body['patch_ref']==row['patch_ref'],'OUTER_PATCH_CHANGED')
        foreign=[item[0]for item in body['foreign']]
        require(len(foreign)==len(set(foreign)),'OUTER_DUPLICATE_FOREIGN')
        require(seen<=set(foreign)|set(body['owner_exemptions']),'OUTER_PREFIX_OMITTED')
        require(body_hash(body['physical_proof'])==body['physical_proof_sha256'] and body['physical_proof']['passed']is True,'OUTER_PHYSICAL_PROOF')
        wp=body['window_policy'];epsilon=group['area_epsilon_mm2']
        require(epsilon==1e-12 and wp['schema']==WINDOW_SCHEMA and wp['patch_sha256']==row['patch_ref']['sha256']and wp['window_fingerprint']==body['window']and wp['area_epsilon_mm2']==epsilon
            and type(wp['outside_area_mm2'])is float and isfinite(wp['outside_area_mm2'])and 0<=wp['outside_area_mm2']<=epsilon
            and wp['predicate']=='GEOS_DIFFERENCE_AREA_LEQ_EXISTING_POLICY','OUTER_WINDOW_WITNESS')
        patch=from_wkb(store.get(row['patch_ref'],kind='geometry'));region=from_wkb(store.get(body['region_ref'],kind='geometry'))
        store.get(body['window_ref'],kind='geometry')
        require(patch.is_valid and not patch.is_empty and region.is_valid,'OUTER_LOCAL_GEOMETRY_INVALID')
        require(region.covers(patch)or patch.difference(region).is_empty,'OUTER_PATCH_OUTSIDE_CERTIFIED_REGION')
        head=body_hash([head,entry]);seen.add(sid);counts['local_containments']+=1
    require(head==group['ledger_head']==seal['ledger_head'],'OUTER_INCOMPLETE_CHAIN')
    candidate=group['candidate'];rows=group['plan']['details']['routes'];decisions=candidate['decisions']
    require([d['source_id']for d in decisions]==[r['source_id']for r in rows],'OUTER_DECISION_COVERAGE')
    require([dict(source_id=d['source_id'],patch_ref=d['patch_ref'])for d in decisions if d['status']=='GROWN']==[dict(source_id=e['source_id'],patch_ref=e['patch_ref'])for e in accepted],'OUTER_GROWTH_COVERAGE')
    for row,decision in zip(rows,decisions):
        require(all(decision[k]==v for k,v in row.items())and decision['status']in('KEEP','GROWN'),'OUTER_DECISION_MEMBERSHIP')
    output=store.get_json(candidate['output_scene_ref'],kind='scene')
    require(body_hash(output)==seal['composition']['scene_sha256']and candidate['after_ref']['sha256']==seal['composition']['copper_sha256'],'OUTER_COMPOSITION_CHANGED')
    for ref in manifest['dependencies']:store.get(ref);counts['inner_dependency_reads']+=1
    return seal['result']


def consume(run,package,public_anchor,expected):
    """Public-only independent process. Never opens a signing key or constructor."""
    began=perf_counter();counts=Counter();times={}
    body=package['body'];verify(public_anchor,canonical(body),package['signature'])
    require(body['schema']==SCHEMA and body['expected']==expected,'OUTER_EXPECTED_BINDING_CHANGED')
    require(body['backend']==backend_identity(),'OUTER_SIGNATURE_BACKEND_BINDING')
    times['authentication']=perf_counter()-began;point=perf_counter()
    check_binding(run,expected);store=ReadOnlyStore(Path(run)/'runtime')
    raw=store.get(body['dependencies_ref'],kind='t05-outer-reads')
    require(len(raw)*4+1024**2<=READER_METADATA_LIMIT,'OUTER_READER_METADATA_BUDGET')
    # Deserialize already authenticated bytes, avoiding hash/open SQLite TOCTOU.
    database=sqlite3.connect(':memory:');database.deserialize(raw);database.execute('PRAGMA query_only=ON')
    try:
        require(database.execute('PRAGMA integrity_check').fetchone()==('ok',),'OUTER_READ_MANIFEST_CORRUPTED')
        for namespace,aid,h in database.execute('SELECT namespace,artifact_id,sha256 FROM reads ORDER BY namespace,artifact_id'):
            require(namespace=='runtime','OUTER_READ_NAMESPACE')
            store.get(dict(artifact_id=aid,sha256=h));counts['worker_dependency_reads']+=1
    finally:database.close()
    require(counts['worker_dependency_reads']==body['capture']['unique_reads'],'OUTER_READ_SET_INCOMPLETE')
    result=store.get_json(body['result_ref'],kind='t05-outer-result');group=store.get_json(body['group_ref'],kind='t05-outer-group')
    require(file_bytes(Path(run)/'t05.json')==canonical(result),'OUTER_ACTUAL_STAGE_FILE_CHANGED')
    for reference in artifact_refs([result,group]):store.get(reference);counts['output_reads']+=1
    times['input_output_dependencies']=perf_counter()-point;point=perf_counter()
    inner=_local_chain(store,group,counts);_unchanged_final_scene(store,result,group['candidate'])
    require(result['verification']==inner,'OUTER_FINAL_VERDICT_CHANGED')
    times['local_certificate_consumption']=perf_counter()-point
    return dict(schema=SCHEMA,status='PASS',evidence_kind='SIGNED_COMPLETED_CONSTRUCTION_PLUS_ACTUAL_ARTIFACTS_AND_LOCAL_PROOFS',
        stage='t05',job_nonce=expected['job_nonce'],stage_sha256=body_hash(result),
        certificate_sha256=body_hash(package),public_anchor_sha256=hash_bytes(public_anchor),
        counts=dict(counts),seconds=times,total_seconds=perf_counter()-began,
        reader_metadata_accounted_bytes=len(raw)*4+1024**2,
        reconstruction_performed=False,physical_checks_repeated=0)
