#!/usr/bin/env python3
"""Ordinary-English whole-board facade; embedded client uses local files only."""
import argparse,json,sys,time,uuid
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.pcb_c01_operator import Operator,scoped,sha,decode,now,publish,encode
from tools.t01_route_client import Client
from tools import t01_crop_jobs as jobs
from tools import t01_board_jobs as board_jobs

class BoardClient(Client):
    def call(self,name,arguments,*,timeout=180):
        budgets=decode((ROOT/'contracts/operator/t01_board.json').read_bytes())['native_timeout_seconds'];timeout=max(timeout,budgets.get(name,budgets['default'])+120)
        rid=self.submit(name,arguments);started=time.monotonic();next_notice=started+20
        while time.monotonic()-started<timeout:
            health_check=getattr(self,'health_check',None)
            if health_check:health_check()
            if(self.replies/(rid+'.json')).exists():return self.receive(rid)
            if time.monotonic()>=next_notice:
                phase='render'if name=='render_compare'else'verify'if name=='render_verify'else None
                paths=sorted((self.root/'render_output').glob(phase+'-*.progress.json'))if phase else []
                progress=decode(paths[-1].read_bytes())if paths else None
                print(json.dumps(dict(status='NATIVE_WORK_IN_PROGRESS',operation=name,elapsed_seconds=round(time.monotonic()-started),native_progress=progress)),flush=True);next_notice=time.monotonic()+20
            time.sleep(.1)
        raise TimeoutError('NATIVE_CHANNEL_UNAVAILABLE_OR_INCOMPLETE: retained request '+rid)

class BoardOperator(Operator):
    steps=tuple(decode((ROOT/'contracts/operator/t01_board.json').read_bytes())['operations'])
    complete_status='COMPLETE_AUDITED_BOARD_SEQUENCE'
    def __init__(self,binding):
        super().__init__(binding);self.client=BoardClient(self.client.root/'agent_setup.json','LocalCode')
    def validate_tools(self,names):
        if names!={*self.steps,'board.submit','native_route.info','native_route.verify_receipt','native_route.audit'}:raise ValueError('BOUND_BOARD_PROFILE_REQUIRED')
    def start_board(self,**inputs):
        if self.state_path.exists():raise ValueError('TASK_ALREADY_STARTED')
        result=self.client.call('board.submit',inputs)
        if result['status']!='BOARD_INPUTS_BOUND':raise ValueError('BOARD_INTAKE_FAILED')
        return self.start()
    def summary_details(self,index,raw):
        result=dict(total_slices=len(self.steps),evidence_scope='Entire supported native F.Cu source. No crop/image. Owner PENDING_USER; independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.')
        op=self.steps[index]
        if op in('pcb_board_scope','pcb_board_verify'):result.update(bounds_mm=raw['bounds_mm'],source_objects=raw['source_objects'],canonical_sites=raw['canonical_sites'],source_occurrences=raw['source_occurrences'])
        if op=='render_verify':result['measurements']=raw['audits']
        if op in('pcb_export_controls','render_controls','pcb_board_verify'):result['controls']=raw['controls']
        return result
    def delivery(self):
        result=super().delivery();root=self.client.root;out=root/'data_output';write=decode((out/'pcb_kicad_write.json').read_bytes());export=decode((out/'pcb_gerber_export.json').read_bytes());render=decode((root/'render_output/render.json').read_bytes())
        paths={write['board']:write['board_sha256'],**export['output_sha256'],**{str(root/'render_output'/name):h for name,h in render['files'].items()}}
        for p in [root/'RECEIPT.json',root/'data_board/verified.json',root/'render_output/verification.json',root/'render_output/controls.json']:
            paths[str(p)]=sha(p.read_bytes())
        for path,h in paths.items():
            blob=scoped(path).read_bytes()
            if sha(blob)!=h:raise ValueError('FINAL_BOARD_ARTIFACT_CHANGED')
            result['files'].append(dict(path=path,sha256=h,bytes=len(blob),format=Path(path).suffix))
        png=root/'render_output/comparison.png';page=root/'render_output/index.html';gerber=out/'candidate/gerbers/board-F_Cu.gbr'
        discovery=decode((root/'RECEIPT.json').read_bytes())['facts']
        markdown=f'''Whole-board T01 completed: {discovery['canonical_sites']} canonical sites and {discovery['aliases']} source occurrences. All 21 native slices and separate observation audits passed. Frozen results, shared clearance and T02–T05 remain unchanged. Owner review is pending.\n\n![Whole-board candidate KiCad and Gerber overview]({png})\n\n[Complete side-by-side tile review]({page}) · [KiCad]({write['board']}) · [F.Cu Gerber]({gerber})\n\nThe overview is for navigation; every native detail tile is separately audited. Independent, electrical and manufacturing approval are not established.'''
        result.update(status=self.complete_status,native_slices=21,observation_audits=21,scope='Whole supported F.Cu board; complete source coverage and tiled native review',display=str(png),html=str(page),kicad=write['board'],gerber=str(gerber),ready_markdown=markdown,report_text=markdown,next_action='Return ready_markdown unchanged and stop; no extra probes.')
        return result

