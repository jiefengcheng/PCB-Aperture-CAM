"""Run bounded large-copper trimming independently of the Gerber viewer."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    from src.gerber_u05.workspace import configure
    configure()
    from src.large_copper_runner import run,status,publish_saved
    parser=argparse.ArgumentParser(description=__doc__)
    command=parser.add_subparsers(dest='command',required=True)
    execute=command.add_parser('run')
    execute.add_argument('--source',type=Path,required=True)
    execute.add_argument('--output',type=Path)
    execute.add_argument('--prepare-display',action='store_true')
    inspect=command.add_parser('status');inspect.add_argument('--job',type=Path,required=True)
    show=command.add_parser('prepare-display');show.add_argument('--job',type=Path,required=True)
    show.add_argument('--new-revision',action='store_true',help='Create a separate saved display derivative; retain previous snapshots')
    args=parser.parse_args()
    try:
        if args.command=='status':answer=status(args.job)
        elif args.command=='prepare-display':answer=publish_saved(args.job,new_revision=args.new_revision)
        else:
            if not args.source.is_absolute():raise ValueError('EXPLICIT_ABSOLUTE_SOURCE_REQUIRED')
            answer=run(args.source,output=args.output,
                progress_callback=lambda **event: print(json.dumps(dict(event='progress',**event)),file=sys.stderr,flush=True))
            completed=answer.get('retained',answer)['status'] in ('COMPLETED_FOR_PROFILE','COMPLETED_WITH_UNRESOLVED')
            if args.prepare_display and completed:
                answer['display']=publish_saved(answer['job'])
        print(json.dumps(answer,sort_keys=True))
    except Exception as exc:
        print(json.dumps(dict(status='FAIL',error=repr(exc))),file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':sys.exit(main())
