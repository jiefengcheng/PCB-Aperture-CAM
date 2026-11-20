"""One fresh full-board legacy T05 construction, then public certificate readers.

Uses an explicitly supplied, completed T04/T02 checkpoint. No T02 rerun, reference
arm, outer reconstruction, retry or resume. Historical custody is named rather
than relabelled as current source assembly admission. Export/connected finishing
are outside this diagnostic route.
"""
import argparse
import base64
import cProfile
import json
import os
from pathlib import Path
import pstats
import subprocess
import sys
import tempfile
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.stage_abi.store import canonical
from src.t05_outer_acceptance import file_bytes,expected_binding,verify_checkpoint_custody
from src.t05_outer_crypto import sha,Signer,_pipe

PROFILE=dict(schema='pcb-cam/t05-outer-checkpoint/1',stage='t05',
    construction_workers=1,public_readers=2,reconstruction_workers=0,
    reference_arms=0,reference_measurement_bank=False,memo_bytes=512*1024**2,
    scope='legacy-saved-t04-t02; source constructor; no connected finishing',elapsed_cutoff=None)
STAGES=('t01','t03','t04','t02')
MODES=('construct','1','2')
read=lambda path:json.loads(file_bytes(path))


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb')as stream:stream.write(canonical(value))


def retained_custody(prefix,t04_sha):
    """Original completed job and its actual stage/receipt/source custody only."""
    from tools.pcb_workspace import require_storage
    from src.u05_board.store import ReadOnlyStore
    from src.stage_abi.scene import validate_scene
    prefix=Path(prefix).resolve(strict=True)
    if not prefix.is_relative_to(require_storage().resolve()):raise ValueError('PREFIX_OUTSIDE_LACIE')
    job=prefix.parent;plan=read(job/'RUN_PLAN.json')
    if sha(file_bytes(job/'RUN_PLAN.json'))!=(job/'RUN_PLAN.sha256').read_text().strip():raise ValueError('PREFIX_PLAN_CHANGED')
    latch=read(job/'EXECUTION_STARTED.json')
    if latch['plan_sha256']!=sha(file_bytes(job/'RUN_PLAN.json')):raise ValueError('PREFIX_EXECUTION_LATCH_CHANGED')
    result=read(job/'RESULT.json');outer=read(job/'OUTER_TIMING.json')
    if result['status']!='PASS'or not result['proofs_match']or outer['returncode']!=0:raise ValueError('COMPLETED_PREFIX_REQUIRED')
    producer=sha(file_bytes(prefix/'PRODUCER_BINDING.json'))
    if producer!=plan['producer_binding_sha256']:raise ValueError('PREFIX_PRODUCER_CHANGED')
    source=read(prefix/'source.json');source_sha=source['source_ref']['sha256']
    named=dict(plan['custody']['retained_stage_producers'],t02=producer)
    hashes={}
    for stage in STAGES:
        stage_sha=sha(file_bytes(prefix/(stage+'.json')));hashes[stage]=stage_sha
        receipt_bytes=[file_bytes(prefix/'audits'/stage/(mode+'.json'))for mode in MODES]
        if not receipt_bytes[0]==receipt_bytes[1]==receipt_bytes[2]:raise ValueError('PREFIX_RECEIPT_BYTES_CHANGED:'+stage)
        receipts=[json.loads(raw)for raw in receipt_bytes]
        proof=receipts[0]
        if not(receipts[0]==receipts[1]==receipts[2]and proof['status']=='PASS'and proof['stage']==stage
               and proof['candidate_sha256']==stage_sha and proof['producer_binding_sha256']==named[stage]
               and proof['source_sha256']==source_sha):raise ValueError('PREFIX_RECEIPTS_CHANGED:'+stage)
    if hashes['t04']!=t04_sha or source_sha!=plan['custody']['source_sha256']:raise ValueError('PREFIX_SOURCE_OR_T04_CHANGED')
    store=ReadOnlyStore(prefix/'runtime')
    if store.get(source['source_ref'],kind='gerber-source')!=file_bytes(prefix/'source_snapshot/top.art.gbr'):raise ValueError('PREFIX_RAW_SOURCE_CHANGED')
    scene=validate_scene(store,read(prefix/'t02.json')['output_scene_ref'])
    if scene['source_sha256']!=source_sha:raise ValueError('PREFIX_SCENE_SOURCE_CHANGED')
    for row in scene['objects']:
        for field in ('original_ref','geometry_ref'):store.get(row[field],kind='geometry')
    pin=read(prefix/'PIN_SEPARATION_POLICY.json')
    if pin['working_source_sha256']!=source_sha:raise ValueError('PREFIX_PIN_SOURCE_CHANGED')
    for name,h in read(prefix/'PRODUCER_BINDING.json')['job_inputs'].items():
        if sha(file_bytes(name))!=h:raise ValueError('PREFIX_OPTION_CHANGED:'+name)
    evidence={str(job/name):sha(file_bytes(job/name))for name in('RUN_PLAN.json','RUN_PLAN.sha256','EXECUTION_STARTED.json','RESULT.json','OUTER_TIMING.json')}
    if(prefix/'SOURCE_ASSEMBLY_BINDING.json').exists():
        assembly=read(prefix/'SOURCE_ASSEMBLY_BINDING.json')
        if assembly['assembled_source_sha256']!=source_sha:raise ValueError('PREFIX_ASSEMBLY_SOURCE_CHANGED')
        for name,h in assembly['files'].items():
            if sha(file_bytes(name))!=h:raise ValueError('PREFIX_ASSEMBLY_CUSTODY_CHANGED')
            evidence[name]=h
    return dict(schema='verified-saved-t04-t02-custody/1',stage_producers=named,stage_sha256=hashes),evidence,dict(
        source_sha256=source_sha,pin_intent='UNDECLARED'if pin['declaration']is None else'DECLARED',
        source_checkpoint=str(prefix),t02_sha256=hashes['t02'],t04_sha256=hashes['t04'])


