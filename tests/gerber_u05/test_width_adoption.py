import json
from pathlib import Path
import pytest
from src.gerber_u05 import width_adoption as a

def test_worker_change_is_limited_to_authorized_width_checkpoint_branch():
    after=(Path(a.__file__).parent/'worker.py').read_text()
    new="name=='t04'and(os.environ.get('U05_WORKER_MODE')!='construct'or(run/'REUSED_WIDTH_BINDING.json').exists())"
    before=after.replace(new,"name=='t04'and os.environ.get('U05_WORKER_MODE')!='construct'")
    before=before.replace("name=='t04'and os.environ.get('U05_WORKER_MODE')=='construct'and not(run/'REUSED_WIDTH_BINDING.json').exists()","name=='t04'and os.environ.get('U05_WORKER_MODE')=='construct'")
    a.worker_same(before,after)
    with pytest.raises(ValueError,match='UPSTREAM_WORKER_CHANGED'):a.worker_same(before,after.replace("name=='t05':p.save","name=='t03':p.save"))

def test_corrupted_copied_width_checkpoint_cannot_advance(tmp_path,monkeypatch):
    original={'original_run':'explicit-retained-run'};monkeypatch.setattr(a,'inspect',lambda path:original)
    raw=tmp_path/'RAW_WIDTH_CHECKPOINT.json';raw.write_text('original')
    (tmp_path/'REUSED_WIDTH_BINDING.json').write_text(json.dumps(dict(original=original,copied_files={raw.name:a.sha(raw)})))
    a.verify(tmp_path)
    raw.write_text('corrupt')
    with pytest.raises(ValueError,match='COPIED_EVIDENCE_CHANGED'):a.verify(tmp_path)

def test_retained_original_evidence_cannot_change_after_adoption(tmp_path,monkeypatch):
    (tmp_path/'REUSED_WIDTH_BINDING.json').write_text(json.dumps(dict(original={'original_run':'explicit-retained-run'},copied_files={})))
    monkeypatch.setattr(a,'inspect',lambda path:{'original_run':'changed'})
    with pytest.raises(ValueError,match='ORIGINAL_EVIDENCE_CHANGED'):a.verify(tmp_path)
