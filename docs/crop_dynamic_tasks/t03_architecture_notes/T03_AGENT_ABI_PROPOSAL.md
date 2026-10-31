# T03 ChatGPT-agent ABI suite — design proposal only

Historical design proposal retained below. The separately versioned, executable [stage-agent-abi/1.0 runtime](../../agent_abi/STAGE_RUNTIME.md) now implements this suite for explicit supported families; use its schemas and qualification limits. This does not change the legacy v0.1 profiles or frozen crop evidence.

**PROPOSED / NOT_IMPLEMENTED.** This is a host-neutral JSON contract design, not
registered ChatGPT tools, a callable server or an extension to the live v0.1 ABI.
No functions, stubs, adapters, runtime schemas or executor wiring are implemented.
The [architecture map](T03_CODE_STRUCTURE.md) separates existing code from gaps.
The existing `cam_run` / `cam_verify` ports remain unavailable.

## Small agent-facing operation suite

| Proposed operation | Purpose and required input payload | Result | Intended future side effects |
|---|---|---|---|
| `t03_describe` | No scene; request contract/version | Capabilities, support matrix, parameter bounds and actual adapter availability | None |
| `t03_inspect` | Scene/policy refs; selection of source IDs or finding IDs; bounded page request | Exact operands, eligible chains, ports, obstacle witnesses, explicit ambiguities and continuation cursor | None |
| `t03_plan` | Inspected scene, objective refs, authorized bounds, strategy and protected-contact refs | Content-addressed plan: original/expanded patches, movable groups, fixed objects, candidate ranking, budgets and unsupported requirements | None; no candidate construction |
| `t03_search` | Plan ref, exact scene/policy refs, separately granted execution authorization, idempotency key | Attempt receipt, accepted/rejected candidate refs or no-improvement/unknown disposition; deterministic counters | New immutable evidence under a fresh out/ run; no accepted-scene mutation |
| `t03_verify` | Saved candidate ref, source scene, policy, plan and verifier implementation refs | Complete cumulative geometric checks, exact failing operands, attachment and parallelism proof coverage | New verification evidence only; never searches or repairs |
| `t03_compare` | Compatible predecessor/candidate refs, common viewport, bounded evidence selection | Source-ID change map, exact added/removed copper, comparable cumulative images and metric differences | Derived review artifacts in out/ only |
| `t03_review` | Run/verification refs and evidence filters | Stored receipts and distinct human/independent decisions, limitations and missing evidence | None; cannot fabricate acceptance |

No `commit`, `freeze`, `approve` or tool-driven human acceptance operation is
included. An actual authorized coordinator must bind a qualified verifier receipt
and real decisions before advancing the accepted predecessor. Proposal creation
and verification never implicitly publish or promote copper. Rollback means
retaining the immutable predecessor and marking the candidate rejected; it does
not require undoing a mutation of accepted geometry.

## Common proposed envelope

All keys below are required in the proposed wire model; irrelevant refs are null.
Operation-specific payloads must be closed and validated before filesystem reads.
This design description is not an implemented JSON Schema.

```json
{
  "abi_version": "t03-proposed-0.1",
  "request_id": "caller-stable-request-id",
  "operation": "t03_plan",
  "scene_ref": {"artifact_id": "scene-example", "sha256": "<64-lowercase-hex>"},
  "policy_ref": {"artifact_id": "policy-example", "sha256": "<64-lowercase-hex>"},
  "plan_ref": null,
  "authorization_ref": null,
  "idempotency_key": null,
  "payload": {
    "inspection_ref": {"artifact_id": "inspection-example", "sha256": "<64-lowercase-hex>"},
    "objective_ids": ["source-bound-objective-id"],
    "bounds_ref": {"artifact_id": "approved-bounds-example", "sha256": "<64-lowercase-hex>"},
    "strategy": "obstacle_directed_single_or_bundle",
    "protected_contacts_ref": {"artifact_id": "contacts-example", "sha256": "<64-lowercase-hex>"}
  }
}
```

The digest placeholders above are documentation, not executable inputs. Examples
are never grants. Artifact IDs resolve through a trusted project-local registry;
no arbitrary shell command, Python import, evaluator callback, network URL or
caller-supplied WKB validator enters an execution request. Source selection uses
board SHA plus native occurrence/byte span and geometry hash, not UI labels.
Coordinates are mm in a declared frame, angles explicitly deg or rad; schema and
geometry-family versions are mandatory in referenced scene/policy objects.