def prepare(prefix,t04_sha,*,parent=None):
    from tools.pcb_workspace import configure
    from tools.preflight import verify_manifest
    from tools.t02_t05_checkpoint import NAMES
    from src.gerber_u05.guard import seal,producer_files
    from src.gerber_u05.performance import capture,capture_t05,t05_profile
    started=time.perf_counter();work=configure().resolve();verify_manifest()
    custody,evidence,summary=retained_custody(prefix,t04_sha);prefix=Path(prefix).resolve()
    parent=Path(parent)if parent is not None else work/'evidence/t05_outer_full_board'
    if not parent.resolve().is_relative_to(work):raise ValueError('JOB_OUTSIDE_LACIE')
    parent.mkdir(parents=True,exist_ok=True)
    job=Path(tempfile.mkdtemp(prefix='certified.',dir=parent));run=job/'legacy';run.mkdir()
    copied={}
    names=(*NAMES,'t02.json',*(f'audits/{s}/{m}.json'for s in STAGES for m in MODES))
    for name in names:
        src=prefix/name
        if not src.exists():continue
        dst=run/name;dst.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['/bin/cp','-cR'if src.is_dir()else'-c',str(src),str(dst)],check=True)
        if src.is_file():
            if file_bytes(src)!=file_bytes(dst):raise ValueError('PREFIX_COPY_CHANGED:'+name)
            copied[name]=sha(file_bytes(dst))
    copied['source_snapshot/top.art.gbr']=sha(file_bytes(run/'source_snapshot/top.art.gbr'))
    capture(run);capture_t05(run);save(run/'T05_OUTER_ACCEPTANCE.json',PROFILE)
    seal(run,'diagnostic-legacy-t05-outer-certificate-consumption/1');t05_profile(run)
    expected=expected_binding(run,os.urandom(32).hex())
    expected.update(checkpoint_custody=custody,extra_reference_inputs=evidence)
    verify_checkpoint_custody(run,expected)
    save(job/'EXPECTED.json',expected)
    # Retain exact current producer bytes for future audit, without changing old jobs.
    code={}
    for path in producer_files():
        relative=path.relative_to(ROOT);dst=job/'producer_source'/relative
        dst.parent.mkdir(parents=True,exist_ok=True);raw=file_bytes(path);dst.write_bytes(raw)
        code[str(relative)]=sha(raw)
    save(job/'PRODUCER_SOURCE_MANIFEST.json',code)
    plan=dict(profile=PROFILE,job=str(job),run=str(run),prefix=summary,
        expected_sha256=sha(file_bytes(job/'EXPECTED.json')),copied_files=copied,
        producer_binding_sha256=sha(file_bytes(run/'PRODUCER_BINDING.json')),
        setup_seconds=time.perf_counter()-started,status='PREPARED_NOT_EXECUTED')
    save(job/'RUN_PLAN.json',plan)
    (job/'RUN_PLAN.sha256').write_text(sha(file_bytes(job/'RUN_PLAN.json'))+'\n')
    return plan


