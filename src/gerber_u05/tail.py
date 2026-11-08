"""Fresh export qualification after an unchanged, fully checked T05.

The old job is never resumed or relabelled. All three completed T05 proofs,
process exits, inputs and geometry-producing code must still match. Only the
export/check/report implementation may differ in this new job.
"""
import argparse,datetime,json,os,subprocess,uuid
from pathlib import Path
from . import pipeline as p
from .guard import ROOT,seal,verify_sources,install_read_fence
from .prefix import sha,load,verify as verify_prefix,shared_gap_restore_same
from .incremental import copy_file
from .run import Coordinator,CONNECTED
from .workspace import configure

TAIL_ONLY={
 'src/gerber_u05/guard.py','src/gerber_u05/prefix.py','src/gerber_u05/exporter.py',
 'src/gerber_u05/controls.py','src/gerber_u05/remaining_defects.py',
 'src/gerber_u05/render.py','src/gerber_u05/delivery.py',
 'src/gerber_u05/contours.py','src/gerber_u05/exact_cut_in.py',
 'src/gerber_u05/native_assembly.py','src/gerber_u05/native_material.py',
 'src/gerber_u05/native_spindle_operand.py','src/gerber_u05/source_prefix_control.py',
 'src/gerber_u05/tail.py','src/gerber_u05/qualification_tail.py',
 'src/shared_gap_projection.py',
 'src/gerber_u05/native_inclusive_identity.py',
}

def verify_code(original,current,old_root):
 current=Path(current);old_root=Path(old_root);changed=[];known=set()
 for name,expected in original['files'].items():
  old=Path(name)
  if not old.is_relative_to(old_root)or sha(old)!=expected:raise ValueError('REUSED_T05_ORIGINAL_CODE_CHANGED:'+name)
  relative=old.relative_to(old_root).as_posix();known.add(relative)
  if relative=='SOURCE_REVISION.json':continue
  actual=sha(current/relative)
  if actual!=expected:
   if relative=='src/t02_shared_gaps.py':
    changed.append(dict(path=relative,before_sha256=expected,after_sha256=actual,proof=shared_gap_restore_same(old.read_text(),(current/relative).read_text())));continue
   if relative not in TAIL_ONLY:raise ValueError('REUSED_T05_GEOMETRY_CODE_CHANGED:'+relative)
   changed.append(dict(path=relative,before_sha256=expected,after_sha256=actual))
 # A new driver is allowed; new geometry modules/configuration are not.
 files=[file for directory in('src','contracts','tools','web')for file in(current/directory).rglob('*')if file.is_file()and file.suffix in('.py','.json','.command','.js','.html')]
 if(current/'SOURCE_REVISION.json').is_file():files.append(current/'SOURCE_REVISION.json')
 extras={file.relative_to(current).as_posix()for file in files}-known
 if extras-{'src/gerber_u05/tail.py','src/gerber_u05/qualification_tail.py','src/shared_gap_projection.py','src/gerber_u05/native_inclusive_identity.py','SOURCE_REVISION.json'}:raise ValueError('REUSED_T05_UNDECLARED_PRODUCER_ADDED')
 return changed

def validate_stage(run,state,producer_sha):
 run=Path(run);records={}
 for mode in('construct','1','2'):
  key='connected_t05_'+mode;record=state.get('checks',{}).get(key,{})
  if record.get('status')!='PASS'or record.get('returncode')!=0:raise ValueError('REUSED_T05_NATIVE_CHECK_INCOMPLETE:'+mode)
  records[key]=record
 if records['connected_t05_1']['pid']==records['connected_t05_2']['pid']:raise ValueError('REUSED_T05_EVALUATIONS_NOT_SEPARATE')
 proofs=[load(run/'audits/t05'/(m+'.json'))for m in('construct','1','2')]
 if proofs[0]!=proofs[1]or proofs[0]!=proofs[2]:raise ValueError('REUSED_T05_PAIRED_PROOFS_DIFFER')
 proof=proofs[0]
 if proof['status']!='PASS'or proof['candidate_sha256']!=sha(run/'t05.json')or proof['producer_binding_sha256']!=producer_sha:raise ValueError('REUSED_T05_CANDIDATE_OR_PRODUCER_CHANGED')
 return records

