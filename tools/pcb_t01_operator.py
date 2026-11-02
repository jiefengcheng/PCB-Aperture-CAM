#!/usr/bin/env python3
"""Ordinary-English crop facade; stdlib transport, native data/T01/render ABIs."""
import argparse,json,sys,uuid
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.pcb_c01_operator import Operator,scoped,sha,decode,now,publish,encode
ACTIVE=ROOT/'out/operator_routes/t01_crop/current.json'

class CropOperator(Operator):
    steps=tuple(json.loads((ROOT/'contracts/operator/t01_crop.json').read_bytes())['operations'])
    complete_status='COMPLETE_AUDITED_CROP_SEQUENCE'
    def __init__(self,binding=ACTIVE):super().__init__(binding)
    def validate_tools(self,names):
        if names!={*self.steps,'crop.submit','native_route.info','native_route.verify_receipt','native_route.audit'}:raise ValueError('BOUND_CROP_PROFILE_REQUIRED')
    def start_crop(self,crop,kicad=None,gerber=None):
        if self.state_path.exists():raise ValueError('TASK_ALREADY_STARTED')
        args=dict(crop=crop)
        if kicad:args['kicad']=kicad
        if gerber:args['gerber']=gerber
        result=self.client.call('crop.submit',args)
        if result['status']!='CROP_INPUTS_BOUND':raise ValueError('CROP_INTAKE_FAILED')
        return self.start()
    def summary_details(self,index,raw):
        details=dict(total_slices=len(self.steps),evidence_scope='Current native slice only. Data ABI locates screenshot; source geometry supplies T01 copper. Owner PENDING_USER; independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.')
        op=self.steps[index]
        if op=='pcb_roi_locate':details.update(location=raw['best'],uncertainty_mm=raw['uncertainty_mm'],location_policy=raw['policy'],limits=raw['limits'])
        if op=='pcb_roi_verify':details.update(bounds_mm=raw['bounds_mm'],uncertainty_mm=raw['uncertainty_mm'],overlay=raw['overlay'])
        if op=='render_verify':details['measurements']=raw['audits']
        if op in ('pcb_export_controls','render_controls'):details['controls']=raw['controls']
        return details
    def delivery(self):
        result=super().delivery();out=self.client.root/'data_output';write=decode((out/'pcb_kicad_write.json').read_bytes());export=decode((out/'pcb_gerber_export.json').read_bytes())
        for path,h in {write['board']:write['board_sha256'],**export['output_sha256']}.items():
            blob=scoped(path).read_bytes()
            if sha(blob)!=h:raise ValueError('FINAL_EXPORT_CHANGED')
            result['files'].append(dict(path=path,sha256=h,bytes=len(blob),format='KiCad' if path.endswith('.kicad_pcb') else 'Gerber'))
        png=self.client.root/'render_output/comparison.png';html=self.client.root/'render_output/index.html';roi=self.client.root/'data_roi/roi_overlay.png';gerber=out/'candidate/gerbers/board-F_Cu.gbr'
        for p in (roi,self.client.root/'data_roi/roi_verified.json',self.client.root/'RECEIPT.json'):
            blob=scoped(p).read_bytes()
            result['files'].append(dict(path=str(p),sha256=sha(blob),bytes=len(blob),format='PNG' if p.suffix=='.png' else 'JSON'))
        markdown=f'''T01 completed for the located crop. All 21 native slices and separate observation audits passed. Frozen results and T02–T05 are unchanged. Owner review remains pending.\n\n![T01 KiCad and Gerber exports]({png})\n\n[KiCad]({write['board']}) · [Top copper Gerber]({gerber}) · [Interactive comparison]({html}) · [Crop location overlay]({roi})'''
        result.update(status=self.complete_status,native_slices=len(self.steps),observation_audits=len(self.steps),scope='Uploaded crop located by PCB data ABI; T01 only; fresh native exports and read-only display',display=str(png),html=str(html),kicad=write['board'],gerber=str(gerber),proof='Dynamic source coverage, full T01 reconstruction, native export/reparse, display fidelity and deliberate controls passed.',report_text=markdown,ready_markdown=markdown,next_action='Return ready_markdown unchanged as the final answer, with no further command or probes.')
        return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','review','reject']);parser.add_argument('observation',nargs='?',default='');parser.add_argument('--crop');parser.add_argument('--kicad');parser.add_argument('--gerber')
    parser.add_argument('--attachment',help='Current native attachment filename; use the app-staged project copy, never Desktop')
    parser.add_argument('--kicad-attachment');parser.add_argument('--gerber-attachment');a=parser.parse_args();operator=None;job=None;started=now()
    def journal(result,code):
        if operator:
            operator.ui.mkdir(exist_ok=True);folder=operator.ui/'client_calls';folder.mkdir(exist_ok=True)
            publish(folder/(uuid.uuid4().hex+'.json'),encode(dict(started_at=started,completed_at=now(),action=a.action,observation=a.observation,returncode=code,result=result)))
    from tools import t01_crop_jobs as jobs
    try:
        with jobs.exclusive():
            try:
                if a.action=='start':
                    if not a.crop and not a.attachment:raise ValueError('ACTUAL_ATTACHMENT_NAME_OR_PATH_REQUIRED')
                    attached={k:v for k,v in [('crop',a.attachment),('kicad',a.kicad_attachment),('gerber',a.gerber_attachment)] if v is not None}
                    if attached:rows,blobs=jobs.inputs(a.crop,a.kicad,a.gerber,attachments=attached)
                    else:rows,blobs=jobs.inputs(a.crop,a.kicad,a.gerber)
                    jobs.launcher_ready()
                    job,row=jobs.allocate(rows,blobs)
                    binding=jobs.launch(job)
                    operator=CropOperator(binding)
                    result=operator.start_crop(**row['staged'])
                else:
                    if a.crop or a.kicad or a.gerber or a.attachment or a.kicad_attachment or a.gerber_attachment:raise ValueError('INPUT_REBINDING_FORBIDDEN')
                    selected,row=jobs.current()
                    if row.get('task_scope')=='full-board-export-only':raise ValueError('EXPORT_ONLY_JOB_USE_EXPORT_OPERATOR')
                    if row.get('task_scope')=='full-board':raise ValueError('BOARD_JOB_USE_BOARD_OPERATOR')
                    if jobs.outcome(selected)=='HALTED':raise ValueError('TASK_HALTED: retained failure; no retry or probes; '+str(selected))
                    # A duplicate read of a completed delivery never writes into its job.
                    completed=jobs.outcome(selected)=='COMPLETE'
                    binding=jobs.binding(selected,require_live=not completed)
                    if completed:
                        cached=CropOperator(binding)
                        result=cached.terminal_result(cached.state())
                    else:
                        job=selected
                        operator=CropOperator(binding)
                        result=operator.review(a.observation,a.action=='reject')
                if job:
                    result['job']=str(job)
                    journal(result,0)
                    if jobs.outcome(job)=='COMPLETE':jobs.stop(job)
            except Exception as e:
                if job:jobs.halt(job,e)
                raise
        print(json.dumps(result,sort_keys=True));return 0
    except Exception as e:
        result=dict(status='HALTED',next_action='REPORT_AND_STOP',error=str(e),task_outcome='INCOMPLETE_NOT_ACCEPTED',report_text='The crop-driven T01 task stopped at a required gate. Report the retained error and stop. No retries, probes, replacement inputs or acceptance promotion.',evidence=str(job) if job else None)
        if operator:
            operator.ui.mkdir(exist_ok=True)
            if not (operator.ui/'failure.json').exists():publish(operator.ui/'failure.json',encode(dict(result,at=now())))
        journal(result,2);print(json.dumps(result,sort_keys=True));return 2

if __name__=='__main__':raise SystemExit(main())
