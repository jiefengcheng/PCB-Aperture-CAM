"""Prepare or explicitly execute ONE fresh legacy T02→T05 checkpoint experiment.

Preflight/prepare never execute a growth stage. This is diagnostic custody of a
saved legacy T04 checkpoint, not adoption into the connected production route.
Historical stage producers remain named and bound; no version allowlist changes.
Every future stage runs construction and two fresh reconstruction workers, with
all current checks and canonical proof parity. No export, rendering or delivery.
For the separately selected T05-only outer certificate route, use
tools/t05_certified_checkpoint.py; this repeat-build audit route is unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
MODES=('construct','1','2')
NAMES=('source.json','source_snapshot','runtime','t01.json','t03.json','t04.json',
    'RAW_WIDTH_CHECKPOINT.json','LEGACY_REFERENCE_JOB.json','input_inventory.json',
    'PIN_SEPARATION_POLICY.json','STORAGE_ENCODING.json','SOURCE_ASSEMBLY_BINDING.json',
    'HOLE_ACCEPTANCE_SNAPSHOT.json','T04_SETTINGS_SNAPSHOT.json','CLEARANCE_SNAPSHOT.json',
    'REMEDY_POLICY_SNAPSHOT.json','T04_PASS_SCHEDULE.json')
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
load=lambda path:json.loads(Path(path).read_bytes())


def audit_prefix(prefix,expected_t04):
    """Read-only, exact retained geometry/audit custody; not current-code replay."""
    from src.u05_board.store import ReadOnlyStore
    from src.stage_abi.scene import validate_scene
    prefix=Path(prefix)
    if not(prefix/'LEGACY_REFERENCE_JOB.json').is_file():raise ValueError('LEGACY_CHECKPOINT_REQUIRED')
    if sha(prefix/'t04.json')!=expected_t04:raise ValueError('T04_CHECKPOINT_HASH_CHANGED')
    source=load(prefix/'source.json');producer=load(prefix/'PRODUCER_BINDING.json')
    old_producer=sha(prefix/'PRODUCER_BINDING.json')
    if producer['source_binding_sha256']!=sha(prefix/'source.json'):raise ValueError('SOURCE_BINDING_CHANGED')
    history=prefix/'REUSED_LEGACY_BINDING.json'
    prior_map={}
    if history.exists():
        inputs={Path(k).resolve():v for k,v in producer.get('job_inputs',{}).items()}
        if inputs.get(history.resolve())!=sha(history):raise ValueError('LEGACY_HISTORY_UNBOUND')
        record=load(history)['original']
        if record['source_sha256']!=source['source_ref']['sha256']:raise ValueError('LEGACY_HISTORY_SOURCE_CHANGED')
        prior_map=record['stage_producer_bindings']
    producers={}
    for stage in ('t01','t03','t04'):
        proofs=[load(prefix/'audits'/stage/(mode+'.json'))for mode in MODES]
        expected_producer=prior_map.get(stage,old_producer)
        if not(proofs[0]==proofs[1]==proofs[2] and proofs[0]['status']=='PASS'
            and proofs[0]['stage']==stage and proofs[0]['candidate_sha256']==sha(prefix/(stage+'.json'))
            and proofs[0]['source_sha256']==source['source_ref']['sha256']
            and proofs[0]['producer_binding_sha256']==expected_producer):
            raise ValueError('RETAINED_STAGE_PROOF_CHANGED:'+stage)
        producers[stage]=expected_producer
    store=ReadOnlyStore(prefix/'runtime')
    scene=validate_scene(store,load(prefix/'t04.json')['output_scene_ref'])
    if scene['source_sha256']!=source['source_ref']['sha256']:raise ValueError('T04_SOURCE_CHANGED')
    for row in scene['objects']:
        for field in ('original_ref','geometry_ref'):store.get(row[field],kind='geometry')
    raw=store.get(source['source_ref'],kind='gerber-source')
    if raw!=(prefix/'source_snapshot/top.art.gbr').read_bytes():raise ValueError('RAW_SOURCE_CHANGED')
    pin=load(prefix/'PIN_SEPARATION_POLICY.json')
    if pin['working_source_sha256']!=scene['source_sha256']:raise ValueError('PIN_SOURCE_CHANGED')
    if(prefix/'SOURCE_ASSEMBLY_BINDING.json').exists():
        assembly=load(prefix/'SOURCE_ASSEMBLY_BINDING.json')
        if assembly['assembled_source_sha256']!=scene['source_sha256']or any(sha(n)!=h for n,h in assembly['files'].items()):
            raise ValueError('SOURCE_ASSEMBLY_CUSTODY_CHANGED')
    return dict(status='PASS_RETAINED_LEGACY_CUSTODY',t04_sha256=expected_t04,
        source_sha256=scene['source_sha256'],old_producer_sha256=old_producer,
        retained_stage_producers=producers,objects=len(scene['objects']),
        pin_intent='UNDECLARED'if pin['declaration']is None else'DECLARED',
        scope='New diagnostic legacy T02/T05 computation; no connected-profile adoption or acceptance promotion')


def prepare(prefix,expected_t04,*,parent=None):
    from tools.pcb_workspace import require_storage
    from tools.preflight import verify_manifest
    from src.gerber_u05.guard import seal
    from src.gerber_u05.performance import capture,capture_t05
    from src.gerber_u05 import pipeline as p
    started=time.perf_counter();work=require_storage().resolve();verify_manifest()
    prefix=Path(prefix).resolve(strict=True)
    if not prefix.is_relative_to(work):raise ValueError('CHECKPOINT_MUST_BE_ON_LACIE')
    custody=audit_prefix(prefix,expected_t04)
    parent=Path(parent)if parent is not None else work/'evidence/t02_t05_prepared'
    if not parent.resolve().is_relative_to(work):raise ValueError('JOB_MUST_BE_ON_LACIE')
    parent.mkdir(parents=True,exist_ok=True)
    job=Path(tempfile.mkdtemp(prefix='prepared.',dir=parent));run=job/'legacy';run.mkdir()
    files={}
    for name in (*NAMES,*(f'audits/{s}/{m}.json'for s in ('t01','t03','t04')for m in MODES)):
        src=prefix/name
        if not src.exists():continue
        dst=run/name;dst.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['/bin/cp','-cR'if src.is_dir()else'-c',str(src),str(dst)],check=True)
        if dst.is_file():
            if sha(dst)!=sha(src):raise ValueError('CHECKPOINT_COPY_CHANGED:'+name)
            files[str(dst.relative_to(job))]=sha(dst)
    files['legacy/source_snapshot/top.art.gbr']=sha(run/'source_snapshot/top.art.gbr')
    capture(run);capture_t05(run)
    p.save(run/'CHECKPOINT_CUSTODY.json',dict(custody,retained_prefix=str(prefix),copied_files=files))
    seal(run,'diagnostic-legacy-t04-certified-timing/1')
    plan=dict(schema='pcb-cam/t02-t05-prepared-run/1',status='PREPARED_NOT_EXECUTED',
        job=str(job),run=str(run),source_checkpoint=str(prefix),custody=custody,
        producer_binding_sha256=sha(run/'PRODUCER_BINDING.json'),custody_sha256=sha(run/'CHECKPOINT_CUSTODY.json'),
        setup_seconds=time.perf_counter()-started,stages=['t02','t05'],modes=list(MODES),
        shared_performance=True,t05_certificates=True,configured_t05_memo_bytes=512*1024**2,
        constructor='SOURCE_SPINDLE; no 160-route measurement bank',elapsed_time_cutoff=None,
        export='NOT_REQUESTED',full_board_execution='NOT_STARTED',
        command=f'tools/Run_T02_T05_Checkpoint.command --execute-plan "{job/"RUN_PLAN.json"}"')
    p.save(job/'RUN_PLAN.json',plan)
    (job/'RUN_PLAN.sha256').write_text(sha(job/'RUN_PLAN.json')+'\n')
    return plan


def check_job(plan):
    from src.gerber_u05.guard import producer_files
    from src.gerber_u05.performance import t05_profile,parsed_reference_cache
    from src import hole_acceptance
    from tools.pcb_workspace import require_storage
    work=require_storage().resolve()
    job=Path(plan['job']).resolve();run=Path(plan['run']).resolve()
    if not job.is_relative_to(work)or run!=job/'legacy':raise ValueError('PREPARED_JOB_OUTSIDE_LACIE')
    if sha(job/'RUN_PLAN.json')!=(job/'RUN_PLAN.sha256').read_text().strip()or load(job/'RUN_PLAN.json')!=plan:
        raise ValueError('PREPARED_PLAN_CHANGED')
    if plan['stages']!=['t02','t05']or plan['modes']!=list(MODES)or plan['elapsed_time_cutoff']is not None:
        raise ValueError('PREPARED_EXECUTION_SCOPE_CHANGED')
    run=Path(plan['run']);producer=load(run/'PRODUCER_BINDING.json')
    if sha(run/'PRODUCER_BINDING.json')!=plan['producer_binding_sha256']or sha(run/'CHECKPOINT_CUSTODY.json')!=plan['custody_sha256']:
        raise ValueError('PREPARED_JOB_BINDING_CHANGED')
    if set(producer['files'])!={str(q)for q in producer_files()}or any(sha(q)!=h for q,h in producer['files'].items()):
        raise ValueError('PREPARED_PRODUCER_CHANGED_REPREPARE_REQUIRED')
    if sha(run/'source.json')!=producer['source_binding_sha256']or any(sha(q)!=h for q,h in producer['job_inputs'].items()):
        raise ValueError('PREPARED_INPUT_CHANGED')
    imported=load(run/'CHECKPOINT_CUSTODY.json')
    if any(sha(run.parent/q)!=h for q,h in imported['copied_files'].items()):raise ValueError('PREPARED_CUSTODY_CHANGED')
    if t05_profile(run)is None:raise ValueError('PREPARED_T05_OPTION_MISSING')
    parsed_reference_cache(run,'t02')
    hole_acceptance.bind(run)
    return run


def worker(plan_path,stage,mode):
    from src.gerber_u05 import pipeline as p,worker as engine
    from tools.pcb_workspace import require_storage
    from importlib.metadata import version
    import shapely
    p.configure();plan=load(plan_path)
    if stage not in ('t02','t05')or mode not in MODES:raise ValueError('CHECKPOINT_WORKER_SCOPE_INVALID')
    run=check_job(plan)
    runtime=load(ROOT/'contracts/gerber_u05/runtime.json')
    if {k:version(k)for k in runtime['packages']}!=runtime['packages']or shapely.geos_version_string!=runtime['geos']:
        raise ValueError('PINNED_RUNTIME_CHANGED')
    work=require_storage().resolve();allowed=run.parent.resolve()
    def fence(event,args):
        if event=='open'and isinstance(args[0],(str,bytes,os.PathLike)):
            q=Path(os.fsdecode(args[0])).resolve()
            if q.is_relative_to(work)and not q.is_relative_to(allowed)and q!=work/'STORAGE_IDENTITY.json':
                raise PermissionError('CHECKPOINT_WORKER_OUTSIDE_FRESH_JOB:'+str(q))
    sys.addaudithook(fence);os.environ['U05_WORKER_MODE']=mode
    for previous in engine.ORDER[:engine.ORDER.index(stage)]:
        for m in MODES:
            proof=load(run/'audits'/previous/(m+'.json'))
            if proof['status']!='PASS'or proof['candidate_sha256']!=sha(run/(previous+'.json')):
                raise ValueError('PREDECESSOR_PROOF_CHANGED')
    started=time.perf_counter();value=engine.compute(run,stage);path=run/(stage+'.json')
    if mode=='construct':p.save(path,value)
    elif p.canonical(value)!=path.read_bytes():raise ValueError('FRESH_STAGE_PROOF_DIFFERS:'+stage)
    proof=dict(status='PASS',stage=stage,candidate_sha256=sha(path),source_sha256=plan['custody']['source_sha256'],
        producer_binding_sha256=plan['producer_binding_sha256'],summary=value['summary'])
    p.save(run/'audits'/stage/(mode+'.json'),proof);check_job(plan)
    print(json.dumps(dict(status='PASS',stage=stage,mode=mode,seconds=time.perf_counter()-started,proof_sha256=sha(path))),flush=True)


def execute(plan_path):
    started=time.perf_counter()
    from src.gerber_u05 import pipeline as p
    from tools.pcb_workspace import require_storage
    require_storage();plan=load(plan_path);job=Path(plan['job']);check_job(plan)
    if Path(plan_path).resolve()!=(job/'RUN_PLAN.json').resolve():raise ValueError('EXACT_PREPARED_PLAN_REQUIRED')
    if plan['status']!='PREPARED_NOT_EXECUTED':raise ValueError('PREPARED_PLAN_REQUIRED')
    # Exclusive latch: failed or partial work is retained, never resumed.
    with (job/'EXECUTION_STARTED.json').open('x')as f:json.dump(dict(plan_sha256=sha(plan_path)),f)
    stages={};logs=job/'logs';logs.mkdir()
    try:
        for stage in ('t02','t05'):
            began=time.perf_counter();batches=[]
            for modes in (('construct',),('1','2')):
                start=time.perf_counter();jobs=[]
                for mode in modes:
                    stream=(logs/f'{stage}_{mode}.log').open('x')
                    child=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-B',__file__,'--worker',str(plan_path),stage,mode],
                        cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1'),stdout=stream,stderr=subprocess.STDOUT)
                    jobs.append((mode,child,stream))
                results=[]
                for mode,child,stream in jobs:
                    code=child.wait();stream.close();results.append(dict(mode=mode,returncode=code))
                batches.append(dict(modes=list(modes),seconds=time.perf_counter()-start,results=results))
                if any(r['returncode']for r in results):raise ValueError('CHECKPOINT_WORKER_FAILED:'+stage)
            proofs=[load(Path(plan['run'])/'audits'/stage/(mode+'.json'))for mode in MODES]
            if not proofs[0]==proofs[1]==proofs[2]:raise ValueError('PAIRED_STAGE_PROOFS_DIFFER:'+stage)
            stages[stage]=dict(seconds=time.perf_counter()-began,batches=batches,proof_sha256=proofs[0]['candidate_sha256'])
            print(json.dumps(dict(stage=stage,**stages[stage])),flush=True)
        p.save(job/'RESULT.json',dict(status='PASS',scope='Diagnostic legacy T02/T05 only',stages=stages,
            execution_seconds=time.perf_counter()-started,setup_seconds=plan['setup_seconds'],
            complete_seconds=plan['setup_seconds']+time.perf_counter()-started,
            proofs_match=True,pin_intent=plan['custody']['pin_intent'],export='NOT_RUN'))
    except BaseException as error:
        p.save(job/'HALTED.json',dict(error=repr(error),completed=stages,remaining='NOT_RUN',seconds=time.perf_counter()-started));raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix-run',type=Path);parser.add_argument('--t04-sha256')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--execute-plan',type=Path)
    mode.add_argument('--worker',nargs=3,metavar=('PLAN','STAGE','MODE'))
    args=parser.parse_args()
    if args.worker:worker(Path(args.worker[0]),*args.worker[1:]);return
    if args.execute_plan:execute(args.execute_plan);return
    if args.prefix_run is None or not args.prefix_run.is_absolute()or args.t04_sha256 is None:
        parser.error('Explicit absolute --prefix-run and exact --t04-sha256 required')
    from tools.pcb_workspace import require_storage
    work=require_storage().resolve()
    if not args.prefix_run.resolve().is_relative_to(work):parser.error('Prefix must be in prepared LaCie workspace')
    print(json.dumps(prepare(args.prefix_run,args.t04_sha256)if args.prepare else audit_prefix(args.prefix_run,args.t04_sha256),indent=2))


if __name__=='__main__':main()
