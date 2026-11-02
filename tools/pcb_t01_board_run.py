#!/usr/bin/env python3
"""Single native Terminal run: fresh directory T01, 18 machine audits, exports only."""
import argparse,json,os,sys,time,threading,uuid,subprocess,signal,traceback
from datetime import datetime,timezone
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import t01_crop_jobs as jobs
from tools.t01_route_client import encode,decode,publish


class OwnedRunner:
    """Only explicitly owned process groups may be stopped on timeout/SIGINT."""
    def __init__(self,evidence=None):self.evidence=evidence;self.lock=threading.Lock();self.current=None;self.cancelled=False
    def _terminate(self,process):
        if process.poll()is None:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait(timeout=10)
    def cancel(self):
        with self.lock:self.cancelled=True;process=self.current
        if process:self._terminate(process)
    def __call__(self,argv,*,cwd,capture_output=True,timeout=300):
        with self.lock:
            if self.cancelled:raise OSError('TERMINAL_RUN_CANCELLED')
            process=subprocess.Popen(argv,cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,close_fds=True);self.current=process
        try:
            try:stdout,stderr=process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._terminate(process);stdout,stderr=process.communicate();raise subprocess.TimeoutExpired(argv,timeout,output=stdout,stderr=stderr)
            if self.evidence:
                record=dict(argv=list(argv),returncode=process.returncode,stdout=stdout.decode(errors="replace"),stderr=stderr.decode(errors="replace"))
                retain_error(self.evidence/("process-"+str(process.pid)+".json"),record)
            return subprocess.CompletedProcess(argv,process.returncode,stdout,stderr)
        finally:
            with self.lock:self.current=None


def retain_error(path, record):
    """Publish evidence when possible; always expose recording failures on stderr."""
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        publish(path,encode(record))
    except BaseException as error:
        print(json.dumps(dict(evidence_write_failed=str(path),error=repr(error),record=record)),file=sys.stderr,flush=True)


def adapter_health(thread, errors):
    if errors:raise RuntimeError('TERMINAL_ADAPTER_FAILED: '+json.dumps(errors,sort_keys=True))
    if not thread.is_alive():raise RuntimeError('TERMINAL_ADAPTER_EXITED_WITHOUT_REPLY')


