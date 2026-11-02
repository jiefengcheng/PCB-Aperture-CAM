"""Bound agent output without dropping the stored per-file custody manifest."""
import json,hashlib
from tools.pcb_t01_board_operator import stdout_result
import pytest


def test_nonterminal_facts_are_not_projected_or_changed():
    result=dict(status='REVIEW_REQUIRED',facts=dict(sites=1408),files=['do not trim intermediate facts'])
    assert stdout_result(result)is result


def test_large_terminal_returns_markdown_and_bound_full_manifest(tmp_path):
    ui=tmp_path/'operator_ui';ui.mkdir();files=[dict(path='native-detail-'+str(i),sha256='a'*64)for i in range(2000)];result=dict(terminal=True,evidence=str(tmp_path),files=files,ready_markdown='Native overview and all tile links.',status='COMPLETE_AUDITED_BOARD_SEQUENCE')
    blob=json.dumps(result).encode();manifest=ui/'terminal.json';manifest.write_bytes(blob);(ui/'current.json').write_text(json.dumps(dict(status='COMPLETE',terminal=str(manifest),terminal_sha256=hashlib.sha256(blob).hexdigest())))
    view=stdout_result(result);assert len(json.dumps(view))<4000 and view['file_count']==2000 and view['ready_markdown']==result['ready_markdown']
    assert 'files'not in view and result['files']==files and json.loads(manifest.read_bytes())['files']==files
    manifest.write_bytes(blob+b' ')
    with pytest.raises(ValueError,match='CUSTODY_MANIFEST_CHANGED'):stdout_result(result)
