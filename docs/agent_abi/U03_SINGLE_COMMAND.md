# Fresh U03: whole board or absolute crop-image path, no rendering

User authorization: 2026-11-02, commit/push the existing checkpoint and implement
the supplied U03 handoff. U03 uses the existing checkout. The preceding U02 and
cache changes were committed as `d8fcf6e` and `3239f4f`; the latter was verified
on `origin/codex/t01-c01-english-contract-abi`. U03 publication is not implicit.

## Absolute crop-image input (2026-11-03)

The user requested crop processing and clarified that `--crop` must take an
**absolute image-file path**, just as `--input-dir` takes an absolute directory.
It is not a C01/C02/C03 alias, a preset, or a saved-job selector. For example:

```sh
"/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/tools/Run_U03_Board.command" \
  --input-dir "/Users/geoffcheng/Projects/client/PCB/szu_comm/manual-test-3020301113B/ORG" \
  --crop "/absolute/path/to/C01.png"
```

Supply the actual path to C02, C03 or another supported crop image in the same
way. Omitting `--crop` retains whole-board processing; `--whole-board` selects it
explicitly. The two flags are mutually exclusive. A relative path or `--crop C01`
is rejected. Keep the raw directory limited to its PCB/Gerber inputs; the crop
image is supplied separately.

Native intake reads exactly that image file, stages unchanged bytes on LaCie,
and binds its SHA-256 alongside the raw directory. The embedded client only
sends the two paths. No filename matching, remembered viewport, saved candidate,
or crop-name geometry enters the new pipeline.

Crop runs retain all 33 original native operations and add `pcb_crop_locate` and
`pcb_crop_verify` before T01: **35 operations and 35 separate machine audits**
for Terminal, or 35 distinct agent observations for Local Code. Whole-board runs
retain 33. Both new gates use the existing PCB data ABI's full-source circle
constellation, native-mask refinement, edge-error policy, landmark witnesses,
and wrong-location/missing-copper/ambiguity controls. Unmatched, ambiguous or
unsupported images halt with retained evidence. Thresholds are unchanged.
Internal location masks are retained as NPY evidence; there is no candidate
render, display renderer, SVG, PDF or generated comparison image.

T01 selects complete circle growth envelopes inside the located window, inset
by its verified edge uncertainty. T03 rechecks the selected fresh T01 growth
against the complete original trace inventory. T04 selects complete native
paths and complete parallel groups whose maximum supported width envelopes fit
inside the same window. Crossing paths/groups stay unchanged; no primitive is
trimmed to the crop edge. All original F.Cu remains obstacle context, every
unselected source remains protected, and the output is still a complete-board
candidate plus actual nine-layer native Gerbers. Crop allocation is fresh and
can differ from a historical C01/C02/C03 result; this is not frozen-result replay
or whole-board modification/acceptance.

Local Code uses:

```sh
python3 tools/pcb_u03_board_operator.py start --input-dir "/absolute/raw/directory" --crop "/absolute/crop/image.png"
```

Reopen `tools/Start_T01_Native_Launcher.command` once to load the crop-image
intake capability for Local Code. Terminal owns its process lifecycle and
requires no launcher setup. Review commands stay unchanged. Image bytes, source
bindings, location/verification receipts, complete pages, checkpoints and the
chosen scope are hash-bound throughout the run and named in the final report.
All evidence stays in `out/lacie_work`; failed/stopped jobs stay unchanged.

The absolute-image extension passes a complete synthetic native Terminal run:
35 gates, 35 machine audits, unchanged outside-crop copper, actual native
nine-layer exports and all controls. The supplied image path includes spaces
and Unicode. Ten focused image/scope tests plus that native command test pass.
This is implementation qualification on a synthetic board, not a claim about
real C01/C02/C03 runtime or acceptance. Retained evidence:
`out/lacie_work/evidence/u03_crop_implementation_20261103T030418Z/IMAGE_CROP_QUALIFICATION.json`.

## Interfaces

Terminal owns the native intake, adapter and child-process lifecycle:

```sh
"/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/tools/Run_U03_Board.command" --input-dir "/Users/geoffcheng/Projects/client/PCB/szu_comm/manual-test-3020301113B/ORG"
```

Local Code ordinary-English statement (owner performs the manual app trial):

> Run fresh U03 (T01 → T03 → T04), without rendering, from /Users/geoffcheng/Projects/client/PCB/szu_comm/manual-test-3020301113B/ORG. Use the U03 operator, review every native gate, and return audited candidate KiCad/Gerber exports and evidence. Stop on failure; keep owner review pending.