def stdout_result(result):
    """Compact terminal projection only; every artifact remains in custody JSON."""
    if result.get('mode')=='REPORT_ONLY_RETAINED_EVIDENCE':
        from tools.t01_board_completion import compact
        return compact(result)
    if not result.get('terminal'):return result
    manifest=scoped(Path(result['evidence'])/'operator_ui/terminal.json')
    state=decode((manifest.parent/'current.json').read_bytes())
    digest=sha(manifest.read_bytes())
    if state['status']!='COMPLETE' or state['terminal']!=str(manifest) or state['terminal_sha256']!=digest:
        raise ValueError('FINAL_CUSTODY_MANIFEST_CHANGED')
    projected={k:v for k,v in result.items()if k!='files'}
    projected.update(file_count=len(result['files']),custody_manifest=str(manifest),custody_manifest_sha256=digest)
    return projected

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','review','reject','finalize']);p.add_argument('observation',nargs='?',default='');p.add_argument('--job',type=Path);p.add_argument('--kicad');p.add_argument('--gerber');p.add_argument('--kicad-attachment');p.add_argument('--gerber-attachment');a=p.parse_args();operator=None;job=None;started=now()
    def journal(result,code):
        if operator:
            operator.ui.mkdir(exist_ok=True);folder=operator.ui/'client_calls';folder.mkdir(exist_ok=True);publish(folder/(uuid.uuid4().hex+'.json'),encode(dict(started_at=started,completed_at=now(),action=a.action,observation=a.observation,returncode=code,result=result)))
    try:
        if a.job is not None and a.action!='finalize':raise ValueError('JOB_SELECTION_ONLY_FOR_REPORT_FINALIZATION')
        if a.action=='finalize':
            if a.observation or a.kicad or a.gerber or a.kicad_attachment or a.gerber_attachment:raise ValueError('FINALIZATION_TAKES_NO_NEW_INPUTS_OR_AUDITS')
            from tools.t01_board_completion import finalize,compact
            selected=a.job if a.job is not None else jobs.current()[0]
            print(json.dumps(compact(finalize(selected)),sort_keys=True));return 0
        with jobs.exclusive():
            try:
                if a.action=='start':
                    attached={k:v for k,v in [('kicad',a.kicad_attachment),('gerber',a.gerber_attachment)]if v is not None};rows,blobs=board_jobs.inputs(a.kicad,a.gerber,attachments=attached)
                    jobs.launcher_ready();job,row=board_jobs.allocate(rows,blobs);binding=jobs.launch(job);operator=BoardOperator(binding);result=operator.start_board(**row['staged'])
                else:
                    if a.kicad or a.gerber or a.kicad_attachment or a.gerber_attachment:raise ValueError('INPUT_REBINDING_FORBIDDEN')
                    selected,row=jobs.current()
                    if row.get('task_scope')=='full-board-export-only':raise ValueError('EXPORT_ONLY_JOB_USE_EXPORT_OPERATOR')
                    if row.get('task_scope')!='full-board':raise ValueError('CROP_JOB_USE_CROP_OPERATOR')
                    if jobs.outcome(selected)=='HALTED':
                        if a.action=='reject':raise ValueError('TASK_HALTED: retained failure; no retries; '+str(selected))
                        from tools.t01_board_completion import finalize,compact
                        print(json.dumps(compact(finalize(selected)),sort_keys=True));return 0
                    completed=jobs.outcome(selected)=='COMPLETE';binding=jobs.binding(selected,require_live=not completed)
                    if completed:
                        cached=BoardOperator(binding);result=cached.terminal_result(cached.state())
                    else:job=selected;operator=BoardOperator(binding);result=operator.review(a.observation,a.action=='reject')
                if job:
                    result['job']=str(job);journal(result,0)
                    if jobs.outcome(job)=='COMPLETE':jobs.stop(job)
            except Exception as error:
                if job:jobs.halt(job,error)
                raise
        print(json.dumps(stdout_result(result),sort_keys=True));return 0
    except Exception as error:
        result=dict(status='HALTED',next_action='REPORT_AND_STOP',error=str(error),task_outcome='INCOMPLETE_NOT_ACCEPTED',report_text='Whole-board T01 stopped at a required gate. Report the retained error and stop; no retries, crop substitution, source edits or acceptance promotion.',evidence=str(job)if job else None)
        if operator:
            operator.ui.mkdir(exist_ok=True)
            if not(operator.ui/'failure.json').exists():publish(operator.ui/'failure.json',encode(dict(result,at=now())))
        journal(result,2)
        if job is not None:
            # The native failure stays immutable. Only a fully verified export
            # prefix and a retained pixel-tolerance rejection may finish as a
            # separate report with FAIL findings; no native call is repeated.
            until=time.monotonic()+5
            while not (job/'native/adapter_stopped.json').exists() and time.monotonic()<until:time.sleep(.1)
            try:
                from tools.t01_board_completion import finalize,compact
                completed=finalize(job)
            except (ValueError,OSError,KeyError,TypeError) as completion_error:
                result['report_finalization_error']=str(completion_error)
            else:
                print(json.dumps(compact(completed),sort_keys=True));return 0
        print(json.dumps(result,sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