def run(input_dir,*,state_dir=None):
    from tools.t01_native_route import require_native
    from tools.t01_board_auto_route import initialize,MachineRoute
    from tools.t01_board_auto_operator import MachineOperator
    from tools.t01_macos_adapter import MacOSAdapter
    from tools.pcb_workspace import configure
    configure()
    require_native()
    if sys.platform!='darwin':raise ValueError('MACOS_NATIVE_TERMINAL_REQUIRED')
    if state_dir is not None:
        from tools.pcb_workspace import WORK
        if not Path(state_dir).absolute().is_relative_to(WORK):raise ValueError('T01_STATE_MUST_BE_ON_LACIE')
        jobs.MANAGED=jobs.output(Path(state_dir).absolute())
    journal=jobs.output(jobs.MANAGED.parent/'terminal_runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex));journal.mkdir(parents=True)
    registry=journal/'intake';call=registry/'calls/directory';call.mkdir(parents=True);(registry/'replies').mkdir()
    request=dict(action='directory_intake',launcher_id='terminal-'+uuid.uuid4().hex,input_directory=str(Path(input_dir).expanduser().absolute()),companion_policy='PRESERVE_EXCLUDED')
    publish(call/'request.json',encode(request));job=None;operator=None;thread=None;stop=threading.Event();thread_error=[];stage='intake';owned=OwnedRunner(journal/'processes')
    def progress(event,**facts):print(json.dumps(dict(status=event,**facts),sort_keys=True),flush=True)
    try:
        progress('NATIVE_DIRECTORY_INTAKE',input_directory=request['input_directory'],evidence=str(call),rendering='NOT_REQUESTED')
        # The same native intake worker/closed contract as the Local Code route.
        # Terminal owns the native process, so no pre-opened launcher is needed.
        intake_argv=[sys.executable,'-B',str(ROOT/'tools/t01_directory_intake_worker.py'),'--call',str(call),'--registry',str(registry),'--managed',str(jobs.MANAGED)]
        completed=[];intake_errors=[]
        def qualify():
            try:completed.append(owned(intake_argv,cwd=ROOT,timeout=1200))
            except BaseException as error:intake_errors.append(error)
        intake_thread=threading.Thread(target=qualify,name='T01-native-intake',daemon=True);intake_thread.start();started=time.monotonic();notice=started+20
        while intake_thread.is_alive():
            intake_thread.join(.1)
            if time.monotonic()>=notice:progress('NATIVE_WORK_IN_PROGRESS',operation='directory_intake',elapsed_seconds=round(time.monotonic()-started));notice=time.monotonic()+20
        if intake_errors:raise intake_errors[0]
        completed=completed[0];publish(call/'terminal_stdout.log',completed.stdout);publish(call/'terminal_stderr.log',completed.stderr)
        if completed.returncode:
            failed=decode((call/'response.json').read_bytes())if(call/'response.json').exists()else dict(error='NATIVE_INTAKE_EXITED_WITHOUT_REPLY')
            raise ValueError(failed['error'])
        reply=decode((call/'response.json').read_bytes());job=jobs.output(reply['job']);row=decode((job/'job.json').read_bytes())
        if jobs.digest((job/'job.json').read_bytes())!=reply['job_sha256']:raise ValueError('TERMINAL_INTAKE_JOB_CHANGED')
        with jobs.exclusive():
            publish(job/'TERMINAL_RUN.json',encode(dict(schema='pcb-t01-terminal-run/1',journal=str(journal),mode='DETERMINISTIC_MACHINE_AUDIT',pid=os.getpid(),human_or_agent_observations='NOT_RUN')))
            session=initialize(job/'native');route=MachineRoute(session,runner=owned);adapter=MacOSAdapter(route)
            binding=session/'operator_binding.json';publish(binding,encode(dict(schema='pcb-c01-operator-binding/1',setup=str(session/'agent_setup.json'),setup_sha256=jobs.digest((session/'agent_setup.json').read_bytes()))))
            publish(job/'ready.json',encode(dict(session=str(session),pid=os.getpid(),binding_sha256=jobs.digest(binding.read_bytes()))))
            # One adapter and one client, the same file protocol used by agents.
            # No model requests, invented observations or source probes.
            def serve():
                try:
                    while not stop.is_set():
                        adapter.drain();stop.wait(.01)
                except BaseException as error:
                    record=dict(error_type=type(error).__name__,error=str(error),errno=getattr(error,'errno',None),traceback=traceback.format_exc())
                    thread_error.append(record);stop.set()
                    retain_error(journal/'adapter_failure.json',record)
            thread=threading.Thread(target=serve,name='T01-native-adapter',daemon=True);thread.start();operator=MachineOperator(binding)
            operator.client.health_check=lambda:adapter_health(thread,thread_error)
            stage='native_sequence'
            result=operator.start_board(**row['staged'])
            for i,op in enumerate(operator.steps):
                progress('MACHINE_AUDIT_PENDING',slice=i+1,total=18,operation=op,facts=result.get('facts'),job=str(job))
                if thread_error:raise ValueError('TERMINAL_ADAPTER_FAILED:'+str(thread_error))
                operator.audit_current(advance=False)
                progress('MACHINE_AUDIT_PASSED',slice=i+1,total=18,operation=op)
                result=operator.offer(i+1)if i<17 else operator.finish()
            if result.get('machine_audits')!=18 or result.get('observation_audits')!=0 or result.get('render_operations')!=0:raise ValueError('TERMINAL_MACHINE_SEQUENCE_INCOMPLETE')
            result.update(job=str(job),terminal_journal=str(journal))
            publish(journal/'result.json',encode(result));jobs.stop(job)
            progress('COMPLETE_MACHINE_AUDITED_T01_EXPORT',job=str(job),machine_audits=18,rendering='NOT_REQUESTED')
            print(result['ready_markdown'],flush=True);return 0
    except BaseException as error:
        owned.cancel()
        if job:
            try:jobs.halt(job,error)
            except BaseException as write_error:print('HALT_RECORD_WRITE_FAILED: '+repr(write_error),file=sys.stderr,flush=True)
        complete=[]
        if operator:
            try:complete=list(route.accepted)
            except Exception:pass
        operations=decode((ROOT/'contracts/operator/t01_board_auto.json').read_bytes())['sequence']
        failure=dict(status='HALTED',task_outcome='INCOMPLETE_NOT_ACCEPTED',stage=stage,error=str(error),evidence=str(job or call),job=str(job)if job else None,rendering='NOT_REQUESTED',owner='PENDING_USER',human_or_agent_observations='NOT_RUN',dispositions=[dict(operation=op,status='PASS'if op in complete else'FAIL'if len(complete)==i and stage=='native_sequence'else'NOT_RUN')for i,op in enumerate(operations)],next_action='REPORT_AND_STOP; no retries or acceptance promotion')
        failure.update(error_type=type(error).__name__,traceback=traceback.format_exc(),adapter_errors=thread_error)
        retain_error(journal/'failure.json',failure);print(json.dumps(failure,sort_keys=True),flush=True);return 2
    finally:
        stop.set()
        if thread:thread.join(timeout=10)
        if job and(job/'native').exists():
            p=job/'native/adapter_stopped.json'
            if not p.exists():retain_error(p,dict(status='STOPPED',at=datetime.now(timezone.utc).isoformat(),mode='TERMINAL_NATIVE_AUTOMATION'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',required=True,type=Path);p.add_argument('--state-dir',type=Path,help='Optional isolated managed state under project out/; default is the shared project job slot');args=p.parse_args()
    return run(args.input_dir,state_dir=args.state_dir)
if __name__=='__main__':raise SystemExit(main())
