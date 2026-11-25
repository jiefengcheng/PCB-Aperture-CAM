"""One explicit-source cleanup execution path for CLI and the native viewer.

Saved results are immutable and separate from any existing live connection.
All required families share one fixed operation; unqualified boundaries stay open.
"""
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import stat
import time
import traceback
import uuid

from shapely import from_wkb, to_wkb
from shapely.geometry import Polygon

from src.bulk_edge_restore import topology
from src.edge_restoration_settings import capture
from src.large_copper_discovery import (discover, PROFILE, MIN_SUPPORT_MM, MAX_SPAN_MM,
                                        REQUIRED_FAMILIES, DISCOVERY_GAPS)
from src.shared_copper_context import for_board
from src.stage_abi.store import process_identity, owner_state
from src.viewer_abi.publisher import encode, digest, atomic_write

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'large-copper-execution/1'


def read_file(path, maximum=64*1024**2):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('REGULAR_FILE_REQUIRED:'+str(path))
        raw=stream.read(maximum+1)
    if len(raw)>maximum:raise ValueError('LARGE_COPPER_SOURCE_RESOURCE_LIMIT')
    return raw


def workspace_path(path):
    from src.cleanup_runtime import workspace_root
    work=workspace_root()
    target=Path(path).absolute().resolve()
    if not target.is_relative_to(work) or target==work:
        raise ValueError('LACIE_OUTPUT_REQUIRED')
    return target


def implementation():
    import shapely, gerbonara
    paths=sorted((ROOT/'src').rglob('*.py'))
    paths += [ROOT/'tools/run_large_copper.py',ROOT/'contracts/edge_restoration/settings.json']
    return dict(files={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in paths},
                shapely=shapely.__version__,geos=shapely.geos_version_string,
                gerbonara=gerbonara.__version__)


def bound_file(path):
    return dict(path=str(Path(path).resolve()),sha256=digest(read_file(path,1024**3)))


def authenticate(job):
    """Byte custody only. Never treatment, discovery, or geometry acceptance."""
    job=workspace_path(job)
    result=json.loads(read_file(job/'RESULT.json'))
    if result['schema']!=SCHEMA or result['status'] not in ('COMPLETED_FOR_PROFILE','COMPLETED_WITH_UNRESOLVED'):
        raise ValueError('VALIDATED_CLEANUP_RESULT_REQUIRED')
    for name in ('stage','source_binding','source'):
        ref=result[name];path=Path(ref['path'])
        if not path.resolve().is_relative_to(job) or digest(read_file(path,1024**3))!=ref['sha256']:
            raise ValueError('CLEANUP_SAVED_ARTIFACT_CHANGED:'+name)
    stage=json.loads(gzip.decompress(read_file(result['stage']['path'],1024**3)))
    if stage['execution_binding']!=result['execution_binding'] or stage['operation']!='TRIM_ONLY':
        raise ValueError('CLEANUP_SAVED_BINDING_CHANGED')
    proof=stage['trim_only_phase']
    if (proof.get('passed') is not True or proof.get('positive_copper_mm2')!=0 or
            proof.get('all_rectangles_preserved') is not True or
            proof.get('topology_before')!=proof.get('topology_after') or
            stage['batch_proof'].get('passed') is not True or
            any(r.get('passed') is not True for r in stage['large_copper_cleanup']['records'])):
        raise ValueError('CLEANUP_SAVED_VALIDATION_REQUIRED')
    from src.gerber_u05.pipeline import Store, operands
    if not (job/'runtime/artifacts').is_dir():raise ValueError('CLEANUP_SAVED_RUNTIME_MISSING')
    store=Store(job/'runtime')
    binding=json.loads(read_file(result['source_binding']['path']))
    if binding['scene_ref']!=stage['input_binding']['scene_ref']:
        raise ValueError('CLEANUP_SAVED_SCENE_CHANGED')
    scene=store.get_json(binding['scene_ref'],kind='scene')
    rows,original,_=operands(store,scene)
    store.get(binding['source_ref'],kind='gerber-source')
    if list(rows)!=stage['ordered_source_ids'] or digest(read_file(result['source']['path']))!=stage['input_binding']['source_sha256']:
        raise ValueError('CLEANUP_SAVED_SOURCE_COVERAGE_CHANGED')
    mapping=stage['hybrid_components']['changed_bulk_copper']
    if not set(mapping)<=set(rows):raise ValueError('CLEANUP_SAVED_FOREIGN_SOURCE')
    return result,stage,rows,original


