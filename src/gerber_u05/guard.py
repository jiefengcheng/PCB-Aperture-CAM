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
 from .pipeline import save
 inputs=[run/name for name in('input_inventory.json','LEGACY_REFERENCE_JOB.json','CLEARANCE_SNAPSHOT.json','REMEDY_POLICY_SNAPSHOT.json','POLICY_SNAPSHOT.json','REFERENCE_BINDING.json')if(run/name).is_file()]
 save(run/'PRODUCER_BINDING.json',dict(job_inputs={str(p):sha(p)for p in inputs},schema='source-only-gerber-u05-producer/1',profile=profile,files={str(p):sha(p)for p in producer_files()},source_binding_sha256=sha(run/'source.json')))
def verify_sources(run):
 from importlib.metadata import version
 import shapely
 runtime=json.loads((ROOT/'contracts/gerber_u05/runtime.json').read_bytes())
 if {name:version(name)for name in runtime['packages']}!=runtime['packages']or shapely.geos_version_string!=runtime['geos']:raise ValueError('GERBER_U05_PINNED_RUNTIME_CHANGED')
 seal=json.loads((run/'PRODUCER_BINDING.json').read_bytes())
 for name,expected in seal['files'].items():
  if sha(name)!=expected:raise ValueError('GERBER_RUN_PRODUCER_CHANGED:'+name)
 for name,expected in seal.get('job_inputs',{}).items():
  if sha(name)!=expected:raise ValueError('GERBER_JOB_INPUT_CHANGED:'+name)
 if sha(run/'source.json')!=seal['source_binding_sha256']:raise ValueError('GERBER_RUN_SOURCE_BINDING_CHANGED')
 if (run/'HALTED.json').exists():raise ValueError('HALTED_RUN_CANNOT_RESUME')
 return seal

def install_read_fence(run):
 """Generation cannot open any retained result outside its own fresh job."""
 import os,sys
 from .workspace import configure
 evidence=configure()/'evidence';allowed=(ROOT.resolve(),Path(run).resolve())
 def hook(event,args):
  if event!='open'or not isinstance(args[0],(str,bytes,os.PathLike)):return
  path=Path(os.fsdecode(args[0])).resolve()
  if path.is_relative_to(evidence)and not any(path.is_relative_to(p)for p in allowed):
   raise PermissionError('HISTORICAL_EVIDENCE_READ_FORBIDDEN:'+str(path))
 sys.addaudithook(hook)
