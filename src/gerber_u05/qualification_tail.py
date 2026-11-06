"""Requalify/report an unchanged native export under its frozen one-pass policy.

Every original successful native operation and failed audit stays immutable.
No geometry, growth decision, export or negative control is regenerated here.
"""
import argparse,datetime,hashlib,json,os,re,subprocess,uuid
from pathlib import Path
from . import pipeline as p
from .guard import ROOT,seal,verify_sources,install_read_fence
from .tail import prepare as prepare_t05
from .workspace import configure
from .run import Coordinator,CONNECTED

MODE='INCREMENTAL_REUSED_NATIVE_EXPORT_REPORT'
POST={'src/gerber_u05/guard.py','src/gerber_u05/tail.py','src/gerber_u05/render.py','src/gerber_u05/remaining_defects.py'}
NEW={'src/gerber_u05/qualification_tail.py'}
def sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()
def load(file):return json.loads(Path(file).read_bytes())

def verify_code(original,old_root,current=ROOT):
 old_root=Path(old_root);current=Path(current);known=set();changed=[]
 for name,expected in original['files'].items():
  old=Path(name)
  if not old.is_relative_to(old_root)or sha(old)!=expected:raise ValueError('QUALIFIED_EXPORT_ORIGINAL_CODE_CHANGED:'+name)
  relative=old.relative_to(old_root).as_posix();known.add(relative)
  if relative=='SOURCE_REVISION.json':continue
  actual=sha(current/relative)
  if actual!=expected:
   if relative not in POST:raise ValueError('QUALIFIED_EXPORT_GEOMETRY_OR_CHECK_CODE_CHANGED:'+relative)
   changed.append(dict(path=relative,before_sha256=expected,after_sha256=actual))
 files={f.relative_to(current).as_posix()for d in('src','contracts','tools','web')for f in(current/d).rglob('*')if f.is_file()and f.suffix in('.py','.json','.command','.js','.html')}
 if files-known-NEW:raise ValueError('QUALIFIED_EXPORT_UNKNOWN_PRODUCER_ADDED')
 return changed

def validate_export(run,state,producer_file=None):
 run=Path(run);producer_file=run/'PRODUCER_BINDING.json'if producer_file is None else Path(producer_file)
 keys=['connected_export_construct','connected_export_1','connected_export_2','connected_controls_all']
 records={k:state.get('checks',{}).get(k,{})for k in keys}
 if any(v.get('status')!='PASS'or v.get('returncode')!=0 for v in records.values()):raise ValueError('QUALIFIED_EXPORT_NATIVE_CHECK_INCOMPLETE')
 if records['connected_export_1']['pid']==records['connected_export_2']['pid']:raise ValueError('QUALIFIED_EXPORT_WORKERS_NOT_SEPARATE')
 a,b=[load(run/'export'/('proof_'+m+'.json'))for m in('1','2')];ledger=load(run/'export/ledger.json');bodysha=sha(run/'export/top.art.gbr')
 if a!=b or a['status']!='PASS'or a['generated_sha256']!=bodysha:raise ValueError('QUALIFIED_EXPORT_PAIRED_PROOF_CHANGED')
 if (a['geometry_producer_binding_sha256']!=sha(producer_file)or ledger['geometry_producer_binding_sha256']!=a['geometry_producer_binding_sha256']or ledger['generated_sha256']!=bodysha):raise ValueError('QUALIFIED_EXPORT_PRODUCER_BINDING_CHANGED')
 controls=load(run/'negative_controls/RESULT.json')
 if controls['status']!='PASS'or controls['generated_sha256']!=bodysha:raise ValueError('QUALIFIED_EXPORT_CONTROLS_CHANGED')
 return records

def prepare(old,job):
 old=Path(old);state=load(old.parent/'STATUS.current.json')
 if state['status']not in('HALTED','U05_EXPORT_REPARSE_CONTROLS_RENDER_PASSED'):raise ValueError('QUALIFIED_EXPORT_PREFIX_NOT_TERMINAL')
 records=validate_export(old,state);producer=load(old/'PRODUCER_BINDING.json');oldroot=Path(os.path.commonpath(list(producer['files'])));changes=verify_code(producer,oldroot)
 original_t05=load(old/'REUSED_T05_BINDING.json')['original_run']
 run=prepare_t05(Path(original_t05),job,qualification_mode=MODE,seal_job=False)
 for name in('source.json','t01.json','t03.json','t04.json','t02.json','t05.json','CLEARANCE_SNAPSHOT.json','REMEDY_POLICY_SNAPSHOT.json'):
  if sha(old/name)!=sha(run/name):raise ValueError('QUALIFIED_EXPORT_INPUT_OR_STAGE_CHANGED:'+name)
 for name in('export','negative_controls'):subprocess.run(['cp','-cR',str(old/name),str(run/name)],check=True)
 destination=run/'runtime/artifacts';missing=[]
 for file in(old/'runtime/artifacts').iterdir():
  if file.is_symlink()or not file.is_file():raise ValueError('UNSAFE_QUALIFIED_EXPORT_ARTIFACT')
  if not re.fullmatch(r'[a-z][a-z0-9-]{0,30}:[0-9a-f]{64}',file.name):
   if file.name.endswith('.tmp'):continue
   raise ValueError('UNKNOWN_QUALIFIED_EXPORT_ARTIFACT:'+file.name)
  if not(destination/file.name).exists():missing.append(str(file))
 for offset in range(0,len(missing),256):subprocess.run(['cp','-c',*missing[offset:offset+256],str(destination)],check=True)
 evidence=run/'prefix_evidence';old_producer=evidence/'NATIVE_ORIGINAL_PRODUCER_BINDING.json';old_producer.write_bytes((old/'PRODUCER_BINDING.json').read_bytes());old_state=evidence/'NATIVE_ORIGINAL_ROUTE_STATUS.json';old_state.write_bytes((old.parent/'STATUS.current.json').read_bytes())
 files=[old_producer,old_state,*[run/'export'/n for n in('top.art.gbr','ledger.json','proof_1.json','proof_2.json')],run/'negative_controls/RESULT.json']
 if(old/'REMAINING_DEFECT_AUDIT.json').exists():
  inventory=evidence/'ORIGINAL_OPTIONAL_GROWTH_AUDIT.json';inventory.write_bytes((old/'REMAINING_DEFECT_AUDIT.json').read_bytes());files.append(inventory)
 logs=evidence/'native_export_logs';logs.mkdir()
 for key in records:
  for suffix in('.log','.stderr.log'):
   src=old.parent/'logs'/(key+suffix);dest=logs/src.name;subprocess.run(['cp','-c',str(src),str(dest)],check=True);files.append(dest)
 binding=dict(schema='retained-verified-native-export/1',retained_operation_count=42,original_run=str(old),original_source_root=str(oldroot),source_binding_sha256=sha(run/'source.json'),producer_binding_sha256=sha(old_producer),code_changes=changes,geometry_and_native_check_implementations='BYTE_IDENTICAL',original_failed_audit='PRESERVED; further valid growth proposals are not missing selected repairs under the frozen one-pass policy',files={str(f.relative_to(run)):sha(f)for f in files})
 p.save(run/'REUSED_NATIVE_EXPORT_BINDING.json',binding);seal(run,CONNECTED);return run

