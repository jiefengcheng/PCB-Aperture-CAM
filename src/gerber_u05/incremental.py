"""Incremental qualification: reuse an accepted source/prefix, run T05 onward."""
import argparse,datetime,json,os,shutil,subprocess,uuid
from pathlib import Path
from . import pipeline as p
from .guard import seal,verify_sources,install_read_fence
from .prefix import STAGES,sha,load,verify_code
from .run import Coordinator,CONNECTED
from .workspace import configure


def copy_file(source,target):
 target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():raise ValueError('INCREMENTAL_COPY_TARGET_EXISTS')
 subprocess.run(['cp','-c',str(source),str(target)],check=True)
 if sha(source)!=sha(target):raise ValueError('INCREMENTAL_COPY_CHANGED')


def prepare(prefix,job):
 from src.pcb_data_abi.input_directory import collect_raw
 prefix=Path(prefix);old_job=prefix.parent;original=load(prefix/'PRODUCER_BINDING.json');state=load(old_job/'STATUS.current.json');inventory=load(prefix/'input_inventory.json')
 if original['profile']!=CONNECTED:raise ValueError('CONNECTED_PREFIX_PROFILE_REQUIRED')
 required=['legacy_'+stage+'_'+mode for stage in('t01','t03','t04','t02','t05')for mode in('construct','1','2')]+['legacy_t01_supplement_'+m for m in('1','2')]+['legacy_legacy_export_'+m for m in('construct','1','2')]+['reference_remedy_'+m for m in('construct','1','2')]+['connected_'+stage+'_'+m for stage in STAGES for m in('construct','1','2')]
 if any(key not in state['checks']or state['checks'][key]['status']!='PASS'or state['checks'][key]['returncode']!=0 for key in required):raise ValueError('REUSED_SOURCE_OR_PREFIX_CHECK_INCOMPLETE')
 old_root=Path(os.path.commonpath(list(original['files'])));code=verify_code(original,p.ROOT,old_root)
 root,blobs,ignored=collect_raw(inventory['input_directory'])
 if {n:p.digest(b)for n,b in blobs.items()}!=inventory['files']or ignored!=inventory['ignored']:raise ValueError('REUSED_RAW_INPUT_CUSTODY_CHANGED')
 source=load(prefix/'source.json')
 if p.digest(blobs[inventory['selected']])!=source['source_ref']['sha256']:raise ValueError('REUSED_SELECTED_SOURCE_CHANGED')
 run=job/'connected';run.mkdir();subprocess.run(['cp','-cR',str(prefix/'runtime'),str(run/'runtime')],check=True)
 for name in('source.json','CLEARANCE_SNAPSHOT.json','REMEDY_POLICY_SNAPSHOT.json','REFERENCE_BINDING.json','RAW_WIDTH_CHECKPOINT.json'):
  if(prefix/name).exists():copy_file(prefix/name,run/name)
 for folder in('source_snapshot','reference','width_prefix_audits'):
  if(prefix/folder).exists():subprocess.run(['cp','-cR',str(prefix/folder),str(run/folder)],check=True)
 (run/'audits').mkdir()
 for stage in STAGES:
  copy_file(prefix/(stage+'.json'),run/(stage+'.json'));subprocess.run(['cp','-cR',str(prefix/'audits'/stage),str(run/'audits'/stage)],check=True)
 evidence=run/'prefix_evidence';evidence.mkdir();copy_file(prefix/'PRODUCER_BINDING.json',evidence/'ORIGINAL_PRODUCER_BINDING.json');copy_file(old_job/'STATUS.current.json',evidence/'ORIGINAL_ROUTE_STATUS.json');copy_file(old_job/'ASSET_MANIFEST_PROOF.json',evidence/'ORIGINAL_ASSET_MANIFEST_PROOF.json')
 for index,(name,expected)in enumerate(original.get('job_inputs',{}).items()):
  if sha(name)!=expected:raise ValueError('REUSED_ORIGINAL_JOB_INPUT_CHANGED')
  copy_file(name,evidence/'original_inputs'/(str(index)+'_'+Path(name).name))
 for family in('legacy','reference'):
  source_family=old_job/family
  for name in('PRODUCER_BINDING.json','source.json','POLICY_SNAPSHOT.json','CLEARANCE_SNAPSHOT.json'):
   if(source_family/name).exists():copy_file(source_family/name,evidence/family/name)
  if family=='legacy':
   for stage in('t01','t03','t04','t02','t05'):
    copy_file(source_family/(stage+'.json'),evidence/family/(stage+'.json'))
   subprocess.run(['cp','-cR',str(source_family/'audits'),str(evidence/family/'audits')],check=True)
  for proof in(source_family/'export').glob('proof_*.json'):copy_file(proof,evidence/family/'export'/proof.name)
 # Every native worker stdout/stderr and exit status remains available without
 # using a historical candidate as a new generation input outside this prefix.
 for key in required:
  for suffix in('.log','.stderr.log'):copy_file(old_job/'logs'/(key+suffix),evidence/'logs'/(key+suffix))
 binding=dict(schema='incremental-native-prefix/1',source_sha256=source['source_ref']['sha256'],original_source_root=str(old_root),original_run=str(prefix),original_job_status=state['status'],original_route_completion='NOT_CLAIMED; intentional boundary stop preserved',original_producer_binding_sha256=sha(prefix/'PRODUCER_BINDING.json'),original_checks={key:state['checks'][key]for key in required},retained_operation_count=len(required),reused_stages=list(STAGES),code_dependency_checks=code,files={})
 files=[*evidence.rglob('*'),*[run/(stage+'.json')for stage in STAGES],*(run/'audits').rglob('*.json')]
 if(run/'RAW_WIDTH_CHECKPOINT.json').exists():files.append(run/'RAW_WIDTH_CHECKPOINT.json')
 binding['files']={str(file.relative_to(run)):sha(file)for file in files if file.is_file()}
 p.save(run/'REUSED_PREFIX_BINDING.json',binding)
 revision=p.load(p.ROOT/'SOURCE_REVISION.json')if(p.ROOT/'SOURCE_REVISION.json').exists()else dict(status='SOURCE_DIGEST_BOUND_WORKING_CANDIDATE; commit pending')
 inventory=dict(inventory,source_revision=revision,qualification_mode='INCREMENTAL_REUSED_NATIVE_PREFIX',reused_source_revision=inventory.get('source_revision'))
 p.save(run/'input_inventory.json',inventory);p.save(job/'INPUT_INVENTORY.json',inventory);seal(run,CONNECTED)
 return run,binding


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prefix-run',required=True,type=Path);args=parser.parse_args()
 if not args.prefix_run.is_absolute():parser.error('prefix run must be an explicit absolute path')
 work=configure();parent=work/'operator_routes/gerber_u05_incremental';parent.mkdir(parents=True,exist_ok=True);job=parent/(datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex);job.mkdir();coordinator=Coordinator(job);coordinator.state.update(source_only=False,qualification_mode='INCREMENTAL_REUSED_NATIVE_PREFIX')
 try:
  run,binding=prepare(args.prefix_run,job);coordinator.state['reused_prefix']=dict(operations=binding['retained_operation_count'],stages=binding['reused_stages'],binding_sha256=sha(run/'REUSED_PREFIX_BINDING.json'));install_read_fence(job)
  from tools.preflight import verify_manifest
  p.save(job/'ASSET_MANIFEST_PROOF.json',dict(status='PASS',files=verify_manifest()));verify_sources(run)
  coordinator.execute(run,'t05',['construct']);coordinator.execute(run,'t05',['1','2'])
  proofs=[p.load(run/'audits/t05'/(mode+'.json'))for mode in('construct','1','2')]
  if proofs[0]!=proofs[1]or proofs[0]!=proofs[2]:raise ValueError('FRESH_T05_PAIRED_PROOFS_DIFFER')
  coordinator.execute(run,'export',['construct'],module='exporter');coordinator.execute(run,'export',['1','2'],module='exporter')
  coordinator.execute(run,'controls',['all'],module='controls');coordinator.execute(run,'remaining_defects',['all'],module='remaining_defects');coordinator.execute(run,'render',['all'],module='render')
  from .delivery import deliver
  coordinator.state.update(delivery=deliver(run),status='U05_EXPORT_REPARSE_CONTROLS_RENDER_PASSED',run=str(run),generated_sha256=sha(run/'export/top.art.gbr'));coordinator.record()
 except BaseException as error:
  coordinator.state.update(status='HALTED',error=str(error),remaining_operations='NOT_RUN; no retry or acceptance promotion');coordinator.record();p.save(job/'HALTED.json',coordinator.state);raise

if __name__=='__main__':main()
