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

def _enclosures(raw,store):
 from src.source_common_frame import discover
 original,parser,oracle=p.source_profile.parse_source(raw)
 originals={tuple(span):i for i,span in parser.spans.items()}
 current=raw;removed=[];removed_spans=set();rounds=[];certificate=None
 while True:
  # Removing a drawing rectangle may expose another complete enclosing trace.
  # Reapply the unchanged whole-source predicate; never choose an inner ROI.
  binding=p.build_source(store,current);scene=store.get_json(binding['scene_ref'],kind='scene')
  native,current_parser,_=p.source_profile.parse_source(current)
  source=p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in native.objects),1,-1,origin=(0,0))
  frame,found=discover(source,p.digest(current),scene,store)
  if certificate is None:certificate=found
  ids={s for row in found.get('frame_source_rows',[])for s in row['source_ids']}
  if frame is None:
   if ids:raise ValueError('ASSEMBLY_FRAME_CERTIFICATE_WITHOUT_FRAME')
   break
  if not ids:raise ValueError('ASSEMBLY_ENCLOSURE_REMOVAL_MUST_PROGRESS')
  spans={tuple(map(int,re.search(r':bytes:(\d+):(\d+)$',s).groups())):s for s in ids}
  if len(spans)!=len(ids):raise ValueError('ASSEMBLY_DUPLICATE_SOURCE_SPAN')
  if removed_spans.intersection(spans):raise ValueError('ASSEMBLY_ENCLOSURE_REMOVAL_MUST_PROGRESS')
  body=bytearray(current);changes=[]
  for i,obj in enumerate(native.objects):
   a,b=current_parser.spans[i]
   if (a,b)not in spans:continue
   if (a,b)not in originals:raise ValueError('ASSEMBLY_ORIGINAL_SOURCE_SPAN_MISSING')
   if not obj.polarity_dark or not isinstance(obj,(p.go.Line,p.go.Arc)):raise ValueError('ASSEMBLY_POSITIVE_NATIVE_STROKE_REQUIRED')
   command=current[a:b];matches=list(re.finditer(rb'D(0?)1\*',command))
   if len(matches)!=1:raise ValueError('ASSEMBLY_EXPLICIT_DRAW_REQUIRED')
   m=matches[0];replacement=b'D'+m[1]+b'2*'
   if len(replacement)!=m.end()-m.start():raise ValueError('ASSEMBLY_OPERATION_LENGTH_CHANGED')
   body[a+m.start():a+m.end()]=replacement
   changes.append(dict(original_ordinal=originals[(a,b)],source_id=f'{p.digest(raw)}:bytes:{a}:{b}',source_span=[a,b],original_command_sha256=p.digest(raw[a:b]),replacement_command_sha256=p.digest(bytes(body[a:b]))))
  if len(changes)!=len(ids):raise ValueError('ASSEMBLY_ENCLOSURE_OCCURRENCE_MISSING')
  following=bytes(body)
  if len(following)!=len(raw):raise ValueError('ASSEMBLY_FILE_LENGTH_CHANGED')
  # Each round consumes previously unremoved original native occurrences.
  # Thus the original occurrence count bounds the process without a search.
  removed.extend(changes);removed_spans.update(spans)
  if len(removed)>len(original.objects):raise ValueError('ASSEMBLY_ENCLOSURE_REMOVAL_MUST_PROGRESS')
  rounds.append(dict(input_source_sha256=p.digest(current),output_source_sha256=p.digest(following),removed_original_ordinals=sorted(r['original_ordinal']for r in changes),enclosure_certificate=found))
  current=following
 assembled=current;removed.sort(key=lambda r:r['original_ordinal'])
 if len(assembled)!=len(raw):raise ValueError('ASSEMBLY_FILE_LENGTH_CHANGED')
 retained=prove_atoms(raw,assembled,{r['original_ordinal']for r in removed})
 proof=dict(schema='original-to-assembled-gerber/1',status='PASS',policy=POLICY,raw_source_sha256=p.digest(raw),assembled_source_sha256=p.digest(assembled),source_objects=len(original.objects),removed_objects=len(removed),retained_objects=len(retained),removed=removed,retained_atom_proofs=retained,enclosure_certificate=certificate,disposition='CONFIRMED_ENCLOSURE_REMOVED'if removed else'NO_UNAMBIGUOUS_ENCLOSURE_UNCHANGED',method='Only certified positive outer-stroke D01 draws become D02 moves; all other bytes unchanged and all retained native atoms identical',raw_input_modified=False)
 # Preserve the existing single/no-frame receipt exactly. Nested cases also
 # bind every intermediate source and the final absence of a certified frame.
 if len(rounds)>1:proof.update(enclosure_rounds=rounds,final_enclosure_certificate=found)
 return assembled,proof

