# Implementation consolidation — latest C02 worktree

This records and versions useful existing implementation across the repository,
not only the T03 architecture documents. The inventory binds125 Python files:
32 source modules,33 associated test modules and60 command-line tools. Two root
memo files are unrelated and excluded. Existing C03 tools are retained as inactive
history; no C03 construction is resumed. No new T03 ABI function is implemented.

## What has actually been built

| Layer | Existing implementation now retained | Scope / limitation |
|---|---|---|
| Source inventory and chain identity | `trace_endpoint_inventory`, `uniform_source_paths`, `source_junction_paths`, `trace_chain_contacts` | Native endpoint chains, source occurrence IDs, junction decomposition and contact qualification. Geometry contacts do not prove electrical intent. |
| Eligibility and coverage | `trace_growth_eligibility`, `source_bulk_components`, `filled_copper_source_role`, `crop_growth_coverage` | Exposed versus covered source strokes, explicit bulk exclusions and focused rectangle coverage. Filled-role helpers include proposed diagnostics; inventory membership alone is not successful growth. |
| Neighbor/cohort construction | `parallel_trace_relations`, `parallel_curve_relations`, `primary_parallel_cohorts` | Immediate-neighbor proposals and disjoint full-trace width cohorts. Sampled relations are not continuous parallel-route proof or automatic T03 group permission. |
| T01/T02 growth and scene contracts | `crop_stage_growth`, `joint_rectangle_growth`, `prepared_land_scene`, `crop_attachment_support` | Whole-contour growth checks, source-core preservation, finite attachment regions, bounded rectangle axes and stage-owned clearance. Historical policies remain version-specific. |
| Attachment and replay diagnostics | `crop_attachment_diagnostic`, `crop_pinned_circle_binding`, `crop_replay_comparison` | Source-specific witnesses and representation comparisons. These are not universal contact exemptions or acceptance waivers. |
| T04 uniform width construction | `uniform_trace_width`, `uniform_trace_width_v2`, `uniform_trace_nominal`, `source_offset_width` | Versioned nominal copper and conservative checking-envelope families; fixed routes and verified original widths. Historical families are retained for comparison, not merged into an unqualified universal constructor. |
| T04 bounds, search and verification | `collective_width_bounds`, `bounded_width_solver`, `trace_width_clearance`, `prepared_width_scene` | Common factors, finite deterministic search and full-source context checks. Generic solver proof scope differs from current222 two-cohort allocation; current global/coordinatewise maximum is NOT_ESTABLISHED. |
| T03 bounded routes and execution controls | `t03_route_preflight`, `t03_c2_search_executor`, `t03_c2_search_run`, `t03_c2_search_guard` | Actual historical single-chain construction and source/policy/code-locked orchestration. C2-specific width/domain/packet constraints are intentional. No automatic retargeting to current232. |
| T03 verification, storage and review | `t03_c2_source_verifier`, `t03_c2_cumulative_result` | Source partitions, contact obligations, saved geometry archive and cumulative renderer. Rendering a trusted result is not independent verification. |
| Orchestration and diagnostic tools |60 files under `tools/`, listed in `IMPLEMENTATION_INVENTORY.json` | Coverage builders, qualification/preflight/replay, source-binding probes, controlled runs, and actual geometry renderers. Tool ASTs are checked; not every tool was executed in this consolidation. Some require retained out/ fixtures and macOS sips. |

Names in the table are modules under `src/`; the inventory lists exact paths,
SHA-256 values, public/top-level symbols, imports and role classifications.
Not every helper is a production entry point or independently qualified.
The [T03 architecture map](../../crop_dynamic_tasks/t03_architecture_notes/T03_CODE_STRUCTURE.md)
and [ABI design](../../crop_dynamic_tasks/t03_architecture_notes/T03_AGENT_ABI_PROPOSAL.md)
remain the intended boundaries. Recursive bundle routing and continuous bundle
preservation are proposed extensions; existing sampled helper code does not
implement or qualify those claims.

## Latest result and run-bound source preservation

