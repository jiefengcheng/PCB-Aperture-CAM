# Executable stage suites, version 1

`stage-agent-abi/1.0` implements **35 local operations** across five separate
suites. T02 owns ordinary/inclusive rectangles. T05 owns additive junction
treatment. Neither delegates its geometry domain to the other.

| Suite | Operations | Registered adapter family | Writable domain |
|---|---|---|---|
| T01 | `t01_describe`, `t01_inspect`, `t01_plan`, `t01_run`, `t01_verify`, `t01_compare`, `t01_review` | `round-class-v1` | Source-bound filled circles, discrete classes, original 1.5× diameter cap |
| T03 | `t03_describe`, `t03_inspect`, `t03_plan`, `t03_search`, `t03_verify`, `t03_compare`, `t03_review` | `parallel-route-v1` | Authorized constant-width polygonal trace spans; bounded adaptive patch extension and coordinated bundle displacement |
| T04 | `t04_describe`, `t04_inspect`, `t04_plan`, `t04_run`, `t04_verify`, `t04_compare`, `t04_review` | `native-width-v1` | Complete native or explicitly T03-derived routes; one uniform 1..1.5× factor per source-disjoint group, including singletons |
| T02 | `t02_describe`, `t02_inspect`, `t02_plan`, `t02_run`, `t02_verify`, `t02_compare`, `t02_review` | `rectangle-inclusive-v1` | Whole axis-aligned rectangles within original 1.25× axis caps; connected inclusive fills with at most 20% area shortage |
| T05 | `t05_describe`, `t05_inspect`, `t05_plan`, `t05_run`, `t05_verify`, `t05_compare`, `t05_review` | `spindle-v1` | Optional spindle additions inside source-contact-qualified windows; predecessor geometry unchanged |

These are executable local JSON selectors, not installed ChatGPT tools or a
network service. The historical [v0.1 reader](README.md) and its frozen unavailable
`cam_run`/`cam_verify` profiles remain compatible. The proposed `*-proposed-0.1`
envelopes were design documents; callers use the implemented version-1 schemas.

## Invocation

From this checkout, with a **trusted host-prepared** catalogue and store:

```sh
.venv/bin/python tools/stage_agent_abi.py \
  --registry out/your_scope/registry.json \
  --registry-sha256 EXACT_CATALOGUE_SHA256 \
  --store out/your_scope/runtime \
  --input out/your_scope/request.json
```

The paths above are explanatory. An actual executable source qualification is:

```sh
.venv/bin/python tools/qualify_stage_abi_source_profiles.py \
  --stage t05 --output out/new_unique_source_t05_execution
```

That host script verifies immutable assets and the full native source cache,
prepares one selected operation on actual C03 inputs, binds local authority,
calls inspect/plan/run/verify, and saves requests, responses, code snapshots,
geometry, measurements and full/detail images. It refuses to overwrite an output.
`--stage` also supports `t01`, `t02`, `t03`. T04 has a native complete-route example:

```sh
.venv/bin/python tools/qualify_stage_abi_native_width.py \
  --output out/new_unique_native_width_execution
```

Public request and response contracts:
[request schema](../../contracts/stage_abi/v1/request.schema.json),
[response schema](../../contracts/stage_abi/v1/response.schema.json), and
[35 host-neutral tool projections](../../contracts/stage_abi/v1/tool_projection.json).
The projections bind each operation to one closed request shape; they do not install tools.
Every top-level key is required; unused references are null. A reference is
exactly `{"artifact_id":"kind:SHA256","sha256":"SHA256"}` with matching
lowercase hashes. A request contains:

```json
{
  "abi_version": "stage-agent-abi/1.0",
  "request_id": "caller-stable-id",
  "operation": "t05_describe",
  "profile_id": null,
  "scene_ref": null,
  "policy_ref": null,
  "plan_ref": null,
  "authorization_ref": null,
  "idempotency_key": null,
  "payload": {"requested_contract_version": null}
}
```

For exact executable examples for every selector, see
[`test_stage_abi_all_wire.py`](../../tests/test_stage_abi_all_wire.py). It invokes
the actual CLI for all 35 operations using registered production factories.

## Host preparation and modular composition

The host imports supported, source-qualified geometry into immutable artifacts,
then registers exact scene/policy/bounds/verifier refs. The native importer binds
the board bytes, complete original cache and selected complete-route members.
Changed current native strokes require current-width authority. Other imports
must provide equally explicit geometry/source-role qualification. Original
source, current contribution and composed visible copper are separate operands.

