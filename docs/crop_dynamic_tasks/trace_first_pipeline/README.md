# Reusable prepared-region trace-first pipeline

The accepted C01, C02 and C03 results remain frozen. This consolidation introduces a shared **prepared-region** driver for T01 → T03 → T04 → T02 → T05; it does not start a larger-region campaign or change acceptance.

## Run

```
.venv/bin/python tools/run_trace_first_pipeline.py CONFIG.json out/NEW_RUN
.venv/bin/python tools/run_trace_first_pipeline.py CONFIG.json out/NEW_REPLAY --replay
```

The second command copies hash-bound saved stages as **SAVED_STAGE_REPLAY**, never a fresh search. Outputs must be new project-local directories. The prepared C03 example and exact input inventories are under `out/crop_dynamic_tasks/trace_first_pipeline_consolidation_20261030_271/C03_PROFILE.json`. Paths are checkout-relative; the original source cache is retained locally and not in Git. An existing project archive symlink requires its exact resolved target in the input binding. No new external acquisition is performed.

## Actual reusable implementation

| Responsibility | Implementation | Current limit |
|---|---|---|
| Custody, stage order, exact predecessor, additive scenes, failure retention, freeze guards | `src/trace_first_pipeline.py` | Native prepared-region profile; no automatic owner acceptance |
| Source bank and T01/T04/T02 replacement composition | `src/trace_first_scene.py` | Native KiCad cache/manifest and supported shapes |
| CLI and explicit stage adapters | `tools/run_trace_first_pipeline.py` | Prepared scope, complete trace paths and parallel groups required |
| T01 | Existing `tools/run_c03_round_class_stage.py` callable, or exact bound T01 snapshot reuse | Supported diameter classes, round-only profile; historical C03 presentation wording retained |
| T03 | Fresh `PreparedLandScene` check against original source | No-change branch only. A growth defect stops the pipeline before T04; route replacement is not silently assumed |
| T04 | `tools/trace_first_width_stage.py` → source-offset construction, prepared scene, bounded/resumed solver | Complete uniform paths, fixed source roles and explicit groups supplied; finite evaluation budget |
| T02 | Shared callable `tools/run_c03_trace_first_rectangles.py`, injected source loader | Whole axis-aligned rectangles, source-bound ports, 1.25 per-axis cap, ≤20% missing-area inclusive fills; no-rectangle stage is explicitly not applicable |
| T05 | Shared callable `tools/run_c03_junction_stage.py`, injected source loader/cache → `src/junction_spindle_stage.py` | Filled circles/axis-aligned rectangles, qualified original contacts, bounded additive spindle |

The C03-named rectangle and junction files remain compatibility entry points; they are reused directly, not copied into another geometry implementation. Their default source binding and accepted construction behavior are retained. `tools/c03_sequence_scene.py` is now a small compatibility wrapper around the shared loader. The old frozen source snapshots are unchanged.

`tools/trace_first_width_stage.py` is extracted from run269's previously out-only runner. It removes fixed C03 paths, the hard-coded17,849 source count and compulsory old hints. Original and resumed solvers remain separate. Optional hints undergo fresh checks. A separate fixed-scale reconstruction option exists for regression qualification; it expressly does not establish a new maximum.

## Contract

Configuration schema identifier: `prepared-native-region-pipeline/1`. This is a local Python/CLI contract, **not** an Agent ABI implementation.

Required fields: exact `sequence`, supported `profile`, `t03_mode`, pinned `inputs`, all three `protected_freezes`, and positive integer `limits` for source objects, routes, groups and width evaluations. Inputs identify native source, source manifest, supported target scope, baseline, complete-route definitions, the source-eligibility disposition ledger and parallel membership. Optional inputs include existing fixed-bulk roles, warm-start hints and a fully hash-bound T01 snapshot. Replay additionally binds each stage's file inventory.

Every stage supplies before/after WKB and a result binding. The driver validates WKB, predecessor bytes and no material copper loss (1e-12mm² numerical allowance). T03 also requires an explicit fresh growth verdict and exact no-change bytes in the admitted branch. Stage adapters retain their own finite-surface, width, attachment and simultaneous-addition checks. A driver PASS alone is not a replacement for these geometry checks or source reconstruction.

Failure evidence remains in place; subsequent stages do not execute. Fresh output is required for retries. All bound inputs and all accepted freeze files are checked. Stage file hashes and execution mode are recorded. Existing original-source sub-minimum relationships do not become remediation targets merely because they are measurable.

Production preparation still has to establish source completeness, classification and boundary suitability. This driver deliberately does not invent those facts.

## Evidence

- `out/crop_dynamic_tasks/trace_first_pipeline_replay_20261030_272/PIPELINE_RECEIPT.json`: exact accepted C03 final hash through all five stages, saved-stage replay mode.
- Same run `verification/REPLAY.json`: fresh final-source reconstruction, nominal and envelope checks, T02 fills and all85 spindle patches; same-assistant review only.
- `out/crop_dynamic_tasks/trace_first_pipeline_t03_recheck_20261030_273/T03/RESULT.json`: actual fresh generic T03 no-change check.
- `out/crop_dynamic_tasks/trace_first_pipeline_adapter_validation_20261030_275/ADAPTER_PARITY.json`: fresh source-offset T04 at saved scales, fresh T02/T05 construction and accepted geometry parity (PASS). Attempt274 retained its missing-ledger failure; T04/T02 parity from that attempt was checked before fresh T05 validation in275.
- Tests: `tests/test_trace_first_pipeline.py` covers sequence, predecessor corruption, changed inputs including final-stage mutation, unknown T03 mode, false no-change verdict, frozen-manifest changes, symlink/path escape and bound-only evidence copying.

See [LARGER_REGION_READINESS.md](LARGER_REGION_READINESS.md) before selecting a larger region. No ABI suite functions, new native exporter or independent qualification were implemented here.