def reconstruct(raw,store,scope=None):
 from .pcb_artwork_scope import REGISTERED,select
 if scope is None:
  if any(p.digest(raw)==s['source_sha256']for s in REGISTERED.values()):raise ValueError('PCB_SCOPE_AUTHORIZATION_AND_OUTLINE_REQUIRED')
  return _enclosures(raw,store)
 contract,outline=scope
 scoped,selection=select(raw,outline,contract)
 assembled,enclosure=_enclosures(scoped,store)
 original,parser,_=p.source_profile.parse_source(raw)
 ordinals={tuple(span):i for i,span in parser.spans.items()}
 removed=set(selection['excluded_original_ordinals'])
 removed.update(ordinals[tuple(row['source_span'])]for row in enclosure['removed'])
 if not set(selection['boundary_marker_original_ordinals'])<=removed:raise ValueError('PCB_SCOPE_BOUNDARY_MARKER_MUST_BE_REMOVED_AS_CONFIRMED_FRAME')
 retained=prove_atoms(raw,assembled,removed)
 proof=dict(schema='original-to-assembled-gerber/2',status='PASS',policy=POLICY,
  raw_source_sha256=p.digest(raw),assembled_source_sha256=p.digest(assembled),
  source_objects=len(original.objects),removed_objects=len(removed),retained_objects=len(retained),
  removed_original_ordinals=sorted(removed),retained_atom_proofs=retained,
  pcb_scope=selection,post_scope_enclosure=enclosure,
  disposition='APPROVED_PCB_SCOPE_AND_CONFIRMED_ENCLOSURE_REMOVAL',
  method='Excluded native plots become moves; retained native atoms and original drawing order unchanged',
  raw_input_modified=False)
 return assembled,proof

def verify_payload(raw,assembled,receipt,store,scope=None):
 expected,proof=reconstruct(raw,store,scope)
 if expected!=assembled or p.canonical(proof)!=p.canonical(receipt):raise ValueError('ASSEMBLY_AUTHORIZED_CHANGE_OR_PROOF_CHANGED')
 return proof

def _producer(run):
 from .guard import producer_files,sha
 result=dict(schema='enclosure-assembly-producer/1',files={str(f):sha(f)for f in producer_files()},raw_source_sha256=sha(run/'original.gbr'),inventory_sha256=sha(run/'INPUT_INVENTORY.json'))
 from .pcb_artwork_scope import captured
 if captured(run)is not None:result['pcb_scope_inputs']={str(run/name):sha(run/name)for name in('PCB_SCOPE.json','pcb_outline.gbr')}
 return result

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
 scope_inputs=[run/name for name in('PCB_SCOPE.json','pcb_outline.gbr')]if'pcb_scope'in receipt else[]
 if bool(scope_inputs)!=bool(captured.get('pcb_scope_inputs')):raise ValueError('ASSEMBLY_SCOPE_PRODUCER_BINDING_CHANGED')
 return dict(schema='verified-source-assembly-binding/1',policy=POLICY,assembly_run=str(run.resolve()),raw_source_sha256=receipt['raw_source_sha256'],assembled_source_sha256=receipt['assembled_source_sha256'],removed_objects=receipt['removed_objects'],files={str(f.resolve()):p.digest(f.read_bytes())for f in [run/'ASSEMBLY_PRODUCER.json',run/'INPUT_INVENTORY.json',run/'original.gbr',run/'assembled.gbr',run/'RECEIPT.json',*scope_inputs,*[run/'audits'/(m+'.json')for m in('construct','1','2')],*[run/'audits'/('execution_'+m+'.json')for m in('construct','1','2')]]})

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
 from .pcb_artwork_scope import captured as scope_inputs
 body,receipt=reconstruct((run/'original.gbr').read_bytes(),p.Store(run/'runtime'),scope_inputs(run))
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
