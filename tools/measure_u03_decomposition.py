#!/usr/bin/env python3
"""Refine graph separators and validate saved decomposition certificates, no U03."""
import sys,json,hashlib,math,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
from src.u03_analysis.graph import elimination,minor_lower_bound,verify_minor_certificate,decomposition_separator,recursive_partition


def main():
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 from tools.pcb_workspace import configure
 work=configure();out=a.output.resolve();assert out.is_relative_to(work) and not out.exists();out.mkdir(parents=True);start=time.monotonic();used={}
 def load(p):
  data=p.read_bytes();used[str(p.absolute())]=hashlib.sha256(data).hexdigest();return json.loads(data)
 def save(n,r):
  with (out/n).open('x') as f:json.dump(r,f,sort_keys=True,indent=2);f.write('\n')
 summary=load(a.study/'SUMMARY.json');graph=load(a.study/'GRAPH.json')
 for p,h in summary['input_files'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
 results={}
 for label,key in [('broad','broad_edges'),('tight','edges')]:
  adj={i:set() for i in range(len(graph['groups']))}
  for v,w in graph[key]:adj[v].add(w);adj[w].add(v)
  saved=load(a.study/(label.upper()+'_MEASUREMENTS.json'));parts=[]
  for component in saved['components']:
   nodes=set(component['nodes']);g={v:adj[v]&nodes for v in nodes};d=elimination(g);lower=minor_lower_bound(g);assert verify_minor_certificate(g,lower)
   assert d['width']==component['treewidth_upper'] and lower['width']==component['treewidth_lower']
   cut=decomposition_separator(g,d) if len(nodes)>1 else component['separator']
   # Actual bag-domain sizes, not just n * worst-case upper bound.
   domains={}
   for q in (2,4,8,16):
    domains[str(q)]=dict(maximum_bag_entries=q**(d['width']+1),summed_bag_entries=sum(q**len(b) for b in d['bags'].values()),maximum_message_entries=max([q**len(set(d['bags'][v])&set(d['bags'][parent])) for v,parent in d['parents'].items() if parent is not None],default=1))
   parts.append(dict(nodes=component['nodes'],size=len(nodes),treewidth_lower=lower['width'],treewidth_upper=d['width'],exact_treewidth_established=lower['width']==d['width'],lower_certificate_verified=True,separator=cut,finite_domain_table_sizes=domains))
  partition=recursive_partition(adj)
  result={k:v for k,v in saved.items() if k not in ('components','blocks')};result.update(components=parts,recursive_partition=partition)
  save(label.upper()+'_DECOMPOSITION.json',result);results[label]=result
  print(json.dumps(dict(stage=label,largest=parts[0]['size'],separator=parts[0]['separator']['size'],remaining=parts[0]['separator']['remaining_component_sizes'][:10],treewidth=[parts[0]['treewidth_lower'],parts[0]['treewidth_upper']],recursive_separator_max=max(partition['separator_sizes'],default=0),leaves=partition['leaf_count'],max_leaf_boundary=partition['maximum_leaf_boundary'])),flush=True)
 save('PROVENANCE.json',dict(mode='RETAINED_GRAPH_ANALYSIS',u03_operations_executed=0,source_study=str(a.study.absolute()),input_files=used,retained_inputs_reverified=len(summary['input_files']),implementation_files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).resolve(),ROOT/'src/u03_analysis/graph.py')},elapsed_seconds=time.monotonic()-start))
 for label,m in results.items():
  c=m['components'][0];print(label,json.dumps(dict(component_histogram=m['component_size_histogram'],largest_size=c['size'],treewidth=[c['treewidth_lower'],c['treewidth_upper']],separator=c['separator']['size'],leaf_limit=m['recursive_partition']['leaf_limit'],leaves=m['recursive_partition']['leaf_count'])))
 return 0
if __name__=='__main__':raise SystemExit(main())
