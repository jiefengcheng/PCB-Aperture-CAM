# Version-1 ABI implementation completion audit

Verdict: **IMPLEMENTED_AND_LOCALLY_VERIFIED** for all 35 operations and the
explicit families in [the runtime catalogue](STAGE_RUNTIME.md). This is a
same-assistant implementation audit. It grants no new crop acceptance, independent
verification, native export, electrical or manufacturing qualification.

The consolidation/design commit is `d6a0cfb`. Runtime source and published
qualification results are the subsequent implementation delivery. The current
runtime fingerprint is
`8636a36610be1f13e6b6a2be516bdd6328df4794512a427fb8b9c12983211091`.
It binds all local top-level kernels, stage ABI source and runtime libraries.
Source qualifications retain matching code snapshots and per-file manifests.

| Required work | Direct implementation / evidence | Result |
|---|---|---|
| Separate suites and scope | `lands.py` owns T01/T02; `routes.py` T03; `width.py` T04; `spindle.py` T05. T02 performs no junction blending; T05 performs no rectangle enlargement. Legacy v0.1 files remain unchanged. | PASS |
| Closed public contracts | Request/response schemas and 35 per-operation host-neutral tool projections; exact required/null fields, finite plain JSON, explicit selection, no executable payloads. | PASS |
| Actual dispatch for every operation | `test_stage_abi_all_wire.py` executes all 35 selectors through the stdin/stdout CLI and registered production factories. These are not unavailable stubs. | PASS |
| Source/profile/authority custody | Trusted catalogue digest; registered scene/policy/bounds/verifier refs; distinct execution authorization; exact plan/runtime binding; corruption, scope drift and stale cursor/plan negatives. | PASS |
| T01 construction and verification | Positive native circle C202 growth with complete 17,849-object source context; explicit original 20-quadrant tessellation and diameter classes; direct selected class replay. | PASS, bounded native operation |
| T03 actual route modification | Adaptive domain extension and recursive two-member movement through one reference; analytic segment/miter parallel/order checks, full finite copper and protected-width/port checks. Positive synthetic bundle → native-derived T04 composition is retained. A source-native segment case correctly returns NO_CHANGE_REQUIRED. | PASS for declared polygonal family; no broad native-curve claim |
| T04 construction and verification | Actual two-part complete native route reaches common factor 1.5; direct nominal/envelope/source/scale reconstruction. Synthetic parallel groups exercise active limiting and fresh rejected-upper proof checks. | PASS, bounded native operation and group models |
| T02 construction and verification | Positive native rectangle R258 growth over actual T04 input; whole geometry, original-source ceiling and final scene checks. Connected inclusive fills and disconnected/foreign rejection controls execute on models. Repeated stages cannot compound the original 1.25× cap. | PASS for declared ordinary/inclusive family |
| T05 construction and verification | Positive actual source-contact spindle over actual post-T02 input, added area 0.006514554710827934 mm², zero removals; direct patch reconstruction and final checks. False contact/patch, covered role, ring/box and conflicting alias negatives. | PASS, bounded native operation |
| Comparison and review | Exact source-contribution refs, added/removed WKB, compatible same-frame SVGs, bounded decision pagination. Missing owner/independent decisions remain PENDING/NOT_RUN. | PASS |
| Deterministic jobs and recovery | Actual subprocess death during all five construction/search and all five verification paths; exact owned-prefix recovery, equal candidate/proof refs versus uninterrupted execution, no live-owner takeover, no reset deadline. Whole-output budgets, scope conflicts and failed terminal retry tested. | PASS |
| Modular composition | Full T01→T03→T04→T02→T05 model sequence and positive moving-bundle→T04 handoff use ABI calls. Failed verification stops before dependent work; changed/unregistered composition grants reject. Output acceptance is never fabricated. | PASS for admitted inputs; whole-board discovery not claimed |
| Regression and compatibility | **313 tests plus 2 subtests pass**, covering stage ABI, legacy v0.1, shared source-offset/width/clearance/land/spindle kernels and pipeline. Dependencies already pinned; none installed or changed. | PASS |
| Frozen acceptance preservation | 70/70 immutable assets; all **19,990 frozen files and three receipts** unchanged. Existing checked-in C01/C02 and C03 packages pass their 347-file/45-link and 1,100-file/46-link saved-geometry checks. | PASS |
| Visual/reproducible delivery | [Local evidence gallery](results/20261031/index.html), same-frame full/detail source images, explicit synthetic model, compressed actual wire transcripts, WKB, exact local artifact manifests and deterministic delivery verifier. | PASS |

The actual-board qualifications are separate selected-operation executions with
complete source context. They are **not** a newly accepted five-stage whole-board
run. End-to-end composition is exercised on explicitly labelled models; an actual
positive T03 native curve repair and automatic new-board route discovery remain
outside the qualified input family. Unsupported geometry must be admitted through
a separately versioned profile, not coerced into a passing one. The full source
cache and runtime stores stay local; their hashes are published without copying
the raw board cache into this package.

The first exploratory T01 target C028 was correctly classified COVERED_SKIP by
the new adapter and therefore did not meet that packet's positive-growth goal.
The later C202 packet provides the required positive native case. A concurrent
source edit caused the first T02 qualification's verify call to reject STALE_PLAN;
that failed attempt remains preserved. A fresh unchanged-runtime execution passes.
These outcomes are retained under packets 281/282, not overwritten or promoted.

Historical C02 independent `REVISE_STRICT_EXACT_REPLAY_NOT_CLOSED`, inherited
findings and C03 provisional screenshot localization are preserved. No evidence
here closes them. Independent review of this runtime is **NOT_RUN**. The ABI's
local geometric PASS is limited to its explicit source/family/selection and
checks; it does not establish net intent or whole-board absence of defects.

Recheck the delivered package with:

```sh
.venv/bin/python tools/verify_stage_abi_delivery.py \
  docs/agent_abi/results/20261031 --require-current-runtime
```

Without `--require-current-runtime`, this command verifies historical package
integrity and saved geometry while reporting code drift explicitly. It does not
re-execute source construction or claim independent mathematical verification.