def verify(run):
 run=Path(run);file=run/'REUSED_NATIVE_EXPORT_BINDING.json'
 if not file.exists():return None
 binding=load(file)
 if binding['retained_operation_count']!=42:raise ValueError('QUALIFIED_EXPORT_OPERATION_COUNT_CHANGED')
 for name,expected in binding['files'].items():
  f=run/name
  if not f.is_relative_to(run)or sha(f)!=expected:raise ValueError('QUALIFIED_EXPORT_EVIDENCE_CHANGED:'+name)
 original=run/'prefix_evidence/NATIVE_ORIGINAL_PRODUCER_BINDING.json';producer=load(original)
 if sha(original)!=binding['producer_binding_sha256']or sha(run/'source.json')!=producer['source_binding_sha256']or sha(run/'source.json')!=binding['source_binding_sha256']:raise ValueError('QUALIFIED_EXPORT_SOURCE_OR_PRODUCER_CHANGED')
 verify_code(producer,binding['original_source_root']);validate_export(run,load(run/'prefix_evidence/NATIVE_ORIGINAL_ROUTE_STATUS.json'),original);return binding

def required_coverage(store,stages,groups,contracts):
 from dataclasses import asdict
 rows=[];expected_radii=[c.notch_radius_mm for c in contracts]
 for stage,value in stages.items():
  actual=[]
  for record in value['intra']['rounds']:
   if record.get('status')=='RETAINED_SUCCESSFUL_CONSTRUCTION_PREFIX':actual.extend(record['radii_mm']);continue
   radius=record['radius_mm'];actual.append(radius);contract=next(c for c in contracts if c.notch_radius_mm==radius)
   if record['plan']['contract']!=asdict(contract):raise ValueError('QUALIFIED_REMEDY_ROUND_POLICY_CHANGED:'+stage)
  if actual!=expected_radii:raise ValueError('QUALIFIED_REMEDY_FROZEN_ROUND_ORDER_CHANGED:'+stage)
  for fill in value['intra']['fills']:
   own=fill['original_owner_id']
   if own not in groups:raise ValueError('QUALIFIED_REMEDY_ORIGINAL_OWNER_MISSING')
   logical=p.geometry(store,fill['logical_patch_ref']);missing=logical.difference(groups[own].buffer(contracts[0].file_uncertainty_mm)).area
   if missing>contracts[0].area_epsilon_mm2:raise ValueError('NATIVE_REQUIRED_POCKET_OR_NOTCH_MISSING:'+stage+':'+fill['source_id'])
   rows.append(dict(stage=stage,source_id=fill['source_id'],original_owner_id=own,missing_area_mm2=missing))
 return dict(passed=True,planned_owner_surface_updates=len(rows),records=rows,execution_policy='FROZEN_CONSECUTIVE_COMPONENTS_NO_REVISIT')

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verified-export-run',type=Path,required=True);args=parser.parse_args()
 if not args.verified_export_run.is_absolute():parser.error('verified export run must be absolute')
 parent=configure()/'operator_routes/gerber_u05_qualification';parent.mkdir(parents=True,exist_ok=True);job=parent/(datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex);job.mkdir();c=Coordinator(job);c.state.update(source_only=False,qualification_mode=MODE,reused_operations=42,fresh_operations=2)
 try:
  run=prepare(args.verified_export_run,job);install_read_fence(job)
  from tools.preflight import verify_manifest
  p.save(job/'ASSET_MANIFEST_PROOF.json',dict(status='PASS',files=verify_manifest()));verify_sources(run)
  c.execute(run,'remaining_defects',['all'],module='remaining_defects');c.execute(run,'render',['all'],module='render')
  from .delivery import deliver
  c.state.update(delivery=deliver(run),status='U05_EXPORT_REPARSE_CONTROLS_RENDER_PASSED',run=str(run),generated_sha256=sha(run/'export/top.art.gbr'));c.record()
 except BaseException as error:
  c.state.update(status='HALTED',error=str(error),remaining_operations='NOT_RUN; original failures and all checked prefixes remain unchanged');c.record();p.save(job/'HALTED.json',c.state);raise

if __name__=='__main__':main()
