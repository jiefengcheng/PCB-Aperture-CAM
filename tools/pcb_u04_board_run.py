#!/usr/bin/env python3
"""Single native Terminal run: fresh directory U04, dynamic audit count, exports only."""
import argparse,json,os,sys,time,threading,uuid,subprocess,signal,traceback
from datetime import datetime,timezone
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import t01_crop_jobs as jobs
from tools.t01_route_client import encode,decode,publish


from tools.pcb_t01_board_run import OwnedRunner,retain_error,adapter_health


def run(input_dir,*,state_dir=None,crop=None,c03_recovery=False):
    if crop is not None:
        if not Path(crop).is_absolute():raise ValueError('U04_ABSOLUTE_CROP_PATH_REQUIRED')
    if not Path(input_dir).is_absolute():raise ValueError('EXPLICIT_ABSOLUTE_INPUT_DIRECTORY_REQUIRED')
    from tools.t01_native_route import require_native
    from tools.u04_board_route import initialize,MachineRoute
    if c03_recovery:
        if crop is None:raise ValueError('C03_EXPLICIT_CROP_REQUIRED')
        from tools.c03_recovery_route import initialize,MachineRoute
    from tools.u04_board_auto_operator import MachineOperator
    if c03_recovery:
        from tools.c03_recovery_operator import C03MachineOperator as MachineOperator
    from tools.t01_macos_adapter import MacOSAdapter
    from tools.pcb_workspace import configure
    configure()
    from tools import u04_board_jobs
    u04_board_jobs.configure()
    require_native()
    if sys.platform!='darwin':raise ValueError('MACOS_NATIVE_TERMINAL_REQUIRED')
    if state_dir is not None:
        from tools.pcb_workspace import WORK
        if Path(state_dir).absolute()!=u04_board_jobs.MANAGED:raise ValueError('U04_MANAGED_NAMESPACE_REQUIRED')
        jobs.MANAGED=jobs.output(Path(state_dir).absolute())
    journal=jobs.output(jobs.MANAGED.parent/'terminal_runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex));journal.mkdir(parents=True)
    registry=journal/'intake';call=registry/'calls/directory';call.mkdir(parents=True);(registry/'replies').mkdir()
    request=dict(action='u04_directory_intake',launcher_id='terminal-'+uuid.uuid4().hex,input_directory=str(Path(input_dir).expanduser().absolute()),companion_policy='PRESERVE_EXCLUDED')
    if crop is not None:request['crop']=str(crop)
    publish(call/'request.json',encode(request));job=None;operator=None;thread=None;stop=threading.Event();thread_error=[];stage='intake';owned=OwnedRunner(journal/'processes')
    def progress(event,**facts):print(json.dumps(dict(status=event,**facts),sort_keys=True),flush=True)
    try:
        progress('NATIVE_DIRECTORY_INTAKE',selection=str(crop) if crop else 'WHOLE_BOARD',input_directory=request['input_directory'],evidence=str(call),rendering='NOT_REQUESTED')
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
            publish(job/'TERMINAL_RUN.json',encode(dict(schema='pcb-u04-terminal-run/1',journal=str(journal),mode='DETERMINISTIC_MACHINE_AUDIT',pid=os.getpid(),human_or_agent_observations='NOT_RUN')))
            session=initialize(job/'native',mode='DETERMINISTIC_MACHINE_AUDIT');route=MachineRoute(session,runner=owned);adapter=MacOSAdapter(route)
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
                progress('MACHINE_AUDIT_PENDING',slice=i+1,total=len(operator.steps),operation=op,facts=result.get('facts'),job=str(job))
                if thread_error:raise ValueError('TERMINAL_ADAPTER_FAILED:'+str(thread_error))
                operator.audit_current(advance=False)
                progress('MACHINE_AUDIT_PASSED',slice=i+1,total=len(operator.steps),operation=op)
                result=operator.offer(i+1)if i<len(operator.steps)-1 else operator.finish()
            if result.get('machine_audits')!=len(operator.steps) or result.get('observation_audits')!=0 or result.get('render_operations')!=0:raise ValueError('TERMINAL_MACHINE_SEQUENCE_INCOMPLETE')
            result.update(job=str(job),terminal_journal=str(journal))
            publish(journal/'result.json',encode(result));jobs.stop(job)
            progress('COMPLETE_MACHINE_AUDITED_U04_EXPORT',job=str(job),machine_audits=len(operator.steps),rendering='NOT_REQUESTED')
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
        from src.u04_board.custody import operation_steps
        operations=operation_steps(job/'native' if job else None,cropped=crop is not None)
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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',required=True,type=Path);p.add_argument('--state-dir',type=Path,help='Optional isolated managed state under project out/; default is the shared project job slot');choice=p.add_mutually_exclusive_group();choice.add_argument('--crop',type=Path,help='Absolute crop image path; native image-to-source location gates select complete features, with full-board clearance context');choice.add_argument('--whole-board',action='store_true',help='Explicitly select whole-board processing (the default without --crop)');p.add_argument('--c03-recovery',action='store_true',help='Explicit owner-bound exact C03 round/contact family; original blocked obligations retained');args=p.parse_args()
    if args.crop is not None and not args.crop.is_absolute():p.error('--crop requires an absolute image file path')
    return run(args.input_dir,state_dir=args.state_dir,crop=args.crop,c03_recovery=args.c03_recovery)
if __name__=='__main__':raise SystemExit(main())
