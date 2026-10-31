# Full stage ABI implementation — completed local runtime

User objective: commit/push T04/T05 consolidation and designs while preserving frozen C01/C02/C03, then **fully implement all ABI suites**. All 35 version-1 suite operations are now implemented and locally verified for explicit supported input families. See [completion audit](STAGE_RUNTIME_COMPLETION_AUDIT.md), [runtime catalogue and examples](STAGE_RUNTIME.md), and [visual evidence](results/20261031/index.html). The sections below preserve the implementation checkpoints and their then-current pending work. The existing v0.1 interface remains compatible; it is not silently promoted to a qualified constructor.

The consolidation was committed/pushed as `d6a0cfb`. Frozen90+881+19,019 files and three acceptance receipts were verified unchanged before the push. Unrelated user memos remain untouched.

## Implemented foundation

- `src/stage_abi/contracts.py`: closed plain-JSON requests for35 selectors across T01–T05, including `t03_search` rather than a misleading run alias. Explicit stage strategy, references, selection/page limits, operation-scoped authorization and idempotency.
- `src/stage_abi/schema.py` and `contracts/stage_abi/v1/request.schema.json`: machine-readable version `stage-agent-abi/1.0`; old proposed versions remain historical design references, not alternate runtime versions accepted implicitly.
- `src/stage_abi/store.py`: content-addressed immutable artifacts with exact kind/hash checks and no request-provided paths; process-safe attempt claims, input-bound idempotency, retained checkpoints, immutable terminal state and explicit failures. Local custody is not an external security authority.
- Focused evidence:118 passing tests plus2 subtests, including existing v0.1 compatibility, all35 request shapes, schema/source parity, invalid selectors/numbers/paths/authorization, artifact corruption/symlinks, concurrent artifact writes and single-attempt claiming.

No stage execution operation is advertised as implemented merely because its request can be validated. The store is an internal primitive; no public artifact-write endpoint grants callers the ability to mint execution authority.

## Original completion checklist at the foundation checkpoint (historical)

| Requirement | Current state | Required direct evidence |
|---|---|---|
| Consolidation commit/push and freeze preservation | Verified | Commit/remote and unchanged freeze manifests |
| Closed request and artifact/job custody | Implemented, focused tests pass | Retain schema/negative/concurrency evidence |
| Profile/scene/policy/authorization registry and request/response CLI | Pending | Trusted local bindings, strict response contracts, actual dispatch tests |
| Describe, inspect and paginated source/finding evidence for each suite | Pending | Real bound scene records, stale cursor and unsupported profile tests |
| Deterministic plans for every suite | Pending | Exact writable/protected sets, scopes, budgets, source/family/implementation bindings |
| T01 run and verify | Pending | Actual circle construction and saved-source reconstruction, original shape policy and explicit unsupported profiles |
| T02 run and verify | Pending | Actual ordinary/inclusive rectangle execution; full current scene and source ports; no junction-domain leakage |
| T03 search and verify | Pending | Actual bounded single-chain/bundle generator execution, adaptive patch bounds, fixed-width/protected-land checks, continuous bundle/transition proof scope; no no-change-only substitute |
| T04 run and verify | Pending | Actual bounded complete-route width search plus independent source reconstruction of nominal/envelope results and scale/group invariants |
| T05 run and verify | Pending | Actual source-contact admission, bounded spindle construction and saved owner/window/patch replay with simultaneous final checks |
| Compare and review for every suite | Pending | Exact compatible source/frame comparisons, real cumulative visuals/deltas, recorded rather than manufactured decisions |
| Execution authority/idempotency/resume integration | Pending | Host-bound authorizations, no duplicate execution, conflicting retry, failure/interruption/budget controls and actual backend checkpoints |
| Modular composition and new-sample qualification | Pending | Compatible exact scene handoffs and scope isolation across stages; unsupported orders stop; source-bound end-to-end samples |
| Legacy compatibility and complete regression | Partially verified | Preserve v0.1 read behavior and frozen decisions; new execution paths need their own real-source tests |
| Delivery | Active | Actual implementation map, reproducible commands, final test/negative-control/visual evidence and requirement-by-requirement completion audit |

Independent review, native export, electrical intent and manufacturing remain separate qualification statuses. No accepted crop, original fixture or historical audit is rewritten to make a runtime test pass.


## Service / first real adapter checkpoint

Implemented after the foundation checkpoint:

