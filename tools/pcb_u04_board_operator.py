#!/usr/bin/env python3
"""Local Code: one explicit directory and one factual observation per U04 gate."""
import sys,argparse,json,uuid,shlex
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.pcb_t01_board_operator import BoardOperator,BoardClient,stdout_result
from tools.pcb_c01_operator import decode,encode,publish,sha,now,scoped
from tools import t01_crop_jobs as jobs,u04_board_jobs as u04_jobs
from src.u03_board.selection import for_root


class U04Client(BoardClient):
    def call(self,name,arguments,*,timeout=180):
        budgets=decode((ROOT/'contracts/operator/u04_board.json').read_bytes())['native_timeout_seconds']
        return super().call(name,arguments,timeout=max(timeout,budgets.get(name,budgets['default'])+120))


class U04Operator(BoardOperator):
    steps=tuple(decode((ROOT/'contracts/operator/u04_board.json').read_bytes())['operations'])
    complete_status='COMPLETE_AUDITED_U04_SEQUENCE'
    machine=False
    def __init__(self,binding):
        super().__init__(binding)
        from src.u04_board.custody import operation_steps
        self.steps=operation_steps(self.client.root)
        self.client=U04Client(self.client.root/'agent_setup.json','LocalCode')
    def validate_tools(self,names):
        from src.u04_board.custody import operation_steps
        self.steps=operation_steps(self.client.root)
        return super().validate_tools(names)
    def summary_details(self,index,raw):
        result=dict(total_slices=len(self.steps),rendering='NOT_REQUESTED',evidence_scope='Fresh T01 → exact retain-valid-paths T03 → source-bound T04 → whole-rectangle/inclusive T02; full native junction paths and geometric parallel groups, fixed paths and uniform width 1..1.5×; no electrical/manufacturing or owner approval.')
        # The deliberate unsupported-English control returns result: null.
        if raw is not None and 'controls' in raw:result['controls']=raw['controls']
        return result

    def delivery(self):
        root=self.client.root;receipt=decode((root/'U04_RECEIPT.json').read_bytes());cp=root/'U04_EXPORT_CHECKPOINT.json'
        if receipt['status']!='PASS_FRESH_U04_EXPORT' or receipt['operations']!=list(self.steps) or receipt['checkpoint_sha256']!=sha(cp.read_bytes()):raise ValueError('U04_COMPLETE_CHECKPOINT_REQUIRED')
        paths={str(cp):sha(cp.read_bytes()),str(root/'U04_RECEIPT.json'):sha((root/'U04_RECEIPT.json').read_bytes())}
        paths.update({str(scoped(root/name)):h for name,h in decode(cp.read_bytes())['files'].items()})
        # Content-addressed native evidence is part of the final delivery,
        # including every solver report and reconstructed source/part page.
        for artifact in (root/'runtime/artifacts').iterdir():
            if not artifact.is_file() or ':' not in artifact.name:raise ValueError('U04_RUNTIME_ARTIFACT_INVALID')
            paths[str(scoped(artifact))]=artifact.name.split(':',1)[1]
        job=decode((root.parent/'job.json').read_bytes());mp=scoped(job['input_directory']);manifest=decode(mp.read_bytes())
        if sha(mp.read_bytes())!=job['input_directory_sha256'] or job['task_scope']!='u04-board':raise ValueError('U04_JOB_BINDING_CHANGED')
        paths[str(mp)]=sha(mp.read_bytes());companions=[]
        for row in manifest['files']:
            if row['kind']!='companion':continue
            source=scoped(mp.parent/'raw_inputs'/row['relative_path']);blob=source.read_bytes()
            if sha(blob)!=row['sha256'] or len(blob)!=row['bytes']:raise ValueError('U04_COMPANION_CHANGED')
            target=scoped(root/'excluded_companions'/row['relative_path']);target.parent.mkdir(parents=True,exist_ok=True);publish(target,blob)
            paths[str(target)]=row['sha256'];companions.append(str(target))
        write=decode((root/'data_output/pcb_kicad_write.json').read_bytes());gerber=root/'data_output/candidate/gerbers/board-F_Cu.gbr';t03=decode((root/'u02_t03/t03_inspect.json').read_bytes())['facts'];width=decode((root/'u03_t04/t04_verify.json').read_bytes())['facts'];admission=decode((root/'u03_t04/t04_inspect.json').read_bytes())['facts']
        rectangle=decode((root/'u04_t02/t02_run.json').read_bytes())['facts']
        proofs=sorted((root/'audits').glob('machine-*/proof.json'))
        if self.machine:
            if len(proofs)!=len(self.steps) or list((root/'operator_ui').glob('review-*.json')):raise ValueError('U04_MACHINE_COUNT_OR_FALSE_OBSERVATION')
            machine=root/'MACHINE_RECEIPT.json';publish(machine,encode(dict(schema='pcb-u04-machine-receipt/1',operations=list(self.steps),proofs={str(p.relative_to(root)):sha(p.read_bytes()) for p in proofs},checkpoint_sha256=sha(cp.read_bytes()),human_or_agent_observations='NOT_RUN',owner='PENDING_USER')));paths[str(machine)]=sha(machine.read_bytes())
        elif proofs:raise ValueError('U04_AUDIT_MODE_SUBSTITUTION')
        raw_directory=decode(Path(decode((root.parent/'INTAKE_RECEIPT.json').read_bytes())['request']).read_bytes())['input_directory']
        selection=for_root(root)
        if receipt.get('selection')!=selection:raise ValueError('U04_DELIVERY_SELECTION_CHANGED')
        scope_text=(f"Scope image: {job['crop']['provided_path']}; verified source window {selection['bounds_mm']} mm; location {selection['location_status']}. Complete features only; outside/boundary paths and complete crossing groups stay unchanged. Full original board remains clearance context and the export base.\n\n" if selection else '')
        command=shlex.join([str(ROOT/'tools/Run_U04_Board.command'),'--input-dir',raw_directory,*(['--crop',job['crop']['provided_path']] if selection else [])])
        if selection:paths[str(Path(job['crop']['path']))]=job['crop']['sha256']
        crop_english=f", using crop image {job['crop']['provided_path']}," if selection else ','
        count=len(self.steps);audit=f'{count} deterministic machine audits; zero human/agent observations'if self.machine else f'{count} distinct agent observations'
        markdown=scope_text+f'''U04 completed: fresh T01 → T03 → T04 → T02 → native KiCad/Gerber exports. All {count} native gates and {audit} passed.\n\nT03: NO_CHANGE_REQUIRED. All {t03['trace_occurrences']} native trace occurrences were retained at their original widths; {t03['affected_pairs']} trace/land pairs were assessed across {t03['trace_pages']} trace pages. This T03 family supports valid unchanged paths; automatic whole-board displacement is not qualified.\n\nT04: {width['changed_routes']} routes widened, {width['changed_native_parts']} native parts; {width['groups']} source-bound groups. Fixed paths, uniform scales 1..1.5×; nominal/envelope reconstruction and final-neighbor upper proofs passed. Coordinate-wise model maximum only. {admission['classifications'].get('KEEP_FULLY_COVERED',0)} complete paths remain protected by exact full-coverage proofs.\n\nT02: {rectangle['grown']} whole rectangles grew; {rectangle['kept']} retained; {rectangle['inclusive_fills']} connected inclusive fills. Disposition: {rectangle['disposition']}. Original 1.25× per-axis caps, finite-surface checks and complete ordinary/inclusive reconstruction passed. Trace paths and widths remain unchanged by T02.\n\n[Rectangle deltas]({root/'u04_t02/t02_compare.json'}) · [Source-bound width deltas]({root/'u03_t04/t04_compare.json'}) · [KiCad]({write['board']}) · [F.Cu Gerber]({gerber}) · [All native Gerbers]({gerber.parent}) · [Evidence checkpoint]({cp})\n\n{len(companions)} unmatched Gerbers remain unchanged excluded companions ([copies]({root/'excluded_companions'})); their layer/geometry is NOT_ESTABLISHED. Rendering NOT_REQUESTED. Owner PENDING_USER; independent NOT_RUN: CHANNEL_UNAVAILABLE; electrical/manufacturing NOT_ESTABLISHED. Changed traces are serialized as source-bound filled copper contours at the existing file grid; the source paths and nominal widths remain in the T04 evidence. No later U stage ran.\n\nTerminal: `{command}`. Local Code: “Run fresh U04 (T01 → T03 → T04 → T02), without rendering{crop_english} from {raw_directory}. Review every native gate and return audited candidate KiCad/Gerber exports and evidence. Stop on failure; keep owner review pending.”'''
        report=root/'U04_REPORT.md';publish(report,markdown.encode());paths[str(report)]=sha(report.read_bytes());files=[]
        for name,h in paths.items():
            p=scoped(name);blob=p.read_bytes()
            if sha(blob)!=h:raise ValueError('U04_FINAL_ARTIFACT_CHANGED:'+name)
            files.append(dict(path=name,sha256=h,bytes=len(blob),format=p.suffix))
        return dict(status=self.complete_status,terminal=True,next_action='REPORT_AND_STOP',evidence=str(root),native_slices=count,machine_audits=count if self.machine else 0,observation_audits=0 if self.machine else count,selection=selection,render_operations=0,rendering='NOT_REQUESTED',files=files,kicad=write['board'],gerber=str(gerber),gerber_directory=str(gerber.parent),report=str(report),ready_markdown=markdown,report_text=markdown,owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',electrical_manufacturing='NOT_ESTABLISHED')


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','review','reject']);p.add_argument('observation',nargs='?',default='');p.add_argument('--input-dir');p.add_argument('--crop',type=Path);a=p.parse_args();job=None;operator=None
    try:
        u04_jobs.configure()
        if a.action=='start':
            if not a.input_dir or not Path(a.input_dir).is_absolute():raise ValueError('EXPLICIT_ABSOLUTE_INPUT_DIRECTORY_REQUIRED')
            job,row=u04_jobs.intake(a.input_dir,crop=a.crop)
            with jobs.exclusive():
                operator=U04Operator(jobs.launch(job));result=operator.start_board(**row['staged'])
        else:
            if a.input_dir or a.crop:raise ValueError('U04_INPUT_REBINDING_FORBIDDEN')
            with jobs.exclusive():
                selected,row=jobs.current()
                if row.get('task_scope')!='u04-board':raise ValueError('U04_JOB_REQUIRED')
                if jobs.outcome(selected)=='HALTED':raise ValueError('U04_HALTED_NO_RETRY:'+str(selected))
                complete=jobs.outcome(selected)=='COMPLETE';operator=U04Operator(jobs.binding(selected,require_live=not complete))
                if complete:result=operator.terminal_result(operator.state())
                else:job=selected;result=operator.review(a.observation,a.action=='reject')
        if operator:
            folder=operator.ui/'client_calls';folder.mkdir(exist_ok=True);publish(folder/(uuid.uuid4().hex+'.json'),encode(dict(at=now(),action=a.action,observation=a.observation,returncode=0,result=result)))
        if job:
            result['job']=str(job)
            if jobs.outcome(job)=='COMPLETE':jobs.stop(job)
        print(json.dumps(stdout_result(result),sort_keys=True));return 0
    except Exception as error:
        if job:jobs.halt(job,error)
        result=dict(status='HALTED',task_outcome='INCOMPLETE_NOT_ACCEPTED',error=str(error),evidence=str(job)if job else getattr(error,'evidence',None),owner='PENDING_USER',rendering='NOT_REQUESTED',dispositions=u04_jobs.dispositions(job),next_action='REPORT_AND_STOP; no retries or acceptance promotion')
        if operator and operator.ui.exists()and not(operator.ui/'failure.json').exists():publish(operator.ui/'failure.json',encode(result))
        print(json.dumps(result,sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
