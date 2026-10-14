"""Finalize a new completion run with full regressions, compatibility and binding.
Raw run reports are retained; this writes a distinct final_report.json once.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
from .gerber_image import read_image
from .completion_checks import summary
from .validator import Unsupported

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def finalize(run):
    run=Path(run).resolve()
    if not run.is_relative_to(ROOT/'out/v15_completion'):raise ValueError('run outside completion output')
    if (run/'final_report.json').exists():raise ValueError('final report already frozen')
    report=json.loads((run/'report.json').read_text())
    if report.get('unresolved_error'):raise ValueError('raw run failed; no successful finalization allowed')
    required={'GlowStitch','HALPI2-HDMI-FPC'}
    if set(report['boards'])!=required:raise ValueError('incomplete required board set')
    process=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True,timeout=240)
    (run/'regressions.log').write_text(process.stdout+process.stderr)
    report['regressions']={'argv':[sys.executable,'-m','unittest','discover','-s','tests','-v'],'exit_code':process.returncode,'status':'PASS' if process.returncode==0 else 'FAIL','log':str(run/'regressions.log')}
    optional=[];folder=ROOT/'out/v1_5/Ucamco/extracted/2026_03_24_Gerber_Layer_Format_Test_Files'
    for file in sorted(folder.glob('*.gbr')):
        if file.name=='Block_with_different_orientations.gbr':continue
        try:
            image=read_image(file);item={'file':file.name,'status':'PASS','meaning':'Generic image composed under declared profile; independent exact render/reference NOT_ESTABLISHED','geometry':summary(image['geometry'])}
        except Exception as exc:item={'file':file.name,'status':'NOT_ESTABLISHED','reason':str(exc)}
        item['sha256']=sha(file);optional.append(item)
    report['optional_ucamco']=optional
    frozen=json.loads((ROOT/'out/v15_completion/required_matrix_freeze.json').read_text())
    matrix_ok=sha(ROOT/frozen['path'])==frozen['sha256']
    prior=json.loads((ROOT/'out/v15_completion/prior_evidence_hashes.json').read_text())
    changed=[f for f,d in prior.items() if not (ROOT/f).is_file() or sha(ROOT/f)!=d]
    report['historical_evidence_integrity']={'status':'PASS' if not changed else 'FAIL','changed':changed,'files_checked':len(prior)}
    report['required_matrix_integrity']='PASS' if matrix_ok else 'FAIL'
    report['implementation_hashes']={str(p.relative_to(ROOT)):sha(p) for p in [*(ROOT/'src').glob('*.py'),*(ROOT/'tests').glob('*.py'),ROOT/'requirements-completion.txt']}
    report['input_reference_bindings']={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'docs/CODEX_V1_5_COMPLETION_HANDOFF.md',ROOT/'docs/V1_5_COMPLETION_MATRIX.md',ROOT/'docs/V1_5_REFERENCE_QUALIFICATION.md',ROOT/'contracts/asset_manifest.sha256',ROOT/'contracts/public_sources.json',ROOT/'tests/fc1_expected.json',ROOT/'requirements.lock.txt',ROOT/'out/v15_completion/gerber-specification-2026.05.pdf']}
    manifest=json.loads((ROOT/'contracts/public_sources.json').read_text())['sources']
    for name,board in report['boards'].items():
        expected=manifest[name]['selection']['source_board_sha256']
        work=run/name/'work'/manifest[name]['selection']['board']
        if board['source_board_sha256']!=expected or sha(work)!=expected:raise ValueError('native source custody mismatch')
        board['electrical_profile_scope']='Only independently source-justified same-layer named-net pairs and terminal-labelled copper components; not cross-layer/full-job acceptance.'
    report['output_hashes']={str(p.relative_to(run)):sha(p) for p in sorted(run.rglob('*')) if p.is_file() and p.name not in ('final_report.json','decision.md')}
    report['specification']={'revision':'2026.05','url':'https://www.ucamco.com/files/downloads/file_en/554/gerber-layer-format-specification-revision-2026-05_en.pdf','sha256':sha(ROOT/'out/v15_completion/gerber-specification-2026.05.pdf'),'prior_pin':'No prior specification PDF/hash in repository; first explicit pin for the completion adapter, not a frozen V1 contract migration.'}
    report['remaining_obligations']=[{'check':'GlowStitch electrical net acceptance','status':'NOT_ESTABLISHED','missing_datum':'A qualified net/terminal intent map or schematic for the 80 source pads; native net table contains only unnamed net 0. Physical preservation tests do not invent electrical labels.'},
        {'check':'Whole-board clearance/process acceptance','status':'NOT_ESTABLISHED','missing_datum':'Qualified assignments for unlabelled copper and a justified process threshold; numeric named-net spacing is reported separately.'},
        {'check':'Cross-layer electrical connectivity','status':'NOT_ESTABLISHED','missing_datum':'Qualified drill/plating and cross-layer topology contract; only same-layer checks were declared.'}]
    if process.returncode or changed or not matrix_ok:report['overall']='FAIL'
    report['technical_geometry_profile']='PASS' if report['raw_parser_to_fc1']['status']=='PASS' and all(x['geometry_profile']=='PASS' and all(f['status']=='PASS' for f in x['faults']) for x in report['boards'].values()) and process.returncode==0 and matrix_ok and not changed else 'FAIL'
    report['limitations']=['Source-design extraction is independent input evidence, not an independent geometry engine. Both vector routes use GEOS; analytic semantic fixtures supply independent mathematical references.',
        'No-edit same-compositor replay proves preservation/repeatability, not correctness by itself; semantics controls and all native-pad anchors are separate obligations.',
        'Glow bridge detection is physical baseline preservation, not named-net electrical acceptance.',
        'Optional refusal tests are not counted as successful geometry interpretations.','No pcb_Z inspection/integration, V2/V3, remote publication or manufacturing approval.']
    (run/'final_report.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# V1.5 completion technical decision','',f"Geometry/preservation profile: **{report['technical_geometry_profile']}**. Overall required electrical validation: **{report['overall']}**.",'','| Dimension | Result |','|---|---|',f"| Frozen V1 and FC-1 plus new regressions | {report['regressions']['status']} |",f"| Raw reader/compositor vs FC-1 | {report['raw_parser_to_fc1']['status']} |"]
    for name,b in report['boards'].items():
        lines += [f"| {name}: all nine layer geometry/replay/source anchors | {b['geometry_profile']} |",f"| {name}: scoped source-justified named-net checks | {b['electrical_profile']} |",f"| {name}: six fault controls | {'PASS' if all(f['status']=='PASS' for f in b['faults']) else 'NOT_ESTABLISHED'} |"]
    lines += [f"| Historical integrity | {report['historical_evidence_integrity']['status']} |",'| Cursor review | NOT_RUN / CHANNEL_UNAVAILABLE |','| Factory/manufacturing acceptance | NOT_ESTABLISHED |','','The implementation now composes the declared real layers and detects the declared preservation faults. Missing electrical/process intent is not manufactured into a PASS.','',*['- '+x['missing_datum'] for x in report['remaining_obligations']]]
    (run/'decision.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'run':str(run),'geometry_profile':report['technical_geometry_profile'],'overall':report['overall'],'regressions':report['regressions']['status'],'optional_interpreted':sum(x['status']=='PASS' for x in optional),'optional_unsupported':sum(x['status']=='NOT_ESTABLISHED' for x in optional)},indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();finalize(a.run)
