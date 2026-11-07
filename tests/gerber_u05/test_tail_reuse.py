"""T05 reuse is conditional on unchanged geometry code and completed proofs."""
import hashlib,json
from pathlib import Path
import pytest
from src.gerber_u05.tail import verify_code,validate_stage
from src.gerber_u05 import pipeline as p


def code_pair(tmp_path):
 old=tmp_path/'old';new=tmp_path/'new'
 files={'src/geometry.py':'grow=1','src/gerber_u05/exporter.py':'export=1','contracts/policy.json':'{"gap":0.04}'}
 for root in(old,new):
  for name,body in files.items():
   file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(body)
 original={'files':{str(old/name):hashlib.sha256((old/name).read_bytes()).hexdigest()for name in files}}
 return old,new,original


def test_export_correction_can_reuse_unchanged_t05(tmp_path):
 old,new,original=code_pair(tmp_path);(new/'src/gerber_u05/exporter.py').write_text('export=2')
 assert verify_code(original,new,old)[0]['path']=='src/gerber_u05/exporter.py'


@pytest.mark.parametrize('name',['src/gerber_u05/tail.py','src/gerber_u05/qualification_tail.py'])
def test_export_driver_revision_does_not_invalidate_completed_geometry(tmp_path,name):
 old,new,original=code_pair(tmp_path)
 for root in(old,new):(root/name).write_text('driver=1')
 original['files'][str(old/name)]=hashlib.sha256((old/name).read_bytes()).hexdigest()
 (new/name).write_text('driver=2')
 assert verify_code(original,new,old)[0]['path']==name


@pytest.mark.parametrize('name',['src/geometry.py','contracts/policy.json'])
def test_geometry_or_policy_change_invalidates_t05_reuse(tmp_path,name):
 old,new,original=code_pair(tmp_path);(new/name).write_text('changed')
 with pytest.raises(ValueError,match='GEOMETRY_CODE_CHANGED'):verify_code(original,new,old)


def test_unrecognized_added_producer_is_not_a_tail_change(tmp_path):
 old,new,original=code_pair(tmp_path);(new/'src/surprise.py').write_text('changed')
 with pytest.raises(ValueError,match='UNDECLARED_PRODUCER_ADDED'):verify_code(original,new,old)


def stage(tmp_path):
 p.save(tmp_path/'t05.json',{'candidate':'geometry'});h=hashlib.sha256((tmp_path/'t05.json').read_bytes()).hexdigest()
 proof=dict(status='PASS',candidate_sha256=h,producer_binding_sha256='producer')
 state={'checks':{}}
 for pid,mode in enumerate(('construct','1','2'),10):
  p.save(tmp_path/'audits/t05'/(mode+'.json'),proof);state['checks']['connected_t05_'+mode]=dict(status='PASS',returncode=0,pid=pid)
 return state


def test_all_three_actual_native_outcomes_are_required(tmp_path):
 state=stage(tmp_path);assert len(validate_stage(tmp_path,state,'producer'))==3
 state['checks']['connected_t05_2']['returncode']=1
 with pytest.raises(ValueError,match='NATIVE_CHECK_INCOMPLETE'):validate_stage(tmp_path,state,'producer')


def test_candidate_tampering_or_same_process_evaluations_reject(tmp_path):
 state=stage(tmp_path);(tmp_path/'t05.json').write_bytes(p.canonical({'candidate':'tampered'}))
 with pytest.raises(ValueError,match='CANDIDATE_OR_PRODUCER_CHANGED'):validate_stage(tmp_path,state,'producer')
 state['checks']['connected_t05_2']['pid']=state['checks']['connected_t05_1']['pid']
 with pytest.raises(ValueError,match='EVALUATIONS_NOT_SEPARATE'):validate_stage(tmp_path,state,'producer')


def test_incomplete_job_is_rejected_before_reading_or_copying_candidate(tmp_path):
 with pytest.raises(ValueError,match='NATIVE_CHECK_INCOMPLETE'):validate_stage(tmp_path,{'checks':{}},'producer')


def test_running_code_namespace_must_match_its_seal(tmp_path,monkeypatch):
 from src.gerber_u05 import guard
 first=tmp_path/'old/producer.py';second=tmp_path/'new/producer.py'
 for path in(first,second):path.parent.mkdir(parents=True);path.write_text('same contents')
 run=tmp_path/'run';p.save(run/'source.json',{'source':'raw'})
 monkeypatch.setattr(guard,'producer_files',lambda:[first]);guard.seal(run,'fixture')
 monkeypatch.setattr(guard,'producer_files',lambda:[second])
 with pytest.raises(ValueError,match='PRODUCER_NAMESPACE_CHANGED'):guard.verify_sources(run)
