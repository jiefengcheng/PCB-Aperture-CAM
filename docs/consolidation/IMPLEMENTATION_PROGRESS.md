Final bounded disposition: [CONSOLIDATION_DECISION.md](CONSOLIDATION_DECISION.md).
The entries below preserve earlier incomplete checkpoints; they are not the final state.

# Historical consolidation implementation checkpoints

This is an execution checkpoint, not the consolidation decision. The eight
acceptance outcomes in CODEX_CONSOLIDATION_HANDOFF.md remain authoritative.

Implemented source modules:

- `source_locators`: original-byte spans and occurrence identities, including
  nested objects and repeated native identifiers.
- `revision_catalog`: SHA256 payloads, revision/occurrence-scoped SQLite records,
  deferred parent foreign keys, proof occurrences, transactional publication,
  reopen validation, bounded queries and explicit selection/context semantics.
- `native_inventory`: maintained sexpdata decoding, source/layer inventory,
  nominal geometry and explicit unsupported records. No native reassembly or
  independent electrical acceptance claim.
- `spatial_context`: layer-scoped Rtree candidates, separately declared zero
  contact and distance predicates, recomputed components and typed omissions.
- `native_graph_adapter`: actual pinned gfs DB0 process reads, full identity
  sidecars, local VID/tag maps and retained proof occurrences; SHADOW_ONLY.

Recorded integration:

- `out/consolidation/pipeline_20261014T183407_799080Z`: synthetic and legacy
  inventory → spatial/exact relationships → components → persisted revisions.
  Synthetic context contains six objects, while the contract allows four writes.
- Legacy inventory retains 26,026 records / 25,840 layer instances; 23,225 objects
  have diagnostic geometry. Unsupported: 186 containers, 163 degenerate arcs,
  2,452 non-positive-width strokes. These are not electrical defects.
- `out/consolidation/shadow_20261014T183540_693318Z`: synthetic outgoing typed
  adjacency parity, nine materialized identities.
- `out/consolidation/shadow_20261014T183552_109446Z`: legacy outgoing typed
  adjacency parity, all 23,204 non-isolated materialized identities, no mismatch.
  Isolated vertices are not currently admitted to this graph materialization;
  unknown/outside materialization is distinct from complete-empty traversal.
- Two failed native compile receipts are preserved. Private headers were added
  to a supplemental pin; unneeded tensor modules requiring other lanes were
  excluded. Shared sources were not changed.

Replay projection and snapshot verification are implemented. Targeted actual
browser checks cover PLANNED → zoom for accepted/rejected records and an
unretained intermediate event. The complete browser control matrix remains
pending. Model repeat-consumer tests do not substitute for that matrix.

Custody check first detected the generator's mutable `out/visual/current.txt`
pointer. Its exact baseline bytes were restored, preserving the failure receipt.
`history_after_pointer_restore.json` confirms all 1,268 prior files match.
New consolidation pointers belong under `out/consolidation`; use the generator's
`--pointer` option to avoid modifying the frozen baseline pointer.

Still required before a final decision:

1. Integrate Processing/Cases/Storage navigation and linked selections in the
   existing workbench, using these receipts and persisted source identities.
2. Include pinned public source inventories and qualified context overlays;
   refine geometry ambiguity/coverage qualification and extraction selections.
3. Exact evidence record navigation and complete replay/control browser checks.
4. Native/reference benchmark decomposition, child memory, representative
   repeated workloads, explicit role decisions and unavailable B/R-tree gap.
5. Feed reopened catalog/context into the unchanged approved V2 execution and
   independent exported acceptance, retaining failure/rollback evidence.
6. One reproducible demonstration command, updated reuse/decision documentation,
   immutable review packet and requirement-by-requirement completion audit.

Cursor review remains NOT_RUN: CHANNEL_UNAVAILABLE. No consolidation PASS, new
repair family, public-board automatic editing, manufacturing release or V3 is
established by this checkpoint.


## Integrated workbench update

Processing / Cases / Storage & indexes now share one application. Pipeline
scene generation binds the synthetic and legacy datasets to their receipt
outputs and exact raw source bytes. Stored records, selected component geometry,
query witnesses and source excerpts are inspectable. Browser checks demonstrate
six component objects with four writable and two protected colors, navigation
back to P1's original Cases snapshot, legacy 50-row paging (521 pages), and the
explicit viewport display cap. Cases-to-storage lookup now requires source hash
plus native ID and rejects ambiguity/missing indexed revisions.

