#!/usr/bin/env python3
"""Build G10 paired-plot coupons across the EDIT arc parameter envelope."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path('assets/starter/fixtures/before/kicad/coupon.kicad_pcb')
G8_REPORT = Path('out/ingestion/gerber_fidelity/real_arc_compatibility_20261024_v1/real_arc_compatibility.json')
CLI = Path('/Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def uid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'pcb-aperture-cam-g10-attribution:{name}'))


def verify_assets():
    rows=[]
    for line in (ROOT/'contracts/asset_manifest.sha256').read_text().splitlines():
        expected,rel=line.split('  ',1); path=ROOT/rel
        actual=sha(path) if path.is_file() else None
        if actual!=expected: raise SystemExit(f'immutable asset hash mismatch: {rel}')
        rows.append({'path':rel,'sha256':actual})
    return rows


def serialize_segment(name,segment):
    return (f' (segment (start {segment["start"][0]:.6f} {segment["start"][1]:.6f}) '
            f'(end {segment["end"][0]:.6f} {segment["end"][1]:.6f}) '
            f'(width {segment["width"]:.6f}) (layer "F.Cu") (net 1) '
            f'(tstamp {uid(name)}))\n')


def serialize_target(name,target):
    points=' '.join(f'({k} {target[k][0]:.6f} {target[k][1]:.6f})'
                    for k in ('start','mid','end'))
    return (f' (arc {points} (width {target["width"]:.6f}) (layer "F.Cu") '
            f'(net 1) (tstamp {uid(name)}))\n')


def author_board(template,scenario,include_target):
    text=template.replace('(gr_rect locked (start 17.0 17.0) (end 26.0 29.0)',
                          '(gr_rect locked (start 17.0 17.0) (end 79.0 29.0)')
    if not text.rstrip().endswith(')'): raise SystemExit('unexpected template end')
    text=text.rstrip()[:-1]
    for i,seg in enumerate(scenario['context_segments']):
        text+=serialize_segment(f'{scenario["id"]}:context:{i}',seg)
    if include_target:
        text+=serialize_target(f'{scenario["id"]}:target',scenario['target'])
    return text+')\n'


def export_board(cli,tool_hash,version,board,output,precision):
    output.mkdir(parents=True)
    argv=[str(cli),'pcb','export','gerbers','--layers','F.Cu','--precision',str(precision),
          '--no-protel-ext','--check-zones','-o',str(output.resolve())+'/',str(board.resolve())]
    r=subprocess.run(argv,text=True,capture_output=True,check=False)
    (output/'stdout.txt').write_text(r.stdout); (output/'stderr.txt').write_text(r.stderr)
    if r.returncode: raise SystemExit(f'KiCad export failed: {board.name}, precision {precision}: {r.stderr}')
    files=sorted(x for x in output.iterdir() if x.name.endswith('-F_Cu.gbr'))
    if len(files)!=1: raise SystemExit(f'unexpected F.Cu outputs for {board}: {files}')
    return {'board_path':str(board.relative_to(ROOT)),'board_sha256':sha(board),
            'gerber_path':str(files[0].relative_to(ROOT)),'gerber_sha256':sha(files[0]),
            'argv':argv,'tool_sha256':tool_hash,'tool_version':version,
            'precision':precision,'exit_code':r.returncode}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='out/ingestion/gerber_fidelity/g10_arc_attribution_sweep_v2')
    args=parser.parse_args(); output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT/'out'): raise SystemExit('output must stay under out/')
    if output.exists(): raise SystemExit(f'refusing to overwrite existing output: {output}')
    assets=verify_assets(); report_path=ROOT/G8_REPORT
    report=json.loads(report_path.read_text())
    if len(report['records'])!=84: raise SystemExit('expected frozen G8 report with 84 rows')
    by_length=sorted(report['records'],key=lambda r:r['centerline_length_mm'])
    by_width=sorted(report['records'],key=lambda r:r['width_mm'])
    selections={
        'shortest':by_length[0], 'longest':by_length[-1],
        'narrowest':by_width[0], 'widest':by_width[-1],
        'median_length':by_length[len(by_length)//2],
    }
    # Keep distinct source records while preserving which extrema they represent.
    unique=[]; seen=set()
    for label,row in selections.items():
        if row['source_identity'] not in seen:
            unique.append((label,row)); seen.add(row['source_identity'])
    cases=[]; base_x=30.0; x_step=4.0
    def add_case(label,row,orientation,context_kind):
        i=len(cases); x=base_x+i*x_step; y=20.0
        length=float(row['centerline_length_mm']); width=float(row['width_mm'])
        if orientation=='horizontal': start,end=[x,y],[x+length,y]
        else: start,end=[x,y],[x,y+length]
        mid=[(start[0]+end[0])/2,(start[1]+end[1])/2]
        target={'start':start,'mid':mid,'end':end,'width':width,
                'parameter_identity':row['source_identity'],
                'parameter_label':label,'centerline_length_mm':length}
        context=[]
        dx=end[0]-start[0]; dy=end[1]-start[1]
        if context_kind=='partial_overlap':
            context=[{'start':[start[0]+dx/3,start[1]+dy/3],
                      'end':[start[0]+2*dx/3,start[1]+2*dy/3], 'width':width*0.45}]
        elif context_kind=='full_occlusion':
            context=[{'start':start,'end':end,'width':width*1.8}]
        case={'id':f'{label}_{orientation}_{context_kind}','parameter_label':label,
              'orientation':orientation,'context_kind':context_kind,
              'target':target,'context_segments':context}
        cases.append(case)
    for label,row in unique:
        add_case(label,row,'horizontal','isolated')
    for label in ('shortest','longest'):
        if label in selections: add_case(label,selections[label],'vertical','isolated')
    for label in ('shortest','widest'):
        if label in selections: add_case(label,selections[label],'horizontal','partial_overlap')
    for label in ('narrowest','widest'):
        if label in selections: add_case(label,selections[label],'horizontal','full_occlusion')

    version=subprocess.run([str(CLI),'version'],capture_output=True,text=True,check=False)
    if version.returncode or version.stdout.strip()!='10.99.0': raise SystemExit('KiCad 10.99.0 required')
    tool_hash=sha(CLI); template=ROOT/TEMPLATE
    (output/'sources').mkdir(parents=True); (output/'gerbers').mkdir(parents=True)
    records={}
    for case in cases:
        btext=author_board(template.read_text(),case,False)
        ttext=author_board(template.read_text(),case,True)
        # Exact byte check: treatment must equal baseline plus exactly the target arc.
        target_text=serialize_target(f'{case["id"]}:target',case['target'])
        if ttext != btext[:-2] + target_text + ')\n':
            raise SystemExit(f'pair source differs beyond target serialization: {case["id"]}')
        bpath=output/'sources'/f'{case["id"]}_without_target.kicad_pcb'
        tpath=output/'sources'/f'{case["id"]}_with_target.kicad_pcb'
        bpath.write_text(btext); tpath.write_text(ttext)
        record={'scenario':case,'source_pair':{
            'without_target':{'path':str(bpath.relative_to(ROOT)),'sha256':sha(bpath)},
            'with_target':{'path':str(tpath.relative_to(ROOT)),'sha256':sha(tpath)},
            'verified_exact_target_only_byte_delta':True,
            'target_serialized_sha256':hashlib.sha256(target_text.encode()).hexdigest()},
            'plots':{}}
        # KiCad CLI 10.99 supports only Gerber coordinate precision 5 or 6.
        for precision in (6,5):
            if precision!=6 and case['context_kind']=='isolated' and case['parameter_label'] not in ('shortest','widest'):
                continue
            record['plots'][str(precision)]={}
            for side,path in (('without_target',bpath),('with_target',tpath)):
                dest=output/'gerbers'/case['id']/f'p{precision}'/side
                record['plots'][str(precision)][side]=export_board(CLI,tool_hash,version.stdout.strip(),path,dest,precision)
        records[case['id']]=record

    # Fresh-process repeats of the two boundary-sensitive precision-6 pairs.
    for case_id in ('shortest_horizontal_isolated','widest_horizontal_partial_overlap'):
        if case_id not in records: continue
        rec=records[case_id]
        rec['plots']['6_repeat']={}
        for side in ('without_target','with_target'):
            board=ROOT/rec['source_pair'][side]['path']
            dest=output/'gerbers'/case_id/'p6_repeat'/side
            rec['plots']['6_repeat'][side]=export_board(CLI,tool_hash,version.stdout.strip(),board,dest,6)

    spec={'schema':'g10-arc-attribution-envelope-sweep/1',
          'status':'SYNTHETIC_DIAGNOSTIC_ONLY',
          'asset_manifest':{'path':'contracts/asset_manifest.sha256','verified_count':len(assets)},
          'source_template':{'path':TEMPLATE.as_posix(),'sha256':sha(template)},
          'g8_report':{'path':G8_REPORT.as_posix(),'sha256':sha(report_path),
                       'source_sha256':report['source']['sha256'],
                       'gerber_sha256':report['gerber']['sha256']},
          'kicad_cli':{'path':str(CLI),'version':version.stdout.strip(),'sha256':tool_hash},
          'selected_real_edit_parameters':{label:{'source_identity':row['source_identity'],
              'centerline_length_mm':row['centerline_length_mm'],'width_mm':row['width_mm']}
              for label,row in selections.items()},
          'source_pair_invariant':'with_target source bytes equal without_target bytes plus exactly one serialized target arc immediately before the root closing parenthesis.',
          'metric_status_vocabulary':['OBSERVABLE_INCREMENT','NO_OBSERVABLE_INCREMENT','UNRESOLVED'],
          'precision_runs':{'all_cases':[6],'boundary_sensitive_repeat':[6,'6_repeat'],
                            'precision_sensitivity_for_shortest_and_widest':[6,5],
                            'unsupported_cli_precision':{'requested':4,'status':'NOT_RUN_UNSUPPORTED_BY_KICAD_CLI'}},
          'cases':list(records.values()),
          'limitations':['Synthetic source/plot experiments only; not a real EDIT counterfactual.',
                         'No native parser classification changed.',
                         'No ORG-to-EDIT enhancement, connectivity, or manufacturing acceptance established.']}
    (output/'scenario_spec.json').write_text(json.dumps(spec,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'output':str(output.relative_to(ROOT)),'scenario_count':len(records),
                      'precision_sensitive_cases':2,'asset_manifest_verified':len(assets),
                      'kicad_version':version.stdout.strip()},indent=2))


if __name__=='__main__': main()
