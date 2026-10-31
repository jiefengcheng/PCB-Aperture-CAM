# Modular stage composition and common proposed agent contract

**Design contract; not a live ABI, planner or arbitrary-order executor.** T01 circle growth, T03 route accommodation, T04 nominal trace-width growth, T02 rectangle growth and T05 additive junction treatment own different writable domains. A stage order is explicit lineage, not a universal baked-in assumption. Current qualified regression order is T01 → T03(no route change) → T04 → T02 → T05. Other orders must satisfy each adapter's declared preconditions and obtain applicable authority. Existing frozen results are never experimental inputs to mutate.

## Ownership and handoffs

| Stage | May change | Must preserve |
|---|---|---|
| T01 | Admitted circle contribution under its versioned shape/priority policy | Original cores, protected contributions, recorded source contacts |
| T03 | Admitted trace route spans with bounded cut ports/groups | Fixed lands, original widths, protected connections/order/parallelism where required |
| T04 | Nominal width of complete admitted trace routes | Routes, lands, unrelated copper; one shared factor per parallel cohort |
| T02 | Admitted rectangle dimensions and separately admitted inclusive rectangular fills | Routes/widths and unrelated contributions; source-qualified attachments and clearances |
| T05 | Optional local junction addition inside admitted windows | All predecessor contributions, nominal route/width metadata and unrelated copper |

T04 scales do not define T05 local spindle flare limits. T05 does not enlarge or simplify rectangles. T02 may inspect surrounding traces/lands without acquiring permission to change their routes, widths or junctions. Inclusive T02 fills remain legitimate T02 scope and are not moved to T05.

## Proposed wire contract shared by T04/T05 designs

All requests are plain closed JSON objects with required keys: `abi_version`, `request_id`, `operation`, `profile_id`, `scene_ref`, `policy_ref`, `plan_ref`, `authorization_ref`, `idempotency_key`, `payload`. Unknown fields reject. Operation-specific payloads are closed. Unused references are explicitly null. References contain exactly `artifact_id` and lowercase64-hex `sha256`, resolved through a trusted local registry, not arbitrary paths, shell commands, imports, URLs or caller-supplied checkers.

A scene binds source board/input hashes, layer/units/polarity, exact viewport/frame, original and current source-ID contribution maps, effective complete copper, actual route/width/attachment metadata, ordered stage lineage, policy/implementation/kernel versions, coverage dispositions and acceptance/qualification evidence. Source occurrence/byte-span identities survive display renumbering. All numeric fields are finite, with explicit units; no guessed coordinate inversions or normalization of identity failures.

A plan binds the exact scene/policy/inspection/selection/bounds and implementation hashes, writable/protected sets, strategy, objective, deterministic order, object/evaluation/time/output budgets and required proof coverage. Caller parameters may narrow, never broaden, authorized bounds. The versioned profile declares supported input families and proof obligations; unsupported scene kinds stop before construction.

Operation rules:

- `describe`: refs/idempotency null, profile optionally null, payload contains requested contract version only.
- `inspect`: scene/policy required; payload contains explicit source/finding IDs, finite page size and cursor (nullable); other refs/idempotency null. Empty selection never means all objects.
- `plan`: scene/policy required; payload exactly inspection_ref, selection_ref, predecessor_qualification_ref, bounds_ref, strategy. Other refs/idempotency null. Planning constructs no copper.
- `run`: scene/policy/plan/authorization/idempotency required; payload exactly output_scope_ref. The bound plan supplies numerical settings. A fresh project-local immutable attempt is the only permitted construction effect.
- `verify`: scene/policy/plan required; payload exactly candidate_ref, verifier_ref, proof_scope_ref. Verification job idempotency is required; authorization follows the host's explicitly declared verification-execution policy. Never searches, repairs or promotes.
- `compare`: scene/policy required; payload exactly left_ref, right_ref, viewport_ref, evidence_selection_ref; other refs/idempotency null. Compatibility is checked before equivalence statements; bounded derived visuals are permitted.
- `review`: scene/policy required; payload exactly candidate_ref, verification_ref (nullable), decision_filters; other refs/idempotency null. Reads actual saved decisions without creating one.