Finding pages use exact JSON pointers and link the complete original snapshot.
The HALPI2 open view says 15 expected relationships are broken before raw JSON.
The current browser-check receipt is `dashboard_browser_checks.json` under
`out/consolidation`; Python regression receipt reports 87 passing methods.
Snapshot verifier passes the generated bundle. Historical custody remains
1,268/1,268 after this update.

Remaining: indexed candidate/public source views, complete event/control and
visual layout checks, backend comparison switch/benchmark qualification,
catalog-admitted fresh V2 execution, reproducible aggregate command, and final
requirement-by-requirement decision/review packet. Existing benchmark samples
and targeted UI checks do not establish these broader acceptance outcomes.


## Catalog-admitted execution and public-index update

`tools/catalog_v2_run.py` reopens the catalog, retrieves original bytes, resolves
all four permitted native IDs uniquely, verifies the two protected neighbors
from persisted physical relations, and admits the unchanged executor. It does
not replace independent acceptance with the context index.

Authoritative current execution: `out/v2/catalog_20261014T184650_266054Z/result.json`
(PASS). Actual KiCad before/candidate exports, byte-identical candidate/replay
comparison with the prior accepted board, frozen validator acceptance, all
Gerber fault controls, explicit broken/unsupported exports and two transaction
failure phases are recorded. This establishes a fresh bounded catalog-admitted
execution, not a new operation family or manufacturing decision.

The guarded five-dataset pipeline is
`out/consolidation/pipeline_20261014T184738_272340Z`. Its source implementation
remained unchanged during execution, and its before catalog revision matches
that actual V2 admission. It includes before, produced candidate, legacy scale,
GlowStitch and HALPI2. Every supported shape or typed unsupported occurrence is
retained. Public sources remain read-only.

`out/visual/run_20261014T185021_474415Z` is the compact offline checkpoint. A
68-MiB uncompressed HTML exceeded the browser-control frame limit; gzip/base64
embedded transport reduced HTML to approximately 21 MiB. Raw scene/evidence
remain independently bound. The browser verified the decompressed checksum,
candidate P1 source mapping and HALPI2 J22.1 mapping. Snapshot verifier checks
127 outputs. Large bundles require browser DecompressionStream support; absence
is explicit unavailability. Original source CRLF/UTF-8 bytes are preserved.

Current regression receipt: 93 Python methods pass. All 1,268 baseline evidence
files remain unchanged. Per-layer native materialization/scope tests now pass;
a real synthetic F.Cu native shadow result is stored under
`out/consolidation/shadow_20261014T185034_404141Z`.

Remaining: full replay/control/visual matrix, named-group/region extraction
semantics, bounded catalog query work qualification, full benchmark decomposition,
native/reference workbench switching, reproducible aggregate command and final
reuse/decision/completion audit. The final audit must also exclude the earlier
producer with documented mid-run source-binding drift. No completion claim is
made by this update.


## Bounded query and selective extraction update

The catalog now caches fully verified immutable revisions with invalidation on
SQLite connection/data/schema generations and source file metadata. Source
mutation during verification and index-column drift are explicit errors. Cold
verification has declared manifest/payload budgets; warm SQL queries have row,
JSON-byte and VM-work bounds, cancellation and ordered paging. Public snapshots
cannot mutate the private cache.

Measured legacy identity lookup: before caching, three reads took 0.815–0.944 s;
with caching, first verification/read took 0.589 s and two warm reads took
0.063–0.088 ms, with identical answer hashes. These are one-process, one-query
measurements without OS cache flushing. They establish the identified cache
benefit, not production scaling or a native-language speed advantage. Original
receipts: `catalog_query_before_cache.json` and `catalog_query_after_cache.json`.

Named PCB_GROUP, native-ID, object, explicit-all and exact-region selections
are implemented. Overlaps deduplicate; missing/ambiguous/cyclic references
reject. Source-container dependencies are recorded separately from physical
protected context and never gain write permission. Region results distinguish
complete available-geometry search from unknown unsupported geometry. General
native reassembly remains unsupported; these are preserved-source diagnostic
bundles.