def display_record(job):
    pointer=job/'DISPLAY_CURRENT.json'
    if not pointer.exists():return json.loads(read_file(job/'DISPLAY.json')) if (job/'DISPLAY.json').exists() else None
    ref=json.loads(read_file(pointer));path=workspace_path(ref['path'])
    if not path.is_relative_to(job) or digest(read_file(path))!=ref['sha256']:
        raise ValueError('CLEANUP_DISPLAY_RECEIPT_CHANGED')
    return json.loads(read_file(path))


def status(job):
    job=workspace_path(job)
    progress=json.loads(read_file(job/'PROGRESS.json'))
    if progress['status']=='RUNNING' and owner_state(progress['owner'])=='DEAD':
        return dict(progress,status='INTERRUPTED_RETAINED_NO_AUTOMATIC_RETRY')
    if not (job/'RESULT.json').exists():return progress
    result,_,_,_=authenticate(job)
    display=dict(status='NOT_REQUESTED')
    if (job/'DISPLAY_FAILED.json').exists():display=dict(status='FAILED_RETAINED',evidence=bound_file(job/'DISPLAY_FAILED.json'))
    saved_display=display_record(job)
    if saved_display:
        display=saved_display
        if display['result']!=bound_file(job/'RESULT.json'):raise ValueError('CLEANUP_DISPLAY_RESULT_CHANGED')
        from src.viewer_abi.publisher import read_current
        session=workspace_path(display['workspace'])
        if not session.is_relative_to(job):raise ValueError('CLEANUP_DISPLAY_PATH_CHANGED')
        manifest,snapshot=read_current(session)
        if manifest['sha256']!=display['snapshot_sha256'] or snapshot['revision']!=display['revision']:
            raise ValueError('CLEANUP_DISPLAY_REVISION_CHANGED')
        ack=session/'outbox/display.json'
        display['status']='PENDING_NATIVE_ACK'
        if ack.exists():
            value=json.loads(read_file(ack))
            if (value.get('status')=='DISPLAY_DOM_UPDATED' and value.get('job')==snapshot['job'] and value.get('revision')==display['revision']
                    and value.get('payloadSHA256')==display['snapshot_sha256'] and value.get('presentation')=='BULK_COPPER_CLEANUP'):
                display.update(status='NATIVE_DISPLAY_ACKNOWLEDGED',ack=bound_file(ack))
    return dict(status=result['status'],job=str(job),counts=result['counts'],display=display,
                custody='AUTHENTICATED_SAVED_BYTES; GEOMETRY_NOT_RERUN')


def execution_binding(raw,policy,code):
    """One canonical producer identity for execution and orchestration."""
    return dict(schema=SCHEMA,source_sha256=digest(raw),implementation=code,
        policy=policy.resolved(),discovery=dict(profile=PROFILE,minimum_support_mm=MIN_SUPPORT_MM,
            maximum_span_mm=MAX_SPAN_MM,circular_fit_bound_mm=.004),
        treatment=dict(selection='ALL_REQUIRED_FAMILIES; NO_EXECUTION_FAMILY_SWITCHES',
            required_families=list(REQUIRED_FAMILIES),
            unresolved_discovery_families=list(DISCOVERY_GAPS),
            family_filters='SAVED_VIEW_ONLY'),
        original_paths_and_contacts='CAUSING_PATH_PRESERVED_OR_BOUNDED_AREA_NOISE_FREE_END; SHALLOW_PATH_STRICT; PHYSICAL_AND_TERMINAL_CONTACTS_PRESERVED',
        overlapping_plotting_fragments='EXISTING_WHOLE_PHYSICAL_NOISE_RULE; NO_INDEPENDENT_FRAGMENT_DENOMINATORS',rectangles='IGNORED',
        flash_policy='UNRELATED_AND_DECLARED_PROTECTED; EXACT_CAUSING_PAD_AND_REDUNDANT_ENDPOINT_PROOFS_REQUIRED')


def execution_identity(binding):
    # Native preparation annotates the saved execution after its source/code/
    # policy key was allocated. These are results, not a second job identity.
    return digest(encode({k:v for k,v in binding.items()if k not in('shared_context','original_revision')}))


