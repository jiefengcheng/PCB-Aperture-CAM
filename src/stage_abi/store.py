"""Content-addressed immutable JSON/binary artifacts and atomic attempt custody.

No user paths are resolved by an artifact reference. This is a local integrity
boundary, not protection against an attacker able to rewrite the whole checkout.
"""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket,time,subprocess
from .contracts import StageABIError, ref, finite_json


def canonical(value):
 finite_json(value)
 return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def digest(blob):return hashlib.sha256(blob).hexdigest()

def process_identity(pid=None):
 pid=os.getpid() if pid is None else pid
 try:
  value=subprocess.run(['ps','-p',str(pid),'-o','lstart='],capture_output=True,text=True,check=False).stdout.strip()
 except OSError:return None
 return None if not value else dict(host=socket.gethostname(),pid=pid,start=value)


def owner_state(owner):
 if type(owner) is not dict or owner.get('host')!=socket.gethostname():return 'UNKNOWN'
 current=process_identity(owner.get('pid'))
 if current is None:
  try:os.kill(owner['pid'],0)
  except ProcessLookupError:return 'DEAD'
  except (PermissionError,ValueError,TypeError):return 'UNKNOWN'
  return 'UNKNOWN'
 return 'LIVE' if current==owner else 'DEAD'


class ArtifactStore:
 def __init__(self, root):
  self.root=Path(root)
  if self.root.is_symlink():raise StageABIError('UNSAFE_STORE','symlink store')
  self.root.mkdir(parents=True,exist_ok=True)
  for name in ('artifacts','jobs','locks'):
   p=self.root/name
   if p.is_symlink():raise StageABIError('UNSAFE_STORE','symlink directory')
   p.mkdir(exist_ok=True)
 def put(self, kind, blob):
  if type(kind) is not str or not re.fullmatch('[a-z][a-z0-9-]{0,30}',kind):raise StageABIError('ARTIFACT_KIND_INVALID','kind')
  if type(blob) is not bytes:raise StageABIError('ARTIFACT_BYTES_REQUIRED','blob')
  from .journal import ACTIVE
  journal=ACTIVE.get()
  if journal is not None:journal.charge(kind,blob)
  h=digest(blob);artifact_id=kind+':'+h;p=self.root/'artifacts'/artifact_id
  with self._lock('artifact-'+h):
   if p.is_symlink():raise StageABIError('UNSAFE_STORE','symlink artifact')
   if p.exists():
    if p.read_bytes()!=blob:raise StageABIError('ARTIFACT_CORRUPTED',artifact_id)
   else:
    temporary=p.with_name(p.name+'.tmp')
    if temporary.is_symlink():raise StageABIError('UNSAFE_STORE','symlink artifact temporary')
    with temporary.open('wb') as stream:stream.write(blob);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,p)
  return dict(artifact_id=artifact_id,sha256=h)
 def put_json(self, kind, value):return self.put(kind,canonical(value))
 def get(self, reference, *, kind=None):
  ref(reference,'artifact_ref');aid=reference['artifact_id'];p=self.root/'artifacts'/aid
  expected=aid.split(':',1)
  if len(expected)!=2 or expected[1]!=reference['sha256'] or (kind is not None and expected[0]!=kind):raise StageABIError('ARTIFACT_KIND_MISMATCH',aid)
  if p.is_symlink() or not p.is_file():raise StageABIError('ARTIFACT_MISSING_OR_UNSAFE',aid)
  data=p.read_bytes()
  if digest(data)!=reference['sha256']:raise StageABIError('ARTIFACT_CORRUPTED',aid)
  return data
 def get_json(self, reference, *, kind=None):
  try:result=json.loads(self.get(reference,kind=kind))
  except (UnicodeError,json.JSONDecodeError) as error:raise StageABIError('ARTIFACT_JSON_INVALID',str(error)) from error
  finite_json(result);return result
 @contextlib.contextmanager
 def _lock(self, identity):
  p=self.root/'locks'/identity
  if p.is_symlink():raise StageABIError('UNSAFE_STORE','symlink lock')
  with p.open('a+b') as lock:
   fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
   try:yield
   finally:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)
 def _job_id(self, key):return digest(canonical(key))
 def begin(self, key, binding):
  identity=self._job_id(key);bound=digest(canonical(binding));binding_ref=self.put_json('execution-binding',binding);p=self.root/'jobs'/identity
  with self._lock(identity):
   if p.is_symlink():raise StageABIError('UNSAFE_STORE','symlink job')
   if p.exists():
    previous=json.loads(p.read_bytes())
    if previous['binding_sha256']!=bound:raise StageABIError('IDEMPOTENCY_CONFLICT',identity)
    if previous['status']=='RUNNING' and owner_state(previous.get('owner'))=='DEAD':
     previous=dict(previous,owner=process_identity(),resume_count=previous.get('resume_count',0)+1)
     self._write_job(p,previous);return True,previous
    return False,previous
   value=dict(job_id=identity,binding_sha256=bound,status='RUNNING',request_binding_ref=binding_ref,result_ref=None,checkpoint_ref=None,owner=process_identity(),created_epoch=time.time(),created_monotonic=time.monotonic(),resume_count=0)
   self._write_job(p,value)
   return True,value
 def checkpoint(self,key,binding,checkpoint_ref):
  self.get(checkpoint_ref);return self._update(key,binding,checkpoint_ref=checkpoint_ref)
 def finish(self,key,binding,result_ref,*,failed=False):
  self.get(result_ref)
  return self._update(key,binding,status='FAILED' if failed else 'COMPLETED',result_ref=result_ref)
 def _update(self,key,binding,**changes):
  identity=self._job_id(key);p=self.root/'jobs'/identity
  with self._lock(identity):
   if p.is_symlink() or not p.is_file():raise StageABIError('JOB_MISSING_OR_UNSAFE',identity)
   old=json.loads(p.read_bytes())
   if old['binding_sha256']!=digest(canonical(binding)):raise StageABIError('IDEMPOTENCY_CONFLICT',identity)
   if old['status']!='RUNNING':
    if any(old[k]!=v for k,v in changes.items()):raise StageABIError('TERMINAL_JOB_IMMUTABLE',identity)
    return old
   if old.get('owner') is not None and old['owner']!=process_identity():raise StageABIError('JOB_LEASE_NOT_OWNED',identity)
   result=dict(old,**changes);self._write_job(p,result);return result
 def _write_job(self,p,result):
   temporary=p.with_name(p.name+'.tmp')
   if temporary.is_symlink():raise StageABIError('UNSAFE_STORE','symlink temporary job')
   with temporary.open('wb') as stream:stream.write(canonical(result));stream.flush();os.fsync(stream.fileno())
   os.replace(temporary,p)
