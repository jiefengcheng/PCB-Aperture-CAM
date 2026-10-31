# T02 ChatGPT-agent ABI suite — design only

Historical design proposal retained below. The separately versioned, executable [stage-agent-abi/1.0 runtime](../../agent_abi/STAGE_RUNTIME.md) now implements this suite for explicit supported families; use its schemas and qualification limits. This does not change the legacy v0.1 profiles or frozen crop evidence.

**PROPOSED / NOT_IMPLEMENTED.** T02 owns rectangle-land growth and separately admitted inclusive rectangle consolidation only. The earlier request named T02 alongside T05 consolidation; standalone T04 and T05 suites are now specified separately. No route-width or junction-growth operations belong to T02. No functions, stubs, runtime schemas, service endpoints, registry entries or new executable tests are implemented by this design. Existing v0.1 `cam_run` and `cam_verify` remain unavailable.

The [older deferred mapping](T02_AGENT_ABI_DEFERRED.md) and [v69 structure map](T02_CODE_STRUCTURE.md) remain historical references. This proposal covers both their evidence-inspection boundary and the newer trace-first T02 lineage, without pretending those profiles are interchangeable.

## Scope clarification — 2026-10-31

Review found no T05 selectors or spindle implementation inside this specification; no runtime scope restoration was necessary. T02's legitimate original ordinary/inclusive rectangle behavior is retained. Trace/land contact and clearance inspection is a constraint check, not permission to perform T03 routing, T04 width changes or T05 junction blending. Historical v69/v15 and trace-first profiles remain distinct. Stage order is an explicit profile/predecessor requirement, not a universal dependency on one named crop. See [T04](../t04_architecture_notes/T04_AGENT_ABI_PROPOSAL.md), [T05](../t05_architecture_notes/T05_AGENT_ABI_PROPOSAL.md) and [composition rules](../AGENT_STAGE_COMPOSITION.md).

## Agent workflow and operations

An agent should describe support, inspect exact current scene/selection, request a bounded plan, separately authorize construction when a real adapter is qualified, verify the saved candidate, and inspect comparable evidence. No step silently advances the accepted scene.

| Proposed operation | Required payload | Returned artifact/data | Future side effects |
|---|---|---|---|
| `t02_describe` | Requested ABI/profile version, or null for the support catalogue | Operations, input families, parameter provenance, support/adapter availability and qualification limits | None |
| `t02_inspect` | Scene and policy refs; source/finding/ledger selection; bounded page size/cursor | Current rectangle cores, exact neighbors and surface metrics, attachments, coverage/skip witnesses, inherited findings and ambiguities | None |
| `t02_plan` | Inspection ref, target-set ref, predecessor qualification receipt, policy ref, authorized bounds ref, requested ordinary/inclusive phases | Content-addressed plan with ordered targets, immutable set, caps, merge candidates, objective, budgets and unsupported requirements | None; no geometric construction |
| `t02_run` | Plan, exact current scene/policy refs, execution authorization ref and idempotency key | Immutable attempt receipt, per-target decisions, optional candidate ref, complete cumulative scene, actual delta and unresolved evidence | New project-local candidate/evidence only; cannot mutate accepted geometry |
| `t02_verify` | Saved candidate, source scene, plan, policy and verifier-family refs | Executed saved-source replay and full declared geometric checks; exact failing operands, coverage and numerical limits | New verification evidence only; no search/repair |
| `t02_compare` | Compatible predecessor/candidate refs, common viewport/frame, bounded source/finding filters | Source-ID change map, actual added/removed copper, aligned full/detail images, metric and ledger differences | New derived review artifacts only |
| `t02_review` | Candidate/verification refs and bounded receipt filters | Stored owner and independent decisions, scope and availability, missing evidence, inherited limitations | None; cannot approve, freeze, promote or fabricate a review |

These seven names are proposed operation selectors, not callable tools. Their eventual mapping to `cam_describe`, `cam_inspect`, `cam_plan`, `cam_run`, `cam_verify`, `cam_compare`, `cam_review` is one-to-one through an explicitly qualified T02 profile adapter. Do not add aliases to the live v0.1 dispatcher now. A local procedural script is not an ABI adapter; a saved audit is not execution of `t02_verify`.

There is no agent-facing `approve`, `freeze`, `commit`, `push` or automatic next-stage operation. Promotion requires real recorded coordinator/owner authority at the appropriate scope, outside this suite. Rollback retains the immutable predecessor and records a rejected candidate; it never edits the accepted input to undo an implicit mutation.

