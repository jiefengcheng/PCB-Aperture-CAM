#!/usr/bin/env python3
"""Validate a recorded native export pair and preserve V1 evidence."""
from pathlib import Path
import argparse, importlib.metadata, json, platform, sys, subprocess
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.preflight import verify_manifest
from src.validator import evaluate, layers, equivalent, sha, Unsupported
from src.falsification import falsify

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--run',type=Path,required=True); args=ap.parse_args()
    run=args.run.resolve()
    if not run.is_relative_to(ROOT/'out'): raise SystemExit('export run must be under this checkout/out')
    count=verify_manifest()
    receipt=json.loads((run/'run_receipt.json').read_text())
    before,candidate=run/'before/gerbers',run/'candidate/gerbers'
    report=evaluate(before,candidate)
    checks=report['checks']
    def add(key,status,actual,evidence): checks.append({'id':key,'mandatory':True,'status':status,'actual':actual,'evidence':evidence})
    add('G0','PASS',{'assets_verified':count},['contracts/asset_manifest.sha256'])
    custody=receipt['status']=='EXPORT_COMPLETED_GEOMETRY_UNVALIDATED'
    for case in ('before','candidate'):
        r=receipt['cases'].get(case,{})
        source=ROOT/'assets/starter/fixtures'/case/'kicad/coupon.kicad_pcb'
        custody=custody and r.get('source_sha256')==sha(source)==r.get('work_sha256_initial')==r.get('work_sha256_after')
        for name,digest in r.get('exported',{}).items(): custody=custody and sha(run/case/'gerbers'/name)==digest
        custody=custody and bool(r.get('exported')) and r['commands'][-1]['exit_code']==0
    add('G1','PASS' if custody else 'FAIL',receipt,[str(run/'run_receipt.json')])
    try:
        observed=layers(ROOT/'assets/observed_before'); b=layers(before)
        comparison={k:equivalent(b[k]['geometry'],observed[k]['geometry']) for k in b}
        add('observed_before_crosscheck','PASS' if all(comparison.values()) else 'FAIL',comparison,['assets/observed_before',str(before)])
    except (Unsupported,OSError,ValueError) as exc:
        add('observed_before_crosscheck','NOT_ESTABLISHED',str(exc),[str(before)])
    negatives=falsify(before,candidate,ROOT/'out/negative_controls')
    add('negative_controls','PASS' if all(x['status']=='PASS' for x in negatives) else 'FAIL',
        [{k:v for k,v in x.items() if k!='report'} for x in negatives],['out/negative_controls.json'])
    (ROOT/'out/negative_controls.json').write_text(json.dumps(negatives,indent=2)+'\n')
    report.update(implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), implementation_hashes={str(p.relative_to(ROOT)):sha(p) for folder in ('src','tools','tests') for p in (ROOT/folder).glob('*.py')}, report_version='1.0',inputs={case:{'path':str(run/case/'gerbers'),'hashes':receipt['cases'][case]['exported'],'source_sha256':receipt['cases'][case]['source_sha256']} for case in ('before','candidate')},
        policy_sha256=sha(ROOT/'assets/starter/reference/policy.json'),
        independent_intent_sha256=sha(ROOT/'assets/starter/reference/intended_connections.json'),
        dependency_licenses={p:dict(importlib.metadata.metadata(p)).get('License-Expression',dict(importlib.metadata.metadata(p)).get('License','See package LICENSE')) for p in ('gerbonara','shapely','jsonschema')},
        tool_versions={**{p:importlib.metadata.version(p) for p in ('gerbonara','shapely','jsonschema')},'python':platform.python_version(),'kicad':receipt['tool_version']},
        coordinate_transform={'source':'Gerber mm, Y up','evaluation':'KiCad mm, Y down','mapping':'(x,y) -> (x,-y)'},
        limitations=['Synthetic coupon only; no manufacturing or DFM approval.',
            'Single front copper layer; no holes, zones, arcs, macros, step-repeat or image transforms qualified. Unknown constructs yield NOT_ESTABLISHED.',
            'Negative mask file describes openings; dark regions are opening geometry, not copper. Profile omits FilePolarity and is qualified as positive stroke geometry.',
            'Circular strokes use 128 chords per quadrant; maximum radial underestimate for 0.125 mm radius is 0.000002354 mm; decision tolerance 0.001 mm. Clearance requires an extra 0.001 mm guard.',
            'Connectivity is checked after 0.099 mm erosion to reject narrow necks; this is an experimental width bound, not a process guarantee.',
            'Terminal identity uses X2 .P attributes; net intent is supplied independently. X2 net names are not used to establish physical connectivity.',
            'Native DRC reports a library-table warning; it is supplementary and does not establish acceptance.'],
        cursor_review={'status':'NOT_RUN','reason':'CHANNEL_UNAVAILABLE'})
    statuses=[c['status'] for c in checks if c['mandatory']]
    report['overall']='FAIL' if 'FAIL' in statuses else ('NOT_ESTABLISHED' if any(s!='PASS' for s in statuses) else 'PASS')
    from jsonschema import validate
    validate(report,json.loads((ROOT/'contracts/report.schema.json').read_text()))
    (ROOT/'out/v1_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# V1 validation: '+report['overall'],'','Native export run: `'+str(run.relative_to(ROOT))+'`.','',
           '| Check | Result |','|---|---|']+[f"| {c['id']} | {c['status']} |" for c in checks]
    measurements={c['id']:c.get('actual') for c in checks if c['id'] in ('exposure','center_registration','clearance','connectivity','scope')}
    lines+=['','Measured evidence:', '```json', json.dumps(measurements,indent=2), '```','',
            'Cursor independent review: NOT_RUN / CHANNEL_UNAVAILABLE.','',*['- '+s for s in report['limitations']], '',
            'Exact commands, output hashes and DRC logs are in the native run receipt; per-check measurements are in v1_validation.json.', '', 'Reproduce: `KICAD_RUN_FROM_BUILD_DIR=1 python3 tools/export_native.py --case both --cli <supplied-cli>`; then `.venv/bin/python tools/validate_native.py --run <run>` and `.venv/bin/python -m unittest discover -s tests -v`.']
    (ROOT/'out/v1_validation.md').write_text('\n'.join(lines)+'\n')
    (ROOT/'out/current_native.txt').write_text(str(run)+'\n')
    print(json.dumps({'overall':report['overall'],'negative_controls':[(x['name'],x['status']) for x in negatives]},indent=2))
if __name__=='__main__': main()
