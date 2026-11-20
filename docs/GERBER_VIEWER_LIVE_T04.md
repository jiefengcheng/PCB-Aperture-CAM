# Live T04 viewer connection

The user authorized connecting **T04 category-based pass optimization** to the viewer on 2026-11-21. The active connection is `out/lacie_work/viewer/t04_live`; `connection.json` pins the chat, client source, accepted T03 and retained initial construction. Client Gerbers, engineering artifacts and T04 implementation remain read-only to this bridge.

## Operation

Run `tools/Start_T04_Viewer_Link.command` to resume the local watcher and open the linked native viewer. The watcher is a project-local background Python process with an OS-held single-writer lock, not a global service. It polls a viewer-only queue once per second. The native viewer polls the resulting snapshot manifest every 0.7 seconds. The live queue waits for a matching native DOM-update acknowledgment before advancing to another revision, so a burst of completions does not skip intermediate slices. Reopening the launcher does not duplicate an active watcher.

The active T04 chat has received the producer contract and has begun using its status interface. At each natural completion, after both files are finalized, it seals a notification with:

```sh
.venv/bin/python -B tools/viewer_live.py \
  --connection "$PWD/out/lacie_work/viewer/t04_live" complete \
  --label "T04 slice description" \
  --report "/absolute/finalized/REPORT.json" \
  --shapes "/absolute/finalized/SHAPES.json"
```

`SHAPES.json` maps source IDs to `before_wkb_hex` and `after_wkb_hex`. The unsimplified before WKB must match the exact currently published engineering predecessor. For an independent cohort's complete stored construction, use `--construction /absolute/construction.json.gz` instead of `--shapes`. Its source, T03 digest and scene reference must match the connection. Complete construction replacements are assembled over the pinned T03 template, never compounded over an unrelated experiment.

The current benchmark also has a pinned automatic completion-feed adapter: `t04_residual_end_match_20261121/BENCHMARK_02.log`, its `qualification/` directory and the exact hash of `benchmark2.py`. That existing producer emits `CASE_DONE` only after writing the construction, running its checks/source-custody verification and finalizing `CASE.json`. The bridge matches the terminal marker to the report's arm, timing and native-connection checks, verifies its construction digest, then seals the same queue notification automatically. It does not modify the benchmark script. Partial log lines and progress records cannot publish. A rewritten log prefix or changed producer script stops this feed rather than guessing or silently rebinding it.

For this pinned benchmark, no per-arm chat command is needed. The generic `complete` hook remains available for other completed slices; duplicate notifications of the same report/geometry are idempotent. Three newly completed arms—hard baseline, hard matching and five-case baseline—were delivered and the current native DOM acknowledgment was verified during setup.

The watcher does not infer completion from a directory scan or file appearance. Explicit registration or the pinned terminal-marker adapter seals exact report/geometry hashes after producer completion. Duplicate registrations of identical artifacts are idempotent. In-progress files, wrong source or predecessor, altered seals and invalid geometry cannot become published updates. The bridge retains rejected-event receipts and the last good display; it never retries an engineering operation.

**Show changes** and **Follow latest change** start enabled in this linked launch mode. Users can turn either off. A no-change slice is explicitly labeled as such. Display status is Preview or explicitly Failed; this delivery path cannot promote a result to Verified. The report retains its own qualification and scope, including failed or incomplete findings.

## Selection feedback

Clicking an object writes `session/outbox/selection.json`. The watcher validates its job, revision, identity and object record, then updates `feedback/latest.json`. Selection is refreshed when its object remains selected across incoming revisions. Clicking empty space, switching comparison revision or removing the selected object emits an explicit clear. Old or mismatched selections are reported as stale/rejected, never silently rebound to another source.

The T04 chat reads feedback before subsequent work and after publication through:

```sh
.venv/bin/python -B tools/viewer_live.py \
  --connection "$PWD/out/lacie_work/viewer/t04_live" status
```

The viewer also returns `session/outbox/display.json` with a revision-bound DOM-update acknowledgment; `status` reports whether it matches the latest published payload. This is UI delivery evidence, not pixel-fidelity or CAM approval.

This is feedback for its next tool call, not authority to edit geometry. The local ABI does not wake an idle model turn on every click. There is no MCP or network transport in the visualization/selection data path. The initial coordination message used the app's chat coordination tool at the user's explicit request.

## Custody and recovery

All snapshots, state, queues, feedback, logs and tests remain on the prepared LaCie workspace. The watcher rechecks storage availability and the 5 GiB reserve before each iteration; missing storage stops it without an internal fallback. Reopen the launcher after restoring storage. It does not remove retained locks, failed receipts, old snapshots or source files.

A revision's exact geometry fingerprints are separately hash-bound in its manifest. Snapshot/state files are persisted before the atomic manifest commit. Restart recovery follows only the committed state lineage; orphan files do not count as published events. Watcher process state and last-tick time are retained in `watcher.json`; a heartbeat is operational evidence, not engineering approval.

The initial context is the complete retained attempt_04 T04 diagnostic, not the earlier one-trace demonstration. Actual newly completed producer artifacts may still be partial, failed or unchanged. This connection does not establish whole-board T04 completion, electrical/manufacturing acceptance, owner approval or independent review.

### Selection explanation round trip

A canvas click emits the exact source occurrence and displayed revision through
`session/outbox/selection.json`. The active T04 chat can inspect a frozen copy
and the corresponding retained evidence, then return a read-only explanation.
`tools/viewer_explain.py --workspace <session> --selection <frozen-selection.json>
--text-file <answer.txt> --author "Active T04 chat" --evidence <report-path>`
atomically publishes the response to `session/inbox/explanation.json`.

The response contains a checksummed, size-bounded payload bound to the job,
revision, object ID and source ID. The native reader rejects mismatches and the
canvas displays the answer only while that exact selection remains active.
Changing selection or revision clears the answer. This text channel writes no
snapshot, source geometry or engineering acceptance. The coding chat currently
coordinates the question and response; clicking alone does not launch inference
or send a new chat message. Apple Intelligence remains a separate provider.

The real-client demonstration is retained under
`out/lacie_work/viewer/t04_live/verification/trace_explanation/`:
source Line occurrence 771, bytes 19017–19031, displayed revision
`e026f876f6564d4d8e22a79840bea8c6`. Its answer comes from the active T04 chat,
not the viewer or an inferred electrical net.
