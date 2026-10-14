"""Measured source/catalog/index/graph workloads, with explicit cache conditions."""
from pathlib import Path
import argparse,datetime,importlib.metadata,json,os,platform,resource,sqlite3,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.revision_catalog import RevisionCatalog,canonical,digest
from src.native_graph_adapter import NativeGraphAdapter
ROOT=Path(__file__).resolve().parents[1]
def rss(kind):
    value=resource.getrusage(kind).ru_maxrss
    return value if sys.platform=='darwin' else value*1024

def main():
    ap=argparse.ArgumentParser();ap.add_argument('pipeline',type=Path,nargs='?');ap.add_argument('--comparisons',type=Path);ap.add_argument('--native-probe',nargs=5,metavar=('BINARY','STORE','SNAPSHOT','LAYER','SEEDS'));ap.add_argument('--binary',type=Path,default=ROOT/'out/consolidation/native/pcb_graph_shadow');args=ap.parse_args()
    if args.native_probe:
        binary,store,snapshot,layer,encoded_seeds=args.native_probe
        start=time.perf_counter();q=NativeGraphAdapter(binary).query(store,snapshot,json.loads(encoded_seeds),expected_layer=layer,timeout_seconds=60)
        print(json.dumps({'status':q['status'],'complete':q['complete'],'result_sha256':q.get('result_sha256'),'records':len(q['records']),'api_wall_seconds':time.perf_counter()-start,'native_process_seconds':q.get('native_process_seconds'),'native_child_peak_rss_bytes':rss(resource.RUSAGE_CHILDREN),'python_coordinator_peak_rss_bytes':rss(resource.RUSAGE_SELF),'memory_scope':'One fresh Python probe, one native child; process high-water marks, not allocation deltas.'}));return
    if args.pipeline is None:ap.error('pipeline required')
    run=ROOT/'out/consolidation'/datetime.datetime.now(datetime.timezone.utc).strftime('bench_%Y%m%dT%H%M%S_%fZ');run.mkdir()
    receipt=json.loads((args.pipeline/'receipt.json').read_text());comparisons=json.loads(args.comparisons.read_text())['comparisons'] if args.comparisons else []
    datasets=[]
    with RevisionCatalog(args.pipeline/'catalog') as catalog:
        for entry in receipt['datasets']:
            path=args.pipeline/entry['file'];raw=path.read_bytes();
            if digest(raw)!=receipt['outputs'][entry['file']]:raise RuntimeError('BENCHMARK_INPUT_SNAPSHOT_MISMATCH')
            start=time.perf_counter();data=json.loads(raw);decode=time.perf_counter()-start
            revision=data['catalog_revision'];objects=data['inventory']['objects'];first=next(r for r in objects if r.get('geometry_sha256') and 'F.Cu' in r['layers'])
            samples=[]
            for repeat in range(3):
                for name,kwargs in [('identity',{'ids':[first['id']]}),('ordered_page',{'after_id':first['id'],'limit':50}),('pads_on_front',{'properties':{'kind':'pad'},'layer':'F.Cu','limit':100})]:
                    start=time.perf_counter();q=catalog.query(revision,**kwargs);samples.append({'workload':name,'repeat':repeat,'condition':'first read in coordinator' if repeat==0 else 'same coordinator, stable generation cache','wall_seconds':time.perf_counter()-start,'status':q['status'],'records':len(q['records']),'returned_json_bytes':q.get('returned_json_bytes'),'result_sha256':q['result_sha256'],'verification':q['verification']})
            region=[]
            for repeat in range(3):
                q=catalog.region_query(revision,first['bounds_mm'],'F.Cu',limit=1000);region.append({'repeat':repeat,**{k:v for k,v in q.items() if k not in ('records','unsupported_sample')}})
            start=time.perf_counter();encoded=canonical(objects[:1000]);serialize=time.perf_counter()-start
            plans={}
            for name,sql,params in [('identity','SELECT record_json FROM objects WHERE revision=? AND object_id=?',(revision,first['id'])),('native_identity','SELECT record_json FROM objects WHERE revision=? AND native_id=?',(revision,first.get('native_id'))),('ordered_range','SELECT record_json FROM objects WHERE revision=? AND object_id>? ORDER BY object_id LIMIT 50',(revision,first['id']))]:
                plans[name]=[tuple(row) for row in catalog.db.execute('EXPLAIN QUERY PLAN '+sql,params)]
            graph=[]
            for comparison in (c for c in comparisons if c['dataset']==entry['label']):
                report_path=Path(comparison['path']);report=json.loads(report_path.read_text());
                if report['status']!='PARITY_PASS' or report['source_snapshot']!=revision or report['source_pipeline_sha256']!=digest(raw):raise RuntimeError('BENCHMARK_NATIVE_SNAPSHOT_MISMATCH')
                layer=comparison['layer'];seeds=report['actual_query_samples']['out']['query']['seeds'][:16]
                start=time.perf_counter();adj={}
                for r in data['topology']['relations']:
                    if r['witness']['layer']==layer:adj.setdefault(r['source'],set()).add(r['target'])
                ref_build=time.perf_counter()-start;reference_samples=[];native_samples=[]
                for repeat in range(3):
                    start=time.perf_counter();rows=sorted([{'seed':uid,'source':uid,'target':target,'type':'physical_contact'} for uid in seeds for target in adj.get(uid,set())],key=lambda r:(r['seed'],r['source'],r['target']));answer=digest(canonical(rows));reference_samples.append({'repeat':repeat,'wall_seconds':time.perf_counter()-start,'result_sha256':answer,'records':len(rows)})
                    argv=[sys.executable,str(Path(__file__).resolve()),'--native-probe',str(args.binary),str(report_path.parent/'materialization'),revision,layer,json.dumps(seeds)]
                    start=time.perf_counter();p=subprocess.run(argv,capture_output=True,text=True,check=True);probe=json.loads(p.stdout);probe['isolated_probe_process_wall_seconds']=time.perf_counter()-start;probe['repeat']=repeat
                    if not probe['complete'] or probe['result_sha256']!=answer:raise RuntimeError('BENCHMARK_QUERY_PARITY_FAILURE')
                    native_samples.append(probe)
                graph.append({'layer':layer,'seeds':seeds,'reference_adjacency_build_seconds':ref_build,'native_storage_bytes':{'core_db':sum(p.stat().st_size for p in (report_path.parent/'materialization/db').rglob('*') if p.is_file()),'identity_mapping':(report_path.parent/'materialization/identities.json').stat().st_size,'proof_occurrences':(report_path.parent/'materialization/occurrences.json').stat().st_size},'recorded_native_core_build_seconds':report['native_build']['elapsed_seconds'],'reference_samples':reference_samples,'native_samples':native_samples,'condition':'Each native sample uses a fresh coordinator/native child; OS caches uncontrolled. After prior materialization/parity; no cold-disk claim.','role':'typed adjacency only; proof occurrences remain in catalog'})
            datasets.append({'label':entry['label'],'catalog_revision':revision,'source_bytes':len((args.pipeline/'catalog/payloads'/data['source_sha256']).read_bytes()),'pipeline_json_bytes':len(raw),'pipeline_json_decode_seconds':decode,'recorded_pipeline_stage_metrics':[{'stage':s['stage'],'elapsed_seconds':s['elapsed_seconds'],'counts':s['counts'],'timing_breakdown':s['details'].get('timing_breakdown','NOT_RECORDED')} for s in data['stages']],'catalog_samples':samples,'region_samples':region,'ordered_index_query_plans':plans,'serialize_first_1000_records_seconds':serialize,'serialize_first_1000_records_bytes':len(encoded),'graph':graph,'coordinator_peak_rss_bytes_at_boundary':rss(resource.RUSAGE_SELF)})
            print(json.dumps({'dataset':entry['label'],'state':'MEASURED'}),flush=True)
    try:chip=subprocess.check_output(['/usr/sbin/sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
    except (OSError,subprocess.CalledProcessError):chip='NOT_RECORDED'
    try:
        from rtree import core
        spatial_version=core.rt.SIDX_Version().decode()
    except Exception:spatial_version='NOT_RECORDED'
    build_path=args.binary.parent/'build_receipt.json';build_receipt=json.loads(build_path.read_text()) if build_path.is_file() else {'status':'NOT_RUN_NATIVE_BUILD_UNAVAILABLE'}
    if build_receipt.get('binary',{}).get('sha256') and build_receipt['binary']['sha256']!=digest(args.binary.read_bytes()):raise RuntimeError('NATIVE_BUILD_BINARY_BINDING_MISMATCH')
    result={'status':'MEASURED_PARITY_PRESERVED','pipeline':str(args.pipeline),'pipeline_receipt_sha256':digest((args.pipeline/'receipt.json').read_bytes()),'datasets':datasets,'hardware':{'platform':platform.platform(),'architecture':platform.machine(),'cpu':chip,'logical_cpu_count':os.cpu_count()},'versions':{n:importlib.metadata.version(n) for n in ['rtree','shapely','sexpdata','gerbonara']},'libspatialindex_version':spatial_version,'sqlite_version':sqlite3.sqlite_version,'geos_version':__import__('shapely').geos_version_string,'native_build_receipt':build_receipt,'source_sha256':{p:digest((ROOT/p).read_bytes()) for p in ['tools/consolidation_bench.py','src/revision_catalog.py','src/catalog_selection.py','src/native_graph_adapter.py']},'catalog_storage':{'sqlite_bytes':(args.pipeline/'catalog/catalog.sqlite').stat().st_size,'payload_bytes':sum(p.stat().st_size for p in (args.pipeline/'catalog/payloads').iterdir() if p.is_file()),'payload_files':sum(p.is_file() for p in (args.pipeline/'catalog/payloads').iterdir())},'decisions':{'artifact_catalog':'ADOPT within declared consistency scope','ordered_identity_range':'KEEP_REFERENCE: SQLite indexed query plans verified','spatial_candidates':'KEEP_REFERENCE: native libspatialindex through Rtree','exact_geometry':'KEEP_REFERENCE: GEOS; independent acceptance unchanged','gfs_graph':'SHADOW_ONLY: parity; include admission/process/transfer costs' if comparisons else 'NOT_RUN: no native comparison receipts','custom_cpp_btree_rtree':'DEFER: no admitted implementation/package established'},'limitations':['Three repetitions per workload; not production scalability evidence.','OS caches are not forcibly flushed; no cold-disk benchmark established.','Python RSS is cumulative process high-water at boundaries; native probe memory is isolated child high-water.','Browser DOM/draw timings must be collected separately from actual rendered UI.','Graph adjacency is not electrical, permission or manufacturing acceptance.']}
    (run/'result.json').write_bytes(canonical(result));print(json.dumps({'run':str(run),'status':result['status']}),flush=True)
if __name__=='__main__':main()