def verify(run):
 run=Path(run);path=run/'REUSED_T05_BINDING.json'
 if not path.exists():return None
 binding=load(path);original=load(run/'prefix_evidence/T05_ORIGINAL_PRODUCER_BINDING.json')
 if binding['retained_operation_count']!=38:raise ValueError('REUSED_T05_OPERATION_COUNT_CHANGED')
 if sha(run/'prefix_evidence/T05_ORIGINAL_PRODUCER_BINDING.json')!=binding['producer_binding_sha256']:raise ValueError('REUSED_T05_PRODUCER_BINDING_CHANGED')
 verify_code(original,ROOT,binding['original_source_root'])
 if sha(run/'source.json')!=original['source_binding_sha256']:raise ValueError('REUSED_T05_SOURCE_CHANGED')
 for relative,expected in binding['files'].items():
  file=run/relative
  if not file.is_relative_to(run)or sha(file)!=expected:raise ValueError('REUSED_T05_EVIDENCE_CHANGED:'+relative)
 validate_stage(run,load(run/'prefix_evidence/T05_ORIGINAL_ROUTE_STATUS.json'),binding['producer_binding_sha256'])
 return binding

def prepare(old,job,*,qualification_mode='INCREMENTAL_REUSED_NATIVE_T05',seal_job=True,coordinator=None):
 if qualification_mode not in('INCREMENTAL_REUSED_NATIVE_T05','INCREMENTAL_REUSED_NATIVE_EXPORT_REPORT'):raise ValueError('UNSUPPORTED_INCREMENTAL_QUALIFICATION_MODE')
 old=Path(old);original=load(old/'PRODUCER_BINDING.json');state=load(old.parent/'STATUS.current.json')
 if original['profile']!=CONNECTED:raise ValueError('REUSED_T05_CONNECTED_PROFILE_REQUIRED')
 # Reject before allocating/copying another runtime unless every native T05
 # operation has actually finished successfully.
 records=validate_stage(old,state,sha(old/'PRODUCER_BINDING.json'))
 if state['status']not in('HALTED','U05_EXPORT_REPARSE_CONTROLS_RENDER_PASSED'):raise ValueError('REUSED_T05_ROUTE_NOT_TERMINAL')
 if verify_prefix(old)is None:raise ValueError('REUSED_T05_VERIFIED_SOURCE_PREFIX_REQUIRED')
 old_root=Path(os.path.commonpath(list(original['files'])));changes=verify_code(original,ROOT,old_root)
 for name,expected in original['job_inputs'].items():
  if sha(name)!=expected:raise ValueError('REUSED_T05_ORIGINAL_INPUT_CHANGED:'+name)
 fresh_assembly=0
 if(old/'SOURCE_ASSEMBLY_BINDING.json').exists():
  from . import source_assembly
  authority=load(old/'SOURCE_ASSEMBLY_BINDING.json');assembly_source=Path(authority['assembly_run'])
  if assembly_source.resolve()!=old.parent.resolve()/'assembly':raise ValueError('REUSED_T05_ASSEMBLY_AUTHORITY_CHANGED')
  if any(sha(name)!=expected for name,expected in authority['files'].items()):raise ValueError('REUSED_T05_ORIGINAL_ASSEMBLY_CHANGED')
  assembly=job/'assembly';assembly.mkdir()
  copy_file(assembly_source/'original.gbr',assembly/'original.gbr');copy_file(assembly_source/'INPUT_INVENTORY.json',assembly/'INPUT_INVENTORY.json')
  p.save(assembly/'ASSEMBLY_PRODUCER.json',source_assembly._producer(assembly))
  coordinator=Coordinator(job)if coordinator is None else coordinator
  coordinator.execute(assembly,'source_assembly',['construct'],module='source_assembly');coordinator.execute(assembly,'source_assembly',['1','2'],module='source_assembly')
  source_assembly.verify_job(assembly)
  if sha(assembly/'assembled.gbr')!=load(old/'source.json')['source_ref']['sha256']:raise ValueError('REUSED_T05_FRESH_ASSEMBLY_SOURCE_CHANGED')
  fresh_assembly=3
 run=job/'connected';run.mkdir()
 for folder in('runtime','source_snapshot','reference','prefix_evidence','audits','width_prefix_audits','raw_checkpoints','completion_checkpoints'):
  if(old/folder).exists():subprocess.run(['cp','-cR',str(old/folder),str(run/folder)],check=True)
 names=['source.json','CLEARANCE_SNAPSHOT.json','HOLE_ACCEPTANCE_SNAPSHOT.json','REMEDY_POLICY_SNAPSHOT.json','REFERENCE_BINDING.json','REFERENCE_CHANNELS.json','REUSED_PREFIX_BINDING.json','RAW_WIDTH_CHECKPOINT.json','T04_PRIOR_WIDTH_COMPATIBILITY.json','T04_SETTINGS_SNAPSHOT.json','PIN_SEPARATION_POLICY.json','STORAGE_ENCODING.json',*[s+'.json'for s in('t01','t03','t04','t02','t05')]]
 for name in names:
  if(old/name).exists():copy_file(old/name,run/name)
 evidence=run/'prefix_evidence';copy_file(old/'PRODUCER_BINDING.json',evidence/'T05_ORIGINAL_PRODUCER_BINDING.json');copy_file(old.parent/'STATUS.current.json',evidence/'T05_ORIGINAL_ROUTE_STATUS.json');copy_file(old/'input_inventory.json',evidence/'T05_ORIGINAL_INPUT_INVENTORY.json')
 if fresh_assembly:
  copy_file(old/'SOURCE_ASSEMBLY_BINDING.json',evidence/'T05_ORIGINAL_SOURCE_ASSEMBLY_BINDING.json')
  source_assembly.attach(run,job/'assembly')
 prefix_binding=load(run/'REUSED_PREFIX_BINDING.json')
 if prefix_binding.get('checked_legacy_files'):
  legacy=job/'legacy';subprocess.run(['cp','-cR',str(old.parent/'legacy'),str(legacy)],check=True)
  for relative,expected in prefix_binding['checked_legacy_files'].items():
   file=legacy/relative
   if not file.resolve().is_relative_to(legacy.resolve())or sha(file)!=expected:raise ValueError('REUSED_T05_CHECKING_ENVELOPE_CHANGED')
 for key in records:
  for suffix in('.log','.stderr.log'):copy_file(old.parent/'logs'/(key+suffix),evidence/'t05_logs'/(key+suffix))
 for name,expected in original['job_inputs'].items():
  if Path(name).name not in('input_inventory.json','SOURCE_ASSEMBLY_BINDING.json')and sha(run/Path(name).name)!=expected:raise ValueError('REUSED_T05_PHYSICAL_INPUT_CHANGED:'+name)
 files=[run/'t05.json',*[run/'audits/t05'/(m+'.json')for m in('construct','1','2')],evidence/'T05_ORIGINAL_PRODUCER_BINDING.json',evidence/'T05_ORIGINAL_ROUTE_STATUS.json',evidence/'T05_ORIGINAL_INPUT_INVENTORY.json',*(evidence/'t05_logs').glob('*')]
 if fresh_assembly:files.append(evidence/'T05_ORIGINAL_SOURCE_ASSEMBLY_BINDING.json')
 binding=dict(schema='incremental-native-t05/1',retained_operation_count=38,fresh_assembly_operations=fresh_assembly,original_run=str(old),original_source_root=str(old_root),original_route_completion='NOT_CLAIMED; only completed source/prefix and T05 reused',producer_binding_sha256=sha(old/'PRODUCER_BINDING.json'),code_dependency_changes=changes,files={str(file.relative_to(run)):sha(file)for file in files})
 p.save(run/'REUSED_T05_BINDING.json',binding)
 inventory=load(old/'input_inventory.json');revision=load(ROOT/'SOURCE_REVISION.json')if(ROOT/'SOURCE_REVISION.json').exists()else dict(status='SOURCE_DIGEST_BOUND_WORKING_CANDIDATE; release commit pending')
 inventory=dict(inventory,source_revision=revision,qualification_mode=qualification_mode,reused_t05_source_revision=inventory['source_revision']);p.save(run/'input_inventory.json',inventory);p.save(job/'INPUT_INVENTORY.json',inventory)
 if seal_job:seal(run,CONNECTED)
 return run

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verified-t05-run',required=True,type=Path);args=parser.parse_args()
 if not args.verified_t05_run.is_absolute():parser.error('verified T05 run must be absolute')
 work=configure();parent=work/'operator_routes/gerber_u05_tail';parent.mkdir(parents=True,exist_ok=True);job=parent/(datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex);job.mkdir();coordinator=Coordinator(job);coordinator.state.update(source_only=False,qualification_mode='INCREMENTAL_REUSED_NATIVE_T05',reused_operations=38)
 try:
  run=prepare(args.verified_t05_run,job,coordinator=coordinator);install_read_fence(job)
  from tools.preflight import verify_manifest
  p.save(job/'ASSET_MANIFEST_PROOF.json',dict(status='PASS',files=verify_manifest()));verify_sources(run)
  coordinator.execute(run,'export',['construct'],module='exporter');coordinator.execute(run,'export',['1','2'],module='exporter');coordinator.execute(run,'controls',['all'],module='controls');coordinator.execute(run,'remaining_defects',['all'],module='remaining_defects');coordinator.execute(run,'render',['all'],module='render')
  from .delivery import deliver
  coordinator.state.update(delivery=deliver(run),status='U05_EXPORT_REPARSE_CONTROLS_RENDER_PASSED',run=str(run),generated_sha256=sha(run/'export/top.art.gbr'));coordinator.record()
 except BaseException as error:
  coordinator.state.update(status='HALTED',error=str(error),remaining_operations='NOT_RUN; old job never resumed or promoted');coordinator.record();p.save(job/'HALTED.json',coordinator.state);raise

if __name__=='__main__':main()
