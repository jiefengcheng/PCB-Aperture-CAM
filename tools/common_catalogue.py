"""Build, reopen or export the bounded R140 common catalogue locally."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.common_catalogue import publish,retrieve,export_context,verify_bundle,validate_positive,SCHEMA
from src.ingestion_files import write_json,local


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['build','retrieve','verify','export','acceptance'])
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--revision')
    parser.add_argument('--output',type=Path,default=ROOT/'out/common_catalogue/materialized')
    parser.add_argument('--fail-before-publish',action='store_true')
    args=parser.parse_args(argv)
    if args.action=='build':
        run,revision=publish(ROOT,args.output,fail_before_publish=args.fail_before_publish)
        result={'schema':SCHEMA,'status':'PASS','run':str(run),'dataset_revision':revision,'writer_pid':os.getpid()}
    elif args.action=='acceptance':
        require_output=args.output.resolve()
        if not require_output.is_relative_to(ROOT/'out') or require_output.exists():raise ValueError('Acceptance output must be a new checkout/out directory')
        require_output.mkdir(parents=True)
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        def run(action,*arguments):
            command=[sys.executable,str(Path(__file__).resolve()),action,*map(str,arguments)]
            child=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True)
            (require_output/(action+'.stdout.json')).write_text(child.stdout)
            (require_output/(action+'.stderr.log')).write_text(child.stderr)
            if child.returncode:raise ValueError(action+' failed: '+child.stdout[-1000:]+child.stderr[-1000:])
            return json.loads(child.stdout)
        built=run('build','--output',require_output/'catalogue')
        bundle=built['run'];revision=built['dataset_revision']
        reopened=run('retrieve','--bundle',bundle,'--revision',revision);validate_positive(reopened)
        write_json(require_output/'reopened.json',reopened)
        exported=run('export','--bundle',bundle,'--revision',revision,'--output',require_output/'selection')
        offline=run('retrieve','--bundle',exported['destination'],'--revision',revision)
        write_json(require_output/'export_reopened.json',offline)
        if not (len({built['writer_pid'],reopened['reader_pid'],offline['reader_pid']})==3 and reopened['result_sha256']==offline['result_sha256']):raise ValueError('Fresh-process/export identity failed')
        result={'schema':SCHEMA,'status':'PASS','scope':'Bounded R140 persistence/reopen/correspondence/diagnostic export',
                'run':bundle,'dataset_revision':revision,'result_sha256':reopened['result_sha256'],
                'writer_pid':built['writer_pid'],'reader_pid':reopened['reader_pid'],'export_reader_pid':offline['reader_pid'],
                'output':str(require_output),'independent_review':'NOT_RUN','engineering_acceptance':'NOT_ESTABLISHED'}
        write_json(require_output/'acceptance.json',result)
    else:
        if not args.bundle or not args.revision:parser.error('--bundle and explicit --revision are required')
        bundle=local(ROOT,str(args.bundle))
        if args.action=='verify':
            context=retrieve(bundle,args.revision);validate_positive(context)
            result={'schema':SCHEMA,'status':'PASS','dataset_revision':args.revision,'result_sha256':context['result_sha256'],
                    'scope':'Integrity, complete four-role retrieval, retained qualification semantics and required local geometry correspondences; no whole-board acceptance'}
        elif args.action=='retrieve':result=retrieve(bundle,args.revision)
        else:
            output=local(ROOT,str(args.output))
            if not output.is_relative_to(ROOT/'out'):raise ValueError('Export stays under out/')
            result=export_context(bundle,output,args.revision)
    print(json.dumps(result,allow_nan=False));return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:
        print(json.dumps({'status':'FAIL','error':str(error)}));sys.exit(1)