def check_job(job):
    from tools.pcb_workspace import configure
    from src.gerber_u05.performance import t05_profile
    job=Path(job).resolve();work=configure().resolve()
    if not job.is_relative_to(work):raise ValueError('JOB_OUTSIDE_LACIE')
    plan=read(job/'RUN_PLAN.json');run=job/'legacy';expected=read(job/'EXPECTED.json')
    if plan['profile']!=PROFILE or plan['job']!=str(job)or plan['run']!=str(run):raise ValueError('EXECUTION_PROFILE_CHANGED')
    if sha(file_bytes(job/'RUN_PLAN.json'))!=(job/'RUN_PLAN.sha256').read_text().strip():raise ValueError('EXECUTION_PLAN_CHANGED')
    if sha(file_bytes(job/'EXPECTED.json'))!=plan['expected_sha256']:raise ValueError('EXPECTED_BINDING_CHANGED')
    if read(run/'T05_OUTER_ACCEPTANCE.json')!=PROFILE:raise ValueError('OUTER_JOB_OPTION_CHANGED')
    if sha(file_bytes(run/'PRODUCER_BINDING.json'))!=plan['producer_binding_sha256']:raise ValueError('PRODUCER_BINDING_CHANGED')
    for name,h in plan['copied_files'].items():
        if sha(file_bytes(run/name))!=h:raise ValueError('COPIED_PREFIX_CHANGED:'+name)
    t05_profile(run);verify_checkpoint_custody(run,expected)
    return plan,expected


def construct(job,fd):
    from src.gerber_u05 import pipeline as p
    from src.t05_outer_acceptance import execute_once,publish
    from src.t05_outer_observer import Capture
    p.configure();plan,expected=check_job(job);job=Path(plan['job']);run=Path(plan['run'])
    if not(job/'EXECUTION_STARTED.json').exists():raise ValueError('EXECUTION_LATCH_REQUIRED')
    signer=Signer.from_inherited_fd(fd,file_bytes(job/'PUBLIC.pem'))
    install_fence(job,expected)
    os.environ['U05_WORKER_MODE']='construct';started=time.perf_counter()
    capture=Capture(run,job/'ACTUAL_READS.sqlite');profile=cProfile.Profile();profile.enable()
    value=execute_once(run,capture,expected)
    package,publication=publish(run,capture,value,signer,expected);del signer
    profile.disable();profile.dump_stats(str(job/'CONSTRUCTION.prof'))
    counts=pstats.Stats(profile).stats
    physical_calls=sum(v[1]for(f,l,n),v in counts.items()if n=='_check')
    save(job/'OUTER_CERTIFICATE.json',package);save(job/'PUBLICATION.json',publication)
    proof=dict(status='PASS',stage='t05',mode='construct',candidate_sha256=sha(file_bytes(run/'t05.json')),
        producer_binding_sha256=plan['producer_binding_sha256'],source_sha256=expected['source_sha256'],
        summary=value['summary'],physical_issuance_checks=physical_calls,pid=os.getpid(),seconds=time.perf_counter()-started)
    save(run/'audits/t05/construct.json',proof)
    print(json.dumps(proof),flush=True)


def install_fence(job,expected):
    """Only fresh-job writes; exact named historical custody files are read-only."""
    from tools.pcb_workspace import require_storage
    job=Path(job).resolve();work=require_storage().resolve()
    scratch=job/'tmp';scratch.mkdir(exist_ok=True)
    os.environ.update(TMPDIR=str(scratch),TMP=str(scratch),TEMP=str(scratch))
    tempfile.tempdir=str(scratch)
    named={Path(p).resolve()for p in expected.get('extra_reference_inputs',{})}
    named.add(work/'STORAGE_IDENTITY.json')
    def audit(event,args):
        if event!='open'or not isinstance(args[0],(str,bytes,os.PathLike)):return
        path=Path(os.fsdecode(args[0])).resolve()
        mode=args[1];flags=args[2]if len(args)>2 else 0
        writing=(isinstance(mode,str)and any(c in mode for c in 'wax+'))or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if writing and not path.is_relative_to(job):raise PermissionError('OUTER_WRITE_OUTSIDE_JOB:'+str(path))
        if path.is_relative_to(work)and not path.is_relative_to(job)and path not in named:
            raise PermissionError('OUTER_UNBOUND_HISTORICAL_READ:'+str(path))
    sys.addaudithook(audit)