The agent can inspect explicit source/finding records with bound pagination,
plan an inspected selection, execute with registered authority and a stable
idempotency key, verify the saved candidate, compare compatible scenes and read
recorded decisions. Inspection returns actual source metadata and geometry refs;
it does not automatically discover a qualified whole-board target set or infer
electrical intent. Planning adds the stage-specific eligibility and geometry
bindings. Compare returns exact source-contribution refs, copper deltas and
same-frame SVGs. Full/detail viewports are explicit separate compare requests.

`src.stage_abi.composition.execute_sequence` is the trusted host coordinator.
A composition grant binds the initial scene, source hash, exact ordered step and
selection-template refs, output scope and step limit. It calls the same ABI
inspect/plan/run-or-search/verify operations. Only a passing verification admits
the exact output scene to the next stage. A failed stage stops dependent work and
retains the previous qualified scene and complete transcript.

The tested order is **T01 → T03 → T04 → T02 → T05**. Stage order is explicit,
not hardcoded into constructors. Each selected adapter must admit its actual
predecessor. A qualified T03 replacement emits separately bound derived native
route authorities for T04; it never reuses old route bytes under a new label.
See [`test_stage_abi_composition.py`](../../tests/test_stage_abi_composition.py)
for a complete five-stage example and a positive two-trace T03 movement → T04
handoff. Those composition fixtures are labelled synthetic/native-parsed models,
separate from the actual-board single-operation qualifications.

The JSON client cannot install adapters, register scenes, grant itself authority,
provide arbitrary executable checkers, choose filesystem output paths, approve,
freeze, commit or push. These remain coordinator operations. Local catalogue
hashes provide integrity, not a security boundary against the filesystem owner.

## Supported families and limits

- T01 binds explicit native circle center/radius, original tessellation and
  admissible classes. It preserves round shape. Historical square-guided or
  non-round T01 profiles are not silently exposed through this adapter.
- T03 supports exact constant-width polygonal polyline footprints, common
  reference normal offsets and bounded miter joins. Segment tangent alignment
  and offset ordering are analytic; finite copper spacing is checked against
  the complete scene. Endpoints and endpoint tangents stay fixed. Curved native
  families that do not exactly match this model are unsupported, not normalized
  into it. The actual native example correctly returns `NO_CHANGE_REQUIRED`;
  adaptive, recursive two-member movement is separately demonstrated on a
  synthetic model. This is not proof of broad native curve routing.
- T04 requires host-qualified complete chains and a source-disjoint group
  partition. Fully covered/bulk source selection must be resolved by admission,
  not inferred from a component label. It retains per-native-part evidence and
  displays the collective copper delta once. Maximality is coordinatewise within
  the bounded source-offset model, not a global optimization theorem.
- T02 keeps the original rectangle center and core. Its ordinary ceiling is
  measured from the original source, including repeated invocations. Inclusive
  fill has a separate connectivity/shortage/foreign-clearance qualification.
- T05 binds original positive-area contacts and current contacts, rejects
  conflicting land aliases and unsupported source circle/rectangle roles,
  skips covered lands, and preserves every incoming contribution. Its four-radius
  schedule is a bounded spindle family, not a nominal trace-width change.

The currently registered policies use actual finite-width surfaces and explicit
attachment exceptions. A route centerline is never a clearance operand. Inherited
unchanged small gaps remain recorded; no stage silently turns them into a repair
target or a whole-board minimum-clearance PASS.

## Jobs, verification and evidence

Artifacts are content-addressed and atomically published. Plans bind source,
scene, policy, selection, qualification, finite bounds, adapter implementation,
all local runtime/kernel code and Python/Shapely/GEOS versions. Stale inputs or
code reject. Run/search and verify have separate scoped job identities.

Same key and binding reuses the original job; a conflicting binding rejects.
Recovery is permitted only when the same-host owner is demonstrably dead.
Committed check events replay that attempt's own exact prefix as `REPLAY`, then
continue with the next uncommitted event. Deadline and evaluation consumption
are retained, including downtime. A live or unknown owner is not stolen.
Terminal failures remain immutable. Total logical output includes journal,
metadata and checkpoint artifacts. Explicit bounds reject exhausted work.

Verification reconstructs selected geometry from source/family parameters,
checks protected contributions and cumulative assembly, and executes declared
simultaneous surface checks. It shares the project's geometry kernel and is
**same-assistant local verification**, not independent mathematical verification.
`OK` means the operation completed; a verification result can contain geometry
`FAIL`. Missing owner receipts remain `PENDING`; missing independent review is
`NOT_RUN`; native export, electrical intent and manufacturing qualification remain
`NOT_ESTABLISHED`.

The runtime never changes accepted C01/C02/C03 freezes. Qualification evidence
and the completion audit are linked from
[implementation record](STAGE_RUNTIME_IMPLEMENTATION.md).