Scene refs bind board, ordered predecessor lineage, complete source partition,
viewport and geometry hashes. Policy refs bind finite-width clearance floors,
construction guards, curve/tessellation error bounds, contact exceptions,
parallel alignment/spacing tolerances and transition rules. Centerlines may
represent routes; they never substitute for copper-surface clearance operands.
Historical C2 widths/policies cannot silently become generic defaults.

A plan records movable source IDs, fixed source IDs, original and expanded ports,
original widths, required/forbidden contacts, bounded transition regions, bundle
ordering and reasoned expansion steps. Every numeric search bound is finite and
hash-bound. Callers cannot overwrite protected geometry or widen permissions by
editing a plan. Invalid, stale or unqualified refs fail closed.

## Response, errors and reproducibility

Each response includes `abi_version`, `request_id`, `operation`,
`adapter_status`, `execution_status`, `geometry_verdict`, `disposition`,
`scope`, input/code/policy hashes, result/evidence refs, deterministic budget
counters, limitations and an error object or null. Errors have a stable code,
message, operand refs and retry class, not just free text.

Keep these dimensions independent:

- Adapter: NOT_IMPLEMENTED / UNAVAILABLE / AVAILABLE_QUALIFIED.
- Execution: NOT_RUN / COMPLETED / ABORTED.
- Geometry: NOT_RUN / PASS / FAIL / NOT_ESTABLISHED.
- Outcome: CANDIDATE_FOUND / NO_IMPROVEMENT_FOUND / REJECTED / BLOCKED / NONE.
- Human and independent acceptance: saved decisions with exact scope; absent
  decisions remain PENDING or NOT_RUN, never a derived boolean PASS.

Proposed errors include `SOURCE_BINDING_MISMATCH`, `POLICY_UNSUPPORTED`,
`PREDECESSOR_NOT_QUALIFIED`, `STALE_SCENE`, `CONTACT_INTENT_UNRESOLVED`,
`SCOPE_LIMIT_REACHED`, `PARALLELISM_NOT_ESTABLISHED`, `BUDGET_EXHAUSTED`,
`AUTHORIZATION_MISSING`, `IDEMPOTENCY_CONFLICT`, `ADAPTER_NOT_IMPLEMENTED` and
`CANDIDATE_GEOMETRY_REJECTED`. A rejected candidate may be a successfully completed
verification operation; transport success is not geometry PASS.

For search, hash canonical request/plan/scene/policy/implementation bindings with
an idempotency key. Same key and same inputs returns the same stored attempt;
same key with changed inputs rejects. Persist checkpoints and consumed candidate
ordinals; do not silently restart or repeat an authorized one-shot run. Cursor
pagination binds the same scene, selection and sort order; stale cursors reject.
Future asynchronous jobs expose job IDs and poll state without launching again.
These are design obligations, not current services.

Every result preserves predecessor, per-source replacements, rejected candidates,
complete cumulative scene, exact source and land partitions, verification
coverage, full-crop and located close-up views with identical frames, added and
removed copper, numerical witnesses and artifact hashes. Content hashes prove
binding, not independent correctness or authorization. No quiet numerical waiver,
cached-result injection or platform-specific identity rewrite is acceptable.

## Qualification before any future implementation can be exposed

1. Bind supported scene/policy families and original widths without C2 constants.
2. Test source/scene/hash mismatch, unknown keys, unsafe paths, missing artifacts,
   stale plans, wrong operation selectors and no implicit execution fallback.
3. Check source coverage and exact selected-span replacement; no old/new route
   union, scope leak, missing branch, introduced contact or narrowed trace.
4. Exercise anchor extension and recursive groups at every finite limit; prove
   blocked fixed obstacles and budget exhaustion preserve the predecessor.
5. Check bundle order, shared offsets, continuous error-bounded alignment and
   copper spacing, both sides and separately qualified transitions. Reject
   crossing, insufficient curve support and sampled-only proof claims.
6. Qualify direct-runner/adapter parity, idempotency, resume after interruption,
   deterministic ordering and retained negative controls. Synthetic parity does
   not establish real-source qualification.
7. Reconstruct saved cumulative source parts and independently audit the claimed
   geometric scope. Keep owner, native, electrical and manufacturing statuses
   separate. T03 changes must not defer violations to T04 or T02.

The suite remains a proposal until separate implementation and qualification.
