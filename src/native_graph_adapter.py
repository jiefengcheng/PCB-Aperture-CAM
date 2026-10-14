"""PCB-owned shadow adapter over a pinned gfs DB0 process.

Full identities and proof occurrences remain in sidecars/catalog records. VIDs
and numeric tags are local to one materialization, never global identities.
"""
from pathlib import Path
import json
import subprocess
import time
from .revision_catalog import canonical,digest,CatalogError

class NativeGraphAdapter:
    VERSION='pcb-gfs-shadow/2'
    def __init__(self,binary):
        self.binary=Path(binary).resolve()
        if not self.binary.is_file():raise CatalogError('NATIVE_BINARY_UNAVAILABLE')
        self.binary_hash=digest(self.binary.read_bytes())

    def materialize(self,folder,source_snapshot,relation_type,relations,*,local_tag=7,layer=None,hook=None):
        if not isinstance(local_tag,int) or not 0<=local_tag<255:raise CatalogError('INVALID_LOCAL_TAG')
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
        if any(r['type']!=relation_type for r in relations):raise CatalogError('RELATION_SCOPE_MISMATCH')
        input_occurrences=len(relations)
        if layer is not None:relations=[r for r in relations if r.get('witness',{}).get('layer')==layer]
        if not relations:raise CatalogError('NO_RELATIONS_IN_DECLARED_LAYER_SCOPE')
        identities=sorted({r[k] for r in relations for k in ('source','target')})
        if len(identities)>=4294967295:raise CatalogError('VID_RANGE_EXCEEDED')
        mapping={uid:i+1 for i,uid in enumerate(identities)}
        # Deduplicate physical adjacency only, retaining all proof occurrences.
        edges=sorted({(mapping[r['source']],mapping[r['target']]) for r in relations})
        (folder/'edges.csv').write_text(''.join(f'{a},{b}\n' for a,b in edges))
        (folder/'identities.json').write_bytes(canonical(mapping))
        (folder/'occurrences.json').write_bytes(canonical(relations))
        if hook:hook('FILES_STAGED',folder)
        started=time.perf_counter()
        p=subprocess.run([str(self.binary),'build',str((folder/'db').resolve()),str((folder/'edges.csv').resolve()),str(local_tag)],capture_output=True,text=True,timeout=60)
        if p.returncode:raise CatalogError('NATIVE_BUILD_FAILED: '+p.stderr)
        if hook:hook('INDEX_BUILT',folder)
        manifest={'adapter':self.VERSION,'source_snapshot':source_snapshot,'relation_type':relation_type,'local_tag':local_tag,'layer_scope':layer if layer is not None else 'ALL_RECORDED_LAYERS','input_occurrences':input_occurrences,'binary_sha256':self.binary_hash,'local_vid_policy':'sorted complete string identity, 1-based; materialization local','proof_occurrences':len(relations),'deduplicated_edges':len(edges),'elapsed_seconds':time.perf_counter()-started,'build_stdout':p.stdout,'files':{str(f.relative_to(folder)):digest(f.read_bytes()) for f in sorted(folder.rglob('*')) if f.is_file()}}
        temporary=folder/'manifest.pending';temporary.write_bytes(canonical(manifest));temporary.replace(folder/'manifest.json');return manifest

    def open(self,folder,expected_snapshot):
        folder=Path(folder)
        try:manifest=json.loads((folder/'manifest.json').read_text())
        except (OSError,ValueError) as exc:raise CatalogError('NATIVE_MATERIALIZATION_UNAVAILABLE') from exc
        if manifest['source_snapshot']!=expected_snapshot:raise CatalogError('STALE_NATIVE_SNAPSHOT')
        if manifest['binary_sha256']!=self.binary_hash:raise CatalogError('NATIVE_BINARY_MISMATCH')
        for rel,sha in manifest['files'].items():
            path=(folder/rel).resolve()
            if not path.is_relative_to(folder.resolve()):raise CatalogError('UNSAFE_MATERIALIZATION_PATH')
            if not path.is_file() or digest(path.read_bytes())!=sha:raise CatalogError('NATIVE_MATERIALIZATION_HASH_MISMATCH')
        return manifest,json.loads((folder/'identities.json').read_text())

    def query(self,folder,expected_snapshot,seeds,*,direction='out',limit_per_seed=1000,timeout_seconds=10,expected_layer=None):
        query_started=time.perf_counter()
        if direction not in ('in','out'):raise CatalogError('INVALID_DIRECTION')
        if not isinstance(limit_per_seed,int) or not 0<=limit_per_seed<=1000:raise CatalogError('INVALID_QUERY_LIMIT')
        if not 0<timeout_seconds<=60:raise CatalogError('INVALID_PROCESS_TIMEOUT')
        seeds=sorted(set(seeds))
        if len(seeds)>256:raise CatalogError('SEED_BUDGET_EXCEEDED')
        if digest(self.binary.read_bytes())!=self.binary_hash:raise CatalogError('NATIVE_BINARY_DRIFT')
        manifest,mapping=self.open(folder,expected_snapshot)
        if expected_layer is not None and manifest['layer_scope']!=expected_layer:raise CatalogError('NATIVE_LAYER_SCOPE_MISMATCH')
        reverse={v:k for k,v in mapping.items()}
        if any(seed not in mapping for seed in seeds):raise CatalogError('OBJECT_OUTSIDE_MATERIALIZATION')
        if not seeds:return {'status':'COMPLETE','complete':True,'records':[],'source_snapshot':expected_snapshot,'query':{'seeds':seeds,'direction':direction,'limit_per_seed':limit_per_seed,'expected_layer':expected_layer},'elapsed_seconds':time.perf_counter()-query_started}
        argv=[str(self.binary),'query',str((Path(folder)/'db').resolve()),str(manifest['local_tag']),direction,str(limit_per_seed),*[str(mapping[s]) for s in seeds]]
        started=query_started
        process_started=time.perf_counter()
        try:p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            return {'status':'CANCELLED_PROCESS_TIMEOUT','complete':False,'records':[],'source_snapshot':expected_snapshot,'query':{'seeds':seeds,'direction':direction,'limit_per_seed':limit_per_seed,'expected_layer':expected_layer},'elapsed_seconds':time.perf_counter()-started}
        process_seconds=time.perf_counter()-process_started
        if p.returncode:raise CatalogError('NATIVE_QUERY_FAILED: '+p.stderr)
        rows=[];ends={}
        try:
            for line in p.stdout.splitlines():
                fields=line.split()
                if fields[0]=='END':
                    seed_index=int(fields[1]);state=fields[2]
                    if seed_index in ends or state not in ('COMPLETE','TRUNCATED'):raise ValueError('bad completion marker')
                    ends[seed_index]=state
                else:
                    seed_index,a,b,tag=map(int,fields)
                    if tag!=manifest['local_tag'] or not 0<=seed_index<len(seeds):raise ValueError('scope/tag mismatch')
                    if (a if direction=='out' else b)!=mapping[seeds[seed_index]]:raise ValueError('seed scope mismatch')
                    rows.append({'seed':seeds[seed_index],'source':reverse[a],'target':reverse[b],'type':manifest['relation_type']})
            if set(ends)!=set(range(len(seeds))):raise ValueError('missing completion markers')
        except (ValueError,KeyError,IndexError) as exc:raise CatalogError('INVALID_NATIVE_RESULT: '+str(exc)) from exc
        self.open(folder,expected_snapshot)  # reject ordinary file mutation during the process read
        rows=sorted(rows,key=lambda r:(r['seed'],r['source'],r['target']))
        status='COMPLETE' if all(s=='COMPLETE' for s in ends.values()) else 'TRUNCATED'
        return {'query':{'seeds':seeds,'direction':direction,'limit_per_seed':limit_per_seed,'expected_layer':expected_layer},'native_process_seconds':process_seconds,'adapter':self.VERSION,'status':status,'complete':status=='COMPLETE','records':rows,'source_snapshot':expected_snapshot,'relation_type':manifest['relation_type'],'direction':direction,'layer_scope':manifest['layer_scope'],'local_vids_exposed':False,'elapsed_seconds':time.perf_counter()-started,'result_sha256':digest(canonical(rows)),'scope':'typed adjacency only; proof occurrences remain in catalog/occurrences.json; no edit authority'}
