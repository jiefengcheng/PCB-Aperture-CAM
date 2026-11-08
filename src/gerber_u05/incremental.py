"""Incremental qualification from an audited T03 or T02 prefix in a new job."""
import argparse,datetime,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
from . import pipeline as p
from .guard import seal,verify_sources,install_read_fence
from .prefix import STAGES,sha,load,verify_code,retained_stages,operation_keys,require_retained_t03
from .run import Coordinator,CONNECTED,ORDER
from .workspace import configure


def copy_file(source,target):
 target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():raise ValueError('INCREMENTAL_COPY_TARGET_EXISTS')
 subprocess.run(['cp','-c',str(source),str(target)],check=True)
 if sha(source)!=sha(target):raise ValueError('INCREMENTAL_COPY_CHANGED')

def completed_records(old_job,old_root):
 """Re-evaluate the existing frozen legacy-prefix verifier before adoption."""
 state=load(old_job/'STATUS.current.json');records=dict(state['checks']);log_roots=[old_job];legacy=old_job/'legacy';proof=None
 if(legacy/'REUSED_LEGACY_BINDING.json').exists():
  script="import json,sys;from src.gerber_u05.legacy_prefix import inspect;print(json.dumps(inspect(sys.argv[1],'t05')))"
  proof=json.loads(subprocess.check_output([sys.executable,'-B','-c',script,str(legacy)],cwd=old_root,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}))
  if proof['retained_operation_count']!=17:raise ValueError('REUSED_LEGACY_COMPLETE_PREFIX_REQUIRED')
  records=dict(proof['original_checks'],**records);seen=set();current=legacy
  while(current/'REUSED_LEGACY_BINDING.json').exists():
   if str(current)in seen:raise ValueError('REUSED_LEGACY_AUTHORITY_CYCLE')
   seen.add(str(current));current=Path(load(current/'REUSED_LEGACY_BINDING.json')['original']['original_run']);log_roots.append(current.parent)
 return records,log_roots,proof


