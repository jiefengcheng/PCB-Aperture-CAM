#!/usr/bin/env python3
"""Exact retained-U05 append-only C03 width qualification; local machine audits."""
import argparse,json,sys,os,subprocess,time,uuid,traceback
from pathlib import Path
from datetime import datetime,timezone
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.c03_width_qualification import Gates,STEPS,code_files,inventory,read,fresh,verify_attempt
from src.stage_abi.store import canonical,digest
from src.c03_width_continuation import upstream_u05
from tools.pcb_workspace import configure,WORK


def worker(root,op,mode):
    try:
        configure();root=Path(root).absolute()
        if '..' in root.parts or not root.is_relative_to(WORK):raise ValueError('C03_LACIE_NATIVE_WORKER_REQUIRED')
        gate=Gates(root);gate.require_operation(op)
        if mode=='execute':
            value=gate.execute(op);gate.wc.verify_inputs();fresh(root/'operations'/(op+'.json'),value);result=dict(status='PASS_NATIVE_OPERATION',operation=op,output=str(root/'operations'/(op+'.json')),output_sha256=digest(canonical(value)),facts=value['facts'])
        else:
            value=read(root/'operations'/(op+'.json'));proof=gate.audit(op,value);result=dict(status='PASS_MACHINE_REEVALUATION',pid=os.getpid(),proof=proof)
        print(json.dumps(result,sort_keys=True),flush=True);return 0
    except BaseException as e:
        print(json.dumps(dict(status='HALTED',error=str(e),traceback=traceback.format_exc())),flush=True);return 2


