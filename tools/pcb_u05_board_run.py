#!/usr/bin/env python3
"""Terminal U05: exact retained U04, fresh T05 and fresh audited native exports."""
import sys,json,argparse,subprocess,os,signal,time,uuid,traceback,fcntl
from pathlib import Path
from datetime import datetime,timezone
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.stage_abi.store import canonical,digest
from tools.t01_operator_host import read,fresh
from src.pcb_data_abi.service import fresh as fresh_bytes
from tools.pcb_workspace import configure,WORK
from src.u05_board.custody import binding,inventory,assert_inventory,STEPS,local
from src.u05_board.audit import evaluate
from tools.t01_native_route import require_native,verify_attempt
from src.crop_circle_sources import verify_assets

def now():return datetime.now(timezone.utc).isoformat()
def progress(event,**values):print(json.dumps(dict(values,status=event),sort_keys=True),flush=True)
def implementation():
    files=[ROOT/'AGENTS.md',*[p for folder in ('src','tools','contracts') for p in (ROOT/folder).rglob('*') if p.is_file() and (p.suffix=='.py' or folder=='contracts')],ROOT/'tools/Run_U05_Board.command',ROOT/'docs/agent_abi/U05_SINGLE_COMMAND.md',ROOT/'docs/agent_abi/U05_ATTACHMENT_RULES.md',*sorted((ROOT/'tests').glob('test_u05*.py'))]
    return {str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(set(files))}

def matching_audits(rows):
    if len(rows)!=2 or any(type(r.get('pid')) is not int or r['pid']<=0 for r in rows) or rows[0]['pid']==rows[1]['pid']:raise ValueError('U05_TWO_DISTINCT_MACHINE_EVALUATIONS_REQUIRED')
    proof=rows[0]['proof']
    if proof['status']!='PASS' or rows[1]['proof']!=proof:raise ValueError('U05_MACHINE_REEVALUATION_MISMATCH')
    return proof