The sequence remains T01 → T03 if needed → T04 → T02 → cumulative validation.
Current C02 uses no new T03 route. Result232 cumulative SHA-256 is
`63fd6b9cfdb7ef1412f75618826034a00f3d490d87e14a6e78bd76cf4aad03e1`.
Human visual acceptance remains PASSED. Current232 has113 visible trace runs,
54 cohorts,38 at1.5×,80 interior rectangle decisions and six inclusive fills.

Some latest orchestration was deliberately versioned under ignored out/ runs,
not in generic tools. Eight exact source-text snapshots are retained in
`run_bound_snapshots/` with `RUN_BOUND_SNAPSHOT_MANIFEST.json`: T01-only setup214,
joint width allocation221, trace replay224, ordinary T02 builder226, inclusive
builder/verifier229, and context completion builder/verifier232. Their .txt
extensions mark archival source, not new runnable adapters. Do not execute them
in docs/ or assume their output directories/paths are portable. Original out/
versions and generated geometry remain unchanged. No source fixtures or raw
customer board/exports are uploaded by this commit.

## Independent audit: REVISE remains explicit

The attached receipt is preserved byte-identically under `audit/`, with archive
and final-geometry bindings verified. All19 evidence-ZIP entries pass CRC and
its embedded receipt equals the separately supplied receipt.

- Archive234 integrity independently passes19,028 entries, no extras/mismatches.
- All525 trace-source parts and113 route hashes independently reproduce.
- Independent231 replay passes all74 ordinary rectangle checks.
- Independent224 stops at exact T01 predecessor mismatch.229 and232 stop at
  ordinary T02 source-assembly mismatch. Thus45 trace checks, complete width
  scene validation, inclusive merges and final232 byte replay have not been
  independently re-established.
- Reported predecessor Hausdorff difference is1.7763568394002505e-15mm and area
  difference1.4004235254417757e-18mm². These diagnostic magnitudes do not waive
  the strict failed identity gate. Expected hashes and policies remain unchanged.

The independent verdict is **REVISE_STRICT_EXACT_REPLAY_NOT_CLOSED**. The current
request prioritizes repository implementation analysis/versioning, not a numerical
workaround. Root-cause reconciliation remains pending; no stage is newly frozen
or electrical/manufacturing acceptance inferred. Human acceptance is preserved
as the decision on the displayed version, separate from independent qualification.

## Validation and environmental recovery

All125 selected Python files parse via AST. Selected regression run includes the
33 newly retained test modules and existing v0.1 ABI tests: **306 tests and2
subtests PASS**. This is not the entire repository suite and does not qualify
all tools or the independent audit's cross-platform union reconstruction.

Initial run:281 pass/25 fail. Those failures stop at historical path-containment
guards after large frozen files had been offloaded to LaCie.19 evidence files
(176,750,739bytes) were copied back to their local out/ paths with every SHA-256
checked before replacing the symlink. LaCie copies and all evidence bytes were
unchanged. No containment guard, code pin, numerical threshold or test assertion
was weakened. The rerun then passes306 tests/2 subtests.

Tests that inspect historical pinned evidence require the corresponding local
out/ fixtures. This commit does not pretend that a fresh clone contains all
private or generated evidence. Packet234 is a separate reproducibility bundle;
ABI availability remains distinct. Logs and restore receipts are retained under
`out/crop_dynamic_tasks/repository_implementation_consolidation_20261029_237/`.
`VALIDATION_SUMMARY.json` binds the final selected-test log hash.

## Remaining engineering work

1. Reconcile independent exact-replay failures without changing expected hashes,
   policy, original source objects or using cached-output injection.
2. Re-run and independently close the interrupted checks in224/229/231/232 order.
3. Keep rejected/inherited relationships and acceptance decisions separate.
4. Only after C02 closure advance C01. C03 remains stopped.
5. Implement no proposed T03 ABI functions without a separately scoped
   implementation/qualification slice. Refactoring historical pinned modules
   requires new parity evidence, not renamed files or weakened hashes.
