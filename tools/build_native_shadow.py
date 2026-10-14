"""Compile exact admitted copies into a new versioned PCB-owned build directory."""
from pathlib import Path
import argparse,concurrent.futures,datetime,hashlib,json,re,shutil,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pin',type=Path,default=ROOT/'contracts/native_gfs_source_pin.json');ap.add_argument('--source-snapshot',type=Path,default=ROOT/'out/consolidation/native/source');args=ap.parse_args()
    pin=json.loads(args.pin.read_text());source=args.source_snapshot if args.source_snapshot.is_dir() else Path(pin['source_root'])
    dest=ROOT/'out/consolidation'/datetime.datetime.now(datetime.timezone.utc).strftime('native_build_%Y%m%dT%H%M%S_%fZ');dest.mkdir()
    for rel,expected in pin['files'].items():
        path=(source/rel).resolve()
        if not path.is_relative_to(source.resolve()) or sha(path)!=expected:raise ValueError('PINNED_SOURCE_MISMATCH '+rel)
        target=dest/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    wrapper=dest/'source/pcb_graph_shadow.cc';wrapper.write_bytes((ROOT/'native/pcb_graph_shadow.cc').read_bytes())
    sources=re.search(r'^SRC = (.+)$',(dest/'source/Makefile').read_text(),re.M)[1].split()
    excluded=[rel for rel in sources if rel.startswith('src/gnn_')];sources=[rel for rel in sources if rel not in excluded]
    if any(rel not in pin['files'] for rel in sources):raise ValueError('UNPINNED_COMPILE_INPUT')
    compiler='/usr/bin/clang++';objects=dest/'objects';objects.mkdir();started=time.perf_counter()
    def compile_one(rel):
        output=objects/(rel.replace('/','_')+'.o');argv=[compiler,'-std=c++17','-O1','-DNDEBUG','-I',str(dest/'source/include'),'-c',str(dest/'source'/rel),'-o',str(output)]
        p=subprocess.run(argv,capture_output=True,text=True);(objects/(output.name+'.log')).write_text(p.stdout+p.stderr)
        return {'source':rel,'source_sha256':sha(dest/'source'/rel),'argv':argv,'exit_code':p.returncode,'object':str(output),'object_sha256':sha(output) if output.is_file() else None}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:compiled=list(pool.map(compile_one,sources))
    receipt={'source_commit':pin['head'],'source_dirty':pin['source_dirty'],'pin_sha256':sha(args.pin),'source_copy':str(dest/'source'),'wrapper_sha256':sha(wrapper),'builder_sha256':sha(Path(__file__)),'compiler':subprocess.check_output([compiler,'--version'],text=True),'excluded_tensor_sources':excluded,'compile':compiled,'license':'NOT_ESTABLISHED in admitted source snapshot; local qualification only','status':'COMPILE_FAILED'}
    binary=dest/'pcb_graph_shadow'
    if all(r['exit_code']==0 for r in compiled):
        argv=[compiler,'-std=c++17','-O1','-I',str(dest/'source/include'),str(wrapper),*[r['object'] for r in compiled],'-Wl,-dead_strip','-o',str(binary)]
        p=subprocess.run(argv,capture_output=True,text=True);(dest/'link.log').write_text(p.stdout+p.stderr);receipt['link']={'argv':argv,'exit_code':p.returncode};receipt['status']='BUILT' if p.returncode==0 else 'LINK_FAILED'
        if binary.is_file():receipt['binary']={'path':str(binary),'sha256':sha(binary)}
    receipt['elapsed_seconds']=time.perf_counter()-started;(dest/'build_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'run':str(dest),'status':receipt['status'],'binary':str(binary) if binary.is_file() else None}),flush=True)
    return receipt['status']!='BUILT'
if __name__=='__main__':raise SystemExit(main())
