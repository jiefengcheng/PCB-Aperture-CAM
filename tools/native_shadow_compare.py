"""Compare actual pinned gfs typed reads with the catalog relation snapshot."""
from pathlib import Path
import argparse,datetime,json,platform,resource,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.native_graph_adapter import NativeGraphAdapter
from src.revision_catalog import canonical,digest
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('pipeline',type=Path);ap.add_argument('--dataset',default='synthetic_before');ap.add_argument('--layer');ap.add_argument('--binary',type=Path,default=ROOT/'out/consolidation/native/pcb_graph_shadow');args=ap.parse_args()
    path=args.pipeline/(args.dataset+'.json');raw=path.read_bytes();data=json.loads(raw)
    all_relations=data['topology']['relations'];relations=[r for r in all_relations if args.layer is None or r['witness']['layer']==args.layer];snapshot=data['catalog_revision']
    run=ROOT/'out/consolidation'/datetime.datetime.now(datetime.timezone.utc).strftime('shadow_%Y%m%dT%H%M%S_%fZ');run.mkdir()
    adapter=NativeGraphAdapter(args.binary)
    build=adapter.materialize(run/'materialization',snapshot,'physical_contact',all_relations,layer=args.layer)
    identities=sorted({r[k] for r in relations for k in ('source','target')})
    reference={uid:set() for uid in identities}
    for r in relations:reference[r['source']].add(r['target'])
    queries=[];failures=[];started=time.perf_counter()
    for offset in range(0,len(identities),256):
        seeds=identities[offset:offset+256];q=adapter.query(run/'materialization',snapshot,seeds,timeout_seconds=60,expected_layer=args.layer)
        actual={uid:set() for uid in seeds}
        for r in q['records']:actual[r['source']].add(r['target'])
        if not q['complete']:failures.append({'seeds':seeds,'error':q['status']})
        for uid in seeds:
            if actual[uid]!=reference[uid]:failures.append({'seed':uid,'missing':sorted(reference[uid]-actual[uid]),'unexpected':sorted(actual[uid]-reference[uid])})
        queries.append({k:v for k,v in q.items() if k!='records'})
    elapsed=time.perf_counter()-started
    samples=[]
    for condition in ['first_adapter_read_after_parity','warm_repeat_1','warm_repeat_2']:
        seeds=identities[:min(16,len(identities))];start=time.perf_counter();q=adapter.query(run/'materialization',snapshot,seeds,expected_layer=args.layer)
        samples.append({'condition':condition,'elapsed_seconds':time.perf_counter()-start,'status':q['status'],'result_sha256':q.get('result_sha256'),'note':'Includes manifest hashing, process start, native DB reopen, decoding; OS caches not forcibly flushed.'})
    sample_seeds=set(identities[:min(32,len(identities))]);focus=data.get('selection',{}).get('target_id') if data.get('selection') else None
    if focus in reference:sample_seeds.add(focus)
    for obj in data['inventory']['objects']:
        if obj.get('reference')=='J22' and obj.get('pin')=='1' and obj['id'] in reference:sample_seeds.add(obj['id'])
    actual_samples={direction:adapter.query(run/'materialization',snapshot,sorted(sample_seeds),direction=direction,expected_layer=args.layer) for direction in ['out','in']}
    result={'adapter_source_sha256':digest((ROOT/'src/native_graph_adapter.py').read_bytes()),'producer_source_sha256':digest(Path(__file__).read_bytes()),'layer_scope':args.layer or 'ALL_RECORDED_LAYERS','actual_query_samples':actual_samples,'status':'PARITY_PASS' if not failures else 'PARITY_FAIL','scope':'all materialized identities, outgoing typed adjacency, complete sets; other capabilities independently qualified','source_pipeline_file':str(path),'source_pipeline_sha256':digest(raw),'source_snapshot':snapshot,'binary_sha256':adapter.binary_hash,'native_build':build,'identity_count':len(identities),'relation_occurrences':len(relations),'query_receipts':queries,'failures':failures,'full_parity_seconds':elapsed,'samples':samples,'hardware':platform.platform()+' '+platform.machine(),'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rss_scope':'Python coordinator high-water mark on macOS; child native memory not measured here','backend_decision':'SHADOW_ONLY','limitations':['No cold-cache assertion; no cache flush performed.','No C++ speed advantage established by this parity run.','No acceptance or edit authority transferred to native graph.']}
    (run/'result.json').write_bytes(canonical(result));print(json.dumps({'run':str(run),'status':result['status'],'identities':len(identities),'failures':len(failures)}),flush=True)
if __name__=='__main__':main()
