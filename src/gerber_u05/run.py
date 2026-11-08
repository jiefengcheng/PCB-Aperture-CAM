"""Source-only U05 operation, with immutable jobs and all fresh evaluations."""
import argparse,datetime,json,os,subprocess,sys,time,uuid
from pathlib import Path
from . import pipeline as p
from .guard import seal,verify_sources,install_read_fence
from .component_policy import capture_job
from .workspace import configure
ORDER=('t01','t03','t04','t02','t05')
CONNECTED='original-connected-copper-growth-and-intra-step-completion/1'
class Coordinator:
 def __init__(self,job):
  self.job=job;self.state=dict(status='RUNNING',source_only=True,checks={},owner='PENDING_USER',independent='NOT_RUN',electrical_manufacturing='NOT_ESTABLISHED',custody_finding='.DS_Store: prior custody FAIL remains EXPLICIT_UNWAIVED_UNATTRIBUTED',coverage_recovery='INDEPENDENT_UNCHANGED');(job/'logs').mkdir()
 def record(self):
  path=self.job/'STATUS.current.json';temp=path.with_suffix('.tmp');temp.write_bytes(p.canonical(self.state));temp.replace(path);print(json.dumps(self.state),flush=True)
 def execute(self,run,stage,modes,module='worker'):
  jobs=[]
  for mode in modes:
   key=run.name+'_'+stage+'_'+mode;out=(self.job/'logs'/(key+'.log')).open('xb');err=(self.job/'logs'/(key+'.stderr.log')).open('xb')
   args=[sys.executable,'-B','-m','src.gerber_u05.'+module,str(run)]+([stage,mode]if module=='worker'else[mode])
   child=subprocess.Popen(args,cwd=p.ROOT,stdout=out,stderr=err,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'});jobs.append((key,child,out,err,time.monotonic()));self.state['checks'][key]=dict(status='RUNNING',pid=child.pid)
  self.record();failed=[]
  for key,child,out,err,start in jobs:
   code=child.wait();out.close();err.close();self.state['checks'][key].update(status='PASS'if code==0 else'FAIL',seconds=time.monotonic()-start,returncode=code);self.record()
   if code:failed.append(key)
  if failed:raise ValueError('U05_ROUTE_HALTED:'+','.join(failed))
 def stages(self,run,legacy=False):
  for stage in ORDER:
   self.execute(run,stage,['construct']);self.execute(run,stage,['1','2'])
   proofs=[p.load(run/'audits'/stage/(m+'.json'))for m in('construct','1','2')]
   if len({p.digest(p.canonical(v))for v in proofs})!=1:raise ValueError('PAIRED_STAGE_PROOFS_DIFFER:'+stage)
   if not legacy and stage=='t04':
    from .width_prior import verify
    verify(self.job/'legacy',run)
   if legacy and stage=='t01':self.execute(run,'t01_supplement',['1','2'])
 def prepare(self,run,raw,inventory,legacy=False):
  run.mkdir();(run/'source_snapshot').mkdir();(run/'source_snapshot/top.art.gbr').write_bytes(raw);p.save(run/'input_inventory.json',inventory)
  from .storage_encoding import policy as storage_policy
  p.save(run/'STORAGE_ENCODING.json',storage_policy())
  if legacy:p.save(run/'LEGACY_REFERENCE_JOB.json',dict(schema='fresh-legacy-reservation-reference/1',scope='Source-only recipe, no golden input'))
  else:capture_job(run)
  p.save(run/'source.json',p.build_source(p.Store(run/'runtime'),raw))
  from .source_assembly import attach
  if(self.job/'assembly').exists():attach(run,self.job/'assembly')
  from .pin_policy import capture as capture_pin
  capture_pin(run,inventory)
  if legacy:seal(run,'fresh-legacy-reservation-reference/1')
 def generate(self,input_dir,selected):
  from src.pcb_data_abi.input_directory import collect_raw
  from src.clearance_settings import capture
  work=configure();root,blobs,ignored=collect_raw(str(input_dir))
  if selected not in blobs:raise ValueError('SELECTED_GERBER_MISSING')
  raw=blobs[selected];inventory=dict(input_directory=str(root),files={n:p.digest(b)for n,b in blobs.items()},ignored=ignored,selected=selected,layer_identity='LIKELY_TOP_ARTWORK; X2 stack identity NOT_ESTABLISHED',companions='UNCHANGED_NOT_COPIED')
  inventory['source_revision']=p.load(p.ROOT/'SOURCE_REVISION.json')if(p.ROOT/'SOURCE_REVISION.json').exists()else dict(status='SOURCE_DIGEST_BOUND; Git revision NOT_ESTABLISHED')
  p.save(self.job/'INPUT_INVENTORY.json',inventory);install_read_fence(self.job,legacy_authority=getattr(self,'legacy_authority',None))
  from tools.preflight import verify_manifest
  asset_count=verify_manifest()
  manifest=p.load(p.ROOT/'assets/starter/evidence/fixture_sha256.json')
  for name,expected in manifest.items():
   if p.digest((p.ROOT/'assets/starter'/name).read_bytes())!=expected:raise ValueError('IMMUTABLE_ASSET_HASH_CHANGED:'+name)
  p.save(self.job/'ASSET_MANIFEST_PROOF.json',dict(status='PASS',files=asset_count,starter_files=len(manifest)))
  from . import source_assembly
  assembly=self.job/'assembly';assembly.mkdir();(assembly/'original.gbr').write_bytes(raw);p.save(assembly/'INPUT_INVENTORY.json',inventory)
  from .pcb_artwork_scope import capture as capture_scope
  capture_scope(assembly,root,blobs,inventory)
  p.save(assembly/'ASSEMBLY_PRODUCER.json',source_assembly._producer(assembly))
  self.execute(assembly,'source_assembly',['construct'],module='source_assembly');self.execute(assembly,'source_assembly',['1','2'],module='source_assembly');source_assembly.verify_job(assembly)
  raw=(assembly/'assembled.gbr').read_bytes()
  legacy=self.job/'legacy';self.prepare(legacy,raw,inventory,True);self.stages(legacy,True)
  self.execute(legacy,'legacy_export',['construct']);self.execute(legacy,'legacy_export',['1','2'])
  reference=self.job/'reference';reference.mkdir();p.save(reference/'source.json',p.load(legacy/'source.json'))
  from .storage_encoding import policy as storage_policy
  p.save(reference/'STORAGE_ENCODING.json',storage_policy())
  source_assembly.attach(reference,assembly)
  from .pin_policy import capture as capture_pin
  capture_pin(reference,inventory)
  clearance=capture(p.ROOT/'contracts/clearance/settings.json');clearance.write_snapshot(reference/'CLEARANCE_SNAPSHOT.json');settings=p.load(p.ROOT/'contracts/growth_void/settings.json')
  parameters=dict(settings['parameters'],hard_gap_mm=clearance.nominal_mm,construction_gap_mm=clearance.construction_gap_mm)
  p.save(reference/'POLICY_SNAPSHOT.json',dict(schema='source-only-reference-policy/1',resolved_parameters=parameters,clearance_resolved=clearance.resolved(),owner_allowance_consumed=False,large_pocket_strategy=settings.get('large_pocket_strategy')));seal(reference,'fresh-legacy-local-remedy-reference/1')
  self.execute(reference,'remedy',['construct'],module='reference_recipe');self.execute(reference,'remedy',['1','2'],module='reference_recipe')
  proofs=[p.load(reference/'export'/('proof_'+m+'.json'))for m in('construct','1','2')]
  if len({p.digest(p.canonical(v))for v in proofs})!=1:raise ValueError('FRESH_REFERENCE_PROOFS_DIFFER')
  connected=self.job/'connected';self.prepare(connected,raw,inventory)
  (connected/'reference').mkdir();body=(reference/'export/top.art.gbr').read_bytes();(connected/'reference/top.art.gbr').write_bytes(body)
  binding=dict(schema='job-local-generated-reservation/1',source_sha256=p.digest(raw),generated_sha256=p.digest(body),reference_proof_sha256=p.digest(p.canonical(proofs[0])),source_only=True)
  if 'functional_channels'in proofs[0]:
   import copy
   sidecar=copy.deepcopy(proofs[0]['functional_channels']);source_store=p.Store(reference/'runtime');target_store=p.Store(connected/'runtime')
   sidecar['owned_geometry_refs']={o:target_store.put('geometry',source_store.get(ref,kind='geometry'))for o,ref in sidecar['owned_geometry_refs'].items()}
   if 'pin_separation_state'in sidecar:
    ref=sidecar['pin_separation_state']['rejected_ref'];sidecar['pin_separation_state']['rejected_ref']=target_store.put('geometry',source_store.get(ref,kind='geometry'))
   source_store.verify_reads();target_store.verify_reads();p.save(connected/'REFERENCE_CHANNELS.json',sidecar);binding['functional_channel_sidecar_sha256']=p.digest(p.canonical(sidecar))
  p.save(connected/'REFERENCE_BINDING.json',binding)
  seal(connected,CONNECTED);self.stages(connected)
  self.execute(connected,'export',['construct'],module='exporter');self.execute(connected,'export',['1','2'],module='exporter')
  self.execute(connected,'controls',['all'],module='controls');self.execute(connected,'remaining_defects',['all'],module='remaining_defects');self.execute(connected,'render',['all'],module='render')
  _,final_blobs,final_ignored=collect_raw(str(root))
  if {n:p.digest(b)for n,b in final_blobs.items()}!=inventory['files']or final_ignored!=ignored:raise ValueError('INPUT_CUSTODY_CHANGED')
  from .delivery import deliver
  self.state['delivery']=deliver(connected)
  self.state.update(status='U05_EXPORT_REPARSE_CONTROLS_RENDER_PASSED',run=str(connected),generated_sha256=p.digest((connected/'export/top.art.gbr').read_bytes()));self.record()
  return connected

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input-dir',required=True,type=Path);parser.add_argument('--gerber',required=True);args=parser.parse_args()
 if not args.input_dir.is_absolute():parser.error('input directory must be absolute')
 work=configure();parent=work/'operator_routes/gerber_u05';parent.mkdir(parents=True,exist_ok=True);job=parent/(datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex);job.mkdir();coordinator=Coordinator(job)
 try:coordinator.generate(args.input_dir,args.gerber)
 except BaseException as error:
  coordinator.state.update(status='HALTED',error=str(error),remaining_operations='NOT_RUN; no retry/resume/acceptance promotion');coordinator.record();p.save(job/'HALTED.json',coordinator.state);raise
if __name__=='__main__':main()
