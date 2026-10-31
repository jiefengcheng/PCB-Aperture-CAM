"""Fail-closed local orchestration for explicitly prepared native regions.

Geometry belongs to stage adapters; this layer enforces custody and sequence.
It never freezes results, grants acceptance, exports a board, or edits inputs.
"""
from pathlib import Path
import hashlib,json,shutil
from shapely import from_wkb
ORDER=('T01','T03','T04','T02','T05')

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def inventory(folder):
 folder=Path(folder);result={}
 for p in sorted(folder.rglob('*')):
  if p.is_symlink():raise ValueError('SYMLINK_EVIDENCE_REJECTED')
  if p.is_file():result[str(p.relative_to(folder))]=digest(p)
 return result

def verify_files(folder,files):
 folder=Path(folder).resolve()
 for name,h in files.items():
  p=folder/name
  if p.is_symlink() or not p.resolve().is_relative_to(folder) or digest(p)!=h:raise ValueError('INPUT_FILE_BINDING_CHANGED:'+name)

def copy_bound(source,target,files):
 verify_files(source,files);target=Path(target);target.mkdir()
 for name in sorted(files):
  p=target/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(Path(source)/name,p)

def frozen_fingerprint(root,entry):
 p=(root/entry['path']).resolve()
 if not p.is_relative_to(root.resolve()) or digest(p/'FREEZE_RECEIPT.json')!=entry['receipt_sha256']:raise ValueError('FROZEN_RECEIPT_CHANGED')
 receipt=read(p/'FREEZE_RECEIPT.json')
 if 'manifest_sha256' in receipt and digest(p/'SHA256SUMS.json')!=receipt['manifest_sha256']:raise ValueError('FROZEN_MANIFEST_CHANGED')
 files=read(p/'SHA256SUMS.json') if (p/'SHA256SUMS.json').exists() else receipt['files']
 verify_files(p/'frozen',files)
 return dict(path=entry['path'],receipt_sha256=entry['receipt_sha256'],files=len(files))

class TraceFirstPipeline:
 def __init__(self,root,config,output):
  self.root=Path(root).resolve();self.config=config;self.out=Path(output).resolve()
  if not self.out.is_relative_to(self.root/'out') or self.out.exists():raise ValueError('FRESH_PROJECT_LOCAL_OUTPUT_REQUIRED')
  if config.get('schema')!='prepared-native-region-pipeline/1' or config.get('sequence')!=list(ORDER):raise ValueError('EXACT_TRACE_FIRST_SEQUENCE_REQUIRED')
  if config.get('t03_mode')!='growth-only-no-route-change':raise ValueError('ROUTE_REPAIR_ADAPTER_NOT_QUALIFIED')
  if config.get('profile')!='round-class-full-route-width-whole-rectangle-spindle/1':raise ValueError('UNSUPPORTED_CONSTRUCTION_PROFILE')
  self.protected=config['protected_freezes']
  if {r['crop'] for r in self.protected}!={'C01','C02','C03'}:raise ValueError('ALL_ACCEPTED_CROPS_MUST_BE_PROTECTED')
  self.inputs={}
  for name,b in config['inputs'].items():
   p=self.root/b['path']
   if '..' in Path(b['path']).parts or not p.is_relative_to(self.root) or not p.is_file() or digest(p)!=b['sha256']:raise ValueError('PINNED_INPUT_CHANGED:'+name)
   if not p.resolve().is_relative_to(self.root) and b.get('existing_project_archive_target')!=str(p.resolve()):raise ValueError('UNBOUND_PROJECT_ARCHIVE_TARGET:'+name)
   self.inputs[name]=p
  self.check_protected()
 def check_protected(self):return [frozen_fingerprint(self.root,r) for r in self.protected]
 def execute(self,adapters,*,mode='CONSTRUCTION'):
  if set(adapters)!=set(ORDER) or mode not in ('CONSTRUCTION','SAVED_STAGE_REPLAY'):raise ValueError('COMPLETE_EXPLICIT_STAGE_ADAPTERS_REQUIRED')
  self.out.mkdir();write(self.out/'PIPELINE_CONFIG.json',self.config);rows=[];previous=None
  try:
   for stage in ORDER:
    self.check_protected()
    for name,p in self.inputs.items():
     if digest(p)!=self.config['inputs'][name]['sha256']:raise ValueError('PINNED_INPUT_CHANGED:'+name)
    write(self.out/'PROGRESS.json',dict(stage=stage,status='RUNNING',mode=mode))
    adapters[stage](self.out,self.inputs)
    folder=self.out/stage;result=read(folder/'RESULT.json');before=folder/'before.wkb';after=folder/'after.wkb'
    if result.get('after_sha256')!=digest(after):raise ValueError('STAGE_AFTER_BINDING_FAILED:'+stage)
    if previous is not None and digest(before)!=previous:raise ValueError('EXACT_PREDECESSOR_REQUIRED:'+stage)
    a,b=from_wkb(after.read_bytes()),from_wkb(before.read_bytes())
    if not a.is_valid or not b.is_valid or b.difference(a).area>1e-12:raise ValueError('INVALID_OR_REMOVED_COPPER:'+stage)
    if stage=='T03' and (digest(before)!=digest(after) or result.get('route_changes')!=0 or result.get('growth_check_passed') is not True):raise ValueError('T03_NO_CHANGE_NOT_ESTABLISHED')
    previous=digest(after);rows.append(dict(stage=stage,after_sha256=previous,before_sha256=digest(before),files=inventory(folder)))
    write(self.out/'STAGE_RECEIPTS.json',rows);self.check_protected()
   for name,p in self.inputs.items():
    if digest(p)!=self.config['inputs'][name]['sha256']:raise ValueError('PINNED_INPUT_CHANGED:'+name)
   receipt=dict(status='PASS_PREPARED_REGION_PIPELINE_'+mode,mode=mode,sequence=list(ORDER),after_sha256=previous,protected=self.check_protected(),owner_acceptance='NOT_GRANTED_BY_PIPELINE',qualification='LOCAL_MODEL_ONLY; independent/native/electrical/manufacturing NOT_ESTABLISHED')
   write(self.out/'PIPELINE_RECEIPT.json',receipt);return receipt
  except Exception as error:
   write(self.out/'FAILURE.json',dict(stage=stage,error=type(error).__name__,reason=str(error),dependent_stages='NOT_RUN',completed_stages=[r['stage'] for r in rows]))
   raise
  finally:self.check_protected()

def replay_adapter(stage,source,files):
 """Copy saved geometry as replay only; all file hashes checked before copying."""
 def run(output,inputs):
  copy_bound(source,output/stage,files)
  if stage=='T03':
   # Legacy C03 stores a check receipt only; expose an explicit no-change scene.
   predecessor=output/'T01/after.wkb';shutil.copyfile(predecessor,output/stage/'before.wkb');shutil.copyfile(predecessor,output/stage/'after.wkb');r=read(output/stage/'RESULT.json')
   if r.get('check')!='PASS_SOURCE_VISIBLE_GROWTH_ONLY' or r.get('route_changes')!=0:raise ValueError('LEGACY_T03_VERDICT_NOT_ADMISSIBLE')
   r.update(after_sha256=digest(predecessor),growth_check_passed=True);write(output/stage/'RESULT.json',r)
 return run
