"""Client-authorized illustrative enclosure removal before growth.

The original file remains immutable. Every retained native plotting atom must be
identical, including polarity and modal state. No buffering or geometric cutting
is used to delete the enclosure.
"""
import json,re,sys,time,os
from pathlib import Path
from . import pipeline as p

POLICY='REMOVE_CONFIRMED_ILLUSTRATIVE_OUTER_ENCLOSURE/1'

def prove_atoms(raw,assembled,removed_ordinals):
 original,parser,oracle=p.source_profile.parse_source(raw)
 actual,actual_parser,actual_oracle=p.source_profile.parse_source(assembled)
 expected=[(i,o)for i,o in enumerate(original.objects)if i not in removed_ordinals]
 if len(actual.objects)!=len(expected):raise ValueError('ASSEMBLY_UNRELATED_OPERATION_COUNT_CHANGED')
 if oracle!=actual_oracle:raise ValueError('ASSEMBLY_COORDINATE_ORACLE_CHANGED')
 retained=[]
 for (i,old),new in zip(expected,actual.objects):
  a,_=p.source_profile.object_geometry(old);b,_=p.source_profile.object_geometry(new)
  if type(old)!=type(new)or old.polarity_dark!=new.polarity_dark or p.to_wkb(a)!=p.to_wkb(b):raise ValueError('ASSEMBLY_RETAINED_NATIVE_ATOM_CHANGED:'+str(i))
  retained.append(dict(original_ordinal=i,kind=type(old).__name__,polarity_dark=old.polarity_dark,geometry_sha256=p.digest(p.to_wkb(a))))
 return retained

def reconstruct(raw,store):
 from src.source_common_frame import discover
 binding=p.build_source(store,raw);scene=store.get_json(binding['scene_ref'],kind='scene')
 original,parser,oracle=p.source_profile.parse_source(raw)
 source=p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in original.objects),1,-1,origin=(0,0))
 frame,certificate=discover(source,p.digest(raw),scene,store)
 ids={s for row in certificate.get('frame_source_rows',[])for s in row['source_ids']}
 spans={tuple(map(int,re.search(r':bytes:(\d+):(\d+)$',s).groups())):s for s in ids}
 if len(spans)!=len(ids):raise ValueError('ASSEMBLY_DUPLICATE_SOURCE_SPAN')
 body=bytearray(raw);removed=[]
 for i,obj in enumerate(original.objects):
  a,b=parser.spans[i]
  if (a,b)not in spans:continue
  if not obj.polarity_dark or not isinstance(obj,(p.go.Line,p.go.Arc)):raise ValueError('ASSEMBLY_POSITIVE_NATIVE_STROKE_REQUIRED')
  command=raw[a:b];matches=list(re.finditer(rb'D(0?)1\*',command))
  if len(matches)!=1:raise ValueError('ASSEMBLY_EXPLICIT_DRAW_REQUIRED')
  m=matches[0];replacement=b'D'+m[1]+b'2*'
  if len(replacement)!=m.end()-m.start():raise ValueError('ASSEMBLY_OPERATION_LENGTH_CHANGED')
  body[a+m.start():a+m.end()]=replacement
  removed.append(dict(original_ordinal=i,source_id=spans[(a,b)],source_span=[a,b],original_command_sha256=p.digest(command),replacement_command_sha256=p.digest(bytes(body[a:b]))))
 if len(removed)!=len(ids):raise ValueError('ASSEMBLY_ENCLOSURE_OCCURRENCE_MISSING')
 assembled=bytes(body)
 if len(assembled)!=len(raw):raise ValueError('ASSEMBLY_FILE_LENGTH_CHANGED')
 retained=prove_atoms(raw,assembled,{r['original_ordinal']for r in removed})
 proof=dict(schema='original-to-assembled-gerber/1',status='PASS',policy=POLICY,raw_source_sha256=p.digest(raw),assembled_source_sha256=p.digest(assembled),source_objects=len(original.objects),removed_objects=len(removed),retained_objects=len(retained),removed=removed,retained_atom_proofs=retained,enclosure_certificate=certificate,disposition='CONFIRMED_ENCLOSURE_REMOVED'if removed else'NO_UNAMBIGUOUS_ENCLOSURE_UNCHANGED',method='Only certified positive outer-stroke D01 draws become D02 moves; all other bytes unchanged and all retained native atoms identical',raw_input_modified=False)
 return assembled,proof

def verify_payload(raw,assembled,receipt,store):
 expected,proof=reconstruct(raw,store)
 if expected!=assembled or p.canonical(proof)!=p.canonical(receipt):raise ValueError('ASSEMBLY_AUTHORIZED_CHANGE_OR_PROOF_CHANGED')
 return proof

def _producer(run):
 from .guard import producer_files,sha
 return dict(schema='enclosure-assembly-producer/1',files={str(f):sha(f)for f in producer_files()},raw_source_sha256=sha(run/'original.gbr'),inventory_sha256=sha(run/'INPUT_INVENTORY.json'))