The agent calls `python3 tools/pcb_u03_board_operator.py start --input-dir
"<explicit absolute raw directory>"`, then reads every REVIEW_REQUIRED result
and calls `python3 tools/pcb_u03_board_operator.py review "one distinct factual
observation"` autonomously until terminal. It sends only the directory path;
native intake discovers and reads external inputs. The existing project launcher
must be reopened once to advertise `native-u03/1`. An old launcher rejects before
input discovery. No per-directory setup, global settings or MCP.

Both entrypoints use the same 33 actual operations in
`contracts/operator/u03_board.json`: 13 source/T01 gates, seven retain-valid-paths
T03 gates, eight T04 gates, and five native serialization/export gates. Terminal
records 33 separately hash-bound machine proofs, independently re-evaluated by
the route before advancement, with zero human/agent observations. The Local Code
route records distinct agent observations and no machine-proof substitution.
These counts describe a completed run; a failure retains explicit FAIL/NOT_RUN.

## Exact stage predecessors and T04 admission

Fresh native directory qualification and complete T01 construction/reconstruction
precede T03. The unchanged U02 T03 kernel regenerates exact source ports and
checks the complete trace inventory against fresh T01. Its artifacts are named
`u02_t03` inside the separate U03 job because this is the same implementation.
Movement objectives remain unsupported and halt. U02 reference jobs/candidates
are never implicit U03 inputs.

T04 inspection accounts for every trace/arc/graphic stroke and the complete
current F.Cu scene. The host reuses `source_junction_paths` to define complete
constant-original-width native paths. Exact aliases retain all occurrences;
original width transitions and junction boundaries are explicit, and no native
primitive is trimmed. A unique mutual near-straight continuation crosses an
original branch; other edges terminate at that exact original junction. This
is geometric source-path definition, not electrical or general-router proof.

An entire path is KEEP only when other predecessor copper covers its complete
core. Partial coverage never suppresses an exposed path. Degenerate exposed
strokes and graphic-stroke width families halt with retained exact identities.
Changed T03 routes require separate qualification and are rejected by this U03
profile. All skipped contributions remain protected current-scene operands.

Immediate parallel groups use the existing `parallel_relation` parameters:
one degree, 0.25 mm shared projection and 0.5 mm transverse distance, plus an
actual finite-copper cross-section blocker check. Every admitted route belongs
to exactly one group, including proven singletons. Curves remain full-route
construction/clearance constraints; they do not invent parallel relationships.

`import_width_scene` binds all native members and protected sources. Its scene
must preserve the exact verified T03 copper within the inherited Boolean area
tolerance. The stage ABI inspects all targets through complete 100-record pages,
then plans/runs/verifies the registered source-bound native-width family.
Source, path, group, relationship and comparison inventories have complete page
checks. Genuine empty inventories have an explicit hash-bound empty record,
never a fake source row.

## Unchanged width policy and bounded execution

T04 uses `width_parameters`, `construct_source_offset_width`,
`SourceWidthStage`, and the existing `TraceWidthContract`: uniform factors
1..1.5, 1e-6 scalar bracket, 36 iterations, 0.02000 mm hard gap,
0.02010 mm construction guard, 0.02002 mm original-port buffer addition and
1e-12 comparison epsilon. No land edits, path displacement, narrowing, contour
fitting or shared-clearance changes.

The whole-board sparse solver retains the ceiling-first stable-order scalar
algorithm and fresh final-neighbor upper proofs. It records an initial factor
vector and hash-bound deltas, avoiding quadratic full-vector storage. The
incremental evaluator checks changed routes and every affected old/new finite
neighbor, carrying only unaffected passing predicates. It uses the same surface
predicate, and full final nominal/envelope checks run through the original
`PreparedWidthScene`. Focused equivalence tests compare the sparse solver and
incremental evaluator with their existing counterparts across passes, failures,
interactions and reversions. Verification reconstructs every native part from
source and rechecks every final-neighbor upper bracket. Maximum claims are
coordinate-wise model claims, never a global optimum.

Finite budgets derive from actual scene/group counts, with a four-hour native
width budget and a 12 GB attempt-output budget. Exhaustion halts and retains
failure evidence; there is no partial target selection or automatic resume.

