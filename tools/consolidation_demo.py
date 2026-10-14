"""One local command: inventory/store, execute, native shadow, test and render.

Produces inspectable engineering evidence; visual acceptance and the final
consolidation decision are separate from this producer's exit status.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shutil,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.preflight import verify_manifest

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def last_json(text):
    for line in reversed(text.splitlines()):
        try:return json.loads(line)
        except ValueError:pass
    raise RuntimeError('NO_PRODUCER_RESULT')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--native-binary',type=Path,default=Path((ROOT/'out/consolidation/current_native_binary.txt').read_text().strip()) if (ROOT/'out/consolidation/current_native_binary.txt').is_file() else ROOT/'out/consolidation/native/pcb_graph_shadow');ap.add_argument('--node',type=Path);args=ap.parse_args()
    run=ROOT/'out/consolidation'/datetime.datetime.now(datetime.timezone.utc).strftime('demo_%Y%m%dT%H%M%S_%fZ');run.mkdir()
    sources=[p for folder in ['src','tools','web','native','tests'] for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.js','.cjs','.html','.cc')]
    source_start={str(p.relative_to(ROOT)):sha(p) for p in sources}
    prior=json.loads((ROOT/'out/consolidation/history_before.json').read_text());steps=[];started=time.perf_counter()
    def custody():
        bad=[name for name,expected in prior.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=expected]
        if bad:raise RuntimeError('HISTORICAL_CUSTODY_FAILURE: '+repr(bad))
        return {'verified_files':len(prior),'status':'PASS'}
    def call(name,argv,env=None):
        print(json.dumps({'stage':name,'state':'RUNNING'}),flush=True);start=time.perf_counter()
        p=subprocess.run([str(a) for a in argv],cwd=ROOT,capture_output=True,text=True,env=env)
        log=run/(name+'.log');log.write_text(p.stdout+p.stderr)
        step={'stage':name,'argv':list(map(str,argv)),'exit_code':p.returncode,'elapsed_seconds':time.perf_counter()-start,'log':str(log.relative_to(ROOT)),'log_sha256':sha(log)};steps.append(step)
        if p.returncode:raise RuntimeError(name+' failed; see '+str(log))
        return p.stdout
    result={'producer':'consolidation-demo/1','consolidation_acceptance':'NOT_EVALUATED_BY_PRODUCER','steps':steps,'source_sha256':source_start,'review':'NOT_RUN: CHANNEL_UNAVAILABLE'}
    try:
        result['asset_files_verified']=verify_manifest();result['custody_before']=custody()
        before=last_json(call('source_pipeline',[sys.executable,'tools/consolidation_pipeline.py','--legacy','--public']))
        execution=last_json(call('catalog_v2',[sys.executable,'tools/catalog_v2_run.py',before['run']]))
        if execution['status']!='PASS':raise RuntimeError('CATALOG_V2_NOT_ACCEPTED')
        v2=Path(execution['run'])/'result.json'
        final=last_json(call('indexed_candidate_pipeline',[sys.executable,'tools/consolidation_pipeline.py','--legacy','--public','--v2-result',v2]))
        pipeline=Path(final['run']);receipt=json.loads((pipeline/'receipt.json').read_text())
        if not receipt.get('implementation_unchanged_during_run'):raise RuntimeError('PIPELINE_SOURCE_DRIFT')
        result['pipeline']=str(pipeline);result['catalog_v2_result']={'path':str(v2),'sha256':sha(v2)}
        shadows=[]
        if args.native_binary.is_file():
            for dataset in receipt['datasets']:
                data=json.loads((pipeline/dataset['file']).read_text())
                layers=sorted({r['witness']['layer'] for r in data['topology']['relations']})
                for layer in layers:
                    name='shadow_'+dataset['label']+'_'+layer.replace('.','_')
                    summary=last_json(call(name,[sys.executable,'tools/native_shadow_compare.py',pipeline,'--dataset',dataset['label'],'--layer',layer,'--binary',args.native_binary]))
                    if summary['status']!='PARITY_PASS':raise RuntimeError('NATIVE_PARITY_FAILURE')
                    shadows.append({'dataset':dataset['label'],'layer':layer,'result':str(Path(summary['run'])/'result.json')})
            result['native_role']='SHADOW_ONLY: actual per-layer typed adjacency comparison'
        else:result['native_role']='NOT_RUN: pinned native binary unavailable; no mock native PASS'
        result['native_shadows']=shadows
        comparison_manifest=run/'native_comparisons.json';comparison_manifest.write_text(json.dumps({'comparisons':[{'dataset':s['dataset'],'layer':s['layer'],'path':s['result'],'sha256':sha(s['result'])} for s in shadows]},indent=2)+'\n')
        manifest=json.loads((ROOT/'contracts/visual_inputs_v1.json').read_text());manifest['reports']['v2']={'path':str(v2.relative_to(ROOT)),'sha256':sha(v2)}
        manifest_path=run/'visual_inputs.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
        env=dict(os.environ);env['PCB_CAM_NATIVE_SHADOW_BINARY']=str(args.native_binary)
        call('regressions',[sys.executable,'-m','unittest','discover','-s','tests','-v'],env)
        node=args.node or shutil.which('node') or Path('/Users/geoffcheng/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
        if not Path(node).is_file():raise RuntimeError('NODE_MODEL_TEST_RUNTIME_UNAVAILABLE')
        call('replay_model',[node,'tests/js/replay_projection.test.cjs'])
        visual=last_json(call('visual',[sys.executable,'tools/visual_report.py','--manifest',manifest_path,'--pipeline',pipeline,'--comparisons',comparison_manifest,'--pointer',ROOT/'out/consolidation/current_visual.txt']))
        call('verify_visual',[sys.executable,'tools/verify_visual_bundle.py',visual['run']])
        benchmark=last_json(call('benchmarks',[sys.executable,'tools/consolidation_bench.py',pipeline,'--comparisons',comparison_manifest,'--binary',args.native_binary]));result['benchmark']=benchmark
        call('backend_model',[node,'tests/js/backend_model.test.cjs'])
        result['visual']=visual;result['custody_after']=custody()
        if any(sha(ROOT/p)!=expected for p,expected in source_start.items()):raise RuntimeError('SOURCE_CHANGED_DURING_DEMO')
        result['status']='RECORDED_FOR_INSPECTION'
    except Exception as exc:
        result['status']='FAILED';result['error']=repr(exc)
        raise
    finally:
        result['elapsed_seconds']=time.perf_counter()-started
        (run/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'run':str(run),'status':result['status'],'visual':result.get('visual'),'error':result.get('error')}),flush=True)
if __name__=='__main__':main()