def run(source, *, output=None, progress_callback=lambda **event: None):
    from src.gerber_u05.workspace import configure
    configure()
    source=Path(source)
    if not source.is_absolute():raise ValueError('EXPLICIT_ABSOLUTE_SOURCE_REQUIRED')
    try:raw=read_file(source)
    except (OSError,ValueError) as exc:
        from src.cleanup_runtime import workspace_root
        rejected=workspace_path(output or workspace_root()/'large_copper_jobs'/('intake-'+uuid.uuid4().hex))
        rejected.mkdir(parents=True,exist_ok=False)
        failure=dict(status='FAILED_RETAINED',job=str(rejected),source=str(source),error=repr(exc),
            errno=getattr(exc,'errno',None),remaining='NOT_RUN',phase='intake')
        atomic_write(rejected/'FAILED.json',encode(failure));atomic_write(rejected/'PROGRESS.json',encode(failure))
        raise ValueError('SOURCE_INTAKE_FAILED; EVIDENCE='+str(rejected)) from exc
    policy=capture()
    if policy.maximum_depth_mm>.100 or policy.maximum_noise_area_fraction!=.10:
        raise ValueError('CLEANUP_POLICY_OUTSIDE_AUTHORIZED_LIMITS')
    code=implementation()
    execution=execution_binding(raw,policy,code)
    key=execution_identity(execution)
    from src.cleanup_runtime import workspace_root
    work=workspace_path(workspace_root()/'large_copper_jobs')
    work.mkdir(exist_ok=True)
    locks=work/'locks';locks.mkdir(exist_ok=True)
    # Serialize all policies/revisions for this explicit source, not just one
    # output pathname. flock releases on a crash; the retained job record does not.
    with (locks/(digest(raw)+'.lock')).open('a+b') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('DUPLICATE_SOURCE_JOB_ACTIVE')
        index=work/(key+'.job.json')
        if index.exists():
            prior=json.loads(read_file(index))
            previous=workspace_path(prior['job'])
            if prior['execution_sha256']!=key:
                raise ValueError('CLEANUP_JOB_INDEX_CHANGED')
            return dict(status='DUPLICATE_JOB_RETAINED',job=str(previous),retained=status(previous))
        job=workspace_path(output or work/(time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex))
        job.mkdir(parents=True,exist_ok=False)
        atomic_write(index,encode(dict(job=str(job),execution_sha256=key)))
        started=time.perf_counter();timings={};identity=process_identity()
        def progress(**event):
            atomic_write(job/'PROGRESS.json',encode(dict(schema=SCHEMA,job=str(job),status='RUNNING',
                owner=identity,execution_sha256=key,elapsed_seconds=time.perf_counter()-started,**event)))
            progress_callback(**event)
        try:
            progress(phase='intake')
            from tools.preflight import verify_manifest
            assets=verify_manifest()
            (job/'source.gbr').write_bytes(raw)
            from src.gerber_u05.pipeline import Store, build_source, operands
            store=Store(job/'runtime')
            t=time.perf_counter()
            from src.gerber_u05.gerber_source_profile import parse_source
            parsed,_,_=parse_source(raw)
            function=parsed.file_attrs.get('.FileFunction',())
            polarity=parsed.file_attrs.get('.FilePolarity',())
            if function and function[0]!='Copper' or polarity and polarity!=('Positive',):
                raise ValueError('SELECTED_POSITIVE_COPPER_SURFACE_REQUIRED')
            del parsed
            binding=build_source(store,raw)
            (job/'source.json').write_bytes(encode(binding))
            scene=store.get_json(binding['scene_ref'],kind='scene')
            rows,original,_=operands(store,scene)
            if not original:raise ValueError('NO_SUPPORTED_COPPER_SOURCE')
            timings['intake_seconds']=time.perf_counter()-t
            progress(phase='preparation',source_occurrences=len(rows))
            t=time.perf_counter()
            with for_board(original) as copper, copper.activate():
                timings['preparation_seconds']=time.perf_counter()-t
                execution['original_revision']=copper.source.key
                execution['shared_context']=copper.key
                progress(phase='discovery')
                t=time.perf_counter()
                features,findings,coverage=discover(rows,original,copper.source,progress)
                (job/'DISCOVERY.json').write_bytes(encode(dict(findings=findings,coverage=coverage,
                    features=[dict(f,domain=to_wkb(f['domain']).hex(),smooth_edge=to_wkb(f['smooth_edge']).hex(),
                        removal_mask=to_wkb(f['removal_mask']).hex()) for f in features])))
                timings['discovery_seconds']=time.perf_counter()-t
                progress(phase='construction',candidates=len(features))
                from src.gerber_u05.source_edge_cleanup import CleanupBatch
                # Pads and redundant plotting flashes use the existing exact
                # source-bound exception proofs. Declared/protected terminals
                # and all unrelated rectangles remain protected.
                protected=[s for s,r in rows.items() if any(r['metadata'].get(k) for k in
                    ('rectangle_terminal','declared_terminal','declared_pin','protected_pin','terminal_intent_declared'))]
                batch=CleanupBatch(rows,original,copper.source,features,policy=policy,
                    protected_source_ids=protected,allow_causing_pads=True,allow_redundant_flashes=True,
                    preserve_causing_paths=True,allow_causing_free_end_trim=True,preserve_reference_flanks=True)
                t=time.perf_counter()
                for i,f in enumerate(features):
                    finding=findings[f['finding_index']]
                    try:
                        record=batch.propose(i)
                        finding.update(status='corrected',reason='STAGED_REQUIRES_ASSEMBLED_VALIDATION',proof=record)
                    except ValueError as exc:
                        finding['reason']=str(exc)
                    progress(phase='construction',completed=i+1,candidates=len(features))
                timings['construction_seconds']=time.perf_counter()-t
                (job/'PROPOSALS.json').write_bytes(encode(dict(findings=findings,records=batch.records)))
                progress(phase='validation')
                t=time.perf_counter();after,proof=batch.finish();copper.validate();store.verify_reads()
                if read_file(source)!=raw or implementation()!=code or capture().resolved()!=policy.resolved():
                    raise ValueError('SOURCE_IMPLEMENTATION_OR_POLICY_CHANGED_DURING_RUN')
                image=copper.source.image();result_image=after.image()
                if result_image.difference(image).area>1e-12 or topology(image)!=topology(result_image):
                    raise ValueError('TRIM_ONLY_ASSEMBLED_VALIDATION_FAILED')
                for f in findings:
                    if f['status']=='corrected':f['reason']='VALIDATED_SAVED_CORRECTION'
                changes={s:dict(wkb_hex=to_wkb(g).hex()) for s,g in after.values.items() if to_wkb(g)!=to_wkb(original[s])}
                stage=dict(schema='source-bulk-trim-preview/1',operation='TRIM_ONLY',
                    input_binding=dict(context='original',accepted_t03=False,source_sha256=digest(raw),
                        scene_ref=binding['scene_ref'],original_scene_ref=binding['scene_ref']),
                    execution_binding=execution,ordered_source_ids=list(rows),
                    hybrid_components=dict(continuous_source_bodies={},changed_bulk_copper=changes),
                    large_copper_cleanup=dict(profile=PROFILE,findings=findings,coverage=coverage,records=batch.records),
                    trim_only_phase=dict(passed=True,positive_copper_mm2=0.,
                        source_bytes_changed=False,all_rectangles_preserved=True,rectangular_bumps_considered=False,
                        topology_before=list(topology(image)),topology_after=list(topology(result_image)),
                        total_removed_mm2=proof['actual_removed_mm2']),batch_proof=proof)
                timings['validation_seconds']=time.perf_counter()-t
                diagnostics=copper.diagnostics()
            progress(phase='saving')
            from src.gerber_u05.group_board_job import write_stage
            artifact=write_stage(job/'construction.json.gz',stage)
            counts={kind:sum(f['status']==kind for f in findings) for kind in ('corrected','unresolved','ignored')}
            result=dict(schema=SCHEMA,status='COMPLETED_WITH_UNRESOLVED' if DISCOVERY_GAPS or counts['unresolved'] or
                any(r['unsupported_edge_count'] for r in coverage) else 'COMPLETED_FOR_PROFILE',
                stage=artifact,source=bound_file(job/'source.gbr'),source_binding=bound_file(job/'source.json'),
                execution_binding=execution,asset_manifest=assets,counts=counts,timings=timings,
                diagnostics=diagnostics,peak_process_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                discovery_completeness='NOT_ESTABLISHED_FOR_GENERAL_CURVES_OR_OTHER_DEFECT_FAMILIES',
                treatment_complete=not DISCOVERY_GAPS and not counts['unresolved'] and
                    not any(r['unsupported_edge_count'] for r in coverage),
                required_discovery_gaps=list(DISCOVERY_GAPS),
                growth=False,exports=False,owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',
                electrical_manufacturing='NOT_ESTABLISHED')
            atomic_write(job/'RESULT.json',encode(result))
            authenticate(job)
            atomic_write(job/'PROGRESS.json',encode(dict(status=result['status'],job=str(job),
                elapsed_seconds=time.perf_counter()-started,timings=timings)))
            return dict(status=result['status'],job=str(job),counts=counts,result=bound_file(job/'RESULT.json'))
        except BaseException as exc:
            failure=dict(status='FAILED_RETAINED',job=str(job),error=repr(exc),
                traceback=traceback.format_exc(),remaining='NOT_RUN',timings=timings)
            tb=exc.__traceback__
            while tb is not None:
                if tb.tb_frame.f_code.co_name=='discover':
                    site=tb.tb_frame.f_locals
                    failure['discovery_site']={k:site[k] for k in
                        ('owner','pi','ri','j','i','distance','n','support_count','transient_weight') if k in site}
                    # Save partial discovery as failed evidence only. It is not
                    # a shortened successful inventory or a publication input.
                    atomic_write(job/'FAILED_DISCOVERY.json',encode(dict(
                        status='INCOMPLETE_FAILED_DISCOVERY',findings=site.get('findings',[]),
                        coverage=site.get('coverage',[]),site=failure['discovery_site'])))
                tb=tb.tb_next
            atomic_write(job/'FAILED.json',encode(failure))
            atomic_write(job/'PROGRESS.json',encode(failure))
            raise