- `registry.py`: trusted host profile, policy/scene/bounds/verifier and authorization references. Requests cannot register adapters or mint authority.
- `scene.py`: closed source record sets, original/current finite copper and explicit mm/F.Cu frame semantics.
- `service.py`: shared describe, paginated inspect, bound planning, run/verify job custody, exact geometry comparisons and saved decision review. Execution requires an actual host-selected adapter, scoped registered authority and current plan/implementation hashes. Failure jobs retain evidence; retries do not relaunch.
- `spindle.py`: actual T05 source-contact admission, bounded four-radius spindle construction, direct selected-patch reconstruction, simultaneous patch checks, protected source map, cumulative output scene and explicit lineage.
- `visuals.py`: exact same-frame source-copper/delta SVGs, not illustrative PCB geometry.
- `cli.py` and `tools/stage_agent_abi.py`: one JSON request/response, trusted catalogue digest, project-local store, duplicate-key/oversize rejection. The current factory exposes `spindle-v1` only; other stage execution adapters are still pending.

Current focused regression:125 PASS +2 subtests. T05 plan/run/verify/compare/review, idempotent retry, unregistered authority, stale cursor/plan, forged patch rejection and output-scene composition are exercised on an explicitly synthetic geometry fixture. CLI host registry hash/strict JSON tests pass. This is not native-board or independent qualification. The earlier Pending matrix is retained as the original full completion checklist; the service/T05 rows have progressed, not closed at all required qualification rungs.

Next: implement T01/T02 land, T04 complete-width and T03 real bounded route-search adapters; qualify real source bindings, arbitrary supported scene handoffs, interruption/resume and all operation response/negative controls. Do not equate the available T05 test adapter with completion of all ABI suites.

## T01/T02/T04 execution checkpoint

- `lands.py`: actual T01 round-class construction and T02 whole-rectangle/inclusive-fill construction, using the existing simultaneous source-visible land checker. Original contact ports are rebound from original operands rather than fabricated by incoming width growth. Verification reconstructs selected class/axis factors, rejects over-cap changes, rechecks coverage and repeats connected-span/shortage/foreign/prior-merge rules. No rectangle domain is delegated to T05.
- `width.py`: native source-bound complete-route group planning, original stroke/native span binding, real ceiling-first collective search, simultaneous nominal and conservative-envelope checks, exact per-primitive artifacts, protected contributions, direct source reconstruction and fresh upper-bracket proof checks. No nominal width narrowing or route adjustment.
- `runtime.py`: finite execution budgets and immutable complete output-source-map/lineage construction and replay.
- `native_import.py`: host-only complete original cache binding and atomic complete-route scene normalization. Native member IDs remain in the route metadata. This is not a wire endpoint that can mint authority.
- CLI adds `round-class-v1`, `rectangle-inclusive-v1` and `native-width-v1` alongside `spindle-v1`. T03 execution is still not implemented/advertised by the new factory.

Focused tests:137 PASS +2 subtests. New cases exercise real land construction/replay, rejected fake circle metadata, disconnected inclusive rectangles, changed factors, native parallel-group width limiting, duplicate groups, altered parts and native source/cache drift.

Actual C03 source qualification: `out/crop_dynamic_tasks/stage_abi_native_width_20261031_279/RECEIPT.json` records real ABI inspect/plan/run/verify over one prepared two-segment complete native route with the full17,849-object original/T01 context. It reached1.5× and passed source-bound nominal/envelope replay. Source normalization accounts for all native member IDs:2 selected,17,847 fixed. This is deliberately a single-route qualification, not all-route qualification or a new accepted C03 result. `TRANSCRIPT.json` stores actual requests/responses and `index.html` shows geometry-derived full/detail before/after views.

T03 adaptive single/bundle route search, general composition, response contracts, full interruption/resume integration and broader source qualification remain required. The goal is active; the available stage profiles do not constitute completion of all ABI suites.

## T03 and modular composition checkpoint

- `src/parallel_route_geometry.py`: deterministic common-reference normal offsets, bounded miter joins, analytic segment tangent/order validation, endpoint-tangent-preserving displacement and explicit connected control-chain extension distance. This is a named polygonal family, not sampled-only proof for arbitrary native curves.
- `routes.py`: actual obstacle-directed T03 search. It starts with the selected local control domain, derives an outward direction and minimum clearance displacement, extends the control-chain domain only within finite limits, and recursively includes authorized blocking members. Fixed obstacles, endpoint/source width changes, corridor escape and exhausted budgets reject candidates. Single-route movement is the one-member case. Unresolved search produces NO_IMPROVEMENT_FOUND, not geometric PASS.
- `derived_routes.py`: exact selected T03 replacement paths become separately bound derived native segment sources for T04. Original board hash and original footprints remain bound. These bytes are never represented as an untouched original board.
- T04's pure group model now accepts explicitly bound per-chain source authorities. This permits original and qualified T03-derived routes in one scene without reverting to old route geometry. KEEP retains incoming complete-route bytes.
- `composition.py`: trusted host grants bind an exact stage/template sequence and source scene. Only an actual passing stage verification admits a working output scene to the next profile. Construction and verification still go through suite requests. No owner acceptance, freeze promotion or accepted-scene mutation occurs. Repeated identical scoped attempts reuse prior jobs.
- Verification receipts now explicitly identify their output scene. This closes the mismatch between a verifier's input scene and the qualified scene a dependent stage consumes.

