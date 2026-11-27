#!/usr/bin/env python3
"""Join independent large-copper trimming and T04 jobs through sealed I/O."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run');inputs=run.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--source',type=Path);inputs.add_argument('--cleanup-job',type=Path)
    run.add_argument('--output',type=Path);run.add_argument('--scope',type=Path,help='Explicit bounded T04 route inventory; omit for a full-board diagnostic')
    run.add_argument('--prepare-display',action='store_true',help='Prepare separate linked saved views after successful execution')
    inspect=sub.add_parser('status');inspect.add_argument('--job',type=Path,required=True)
    display=sub.add_parser('prepare-display',help='Openable, separate saved cleanup/T04 workspaces; no treatment')
    display.add_argument('--job',type=Path,required=True)
    display.add_argument('--output',type=Path,help='Fresh saved-display derivative; retains failed presentation and executes no treatment')
    seal=sub.add_parser('seal-cleanup');seal.add_argument('--job',type=Path,required=True);seal.add_argument('--output',type=Path,required=True)
    check=sub.add_parser('verify');check.add_argument('--seal',type=Path,required=True);check.add_argument('--sha256',required=True)
    args=parser.parse_args()
    from src.gerber_u05.workspace import configure
    configure()
    try:
        from src import copper_phase_seal as seals,copper_pipeline as pipeline
        if args.command=='run':
            value=pipeline.run(source=args.source,cleanup_job=args.cleanup_job,output=args.output,scope=args.scope,
                progress=lambda **event:print(json.dumps(event),file=sys.stderr,flush=True))
            if args.prepare_display:
                completed=value.get('retained',value)
                if completed.get('status')!='COMPLETED':
                    raise ValueError('COPPER_PIPELINE_RETAINED_JOB_NOT_COMPLETED:'+str(value.get('job')))
                from src.viewer_abi.copper_pipeline import prepare
                value=dict(value,display=prepare(Path(value['job'])))
        elif args.command=='status':value=pipeline.status(args.job)
        elif args.command=='prepare-display':
            from src.viewer_abi.copper_pipeline import prepare
            value=prepare(args.job,output=args.output)
        elif args.command=='seal-cleanup':value=seals.publish(args.job,args.output)
        else:
            saved=seals.verify(args.seal,args.sha256)
            value={k:saved[k]for k in('phase','job','source_sha256','occurrence_count','summary','acceptance')}
        print(json.dumps(value,sort_keys=True));return 0
    except Exception as exc:
        print(json.dumps(dict(status='FAIL',error=repr(exc))),file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