`pipeline_20261014T185959_384605Z` demonstrates real legacy named Group_55:
18 retained records, including two unavailable shapes. The workbench browser
shows COMPLETE selection with geometry NOT_ESTABLISHED and disabled edit
permissions. The synthetic context separately retains four writable objects,
two protected neighbors and one container dependency. The corresponding visual
checkpoint is `out/visual/run_20261014T190104_269467Z`.

Native failure injection now builds a new actual index, fails before manifest
publication, and proves the previous materialization remains queryable. Source
geometry approximation metadata now accounts for both centerline and buffer
curve approximation; earlier context receipts remain historical rather than
being rewritten. Generator source drift is guarded, and new test scratch stores
are project-local.

`tools/consolidation_demo.py` implements the aggregate local producer sequence
(source pipeline → catalog-admitted execution → indexed candidate → per-layer
native shadow → regression/model checks → visual bundle/verifier). Its CLI and
syntax are checked; the full aggregate command has NOT_RUN status until the
remaining benchmark/backend-display integration is finished and it is exercised.
It does not declare consolidation acceptance itself.

Still pending: full benchmark qualification and native/reference display,
complete browser matrix, aggregate-command execution, final reuse/decision and
requirement-by-requirement audit. No consolidation completion is asserted.


Latest source checks also prevent region-query callers from mutating the private
validation cache, bound aggregate selector/group traversal work, and expand via
layer spans by canonical copper-stack order rather than serialized enum order.
Targeted tests cover these cases. The current complete regression run reports
104 passing methods; final consolidation acceptance is still pending.

## Current consolidation verification continuation

The final aggregate invocation is recorded in
`out/consolidation/demo_20261014T201813_099617Z/` and its console in
`out/consolidation/final_aggregate_console.log`. At this checkpoint the source
and indexed-candidate pipelines, catalog-admitted V2 execution, six actual native
shadow scopes and 108 regression tests have completed successfully; visual and
benchmark stages are being observed through the running process, not assumed.

Browser observations from prior generated snapshots are now durably retained in
`out/consolidation/browser_recorded_matrix.json`: nine event projections with
91 control checks, 18 actual viewport resize checks and nine actual synchronized
pointer pans. These receipts explicitly name their prior-bundle scope; they do
not claim final-source coverage.

A current-source deliberate missing-execution fixture is retained under
`out/visual/missing_execution_test_20261014T202013_038161Z/`. Its browser receipt
`out/consolidation/browser_missing_execution.json` records unavailable replay,
disabled event controls and unavailable event-time metrics preserved after
zoom/overlay controls. The fixture is not a qualified engineering bundle.

The current generated workbench also verified that switching synthetic context
to HALPI2 resets physical and permission checkboxes; unavailable public-board
permissions remain disabled and unchecked. New maintained documentation:
RUN_CONSOLIDATED_DEMO.md, IMPLEMENTED_DATA_CONTRACT.md and
REUSE_AND_COMPONENT_DECISIONS.md. The supplied mandate/proposal remain intact.
Final rendered-bundle audit, consolidated decision/review packet and commit seal
remain required; this update does not close acceptance.

The aggregate run above is now terminal: all 15 stages exited 0 in 190.978 s;
108 tests passed, six native scopes report PARITY_PASS, bundle verification
passed and benchmarks report MEASURED_PARITY_PRESERVED. Both custody checks
verified all 1,268 files. Catalog-admitted V2 reports PASS, identical original/
replay/prior candidate SHA e09c7459d49ad7499c824ee2ea840189153593f2f9777207b150e602631e6ca9,
and PASS source/previous-acceptance preservation.

Current visual: `out/visual/run_20261014T202047_962408Z`, scene SHA
7b6c2858cc09d28b3a93798bc471e35dc05410d6c0c0d9942b388da2b391cb4b.
Actual browser load verifies the embedded checksum and displays final P1
20.05 mm, exposure 1.40 mm², COMMITTED/PASS. Screenshot:
`out/consolidation/current_workbench.jpg`. Observed scene load/verification/
parse 728.2 ms, parse/freeze 76.9 ms and latest board DOM construction 0.2 ms;
these are browser task measurements, not GPU paint benchmarks. Full final
control audit and seal remain pending; producer status is
RECORDED_FOR_INSPECTION, not aggregate consolidation acceptance.