def prepare(prefix,job,coordinator=None,*,through='t02'):
 from src.pcb_data_abi.input_directory import collect_raw
 prefix=Path(prefix);old_job=prefix.parent;original=load(prefix/'PRODUCER_BINDING.json');state=load(old_job/'STATUS.current.json');inventory=load(prefix/'input_inventory.json')
 if original['profile']!=CONNECTED:raise ValueError('CONNECTED_PREFIX_PROFILE_REQUIRED')
 stages=retained_stages(ORDER[:ORDER.index(through)+1])
 if stages==('t01','t03'):require_retained_t03(prefix)
 old_root=Path(os.path.commonpath(list(original['files'])));code=verify_code(original,p.ROOT,old_root,stages=stages)
 records,log_roots,legacy_proof=completed_records(old_job,old_root)
 required=operation_keys(stages)
 if any(key not in records or records[key]['status']!='PASS'or records[key]['returncode']!=0 for key in required):raise ValueError('REUSED_SOURCE_OR_PREFIX_CHECK_INCOMPLETE')
 root,blobs,ignored=collect_raw(inventory['input_directory'])
 if {n:p.digest(b)for n,b in blobs.items()}!=inventory['files']or ignored!=inventory['ignored']:raise ValueError('REUSED_RAW_INPUT_CUSTODY_CHANGED')
 source=load(prefix/'source.json')
 raw=blobs[inventory['selected']];fresh_assembly=0
 if(prefix/'SOURCE_ASSEMBLY_BINDING.json').exists():
  from . import source_assembly
  coordinator=Coordinator(job)if coordinator is None else coordinator
  assembly=job/'assembly';assembly.mkdir();(assembly/'original.gbr').write_bytes(raw);p.save(assembly/'INPUT_INVENTORY.json',inventory)
  from .pcb_artwork_scope import capture as capture_scope
  capture_scope(assembly,root,blobs,inventory)
  p.save(assembly/'ASSEMBLY_PRODUCER.json',source_assembly._producer(assembly))
  coordinator.execute(assembly,'source_assembly',['construct'],module='source_assembly');coordinator.execute(assembly,'source_assembly',['1','2'],module='source_assembly');source_assembly.verify_job(assembly);raw=(assembly/'assembled.gbr').read_bytes();fresh_assembly=3
 if p.digest(raw)!=source['source_ref']['sha256']:raise ValueError('REUSED_SELECTED_SOURCE_CHANGED')
 run=job/'connected';run.mkdir();subprocess.run(['cp','-cR',str(prefix/'runtime'),str(run/'runtime')],check=True)
 names=['source.json','CLEARANCE_SNAPSHOT.json','REMEDY_POLICY_SNAPSHOT.json','REFERENCE_BINDING.json','REFERENCE_CHANNELS.json','T04_SETTINGS_SNAPSHOT.json','PIN_SEPARATION_POLICY.json','STORAGE_ENCODING.json']
 if 't04'in stages:names+=['RAW_WIDTH_CHECKPOINT.json','T04_PRIOR_WIDTH_COMPATIBILITY.json']
 for name in names:
  if(prefix/name).exists():copy_file(prefix/name,run/name)
 for folder in(('source_snapshot','reference','width_prefix_audits')if 't04'in stages else('source_snapshot','reference')):
  if(prefix/folder).exists():subprocess.run(['cp','-cR',str(prefix/folder),str(run/folder)],check=True)
 (run/'audits').mkdir()
 for stage in stages:
  copy_file(prefix/(stage+'.json'),run/(stage+'.json'));subprocess.run(['cp','-cR',str(prefix/'audits'/stage),str(run/'audits'/stage)],check=True)
 evidence=run/'prefix_evidence';evidence.mkdir();copy_file(prefix/'PRODUCER_BINDING.json',evidence/'ORIGINAL_PRODUCER_BINDING.json');copy_file(old_job/'STATUS.current.json',evidence/'ORIGINAL_ROUTE_STATUS.json');copy_file(old_job/'ASSET_MANIFEST_PROOF.json',evidence/'ORIGINAL_ASSET_MANIFEST_PROOF.json')
 if legacy_proof is not None:p.save(evidence/'ORIGINAL_LEGACY_PREFIX_PROOF.json',legacy_proof)
 for index,(name,expected)in enumerate(original.get('job_inputs',{}).items()):
  if sha(name)!=expected:raise ValueError('REUSED_ORIGINAL_JOB_INPUT_CHANGED')
  copy_file(name,evidence/'original_inputs'/(str(index)+'_'+Path(name).name))
 for family in('legacy','reference'):
  source_family=old_job/family
  for name in('PRODUCER_BINDING.json','source.json','POLICY_SNAPSHOT.json','CLEARANCE_SNAPSHOT.json'):
   if(source_family/name).exists():copy_file(source_family/name,evidence/family/name)
  if family=='legacy':
   if(source_family/'REUSED_LEGACY_BINDING.json').exists():copy_file(source_family/'REUSED_LEGACY_BINDING.json',evidence/family/'REUSED_LEGACY_BINDING.json')
   for stage in('t01','t03','t04','t02','t05'):
    copy_file(source_family/(stage+'.json'),evidence/family/(stage+'.json'))
   subprocess.run(['cp','-cR',str(source_family/'audits'),str(evidence/family/'audits')],check=True)
  for proof in(source_family/'export').glob('proof_*.json'):copy_file(proof,evidence/family/'export'/proof.name)
  copy_file(source_family/'export/top.art.gbr',evidence/family/'export/top.art.gbr')
  if family=='legacy':
   from .prefix import legacy_support_identity
   copy_file(source_family/'export/ledger.json',evidence/family/'export/ledger.json')
   refs={r['raw_qualified_ref']['artifact_id']for r in load(source_family/'export/ledger.json')['records']if r['stage']=='t05'}
   for aid in refs:copy_file(source_family/'runtime/artifacts'/aid,evidence/family/'runtime/artifacts'/aid)
   support_identity=legacy_support_identity(evidence/family)
 # Every native worker stdout/stderr and exit status remains available without
 # using a historical candidate as a new generation input outside this prefix.
 for key in required:
  for suffix in('.log','.stderr.log'):
   matches=[root/'logs'/(key+suffix)for root in log_roots if(root/'logs'/(key+suffix)).is_file()]
   if not matches:raise ValueError('REUSED_NATIVE_PROCESS_LOG_MISSING:'+key)
   copy_file(matches[0],evidence/'logs'/(key+suffix))
 checked_legacy={}
 if legacy_proof is not None or load(old_job/'legacy/t04.json')['solution'].get('schema')=='source-route-ten-step-width-ladder/1':
  # These are hash-bound checking-envelope inputs, not a resumed legacy job.
  legacy=job/'legacy';legacy.mkdir();subprocess.run(['cp','-cR',str(old_job/'legacy/runtime'),str(legacy/'runtime')],check=True)
  for name in('source.json','RAW_WIDTH_CHECKPOINT.json','t04.json'):copy_file(old_job/'legacy'/name,legacy/name)
  subprocess.run(['cp','-cR',str(old_job/'legacy/audits'),str(legacy/'audits')],check=True)
  p.save(legacy/'SCOPE.json',dict(role='HASH_BOUND_CHECKING_ENVELOPE_INPUTS_ONLY',original_run=str(old_job/'legacy'),native_job_resumed=False))
  checked_legacy={str(f.relative_to(legacy)):sha(f)for f in legacy.rglob('*')if f.is_file()}
 binding=dict(schema='incremental-native-prefix/1',source_sha256=source['source_ref']['sha256'],original_source_root=str(old_root),original_run=str(prefix),original_job_status=state['status'],original_route_completion='NOT_CLAIMED; original failed/boundary status preserved',original_producer_binding_sha256=sha(prefix/'PRODUCER_BINDING.json'),original_checks={key:records[key]for key in required},retained_operation_count=len(required),reused_stages=list(stages),code_dependency_checks=code,fresh_assembly_operations=fresh_assembly,checked_legacy_files=checked_legacy,legacy_support_identity=support_identity,files={})
 files=[*evidence.rglob('*'),*[run/(stage+'.json')for stage in stages],*(run/'audits').rglob('*.json')]
 if(run/'RAW_WIDTH_CHECKPOINT.json').exists():files.append(run/'RAW_WIDTH_CHECKPOINT.json')
 if(run/'T04_PRIOR_WIDTH_COMPATIBILITY.json').exists():files.append(run/'T04_PRIOR_WIDTH_COMPATIBILITY.json')
 binding['files']={str(file.relative_to(run)):sha(file)for file in files if file.is_file()}
 p.save(run/'REUSED_PREFIX_BINDING.json',binding)
 revision=p.load(p.ROOT/'SOURCE_REVISION.json')if(p.ROOT/'SOURCE_REVISION.json').exists()else dict(status='SOURCE_DIGEST_BOUND_WORKING_CANDIDATE; commit pending')
 inventory=dict(inventory,source_revision=revision,qualification_mode='INCREMENTAL_REUSED_NATIVE_PREFIX',reused_source_revision=inventory.get('source_revision'))
 p.save(run/'input_inventory.json',inventory);p.save(job/'INPUT_INVENTORY.json',inventory)
 if fresh_assembly:
  source_assembly.attach(run,job/'assembly')
 seal(run,CONNECTED)
 from .prefix import verify
 verify(run)
 return run,binding


