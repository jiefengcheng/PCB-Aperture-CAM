#!/usr/bin/env python3
"""Run KiCad DRC/exports on an isolated copy. Does not assert CAM acceptance."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def run(cmd: list[str], log: Path, accepted: tuple[int,...]=(0,)) -> dict:
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=180)
    log.write_text('$ '+' '.join(cmd)+'\n\n'+p.stdout+'\n'+p.stderr,encoding='utf8')
    if p.returncode not in accepted:
        raise RuntimeError(f'Command failed with exit {p.returncode}; see {log}')
    return {'command':cmd,'returncode':p.returncode,'log':str(log)}

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--case',default='candidate')
    ap.add_argument('--cli',help='Path to kicad-cli; otherwise use PATH or standard macOS installation')
    args=ap.parse_args()
    src=ROOT/'fixtures'/args.case/'kicad'
    if not src.is_dir():raise SystemExit(f'No generated case: {src}')
    mac='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
    cli=args.cli or shutil.which('kicad-cli') or (mac if Path(mac).is_file() else None)
    if not cli:raise SystemExit('KiCad CLI not found. Install KiCad; pass --cli /absolute/path/to/kicad-cli. No export validation was performed.')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    out=ROOT/'runs'/f'{args.case}_{stamp}'
    work=out/'work';shutil.copytree(src,work)
    logs=out/'logs';logs.mkdir(); gerbers=out/'gerbers';gerbers.mkdir()
    board=work/'coupon.kicad_pcb'
    evidence={'scope':'KiCad command execution only; not final CAM acceptance','case':args.case,
              'source_board_sha256':hashlib.sha256((src/'coupon.kicad_pcb').read_bytes()).hexdigest(),
              'commands':[],'exported_geometry_checks':'PENDING_INDEPENDENT_READER',
              'schematic_parity':'NOT_APPLICABLE_NO_SCHEMATIC','manufacturing_signoff':'NOT_ESTABLISHED'}
    try:
        evidence['commands'].append(run([cli,'--version'],logs/'version.txt'))
        evidence['commands'].append(run([cli,'pcb','drc','--format','json','--severity-all',
               '--exit-code-violations','-o',str(out/'drc.json'),str(board)],logs/'drc.txt',(0,5)))
        evidence['commands'].append(run([cli,'pcb','export','gerbers','--layers','F.Cu,B.Cu,F.Mask,Edge.Cuts',
               '--precision','6','--no-protel-ext','-o',str(gerbers)+ '/',str(board)],logs/'gerbers.txt'))
        evidence['commands'].append(run([cli,'pcb','export','ipcd356','-o',str(out/'candidate.d356'),str(board)],logs/'ipcd356.txt'))
        evidence['gerber_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in gerbers.iterdir() if p.is_file()}
        evidence['status']='COMMANDS_COMPLETED_VALIDATION_INCOMPLETE'
    except (RuntimeError,subprocess.TimeoutExpired,OSError) as e:
        evidence['status']='TOOL_ERROR';evidence['error']=str(e)
    (out/'execution.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(out)
    print(evidence['status'])
    if evidence['status']=='TOOL_ERROR':raise SystemExit(2)

if __name__=='__main__':main()
