"""Re-evaluate retained, hash-bound native exports; no fresh export claimed."""
from pathlib import Path
import datetime,hashlib,json,subprocess,sys,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.source_aware import evaluate,terminal_identity
from src.native_reference import terminals,children
from src.fc1_run import custody
import sexpdata
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    custody()
    m=json.loads((ROOT/'contracts/source_aware_v1.json').read_text())
    report_path=ROOT/m['baseline_report'];assert sha(report_path)==m['baseline_report_sha256']
    r=json.loads(report_path.read_text());oldrun=report_path.parent
    for f,d in r['implementation_hashes'].items():assert sha(ROOT/f)==d,f
    for f,d in r['input_reference_bindings'].items():assert sha(ROOT/f)==d,f
    for f,d in r['output_hashes'].items():assert sha(oldrun/f)==d,f
    prior=json.loads((ROOT/'out/source_aware_v1/history_before.json').read_text())
    for f,d in prior.items():assert sha(ROOT/f)==d,f
    manifest=json.loads((ROOT/'contracts/public_sources.json').read_text())['sources']['GlowStitch']
    selection=manifest['selection'];source=ROOT/'external/sources/GlowStitch'/selection['archive']
    with zipfile.ZipFile(source) as z:raw=z.read(selection['board']);members=z.namelist()
    assert hashlib.sha256(raw).hexdigest()==selection['source_board_sha256']
    work=oldrun/'GlowStitch/work'/selection['board'];assert work.read_bytes()==raw
    pads=terminals(work);board=sexpdata.loads(raw.decode())
    nets=[x[1:] for x in children(board,'net')]
    assert len(pads)==80 and len({terminal_identity(t) for t in pads})==80
    assert all(t['net'] is None for t in pads) and nets==[[0,'']]
    assert [{k:v for k,v in t.items() if k!='shape'} for t in pads]==[{**t,'center_mm':tuple(t['center_mm'])} for t in r['boards']['GlowStitch']['source_terminals']]
    run=ROOT/'out/source_aware_v1'/datetime.datetime.now(datetime.timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ');run.mkdir()
    test=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True)
    (run/'regressions.log').write_text(test.stdout+test.stderr)
    result=evaluate(r,m)
    if test.returncode:result['status']='FAIL'
    result.update({'baseline_report_sha256':sha(report_path),'manifest_sha256':sha(ROOT/'contracts/source_aware_v1.json'),'regressions_exit_code':test.returncode,'history_files_unchanged':len(prior),'original_precompletion_files_unchanged':289,'bound_original_outputs_verified':len(r['output_hashes']),'intent_dependency':{'classification':'ABSENT_ELECTRICAL_INTENT_DATA','native_net_table':nets,'pads':80,'unique_revision_bound_composite_terminal_identities':80,'source_commit':manifest['commit'],'source_board_sha256':selection['source_board_sha256'],'selected_archive_members':members,'inventory_reference':'contracts/public_sources.json','meaning':'Already acquired inventory has no matching schematic/netlist/authoritative terminal map; unnamed net 0 is unknown, not common net or no-connect. Source/export identities match all 80 terminals; no conflicting revision found.','discharge_source':m['discharge_source']},'evidence_mode':'Re-evaluation of hash-verified retained native exports; no new native export claimed','implementation_sha256':{p:sha(ROOT/p) for p in ['src/source_aware.py','tools/source_aware_run.py','tests/test_source_aware.py']}})
    for f,d in prior.items():assert sha(ROOT/f)==d,f
    (run/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'run':str(run),'profile':result['status'],'original':result['original_overall'],'history_files':len(prior),'tests_exit':test.returncode}))
    return test.returncode or (result['status']!='PASS')
if __name__=='__main__':sys.exit(main())