Current focused regression:171 PASS +2 subtests, including prior request/schema/store/CLI/legacy tests. T03 negatives include fixed blocker, no authorized extension, altered shared reference, reversed inner offsets and endpoint/domain changes. A positive test requires both adaptive extension and recursive two-trace movement; it directly verifies source widths/ports and analytic shared-reference offsets. Another executes T03 movement then native T04 growth against those actual replacement paths. A complete five-suite T01 → T03 → T04 → T02 → T05 test passes through current verified scene handoffs; its T03 objective needs no change, while positive movement is separately exercised. These are model/source-parsed fixtures, not broader real-board qualification.

Remaining full-goal requirements: robust interrupted-job resume and consumed-budget continuity; operation response contracts and further authority/budget falsification; broader real-source qualification/profile support inventory; delivered CLI/composition examples and full requirement-by-requirement completion audit; final implementation commit/push. Historical native/independent/electrical/manufacturing limits remain separate and unchanged.

## Recovery, resource limits and public response checkpoint

Implemented `journal.py` and process-owner leases in `store.py`. A RUNNING attempt is reclaimed only after its original owner is demonstrably dead on the same host; live or unknown owners are never blindly restarted. Committed check events bind request/implementation fingerprint, ordinal, check name, input hash and immutable result. Recovery replays this same attempt's recorded prefix explicitly as REPLAY and continues at the next uncommitted event. It does not inject another attempt's cached PASS or renew consumed evaluation counts. Initial wall/monotonic timing and the original deadline persist across retries. Terminal attempts remain immutable; conflicts reject.

Artifacts and job records use atomic replacement. Jobs retain an exact immutable request binding reference as well as its digest. The dispatcher binds the complete local runtime/kernel and library fingerprint into plans, rejects changed registered bounds, and meters complete logical output including events/checkpoints/metadata, not merely WKB blobs. Expired execution cannot publish a late candidate.

`responses.py` and `contracts/stage_abi/v1/response.schema.json` close operation-specific response envelopes, jobs, execution evidence and errors. The dispatcher validates all outgoing responses; malformed backend output becomes a rejection. Numeric values must be finite and verifier PASS must be a literal boolean. Existing v0.1 compatibility remains unchanged.

Current focused regression:199 PASS +2 subtests. Actual subprocess death/recovery is tested for both construction/search and verification in all five suites. Recovered candidate/verification artifact identities equal uninterrupted execution. Negative tests cover live-owner claims, different bindings, event-input drift, no renewed deadline, whole-output budget exhaustion, late geometry results, changed registered bounds and false truthy verifier statuses. All35 operations now pass through the real JSON CLI and registered stage factories, not just direct request-shape tests.

Inspection of actual C03 native circle input found its original polygon uses20 quadrants rather than the new class constructor's128. T01 admission now binds an explicit original tessellation (4..512) and requires exact original model equality; growth remains the existing128-quadrant class family. It does not silently normalize source geometry. New positive/negative cases cover this real-source preparation requirement. Native import also requires current-width authority for changed fixed native strokes and distinguishes nonrectangular native polygons from rectangle targets.

Still required for goal completion: broaden executed real-source stage qualification beyond the recorded T04 route; finish the supported-family catalogue and reproducible examples; perform the full requirement-by-requirement final audit and implementation delivery. All five local stage runtimes are implemented; broader input-family/native/electrical/manufacturing acceptance is not inferred from implementation or synthetic regressions.

## Final local completion

313 tests plus 2 subtests pass. Fresh source-bound T01, T02, T03, T04 and T05 packets 285–289 share runtime fingerprint `8636a36610be1f13e6b6a2be516bdd6328df4794512a427fb8b9c12983211091`. T01/T02/T04/T05 show positive native construction; T03 native geometry needs no change, with positive adaptive two-member displacement and T04 handoff retained separately in synthetic packet290. All19,990 frozen files, their three receipts and70 assets remain unchanged. The completion audit maps every original requirement to actual code/tests/evidence and states the supported-family limits. Existing independent and native/electrical/manufacturing limitations remain open; functional ABI completion does not promote any acceptance.