def publish_saved(job, *, new_revision=False):
    """Serialize display publication and retain failed derivatives."""
    from src.gerber_u05.workspace import configure
    configure()
    job=workspace_path(job)
    with (job/'.display.lock').open('a+b') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('CLEANUP_DISPLAY_PUBLICATION_ACTIVE')
        if (job/'DISPLAY_FAILED.json').exists():
            failed=json.loads(read_file(job/'DISPLAY_FAILED.json'))
            previous=failed.get('display_implementation_sha256')
            if not new_revision or previous is None or previous==digest(encode(implementation())):
                raise ValueError('CLEANUP_DISPLAY_FAILURE_RETAINED; CORRECTED_IMPLEMENTATION_REQUIRED')
        try:return _publish_saved(job,new_revision=new_revision)
        except BaseException as exc:
            failure=job/('DISPLAY_FAILED-'+uuid.uuid4().hex+'.json' if (job/'DISPLAY_FAILED.json').exists() else 'DISPLAY_FAILED.json')
            atomic_write(failure,encode(dict(status='FAILED_RETAINED',error=repr(exc),
                traceback=traceback.format_exc(),native_display='NOT_RUN',
                display_implementation_sha256=digest(encode(implementation())))))
            raise


def _publish_saved(job, *, new_revision=False):
    """Prepare a new, isolated saved-result viewer session; no live-head edits."""
    job=workspace_path(job)
    started=time.perf_counter()
    display_code=implementation()
    result,stage,rows,original=authenticate(job)
    if display_record(job) and not new_revision:return status(job)['display']
    from shapely.ops import unary_union
    from src.viewer_abi.live import display
    from src.viewer_abi.copper_cleanup import cleanup_cases
    from src.viewer_abi.publisher import path_data, bounds
    before=unary_union(list(original.values()))
    changes=stage['hybrid_components']['changed_bulk_copper']
    after=unary_union([from_wkb(bytes.fromhex(changes[s]['wkb_hex'])) if s in changes else g for s,g in original.items()])
    cleanup=cleanup_cases(stage,rows,original,before.difference(after),Polygon(),display,source_image=before)
    gaps=result.get('required_discovery_gaps')
    if gaps is None:
        cleanup['note']+=' Historical partial straight-flank implementation; required circular discovery and pad/flash exceptions were not established.'
    elif gaps:
        cleanup['note']+=' INCOMPLETE TREATMENT: required circular-reference discovery remains unresolved. This result does not establish parity with the reviewed bumps.'
    # A completed no-change profile is still inspectable as grey original broad
    # objects; no unrelated trace overlay is substituted for an empty case list.
    if not cleanup['objects']:
        for i,body in enumerate([before] if before.geom_type=='Polygon' else before.geoms):
            if body.area<1 or body.buffer(-.125,quad_segs=128).is_empty:continue
            oid='bulk:'+str(i);view,_=display(body)
            cleanup['objects'].append(dict(id=oid,bounds=bounds(body),areaMM2=body.area))
            cleanup['parts'].append(dict(id='growth:'+oid,sourceID=stage['input_binding']['source_sha256']+':display-growth:'+oid,layer='cleanup',kind='source',
                path=path_data(view),bounds=bounds(view),attributes=dict(copper_object=[oid])))
    revision=uuid.uuid4().hex
    workspace=job/('viewer-'+revision if (job/'viewer').exists() else 'viewer')
    if not cleanup['parts']:raise ValueError('NO_LARGE_COPPER_OBJECTS_TO_DISPLAY')
    workspace.mkdir(exist_ok=False);(workspace/'snapshots').mkdir();(workspace/'presentations').mkdir()
    snapshot=dict(schema=1,job=str(job),revision=revision,parentRevision=None,slice='Large copper trimming · saved result',
        status='Preview',bounds=bounds(before),affected=bounds(before),objects=cleanup['parts'],
        sources=[dict(name='source.gbr',sha256=stage['input_binding']['source_sha256'],layer='cleanup')],
        evidence=[str(job/'RESULT.json')],
        limitations=['Required circular discovery NOT_ESTABLISHED; reviewed-bump parity NOT_ATTAINED.' if gaps is None or gaps else 'Saved source-supported trimming result.',
                     'Trimming only; no growth, exports, electrical or manufacturing acceptance.'])
    payload=encode(snapshot)
    if len(payload)>128*1024**2:raise ValueError('VIEWER_PAYLOAD_RESOURCE_LIMIT')
    sha=digest(payload);atomic_write(workspace/'snapshots'/(sha+'.json'),payload)
    presentation=dict(schema=1,job=snapshot['job'],revision=revision,sceneSHA256=sha,
        sourceSHA256=stage['input_binding']['source_sha256'],predecessorSHA256=stage['input_binding']['scene_ref']['sha256'],
        constructionSHA256=result['stage']['sha256'],beforeWkbSHA256=digest(before.wkb),afterWkbSHA256=digest(after.wkb),
        parts=cleanup['parts'],bounds=bounds(before),addedAreaMM2=0.,removedAreaMM2=before.difference(after).area,
        displayHausdorffMM=.0005,summary='Saved large copper trimming · grey copper',
        note='REPLAY of validated saved results; navigation never executes treatment.',cleanup=cleanup)
    import base64
    data=encode(presentation)
    if len(data)>64*1024**2:raise ValueError('BOARD_GROWTH_RESOURCE_LIMIT')
    atomic_write(workspace/'presentations'/(sha+'.json'),encode(dict(schema=1,sha256=digest(data),payloadBase64=base64.b64encode(data).decode())))
    # Authenticate saved dependencies again before the display commit point.
    authenticate(job)
    if implementation()!=display_code:raise ValueError('CLEANUP_DISPLAY_IMPLEMENTATION_CHANGED')
    atomic_write(workspace/'current.json',encode(dict(schema=1,payload=sha+'.json',sha256=sha,previousPayload=None,previousSHA256=None)))
    receipt=dict(status='PENDING_NATIVE_ACK',workspace=str(workspace),revision=revision,snapshot_sha256=sha,
        presentation_preparation_seconds=time.perf_counter()-started,result=bound_file(job/'RESULT.json'),
        display_implementation_sha256=digest(encode(display_code)))
    receipt_path=job/('DISPLAY-'+revision+'.json' if (job/'DISPLAY.json').exists() else 'DISPLAY.json')
    atomic_write(receipt_path,encode(receipt))
    atomic_write(job/'DISPLAY_CURRENT.json',encode(bound_file(receipt_path)))
    return receipt