def continue_stages(coordinator,run,through):
 retained_stages(ORDER[:ORDER.index(through)+1])
 for stage in ORDER[ORDER.index(through)+1:]:
  coordinator.execute(run,stage,['construct']);coordinator.execute(run,stage,['1','2'])
  proofs=[p.load(run/'audits'/stage/(mode+'.json'))for mode in('construct','1','2')]
  if proofs[0]!=proofs[1]or proofs[0]!=proofs[2]or proofs[0]['status']!='PASS':raise ValueError('FRESH_PAIRED_STAGE_PROOFS_DIFFER:'+stage)
  if stage=='t04':
   from .width_prior import verify
   verify(coordinator.job/'legacy',run)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prefix-run',required=True,type=Path);parser.add_argument('--through-stage',choices=('t03','t02'),default='t02');args=parser.parse_args()
 if not args.prefix_run.is_absolute():parser.error('prefix run must be an explicit absolute path')
 work=configure();parent=work/'operator_routes/gerber_u05_incremental';parent.mkdir(parents=True,exist_ok=True);job=parent/(datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex);job.mkdir();coordinator=Coordinator(job);coordinator.state.update(source_only=False,qualification_mode='INCREMENTAL_REUSED_NATIVE_PREFIX')
 try:
  from tools.preflight import verify_manifest
  count=verify_manifest();manifest=load(p.ROOT/'assets/starter/evidence/fixture_sha256.json')
  for name,expected in manifest.items():
   if sha(p.ROOT/'assets/starter'/name)!=expected:raise ValueError('IMMUTABLE_ASSET_HASH_CHANGED:'+name)
  p.save(job/'ASSET_MANIFEST_PROOF.json',dict(status='PASS',files=count,starter_files=len(manifest)))
  run,binding=prepare(args.prefix_run,job,coordinator,through=args.through_stage);coordinator.state['reused_prefix']=dict(operations=binding['retained_operation_count'],stages=binding['reused_stages'],binding_sha256=sha(run/'REUSED_PREFIX_BINDING.json'));install_read_fence(job);verify_sources(run)
  continue_stages(coordinator,run,args.through_stage)
  coordinator.execute(run,'export',['construct'],module='exporter');coordinator.execute(run,'export',['1','2'],module='exporter')
  coordinator.execute(run,'controls',['all'],module='controls');coordinator.execute(run,'remaining_defects',['all'],module='remaining_defects');coordinator.execute(run,'render',['all'],module='render')
  from .delivery import deliver
  coordinator.state.update(delivery=deliver(run),status='U05_EXPORT_REPARSE_CONTROLS_RENDER_PASSED',run=str(run),generated_sha256=sha(run/'export/top.art.gbr'));coordinator.record()
 except BaseException as error:
  coordinator.state.update(status='HALTED',error=str(error),remaining_operations='NOT_RUN; no retry or acceptance promotion');coordinator.record();p.save(job/'HALTED.json',coordinator.state);raise

if __name__=='__main__':main()