## Versioned profiles and lineage

| Proposed profile boundary | Current evidence | What must remain distinct |
|---|---|---|
| Historical v69/policy15 evidence reader | Saved source, accepted T01 admission, v69 decisions, latent covered-circle selections and old ledgers | Inspection of recorded evidence only until adapter qualification. Preserve its actual 0.02002 mm construction target, 0.02000 mm floor and source-specific topology/attachment treatment; do not import old centerline wording. Historical ledger counts are not a new universal target set. |
| Trace-first finite-surface T02 ordinary growth | Current `crop_stage_growth`/`joint_rectangle_growth` helpers and saved C02 result226 | Consume the exact qualified cumulative T01/T03/T04 scene, not T01 alone. Ordinary rectangle axes capped at 1.25×, immutable widened trace parts, finite copper-surface clearance and current ports. Bind actual policy parameters; the current construction target is 0.02010 mm. |
| Connected inclusive rectangle consolidation | Saved C02 merges229, up to 20% missing bounding-box area | Separate operation class and admitted limit; not an unlimited exception to ordinary rectangle caps or blanket permission to join source components. |
| Post-consolidation context rectangles | Saved C02 completion232 | Exact exposed context targets, protected partial-viewport and covered skips, and current final-scene checks. |

These are proposed adapter support partitions, not registered IDs or new qualification. Scene lineage carries ordered stage refs and geometry hashes. It explicitly states whether T03 changed routes, T02 was owner-skipped, or a stage was not run. C01's owner-directed T02 skip is a legitimate recorded disposition, not permission for an agent to run T02 there. C02 T05 consumes the final T02 scene; T05 does not retroactively legalize a failed T02 candidate. C03 requires its own admitted source/crop/predecessors and cannot inherit C02 acceptance by relabeling.

The latest owner-accepted C02 scene is freeze266 after T05. It is an accepted historical result to inspect, not an input on which an agent may silently run T02 again. A new T02 attempt must declare an appropriate immutable pre-T02 scene and a separately scoped lineage.

## Proposed wire envelope

This is a design specification, not an implemented JSON Schema. The top-level object is closed; unknown keys reject. Each operation has a closed payload and explicit required/null rules. Plain JSON data only: no shell command, Python source/import, evaluator callback, network URL or caller-supplied executable checker is accepted.

```json
{
  "abi_version": "t02-proposed-0.1",
  "request_id": "caller-stable-id",
  "operation": "t02_plan",
  "profile_id": "trace-first-ordinary-plus-inclusive-proposed",
  "scene_ref": {"artifact_id": "scene-id", "sha256": "<64-lowercase-hex>"},
  "policy_ref": {"artifact_id": "policy-id", "sha256": "<64-lowercase-hex>"},
  "plan_ref": null,
  "authorization_ref": null,
  "idempotency_key": null,
  "payload": {
    "inspection_ref": {"artifact_id": "inspection-id", "sha256": "<64-lowercase-hex>"},
    "target_set_ref": {"artifact_id": "targets-id", "sha256": "<64-lowercase-hex>"},
    "predecessor_qualification_ref": {"artifact_id": "receipt-id", "sha256": "<64-lowercase-hex>"},
    "bounds_ref": {"artifact_id": "bounds-id", "sha256": "<64-lowercase-hex>"},
    "phases": ["ordinary_rectangles", "inclusive_rectangles", "context_rectangles"]
  }
}
```

Placeholder hashes are explanatory text, not valid inputs or grants. Artifact IDs resolve through a trusted project-local registry; no free-form filesystem path enters a request. Resolution must enforce allowed roots and reject path traversal/symlink escape. Existing project-local frozen inputs may be read; all new outputs use fresh `out/` locations. There are no arbitrary remote downloads or external uploads.

- `describe`: scene/policy/plan/authorization/idempotency refs null; profile selector may be null for the catalogue.
- `inspect`: scene and policy required; plan/authorization/idempotency null. A selection is explicit, never inferred from an empty list meaning “everything.”
- `plan`: scene/policy and the five payload fields shown above required; plan/authorization/idempotency null. The bounds ref declares finite object/iteration/time limits and allowed output/viewport scope.
- `run`: scene/policy/plan/authorization/idempotency required; payload binds the exact objective and requested output scope already present in the plan. Caller numbers cannot broaden the authorized plan.
- `verify`: scene/policy/plan and candidate/verifier refs required; authorization is required if the host policy treats execution of verification as scoped work; no construction authorization is implied. Verification job identity/idempotency is separate from a construction job.
- `compare` and `review`: exact saved artifact refs required; no execution authorization or construction idempotency key. Artifact creation for comparisons remains bounded and records its own evidence request identity.

