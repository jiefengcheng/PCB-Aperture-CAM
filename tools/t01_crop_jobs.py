"""Stdlib job lifecycle for the macOS crop facade; no geometry or audit authority."""
import contextlib
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import sys
import time
import uuid
from tools.t01_route_client import child, decode, encode, publish

ROOT = Path(__file__).resolve().parents[1]
from tools.pcb_workspace import WORK, require_storage
MANAGED = WORK/'operator_routes/t01_crop/managed'
LAUNCHER = WORK/'operator_routes/t01_crop/launcher'
MAX_INPUT = 256 * 1024 * 1024


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def output(path):
    path = Path(path).absolute()
    if path.is_relative_to(WORK):require_storage()
    if '..' in path.parts or not path.is_relative_to(ROOT/'out'):
        raise ValueError('PROJECT_OUTPUT_PATH_REQUIRED')
    return child(ROOT, path)


def replace(path, value):
    temporary = path.with_name('.update-'+uuid.uuid4().hex)
    publish(temporary, encode(value))
    os.replace(temporary, path)


@contextlib.contextmanager
def exclusive():
    output(MANAGED).mkdir(parents=True, exist_ok=True)
    lock = output(MANAGED/'command.lock')
    with lock.open('a+b') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('CROP_COMMAND_IN_PROGRESS: wait for the existing command; no parallel start or review')
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def attachment(value):
    # Read only the explicit path; never discover inputs by searching.
    p = Path(value).absolute()
    if '..' in p.parts or any(q.is_symlink() for q in (p, *p.parents)):
        raise ValueError('ACTUAL_REGULAR_ATTACHMENT_REQUIRED')
    with p.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_INPUT:
            raise ValueError('ATTACHMENT_SIZE_OR_TYPE_UNSUPPORTED')
        blob = stream.read(MAX_INPUT+1)
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino) or len(blob) != before.st_size:
        raise ValueError('ATTACHMENT_CHANGED_DURING_INTAKE')
    return dict(path=str(p), sha256=digest(blob), bytes=len(blob)), blob


def inputs(crop, kicad=None, gerber=None, *, attachments=None):
    defaults = decode((ROOT/'contracts/operator/t01_project.json').read_bytes())['inputs']
    rows, blobs = {}, {}
    for name, supplied in [('crop', crop), ('kicad', kicad), ('gerber', gerber)]:
        if name in (attachments or {}):
            if supplied is not None:raise ValueError('ONE_INPUT_REPRESENTATION_REQUIRED:'+name)
            from tools.t01_crop_attachments import ingest
            row,blob=ingest(attachments[name],ROOT,attachment)
        else:
            value = supplied if supplied is not None else str(ROOT/defaults[name]['path'])
            row, blob = attachment(value)
        if supplied is None and name not in (attachments or {}) and row['sha256'] != defaults[name]['sha256']:
            raise ValueError('PROJECT_INPUT_CHANGED:'+name)
        rows[name], blobs[name] = row, blob
    return rows, blobs


def fingerprint(rows):
    # Paths/names do not create an escape from a failed-input latch.
    return digest(encode({name: row['sha256'] for name, row in rows.items()}))


def implementation():
    paths = [ROOT/'AGENTS.md']
    for directory, pattern in [('src','*.py'), ('tools','*.py'), ('contracts','*')]:
        paths.extend(p for p in (ROOT/directory).rglob(pattern) if p.is_file())
    return digest(encode({str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in sorted(paths)}))


def current():
    path = output(MANAGED/'current.json')
    if not path.exists():
        raise ValueError('NO_CROP_JOB: start with an actual attachment first')
    row = decode(path.read_bytes())
    job = output(row['job'])
    recorded = decode((job/'job.json').read_bytes())
    if recorded != row:
        raise ValueError('CROP_JOB_POINTER_CHANGED')
    return job, row


def outcome(job):
    if (job/'halted.json').exists():
        return 'HALTED'
    native = job/'native'
    ui = native/'operator_ui'
    if (ui/'failure.json').exists() or (job/'worker_failed.json').exists():
        return 'HALTED'
    if (ui/'current.json').exists() and decode((ui/'current.json').read_bytes()).get('status') == 'COMPLETE':
        return 'COMPLETE'
    if (native/'adapter_stopped.json').exists():
        return 'HALTED'
    status=job/'worker_status.json'
    if status.exists():
        row=decode(status.read_bytes())
        if row['status']!='RUNNING' or time.time()-row['updated_at']>15:return 'HALTED'
    return 'IN_PROGRESS'


