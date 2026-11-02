#!/usr/bin/env python3
"""Explicit directory → fresh whole-board T01 → audited exports. Rendering absent."""
import argparse,json,sys,uuid
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.pcb_t01_board_operator import BoardOperator,stdout_result
from tools.pcb_c01_operator import scoped,sha,decode,encode,publish,now
from tools import t01_crop_jobs as jobs,t01_board_export_jobs as directory_jobs

class ExportOperator(BoardOperator):
    steps=tuple(decode((ROOT/'contracts/operator/t01_board_export.json').read_bytes())['operations'])
    complete_status='COMPLETE_AUDITED_BOARD_EXPORT_SEQUENCE'
    def validate_tools(self,names):
        if names!={*self.steps,'board.submit','native_route.info','native_route.verify_receipt','native_route.audit'}:raise ValueError('EXPORT_ONLY_PROFILE_REQUIRED')
    def summary_details(self,index,raw):
        result=super().summary_details(index,raw);result.update(total_slices=18,rendering='NOT_REQUESTED',evidence_scope='Explicit raw-input directory; fresh complete supported F.Cu source and audited native exports. No renderer or later-stage authority.')
        return result
    def delivery(self):
        root=self.client.root;out=root/'data_output';write=decode((out/'pcb_kicad_write.json').read_bytes());export=decode((out/'pcb_gerber_export.json').read_bytes());receipt=decode((root/'EXPORT_ONLY_RECEIPT.json').read_bytes())
        if receipt['status']!='PASS_FRESH_DIRECTORY_T01_EXPORT'or receipt['operations']!=list(self.steps)or receipt['rendering']!='NOT_REQUESTED':raise ValueError('COMPLETE_EXPORT_ONLY_RECEIPT_REQUIRED')
        if receipt['checkpoint']!=str(root/'EXPORT_CHECKPOINT.json')or sha((root/'EXPORT_CHECKPOINT.json').read_bytes())!=receipt['checkpoint_sha256']:raise ValueError('EXPORT_CHECKPOINT_CHANGED')
        job=decode((root.parent/'job.json').read_bytes());manifest=scoped(job['input_directory'])
        if sha(manifest.read_bytes())!=job['input_directory_sha256']:raise ValueError('INPUT_DIRECTORY_MANIFEST_CHANGED')
        inputs=decode(manifest.read_bytes());scope=decode((root/'data_board/verified.json').read_bytes());comparison=decode((root/'operator_ui/slice-10.json').read_bytes())['result']['facts']
        if (root/'render_output').exists()or(root/'pipeline_render_host.json').exists():raise ValueError('UNREQUESTED_RENDER_ARTIFACTS_PRESENT')
        paths={write['board']:write['board_sha256'],**export['output_sha256'],str(manifest):job['input_directory_sha256']}
        for p in(root/'EXPORT_ONLY_RECEIPT.json',root/'EXPORT_CHECKPOINT.json',root/'RECEIPT.json',root/'data_board/verified.json',root/'data_board/directory_inputs_verified.json'):
            paths[str(p)]=sha(p.read_bytes())
        for name,h in decode((root/'EXPORT_CHECKPOINT.json').read_bytes())['files'].items():paths[str(scoped(root/name))]=h
        files=[]
        for name,h in paths.items():
            path=scoped(name);blob=path.read_bytes()
            if sha(blob)!=h:raise ValueError('FINAL_EXPORT_ARTIFACT_CHANGED')
            files.append(dict(path=str(path),sha256=h,bytes=len(blob),format=path.suffix))
        companions=[]
        from src.pcb_data_abi.input_directory import regular_bytes
        for row in inputs['files']:
            if row['kind']!='companion':continue
            source=scoped(manifest.parent/'raw_inputs'/row['relative_path']);blob=regular_bytes(source)
            if sha(blob)!=row['sha256']or len(blob)!=row['bytes']:raise ValueError('EXCLUDED_COMPANION_CHANGED')
            target=scoped(root/'excluded_companions'/row['relative_path']);target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                if regular_bytes(target)!=blob:raise ValueError('EXCLUDED_COMPANION_COPY_CHANGED')
            else:publish(target,blob)
            entry=dict(path=str(target),sha256=row['sha256'],bytes=row['bytes'],format=target.suffix,status='EXCLUDED_COMPANION_UNCHANGED',geometry_qualification='NOT_ESTABLISHED; excluded')
            companions.append(entry);files.append(entry)
        page=root/'export_review.html';gerber=out/'candidate/gerbers/board-F_Cu.gbr'
        import html,os
        link=lambda p:html.escape(os.path.relpath(p,root),quote=True)
        layers=''.join(f'<li><a href="{link(path)}">{html.escape(Path(path).name)}</a></li>'for path in export['exports']['candidate'].values())
        companion_links=''.join(f'<li><a href="{link(row["path"])}">{html.escape(Path(row["path"]).name)}</a> — byte-identical; excluded from geometry qualification and T01</li>'for row in companions)
        body=f'''<!doctype html><meta charset="utf-8"><title>Whole-board T01 audited exports — no rendering</title><style>body{{font:17px system-ui;line-height:1.6;max-width:1000px;margin:40px auto;padding:0 20px;color:#152a40;background:#eef3f7}}</style><h1>Fresh whole-board T01: audited exports</h1><p>18 native slices and 18 separate observation audits passed. Rendering NOT_REQUESTED; no new images or renderer calls. Owner PENDING_USER; independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.</p><p>Input directory: {html.escape(inputs['provided_directory'])}. Every participating Gerber layer was verified against the raw KiCad source; excluded companions are reported separately. Complete F.Cu scope: {scope['canonical_sites']} canonical sites / {scope['source_occurrences']} occurrences / {scope['source_objects']} source objects.</p><p>Added copper {comparison['added_area_mm2']:.12f} mm²; removed {comparison['removed_area_mm2']:.12f} mm². The existing area-based clearance model and file-grid representation limits remain; this is not universal strict-distance, electrical or manufacturing approval.</p><p><a href="{link(write['board'])}">Candidate KiCad</a> · <a href="{link(manifest)}">Raw-input manifest</a> · <a href="EXPORT_ONLY_RECEIPT.json">Export receipt</a></p><ul>{layers}</ul>'''
        if companions:body+=f'<h2>Excluded companions</h2><p>{len(companions)} companion files are preserved unchanged. Their layer identity and geometry correspondence are NOT_ESTABLISHED; they are not included in the nine-layer native export claim.</p><ul>{companion_links}</ul>'
        publish(page,body.encode());files.append(dict(path=str(page),sha256=sha(page.read_bytes()),bytes=page.stat().st_size,format='HTML'))
        markdown=f'''Fresh whole-board T01 completed from the supplied raw directory: {scope['canonical_sites']} canonical sites and {scope['source_occurrences']} occurrences. All 18 native slices and 18 separate observation audits passed. Rendering was NOT_REQUESTED and no new rendering ran.

[Candidate KiCad]({write['board']}) · [Candidate F.Cu Gerber]({gerber}) · [All candidate Gerbers]({out/'candidate/gerbers'}) · [Export audit report]({page}) · [Raw-input manifest]({manifest})

Frozen results, shared clearance and T02–T05 remain unchanged. Owner review is pending; independent, electrical and manufacturing approval are not established.'''
        if companions:markdown+=f'\n\n{len(companions)} [excluded companion files]({root/"excluded_companions"}) were preserved byte-for-byte. Their layer identity and geometry correspondence are NOT_ESTABLISHED; the nine-layer native export does not qualify those companions.'
        return dict(status=self.complete_status,terminal=True,next_action='REPORT_AND_STOP',files=files,native_slices=18,observation_audits=18,rendering='NOT_REQUESTED',render_operations=0,fresh_source_construction=True,input_directory=inputs['provided_directory'],input_manifest=str(manifest),excluded_companions=companions,kicad=write['board'],gerber=str(gerber),gerbers=str(out/'candidate/gerbers'),html=str(page),owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',electrical_manufacturing='NOT_ESTABLISHED',evidence=str(root),ready_markdown=markdown,report_text=markdown)

def main():
    from contextlib import nullcontext
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['start','review','reject']);parser.add_argument('observation',nargs='?',default='');parser.add_argument('--input-dir',type=Path);args=parser.parse_args();operator=None;job=None;started=now()
    def journal(result,code):
        if operator:
            folder=operator.ui/'client_calls';folder.mkdir(exist_ok=True);publish(folder/(uuid.uuid4().hex+'.json'),encode(dict(started_at=started,completed_at=now(),action=args.action,observation=args.observation,returncode=code,result=result)))
    try:
        with (nullcontext()if args.action=='start'else jobs.exclusive()):
            try:
                if args.action=='start':
                    if args.input_dir is None:raise ValueError('EXPLICIT_INPUT_DIRECTORY_REQUIRED: start --input-dir <raw KiCad/Gerber directory>')
                    job,row=directory_jobs.native_intake(args.input_dir)
                    with jobs.exclusive():
                        operator=ExportOperator(jobs.launch(job));result=operator.start_board(**row['staged'])
                else:
                    if args.input_dir is not None:raise ValueError('INPUT_DIRECTORY_REBINDING_FORBIDDEN')
                    selected,row=jobs.current()
                    if(selected/'TERMINAL_RUN.json').exists():raise ValueError('TERMINAL_MACHINE_JOB: use its returned machine-audit report; the observation facade cannot review this mode')
                    if row.get('task_scope')!=directory_jobs.SCOPE:raise ValueError('EXPORT_ONLY_JOB_REQUIRED: use the matching operator for the current job')
                    if jobs.outcome(selected)=='HALTED':raise ValueError('TASK_HALTED: retained failure; no retries; '+str(selected))
                    completed=jobs.outcome(selected)=='COMPLETE';binding=jobs.binding(selected,require_live=not completed)
                    if completed:
                        cached=ExportOperator(binding);result=cached.terminal_result(cached.state())
                    else:job=selected;operator=ExportOperator(binding);result=operator.review(args.observation,args.action=='reject')
                if job:
                    result['job']=str(job);journal(result,0)
                    if jobs.outcome(job)=='COMPLETE':jobs.stop(job)
            except Exception as error:
                if job:jobs.halt(job,error)
                raise
        print(json.dumps(stdout_result(result),sort_keys=True));return 0
    except Exception as error:
        result=dict(status='HALTED',task_outcome='INCOMPLETE_NOT_ACCEPTED',next_action='REPORT_AND_STOP',error=str(error),error_details=getattr(error,'details',None),evidence=str(job)if job else getattr(error,'evidence',None),rendering='NOT_REQUESTED',report_text='Fresh directory T01 export stopped at a required gate. Retain the error and stop; no retries, rendering, input substitutions or acceptance promotion.')
        if operator:
            operator.ui.mkdir(exist_ok=True)
            if not(operator.ui/'failure.json').exists():publish(operator.ui/'failure.json',encode(dict(result,at=now())))
        journal(result,2);print(json.dumps(result,sort_keys=True));return 2

if __name__=='__main__':raise SystemExit(main())
