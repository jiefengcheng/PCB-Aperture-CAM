#!/usr/bin/env python3
"""Separate scoped T02 qualification on a retained T01; never runs T04.

All gates stop on failure. A new evidence directory is mandatory; no resume.
"""
import argparse,copy,json,re,sys,traceback
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.scoped_land_recovery import (permission,validate_machine_prefix,rectangle_scene,
    construct_rectangles,verify_recovery,ScopedRectangleExport,check_export_surfaces,verify_native_scope)
from src.t01_canonical_custody import producers
from src.stage_abi.contracts import StageABIError
from src.prepared_land_scene import PreparedLandScene
from src.pcb_data_abi.service import fresh,read,record
from src.pcb_data_abi import gerber

STEPS=['retained_T01_prefix','ordinary_T02_construction','fresh_T02_reconstruction','T02_corruption_controls',
       'pcb_kicad_write','pcb_kicad_verify','pcb_gerber_export','pcb_gerber_verify','pcb_export_controls',
       'additional_export_controls','actual_target_full_surface','exact_scope_and_coverage']


def run(base,prefix):
    from tools.pcb_workspace import configure,WORK
    configure();base=base.absolute();prefix=prefix.absolute()
    if not base.is_relative_to(WORK):raise ValueError('SCOPED_LAND_LACIE_REQUIRED')
    base.mkdir(exist_ok=False);store=ArtifactStore(base/'runtime');source=ArtifactStore(prefix/'runtime')
    bound=producers();record(base/'PRODUCER_FILES.json',bound)
    ledger=[];service=None;recovery=None;state={}
    def gate(name,fn):
        if producers()!=bound:raise ValueError('SCOPED_LAND_PRODUCER_CHANGED')
        print(name,flush=True)
        from src.stage_abi.preparation import worker_resources
        with worker_resources('scoped-land:'+digest(canonical(bound))+':'+name):value=fn()
        if producers()!=bound:raise ValueError('SCOPED_LAND_PRODUCER_CHANGED')
        record(base/(name+'.json'),value)
        ledger.append(dict(operation=name,status='PASS',result_sha256=digest(canonical(value))))
        record(base/('progress_'+str(len(ledger)).zfill(2)+'.json'),ledger)
        return value
    try:
        receipt=read(prefix/'RECEIPT.json');manifest=read(prefix/'data_board/source_manifest.json')
        host=read(prefix/'pipeline_data_host.json')
        gate(STEPS[0],lambda:validate_machine_prefix(prefix))
        def construct():
            ref,scene=rectangle_scene(source,receipt,manifest,store)
            return construct_rectangles(store,ref,scene)
        recovery=gate(STEPS[1],construct)
        gate(STEPS[2],lambda:verify_recovery(store,read(base/(STEPS[1]+'.json'))))
        def controls():
            reports=[]
            for name in ['cap','missing_target','protected','proof','fill']:
                bad=copy.deepcopy(read(base/(STEPS[1]+'.json')))
                if name=='cap':bad['candidate']['decisions'][0]['shape']['factors'][0]=1.25001
                elif name=='missing_target':bad['candidate']['decisions'].pop()
                elif name=='protected':bad['candidate']['protected_source_refs']={}
                elif name=='proof':bad['verification']['reconstructed_targets']=1
                else:bad['candidate']['inclusive_candidates'].append({'status':'MERGED'})
                record(base/('control_'+name+'.json'),bad)
                try:verify_recovery(store,bad)
                except (ValueError,StageABIError)as error:
                    expected={'cap':'RECTANGLE_SCALE_OUT_OF_SCOPE','missing_target':'COVERAGE_MISMATCH',
                              'protected':'PREDECESSOR_CHANGED','proof':'SCOPED_LAND_RECONSTRUCTION_CHANGED',
                              'fill':'INCLUSIVE_RECONSTRUCTION_MISMATCH'}[name]
                    if getattr(error,'code',str(error))!=expected:raise
                    reports.append(dict(name=name,error=str(error),expected=expected,status='PASS_EXPECTED_REJECTION'))
                else:raise ValueError('SCOPED_LAND_CONTROL_NOT_REJECTED:'+name)
            return dict(passed=True,controls=reports)
        gate(STEPS[3],controls)
        service=ScopedRectangleExport(host,base/'data_output',store,recovery)
        for name in STEPS[4:9]:gate(name,lambda name=name:service.dispatch(name))
        def extra_controls():
            path=Path(read(service.out/'pcb_gerber_export.json')['exports']['candidate']['F.Cu']);blob=path.read_bytes()
            reports=[]
            clear=service.out/'controls/clear_polarity.gbr'
            if b'%LPD*%'not in blob:raise ValueError('SCOPED_CLEAR_CONTROL_TOKEN_MISSING')
            fresh(clear,blob.replace(b'%LPD*%',b'%LPC*%',1))
            try:service.plot_check(clear)
            except ValueError as error:
                if not str(error).startswith('SCOPED_LAND_CLEAR_POLARITY_UNSUPPORTED'):raise
                reports.append(dict(name='clear_polarity',status='PASS_EXPECTED_REJECTION',error=str(error)))
            else:raise ValueError('SCOPED_CLEAR_CONTROL_NOT_REJECTED')
            measured,_,parsed=service.plot_check()
            for row in measured['rectangle_targets']:
                i=row['plot_index'];which=sum(isinstance(o,gerber.go.Region)for o in parsed.objects[:i])
                span=list(re.finditer(rb'G36\*.*?G37\*',blob,re.S))[which]
                missing=service.out/'controls'/('missing_rectangle_'+row['source_id'].rsplit(':',2)[1]+'.gbr')
                fresh(missing,blob[:span.start()]+blob[span.end():])
                try:service.plot_check(missing)
                except ValueError as error:
                    if not str(error).startswith('U04_RECTANGLE_POLYGON_NOT_IN_GERBER:'+row['source_id']):raise
                    reports.append(dict(name='missing_exact_rectangle',source_id=row['source_id'],status='PASS_EXPECTED_REJECTION',error=str(error)))
                else:raise ValueError('SCOPED_RECTANGLE_CONTROL_NOT_REJECTED')
            return dict(passed=True,controls=reports)
        gate(STEPS[9],extra_controls)
        def surface():
            measured,actual,_=service.plot_check();original_scene=source.get_json(receipt['scene_ref'],kind='scene')
            originals={r['source_id']:r for r in original_scene['objects']};meta={r['id']:r for r in manifest['objects']}
            circles=[];rectangles=[];aliases=set()
            for d in service.decisions:
                sid=d['source_id'];aliases.update(d['aliases'])
                name=sid.rsplit(':',2)[1]+'-'+sid.rsplit(':',1)[1]+'.wkb'
                circles.append(dict(id=sid,original=from_wkb(source.get(originals[sid]['original_ref'],kind='geometry')),
                    nominal=from_wkb(source.get(service.candidate['replacements'][sid],kind='geometry')),
                    actual=actual[sid],predecessor_export_wkb=(prefix/'data_output/gerber_target_wkb'/name).read_bytes()))
            ids=permission(receipt['source_sha256'])['ordinary_t02_recovery_source_ids']
            for sid in ids:
                rectangles.append(dict(id=sid,original=from_wkb(source.get(originals[sid]['original_ref'],kind='geometry')),
                    actual=actual[sid]))
            mutable=aliases|set(ids)
            fixed=[dict(id=sid,geometry=from_wkb(source.get(row['original_ref'],kind='geometry')),
                        trace_width_mm=meta[sid].get('trace_width_mm')or 0.)for sid,row in originals.items()if sid not in mutable]
            check=check_export_surfaces(circles,rectangles,fixed)
            state['actual']=actual
            return check
        gate(STEPS[10],surface)
        def coverage():return verify_native_scope(service,prefix,source,state['actual'],receipt)
        gate(STEPS[11],coverage)
        result=dict(status='PASS_SCOPED_RECTANGLE_RECOVERY_ON_RETAINED_T01',operations=ledger,
            native_prefix='RETAINED_VERIFIED',T04='NOT_RUN',C028_full_circle_obligation='BLOCKED',
            owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',electrical_manufacturing='NOT_ESTABLISHED')
        record(base/'RESULT.json',result);print(result['status'],flush=True);return 0
    except BaseException as error:
        result=dict(status='HALTED',error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),
            operations=[*ledger,*[dict(operation=name,status='FAIL'if i==0 else'NOT_RUN')for i,name in enumerate(STEPS[len(ledger):])]],
            next_action='STOP; retain failure, no resume or substitution',T04='NOT_RUN')
        record(base/'FAILURE.json',result);print(result,flush=True);return 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--t01-prefix',required=True,type=Path)
    args=parser.parse_args();raise SystemExit(run(args.output,args.t01_prefix))