Ref validation happens before artifact reads. References bind board SHA, native source occurrence/byte span and exact geometry SHA; UI labels R001 or a physical-component label alone are never sufficient identity. Coordinates are finite mm values in a named frame. No NaN/infinity, unit guessing, implied Y inversion or implicit geometry normalization is admitted. Wire-format numbers use one declared canonical decimal representation; geometry WKB serialization/kernel/tessellation versions are separate bound fields. Exact identity failures are not silently converted into approximate equality.

## Required scene, policy and plan content

A scene binds the original board/input manifest, layer role/units/polarity, exact crop and registration evidence, complete current copper composition, source-to-contribution mapping, ordered predecessor lineage and all current acceptance/qualification receipts. Source selections, current replacements and effective composed copper are different sets. Fixed lands and T04 source parts remain exact protected contributions.

A policy binds the constructor/verification family versions and implementation digests, supported semantics, ordinary axis caps, whole-rectangle/center/orientation constraints, finite copper-surface distance rules, source-local ports, numerical tolerances, inclusive shortage definition, applicable geometry exceptions, comparison scope and every finite budget. A profile must reject semantics it cannot qualify rather than borrow constants or exception rules from another profile.

A plan binds exact eligible target IDs and all covered/withheld/unsupported dispositions; immutable IDs; original contact witnesses and port domains; current complete-neighbor discovery; ordered ordinary and inclusive phases; candidate ranking/search budget; expected predecessor/result assembly order; and failure handling. Each merge has source members/support IDs, its exact current connected span, bounding box, overlap with other merges and admitted threshold. A scope expansion creates a different plan and authorization binding, never a changed in-place writable set.

## Construction and verification obligations

1. **Preserve the source:** ordinary rectangle growth retains the complete core, center/orientation and required attachment. It must stop rather than recess around a disconnected circle and embed that circle in a carved rectangle.
2. **Use actual copper surfaces:** clearance uses the finite-width conductor boundary. Route centerlines may describe the route but never determine T02 clearance acceptance. Both sides, current circle occupation and its safe gap, unrelated copper and other final additions are checked.
3. **Keep trace-first geometry fixed:** no route shift, width reduction or assumption that a later trace step will create room. A proposed new violation cannot be approved as `OPEN_FUTURE_TRACE_SESSION` merely because T03/T04/T05 exist in the architecture. Historical inherited findings remain separately identified.
4. **Consolidate only qualified spans:** `shortage = area(bounding_rectangle − actual_current_span) / area(bounding_rectangle)`; denominator must be positive, shortage ≤ the bound 0.20 for the current profile, and the supporting span must be connected by qualified existing contacts. Filling does not grant new electrical connections or waive foreign clearance. Ordinary axis caps and inclusive-merge limits are separate; any extra bounding-box extent requires explicit profile limits.
5. **Handle covered objects honestly:** report zero effective growth for unchanged KEEP/covered source objects. Legacy latent covered-circle selection, when merely inspected, is distinct from visible copper. The newer profile does not run the legacy circle-palette pass automatically or change frozen T01 circles.
6. **Check the complete final scene:** include all ordinary/context parts, accepted merges and immutable T01/T04 contributions; recheck final neighbors, source contacts, affected physical-component separation, crop bounds, exact delta and assembly. No per-object success alone establishes a valid cumulative result.
7. **Bind verification:** re-derive eligible source operands and construction decisions, compare protected source identities, reconstruct the cumulative scene and retain deliberate failure controls. Numeric differences may be diagnosed, but a strict failed expected hash remains failed until a separately authorized investigation resolves it.

Physical contact, geometry partition preservation, electrical intent and manufacturing suitability remain separate. A connected polygon, accepted screenshot or matching hash does not prove the latter two.

## Response and decision model

Every response carries `abi_version`, request/operation/profile IDs, `adapter_status`, `execution_status`, `geometry_verdict`, `outcome`, input/policy/code/plan digests, result/evidence refs, target coverage, deterministic counters, limitations and an error object or null.