Each future response has request ID, operation, immutable input refs, transport/job status, result refs, error (nullable), and separate construction/check/coverage/owner/independent/native/electrical/manufacturing dimensions. PASS, FAIL, NOT_ESTABLISHED, NOT_RUN, KEEP and NOT_APPLICABLE are distinct. A successful verification call can return geometric FAIL. Owner acceptance is never synthesized from local checks.

Canonical request + scene/policy/plan/implementation bindings and idempotency key identify an attempt. Identical key/bindings reuse the same saved attempt; changed bindings conflict. Async jobs expose state without relaunching. Resume retains checkpoints, original candidate ordinals, rejects and consumed budgets; cached hints need fresh geometry checks. Stale cursors/plans reject. Missing artifacts, unsafe resolution, unsupported profile, exceeded budget and inconsistent identities fail closed.

## Combining stages later

A coordinator must obtain each module's actual support matrix, inspect one exact current scene, bind a legal order and explicit NOT_APPLICABLE stages, and pass the preceding candidate plus verification evidence to the next stage. Qualification and owner decisions remain separate. Before starting a dependent stage, reject missing verification, stale scene hashes, unsupported predecessor family, source/coverage gaps or conflicting writable/protected sets. Failed candidates retain the original scene and cannot leak into later stages.

Final verification composes source replacements by identity plus admitted additions. Never union old and replacement routes together; never merge overlapping accepted crops by raster/polygon union without reconciling their source maps. Preserve both cumulative views and stage-local deltas at identical coordinates. Reordering stages requires new regression evidence, not editing the recorded history of C01/C02/C03.

No suite has `approve`, `freeze`, `commit`, `push` or automatic next-stage authority. No runtime registration, ABI functions, schemas or service endpoints are created by these specifications. Future transport/module qualification remains explicit; local Python runners are not yet agent adapters.

## Example request shape (non-executable placeholders)

```json
{
  "abi_version": "t04-proposed-0.1",
  "request_id": "width-plan-example",
  "operation": "t04_plan",
  "profile_id": "complete-source-uniform-width-proposed",
  "scene_ref": {"artifact_id": "current-scene", "sha256": "<64-lowercase-hex>"},
  "policy_ref": {"artifact_id": "width-policy", "sha256": "<64-lowercase-hex>"},
  "plan_ref": null,
  "authorization_ref": null,
  "idempotency_key": null,
  "payload": {
    "inspection_ref": {"artifact_id": "width-inspection", "sha256": "<64-lowercase-hex>"},
    "selection_ref": {"artifact_id": "complete-route-groups", "sha256": "<64-lowercase-hex>"},
    "predecessor_qualification_ref": {"artifact_id": "predecessor-check", "sha256": "<64-lowercase-hex>"},
    "bounds_ref": {"artifact_id": "authorized-bounds", "sha256": "<64-lowercase-hex>"},
    "strategy": "collective_uniform_width"
  }
}
```

For T05 the same envelope uses `t05-proposed-0.1`, `t05_plan`, the spindle profile, its own policy/inspection/selection references and strategy `bounded_additive_spindle`. It never reuses a T02 plan as a T05 plan. Hash placeholders are explanatory, not accepted inputs or authority.

An inspect payload has exactly `source_ids`, `finding_ids`, `page_size`, `cursor`; both ID arrays are required, at least one selection ID must be present, page_size is a bounded positive integer and cursor is nullable. A describe payload has exactly `requested_contract_version`. A review filter is a closed object with bounded decision types and page size/cursor; its eventual concrete enum and maximum values must be versioned before exposure. These proposed rules are not claims of an installed request validator.