def run(predecessor,output):
    configure();predecessor=Path(predecessor).absolute();output=Path(output).absolute()
    if not predecessor.is_relative_to(WORK)or not output.is_relative_to(WORK)or output.exists():raise ValueError('C03_FRESH_LACIE_CONTINUATION_REQUIRED')
    from src.crop_circle_sources import verify_assets
    from tools.t01_native_route import require_native
    identity=require_native()
    from src.c03_width_profile import marker
    from src.trace_first_pipeline import frozen_fingerprint
    profile=marker();spec=profile['contract'];receipt=(ROOT/spec['predecessor']['receipt']).absolute()
    if predecessor!=receipt.parent or digest(receipt.read_bytes())!=spec['predecessor']['receipt_sha256']:raise ValueError('C03_EXACT_AUTHORIZED_U05_REQUIRED')
    assets=verify_assets();entries=read(ROOT/'out/lacie_work/evidence/c03_baseline_reconciliation_20261104T083840Z/FINAL_CUSTODY_CHECK.json')['protected_freezes'];freezes=[frozen_fingerprint(ROOT,e)for e in entries]
    fingerprint=code_files();input_key=digest(canonical(dict(predecessor=str(predecessor),contract_sha256=profile['contract_sha256'])))
    for p in output.parent.glob('*/native/FAILURE.json'):
        start=read(p.parent/'START.json')
        if start.get('input_key')==input_key and start.get('producer_files')==fingerprint:raise ValueError('C03_SAME_INPUT_IMPLEMENTATION_FAILURE_LATCH')
    output.mkdir();root=output/'native';root.mkdir();u05=upstream_u05(predecessor);u4=Path(read(u05/'U05_START.json')['predecessor']['root']);protected=read(predecessor/'START.json')['predecessor_inventories'] if (predecessor/'START.json').is_file() else {};protected=dict(protected);protected[str(predecessor.parent if predecessor.name=='native' else predecessor)]=inventory(predecessor.parent if predecessor.name=='native' else predecessor);protected.setdefault(str(u4.parent),inventory(u4.parent));protected.setdefault(str(u05),inventory(u05));start=dict(schema='c03-append-width-start/1',predecessor=str(predecessor),input_key=input_key,producer_files=fingerprint,native_identity=identity,assets=assets,protected_freezes=entries,predecessor_inventories=protected,scope='Append-only new complete source groups; all U05 native nodes and prior qualified widths protected',rendering='NOT_REQUESTED')
    fresh(root/'START.json',start);fresh(root/'C03_WIDTH_RECOVERY.json',profile);
    from src.c03_baseline_custody import marker as baseline_marker
    fresh(root/'C03_BASELINE_CUSTODY.json',baseline_marker());fresh(root/'C03_INPUT_FAMILY.json',read(u4/'C03_INPUT_FAMILY.json'));fresh(output/'job.json',dict(task_scope='c03-width-recovery-continuation',inputs=dict(kicad=dict(sha256=spec['source_sha256'])),crop=dict(sha256=spec['crop_sha256']),input_evidence='RETAINED_QUALIFIED_U05; no fresh raw-directory intake claim'))
    (root/'attempts').mkdir();(root/'audits').mkdir();accepted=[];started=time.monotonic();start_sha256=digest((root/'START.json').read_bytes())
    def process(args,folder):
        folder.mkdir(parents=True,exist_ok=True);command=[sys.executable,'-B',str(ROOT/'tools/pcb_c03_width_recovery.py'),'--worker','--root',str(root),'--operation',op,'--mode',args]
        out=(folder/'stdout.json').open('xb');err=(folder/'stderr.log').open('xb');before=time.monotonic();p=subprocess.Popen(command,cwd=ROOT,stdout=out,stderr=err);notice=before+20
        while p.poll()is None:
            if time.monotonic()>=notice:print(json.dumps(dict(status='NATIVE_WORK_IN_PROGRESS',operation=op,mode=args,elapsed_seconds=round(time.monotonic()-before),job=str(output))),flush=True);notice=time.monotonic()+20
            time.sleep(.1)
        out.close();err.close();fresh(folder/'command.json',dict(argv=command,pid=p.pid,returncode=p.returncode,elapsed_seconds=time.monotonic()-before))
        if p.returncode:raise ValueError('C03_NATIVE_WORKER_FAILED:'+str(folder)+':'+(folder/'stdout.json').read_text()[-2500:])
        return read(folder/'stdout.json')
    try:
        for ordinal,op in enumerate(STEPS,1):
            if code_files()!=fingerprint or digest((root/'START.json').read_bytes())!=start_sha256:raise ValueError('C03_WIDTH_PRODUCER_CHANGED')
            for a in accepted:
                verify_attempt(root/'attempts'/a['attempt']);proofpath=root/'audits'/a['proof']
                if digest(proofpath.read_bytes())!=a['proof_sha256'] or digest((root/'operations'/(a['operation']+'.json')).read_bytes())!=a['native_result_sha256']:raise ValueError('C03_PRIOR_MACHINE_AUDIT_CHANGED')
            print(json.dumps(dict(status='NATIVE_OPERATION',slice=ordinal,total=len(STEPS),operation=op,job=str(output))),flush=True)
            name=f'{ordinal:03d}-{op}';folder=root/'attempts'/name;result=process('execute',folder)
            files={str(p.relative_to(folder)):digest(p.read_bytes())for p in folder.rglob('*')if p.is_file()};fresh(folder/'receipt.json',dict(tool=op,attempt_id=name,status='PASS',files=files,completed_at=datetime.now(timezone.utc).isoformat()))
            audits=root/'audits'/f'{ordinal:03d}';rows=[process('audit',audits/str(i))for i in (1,2)]
            proof=rows[0]['proof']
            if rows[0]['pid']==rows[1]['pid']or proof!=rows[1]['proof']or proof['status']!='PASS'or proof['operation']!=op or proof['start_sha256']!=start_sha256 or not proof['checks'] or not all(p['passed']is True for p in proof['checks']) or proof['native_result_sha256']!=result['output_sha256'] or result['output_sha256']!=digest((root/'operations'/(op+'.json')).read_bytes()):raise ValueError('C03_TWO_FRESH_PROCESS_MACHINE_PROOFS_REQUIRED')
            fresh(audits/'proof.json',rows[0]['proof']);accepted.append(dict(operation=op,attempt=name,proof=f'{ordinal:03d}/proof.json',proof_sha256=digest((audits/'proof.json').read_bytes()),native_result_sha256=result['output_sha256']))
            fresh(root/'checkpoints'/f'{ordinal:03d}.json',dict(accepted=accepted,operations=list(STEPS)));print(json.dumps(dict(status='MACHINE_AUDIT_PASSED',operation=op,slice=ordinal,checks=len(rows[0]['proof']['checks']))),flush=True)
        # This is a native-family qualification receipt, never owner acceptance.
        coverage=read(root/'operations/coverage_compare.json')['coverage'];export=read(root/'data_output/pcb_gerber_export.json');actual=read(root/'data_output/pcb_gerber_verify.json')['facts'];checkpoint=root/'checkpoints/014.json'
        result=dict(schema='c03-width-recovery-native-receipt/1',status='PASS_APPEND_ONLY_C03_WIDTH_RECOVERY',job=str(output),native_root=str(root),retained_predecessor=str(predecessor),upstream_u05=str(u05),retained_prefix='RETAINED_VERIFIED_NOT_REEXECUTED',new_native_gates=len(STEPS),machine_audits=len(STEPS),machine_predicates=sum(len(read(root/'audits'/a['proof'])['checks'])for a in accepted),human_or_agent_observations=0,coverage=coverage,actual_export=actual,kicad=str(root/'data_output/candidate/board.kicad_pcb'),gerbers=export['exports']['candidate'],checkpoint_sha256=digest(checkpoint.read_bytes()),producer_files=fingerprint,inputs_verified_unchanged=True,elapsed_seconds=time.monotonic()-started,blocked=['T01:C028','T02:R304','T02:R305'],full_original_recovery='NOT_ESTABLISHED',owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',electrical_manufacturing='NOT_ESTABLISHED',rendering='NOT_REQUESTED')
        fresh(root/'C03_WIDTH_RECOVERY_RECEIPT.json',result);print(json.dumps(dict(status=result['status'],receipt=str(root/'C03_WIDTH_RECOVERY_RECEIPT.json'),met=coverage['met'],unmet=coverage['unmet'],machine_audits=len(STEPS),elapsed_seconds=result['elapsed_seconds'])),flush=True);return 0
    except BaseException as e:
        failure=dict(status='HALTED',error=str(e),traceback=traceback.format_exc(),accepted=accepted,dispositions=[dict(operation=s,status='PASS'if any(a['operation']==s for a in accepted)else'FAIL'if s==op else'NOT_RUN')for s in STEPS],remaining='NOT_RUN',frozen_evidence='PRESERVED',owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE')
        fresh(root/'FAILURE.json',failure);print(json.dumps(failure),flush=True);return 2


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--predecessor','--u05-job',dest='u05_job',type=Path);p.add_argument('--output',type=Path);p.add_argument('--worker',action='store_true');p.add_argument('--root',type=Path);p.add_argument('--operation',choices=STEPS);p.add_argument('--mode',choices=['execute','audit']);a=p.parse_args()
    if a.worker:raise SystemExit(worker(a.root,a.operation,a.mode))
    if a.u05_job is None or a.output is None:p.error('--u05-job and --output are required')
    raise SystemExit(run(a.u05_job,a.output))
