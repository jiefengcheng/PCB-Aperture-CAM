#!/usr/bin/env python3
"""Project-local native launch bridge for file-only embedded clients. No network."""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import signal
import sys
import time
import uuid
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import t01_crop_jobs as jobs
from tools.t01_route_client import decode,encode,publish


class Launcher:
    def __init__(self,registry):
        self.registry=jobs.output(registry);self.registry.mkdir(parents=True,exist_ok=True)
        self.lock=(self.registry/'launcher.lock').open('a+b')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close();raise ValueError('NATIVE_LAUNCHER_ALREADY_RUNNING')
        self.id='launcher-'+uuid.uuid4().hex;self.children={};self.intakes={}
        from tools.u05_app import Continuations
        self.u05=Continuations(ROOT,self.registry,self.id)
        for name in ('inbox','replies','calls'):(self.registry/name).mkdir(exist_ok=True)
        self.heartbeat('READY')
    def heartbeat(self,status):
        jobs.replace(self.registry/'current.json',dict(schema='pcb-native-launcher/1',launcher_id=self.id,status=status,updated_at=time.time(),network=False,directory_intake='native-directory/1',u02_board='native-u02/1',u03_board='native-u03/1',u03_crops='native-u03-crops/1',u04_board='native-u04/1',u05_board='native-u05/1'))
    def process(self,path):
        from tools.t01_route_client import safe_id
        rid=safe_id(path.stem);call=self.registry/'calls'/rid
        try:call.mkdir()
        except FileExistsError:return
        job=None;request={}
        try:
            request=decode(path.read_bytes());publish(call/'request.json',encode(request))
            if request.get('action')=='u05_continuation':
                self.u05.start(rid,call,request);return
            if request.get('action') in ('directory_intake','u02_directory_intake','u03_directory_intake','u04_directory_intake'):
                allowed={'action','launcher_id','input_directory','companion_policy'}
                if request['action'] in ('u03_directory_intake','u04_directory_intake') and 'crop' in request:
                    if type(request['crop']) is not str or not Path(request['crop']).is_absolute():raise ValueError('U03_ABSOLUTE_CROP_PATH_REQUIRED')
                    allowed.add('crop')
                if set(request)!=allowed or request['launcher_id']!=self.id or request['companion_policy']!='PRESERVE_EXCLUDED'or type(request['input_directory'])is not str or len(request['input_directory'])>8192:raise ValueError('DIRECTORY_INTAKE_REQUEST_INVALID_OR_STALE')
                if any(p.poll()is None for p in self.intakes.values()):raise ValueError('NATIVE_DIRECTORY_INTAKE_IN_PROGRESS')
                managed=jobs.MANAGED
                if request['action']=='u02_directory_intake':
                    from tools.u02_board_jobs import MANAGED
                    managed=MANAGED
                elif request['action']=='u04_directory_intake':
                    from tools.u04_board_jobs import MANAGED
                    managed=MANAGED
                elif request['action']=='u03_directory_intake':
                    from tools.u03_board_jobs import MANAGED
                    managed=MANAGED
                argv=[str(ROOT/'.venv/bin/python'),'-B',str(ROOT/'tools/t01_directory_intake_worker.py'),'--call',str(call),'--registry',str(self.registry),'--managed',str(managed)]
                with(call/'stdout').open('xb')as stdout,(call/'stderr').open('xb')as stderr:
                    self.intakes[rid]=subprocess.Popen(argv,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True)
                publish(call/'launch.json',encode(dict(pid=self.intakes[rid].pid,argv=argv,launcher_id=self.id)))
                return
            if set(request)!={'launcher_id','job','job_sha256'} or request['launcher_id']!=self.id:raise ValueError('LAUNCH_REQUEST_INVALID_OR_STALE')
            job=jobs.output(request['job'])
            from tools.u02_board_jobs import MANAGED as U02_MANAGED
            from tools.u03_board_jobs import MANAGED as U03_MANAGED
            from tools.u04_board_jobs import MANAGED as U04_MANAGED
            if job.parent not in (jobs.MANAGED/'jobs',U02_MANAGED/'jobs',U03_MANAGED/'jobs',U04_MANAGED/'jobs'):raise ValueError('MANAGED_JOB_REQUIRED')
            if jobs.digest((job/'job.json').read_bytes())!=request['job_sha256']:raise ValueError('JOB_RECORD_CHANGED')
            if (job/'launch.json').exists() or (job/'halted.json').exists():raise ValueError('FRESH_UNHALTED_JOB_REQUIRED')
            record=decode((job/'job.json').read_bytes())
            if record['job']!=str(job):raise ValueError('JOB_RECORD_PATH_CHANGED')
            if (record.get('task_scope')=='u02-board')!=(job.parent==U02_MANAGED/'jobs'):raise ValueError('JOB_SCOPE_NAMESPACE_MISMATCH')
            if (record.get('task_scope')=='u03-board')!=(job.parent==U03_MANAGED/'jobs'):raise ValueError('JOB_SCOPE_NAMESPACE_MISMATCH')
            if (record.get('task_scope')=='u04-board')!=(job.parent==U04_MANAGED/'jobs'):raise ValueError('JOB_SCOPE_NAMESPACE_MISMATCH')
            argv=[str(ROOT/'.venv/bin/python'),'-B',str(ROOT/'tools/start_t01_crop_operator.py'),'--managed-worker','--session',str(job/'native')]
            with (job/'worker.stdout').open('xb') as stdout,(job/'worker.stderr').open('xb') as stderr:
                process=subprocess.Popen(argv,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True)
            self.children[str(job)]=process
            publish(job/'launch.json',encode(dict(pid=process.pid,argv=argv,launcher_id=self.id)))
            result=dict(status='LAUNCHED',launcher_id=self.id,job=str(job))
        except Exception as e:
            result=dict(status='HALTED',error=str(e),launcher_id=self.id)
            if request.get('action')=='u05_continuation':
                result.update(request_id=rid,request_sha256=jobs.digest((call/'request.json').read_bytes()))
                for name in ('stdout','stderr'):
                    if not(call/name).exists():publish(call/name,b'')
                    result[name+'_sha256']=jobs.digest((call/name).read_bytes())
        publish(call/'response.json',encode(result));publish(self.registry/'replies'/(rid+'.json'),encode(result))
    def tick(self):
        self.heartbeat('READY')
        self.u05.tick()
        for path in sorted((self.registry/'inbox').glob('*.json')):
            # Completed calls are retained and never replayed.
            if not (self.registry/'calls'/path.stem).exists():self.process(path)
        for name,process in list(self.children.items()):
            job=Path(name);code=process.poll()
            jobs.replace(job/'worker_status.json',dict(launcher_id=self.id,status='RUNNING' if code is None else 'EXITED',returncode=code,updated_at=time.time()))
            if code is not None:del self.children[name]
        for rid,process in list(self.intakes.items()):
            code=process.poll()
            if code is not None:
                call=self.registry/'calls'/rid
                if not(call/'response.json').exists():
                    result=dict(status='HALTED',error='NATIVE_INTAKE_WORKER_EXITED_WITHOUT_RESULT',returncode=code,launcher_id=self.id,evidence=str(call))
                    publish(call/'response.json',encode(result));publish(self.registry/'replies'/(rid+'.json'),encode(result))
                del self.intakes[rid]
    def close(self):
        self.heartbeat('STOPPED')
        self.u05.close()
        for process in self.intakes.values():
            if process.poll()is None:process.terminate();process.wait(timeout=10)
        for name in self.children:
            jobs.stop(Path(name))
            jobs.replace(Path(name)/'worker_status.json',dict(launcher_id=self.id,status='STOPPED',updated_at=time.time()))
        fcntl.flock(self.lock,fcntl.LOCK_UN);self.lock.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--registry',type=Path,default=jobs.LAUNCHER);a=p.parse_args()
    if sys.platform!='darwin':p.error('macOS required')
    from tools.t01_native_route import require_native
    require_native()
    # A custom registry is for isolated project-output conformance checks.
    registry=jobs.output(a.registry)
    if registry!=jobs.LAUNCHER:jobs.MANAGED=registry.parent/'managed'
    launcher=Launcher(registry)
    def stop_signal(number,frame):raise KeyboardInterrupt
    for number in (signal.SIGTERM,signal.SIGHUP):signal.signal(number,stop_signal)
    print('T01 native launcher ready. Leave this window open for Local Code T01 crop or raw-directory trials. Close it when finished.',flush=True)
    try:
        while not (registry/('stop-'+launcher.id+'.json')).exists():
            launcher.tick();time.sleep(.2)
    except KeyboardInterrupt:pass
    finally:launcher.close()
    return 0

if __name__=='__main__':raise SystemExit(main())
