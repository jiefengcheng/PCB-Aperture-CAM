import json
from pathlib import Path
import pytest
from src.gerber_u05 import guard,prefix


def fixture(tmp_path,monkeypatch):
 run=tmp_path/'job/connected';legacy=run.parent/'legacy';run.mkdir(parents=True);legacy.mkdir()
 source=dict(source_ref=dict(artifact_id='gerber-source:'+'a'*64,sha256='a'*64))
 for folder in (run,legacy):(folder/'source.json').write_text(json.dumps(source))
 (legacy/'SCOPE.json').write_text(json.dumps(dict(role='HASH_BOUND_CHECKING_ENVELOPE_INPUTS_ONLY',original_run='/retained/job/legacy',native_job_resumed=False)))
 (legacy/'RAW_WIDTH_CHECKPOINT.json').write_text('{}')
 path=run/'REUSED_PREFIX_BINDING.json';path.write_text('{}')
 binding=dict(original_run='/retained/job/connected',checked_legacy_files={p.name:guard.sha(p)for p in legacy.iterdir()})
 monkeypatch.setattr(prefix,'verify',lambda candidate:binding if Path(candidate)==run else None)
 seal=dict(job_inputs={str(path):guard.sha(path)})
 return run,legacy,seal,binding


def test_exact_copied_role_requires_qualified_prefix_and_source(tmp_path,monkeypatch):
 run,legacy,seal,binding=fixture(tmp_path,monkeypatch)
 assert guard.checked_legacy_reference(run,legacy,seal)


def test_nested_role_uses_verified_original_legacy_authority(tmp_path,monkeypatch):
 run,legacy,seal,binding=fixture(tmp_path,monkeypatch)
 binding['original_run']='/newer/job/connected'
 binding['legacy_authority_run']='/retained/job/legacy'
 assert guard.checked_legacy_reference(run,legacy,seal)
 binding['legacy_authority_run']='/different/job/legacy'
 with pytest.raises(ValueError,match='ROLE_CHANGED'):
  guard.checked_legacy_reference(run,legacy,seal)


def test_fresh_role_keeps_existing_full_verification_path(tmp_path):
 assert guard.checked_legacy_reference(tmp_path/'connected',tmp_path/'legacy',{})is False


@pytest.mark.parametrize('change,reason',[
 ('binding','READ_AUTHORITY'),('file','EVIDENCE_CHANGED'),('extra','NAMESPACE'),
 ('scope','ROLE_CHANGED'),('source','SOURCE_CHANGED'),('symlink','SYMLINK'),
 ('missing_authority','AUTHORITY_REQUIRED'),('missing_proof','QUALIFIED_PREFIX_REQUIRED')])
def test_changed_incremental_role_cannot_gain_read_authority(tmp_path,monkeypatch,change,reason):
 run,legacy,seal,binding=fixture(tmp_path,monkeypatch)
 if change=='binding':(run/'REUSED_PREFIX_BINDING.json').write_text('{"changed":true}')
 elif change=='file':(legacy/'RAW_WIDTH_CHECKPOINT.json').write_text('{"changed":true}')
 elif change=='extra':(legacy/'unbound.json').write_text('{}')
 elif change=='scope':
  (legacy/'SCOPE.json').write_text(json.dumps(dict(role='fresh-legacy-reservation-reference/1')))
  binding['checked_legacy_files']['SCOPE.json']=guard.sha(legacy/'SCOPE.json')
 elif change=='source':
  (legacy/'source.json').write_text(json.dumps(dict(source_ref=dict(sha256='b'*64))))
  binding['checked_legacy_files']['source.json']=guard.sha(legacy/'source.json')
 elif change=='symlink':(legacy/'foreign').symlink_to(run/'source.json')
 elif change=='missing_authority':binding['checked_legacy_files']={}
 elif change=='missing_proof':
  def fail(candidate):raise ValueError('QUALIFIED_PREFIX_REQUIRED')
  monkeypatch.setattr(prefix,'verify',fail)
 with pytest.raises(ValueError,match=reason):guard.checked_legacy_reference(run,legacy,seal)


def test_symlinked_copied_role_is_not_a_same_job_role(tmp_path,monkeypatch):
 run,legacy,seal,binding=fixture(tmp_path,monkeypatch);elsewhere=tmp_path/'other';legacy.rename(elsewhere);legacy.symlink_to(elsewhere,target_is_directory=True)
 with pytest.raises(ValueError,match='SAME_JOB'):guard.checked_legacy_reference(run,legacy,seal)
