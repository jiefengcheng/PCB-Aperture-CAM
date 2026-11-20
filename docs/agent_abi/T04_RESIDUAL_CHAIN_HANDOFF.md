# T04 residual chains: agent handoff

## Mental model

A route is connected native trace copper. A parallel group contains nearby
parallel members, potentially from different routes. A residual chain is a
maximal connected run of untreated-by-group sources inside one route. Do not
merge these identities: `JR` is a route, `RC` is a residual treatment chain,
and straight/arc group IDs continue to come from the durable catalogue.

The straight/arc group interiors are already constructed and stay fixed.
Default growth runs as before. A residual between these treated portions may
remain narrow even when it has already grown. Chain matching gives that whole
native span another opportunity, with an independent 10% matching interval at
each registered end. The two ends need not have the same width.

First calculate how much room each side actually has; then allocate width.
Use original rails and owner dependencies to share budgets with future chains.
Plot one smooth profile along the native chain, preserve its existing grown
copper, and reuse existing checks only for residual additions. Source-file
seams do not restart profiles. Existing joint treatment sees the complete chain
at its true ends. This is not a replacement for default growth or a new router.

## Where to start

- [ABI and processing sequence](T04_RESIDUAL_CHAINS.md): Python invocation,
  module boundaries, status meanings, counter semantics and continuation rules.
- [Capability descriptor](../../contracts/agent_abi/t04_residual_chains.json):
  machine-readable opt-in fields, schemas and required evidence.
- [Earlier nominal-only reference](T04_RESIDUAL_END_MATCH.md) and
  [optional wider-end trimming](T04_WIDER_END_TRIMMING.md): distinct experiments;
  neither is interchangeable with chain matching.

The existing `group_stage.run` is the integration point. Both matching flags
must be explicitly enabled. Do not change default enablement, invoke the
full-board diagnostic entry or publish a scene as a side effect of this work.

## Retained bounded reference

Behavior reference: `out/lacie_work/t04_residual_chains_20261121/source04`.
Its `SUMMARY.json`, `BENCHMARK_04.json`, `TEST_BINDING_04.json` and `index.html`
bind the three actual-caller cohorts, source, inputs, timing and visuals.

| Cohort | Old matching stage | Chain stage | New-copper chains | Applicable routes |
|---|---:|---:|---:|---:|
| Hard | 263.28 s | 279.71 s | 53 | 41 |
| Five cases | 95.89 s | 94.98 s | 12 | 30 |
| 64 entries | 141.29 s | 143.40 s | 34 | 62 |

These are single paired observations, not statistical speedup claims. Final
source04 tests: 1,076 passed, 16 skipped. The candidate harness took 609.30 s,
including initialization, three fresh candidate stages, writes and comparisons;
its old reference arms were retained executions. The rail lookup screen lowered
the hard chain phase from 37.55 s to 13.91 s against the unscreened chain
prototype with exact copper/allocation/decision parity. This does not make the
new feature faster overall than the old matching behavior.

Native connection, reference, functional and pocket checks passed on all
applicable routes. Group bytes, covered copper and seven-pass schedule were
preserved. Frozen endpoint diagnostics still record 79/20/33 failures and
corner records remain 81/42/61 for hard/five/64. Some visible shoulders remain.
These records are neither silently accepted nor independently established
physical-clearance defects. No complete joint closure or full T04 acceptance
is claimed. Optional old final joint patches can change; the pre-joint grown
floor cannot be discarded to improve admission counts.

## Safe continuation

1. Run `tools/Prepare_LaCie_Workspace.command`. Keep derived files, test caches,
   snapshots and scratch indexes under `out/lacie_work`; never fall back internally.
2. Construct a frozen T04-only snapshot from an explicit staged allowlist.
   Verify it excludes unrelated dirty T02/T05 code and preserves asset hashes.
3. In that snapshot, run `tools/Run_PCB_Tests.command tests/gerber_u05 -q`.
   Bind the actual imported source inventory to the test receipt.
4. Run the same hard/five/64 cohorts through the bounded Python entry shown
   in the ABI guide, using the existing accepted-T03 and preparation bindings.
   Compare against source04, retaining new receipts separately.
5. Require exact copper, allocations, non-timing decision/proof fields, group
   bodies and schedule. Explicitly exclude only timing and source-binding
   metadata affected by comments/source hashes. Inspect the actual visuals.
6. Report unresolved records and full timing; clean owned temporary directories
   while retaining success/failure evidence. Stop at bounded qualification.

The current consolidation evidence is under
`out/lacie_work/t04_consolidation_20261121`. No command in this handoff grants
full-board execution, replay, export, relaxed clearance/caps or group auditing.

## Consolidation qualification — 2026-11-21

The staged T04-only candidate passed 1,079 tests with 16 skips in 22.76 s.
All 404 qualified source modules retain the source04 executable AST; changes
within them are comments, docstrings and formatting. Three existing committed
viewer modules are also present because the branch starts from current HEAD;
no dirty T02/T05 implementation was included.

| Fresh cohort | Source04 stage | Consolidated stage | Applicable route checks |
|---|---:|---:|---:|
| Hard | 279.71 s | 280.88 s | 41 |
| Five cases | 94.98 s | 103.88 s | 30 |
| 64 entries | 143.40 s | 142.18 s | 62 |

The fresh harness took 623.66 s, including 44.72 s initialization, all three
stages, writes and comparisons. Each cohort retained exact copper, allocation,
non-timing report/proof fields, group bodies, coverage, input binding, schedule
and check outcomes. Only `wall_s` and `*_wall_s` fields were excluded; no source-
binding or witness exclusion was needed in the stage comparison. These single
measurements establish behavior preservation, not a runtime improvement.

Endpoint/corner diagnostics and visible shoulders remain as above. Tests,
snapshots, canonical artifacts, fresh visual comparisons and cleanup receipts
remain in the external evidence directory. An initial snapshot storage-mapping
failure and a stopped preparation attempt are retained separately; neither was
resumed or used as successful qualification. No full-board run or replay occurred.
