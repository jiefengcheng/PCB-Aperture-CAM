"""Retain a completed width search; freshly verify it and finish the corrected stage."""
import argparse,ast,datetime,json,os,subprocess,uuid
from pathlib import Path
from . import pipeline as p
from .guard import seal,producer_files
from .run import Coordinator,CONNECTED
from .workspace import configure

MODE='INCREMENTAL_REUSED_CONNECTED_WIDTH_SEARCH'
sha=lambda f:p.digest(Path(f).read_bytes())
load=lambda f:json.loads(Path(f).read_bytes())

def worker_same(before,after):
 old="name=='t04'and os.environ.get('U05_WORKER_MODE')!='construct'"
 new="name=='t04'and(os.environ.get('U05_WORKER_MODE')!='construct'or(run/'REUSED_WIDTH_BINDING.json').exists())"
 if new not in after:raise ValueError('WIDTH_ADOPTION_WORKER_GUARD_MISSING')
 after=after.replace("name=='t04'and os.environ.get('U05_WORKER_MODE')=='construct'and not(run/'REUSED_WIDTH_BINDING.json').exists()","name=='t04'and os.environ.get('U05_WORKER_MODE')=='construct'")
 if ast.dump(ast.parse(before),include_attributes=False)!=ast.dump(ast.parse(after.replace(new,old)),include_attributes=False):raise ValueError('WIDTH_ADOPTION_UPSTREAM_WORKER_CHANGED')

def original_binding(run):
 binding=load(run/'PRODUCER_BINDING.json')
 for name,expected in {**binding['files'],**binding['job_inputs']}.items():
  if sha(name)!=expected:raise ValueError('WIDTH_ADOPTION_ORIGINAL_PRODUCER_CHANGED:'+name)
 if sha(run/'source.json')!=binding['source_binding_sha256']:raise ValueError('WIDTH_ADOPTION_ORIGINAL_SOURCE_CHANGED')
 return binding

