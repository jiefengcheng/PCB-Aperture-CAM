# V2 MovePadWithConnections — bounded execution decision, 2026-10-15

**Technical result: PASS for one automatic synthetic-coupon transformation.** This demonstrates original + fixed modification contract → computed native candidate → actual KiCad export → independent Gerber acceptance. It is not whole-board routing, HALPI2 modification, AI planning or manufacturing approval.

## Authorization and V1.5 closure

The user explicitly granted standing authorization for the proposed bounded V2 slice and limited read-only pcb_Z discovery integration. Routine steps inside that scope require no repeated approval. Prior stop clauses and checkout isolation are superseded only for this slice and read-only access to the specified `pcb_Z` package. No authority for V3, HALPI2 automatic editing, full legacy merger, other lanes or remote publication follows.

V1.5 engineering investigation is closed as bounded qualification at `a5c5af7`. Its original aggregate and GlowStitch electrical obligation remain NOT_ESTABLISHED. Source-aware profile PASS at `2e004b1` and HALPI2 bounded electrical case PASS at `a5c5af7` remain separate. No earlier decision is relabelled.

## Operation contract and computation

[contracts/v2_move_pad.json](../contracts/v2_move_pad.json) pins the before board, frozen policy, independent synthetic intent, permitted target/dependents, fixed anchor and exact pcb_Z source hashes. Contract SHA-256: `57000f4cd9c6270bd4e39c0d52a0672af682122a3de1f5b70755201a158e1256`. The executor reads the before board and policy, not the supplied candidate or a manual adjustment.

Nearest feasible center calculation intersects required opening coverage (0.10 mm overlap + 0.05 mm registration allowance) with nominal center tolerance and pad size. Both center intervals are [19.95,20.05] mm. Nearest point to the original (20.35,20.00) is (20.05,20.00); movement is 0.30 mm, within 0.50 mm. Decimal constraint arithmetic precedes native six-decimal coordinate serialization.

| Role | Native object | Action |
|---|---|---|
| Target P1 | `29787dde-407e-52c4-8d4f-89a8c02d2b68` | Move center to (20.05,20.00), keep size/net/layer |
| Dependent T1 | `e072ccf0-0384-5730-b6a3-6b138a663415` | Move vertical segment to X=20.05, retain length |
| Dependent T2 | `602c06e5-4143-54fc-928f-13447abe4cc7` | Retain 45° dogleg; new join (20.00,21.55) |
| Dependent T3 | `f95659d2-d006-5b1c-8b08-c76127fa42dc` | Update start to join; keep end (20.00,23.00) |
| Protected | P2–P4, T4/T5, all mask openings, outline, remaining native text | Byte-preserved |
| Read-only obstacles | P3/P4/T5, net N2 | Discovered; no write permission |

The physically connected N1 context also contains protected P2/T4. Membership of a connected component never grants edit permission. Exactly four native lines and coordinate fields change; everything else is preserved. The computed candidate subsequently matches the supplied generated candidate byte-for-byte, as a post-computation reference check only.

## Limited pcb_Z qualification

Authorized source: `/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/pcb_Z`. Only hash-pinned, inspected function ASTs execute: four expression ID/layer/type helpers from import_pcb.py and get_layer_items/find_connected_components from group.py. Their module initializers do not execute; no pcbnew, SQLite/import/export, log, Excel or grouping-save path is invoked.

Legacy front-layer discovery returns five tracks and omits footprint pads. The project adapter explicitly adds four pads. Legacy grouping then finds physical context through installed rtree 1.4.1 and project Shapely Item/BoardView adapters. This qualifies the reused algorithm at **zero clearance**; it does not qualify native pcbnew.GetEffectiveShape or positive-clearance search (the legacy bounding-box query is not expanded by clearance). All seven legacy Python source hashes remain unchanged. No dependencies were added/upgraded: required rtree is already frozen in requirements.lock.txt.

## Native output and independent acceptance

Authoritative run: `out/v2/run_20261014T164520_384804Z`. Final result: `result.json`, SHA-256 `0e03355d2772f5baf78ffda27be962dc290caa7f78fa63e99208d5ea9cd70d3a`. Execution receipt: `out/v2/execution_001.log`.