def execute(job):
    started=time.perf_counter();job=Path(job).resolve();timings={}
    # Exclusive latch precedes all construction. A failure is never resumed.
    with(job/'EXECUTION_STARTED.json').open('xb')as stream:
        stream.write(canonical(dict(pid=os.getpid(),plan_sha256=sha(file_bytes(job/'RUN_PLAN.json')),
            utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))))
    try:
        plan,expected=check_job(job)
        signer=Signer.generate();public=signer.public;(job/'PUBLIC.pem').write_bytes(public)
        fd=signer.inherited_fd();env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1')
        point=time.perf_counter()
        with(job/'CONSTRUCTION.log').open('x')as log:
            child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--construct',str(job),str(fd)],
                cwd=ROOT,env=env,pass_fds=(fd,),stdout=log,stderr=subprocess.STDOUT)
            os.close(fd);save(job/'CONSTRUCTION_PID.json',dict(pid=child.pid));code=child.wait()
        timings['construction_process_wall_seconds']=time.perf_counter()-point;del signer
        if code:raise ValueError('T05_CONSTRUCTOR_FAILED:'+str(code))
        print(json.dumps(dict(event='CONSTRUCTION_COMPLETE',**timings)),flush=True)
        point=time.perf_counter();readers=[]
        anchor=canonical(dict(public_anchor=base64.b64encode(public).decode(),expected_sha256=plan['expected_sha256']))
        for mode in('1','2'):
            fd=_pipe(anchor);log=(job/('CONSUMER_'+mode+'.log')).open('x')
            child=subprocess.Popen([sys.executable,'-B',str(ROOT/'tools/t05_outer_acceptance.py'),str(job),str(fd),mode],
                cwd=ROOT,env=env,pass_fds=(fd,),stdout=log,stderr=subprocess.STDOUT)
            os.close(fd);readers.append((mode,child,log))
        codes=[]
        for mode,child,log in readers:
            code=child.wait();log.close();codes.append(code)
        timings['paired_public_reader_wall_seconds']=time.perf_counter()-point
        if any(codes):raise ValueError('T05_PUBLIC_READER_FAILED:'+str(codes))
        proofs=[read(job/('CONSUMER_'+mode+'.json'))for mode in('1','2')]
        actual_sha=sha(file_bytes(job/'legacy/t05.json'));construction=read(job/'legacy/audits/t05/construct.json')
        for proof in proofs:
            if not(proof['status']=='PASS'and proof['stage_sha256']==actual_sha==construction['candidate_sha256']
                   and proof['reconstruction_performed']is False and proof['physical_checks_repeated']==0
                   and not proof['forbidden_call_records']):raise ValueError('PUBLIC_PROOF_OR_STAGE_MISMATCH')
            if proof['counts'].get('local_containments',0)!=construction['summary']['grown']:raise ValueError('LOCAL_PROOF_COVERAGE')
        check_job(job)
        result=dict(status='PASS',acceptance_mode='ONE_CONSTRUCTION_PLUS_TWO_PUBLIC_CERTIFICATE_READERS',
            full_rebuilds=0,reference_arms=0,measurement_bank=False,memo_bytes=PROFILE['memo_bytes'],
            stage_sha256=actual_sha,summary=construction['summary'],public_readers=proofs,timings=timings,
            execution_seconds=time.perf_counter()-started,setup_seconds=plan['setup_seconds'],
            pin_intent=plan['prefix']['pin_intent'],export='NOT_RUN',connected_profile='NOT_RUN',
            scope=PROFILE['scope'],repeat_build_determinism='SEPARATE_AUDIT_NOT_RUN')
        save(job/'RESULT.json',result);print(json.dumps(result),flush=True)
    except BaseException as error:
        save(job/'HALTED.json',dict(status='HALTED',error=repr(error),traceback=traceback.format_exc(),
            completed_timings=timings,execution_seconds=time.perf_counter()-started,remaining='NOT_RUN; no retry/resume'))
        raise


def measure(job):
    job=Path(job).resolve();started=time.perf_counter()
    # This is the external stopwatch, including coordinator startup and storage readiness.
    with(job/'RUN.log').open('x')as log:
        child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--execute',str(job)],
            cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1'),stdout=log,stderr=subprocess.STDOUT)
        save(job/'COORDINATOR_PID.json',dict(pid=child.pid));code=child.wait()
    wall=time.perf_counter()-started;setup=read(job/'RUN_PLAN.json')['setup_seconds']
    save(job/'OUTER_TIMING.json',dict(returncode=code,execution_wall_seconds=wall,prepared_setup_seconds=setup,
        complete_wall_seconds=wall+setup))
    return code


def main():
    parser=argparse.ArgumentParser(description=__doc__);m=parser.add_mutually_exclusive_group(required=True)
    m.add_argument('--prepare',type=Path);m.add_argument('--execute',type=Path);m.add_argument('--measure',type=Path)
    m.add_argument('--construct',nargs=2);parser.add_argument('--t04-sha256')
    args=parser.parse_args()
    if args.prepare:
        if not args.prepare.is_absolute()or args.t04_sha256 is None:parser.error('Explicit absolute prefix and --t04-sha256 required')
        print(json.dumps(prepare(args.prepare,args.t04_sha256)),flush=True)
    elif args.construct:construct(Path(args.construct[0]),int(args.construct[1]))
    elif args.execute:execute(args.execute)
    else:sys.exit(measure(args.measure))


if __name__=='__main__':main()
