#!/usr/bin/env python3
"""One native directory intake, retained request/result and no renderer authority."""
import argparse,json,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import t01_crop_jobs as jobs
from tools import t01_board_export_jobs as directory_jobs
from tools.t01_route_client import decode,encode,publish
from src.pcb_data_abi.input_directory import collect_raw,collect,IntakeAccessError
from src.pcb_data_abi.raw_directory import identify

def process(call,registry,managed):
    jobs.MANAGED=jobs.output(managed);call=jobs.output(call);registry=jobs.output(registry)
    if call.parent!=registry/'calls':raise ValueError('NATIVE_INTAKE_CALL_PATH_INVALID')
    request=decode((call/'request.json').read_bytes());job=None
    try:
        def cancelled():
            if(call/'cancel_requested.json').exists():raise ValueError('NATIVE_INTAKE_CANCELLED: retained client timeout; no job promotion')
        if set(request)!={'action','launcher_id','input_directory','companion_policy'}or request['action']!='directory_intake'or request['companion_policy']!='PRESERVE_EXCLUDED':raise ValueError('DIRECTORY_INTAKE_REQUEST_INVALID')
        if Path(request['input_directory']).is_absolute()is not True:raise ValueError('EXPLICIT_ABSOLUTE_INPUT_DIRECTORY_REQUIRED')
        # The client does not hold this lock. Native custody covers discovery,
        # qualification, staging and slot publication as one bounded operation.
        with jobs.exclusive():
            cancelled()
            if (jobs.MANAGED/'current.json').exists():
                current,_=jobs.current()
                if jobs.outcome(current)=='IN_PROGRESS':raise ValueError('CROP_JOB_IN_PROGRESS: retained current job; no directory scan')
            from src.crop_circle_sources import verify_assets
            verify_assets()
            root,blobs,ignored=collect_raw(request['input_directory'])
            def command(argv,stem):
                cancelled()
                argv=list(map(str,argv));result=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=300)
                publish(call/(stem+'.json'),encode(dict(argv=argv,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)))
                if result.returncode:raise ValueError('NATIVE_DIRECTORY_SOURCE_EXPORT_FAILED:'+stem)
                return result.stdout.strip()
            supplied=[b for n,b in blobs.items()if Path(n).suffix.lower()!='.kicad_pcb']
            if supplied and all(b'%TF.FileFunction,'in b for b in supplied):
                # Preserve the original exact-X2 profile, including empty layers.
                manifest,strict_blobs=collect(root)
                if strict_blobs!=blobs:raise ValueError('INPUT_DIRECTORY_CHANGED_DURING_QUALIFICATION')
            else:manifest=identify(root,blobs,ignored,call,command)
            publish(call/'IDENTIFICATION.json',encode(manifest))
            cancelled()
            # Detect raw modifications during potentially lengthy qualification.
            _,again,again_ignored=collect_raw(root)
            if blobs!=again or ignored!=again_ignored:raise ValueError('INPUT_DIRECTORY_CHANGED_DURING_QUALIFICATION')
            job,row=directory_jobs.allocate(manifest,blobs)
            cancelled()
            publish(job/'INTAKE_RECEIPT.json',encode(dict(schema='pcb-native-directory-intake/1',request=str(call/'request.json'),request_sha256=jobs.digest((call/'request.json').read_bytes()),identification=str(call/'IDENTIFICATION.json'),identification_sha256=jobs.digest((call/'IDENTIFICATION.json').read_bytes()),rendering='NOT_REQUESTED',job=str(job))))
            result=dict(status='INTAKE_READY',launcher_id=request['launcher_id'],job=str(job),job_sha256=jobs.digest((job/'job.json').read_bytes()),evidence=str(call),rendering='NOT_REQUESTED')
    except Exception as error:
        import traceback
        publish(call/'exception.txt',traceback.format_exc().encode())
        if job:jobs.halt(job,error)
        result=dict(status='HALTED',launcher_id=request.get('launcher_id'),error=str(error),error_details=getattr(error,'details',None),evidence=str(call),rendering='NOT_REQUESTED',construction='NOT_RUN')
    publish(call/'response.json',encode(result));publish(registry/'replies'/(call.name+'.json'),encode(result));return 0 if result['status']=='INTAKE_READY'else 2

def main():
    p=argparse.ArgumentParser();p.add_argument('--call',required=True,type=Path);p.add_argument('--registry',required=True,type=Path);p.add_argument('--managed',required=True,type=Path);a=p.parse_args()
    return process(a.call,a.registry,a.managed)
if __name__=='__main__':raise SystemExit(main())