| Required evidence | Actual result |
|---|---|
| Fresh before + automatically generated candidate KiCad exports | PASS; pinned binary unchanged, version 10.99.0, KICAD_RUN_FROM_BUILD_DIR=1 |
| Frozen V1 Gerber evaluator, all 11 mandatory checks | PASS |
| Required aperture coverage/exposure | 1.19 → 1.40 mm²; 0.15 mm nominal required rim; uncovered expanded area 0 |
| Center and movement | Offset (0.05,0) mm; movement 0.30 mm |
| Connectivity and robust neck | N1 P1–P2 and N2 P3–P4 preserved after frozen 0.099 mm erosion; two separate components |
| Clearance / trace width | Minimum different-net spacing 1.55 mm; native widths 0.25 mm |
| Protected scope | All protected objects fixed; copper difference outside authorized region 0 mm² |
| Frozen V1.5 compositor agreement | PASS on complete F.Cu, F.Mask and Edge.Cuts images against V1 reader geometry within existing budgets |
| Replay | Computed native bytes identical; separate native plots geometrically equivalent |
| Frozen 13 Gerber controls | All expected FAIL/NOT_ESTABLISHED outcomes reproduced |
| End-to-end rejection/rollback | Five rejected attempts: broken connection, unsupported semantics, real CLI failure, staged failure, prepublication failure |
| Regressions | 48 tests PASS: prior 37 plus 11 executor/discovery/transaction controls |
| Custody | 70 assets, pinned public sources, all 927 pre-task evidence files and original frozen source/contracts unchanged |
| Cursor | NOT_RUN: CHANNEL_UNAVAILABLE; no direct authenticated tool available |
| Manufacturing | NOT_ESTABLISHED |

The V1.5 compositor is an additional preserved reader/composition path, not an independent numeric engine; both routes use GEOS. Primary acceptance remains the unchanged frozen V1 validator and independent synthetic policy/net intent. No public-board electrical claims are expanded by this coupon result.

Native DRC on both before and accepted candidate reports zero unconnected items and one Synthetic footprint-library warning, returning exit 5 under --exit-code-violations. It remains supplementary, not clean DRC or factory approval. Full native argv/stdout/stderr, board copies, Gerbers, DRC JSON, operation plans, validation reports and transaction journals are retained.

## Transaction and failure semantics

Every attempt has a new workspace. Stage the generated board, export it, check all 11 mandatory statuses, recheck candidate/source custody, then atomically rename staging/ to accepted/. No failed attempt overwrites a source or earlier accepted bundle. Failed staging is retained for diagnosis rather than discarded. Atomic publication is a directory rename; power-loss durability/full crash recovery is not claimed.

Broken-connectivity and unknown-semantic controls deliberately mutate newly exported staging Gerber copies before validation; their native export receipts describe the pre-corruption bytes and final result hashes bind the actual corrupted bytes. Native corruption is never accepted. Unit controls also reject changed protected pads, source/policy/legacy-hash mismatch, wrong targets/dependencies, ambiguous identities, infeasible constraints, exceeded movement, incomplete PASS reports, write/export/prepublication failures, postvalidation tampering, replay workspace collision and reapplication to a different source revision. Mocked unit callback results are transaction tests only; native acceptance evidence comes from the end-to-end run.

Successful staging bundles are renamed to accepted/. Exact execution-time argv/log paths retain the historical staging prefix; export receipts supply log_relative_to_bundle and result.json records relocation. Accepted bundle paths are the retained artifacts, not the old execution paths.

## Reproduction and completion

```sh
.venv/bin/python tools/v2_run.py
```

Use this checkout's pinned dependencies, retained evidence and exact read-only pcb_Z sources. The command creates a new timestamped run, never overwrites historical receipts or out/current_native.txt, and returns nonzero on any required failure. V1/V1.5 parsers, contracts, tests and tolerance budgets were not modified. Output includes raw result, replay, faults, regression log, hashes and exact commands.

This bounded V2 slice is complete. HALPI2 remains a regression/context asset; no automatic public-board edit was made. No general parser work, full pcb_Z merger/SQLite redesign, V3, remote publication, unrelated lane or global configuration change occurred. Standing authorization is retained for routine work within this approved slice; this completed result grants no broader capability or manufacturing claim.
