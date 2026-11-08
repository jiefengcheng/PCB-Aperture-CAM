import json
import hashlib
import pytest
from src.gerber_u05 import incremental as inc


def prefix(root,original):
 run=root/'connected';run.mkdir(parents=True)
 (run/'REUSED_PREFIX_BINDING.json').write_text(json.dumps(dict(original_run=str(original))))
 return run


def test_nested_family_resolution_verifies_each_link(tmp_path,monkeypatch):
 base=tmp_path/'base/connected';base.mkdir(parents=True)
 first=prefix(tmp_path/'first',base);second=prefix(tmp_path/'second',first);seen=[]
 def verify(run):
  seen.append(run)
  return json.loads((run/'REUSED_PREFIX_BINDING.json').read_text())
 monkeypatch.setattr(inc,'verify_native_prefix',verify)
 assert inc.source_family_job(second)==base.parent
 assert seen==[second,first]


def test_prefix_authority_cycle_rejected(tmp_path,monkeypatch):
 a=prefix(tmp_path/'a',tmp_path/'b/connected');b=prefix(tmp_path/'b',a)
 monkeypatch.setattr(inc,'verify_native_prefix',lambda run:json.loads((run/'REUSED_PREFIX_BINDING.json').read_text()))
 with pytest.raises(ValueError,match='AUTHORITY_CYCLE'):inc.source_family_job(a)


def test_nested_records_preserve_new_failure_and_old_pass(tmp_path,monkeypatch):
 base=tmp_path/'base/connected';base.mkdir(parents=True);run=prefix(tmp_path/'new',base)
 passed=dict(status='PASS',returncode=0,pid=1);failed=dict(status='FAIL',returncode=1,pid=2)
 state=dict(checks=dict(connected_t02_1=passed,connected_t05_construct=failed))
 (run.parent/'STATUS.current.json').write_text(json.dumps(state))
 monkeypatch.setattr(inc,'verify_native_prefix',lambda path:dict(original_run=str(base),original_checks=dict(legacy_t01_1=passed)))
 records,roots,proof=inc.completed_records(run.parent,tmp_path)
 assert records['legacy_t01_1']==passed
 assert records['connected_t02_1']==passed
 assert records['connected_t05_construct']==failed
 assert roots==[run.parent,run/'prefix_evidence']
 assert proof is None


def test_invalid_prefix_is_not_adopted(tmp_path,monkeypatch):
 run=prefix(tmp_path/'new',tmp_path/'base/connected')
 def reject(path):raise ValueError('PREFIX_HASH_CHANGED')
 monkeypatch.setattr(inc,'verify_native_prefix',reject)
 with pytest.raises(ValueError,match='PREFIX_HASH_CHANGED'):inc.source_family_job(run)


@pytest.mark.parametrize('corrupt',[False,True])
def test_nested_legacy_inspection_uses_its_hash_bound_producer(tmp_path,monkeypatch,corrupt):
 family=tmp_path/'family';legacy=family/'legacy';legacy.mkdir(parents=True)
 frozen=tmp_path/'frozen';frozen.mkdir();code=frozen/'verifier.py';code.write_text('frozen verifier')
 expected=hashlib.sha256(code.read_bytes()).hexdigest()
 other=frozen/'contract.json';other.write_text('{}')
 (legacy/'PRODUCER_BINDING.json').write_text(json.dumps(dict(files={str(code):expected,str(other):hashlib.sha256(other.read_bytes()).hexdigest()})))
 (legacy/'REUSED_LEGACY_BINDING.json').write_text(json.dumps(dict(original=dict(original_run=str(tmp_path/'ancestor/legacy')))))
 run=prefix(tmp_path/'new',family/'connected');(run.parent/'STATUS.current.json').write_text(json.dumps(dict(checks={})))
 monkeypatch.setattr(inc,'verify_native_prefix',lambda path:dict(original_run=str(family/'connected'),original_checks={}))
 monkeypatch.setattr(inc,'source_family_job',lambda path:family)
 seen=[]
 def inspect(*args,**kwargs):
  seen.append(kwargs['cwd'])
  return json.dumps(dict(retained_operation_count=17,original_checks={}))
 monkeypatch.setattr(inc.subprocess,'check_output',inspect)
 if corrupt:
  code.write_text('changed verifier')
  with pytest.raises(ValueError,match='LEGACY_PRODUCER_CHANGED'):inc.completed_records(run.parent,tmp_path/'wrong')
  assert seen==[]
 else:
  inc.completed_records(run.parent,tmp_path/'wrong')
  assert seen==[frozen]
