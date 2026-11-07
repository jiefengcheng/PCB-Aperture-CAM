import json,sys
from pathlib import Path
import pytest
from src.gerber_u05 import guard,source_assembly,workspace

def test_sealed_job_local_assembly_is_allowed_but_other_jobs_are_not(tmp_path,monkeypatch):
 work=tmp_path;job=work/'evidence/customer';run=job/'connected';run.mkdir(parents=True);assembly=job/'assembly';assembly.mkdir();bound=run/'SOURCE_ASSEMBLY_BINDING.json';bound.write_text('{}');(run/'PRODUCER_BINDING.json').write_text(json.dumps(dict(job_inputs={str(bound):guard.sha(bound)})))
 hooks=[];monkeypatch.setattr(workspace,'configure',lambda:work);monkeypatch.setattr(sys,'addaudithook',hooks.append);monkeypatch.setattr(source_assembly,'verify_run',lambda current:dict(assembly_run=str(assembly)))
 guard.install_read_fence(run)
 assert len(hooks)==1
 hooks[0]('open',(str(assembly/'original.gbr'),))
 for target in [job/'unsealed-sibling/result.gbr',work/'evidence/other/assembly/original.gbr']:
  with pytest.raises(PermissionError,match='HISTORICAL_EVIDENCE_READ_FORBIDDEN'):hooks[0]('open',(str(target),))

def test_changed_assembly_binding_cannot_grant_read_authority(tmp_path,monkeypatch):
 run=tmp_path/'job/connected';run.mkdir(parents=True);bound=run/'SOURCE_ASSEMBLY_BINDING.json';bound.write_text('{}');(run/'PRODUCER_BINDING.json').write_text(json.dumps(dict(job_inputs={str(bound):'0'*64})));monkeypatch.setattr(workspace,'configure',lambda:tmp_path)
 with pytest.raises(ValueError,match='SOURCE_ASSEMBLY_READ_AUTHORITY_CHANGED'):guard.install_read_fence(run)

def test_assembly_authority_must_be_the_same_job(tmp_path):
 run=tmp_path/'job/connected';run.mkdir(parents=True);(run/'SOURCE_ASSEMBLY_BINDING.json').write_text(json.dumps(dict(assembly_run=str(tmp_path/'other/assembly'))))
 with pytest.raises(ValueError,match='ASSEMBLY_JOB_LOCAL_AUTHORITY_REQUIRED'):source_assembly.verify_run(run)

def test_app_root_enclosing_evidence_does_not_grant_historical_access(tmp_path,monkeypatch):
 run=tmp_path/'evidence/this-job';run.mkdir(parents=True);hooks=[]
 monkeypatch.setattr(guard,'ROOT',tmp_path);monkeypatch.setattr(workspace,'configure',lambda:tmp_path);monkeypatch.setattr(sys,'addaudithook',hooks.append)
 guard.install_read_fence(run)
 hooks[0]('open',(str(run/'working.gbr'),))
 with pytest.raises(PermissionError,match='HISTORICAL_EVIDENCE_READ_FORBIDDEN'):
  hooks[0]('open',(str(tmp_path/'evidence/other-job/top.art.gbr'),))

@pytest.mark.parametrize('mutation',[None,'binding','source','symlink','role'])
def test_only_hash_sealed_same_job_legacy_reference_is_readable(tmp_path,monkeypatch,mutation):
 work=tmp_path;job=work/'evidence/fresh';run=job/'connected';run.mkdir(parents=True);legacy=job/'legacy';legacy.mkdir();source=dict(source_ref=dict(artifact_id='gerber-source:'+'a'*64,sha256='a'*64));reference=run/'REFERENCE_BINDING.json'
 reference.write_text(json.dumps(dict(schema='job-local-generated-reservation/1',source_only=True,source_sha256='a'*64)))
 (run/'source.json').write_text(json.dumps(source));(legacy/'source.json').write_text(json.dumps(source));(run/'PRODUCER_BINDING.json').write_text(json.dumps(dict(job_inputs={str(reference):guard.sha(reference)})))
 hooks=[];monkeypatch.setattr(workspace,'configure',lambda:work);monkeypatch.setattr(sys,'addaudithook',hooks.append);monkeypatch.setattr(guard,'verify_sources',lambda role:dict(profile='wrong'if mutation=='role'else'fresh-legacy-reservation-reference/1'))
 if mutation=='binding':reference.write_text('{}')
 if mutation=='source':(legacy/'source.json').write_text(json.dumps(dict(source_ref=dict(source['source_ref'],sha256='b'*64))))
 if mutation=='symlink':
  (legacy/'source.json').unlink();legacy.rmdir();outside=work/'evidence/other/legacy';outside.mkdir(parents=True);legacy.symlink_to(outside,target_is_directory=True)
 if mutation is not None:
  with pytest.raises(ValueError,match='LOCAL_REFERENCE'):guard.install_read_fence(run)
  assert not hooks
 else:
  guard.install_read_fence(run);assert len(hooks)==1;hooks[0]('open',(str(legacy/'RAW_WIDTH_CHECKPOINT.json'),))
  for forbidden in [job/'unsealed-sibling/result.json',work/'evidence/other/legacy/RAW_WIDTH_CHECKPOINT.json']:
   with pytest.raises(PermissionError,match='HISTORICAL_EVIDENCE_READ_FORBIDDEN'):hooks[0]('open',(str(forbidden),))
