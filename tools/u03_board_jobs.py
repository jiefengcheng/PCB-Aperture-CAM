"""U03's separate fresh job namespace, using the project-native launch bridge."""
from tools import t01_crop_jobs as jobs
from tools import t01_board_export_jobs as directory
from tools.pcb_workspace import WORK,require_storage
from datetime import datetime,timezone
from pathlib import Path
import uuid
from tools.t01_route_client import encode,publish
from src.pcb_data_abi.input_directory import validate,verify_snapshot

MANAGED=WORK/'operator_routes/u03_board/managed'


def configure():
    require_storage();jobs.MANAGED=MANAGED


def intake(value,crop=None):
    configure()
    if jobs.launcher_ready().get('u03_board')!='native-u03/1':raise ValueError('NATIVE_LAUNCHER_UPDATE_REQUIRED: close launcher Terminal and reopen tools/Start_T01_Native_Launcher.command once; no U03 job started')
    if crop is not None:
        if not Path(crop).is_absolute():raise ValueError('U03_ABSOLUTE_CROP_PATH_REQUIRED')
        if jobs.launcher_ready().get('u03_crops')!='native-u03-crops/1':raise ValueError('NATIVE_LAUNCHER_UPDATE_REQUIRED: reopen tools/Start_T01_Native_Launcher.command once for crop images')
        return crop_intake(value,crop)
    return directory.native_intake(value,action='u03_directory_intake',task_scope='u03-board')


def dispositions(job):
    from src.u03_board.custody import operation_steps
    from tools.t01_route_client import decode
    root=job/'native' if job else None;accepted=set();attempted=set()
    if root and root.exists():
        for path in (root/'audits').glob('*/decision.json'):
            value=decode(path.read_bytes())
            if value.get('status')=='PASS_SLICE_OBSERVATION_AUDIT':accepted.add(value['accepted_operation'])
        for path in (root/'attempts').glob('*/receipt.json'):attempted.add(decode(path.read_bytes())['tool'])
    return [dict(operation=op,status='PASS' if op in accepted else 'FAIL' if op in attempted else 'NOT_RUN') for op in operation_steps(root)]


