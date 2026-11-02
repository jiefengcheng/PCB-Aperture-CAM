> **Not adopted.** The user clarified that the objective is smooth end-to-end autonomous operator processing with timely progress, not coordinator watchdogs. This document records the explored direction only. See `out/crop_dynamic_tasks/t01_operator_progress_review_20261031_302/USER_DIRECTION_OVERRIDE.json`. Do not apply the following rules as active policy.

# T01 operator stall review and precautions

Applies to coordinator-supervised request authoring and metadata audits. This
changes no T01 geometry, shared ABI/clearance rule, frozen result or app setting.
Native ABI execution keeps its own existing bounds; do not apply these authoring
timeouts to a running geometry operation.

## What the evidence establishes

Session `out/crop_dynamic_tasks/t01_local_code_c01_ref_20261031_300` and preserved
attempt 299 show multiple causes, not a proved single root cause:

| Observation | Supported conclusion |
|---|---|
| Literal compile authoring stopped after 8m22s without a file | Long text transcription and broad instructions were ineffective in that attempt. |
| Long chat entered compaction for over 6 minutes without a plan request | Context processing was a separate source of delay. |
| Fresh plan request plus free-form preflight audit produced no file in 6m52s; request-only retry finished in 2m17s | Smaller tasks helped this comparison; it is observational, not a controlled causal experiment. |
| Final audit took 7m19s despite six fixed fields | Audit-schema freedom was not the sole explanation. Long generation before a completed file remained a problem. |
| Actual construction and reconstruction took 8.69s and 8.80s | The minute-scale authoring delays were not geometry execution time. |
| Operator invoked shell checks despite an explicit file-only instruction | Correct output does not establish instruction discipline or autonomous qualification. |

Token counts kept increasing during several delays. That establishes activity,
not a completed or useful deliverable. We have not isolated model inference,
decoding, runtime configuration or hardware throughput experimentally. Do not
claim those are a proved root cause or change global settings on that basis.

## Active project-local operating rules

1. One task, one output file, exact absolute paths and a closed field/template
   layout. Separate request writing from auditing the actual response. Do not ask
   an agent to design an audit schema or transcribe complete source-ID arrays.
   Supply the smallest hash-bound input projection and one operation schema.
2. Start authoring/audits in a fresh bounded chat when context exceeds 32,768
   tokens. Avoid automatic long-chat compaction for these tasks; preserve the
   existing chat and resume from immutable capsules/evidence in a new chat.
3. Record dispatch time, expected fresh artifact, attempt number and permitted
   tools before sending. Run the guard with `--before-start` before dispatch;
   it requires a fresh output path and checks context without assuming elapsed
   time is exactly zero. Poll at most every 30 seconds. At 90 seconds without a
   complete read-back artifact, demand a concrete file checkpoint or a specific
   blocker; do not add a second reporting assignment. Token activity alone is
   insufficient progress.
4. At 180 seconds without a completed/read-back artifact, stop the authoring or
   audit turn and preserve it. Allow at most 60 additional seconds for an actual
   file-write call already in flight. Never interrupt a native ABI job under
   this rule. Partial JSON, old files and file existence alone are not completion.
5. One recovery only: a fresh bounded packet and a smaller task. A second timeout
   stops this agent's qualification. Do not keep rephrasing indefinitely, repair
   its request, substitute a coordinator-authored request, or erase failures.
6. An observed tool outside the assignment allowlist immediately stops agent
   qualification, even if read-only or successful. Preserve the event and assess
   ABI behavior separately. No timing, artifact or compiler PASS overrides it.
7. A ready artifact advances only to coordinator review, never directly to ABI
   execution or acceptance. Actual response audits and source-bound verification
   remain required. Owner, independent and manufacturing gates stay distinct.

These are initial operational limits selected to prevent recurrence, not measured
optimal thresholds or an SLA. Review them using fresh attempts and timestamps;
do not loosen them merely to turn a slow attempt into a PASS.

## Read-only coordinator guard

`contracts/t01/operator_progress_policy.json` stores the limits.
`tools/t01_operator_progress_guard.py` checks coordinator-observed elapsed time,
context, tool use, artifact completeness/freshness and confirmed read-back. It
never invokes/stops an app, rewrites a request, grants authority or executes a
stage. The coordinator must act on its result through the authorized UI.

Example (use an actual dispatch timestamp and fresh path):

```sh
.venv/bin/python -B tools/t01_operator_progress_guard.py \
  --expected-artifact /ABSOLUTE/CHECKOUT/out/FRESH_SESSION/request.json \
  --started-at 2026-10-31T12:00:00+00:00 \
  --task-kind request_authoring --ui-phase thinking \
  --context-tokens 14000 --attempt 1 --tool-kind none
```

Use `--readback-confirmed` only after observing actual read-back. Record the JSON
output under the fresh session. `ARTIFACT_READY_FOR_COORDINATOR_REVIEW` means only
that a fresh nonempty JSON object and read-back were observed; it does not validate
request semantics or qualify the agent. Keep a failed attempt immutable and use
an explicit fresh path/attempt for recovery. The guard does not overwrite files.

Tool observations must come from the coordinator's actual UI/tool log, not the
operator's self-report. This guard is procedural supervision, not an app-enforced
sandbox. With the current UI channel it cannot prevent a prohibited call before
the app executes it; therefore autonomous instruction discipline remains
unqualified. No global app configuration or tool permissions are changed.
