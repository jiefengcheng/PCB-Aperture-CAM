import json
from pathlib import Path

import pytest

from tools.t01_operator_progress_guard import assess, inspect_artifact

POLICY = json.loads((Path(__file__).parents[1] / 'contracts/t01/operator_progress_policy.json').read_text())


def classify(**changes):
    values = dict(elapsed_seconds=0, ui_phase='thinking', context_tokens=12000,
                  attempt=1, tool_kind='none', artifact_complete=False,
                  readback_confirmed=False, task_kind='request_authoring', policy=POLICY)
    values.update(changes)
    return assess(**values)


@pytest.mark.parametrize('elapsed,expected', [
    (89, 'CONTINUE_BOUNDED'),
    (90, 'CHECKPOINT_DUE_NO_COMPLETE_READBACK_ARTIFACT'),
    (179, 'CHECKPOINT_DUE_NO_COMPLETE_READBACK_ARTIFACT'),
    (180, 'STOP_CHECKPOINT_RETRY_ONCE_WITH_SMALLER_TASK'),
])
def test_deliverable_deadlines_not_token_activity(elapsed, expected):
    assert classify(elapsed_seconds=elapsed) == expected


def test_writing_grace_is_bounded_and_second_failure_stops():
    assert classify(elapsed_seconds=239, ui_phase='writing').startswith('CHECKPOINT_DUE')
    assert classify(elapsed_seconds=240, ui_phase='writing').startswith('STOP_CHECKPOINT')
    assert classify(elapsed_seconds=180, attempt=2) == 'STOP_OPERATOR_NOT_QUALIFIED'
    assert classify(attempt=3) == 'STOP_OPERATOR_NOT_QUALIFIED'


def test_scope_failure_wins_even_with_completed_artifact():
    assert classify(tool_kind='shell', artifact_complete=True, readback_confirmed=True) == 'STOP_SCOPE_FAILURE'


def test_ready_requires_readback_but_never_approves_semantics():
    assert classify(artifact_complete=True) == 'CONTINUE_BOUNDED'
    assert classify(artifact_complete=True, readback_confirmed=True) == 'ARTIFACT_READY_FOR_COORDINATOR_REVIEW'
    assert classify(elapsed_seconds=300, artifact_complete=True,
                    readback_confirmed=True).startswith('STOP_CHECKPOINT')


def test_fresh_context_and_compaction_boundaries():
    assert classify(elapsed_seconds=0.125, context_tokens=32769, before_start=True) == 'FRESH_CHAT_BEFORE_START'
    assert classify(elapsed_seconds=0.125, before_start=True) == 'READY_FOR_BOUNDED_DISPATCH'
    assert classify(before_start=True, artifact_exists=True) == 'PRESERVE_EXISTING_ARTIFACT_CHOOSE_FRESH_PATH'
    assert classify(ui_phase='compacting', elapsed_seconds=1) == 'STOP_COMPACTION_USE_FRESH_PACKET'


def test_artifact_scope_partial_json_and_complete_json(tmp_path):
    p = tmp_path / 'out/request.json'
    assert not inspect_artifact(p, tmp_path)['complete_json']
    p.parent.mkdir()
    p.write_text('{"operation":')
    assert not inspect_artifact(p, tmp_path)['complete_json']
    p.write_text('{"operation":"example"}')
    assert inspect_artifact(p, tmp_path)['complete_json']
    assert not inspect_artifact(p, tmp_path, since_epoch=p.stat().st_mtime + 1)['fresh_for_attempt']
    with pytest.raises(ValueError, match='checkout/out'):
        inspect_artifact(tmp_path / 'other.json', tmp_path)


def test_invalid_observations_rejected():
    with pytest.raises(ValueError):
        classify(elapsed_seconds=-1)
    with pytest.raises(ValueError):
        classify(ui_phase='made_up')
    with pytest.raises(ValueError, match='native ABI execution'):
        classify(task_kind='native_execution')