def admit(rows, version):
    key = fingerprint(rows)
    active = MANAGED/'current.json'
    if active.exists():
        job, _ = current()
        if outcome(job) == 'IN_PROGRESS':
            raise ValueError('CROP_JOB_IN_PROGRESS: review the existing job; new start cannot replace it')
    for path in (MANAGED/'jobs').glob('*/job.json'):
        row = decode(path.read_bytes())
        if row['input_sha256'] == key and row['implementation_sha256'] == version and outcome(path.parent) == 'HALTED':
            raise ValueError('FAILED_CROP_INPUTS_RETAINED: no automatic retry; '+str(path.parent))
    return key


def allocate(rows, blobs):
    version = implementation()
    key = admit(rows, version)
    job = output(MANAGED/'jobs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex))
    job.mkdir(parents=True)
    staged = job/'inputs'; staged.mkdir()
    args = {name: str(staged/(name+suffix)) for name, suffix in [('crop','.png'), ('kicad','.kicad_pcb'), ('gerber','.gbr')]}
    row = dict(schema='pcb-crop-job/1', job=str(job), input_sha256=key, implementation_sha256=version, inputs=rows, staged=args)
    publish(job/'job.json', encode(row))
    try:
        for name, path in args.items():
            publish(Path(path), blobs[name])
            if digest(Path(path).read_bytes()) != rows[name]['sha256']:
                raise ValueError('STAGED_ATTACHMENT_CHANGED')
    except Exception as error:
        halt(job,error)
        raise
    replace(MANAGED/'current.json', row)
    return job, row


def stop(job):
    path = output(job/'stop_requested.json')
    if not path.exists():
        publish(path, encode(dict(reason='Facade reached terminal outcome; do not replay')))


def halt(job, error):
    path = output(job/'halted.json')
    if not path.exists():
        publish(path, encode(dict(status='HALTED', error=str(error))))
    stop(job)


def launcher_ready():
    try:
        row=decode(output(LAUNCHER/'current.json').read_bytes())
        age=time.time()-row['updated_at']
        if row['schema']!='pcb-native-launcher/1' or row['status']!='READY' or not 0<=age<15:
            raise ValueError('stopped or stale launcher')
        return row
    except (OSError,ValueError,KeyError) as error:
        raise ValueError('NATIVE_LAUNCHER_REQUIRED: open tools/Start_T01_Native_Launcher.command once and leave its window open; no crop job started') from error


def launch(job, *, timeout=120):
    # File-only bridge: the embedded client never performs OS process operations.
    host=launcher_ready();rid='launch-'+uuid.uuid4().hex
    publish(output(LAUNCHER/'inbox'/ (rid+'.json')),encode(dict(launcher_id=host['launcher_id'],job=str(job),job_sha256=digest((job/'job.json').read_bytes()))))
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if launcher_ready()['launcher_id']!=host['launcher_id']:raise ValueError('NATIVE_LAUNCHER_CHANGED')
        reply=output(LAUNCHER/'replies'/(rid+'.json'))
        if reply.exists():
            result=decode(reply.read_bytes())
            if result['status']!='LAUNCHED':raise ValueError('CROP_RUNNER_SETUP_FAILED: '+str(result))
            if result['launcher_id']!=host['launcher_id'] or result['job']!=str(job):raise ValueError('LAUNCH_REPLY_CHANGED')
            if (job/'ready.json').exists():return binding(job)
        if (job/'worker_failed.json').exists():raise ValueError('CROP_RUNNER_SETUP_FAILED: '+str(job/'worker_failed.json'))
        if (job/'worker_status.json').exists() and decode((job/'worker_status.json').read_bytes())['status']!='RUNNING':raise ValueError('CROP_RUNNER_EXITED_BEFORE_READY')
        time.sleep(.1)
    raise TimeoutError('CROP_RUNNER_SETUP_TIMEOUT: retained job; no automatic restart')


def binding(job, *, require_live=True):
    ready = decode(output(job/'ready.json').read_bytes())
    path = output(job/'native/operator_binding.json')
    if ready['binding_sha256'] != digest(path.read_bytes()) or ready['session'] != str(job/'native'):
        raise ValueError('CROP_RUNNER_BINDING_CHANGED')
    if require_live:
        if (job/'native/adapter_stopped.json').exists() or (job/'worker_failed.json').exists():
            raise ValueError('CROP_RUNNER_STOPPED: retained evidence; no automatic restart')
        host=launcher_ready()
        launch_record=decode((job/'launch.json').read_bytes())
        status=decode((job/'worker_status.json').read_bytes())
        if (launch_record['launcher_id']!=host['launcher_id'] or status['launcher_id']!=host['launcher_id'] or
                status['status']!='RUNNING' or not 0<=time.time()-status['updated_at']<15):
            raise ValueError('CROP_RUNNER_INTERRUPTED: retained evidence; no automatic restart')
    return path
