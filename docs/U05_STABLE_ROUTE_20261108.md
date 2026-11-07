# Reusable Gerber U05 route

Integrated code: `62664ee`, on `codex/u05-reproducible-batch`. It combines the
fixed-candidate T02 verifier, registered 1% shared-gap matching, the T05
adopted-floor/read-authority correction, complete-domain T05 pin verification,
export-local complete-gap checks and source-member identity for new T02
inclusive rectangles. Qualification: 799 focused tests, a complete 47-operation
inclusive-fill synthetic route from the frozen candidate, and another complete
47-operation route from the installed normal-app path. Both construction roles
exercise an accepted inclusive rectangle; actual native checks include that
fill. Every tracked snapshot file matched before this documentation overlay.

The frozen batch source is
`out/lacie_work/releases/U05_20261108_62664ee/source/`.
Its external manifest binds all 3,143 read-only source files. The release
preflight verifies source namespace and permissions, 70 immutable assets,
26 pinned runtime packages, LaCie identity/reserve and clearance consistency.
Use its README for the exact command. Activation is recorded separately in
`ACTIVATION.json`; never use an older candidate or infer activation from source
metadata. All previous release candidates remain inactive.

Primary 3020212826 finished in
`20261107T232211Z-6c0ce45c653b4edbad7e3a13e5bd1513`: 38 retained qualified
operations and nine fresh PASS operations account for all 47. Both export
proofs agree; all eight actual corruptions are rejected, the remaining-defect
audit passes, and the checked render and Gerber were delivered to the new
`3020212826_U05_040mm_20261107T234739532162Z` sibling. Native geometry difference
is zero. All 126 components, 128 source holes, 13 protected pin slots and
20 shared-gap spans / 40 boundaries pass. The actual highlighted PNG was viewed.
All 32 current raw input-file hashes match the retained intake. Failed jobs
and their frozen sources, exports and original dispositions remain unchanged.

That seed tail uses frozen strict-gap source `64bd19b`; the combined future app
adds the separately qualified 1% matching setting and fixed-candidate T02
verification. This is incremental qualification, not a fresh full-client run of
the combined app profile. No additional full 3020212826 run is authorized.
The original T01-through-T05 geometry and its proofs were reused unchanged;
only affected export preparation and native identity handling were corrected.

Current receipts are under
`out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/export_inclusive_identity_01/`:
`FINAL_DELIVERY_AUDIT_01.json`, `VISUAL_INSPECTION_01.json`,
`CURRENT_RAW_INPUT_CUSTODY_01.json`, `APP_CANDIDATE_QUALIFICATION_01.json`,
`app_integration_01/INSTALL_RECEIPT.json` and `STABLE_ROUTE_QUEUE_01.json`.
A checked patch and verified dual-source offline Git bundle preserve the exact
seed and future-app revisions. Release activation follows final documentation
and remote verification. Other raw boards then use that one frozen source,
one board at a time, with complete checks and a fresh two-file sibling delivery.

The following describes the earlier installed checkpoint and its retained
qualification. Its former deployment snapshot is inactive and must not be used
as the newly corrected release.

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
snapshot throughout the batch. The earlier installed producer snapshot was:

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

The retained request contains eleven unique targets: the primary 3020212826,
nine other raw directories and the explicitly listed historical generated
directory `3020212826_U05_040mm_20261105T083747Z`. Keep that last target in the
ledger rather than silently dropping it. It is held for source-eligibility and
scope reconciliation; do not treat an old generated file as fresh raw copper
or use it to bypass the prohibition on another full primary-board run.
Retained selection evidence identifies `a-top.art.gbr` for 3020212866 and
3020212956, and `top.art.gbr` for the other established raw targets. Selection
for 3020213110 still requires fresh native intake evidence. The old 3020212866
enclosure-discovery miss remains a finding, not authority to crop or delete
copper. Start no remaining-board jobs before release activation.

The preceding failed job was incremental: 17 retained qualified operations plus
30 required fresh operations. Its frozen `caff24a` source used strict gap
matching and the older T02 evaluations. It halted at T05 preparation and was
not modified to install the correction or future-route verifier. The later 35-plus-12 tail passed T05 but failed export preparation. The completed
38-plus-nine export tail is identified above; receipts retain each source and
qualification boundary.

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
