"""Coordinate separate cleanup/T04 workers through pinned phase seals.

This module does no geometry treatment. A failed/interrupted attempt is retained;
changing an output pathname never bypasses the source/code/policy execution key.
"""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid

from src.copper_phase_seal import publish,verify,reference,file_sha
from src.large_copper_runner import workspace_path,read_file
from src.viewer_abi.publisher import atomic_write,encode,digest
from src.stage_abi.store import process_identity,owner_state

ROOT=Path(__file__).resolve().parents[1]


def implementation():
    from src.gerber_u05.profile_intake import source_inventory
    paths=['tools/run_copper_pipeline.py','tools/run_t04_after_cleanup.py','tools/run_large_copper.py',
           'contracts/edge_restoration/settings.json','contracts/agent_abi/copper_pipeline_v1.json']
    paths.extend(str(p.relative_to(ROOT))for p in sorted((ROOT/'contracts/t04').glob('*.json')))
    return dict(source=source_inventory(),entrypoints_and_policies={p:file_sha(ROOT/p)for p in paths})


def _worker(command,job,label):
    with (job/(label+'.stdout.log')).open('xb')as out,(job/(label+'.stderr.log')).open('xb')as err:
        process=subprocess.run([sys.executable,'-B',*command],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
    if process.returncode:raise ValueError('COPPER_PIPELINE_WORKER_FAILED:'+label+':'+str(process.returncode))


def status(job):
    job=workspace_path(job)
    if not (job/'STATE.json').exists():
        return dict(status='INTERRUPTED_RETAINED_NO_AUTOMATIC_RETRY',job=str(job),reason='STATE_NOT_COMMITTED')
    value=json.loads(read_file(job/'STATE.json'))
    if value['status']=='RUNNING':
        return dict(value,status='INTERRUPTED_RETAINED_NO_AUTOMATIC_RETRY'if owner_state(value['owner'])=='DEAD'else'RUNNING')
    if value['status']!='COMPLETED':return value
    ref=value['result']
    if Path(ref['path']).resolve()!=job/'RESULT.json':raise ValueError('COPPER_PIPELINE_RESULT_PATH_CHANGED')
    raw=read_file(ref['path'])
    if digest(raw)!=ref['sha256']:raise ValueError('COPPER_PIPELINE_RESULT_CHANGED')
    result=json.loads(raw)
    phases={name:verify(**result['outputs'][name],phase=name)for name in('large_copper','t04')}
    if (phases['t04']['parent']!=result['outputs']['large_copper']or
            result['source_sha256']!=phases['large_copper']['source_sha256']or
            result.get('input_source_sha256',phases['large_copper']['source_sha256'])!=
                phases['large_copper']['summary'].get('input_assembly',{}).get('raw_source_sha256',phases['large_copper']['source_sha256'])or
            result['workspaces']!={name:phases[name]['job']for name in phases}or
            result['execution_sha256']!=value['execution_sha256']):
        raise ValueError('COPPER_PIPELINE_OUTPUT_BINDING_CHANGED')
    return dict(result,custody='AUTHENTICATED_SAVED_PHASES; NO_TREATMENT_EXECUTION')


def run(*,source=None,cleanup_job=None,output=None,scope=None,progress=lambda **event:None):
    from src.gerber_u05.workspace import configure
    work=configure()
    if (source is None)==(cleanup_job is None):raise ValueError('ONE_EXPLICIT_SOURCE_OR_SAVED_CLEANUP_REQUIRED')
    if source is not None:
        source=Path(source)
        if not source.is_absolute():raise ValueError('EXPLICIT_ABSOLUTE_SOURCE_REQUIRED')
        raw=read_file(source);source_sha=digest(raw);input_binding=dict(source_sha256=source_sha)
        from src.large_copper_runner import execution_binding,execution_identity,implementation as cleanup_code
        from src.edge_restoration_settings import capture
        producer_key=execution_identity(execution_binding(raw,capture(),cleanup_code()))
    else:
        cleanup_job=workspace_path(cleanup_job)
        from src.large_copper_runner import authenticate,execution_identity
        result,_,_,_=authenticate(cleanup_job)
        source_sha=result['execution_binding']['source_sha256'];input_binding=dict(cleanup=reference(cleanup_job/'RESULT.json'))
        producer_key=execution_identity(result['execution_binding'])
        raw=None
    code=implementation();scope_raw=None if scope is None else read_file(Path(scope))
    if scope_raw is not None:
        routes=json.loads(scope_raw)['requested_routes']
        if not isinstance(routes,list)or not routes or len(routes)!=len(set(routes))or not all(isinstance(s,str)for s in routes):
            raise ValueError('NONEMPTY_UNIQUE_T04_ROUTE_SCOPE_REQUIRED')
    # Fresh-source and retained-cleanup spelling cannot bypass the same T04
    # attempt. Both bind the producer's canonical execution identity.
    key=digest(encode(dict(producer_execution_sha256=producer_key,code=code,
                          scope=None if scope_raw is None else digest(scope_raw))))
    registry=workspace_path(work/'copper_pipeline_jobs');registry.mkdir(exist_ok=True)
    locks=registry/'locks';locks.mkdir(exist_ok=True)
    with (locks/(source_sha+'.lock')).open('a+b')as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('COPPER_PIPELINE_SOURCE_ACTIVE')
        index=registry/(key+'.job.json')
        if index.exists():
            prior=json.loads(read_file(index))
            if prior['execution_sha256']!=key:raise ValueError('COPPER_PIPELINE_INDEX_CHANGED')
            retained=status(prior['job'])
            if retained.get('execution_sha256',key)!=key:raise ValueError('COPPER_PIPELINE_INDEX_JOB_CHANGED')
            return dict(status='DUPLICATE_JOB_RETAINED',job=prior['job'],retained=retained)
        job=workspace_path(output or registry/(time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex))
        if cleanup_job is not None and (job.is_relative_to(cleanup_job)or cleanup_job.is_relative_to(job)):
            raise ValueError('COPPER_PIPELINE_PRODUCER_WORKSPACE_MUST_BE_SEPARATE')
        if job.is_relative_to(work/'shared_copper_context'):
            raise ValueError('COPPER_PIPELINE_PREPARATION_IS_NOT_A_PHASE_WORKSPACE')
        job.mkdir(parents=True,exist_ok=False)
        atomic_write(index,encode(dict(job=str(job),execution_sha256=key)))
        plan=dict(schema='pcb-copper-pipeline/1',execution_sha256=key,source_sha256=source_sha,
            input=input_binding,producer_execution_sha256=producer_key,implementation=code,
            scope='FULL_BOARD_DIAGNOSTIC'if scope_raw is None else'BOUNDED',
            workspaces=dict(large_copper=None,t04=str(job/'t04')),shared_preparation=str(work/'shared_copper_context'),
            native_handles='SEPARATE_PROCESS_LOCAL_WORKERS; SHARED_AUTHENTICATED_PREPARATION')
        atomic_write(job/'PLAN.json',encode(plan));started=time.perf_counter()
        phase='intake'
        def state(value,**extra):
            record=dict(status=value,job=str(job),phase=phase,owner=process_identity(),execution_sha256=key,
                        elapsed_seconds=time.perf_counter()-started,**extra)
            atomic_write(job/'STATE.json',encode(record));progress(**record)
        def unchanged():
            if implementation()!=code:raise ValueError('COPPER_PIPELINE_IMPLEMENTATION_OR_POLICY_CHANGED')
        try:
            state('RUNNING')
            if raw is not None:
                (job/'intake').mkdir();source_copy=job/'intake/source.gbr';source_copy.write_bytes(raw)
                phase='large_copper';state('RUNNING')
                _worker(['tools/run_large_copper.py','run','--source',str(source_copy),'--output',str(job/'large_copper')],job,'large_copper')
                with (job/'large_copper.stdout.log').open()as stream:
                    last=next(reversed([line for line in stream if line.strip()]))
                answer=json.loads(last);cleanup_job=workspace_path(answer['job'])
            unchanged();phase='seal_cleanup_output';state('RUNNING')
            cleanup=publish(cleanup_job,job/'handoffs/large_copper.output.json')
            saved=verify(cleanup['path'],cleanup['sha256'],phase='large_copper')
            if saved['summary'].get('input_assembly',{}).get('raw_source_sha256',saved['source_sha256'])!=source_sha:
                raise ValueError('COPPER_PIPELINE_SOURCE_CHANGED')
            phase='t04';state('RUNNING')
            command=['tools/run_t04_after_cleanup.py','--cleanup-seal',cleanup['path'],
                     '--cleanup-seal-sha256',cleanup['sha256'],'--output',str(job/'t04')]
            if scope_raw is not None:
                path=job/'t04-scope.json';path.write_bytes(scope_raw);command.extend(['--scope',str(path)])
            _worker(command,job,'t04');unchanged()
            prepared=verify(cleanup['path'],cleanup['sha256'],phase='large_copper')
            phase='seal_t04_output';state('RUNNING')
            t04=publish(job/'t04',job/'handoffs/t04.output.json',phase='t04',parent_ref=cleanup)
            child=verify(t04['path'],t04['sha256'],phase='t04')
            value=dict(schema='pcb-copper-pipeline-result/1',status='COMPLETED',job=str(job),
                execution_sha256=key,source_sha256=prepared['source_sha256'],input_source_sha256=source_sha,
                scope=plan['scope'],outputs=dict(large_copper=cleanup,t04=t04),
                workspaces=dict(large_copper=str(cleanup_job),t04=str(job/'t04')),
                shared_preparation=plan['shared_preparation'],wall_seconds=time.perf_counter()-started,
                completion=child['summary'].get('completion','COMPLETED'),
                review_finding_count=child['summary'].get('review_finding_count',0),
                display='NOT_REQUESTED; SEPARATE_SAVED_WORKSPACES',export=False,acceptance='NO_PROMOTION')
            atomic_write(job/'RESULT.json',encode(value));phase='complete';state('COMPLETED',result=reference(job/'RESULT.json'))
            return value
        except BaseException as exc:
            failure=dict(error=repr(exc),traceback=traceback.format_exc(),remaining='NOT_RUN',pipeline_output_published=False,
                         completed_phase_seals_retained=True)
            atomic_write(job/'FAILED.json',encode(failure));state('FAILED_RETAINED',failure=reference(job/'FAILED.json'))
            raise