def allocate(manifest,blobs,*,crop=None):
    if crop is None:return directory.allocate(manifest,blobs,task_scope='u03-board')
    from src.u03_board.crop_roi import read_crop
    crop_record,crop_blob=read_crop(crop)
    task_scope='u03-board'
    validate(manifest)
    if set(blobs)!={r['relative_path']for r in manifest['files']}:raise ValueError('INPUT_DIRECTORY_BLOB_SET_CHANGED')
    # Companion identity uses the sorted content multiset, not filenames: a
    # rename cannot evade a retained failure. Duplicate companion bytes remain.
    companions=sorted((r for r in manifest['files']if r['kind']=='companion'),key=lambda r:r['sha256'])
    rows={('kicad'if r['kind']=='kicad'else'gerber:'+r['layer']):dict(path=str(Path(manifest['provided_directory'])/r['relative_path']),sha256=r['sha256'],bytes=r['bytes'])for r in manifest['files']if r['kind']!='companion'}
    rows.update({'companion:'+str(i):dict(path=str(Path(manifest['provided_directory'])/r['relative_path']),sha256=r['sha256'],bytes=r['bytes'])for i,r in enumerate(companions)})
    rows['crop']=dict(path=crop_record['provided_path'],sha256=crop_record['sha256'],bytes=crop_record['bytes'])
    version=jobs.implementation();key=jobs.admit(rows,version)
    job=jobs.output(jobs.MANAGED/'jobs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex));job.mkdir(parents=True)
    snapshot=job/'raw_inputs';snapshot.mkdir()
    paths={('kicad'if r['kind']=='kicad'else r['layer']):snapshot/r['relative_path']for r in manifest['files']if r['kind']!='companion'}
    mp=job/'INPUT_DIRECTORY.json';publish(mp,encode(manifest))
    staged=dict(kicad=str(paths['kicad']),gerber=str(paths['F.Cu']))
    crop_path=job/'raw_crop'/('crop'+Path(crop).suffix);crop_path.parent.mkdir();publish(crop_path,crop_blob)
    row=dict(schema='pcb-crop-job/1',crop=dict(crop_record,path=str(crop_path)),task_scope=task_scope,job=str(job),input_sha256=key,implementation_sha256=version,inputs=rows,staged=staged,input_directory=str(mp),input_directory_sha256=jobs.digest(mp.read_bytes()),rendering='NOT_REQUESTED')
    publish(job/'job.json',encode(row))
    try:
        for r in manifest['files']:
            data=blobs[r['relative_path']]
            if jobs.digest(data)!=r['sha256']or len(data)!=r['bytes']:raise ValueError('INPUT_DIRECTORY_CHANGED_BEFORE_STAGING')
            path=jobs.output(snapshot/r['relative_path']);path.parent.mkdir(parents=True,exist_ok=True);publish(path,data)
        verify_snapshot(manifest,snapshot)
    except Exception as error:jobs.halt(job,error);raise
    jobs.replace(jobs.MANAGED/'current.json',row);return job,row



def crop_intake(value,crop,timeout=1200):
    action="u03_directory_intake";task_scope="u03-board"
    """File-only client: never list, stat, read or launch against the input dir."""
    import time
    from tools.t01_route_client import decode
    host=jobs.launcher_ready()
    if host.get('directory_intake')!='native-directory/1':raise ValueError('NATIVE_LAUNCHER_UPDATE_REQUIRED: close the old launcher Terminal and reopen tools/Start_T01_Native_Launcher.command; no input scan or job started')
    directory=str(Path(value).expanduser().absolute())
    rid='intake-'+uuid.uuid4().hex
    request=dict(action=action,launcher_id=host['launcher_id'],input_directory=directory,companion_policy='PRESERVE_EXCLUDED',crop=str(crop))
    publish(jobs.output(jobs.LAUNCHER/'inbox'/(rid+'.json')),encode(request))
    until=time.monotonic()+timeout;last=0.
    evidence=jobs.output(jobs.LAUNCHER/'calls'/rid)
    while time.monotonic()<until:
        if jobs.launcher_ready()['launcher_id']!=host['launcher_id']:raise directory.NativeIntakeError(dict(error='NATIVE_LAUNCHER_CHANGED_DURING_INTAKE'),evidence)
        reply=jobs.output(jobs.LAUNCHER/'replies'/(rid+'.json'))
        if reply.exists():
            result=decode(reply.read_bytes())
            if result.get('launcher_id')!=host['launcher_id']:raise directory.NativeIntakeError(dict(error='NATIVE_INTAKE_REPLY_CHANGED'),evidence)
            if result['status']!='INTAKE_READY':raise directory.NativeIntakeError(result,evidence)
            job=jobs.output(result['job']);row=decode((job/'job.json').read_bytes())
            if result['job_sha256']!=jobs.digest((job/'job.json').read_bytes())or row.get('task_scope')!=task_scope:raise directory.NativeIntakeError(dict(error='NATIVE_INTAKE_JOB_BINDING_CHANGED'),evidence)
            return job,row
        if time.monotonic()-last>10:
            import sys
            print('Native directory intake: source qualification running; no rendering.',file=sys.stderr,flush=True);last=time.monotonic()
        time.sleep(.1)
    # Leave the running request/evidence intact. No resubmission or cancellation.
    publish(evidence/'cancel_requested.json',encode(dict(reason='client intake timeout; preserve evidence and stop before job publication')))
    raise directory.NativeIntakeError(dict(error='NATIVE_DIRECTORY_INTAKE_TIMEOUT: retained request; native cancellation requested; no automatic retry'),evidence)
