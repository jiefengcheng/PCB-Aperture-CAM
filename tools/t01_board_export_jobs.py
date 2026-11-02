"""Fresh directory-bound export-only jobs over the existing native Mac launcher."""
from datetime import datetime,timezone
from pathlib import Path
import uuid
from tools import t01_crop_jobs as jobs
from tools.t01_route_client import encode,publish
from src.pcb_data_abi.input_directory import collect,validate,verify_snapshot

SCOPE='full-board-export-only'

def allocate(manifest,blobs,*,task_scope=SCOPE):
    validate(manifest)
    if set(blobs)!={r['relative_path']for r in manifest['files']}:raise ValueError('INPUT_DIRECTORY_BLOB_SET_CHANGED')
    # Companion identity uses the sorted content multiset, not filenames: a
    # rename cannot evade a retained failure. Duplicate companion bytes remain.
    companions=sorted((r for r in manifest['files']if r['kind']=='companion'),key=lambda r:r['sha256'])
    rows={('kicad'if r['kind']=='kicad'else'gerber:'+r['layer']):dict(path=str(Path(manifest['provided_directory'])/r['relative_path']),sha256=r['sha256'],bytes=r['bytes'])for r in manifest['files']if r['kind']!='companion'}
    rows.update({'companion:'+str(i):dict(path=str(Path(manifest['provided_directory'])/r['relative_path']),sha256=r['sha256'],bytes=r['bytes'])for i,r in enumerate(companions)})
    version=jobs.implementation();key=jobs.admit(rows,version)
    job=jobs.output(jobs.MANAGED/'jobs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex));job.mkdir(parents=True)
    snapshot=job/'raw_inputs';snapshot.mkdir()
    paths={('kicad'if r['kind']=='kicad'else r['layer']):snapshot/r['relative_path']for r in manifest['files']if r['kind']!='companion'}
    mp=job/'INPUT_DIRECTORY.json';publish(mp,encode(manifest))
    staged=dict(kicad=str(paths['kicad']),gerber=str(paths['F.Cu']))
    row=dict(schema='pcb-crop-job/1',task_scope=task_scope,job=str(job),input_sha256=key,implementation_sha256=version,inputs=rows,staged=staged,input_directory=str(mp),input_directory_sha256=jobs.digest(mp.read_bytes()),rendering='NOT_REQUESTED')
    publish(job/'job.json',encode(row))
    try:
        for r in manifest['files']:
            data=blobs[r['relative_path']]
            if jobs.digest(data)!=r['sha256']or len(data)!=r['bytes']:raise ValueError('INPUT_DIRECTORY_CHANGED_BEFORE_STAGING')
            path=jobs.output(snapshot/r['relative_path']);path.parent.mkdir(parents=True,exist_ok=True);publish(path,data)
        verify_snapshot(manifest,snapshot)
    except Exception as error:jobs.halt(job,error);raise
    jobs.replace(jobs.MANAGED/'current.json',row);return job,row


class NativeIntakeError(ValueError):
    def __init__(self,result,evidence):
        self.details=result.get('error_details');self.evidence=str(evidence)
        super().__init__(result.get('error','NATIVE_DIRECTORY_INTAKE_FAILED'))

def native_intake(value,timeout=1200,*,action="directory_intake",task_scope=SCOPE):
    """File-only client: never list, stat, read or launch against the input dir."""
    import time
    from tools.t01_route_client import decode
    host=jobs.launcher_ready()
    if host.get('directory_intake')!='native-directory/1':raise ValueError('NATIVE_LAUNCHER_UPDATE_REQUIRED: close the old launcher Terminal and reopen tools/Start_T01_Native_Launcher.command; no input scan or job started')
    directory=str(Path(value).expanduser().absolute())
    rid='intake-'+uuid.uuid4().hex
    request=dict(action=action,launcher_id=host['launcher_id'],input_directory=directory,companion_policy='PRESERVE_EXCLUDED')
    publish(jobs.output(jobs.LAUNCHER/'inbox'/(rid+'.json')),encode(request))
    until=time.monotonic()+timeout;last=0.
    evidence=jobs.output(jobs.LAUNCHER/'calls'/rid)
    while time.monotonic()<until:
        if jobs.launcher_ready()['launcher_id']!=host['launcher_id']:raise NativeIntakeError(dict(error='NATIVE_LAUNCHER_CHANGED_DURING_INTAKE'),evidence)
        reply=jobs.output(jobs.LAUNCHER/'replies'/(rid+'.json'))
        if reply.exists():
            result=decode(reply.read_bytes())
            if result.get('launcher_id')!=host['launcher_id']:raise NativeIntakeError(dict(error='NATIVE_INTAKE_REPLY_CHANGED'),evidence)
            if result['status']!='INTAKE_READY':raise NativeIntakeError(result,evidence)
            job=jobs.output(result['job']);row=decode((job/'job.json').read_bytes())
            if result['job_sha256']!=jobs.digest((job/'job.json').read_bytes())or row.get('task_scope')!=task_scope:raise NativeIntakeError(dict(error='NATIVE_INTAKE_JOB_BINDING_CHANGED'),evidence)
            return job,row
        if time.monotonic()-last>10:
            import sys
            print('Native directory intake: source qualification running; no rendering.',file=sys.stderr,flush=True);last=time.monotonic()
        time.sleep(.1)
    # Leave the running request/evidence intact. No resubmission or cancellation.
    publish(evidence/'cancel_requested.json',encode(dict(reason='client intake timeout; preserve evidence and stop before job publication')))
    raise NativeIntakeError(dict(error='NATIVE_DIRECTORY_INTAKE_TIMEOUT: retained request; native cancellation requested; no automatic retry'),evidence)
