"""Hash-bound source jobs. Stored verdicts never replace fresh geometry checks."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def producer_files():
 files=[p for d in('src','contracts','tools','web')for p in(ROOT/d).rglob('*')if p.is_file()and p.suffix in('.py','.json','.command','.js','.html')]
 if(ROOT/'SOURCE_REVISION.json').exists():files.append(ROOT/'SOURCE_REVISION.json')
 return sorted(files)
def seal(run,profile):
 from src.t04_settings import capture_job,read_snapshot,SNAPSHOT_NAME
 if not(run/SNAPSHOT_NAME).exists():capture_job(run)
 read_snapshot(run/SNAPSHOT_NAME)
 from .pipeline import save
 inputs=[run/name for name in('input_inventory.json','LEGACY_REFERENCE_JOB.json','CLEARANCE_SNAPSHOT.json','REMEDY_POLICY_SNAPSHOT.json','POLICY_SNAPSHOT.json','REFERENCE_BINDING.json','REFERENCE_CHANNELS.json','REUSED_PREFIX_BINDING.json','REUSED_T05_BINDING.json','REUSED_NATIVE_EXPORT_BINDING.json','REUSED_LEGACY_BINDING.json','REUSED_WIDTH_BINDING.json','SOURCE_ASSEMBLY_BINDING.json','PIN_SEPARATION_POLICY.json','T04_SETTINGS_SNAPSHOT.json','STORAGE_ENCODING.json')if(run/name).is_file()]
 save(run/'PRODUCER_BINDING.json',dict(job_inputs={str(p):sha(p)for p in inputs},schema='source-only-gerber-u05-producer/1',profile=profile,files={str(p):sha(p)for p in producer_files()},source_binding_sha256=sha(run/'source.json')))
def verify_sources(run):
 from importlib.metadata import version
 import shapely
 runtime=json.loads((ROOT/'contracts/gerber_u05/runtime.json').read_bytes())
 if {name:version(name)for name in runtime['packages']}!=runtime['packages']or shapely.geos_version_string!=runtime['geos']:raise ValueError('GERBER_U05_PINNED_RUNTIME_CHANGED')
 seal=json.loads((run/'PRODUCER_BINDING.json').read_bytes())
 if set(seal['files'])!={str(file)for file in producer_files()}:raise ValueError('GERBER_RUN_PRODUCER_NAMESPACE_CHANGED')
 for name,expected in seal['files'].items():
  if sha(name)!=expected:raise ValueError('GERBER_RUN_PRODUCER_CHANGED:'+name)
 for name,expected in seal.get('job_inputs',{}).items():
  if sha(name)!=expected:raise ValueError('GERBER_JOB_INPUT_CHANGED:'+name)
 if sha(run/'source.json')!=seal['source_binding_sha256']:raise ValueError('GERBER_RUN_SOURCE_BINDING_CHANGED')
 from .source_assembly import verify_run
 verify_run(run)
 if (run/'HALTED.json').exists():raise ValueError('HALTED_RUN_CANNOT_RESUME')
 from .prefix import verify as verify_prefix
 verify_prefix(run)
 if(run/'REUSED_T05_BINDING.json').exists():
  from .tail import verify as verify_t05
  verify_t05(run)
 if(run/'REUSED_NATIVE_EXPORT_BINDING.json').exists():
  from .qualification_tail import verify as verify_export
  verify_export(run)
 if(run/'REUSED_LEGACY_BINDING.json').exists():
  from .legacy_prefix import verify as verify_legacy
  verify_legacy(run)
 if(run/'REUSED_WIDTH_BINDING.json').exists():
  from .width_adoption import verify as verify_width
  verify_width(run)
 return seal

def install_read_fence(run,legacy_authority=None):
 """Generation cannot open any retained result outside its own fresh job."""
 import os,sys
 from .workspace import configure
 evidence=(configure()/'evidence').resolve();allowed=[Path(run).resolve()]
 # A normal app checkout contains out/evidence. Its source-root authority must
 # not accidentally grant access to every historical result nested underneath.
 if ROOT.resolve()!=evidence and ROOT.resolve().is_relative_to(evidence):allowed.append(ROOT.resolve())
 assembly_binding=Path(run)/'SOURCE_ASSEMBLY_BINDING.json'
 if assembly_binding.exists():
  assembly_seal=json.loads((Path(run)/'PRODUCER_BINDING.json').read_bytes())
  if assembly_seal.get('job_inputs',{}).get(str(assembly_binding))!=sha(assembly_binding):raise ValueError('SOURCE_ASSEMBLY_READ_AUTHORITY_CHANGED')
  from .source_assembly import verify_run
  authority=verify_run(Path(run));allowed.append(Path(authority['assembly_run']).resolve())
 # Connected workers reconstruct their clearance-only T04 envelopes from the
 # freshly generated legacy sibling. Grant that exact sealed job-local role,
 # never the parent directory or arbitrary historical reservation inputs.
 reference=Path(run)/'REFERENCE_BINDING.json'
 if reference.exists():
  seal_value=json.loads((Path(run)/'PRODUCER_BINDING.json').read_bytes())
  if seal_value.get('job_inputs',{}).get(str(reference))!=sha(reference):raise ValueError('LOCAL_REFERENCE_READ_AUTHORITY_CHANGED')
  legacy=Path(run).parent/'legacy'
  if legacy.is_symlink()or legacy.resolve().parent!=Path(run).resolve().parent:raise ValueError('LOCAL_REFERENCE_MUST_BE_SAME_JOB')
  authority=json.loads(reference.read_bytes());source=json.loads((Path(run)/'source.json').read_bytes())
  if authority.get('schema')!='job-local-generated-reservation/1'or authority.get('source_only')is not True or authority.get('source_sha256')!=source['source_ref']['sha256']:raise ValueError('LOCAL_REFERENCE_SOURCE_AUTHORITY_CHANGED')
  legacy_seal=verify_sources(legacy)
  if legacy_seal.get('profile')!='fresh-legacy-reservation-reference/1'or json.loads((legacy/'source.json').read_bytes())['source_ref']!=source['source_ref']:raise ValueError('LOCAL_REFERENCE_ROLE_OR_SOURCE_CHANGED')
  allowed.append(legacy.resolve())
 for width in(Path(run)/'REUSED_WIDTH_BINDING.json',Path(run)/'connected/REUSED_WIDTH_BINDING.json'):
  if not width.exists():continue
  width_seal=json.loads((width.parent/'PRODUCER_BINDING.json').read_bytes())
  if width_seal.get('job_inputs',{}).get(str(width))!=sha(width):raise ValueError('REUSED_WIDTH_READ_AUTHORITY_CHANGED')
  from .width_adoption import verify as verify_width
  authority=verify_width(width.parent);allowed.extend(Path(root).resolve()for root in authority['original']['original_source_roots'])
 if legacy_authority is not None:
  from .legacy_prefix import inspect
  authority=inspect(legacy_authority['original_run'],legacy_authority['through']);allowed.extend(Path(root).resolve()for root in authority.get('original_source_roots',[authority['original_source_root']]))
 for candidate in (Path(run)/'REUSED_LEGACY_BINDING.json',Path(run)/'legacy/REUSED_LEGACY_BINDING.json',Path(run).parent/'legacy/REUSED_LEGACY_BINDING.json'):
  if not candidate.exists():continue
  seal_value=json.loads((candidate.parent/'PRODUCER_BINDING.json').read_bytes())
  if seal_value.get('job_inputs',{}).get(str(candidate))!=sha(candidate):raise ValueError('LEGACY_PREFIX_READ_AUTHORITY_CHANGED')
  from .legacy_prefix import verify as verify_legacy
  authority=verify_legacy(candidate.parent);allowed.extend(Path(root).resolve()for root in authority['original'].get('original_source_roots',[authority['original']['original_source_root']]))
  break
 prefix=Path(run)/'REUSED_PREFIX_BINDING.json'
 if not prefix.exists():prefix=Path(run)/'connected/REUSED_PREFIX_BINDING.json'
 if prefix.exists():
  seal=json.loads((prefix.parent/'PRODUCER_BINDING.json').read_bytes())
  if seal.get('job_inputs',{}).get(str(prefix))!=sha(prefix):raise ValueError('REUSED_PREFIX_READ_AUTHORITY_CHANGED')
  allowed.append(Path(json.loads(prefix.read_bytes())['original_source_root']).resolve())
 t05=Path(run)/'REUSED_T05_BINDING.json'
 if not t05.exists():t05=Path(run)/'connected/REUSED_T05_BINDING.json'
 if t05.exists():
  seal=json.loads((t05.parent/'PRODUCER_BINDING.json').read_bytes())
  if seal.get('job_inputs',{}).get(str(t05))!=sha(t05):raise ValueError('REUSED_T05_READ_AUTHORITY_CHANGED')
  allowed.append(Path(json.loads(t05.read_bytes())['original_source_root']).resolve())
 native=Path(run)/'REUSED_NATIVE_EXPORT_BINDING.json'
 if not native.exists():native=Path(run)/'connected/REUSED_NATIVE_EXPORT_BINDING.json'
 if native.exists():
  seal=json.loads((native.parent/'PRODUCER_BINDING.json').read_bytes())
  if seal.get('job_inputs',{}).get(str(native))!=sha(native):raise ValueError('RETAINED_NATIVE_EXPORT_READ_AUTHORITY_CHANGED')
  allowed.append(Path(json.loads(native.read_bytes())['original_source_root']).resolve())
 def hook(event,args):
  if event!='open'or not isinstance(args[0],(str,bytes,os.PathLike)):return
  path=Path(os.fsdecode(args[0])).resolve()
  if path.is_relative_to(evidence)and not any(path.is_relative_to(p)for p in allowed):
   raise PermissionError('HISTORICAL_EVIDENCE_READ_FORBIDDEN:'+str(path))
 sys.addaudithook(hook)