def inspect(old):
 old=Path(old);work=configure()
 if not old.is_absolute()or old.name!='connected'or'..'in old.parts or not old.is_relative_to(work/'operator_routes/gerber_u05_incremental_legacy'):raise ValueError('EXPLICIT_RETAINED_CONNECTED_WIDTH_RUN_REQUIRED')
 original=original_binding(old);root=Path(os.path.commonpath(list(original['files'])));state=load(old.parent/'STATUS.current.json');source_sha=load(old/'source.json')['source_ref']['sha256']
 allowed={'SOURCE_REVISION.json','src/gerber_u05/guard.py','src/gerber_u05/component_finish.py','src/gerber_u05/render.py'};known=set()
 for name,expected in original['files'].items():
  relative=Path(name).relative_to(root).as_posix();known.add(relative)
  if sha(p.ROOT/relative)==expected:continue
  if relative=='src/gerber_u05/worker.py':worker_same(Path(name).read_text(),(p.ROOT/relative).read_text())
  elif relative not in allowed:raise ValueError('WIDTH_ADOPTION_UPSTREAM_DEPENDENCY_CHANGED:'+relative)
 extras={f.relative_to(p.ROOT).as_posix()for f in producer_files()}-known
 if extras-{'src/gerber_u05/width_adoption.py'}:raise ValueError('WIDTH_ADOPTION_UNDECLARED_PRODUCER')
 legacy=old.parent/'legacy';legacy_seal=original_binding(legacy);inherited=load(legacy/'REUSED_LEGACY_BINDING.json')['original']
 if sha(legacy/'REUSED_LEGACY_BINDING.json')!=legacy_seal['job_inputs'][str(legacy/'REUSED_LEGACY_BINDING.json')]:raise ValueError('WIDTH_ADOPTION_LEGACY_AUTHORITY_CHANGED')
 ancestor=Path(inherited['original_run']);ancestor_seal=original_binding(ancestor)
 if sha(ancestor/'PRODUCER_BINDING.json')!=inherited['original_producer_binding_sha256']:raise ValueError('WIDTH_ADOPTION_ANCESTOR_BINDING_CHANGED')
 for name,expected in inherited['files'].items():
  if sha(ancestor/name)!=expected or sha(legacy/name)!=expected:raise ValueError('WIDTH_ADOPTION_INHERITED_PREFIX_CHANGED:'+name)
 records=dict(inherited['original_checks'],**state['checks'])
 required=['legacy_'+s+'_'+m for s in('t01','t03','t04','t02','t05')for m in('construct','1','2')]+['legacy_t01_supplement_'+m for m in('1','2')]+['legacy_legacy_export_'+m for m in('construct','1','2')]+['reference_remedy_'+m for m in('construct','1','2')]+['connected_'+s+'_'+m for s in('t01','t03')for m in('construct','1','2')]
 if len(required)!=29 or any(records.get(k,{}).get('status')!='PASS'or records[k].get('returncode')!=0 for k in required):raise ValueError('WIDTH_ADOPTION_COMPLETED_NATIVE_PREFIX_REQUIRED')
 for folder,stages in((legacy,('t01','t03','t04','t02','t05')),(old,('t01','t03'))):
  for stage in stages:
   proofs=[load(folder/'audits'/stage/(m+'.json'))for m in('construct','1','2')]
   expected=inherited['original_producer_binding_sha256']if folder==legacy and stage in inherited['stages']else sha(folder/'PRODUCER_BINDING.json')
   if proofs[0]!=proofs[1]or proofs[0]!=proofs[2]or proofs[0]['status']!='PASS'or proofs[0]['producer_binding_sha256']!=expected or proofs[0]['source_sha256']!=source_sha or proofs[0]['candidate_sha256']!=sha(folder/(stage+'.json')):raise ValueError('WIDTH_ADOPTION_NATIVE_STAGE_PROOF_CHANGED')
   prefix=folder.name+'_'+stage
   if records[prefix+'_1']['pid']==records[prefix+'_2']['pid']:raise ValueError('WIDTH_ADOPTION_EVALUATIONS_NOT_SEPARATE')
 for folder in(legacy,old.parent/'reference'):
  modes=('1','2')if folder==legacy else('construct','1','2');proofs=[load(folder/'export'/('proof_'+m+'.json'))for m in modes]
  if any(v!=proofs[0]for v in proofs)or proofs[0]['status']!='PASS'or proofs[0]['generated_sha256']!=sha(folder/'export/top.art.gbr'):raise ValueError('WIDTH_ADOPTION_NATIVE_REFERENCE_CHANGED')
 supplemental=[load(legacy/'audits/t01'/('supplement_'+m+'.json'))for m in('1','2')]
 if supplemental[0]!=supplemental[1]or supplemental[0]['status']!='PASS'or supplemental[0]['stage_result_sha256']!=sha(legacy/'t01.json')or supplemental[0]['source_sha256']!=source_sha:raise ValueError('WIDTH_ADOPTION_T01_SUPPLEMENT_CHANGED')
 if records['legacy_t01_supplement_1']['pid']==records['legacy_t01_supplement_2']['pid']:raise ValueError('WIDTH_ADOPTION_SUPPLEMENTS_NOT_SEPARATE')
 raw=load(old/'RAW_WIDTH_CHECKPOINT.json')
 if not raw['solution']['passed']or not raw['solution']['maximum_established']:raise ValueError('WIDTH_ADOPTION_SEARCH_NOT_COMPLETED')
 originals=[old,legacy,ancestor,old.parent/'reference'];source_roots=sorted({str(Path(os.path.commonpath(list(original_binding(f)['files']))))for f in originals})
 files={str(file):sha(file)for f in originals for file in [f/'PRODUCER_BINDING.json',f/'source.json']}
 for f in [old.parent/'STATUS.current.json',old/'RAW_WIDTH_CHECKPOINT.json',legacy/'REUSED_LEGACY_BINDING.json'] :files[str(f)]=sha(f)
 return dict(schema='completed-connected-width-search/1',original_run=str(old),original_source_root=str(root),original_source_roots=source_roots,original_checks={k:records[k]for k in required},retained_operation_count=29,raw_width_checkpoint_sha256=sha(old/'RAW_WIDTH_CHECKPOINT.json'),original_files=files,original_status=state['status'],old_T04_completion='NOT_CLAIMED; failed remedy remains FAIL; only its completed raw search is retained and freshly checked')

def verify(run):
 bound=load(Path(run)/'REUSED_WIDTH_BINDING.json');current=inspect(bound['original']['original_run'])
 if current!=bound['original']:raise ValueError('WIDTH_ADOPTION_ORIGINAL_EVIDENCE_CHANGED')
 for name,expected in bound['copied_files'].items():
  if sha(Path(run)/name)!=expected:raise ValueError('WIDTH_ADOPTION_COPIED_EVIDENCE_CHANGED:'+name)
 return bound

