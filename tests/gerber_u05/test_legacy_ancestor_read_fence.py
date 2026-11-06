"""Only verified immutable ancestor source trees gain read authority."""
import json,sys
from pathlib import Path
import pytest
from src.gerber_u05 import guard,legacy_prefix,workspace

@pytest.mark.parametrize('explicit_authority',[False,True])
def test_all_verified_ancestor_source_roots_are_allowed_and_other_history_rejects(tmp_path,monkeypatch,explicit_authority):
 work=tmp_path;current=work/'evidence/current-source';first=work/'evidence/original-source';middle=work/'evidence/middle-source';job=work/'operator_routes/new';job.mkdir(parents=True);roots=[first,middle]
 for root in [current,*roots]:root.mkdir(parents=True);(root/'SOURCE_REVISION.json').write_text('{}')
 authority=dict(original_source_root=str(middle),original_source_roots=list(map(str,roots)));calls=[]
 monkeypatch.setattr(guard,'ROOT',current);monkeypatch.setattr(workspace,'configure',lambda:work);monkeypatch.setattr(sys,'addaudithook',calls.append);monkeypatch.setattr(legacy_prefix,'inspect',lambda *args:authority);monkeypatch.setattr(legacy_prefix,'verify',lambda *args:dict(original=authority))
 if not explicit_authority:
  folder=job/'legacy';folder.mkdir();bound=folder/'REUSED_LEGACY_BINDING.json';bound.write_text('{}');(folder/'PRODUCER_BINDING.json').write_text(json.dumps(dict(job_inputs={str(bound):guard.sha(bound)})))
 guard.install_read_fence(job,legacy_authority=dict(original_run='verified-unit-fixture',through='t05')if explicit_authority else None)
 assert len(calls)==1
 for root in roots:calls[0]('open',(str(root/'SOURCE_REVISION.json'),))
 unrelated=work/'evidence/unrelated-old-result/top.art.gbr'
 with pytest.raises(PermissionError,match='HISTORICAL_EVIDENCE_READ_FORBIDDEN'):calls[0]('open',(str(unrelated),))
 # A sibling directory of an allowed source is still outside that authority.
 with pytest.raises(PermissionError,match='HISTORICAL_EVIDENCE_READ_FORBIDDEN'):calls[0]('open',(str(work/'evidence/original-source-sibling/result.gbr'),))


def test_changed_sealed_ancestor_binding_cannot_grant_read_access(tmp_path,monkeypatch):
 job=tmp_path/'operator_routes/new';folder=job/'legacy';folder.mkdir(parents=True);file=folder/'REUSED_LEGACY_BINDING.json';file.write_text('{}');(folder/'PRODUCER_BINDING.json').write_text(json.dumps(dict(job_inputs={str(file):'0'*64})))
 monkeypatch.setattr(workspace,'configure',lambda:tmp_path)
 with pytest.raises(ValueError,match='LEGACY_PREFIX_READ_AUTHORITY_CHANGED'):guard.install_read_fence(job)