def verify_job(run):
 """Recheck immutable assembly proof bindings; native proofs are separate workers."""
 captured=p.load(run/'ASSEMBLY_PRODUCER.json')
 if captured!=_producer(run):raise ValueError('ASSEMBLY_PRODUCER_OR_ORIGINAL_CHANGED')
 receipt=p.load(run/'RECEIPT.json');body=(run/'assembled.gbr').read_bytes()
 if receipt['status']!='PASS'or receipt['policy']!=POLICY or receipt['raw_source_sha256']!=p.digest((run/'original.gbr').read_bytes())or receipt['assembled_source_sha256']!=p.digest(body):raise ValueError('ASSEMBLY_SOURCE_HASH_CHANGED')
 proofs=[p.load(run/'audits'/(m+'.json'))for m in('construct','1','2')]
 if any(v!=proofs[0]for v in proofs)or proofs[0]!=dict(status='PASS',receipt_sha256=p.digest(p.canonical(receipt)),producer_sha256=p.digest(p.canonical(captured))):raise ValueError('ASSEMBLY_PAIRED_PROOFS_CHANGED')
 executions=[p.load(run/'audits'/('execution_'+m+'.json'))for m in('construct','1','2')]
 if len({row['pid']for row in executions})!=3 or any(row['mode']!=m or row['proof_sha256']!=p.digest(p.canonical(proofs[0]))for row,m in zip(executions,('construct','1','2'))):raise ValueError('ASSEMBLY_SEPARATE_NATIVE_WORKERS_REQUIRED')
 return dict(schema='verified-source-assembly-binding/1',policy=POLICY,assembly_run=str(run.resolve()),raw_source_sha256=receipt['raw_source_sha256'],assembled_source_sha256=receipt['assembled_source_sha256'],removed_objects=receipt['removed_objects'],files={str(f.resolve()):p.digest(f.read_bytes())for f in [run/'ASSEMBLY_PRODUCER.json',run/'INPUT_INVENTORY.json',run/'original.gbr',run/'assembled.gbr',run/'RECEIPT.json',*[run/'audits'/(m+'.json')for m in('construct','1','2')],*[run/'audits'/('execution_'+m+'.json')for m in('construct','1','2')]]})

def attach(run,assembly):
 p.save(run/'SOURCE_ASSEMBLY_BINDING.json',verify_job(assembly))

def verify_run(run):
 path=run/'SOURCE_ASSEMBLY_BINDING.json'
 if not path.exists():return None
 binding=p.load(path);assembly=Path(binding['assembly_run'])
 if assembly.resolve()!=run.parent.resolve()/'assembly':raise ValueError('ASSEMBLY_JOB_LOCAL_AUTHORITY_REQUIRED')
 if p.canonical(binding)!=p.canonical(verify_job(assembly)):raise ValueError('ASSEMBLY_BOUND_INPUT_CHANGED')
 if p.load(run/'source.json')['source_ref']['sha256']!=binding['assembled_source_sha256']:raise ValueError('ASSEMBLY_WORKING_SOURCE_CHANGED')
 if (run/'input_inventory.json').exists():
  inventory=p.load(run/'input_inventory.json')
  if inventory['files'][inventory['selected']]!=binding['raw_source_sha256']:raise ValueError('ASSEMBLY_RAW_INVENTORY_CHANGED')
 return binding

def main():
 p.configure();run=Path(sys.argv[1]);mode=sys.argv[2];start=time.monotonic()
 from .guard import install_read_fence
 install_read_fence(run)
 captured=p.load(run/'ASSEMBLY_PRODUCER.json')
 if captured!=_producer(run):raise ValueError('ASSEMBLY_PRODUCER_OR_ORIGINAL_CHANGED')
 body,receipt=reconstruct((run/'original.gbr').read_bytes(),p.Store(run/'runtime'))
 if mode=='construct':
  (run/'assembled.gbr').write_bytes(body);p.save(run/'RECEIPT.json',receipt)
 elif mode in('1','2'):
  if body!=(run/'assembled.gbr').read_bytes()or p.canonical(receipt)!=p.canonical(p.load(run/'RECEIPT.json')):raise ValueError('ASSEMBLY_FRESH_NATIVE_RECONSTRUCTION_CHANGED')
 else:raise ValueError('ASSEMBLY_UNKNOWN_MODE')
 if captured!=_producer(run):raise ValueError('ASSEMBLY_PRODUCER_CHANGED_DURING_CHECK')
 p.save(run/'audits'/(mode+'.json'),dict(status='PASS',receipt_sha256=p.digest(p.canonical(receipt)),producer_sha256=p.digest(p.canonical(captured))))
 p.save(run/'audits'/('execution_'+mode+'.json'),dict(mode=mode,pid=os.getpid(),proof_sha256=p.digest((run/'audits'/(mode+'.json')).read_bytes()),seconds=time.monotonic()-start))
 print(json.dumps(dict(status='PASS',mode=mode,seconds=time.monotonic()-start,removed_objects=receipt['removed_objects'],retained_objects=receipt['retained_objects'])),flush=True)

if __name__=='__main__':main()