| Dimension | Proposed values and interpretation |
|---|---|
| Adapter | `NOT_IMPLEMENTED`, `UNAVAILABLE`, `AVAILABLE_QUALIFIED`; describes that specific profile/operation, not the entire library |
| Execution | `NOT_RUN`, `COMPLETED`, `ABORTED`; no execution is inferred from evidence inspection |
| Geometry | `NOT_RUN`, `PASS`, `FAIL`, `NOT_ESTABLISHED`; PASS only for fully stated supported scope |
| Outcome | `CANDIDATE_FOUND`, `NO_VISIBLE_GROWTH`, `REJECTED`, `BLOCKED`, `NONE`; KEEP is not a construction error |
| Per target | `GROWN`, `KEEP_CLEARANCE_LIMITED`, `KEEP_ALREADY_RECTANGULAR`, `COVERED_SKIP`, `WITHHELD`, `UNSUPPORTED`, `UNRESOLVED`; each has a source-bound reason and actual added area |
| Acceptance | Owner and independent receipts each have their own exact scope/ref; absent receipts stay pending/not run. Electrical/native/manufacturing states remain independent. |

A successful transport/verification operation may return geometry FAIL. An unavailable adapter returns NOT_RUN, not an empty PASS. Missing local artifacts cannot be replaced by a rendered screenshot, a cached final WKB injection into a source replay, or old receipt text presented as a fresh check.

Errors have stable `code`, `message`, `operand_refs`, `stage`, `retry_class` and `evidence_refs`. Proposed codes include `ADAPTER_NOT_IMPLEMENTED`, `SOURCE_BINDING_MISMATCH`, `PREDECESSOR_NOT_QUALIFIED`, `POLICY_PROFILE_UNSUPPORTED`, `FRAME_MISMATCH`, `STALE_SCENE`, `TARGET_SET_AMBIGUOUS`, `CONTACT_INTENT_UNRESOLVED`, `CLEARANCE_FAILED`, `MERGE_SHORTAGE_EXCEEDED`, `MERGE_SPAN_DISCONNECTED`, `FIXED_PART_CHANGED`, `ASSEMBLY_IDENTITY_MISMATCH`, `BUDGET_EXHAUSTED`, `AUTHORIZATION_MISSING`, `IDEMPOTENCY_CONFLICT` and `ARTIFACT_UNAVAILABLE`. Invalid/stale refs require re-inspection, not a retry that bypasses validation; transient storage failure may resume the same job identity.

## Deterministic work, pagination and recovery

Canonical request+scene+policy+plan+implementation digests bind an idempotency key for construction. Same key/same binding returns the same immutable stored attempt; same key/different binding rejects. A completed zero-growth/rejected attempt is still consumed and must not silently restart. Finite deterministic target order, phase order, candidate ordinals and budget consumption survive checkpoints. Output publication is atomic only after its manifest is complete; interrupted jobs expose incomplete status, never accepted scenes.

Pagination has a bounded maximum page size, deterministic source ordering, and cursors bound to the exact scene/selection/query digest. Stale cursors reject; they cannot silently switch crops or lose unresolved findings. Future asynchronous adapters must return a job ref for polling the existing execution, not launch again during status reads.

## Evidence contract and qualification before exposure

Retain original/current source mappings, every target disposition and rejected probe, exact per-source additions, protected identities, whole cumulative before/after copper, source contact and merge coverage, nearest-point finite-surface witnesses, actual delta, same-frame full-crop/located details, runtime versions, code/policy/source hashes and independent versus owner decisions. Ledger entries preserve individual IDs, classification and provenance; an unrelated global count cannot establish closure.

Before any real suite function is registered, separately authorize and qualify:

- Closed payload validation, capability discovery, safe artifact resolution, missing refs, unsupported policy/units/semantics, stale plans/cursors and duplicate source identities.
- Exact predecessor/source binding for each admitted crop and ordinary/inclusive family; direct-runner/adapter parity without hardcoded C02 constants.
- Fixed trace/land preservation; surface-clearance, circle occupation, attachment leakage, disconnected/new-contact merge and shortage boundary negatives; known inherited versus newly introduced relationships.
- Original-source reconstruction, exact cumulative assembly, invalid candidate/zero-growth/KEEP distinctions, preserved failure receipts and full declared target coverage.
- Idempotency conflicts, interruption and partial publication, deterministic resume and finite-budget failure without accepted-scene mutation.
- Output/schema/tool registration qualification independent of geometric tests. Same-assistant parity cannot be advertised as independent mathematical correctness.

**Implementation remains deferred.** This document does not start T02 reconstruction, C03, ABI wiring, native export, network services or public tool exposure. The implemented [T05 consolidation](../t05_architecture_notes/T05_CODE_STRUCTURE.md) remains an internal local capability.
