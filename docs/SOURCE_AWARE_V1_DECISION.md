# Source-aware technical profile v1 decision — 2026-10-15

**Source-aware technical profile v1: PASS. Original aggregate V1.5: NOT_ESTABLISHED, unchanged.**

User authorization: the bounded instruction in the supplied 2026-10-15 pasted request explicitly authorizes this separate profile if the pinned assets lack electrical intent. This does not revise the original contract. Baseline remains `c0f997ca5cdf25734bdc8dfeb4f27a8dbcde6795`.

## Evidence and branch decision

The exact selected archive member hash remains `af31c93973b169e072e45a0596b612c264f7b8e35a84a25c35261b125e8f013d`, from GlowStitch commit `1c5d867ece6a5c38ac5ad7067cac352a5734655a`. Direct native-source recheck yields 80 pads, all unknown assignments, with only native `(net 0 "")`. The pinned inventory and existing qualification contain no matching schematic/netlist or authoritative terminal map. This is absent electrical-intent data, not a hidden mapping task, conflicting revision or export identity mismatch. No additional search/acquisition was performed.

Legacy footprint timestamps repeat across the panel: the 80 pads have only 32 distinct legacy `source_id` strings. A revision-bound terminal identity must combine source board hash, legacy ID, pin, layer and exact nominal coordinates. All 80 composite identities are distinct and the retained export's source-terminal records match the native source. Repeated timestamps or pad numbers alone are insufficient. This clarification does not rewrite frozen receipts or qualify unknown nets.

## Separate required profile

Explicit machine manifest: [source_aware_v1.json](../contracts/source_aware_v1.json). SHA-256: `623d2e81c505c0cfa2787bfde81677410b1cded3e9a3479f98d929f3c17a8873`. Generic evaluator: `src/source_aware.py`; execution: `.venv/bin/python tools/source_aware_run.py`.

| Required responsibility | Actual result |
|---|---|
| Frozen synthetic V1 (computed P1=20.05 mm), FC1 and previous 31 tests | PASS |
| Both public boards, all nine declared layer replay/historical preservation checks | PASS |
| Native anchors, nominal exposure and physical source continuity | PASS |
| Existing six fault controls per board and raw FC1 agreement | PASS; five interpreted faults plus one refusal per board |
| HALPI2 existing source-justified same-layer electrical scope | PASS |
| GlowStitch unknown-intent electrical refusal | PASS; electrical acceptance remains NOT_ESTABLISHED |
| Six new profile controls | PASS; missing/blank/partial intent cannot produce electrical PASS, false electrical claims rejected, missing geometry checks and duplicate identities rejected, fixture rename preserves policy |
| Prior local evidence integrity | PASS: all 918 pre-task files unchanged, including the original 289 |
| Original bound run output/source/reference hashes | PASS; 106 output bindings verified |
| Cursor | NOT_RUN: CHANNEL_UNAVAILABLE |
| Manufacturing | NOT_ESTABLISHED |

All **37 tests pass**, including the prior 31 unchanged tests. Evidence: `out/source_aware_v1/run_20261014T161839_497721Z/result.json` and `regressions.log`. The first local profile test attempt incorrectly assumed legacy source IDs were unique; its failed regression log is retained at `out/source_aware_v1/regressions.log`. The correction uses the composite identity and does not alter baseline geometry or reference data.

This is an actual evaluation of retained, hash-verified native export evidence, not a fresh export claim. No parser/compositor, numeric tolerance, original matrix or original final report changed. Existing geometry and fault results are consumed with their complete output/source bindings; regression tests ran again. The profile's conditional refusal policy is evaluated from source assignment availability, not a hard-coded successful fixture name.

## Deferred original obligation and stop

Deferred original R-INTENT: qualified GlowStitch electrical connectivity and separation for all 80 pads. To discharge it, supply a schematic/netlist, genuine native-source named-net assignments, or authoritative terminal map bound to the exact board revision and composite terminal identities. Each pad must have a qualified assignment or documented no-connect; unknowns cannot mean a shared net or isolation. Candidate copper components, appearance and pcb_Z grouping cannot supply this truth. Any later map must be checked for missing, duplicate, ambiguous, conflicting or wrong-revision records before electrical acceptance.

The unchanged original decision is [V1_5_COMPLETION_DECISION.md](V1_5_COMPLETION_DECISION.md), with final report SHA-256 `55a2d402af1b75b27e0aac6831e4f04203ced5f021bbead2853a24e4faf5af71`. The new PASS establishes only the listed fixture responsibilities. It does not establish full GlowStitch electrical correctness, whole-board/multilayer HALPI2 correctness, independent review or factory approval. Original process/clearance and cross-layer unknowns remain unknown.

Bounded task complete; stop here. No pcb_Z access, V2/V3, other research lanes, remote publication, relay or global changes.
