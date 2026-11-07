# Reusable Gerber U05 route

Code checkpoint: `17a9737`, installed on `codex/u05-reproducible-batch`.
Production source matches the qualified `d450572` snapshot; subsequent changes
add tests and documentation. Other boards remain paused while the last
3020212826 job completes. This document does not declare batch qualification.

## Repeatable operation

The Gerber-only entry is `tools/Run_Gerber_U05.command`. It requires an explicit
absolute raw directory and selected artwork filename, prepares the identity-checked
LaCie workspace, and owns its native processes. No KiCad file or launcher is
required. Selection does not establish an X2 layer identity.

For subsequent boards, freeze one qualified source snapshot and use that same
snapshot throughout the batch. The currently qualified producer snapshot is:

`out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/fixed_candidate_verification_01/source_committed/`

Its manifest and integration receipts bind it to the installed app. Do not edit
the snapshot, its source revision file, registries or shared runtime while jobs
are active. Verify the manifest and runtime before starting the batch. Changes
belong to a separate snapshot with affected-case qualification, followed by an
explicit version change between jobs. The application read fence and producer
hashes reject modified active sources rather than silently changing a job.

The command shape below is documentation, not a submitted run:

```sh
"<qualified-snapshot>/tools/Run_Gerber_U05.command" \
  --input-dir "<absolute-raw-board-directory>" --gerber "top.art.gbr"
```

Use the actual selected filename for each board. Never infer it merely from
names or silently substitute another layer. Each new board gets fresh source
assembly, its own conservative reservation and connected-copper stages, fresh
checks and a new output directory. Historical generated copper is not input to
a new board. Do not launch another full run of 3020212826.

## Fixed behavior and parameters

Stages remain T01 → T03 → T04 → T02 → T05. The reservation export is an
intermediate input; only the final connected-copper export is delivered.
Construction and verification are distinct: T02 sizes once, then both workers
reconstruct the chosen candidate and freshly check it without repeating search.
The attempt ledger remains construction evidence. Other stages retain their
qualified evaluation paths; this change does not claim to eliminate every
repeated calculation or the two construction roles.

| Parameter | Current value |
| --- | --- |
| Production clearance | 0.040 mm; construction guard 0.0401 mm |
| T01 circle eligibility | At least 58% exposed circumference |
| T02 rectangle eligibility | 50% exposed perimeter, 1% relative allowance (49.5% effective) |
| Shared-neighbor gap matching | At most 1% relative difference, distinct from eligibility |
| T04 ladder | Ten deterministic source-width rungs; maximum factor 1.5 |
| T04 total width increase | At most 0.030 mm; both ceilings apply |
| Remedy budget | Existing cumulative 20% limit and smooth-rim treatment |

Each job captures applicable registries and hashes. Source cores, original
integral pad-to-trace joints, source voids, protected pin separation, retained
prior copper and accepted shared-gap corridors remain constrained. Every whole
logical fill is checked; no clipping or later remedy may bypass rejection.
Illustrative enclosure removal uses the source-assembly rule and its native
controls. Positive-only flattening is a separate unfinished slice.

## Completion and failure handling

A new full route has 47 named native operations. All must have explicit passing
dispositions, matched construction/evaluation proofs and unchanged producers.
Final export/reparse, eight actual corrupted-Gerber controls, remaining-defect
audit and rendering are mandatory. The final image must be rendered from the
same checked Gerber hash. Delivery creates one sibling directory containing
only that Gerber filename and `final_render.png`; companions are not copied.
The highlighted additions remain visible against the source.

The current last job is incremental: 17 retained qualified operations plus 30
fresh operations, not 47 newly executed operations. Its frozen `caff24a` source
uses stricter gap matching and the older T02 evaluations. It is not modified to
install the future-route verifier. A final receipt must state these differences.

A failed native job stops with evidence intact and remaining work NOT_RUN.
Engineering corrections create separate, dependency-checked affected-work jobs;
they never resume/reseal a failure or claim reused work as fresh. No additional
full 3020212826 run is authorized. If a necessary correction cannot be qualified
from retained checkpoints and final-file checks, stop and report that limitation.

## Evidence and readiness

The fixed T02 verifier has 196 passing focused checks, two exact retained
78-rectangle evaluations with optimizer calls forbidden, and two synthetic
47-operation routes. One synthetic route exercises two growing rectangles in
both construction roles. Retained evaluations took 253.426 / 258.306 seconds
with reported process peak RSS 1.60 / 1.58 GB; prior search-based evaluations
took about 26 minutes. This is a bounded checkpoint comparison, not measured
runtime for all future boards.

Batch readiness still requires the current client job's actual final export,
checks, visual inspection and delivery receipt. Unsupported source families or
new board-specific failures may still halt; no universal success or fixed
runtime is promised. The six historical broad-suite failures remain deferred
and unwaived, with no repeated broad run required for documentation updates.
Historical `.DS_Store` custody remains EXPLICIT_UNWAIVED_UNATTRIBUTED.
Owner acceptance is pending; independent review is NOT_RUN and electrical /
manufacturing acceptance is NOT_ESTABLISHED.
