#!/usr/bin/env python3
"""Optional local KiCad export of immutable native coupon COPIES. Not V1 acceptance."""
from __future__ import annotations
from pathlib import Path
import argparse, datetime, hashlib, json, shutil, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
MAC_CLI=Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')

def execute(cmd,log,acceptable=(0,)):
    try:
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,timeout=240)
        log.write_text('$ '+' '.join(map(str,cmd))+'\n'+p.stdout+'\n'+p.stderr)
        result={'argv':list(map(str,cmd)),'exit_code':p.returncode,'log':str(log)}
        if p.returncode not in acceptable:
            raise RuntimeError(f'exit={p.returncode}; see {log}')
        return result
    except (subprocess.TimeoutExpired,OSError) as e:
        raise RuntimeError(str(e)) from e

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--case',choices=['before','candidate','both'],default='both')
    ap.add_argument('--cli',default=None)
    args=ap.parse_args()
    cli=args.cli or shutil.which('kicad-cli') or (str(MAC_CLI) if MAC_CLI.is_file() else None)
    if not cli:
        raise SystemExit('NOT_RUN / KICAD_CLI_UNAVAILABLE; supply --cli or run locally with KiCad installed')
    # Verify source integrity before invoking an external program.
    from preflight import verify_manifest
    verify_manifest()
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run=ROOT/'out'/'native_exports'/stamp
    run.mkdir(parents=True)
    receipt={'cli_sha256':sha(Path(cli)),'environment':{'KICAD_RUN_FROM_BUILD_DIR':__import__('os').environ.get('KICAD_RUN_FROM_BUILD_DIR')},'execution':'KICAD_CLI_EXPORT_ONLY_NOT_CAM_ACCEPTANCE','cli':str(cli),'cases':{},'tool_version':None}
    try:
        result=execute([cli,'--version'],run/'version.log')
        receipt['version_command']=result
        receipt['tool_version']=(run/'version.log').read_text().splitlines()[1:3]
        for case in (['before','candidate'] if args.case=='both' else [args.case]):
            source=ROOT/'assets'/'starter'/'fixtures'/case/'kicad'
            working=run/case/'work'
            shutil.copytree(source,working)
            output=run/case/'gerbers';output.mkdir()
            board=working/'coupon.kicad_pcb'
            evidence={'source_sha256':sha(source/'coupon.kicad_pcb'),'work_sha256_initial':sha(board),'commands':[]}
            evidence['commands'].append(execute([cli,'pcb','drc','--format','json','--severity-all','--exit-code-violations','-o',run/case/'drc.json',board],run/case/'drc.log',(0,5)))
            evidence['commands'].append(execute([cli,'pcb','export','gerbers','--layers','F.Cu,F.Mask,Edge.Cuts','--precision','6','--no-protel-ext','-o',str(output)+'/',board],run/case/'export.log'))
            evidence['exported']={p.name:sha(p) for p in output.rglob('*') if p.is_file()}
            evidence['work_sha256_after']=sha(board)
            receipt['cases'][case]=evidence
        receipt['status']='EXPORT_COMPLETED_GEOMETRY_UNVALIDATED'
    except Exception as e:
        receipt['status']='TOOL_ERROR'
        receipt['error']=str(e)
    (run/'run_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(run)
    print(receipt['status'])
    if receipt['status']=='TOOL_ERROR':sys.exit(2)

if __name__=='__main__': main()
