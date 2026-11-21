# Live T04 viewer connection

Start with the [viewer route-selection agent ABI](agent_abi/VIEWER_ROUTE_SELECTION.md)
for the consolidated identities, optional payload fields, component boundaries,
commands and qualification limits. This connection displays saved engineering
results; it does not run T04.

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

### Growth over the original source

Selection explanations can include `--comparison <comparison.json>` generated
with `src.viewer_abi.explanation.growth_comparison`. The producer takes the
hash-bound original WKB and retained candidate WKB, checks that the candidate's
display derivative exactly matches the selected path, and computes actual
candidate-minus-original and original-minus-candidate areas. The difference is
not simplified, so narrow growth bands and joint fragments remain represented.
This does not execute growth or alter engineering geometry.

The inspector offers **Growth over source** and **Fit selection**. Blue is the
original copper, green is added copper and pink is removed copper (when present).
Other artwork is dimmed during comparison. The separate **Show changes** control
still compares consecutive viewer snapshots. Explanation text appears above
collapsed source metadata. Comparisons disappear on selection/revision changes;
all overlay paths ignore pointer events so source picking remains unchanged.

An optional `comparison` in the checksummed explanation payload carries its
schema, original/added/removed polygon paths and bounds, source/candidate WKB
hashes, selected-path hash, area facts, display error, summary and snapshot note.
The native reader validates these bindings and its data-only polygon grammar.
Explanation payloads are limited to 1 MiB (envelopes 2 MiB). A linear contour
scanner preserves finite-coordinate, closed-contour, source and bounds checks
without the regular-expression engine's limit on detailed real joint contours.

The demonstration for source occurrence 16545 (bytes 496852–496864) is retained
under `out/lacie_work/viewer/growth_overlay_20261121/`. The original width is
50.038 µm; the recorded straight-group width is 75.057 µm. Its exact retained
candidate adds 0.1269736567 mm² and removes zero source copper. The displayed
snapshot remains the earlier `64 matching` revision; this object's WKB is
byte-identical to the later `t04_consolidation_20261121/qualification03/64`
artifact. The pinned benchmark feed has not been rebound to that consolidation.
An explanation's freshness note distinguishes object equality from snapshot
currency; it does not mark the entire viewer as the latest engineering result.

### Automatic comparisons for arbitrary selected traces

In a connected T04 session, clicking an object now launches the local
`tools/viewer_trace.py` reader automatically. No chat turn, model call or
manual per-trace preparation is needed for its source-growth overlay. The
native app freezes each request under `session/trace-requests/`, serializes
readers and keeps only the newest pending selection. Responses are validated
and displayed only for their matching object/revision. This reader executes no
T04 constructor, modifies no geometry and needs no additional daemon or MCP.

The reader resolves exact WKB from the committed viewer state, checks the
fingerprint, follows sealed construction or patch lineage, and compares it
with the source occurrence's hash-bound `original_ref`. Current and Previous
use their own bodies. A construction's omitted sources remain that slice's
T03 context; no full-board or newer result is silently substituted. Missing
source records, corruption, derivative mismatch and resource limits produce
explicit unavailability. Stored straight-group widths, side allocations,
route identities, arc groups and residual records are reported when present.
These are retained geometry facts, not a new AI diagnosis or clearance proof.

A later T04 chat answer can add reasoning while keeping the automatic overlay.
An automatic response cannot overwrite an existing chat explanation. Keep
using the coding chat for questions about treatment rationale and remaining
engineering issues.

The all-source comparison audit under
`out/lacie_work/viewer/all_trace_growth_20261121/` verifies all 700 retained
bodies in the current bounded slice: 356 Line and 344 Arc occurrences.
`COVERAGE.json` retains the initial two mixed-dimensional difference failures
and five earlier path-budget limits; `COVERAGE_02.json` records 700 comparisons
ready after the corrections. Area overlays retain exact polygonal differences
without simplification; zero-area boundary lines from GEOS difference results
have no fill and are omitted. Path budgets now share the 1 MiB payload ceiling.
The source and candidate WKB remain untouched. This coverage is for the loaded
bounded snapshot, not every T04 result or a completed full-board qualification.


### Maintained routes and dotted original segments

Route is now the default selection mode. Clicking a trace resolves its maintained
native route, draws the assembled current copper as one filled presentation, and
shows each original segment/arc as a dotted centerline. These lines come directly
from source `route_points_mm`; they are not polygon boundaries or skeletonized
copper. The clicked segment is yellow; other original centerlines are blue.
Straight and arc catalogue references remain separate labels and inspector IDs.
A route is not a parallel group and neither identity establishes a net.

The segment picker retains every member. Segment mode restores the existing
source-growth overlay and source-level inspection; numerical area/growth text
still concerns the clicked source, not an inferred route-wide width. Fit selection
fits the complete route in Route mode and the clicked source in Segment mode.
Original centerlines and group references have independent visibility toggles.

The viewer uses the existing source-role preparation to register a compact,
source/scene-bound membership artifact once:

```sh
.venv/bin/python -B tools/viewer_trace.py \
  --workspace "$PWD/out/lacie_work/viewer/t04_live/session" \
  --catalogue-preparation "/absolute/LaCie/path/to/existing/source_roles"
```

This reads and checks the recorded BINDING/admission/roles hashes. It does not
rerun classification, route search, growth or T04. Bulk-role sources are excluded
using recorded roles, exactly as the native route projection defines. The active
connection registers 1,524 trace routes and 4,524 source members. It avoids
expanding the large whole-board construction merely to discover membership.

A compact picking index is bound to revision, catalogue and the complete ordered
viewer object table. Trace members take priority over covering context on the
active layer; repeated clicks still cycle overlaps. Full route presentation is
built from all current source bodies, including covered context and hash-bound
patch lineage. Original member order is retained. No snapping, trimming, repair
or geometry editing occurs. One selection request shares construction decoding;
repeated members reuse a checksummed per-revision route display cache.

The optional route/index fields use existing explanation transport and the
[route selection descriptor](../contracts/viewer/route_selection_v1.json).
Native validation binds every member to the displayed path, validates the filled
area and finite open centerlines, and rejects stale/foreign/duplicate membership.
The outbox keeps its exact clicked `object` plus `selectionMode` and validated
route ID, membership and binding references. Feedback rejects forged route data.
No geometry snapshot or manifest is rewritten to attach this presentation.

Missing catalogues/centerlines, missing displayed members or oversized complete
routes retain Segment mode support with an explicit reason; no member or point
is silently omitted. Old explanation payloads and standalone Gerber imports
remain source-based. All caches and UI evidence stay under LaCie. This feature
changes selection/presentation only; it grants no T04 execution or acceptance.

Route UI qualification, screenshots, controls and unchanged-geometry receipts:
`out/lacie_work/viewer/route_selection_20261121/`.
