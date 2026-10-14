"""One bounded V2 execution: compute, native plot, independent check, reject faults."""
from pathlib import Path
import datetime,hashlib,importlib.metadata,json,shutil,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.v2_executor import execute,plan,sha,ROOT
from src.fc1_run import custody
from src.validator import evaluate,layers,equivalent
from src.falsification import falsify
from src.gerber_image import read_image
from src.completion_checks import equivalent as image_equivalent
from tools.qualify_public import command
from shapely import affinity
CLI=Path('/Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli')

def main():
    custody()
    contract=json.loads((ROOT/'contracts/v2_move_pad.json').read_text());source=ROOT/contract['source']
    pinned=json.loads((ROOT/'out/native_exports/20261014T140617_287308Z/run_receipt.json').read_text())
    if sha(CLI)!=pinned['cli_sha256']:raise ValueError('KiCad binary differs from frozen baseline')
    run=ROOT/'out/v2'/datetime.datetime.now(datetime.timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ');run.mkdir()
    result={'operation_contract':contract['id'],'contract_sha256':sha(ROOT/'contracts/v2_move_pad.json'),'status':'NOT_ESTABLISHED','cli_sha256':sha(CLI),'environment':{'KICAD_RUN_FROM_BUILD_DIR':'1'},'source_sha256':sha(source),'tool_versions':{n:importlib.metadata.version(n) for n in ('gerbonara','shapely','rtree','sexpdata')},'transactions':{},'Cursor':'NOT_RUN: CHANNEL_UNAVAILABLE','factory':'NOT_ESTABLISHED'}
    def native_export(board,bundle):
        from tools.preflight import verify_manifest
        verify_manifest()
        out=bundle/'gerbers';out.mkdir()
        project=source.with_suffix('.kicad_pro')
        if project.exists() and not board.with_suffix('.kicad_pro').exists():shutil.copy2(project,board.with_suffix('.kicad_pro'))
        receipt={'input_board_sha256':sha(board),'commands':[]}
        commands=[([CLI,'pcb','drc','--format','json','--severity-all','--exit-code-violations','-o',bundle/'drc.json',board],'drc.log',(0,5)),([CLI,'pcb','export','gerbers','--layers','F.Cu,F.Mask,Edge.Cuts','--precision','6','--no-protel-ext','-o',str(out)+'/',board],'export.log',(0,))]
        try:
            for argv,log,allowed in commands:
                rec=command(argv,bundle/log);rec['log_relative_to_bundle']=log;receipt['commands'].append(rec)
                if rec['exit_code'] not in allowed:raise RuntimeError('native tool failed: '+str(rec))
            receipt['outputs']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
            if not receipt['outputs'] or sha(board)!=receipt['input_board_sha256']:raise RuntimeError('native export custody failure')
        finally:(bundle/'export_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        return out
    try:
        result['version']=command([CLI,'version'],run/'version.log')
        if result['version']['exit_code']:raise RuntimeError('native version command failed')
        before=run/'before';shutil.copytree(source.parent,before)
        before_export=native_export(before/'coupon.kicad_pcb',before)
        validator=lambda directory:evaluate(before_export,directory)
        for name in ('positive','replay'):
            journal=execute(source,contract,run/name,native_export,validator);result['transactions'][name]=journal
            if journal['state']!='COMMITTED':raise RuntimeError(name+' did not commit: '+str(journal))
        candidate=run/'positive/accepted/coupon.kicad_pcb';candidate_export=candidate.parent/'gerbers'
        replay=run/'replay/accepted/coupon.kicad_pcb'
        assert candidate.read_bytes()==replay.read_bytes()
        result['deterministic_replay']={'status':'PASS','candidate_sha256':sha(candidate),'replay_sha256':sha(replay)}
        # Oracle comparison is post-execution evidence only; never used to create edits.
        result['computed_candidate_reference_comparison']={'status':'PASS' if candidate.read_bytes()==(ROOT/'assets/starter/fixtures/candidate/kicad/coupon.kicad_pcb').read_bytes() else 'FAIL','meaning':'Computed from before+policy; supplied generated candidate read only after execution for comparison.'}
        result['native_gerber_validation']=evaluate(before_export,candidate_export)
        parsed=layers(candidate_export);replayed=layers(replay.parent/'gerbers')
        result['export_geometry_replay']={k:equivalent(parsed[k]['geometry'],replayed[k]['geometry']) for k in parsed}
        result['V1_5_compositor_agreement']={k:image_equivalent(parsed[k]['geometry'],affinity.scale(read_image(candidate_export/('coupon-'+k+'.gbr'))['geometry'],1,-1,origin=(0,0))) for k in parsed}
        negatives=falsify(before_export,candidate_export,run/'gerber_faults')
        (run/'negative_controls.json').write_text(json.dumps(negatives,indent=2)+'\n')
        result['frozen_gerber_fault_controls']=[{k:v for k,v in x.items() if k!='report'} for x in negatives]
        previous_sha=sha(candidate)
        for name,key,old,new,expected in [
            ('broken_connection','F_Cu','X20000000Y-21550000D02*\nX20000000Y-23000000D01*','','FAIL'),
            ('unsupported_semantics','F_Cu','%LPD*%','%LPD*%\n%LMX*%','NOT_ESTABLISHED')]:
            def corrupted_export(board,bundle,layer=key,a=old,b=new):
                directory=native_export(board,bundle);p=directory/('coupon-'+layer+'.gbr');text=p.read_text()
                if a not in text:raise ValueError('missing fault anchor')
                p.write_text(text.replace(a,b));return directory
            journal=execute(source,contract,run/name,corrupted_export,validator)
            result['transactions'][name]=journal
            observed=json.loads((run/name/'staging/validation.json').read_text())
            assert journal['state']=='REJECTED' and observed['overall']==expected
            assert not (run/name/'accepted').exists() and sha(candidate)==previous_sha
        def failed_export(board,bundle):
            rec=command([CLI,'pcb','export','gerbers','--v2-deliberately-invalid-option',board],bundle/'invalid_export.log')
            (bundle/'tool_failure.json').write_text(json.dumps(rec,indent=2)+'\n')
            assert rec['exit_code']!=0
            raise RuntimeError('deliberate native CLI failure, exit='+str(rec['exit_code']))
        result['transactions']['native_export_failure']=execute(source,contract,run/'native_export_failure',failed_export,validator)
        assert result['transactions']['native_export_failure']['state']=='REJECTED'
        for phase in ('STAGED','VALIDATED'):
            def failure(name,ws,phase=phase):
                if name==phase:raise OSError('deliberate prepublication failure at '+phase)
            name='failure_at_'+phase.lower()
            result['transactions'][name]=execute(source,contract,run/name,native_export,validator,failure)
            assert result['transactions'][name]['state']=='REJECTED' and not (run/name/'accepted').exists()
        assert sha(candidate)==previous_sha
        result['rollback']={'status':'PASS','source_unchanged':sha(source)==contract['source_sha256'],'previous_accepted_unchanged':sha(candidate)==previous_sha,'mechanism':'No failed attempt is published; failed staging is retained, previous accepted bundle is not overwritten.'}
        tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True,timeout=240)
        (run/'regressions.log').write_text(tests.stdout+tests.stderr)
        result['regressions']={'exit_code':tests.returncode,'status':'PASS' if not tests.returncode else 'FAIL'}
        custody()
        for name,digest in contract['pcb_Z_source_sha256'].items():assert sha(Path(contract['pcb_Z_path'])/name)==digest
        history=json.loads((ROOT/'out/v2/history_before.json').read_text())
        changed=[p for p,d in history.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=d]
        result['historical_integrity']={'status':'FAIL' if changed else 'PASS','files_checked':len(history),'changed':changed}
        result['pcb_Z_read_only']={'status':'PASS','all_python_source_hashes_unchanged':True,'module_imports':False,'SQLite_or_legacy_writes_executed':False,'qualified_functions':contract['pcb_Z_allowed_functions'],'limitations':'Native pcbnew runtime not qualified; legacy layer scan omits pads. Explicit pad adapter; grouping qualified only at zero clearance. No full package merger.'}
        required=[result['native_gerber_validation']['overall']=='PASS',result['computed_candidate_reference_comparison']['status']=='PASS',all(result['export_geometry_replay'].values()),all(x['status']=='PASS' for x in result['V1_5_compositor_agreement'].values()),all(x['status']=='PASS' for x in negatives),tests.returncode==0,not changed]
        result['status']='PASS' if all(required) else 'FAIL'
    except Exception as exc:
        result['status']='FAIL';result['error']=repr(exc)
        raise
    finally:
        result['implementation_sha256']={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'src/v2_discovery.py',ROOT/'src/v2_executor.py',ROOT/'tools/v2_run.py',ROOT/'tests/test_v2_executor.py']}
        result['output_sha256']={str(p.relative_to(run)):sha(p) for p in sorted(run.rglob('*')) if p.is_file() and p.name!='result.json'}
        result['artifact_relocation']='Successful transaction staging/ was atomically renamed accepted/; exact native argv/log paths reflect their execution-time staging paths. Use log_relative_to_bundle plus published bundle location.'
        (run/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'run':str(run),'status':result['status'],'error':result.get('error')}),flush=True)
    return result['status']!='PASS'
if __name__=='__main__':sys.exit(main())
