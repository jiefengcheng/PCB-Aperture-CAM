#!/usr/bin/env python3
"""Read-only coordinator guard for operator authoring/audit stalls; no geometry."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'contracts/t01/operator_progress_policy.json'


def assess(*, elapsed_seconds, ui_phase, context_tokens, attempt,
           tool_kind, artifact_complete, readback_confirmed, task_kind, policy,
           before_start=False, artifact_exists=False):
    """Classify coordinator observations; never mistake this for ABI approval."""
    if elapsed_seconds < 0 or context_tokens < 0 or attempt < 1:
        raise ValueError('Invalid timing, context or attempt')
    if task_kind not in {'request_authoring', 'report_audit'}:
        raise ValueError('Guard does not apply to native ABI execution')
    if ui_phase not in {'reading', 'thinking', 'writing', 'complete', 'compacting'}:
        raise ValueError('Unknown UI phase')
    if tool_kind not in policy['allowed_operator_tools']:
        return 'STOP_SCOPE_FAILURE'
    if attempt > policy['maximum_attempts']:
        return 'STOP_OPERATOR_NOT_QUALIFIED'
    if before_start:
        if artifact_exists:
            return 'PRESERVE_EXISTING_ARTIFACT_CHOOSE_FRESH_PATH'
        if context_tokens > policy['maximum_start_context_tokens']:
            return 'FRESH_CHAT_BEFORE_START'
        return 'READY_FOR_BOUNDED_DISPATCH'
    if ui_phase == 'compacting':
        return 'STOP_COMPACTION_USE_FRESH_PACKET'
    stop = policy['no_artifact_stop_seconds']
    if ui_phase == 'writing':
        stop += policy['write_grace_seconds']
    if elapsed_seconds >= stop:
        return ('STOP_OPERATOR_NOT_QUALIFIED' if attempt >= policy['maximum_attempts']
                else 'STOP_CHECKPOINT_RETRY_ONCE_WITH_SMALLER_TASK')
    if artifact_complete and readback_confirmed:
        return 'ARTIFACT_READY_FOR_COORDINATOR_REVIEW'
    if elapsed_seconds >= policy['checkpoint_seconds']:
        return 'CHECKPOINT_DUE_NO_COMPLETE_READBACK_ARTIFACT'
    return 'CONTINUE_BOUNDED'


def inspect_artifact(path, root=ROOT, since_epoch=None):
    path = path.resolve()
    if not path.is_relative_to((root / 'out').resolve()):
        raise ValueError('Expected artifact must be under this checkout/out')
    if not path.exists():
        return dict(exists=False, complete_json=False, fresh_for_attempt=False,
                    sha256=None, bytes=0)
    if not path.is_file():
        raise ValueError('Expected a file')
    blob = path.read_bytes()
    try:
        value = json.loads(blob)
        complete = isinstance(value, dict) and bool(value)
    except (ValueError, UnicodeError):
        complete = False
    return dict(exists=True, complete_json=complete,
                fresh_for_attempt=since_epoch is None or path.stat().st_mtime >= since_epoch,
                sha256=hashlib.sha256(blob).hexdigest(), bytes=len(blob))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-artifact', type=Path, required=True)
    parser.add_argument('--started-at', required=True, help='Timezone-aware ISO timestamp')
    parser.add_argument('--task-kind', choices=['request_authoring', 'report_audit'], required=True)
    parser.add_argument('--ui-phase', required=True)
    parser.add_argument('--context-tokens', type=int, required=True)
    parser.add_argument('--attempt', type=int, required=True)
    parser.add_argument('--tool-kind', required=True, help='Coordinator-observed tool, not operator self-report')
    parser.add_argument('--readback-confirmed', action='store_true')
    parser.add_argument('--before-start', action='store_true', help='Coordinator pre-dispatch check')
    args = parser.parse_args()
    start = datetime.fromisoformat(args.started_at.replace('Z', '+00:00'))
    if start.tzinfo is None:
        parser.error('started-at must include a timezone')
    now = datetime.now(timezone.utc)
    elapsed = (now - start).total_seconds()
    artifact = inspect_artifact(args.expected_artifact, since_epoch=start.timestamp())
    policy = json.loads(POLICY.read_text())
    action = assess(elapsed_seconds=elapsed, ui_phase=args.ui_phase,
                    context_tokens=args.context_tokens, attempt=args.attempt,
                    tool_kind=args.tool_kind,
                    artifact_complete=artifact['complete_json'] and artifact['fresh_for_attempt'],
                    readback_confirmed=args.readback_confirmed,
                    task_kind=args.task_kind, policy=policy,
                    before_start=args.before_start, artifact_exists=artifact['exists'])
    print(json.dumps(dict(schema='t01-operator-progress-observation/1',
                         observed_at=now.isoformat(), elapsed_seconds=elapsed,
                         action=action, artifact=artifact,
                         limitation='No request-semantic, geometry, acceptance or tool-permission verdict'),
                     indent=2))


if __name__ == '__main__':
    main()