def prepare(old,job):
 from src.pcb_data_abi.input_directory import collect_raw
 old=Path(old);binding=inspect(old);inventory=load(old/'input_inventory.json');root,blobs,ignored=collect_raw(inventory['input_directory'])
 if {n:p.digest(b)for n,b in blobs.items()}!=inventory['files']or ignored!=inventory['ignored']:raise ValueError('WIDTH_ADOPTION_FRESH_INPUT_CUSTODY_CHANGED')
 run=job/'connected';run.mkdir()
 for folder in('runtime','source_snapshot','reference'):
  subprocess.run(['cp','-cR',str(old/folder),str(run/folder)],check=True)
 for name in('source.json','CLEARANCE_SNAPSHOT.json','REMEDY_POLICY_SNAPSHOT.json','REFERENCE_BINDING.json','RAW_WIDTH_CHECKPOINT.json','t01.json','t03.json'):
  (run/name).write_bytes((old/name).read_bytes())
 for stage in('t01','t03'):
  (run/'audits').mkdir(exist_ok=True);subprocess.run(['cp','-cR',str(old/'audits'/stage),str(run/'audits'/stage)],check=True)
 source=load(run/'source.json')
 if p.canonical(p.build_source(p.Store(run/'runtime'),blobs[inventory['selected']]))!=p.canonical(source):raise ValueError('WIDTH_ADOPTION_FRESH_SOURCE_RECONSTRUCTION_CHANGED')
 files={str(f.relative_to(run)):sha(f)for f in run.rglob('*')if f.is_file()}
 p.save(run/'REUSED_WIDTH_BINDING.json',dict(original=binding,copied_files=files))
 p.save(run/'input_inventory.json',dict(inventory,qualification_mode=MODE,reused_native_operations=29))
 p.save(job/'INPUT_INVENTORY.json',load(run/'input_inventory.json'));seal(run,CONNECTED);verify(run)
 return run

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--prefix-run',type=Path,required=True);args=parser.parse_args();work=configure();parent=work/'operator_routes/gerber_u05_width_adoption';parent.mkdir(exist_ok=True);job=parent/(datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex);job.mkdir();c=Coordinator(job);c.state.update(source_only=False,qualification_mode=MODE,reused_operations=29)
 try:
  run=prepare(args.prefix_run,job)
  from .guard import install_read_fence
  install_read_fence(job)
  from tools.preflight import verify_manifest
  p.save(job/'ASSET_MANIFEST_PROOF.json',dict(status='PASS',files=verify_manifest()))
  for stage in('t04','t02','t05'):
   c.execute(run,stage,['construct']);c.execute(run,stage,['1','2']);proofs=[load(run/'audits'/stage/(m+'.json'))for m in('construct','1','2')]
   if proofs[0]!=proofs[1]or proofs[0]!=proofs[2]:raise ValueError('WIDTH_ADOPTION_FRESH_STAGE_PROOFS_DIFFER')
  c.execute(run,'export',['construct'],module='exporter');c.execute(run,'export',['1','2'],module='exporter')
  for stage,module in(('controls','controls'),('remaining_defects','remaining_defects'),('render','render')):c.execute(run,stage,['all'],module=module)
  from .delivery import deliver
  _,blobs,ignored=__import__('src.pcb_data_abi.input_directory',fromlist=['collect_raw']).collect_raw(load(run/'input_inventory.json')['input_directory'])
  inventory=load(run/'input_inventory.json')
  if {n:p.digest(b)for n,b in blobs.items()}!=inventory['files']or ignored!=inventory['ignored']:raise ValueError('WIDTH_ADOPTION_FINAL_INPUT_CUSTODY_CHANGED')
  c.state.update(delivery=deliver(run),status='U05_EXPORT_REPARSE_CONTROLS_RENDER_PASSED',run=str(run),generated_sha256=sha(run/'export/top.art.gbr'));c.record()
 except BaseException as error:c.state.update(status='HALTED',error=str(error),remaining_operations='NOT_RUN; original failed job unchanged');c.record();p.save(job/'HALTED.json',c.state);raise

if __name__=='__main__':main()