Historical task text allowing neck-down, local contour edits or later-stage
continuation is superseded here by the executable width family and this user's
bounded U03 handoff. Historical crop/synthetic results are not whole-board
qualification.

## Native exports, controls and custody

U03 writes verified T01 copper plus T04 nominal trace copper to candidate KiCad.
Changed traces use the same filled-copper contour/file-grid representation as
T01; original source paths and nominal widths remain in the T04 records. This
does not claim net-assigned analytic KiCad track editing. Every other native
node is semantically equal. The output is reparsed and independently checked
against reconstructed nominal contours.

The pinned KiCad CLI produces fresh before/candidate nine-layer Gerber exports.
Actual source trace plot atoms are bound by native endpoints, kind, width and
tolerance-bounded finite geometry. Changed trace/circle atoms are matched to
their candidate contours; all remaining F.Cu atoms and eight other layers are
protected. Deliberate wrong-unit, missing-width and protected-native mutations
must reject. T04 additionally retains wrong-predecessor, duplicate-group,
missing-route, narrowed-scale, changed-part, false-coverage and actual
finite-copper intrusion controls. Native process argv/version/exit/stdout/stderr
are retained. Excluded companions retain byte identity and NOT_ESTABLISHED roles.

All jobs, snapshots, tests, caches, logs and evidence use `out/lacie_work`.
Terminal prepares LaCie; tests use `tools/Run_PCB_Tests.command`. No internal
fallback or state directory. Keep the `.localc` symlink and all prior evidence.
U03 has its own namespace, contract, checkpoints and receipts. Producer/policy
hash guards remain active throughout qualification. Failures stop, retain
traceback/process evidence, and leave dependent operations NOT_RUN. No retry,
substitution, resealing or acceptance promotion.

Rendering NOT_REQUESTED. Owner PENDING_USER. Independent NOT_RUN:
CHANNEL_UNAVAILABLE unless a genuine authenticated channel is available.
Electrical/manufacturing NOT_ESTABLISHED. No T02/T05 or later U execution.

## Current evidence

Implementation qualification is in progress. Focused source/ABI/export tests
and fresh ORG results are recorded under `out/lacie_work/evidence/`; no completed
whole-board U03 qualification is claimed by this document before its receipt.

The first fresh job `20261102T115504Z-deb3454730ab4fe893f6cb70414c5d25`
passed the 20 source/T01/T03 gates and machine audits, then halted at
`t04_inspect`: the native junction helper's tuple pairs were rejected by the
strict plain-JSON store. T04 execution and all exports remain NOT_RUN in that
retained job. The user subsequently authorized continuing implementation and
fresh qualification on corrected source, preserving this failed job.

U03 now converts tuple-valued native route evidence to JSON lists at its own
boundary; the shared strict artifact validator is unchanged. T04 inspection
also exhausts explicit-ID batches of at most 1,000 through 100-record pages,
then validates and binds their complete union for host planning. The wire ABI's
limits remain unchanged. Native rejection tracebacks are retained on stderr.

Continuation regression: 207 tests pass, including native rejection stderr and
the actual bounded ABI over 2,371 targets. A separately copied retained prefix
passes all 15,858-source T04 inspection/admission checks and plans all 3,123
routes in 2,931 groups through 32 pages in four bounded request batches.
This is a regression against retained evidence, not a fresh U03 completion.
Evidence: `out/lacie_work/evidence/u03_continuation_20261102T122006Z/`.

All 10,640 admitted native parts also bind to actual retained source plot atoms.
Arc endpoints permit only the existing bounded file-grid rounding. For two
nearly straight source arcs the pinned exporter emits a line: U03 executes an
isolated F.Cu native Gerber plot of the exact original arc fragment and requires
exact plotting-atom equality, including aperture/attribute semantics. The
source-model/plot discrepancy is recorded explicitly. T04 still constructs the
unchanged original native arc path; no numeric width/clearance tolerance is
enlarged. Each isolated plot retains source bytes, CLI hash, argv, exit status,
stdout/stderr and output hashes. These identity probes may be created only by
the original native Gerber verification gate. Audits/controls replay and check
the retained evidence; a missing or altered probe halts without regeneration.

The subsequent ORG job `20261102T123840Z-05b2b0f7ff4247c39ead0337e6967e9f`
passed all 28 source/T01/T03/T04 gates and machine audits, including fresh
construction and verification of 2,931 groups. It halted at the first KiCad
write because the T04 checkpoint producer omitted the T03 files required by
the export validator. That job remains unchanged, with the write FAIL and its
four dependent export gates NOT_RUN. The producer now includes those files.
Export audits validate U03's accepted predecessor prefix while the current
operation's audit is pending; shared T01 custody remains byte-for-byte intact.

