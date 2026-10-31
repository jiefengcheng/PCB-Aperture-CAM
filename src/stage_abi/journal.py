"""Recorded-prefix continuation of the same immutable-input execution attempt.

Only this job's hash-bound, already executed checks may be replayed. Inputs,
code and event ordinal must match. This is explicit REPLAY of prior evidence,
not a fresh geometry execution or an untrusted cached-result hint.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import json,os,time
from .store import canonical,digest
from .contracts import StageABIError
ACTIVE=ContextVar('stage_abi_execution_journal',default=None)

class ExecutionJournal:
 def __init__(self,store,key,binding,job,bounds=None):
  self.store=store;self.binding=digest(canonical(binding));self.path=store.root/'journals'/job['job_id'];self.path.parent.mkdir(exist_ok=True)
  if self.path.is_symlink():raise StageABIError('JOURNAL_UNSAFE','symlink journal')
  self.path.mkdir(exist_ok=True);self.cursor=0;self.replayed=0;self.fresh=0;self.created=job['created_epoch'];self.monotonic_start=time.monotonic();self.initial_elapsed=max(0.,time.time()-self.created,self.monotonic_start-job.get('created_monotonic',self.monotonic_start))
  if time.time()<self.created-1:raise StageABIError('CLOCK_MOVED_BACKWARDS','execution budget clock')
  self.total=len(list(self.path.glob('event-*.json')));self.bounds=bounds;self.output_bytes=0;self.written=set()
 def elapsed(self):return self.initial_elapsed+time.monotonic()-self.monotonic_start
 def charge(self,kind,blob):
  if self.bounds is None:return
  if self.elapsed()>self.bounds['max_seconds']:raise StageABIError('BUDGET_EXHAUSTED','original attempt deadline')
  identity=(kind,digest(blob))
  if identity not in self.written:
   if self.output_bytes+len(blob)>self.bounds['max_output_bytes']:raise StageABIError('BUDGET_EXHAUSTED','complete attempt output budget')
   self.written.add(identity);self.output_bytes+=len(blob)
 def call(self,name,inputs,producer):
  ordinal=self.cursor;p=self.path/f'event-{ordinal:08d}.json';input_sha=digest(canonical(inputs));self.cursor+=1
  if p.is_symlink():raise StageABIError('JOURNAL_UNSAFE','symlink event')
  if p.exists():
   try:record=json.loads(p.read_bytes())
   except ValueError as error:raise StageABIError('JOURNAL_CORRUPTED',str(error)) from error
   if record['binding_sha256']!=self.binding or record['ordinal']!=ordinal or record['name']!=name or record['inputs_sha256']!=input_sha:raise StageABIError('JOURNAL_REPLAY_MISMATCH',name)
   result=self.store.get_json(record['result_ref'],kind='execution-event');self.charge('execution-event',canonical(result));self.charge('journal-record',canonical(record));self.replayed+=1;return result
  if ordinal<self.total:raise StageABIError('JOURNAL_EVENT_MISSING',str(ordinal))
  result=producer();reference=self.store.put_json('execution-event',result);record=dict(ordinal=ordinal,name=name,inputs_sha256=input_sha,binding_sha256=self.binding,result_ref=reference);self.charge('journal-record',canonical(record));temporary=self.path/f'pending-{ordinal:08d}-{os.getpid()}.tmp'
  if temporary.is_symlink():raise StageABIError('JOURNAL_UNSAFE','temporary event')
  with temporary.open('wb') as stream:stream.write(canonical(record));stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,p);self.total+=1;self.fresh+=1;return result
 def assert_consumed(self):
  if self.cursor!=self.total:raise StageABIError('JOURNAL_PREFIX_NOT_CONSUMED','recorded execution diverged')
 def report(self):return dict(mode='OWN_ATTEMPT_PREFIX_REPLAY' if self.replayed else 'FRESH_EXECUTION',replayed_events=self.replayed,fresh_events=self.fresh,total_events=self.total,logical_output_bytes=self.output_bytes,elapsed_seconds=self.elapsed())

@contextmanager
def execution_journal(store,key,binding,job,bounds=None):
 journal=ExecutionJournal(store,key,binding,job,bounds=bounds);token=ACTIVE.set(journal)
 try:yield journal
 finally:ACTIVE.reset(token)

def journalled(name,inputs,producer):
 journal=ACTIVE.get();return producer() if journal is None else journal.call(name,inputs,producer)