def machine_pair(root,attempt,folder):
    evaluations=folder/'evaluations';evaluations.mkdir();workers=[];started=time.monotonic();last=started
    try:
        for n in range(2):
            out=evaluations/f'{n+1}.stdout.json';err=evaluations/f'{n+1}.stderr.log';streams=(out.open('wb'),err.open('wb'))
            argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--machine-evaluate',str(root),attempt]
            try:p=subprocess.Popen(argv,cwd=ROOT,stdout=streams[0],stderr=streams[1],start_new_session=True)
            except BaseException:
                for stream in streams:stream.close()
                raise
            workers.append(dict(process=p,streams=streams,stdout=out,stderr=err,argv=argv))
        while any(w['process'].poll() is None for w in workers):
            if time.monotonic()-last>=20:
                progress('MACHINE_EVALUATIONS_IN_PROGRESS',operation=attempt,elapsed_seconds=int(time.monotonic()-started),finished=sum(w['process'].poll() is not None for w in workers));last=time.monotonic()
            time.sleep(.1)
        for w in workers:
            for stream in w['streams']:stream.close()
        fresh(folder/'evaluations.json',dict(mode='TWO_SEPARATE_FRESH_PROCESSES_CONCURRENT',elapsed_seconds=time.monotonic()-started,workers=[dict(pid=w['process'].pid,argv=w['argv'],exit_code=w['process'].returncode,stdout_sha256=digest(w['stdout'].read_bytes()),stderr_sha256=digest(w['stderr'].read_bytes())) for w in workers]))
        if any(w['process'].returncode!=0 for w in workers):raise ValueError('U05_MACHINE_EVALUATION_PROCESS_FAILED:'+str(evaluations))
        rows=[read(w['stdout']) for w in workers]
        if any(r['pid']!=w['process'].pid for r,w in zip(rows,workers)):raise ValueError('U05_MACHINE_PROCESS_CORRELATION_FAILED')
        return matching_audits(rows)
    finally:
        for w in workers:
            if w['process'].poll() is None:
                try:os.killpg(w['process'].pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:w['process'].wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(w['process'].pid,signal.SIGKILL);w['process'].wait()
            for stream in w['streams']:stream.close()

def native(root,ordinal,op,timeout):
    folder=root/'attempts'/f'{ordinal+1:03d}-{op}';folder.mkdir();abi=folder/'abi';abi.mkdir();request=dict(abi_version='pcb-u05-board/1',request_id=uuid.uuid4().hex,operation=op);fresh(abi/'request.json',request);fresh(abi/'started.json',dict(at=now(),operation=op))
    argv=[sys.executable,'-B',str(ROOT/'tools/pcb_u05_board_abi.py'),'--session',str(root),'--input',str(abi/'request.json')];fresh(folder/'invocation.json',dict(argv=argv,operation=op));p=subprocess.Popen(argv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);started=time.monotonic();failure=None
    try:
        while True:
            try:out,err=p.communicate(timeout=20);break
            except subprocess.TimeoutExpired:
                elapsed=int(time.monotonic()-started);progress('NATIVE_WORK_IN_PROGRESS',operation=op,elapsed_seconds=elapsed)
                if elapsed>=timeout:raise TimeoutError('U05_NATIVE_TIMEOUT:'+op)
    except BaseException as e:
        failure=e
        try:os.killpg(p.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:out,err=p.communicate(timeout=10)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate()
    fresh_bytes(abi/'stdout.json',out);fresh_bytes(abi/'stderr.log',err);fresh(abi/'completed.json',dict(at=now(),operation=op,returncode=p.returncode,error=None if failure is None else str(failure)))
    try:response=json.loads(out)
    except ValueError:response=dict(status='REJECTED',result=None,error=dict(code='U05_INVALID_NATIVE_RESPONSE',message=out[-2000:].decode(errors='replace')))
    fresh(folder/'result.json',response);receipt=dict(schema='u05-native-attempt/1',attempt_id=folder.name,tool=op,status='PASS_NATIVE' if p.returncode==0 and response.get('status')=='OK' and failure is None else 'FAIL',completed_at=now(),files={str(q.relative_to(folder)):digest(q.read_bytes()) for q in folder.rglob('*') if q.is_file()});fresh(folder/'receipt.json',receipt)
    if failure:raise failure
    if receipt['status']=='FAIL':raise ValueError('U05_NATIVE_FAILED:'+str(response.get('error')))
    if any(response[k]!=request[k] for k in ('abi_version','request_id','operation')) or response['error'] is not None:raise ValueError('U05_NATIVE_CORRELATION_FAILED')
    return folder.name,response['result']

def run(predecessor,state_dir=None,reference=None):
    started=time.monotonic();timings=[]
    configure();require_native();base=local((state_dir or WORK/'operator_routes/u05_board/managed').absolute(),False);base.mkdir(parents=True,exist_ok=True);lock=(base/'command.lock').open('a+b');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);job=None;accepted=[];op=None
    try:
        bound=binding(predecessor);reference_bound=None
        if reference is not None:
            from src.u05_board.reference import reference_binding
            reference_bound=reference_binding(reference,bound)
        producers=implementation();fingerprint=digest(canonical(producers));key=digest(canonical(dict(predecessor=bound,implementation=fingerprint,reference=reference_bound)));latch=base/'failed';latch.mkdir(exist_ok=True)
        if (latch/(key+'.json')).exists():raise ValueError('U05_FAILED_INPUT_AND_IMPLEMENTATION_NO_RETRY')
        job=base/'jobs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex);job.mkdir(parents=True);(job/'attempts').mkdir();(job/'audits').mkdir()
        protected=inventory(Path(bound['job']));fresh(job/'U04_INVENTORY.json',protected);fresh(job/'U05_START.json',dict(schema='pcb-u05-start/1',at=now(),predecessor=bound,reference=reference_bound,producer_files=producers,implementation_sha256=fingerprint,operations=list(STEPS),runtime=require_native(),assets=verify_assets(),rendering='NOT_REQUESTED',owner='PENDING_USER'))
        fresh(job/'job.json',dict(task_scope='u05-retained-U04-continuation',implementation_sha256=fingerprint,input_sha256=key,predecessor=bound));fresh(job/'U05_SEQUENCE.json',dict(operations=list(STEPS),accepted=[]));progress('U05_STARTED',job=str(job),retained_U04=bound['job'],new_gates=len(STEPS),prefix='RETAINED_VERIFIED_NOT_REEXECUTED')
        for i,op in enumerate(STEPS):
            operation_started=time.monotonic()
            for previous in accepted:
                proof=job/'audits'/previous['proof'];verify_attempt(job/'attempts'/previous['attempt'])
                if digest(proof.read_bytes())!=previous['proof_sha256']:raise ValueError('U05_PRIOR_AUDIT_CHANGED')
            attempt,result=native(job,i,op,read(ROOT/'contracts/operator/u05_board.json')['native_timeout_seconds']);progress('MACHINE_AUDIT_PENDING',slice=i+1,total=len(STEPS),operation=op,facts=result['facts'])
            folder=job/'audits'/f'{i+1:03d}';folder.mkdir();proof=machine_pair(job,attempt,folder);fresh(folder/'proof.json',proof)
            if proof['status']!='PASS':raise ValueError('U05_MACHINE_PREDICATE_FAILED:'+str(folder/'proof.json'))
            fresh(folder/'decision.json',dict(status='PASS_MACHINE_AUDIT',operation=op,attempt=attempt,proof_sha256=digest((folder/'proof.json').read_bytes()),at=now()));accepted.append(dict(operation=op,attempt=attempt,proof=str((folder/'proof.json').relative_to(job/'audits')),proof_sha256=digest((folder/'proof.json').read_bytes())))
            state=job/'U05_SEQUENCE.json';temporary=job/'sequence.tmp';temporary.write_bytes(canonical(dict(operations=list(STEPS),accepted=accepted)));os.replace(temporary,state)
            progress('MACHINE_AUDIT_PASSED',slice=i+1,total=len(STEPS),operation=op)
            timings.append(dict(operation=op,elapsed_seconds=time.monotonic()-operation_started,machine_pair_seconds=read(folder/'evaluations.json')['elapsed_seconds']))
        preservation=assert_inventory(Path(bound['job']),protected);t05=read(job/'u05_t05/t05_run.json')['facts'];comparison=read(job/'u05_t05/t05_compare.json')['facts'];native_result=read(job/'data_output/pcb_kicad_write.json');plots=read(job/'data_output/pcb_gerber_export.json');predicates=sum(len(read(job/'audits'/f'{i+1:03d}/proof.json')['checks']) for i in range(len(STEPS)))
        runtime=dict(elapsed_seconds=time.monotonic()-started,operations=timings,measurement='Cold fresh managed U05 with two fresh machine processes per gate; no predecessor execution')
        fresh(job/'PERFORMANCE.json',runtime)
        artifacts={str(q.relative_to(job)):digest(q.read_bytes()) for q in job.rglob('*') if q.is_file()};fresh(job/'U05_CHECKPOINT.json',dict(schema='pcb-u05-final-checkpoint/1',predecessor=bound,operations=list(STEPS),accepted=accepted,files=artifacts));receipt=dict(status='PASS_U05_RETAINED_CONTINUATION_EXPORT',job=str(job),checkpoint_sha256=digest((job/'U05_CHECKPOINT.json').read_bytes()),retained_U04_gates=len(bound['retained_operations']),new_native_gates=len(STEPS),machine_audits=len(STEPS),machine_predicates=predicates,human_or_agent_observations=0,predecessor_preservation=preservation,T05=t05,comparison=comparison,performance=runtime,kicad=native_result['board'],gerbers=str(Path(plots['exports']['candidate']['F.Cu']).parent),prefix_execution='RETAINED_VERIFIED_NOT_REEXECUTED',owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',electrical_manufacturing='NOT_ESTABLISHED',rendering='NOT_REQUESTED');fresh(job/'U05_RECEIPT.json',receipt)
        markdown=f'''U05 completed: verified retained U04 → fresh T05 → actual native KiCad/Gerber export/reparse.\n\nAll {len(STEPS)} new native gates and deterministic machine audits passed ({predicates} predicates; zero human/agent observations). The {len(bound['retained_operations'])} U04 gates were verified as retained evidence and were not rerun.\n\nT05: {t05['grown']} routes received additive spindle treatment; {t05['kept']} kept. Added {comparison['added_area_mm2']:.9f} mm²; removed zero. Complete source/contact coverage, bounded radius replay, simultaneous checks and actual Gerber hard-gap checks passed. Every U04 native node remains preserved.\n\n[KiCad candidate]({receipt['kicad']}) · [Gerbers]({receipt['gerbers']}) · [Receipt]({job/'U05_RECEIPT.json'})\n\nOwner PENDING_USER; independent NOT_RUN: CHANNEL_UNAVAILABLE; electrical/manufacturing NOT_ESTABLISHED; rendering NOT_REQUESTED. All {preservation['files']} U04 files remain unchanged by inventory, SHA-256, bytes and mtime.\n''';fresh_bytes(job/'U05_REPORT.md',markdown.encode());progress('COMPLETE_MACHINE_AUDITED_U05_EXPORT',**receipt);print(markdown,flush=True);return 0
    except BaseException as error:
        if job:
            failure=dict(status='HALTED',task_outcome='INCOMPLETE_NOT_ACCEPTED',job=str(job),error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),dispositions=[dict(operation=s,status='PASS' if s in [a['operation'] for a in accepted] else 'FAIL' if s==op else 'NOT_RUN') for s in STEPS],owner='PENDING_USER',rendering='NOT_REQUESTED');fresh(job/'HALTED.json',failure)
            if not (latch/(key+'.json')).exists():fresh(latch/(key+'.json'),failure)
        else:failure=dict(status='HALTED',error=str(error),owner='PENDING_USER')
        progress('HALTED',**{k:v for k,v in failure.items() if k!='status'});return 2
    finally:lock.close()

def main():
    if sys.argv[1:2]==['--machine-evaluate']:
        if len(sys.argv)!=4:raise ValueError('U05_MACHINE_EVALUATION_ARGUMENTS_REQUIRED')
        print(json.dumps(dict(pid=os.getpid(),proof=evaluate(Path(sys.argv[2]),sys.argv[3])),sort_keys=True,allow_nan=False));return 0
    p=argparse.ArgumentParser();p.add_argument('--u04-job',required=True,type=Path);p.add_argument('--state-dir',type=Path);p.add_argument('--reference',type=Path);a=p.parse_args()
    if not a.u04_job.is_absolute():p.error('--u04-job requires the explicit absolute completed U04 job path')
    return run(a.u04_job,a.state_dir,a.reference)
if __name__=='__main__':raise SystemExit(main())