A real synthetic Terminal run passed all 33 gates and machine audits after
these custody fixes. A separately labelled retained-geometry regression also
passed native write/reopen, fresh nine-layer before/candidate Gerber exports,
actual reparse/protected-layer checks and all three export controls for 6,897
changed native parts. Neither result closes the failed ORG job or constitutes
a fresh complete ORG qualification. Evidence:
`out/lacie_work/evidence/u03_custody_correction_20261102T170630Z/`.

The user subsequently prioritized runtime reduction. Profiling attributed
244 of 275 sampled trial seconds to polygon unions. U03 now tests a bounded
512 MiB weighted cache of unchanged original-source unions, with lossless
compression for large default-precision geometries and admission focused on
moving traces. The incremental path can reuse the existing 1.5-width family's
complete source-visibility window when it contains the actual candidate.
Extra original operands outside the candidate AABB are disjoint from that
candidate; no original operand is omitted. The full nominal/envelope verifier
retains its original query, and near the existing clearance comparison boundary
the incremental path re-executes that original query without changing epsilon.
Measurements retain their actual values: tiny gap roundoff is reported, never
rounded away or represented as byte-identical evidence.

Ledger validation still reads and hashes every actual report and validates
every complete scale-vector hash. Sparse canonical-byte updates and finite
numeric validation during JSON decoding avoid repeated full Python traversals;
the shared strict Python-value validator is unchanged. An actual 45,134-file
machine proof was byte-identical after this optimization, with profiled runtime
reduced from 210.6 to 64.4 seconds. These are profiled benchmark timings, not a
whole-board speed claim. Source snapshots, profiles, exact comparisons and
explicit roundoff findings live under
`out/lacie_work/evidence/u03_performance_20261102T171502Z/`. Fresh qualification
and its complete end-to-end timing remain pending.

The optimized source passes 221 focused/preservation tests, including the real
33-gate Terminal regression. All 484 pinned baseline source files are unchanged;
the visibility helper and prefix-audit changes are confined to U03. Six cold
largest-group trials measured 275.2 → 159.3 profiled seconds; four warm evaluations
within that sample measured 116.0 → 18.3 seconds. Every verdict, geometry hash,
source identity and non-gap field matches; gap roundoff up to 5.2e-14 mm is
explicitly retained within the unchanged 1e-12 comparison epsilon. These bounded
results still require a fresh ORG run for complete qualification and timing.


## Real C03 locator correction — 2026-11-03

The retained run `20261103T033843Z-801e30d727864797993bc3e3dd51afa4`
passed three input/source gates and failed `pcb_crop_locate`; its remaining 31
operations remain NOT_RUN. No native job is resumed or promoted by this fix.

The original hypothesis generator let bulk-copper peaks determine a global
minimum radius. C03's 994 image peaks were reduced to eight large non-pad
features, discarding its smaller round-pad constellation. U03 now forms image
hypotheses from round-boundary witnesses. The shared PCB-data ROI implementation
and its numerical acceptance thresholds remain unchanged.

Source circle features also need an observable image landmark. A source circle strictly inside other native copper has no separate silhouette; one at/below the existing four-pixel
peak floor cannot supply a detectable standalone peak. U03 retains an explicit
full source-circle census. Every such image-only disposition requires exact strict-interior original-copper coverage (no shared boundary) or source-derived pixel-resolution evidence; partially covered, boundary-touching, coincident-outline and other resolvable circles remain required. No copper source is
removed from the native mask, T01 selection inventory or clearance geometry.
The six-landmark minimum, 80 percent match rate and .020 mm landmark tolerance
are unchanged. Audits reconstruct every census entry and match; changing an
entry to invent a coverage exception is rejected even with a changed metadata
hash. The full witness is hash-bound through selection and export checkpoints.

A separately labelled retained-input regression locates the actual C03 image at
IoU 0.9842884677, with zero outside-band pixels, then matches 146/157 required
observable landmarks and passes all three location controls and both local
machine checks. This is a location regression using retained verified source,
not a fresh completed C03 U03 pipeline or owner acceptance. Evidence:
`out/lacie_work/evidence/u03_c03_location_audit_20261103T034545Z/`.
