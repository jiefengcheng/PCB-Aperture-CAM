# T02 Agent ABI mapping — deferred

This note maps the accepted T02 capability to the existing seven-operation CAM Agent ABI vocabulary. It specifies future behavior only. It does not add a T02 profile, adapter, schema, wrapper, endpoint, test suite, or module split.

## Current boundary

The T01-oriented v0.1 implementation exists under src/agent_abi and declares cam_describe, cam_inspect, cam_plan, cam_run, cam_verify, cam_compare and cam_review. Its current registry and operations are not a T02 interface. cam_run and cam_verify are explicitly unavailable; reading a saved T02 audit would not make either operation an execution or verification adapter.

The T01 implementation map at docs/crop_dynamic_tasks/T01_CODE_STRUCTURE.md is the architectural reference. The uncommitted docs/agent_abi directory was read as requested for this mapping and was left unchanged. Its local snapshot is bound to an earlier worktree and must not be represented as the current T02 implementation or acceptance.

## Future operation mapping

| Operation | Future T02 role | Boundary |
|---|---|---|
| cam_describe | Describe the supported T02 rectangle and covered-circle treatment, inputs, policy, effects, limitations and open trace obligations. | Read-only capability description. Do not imply manufacturing approval or blanket permission. |
| cam_inspect | Retrieve one bound T02 result, target disposition, limiting constraints, geometry witness, covered-circle selection or trace-ledger entry. | Read-only retrieval from saved evidence. It must identify missing local artifacts. |
| cam_plan | Validate source, accepted T01 decision, inventory, policy compatibility, target scope and any required authorization before a proposed run. | No geometry construction, filesystem writes or permission inference. |
| cam_compare | Compare compatible T02 results and expose changed target decisions, measurement domains, policies and unresolved-ledger continuity. | Do not claim equivalence across different source, T01 scene, policy, target set or metric bindings. |
| cam_review | Return the exact result-bound owner acceptance, its scope and its retained limitations. | A missing bundle cannot be replaced with an image-based proxy or a fresh-verification claim. |
| cam_run | Eventually invoke an explicitly authorized deterministic runner. | Remains unavailable. The current top-level runner is not an import-safe ABI adapter. |
| cam_verify | Eventually execute a separately authorized verification operation against present bound artifacts. | Remains unavailable. A stored audit can be inspected, not rerun through this operation. |

## Required bindings and status dimensions

A future T02 request and result need distinct fields for the ORG source hash, registered crop, accepted T01 decision and scene/policy/selection hashes, inventory and target-set hashes, T02 policy version and hash, generating constructor and runner hashes, environment and geometry settings, result and audit hashes, determinism receipt, owner decision, and trace-work ledger hash. Result version, policy version, generating code revision, acceptance commit and local artifact availability are different identities.

Do not compress interaction evidence into one clearance_pass value. Preserve the metric and context: current side-by-side checks use finite-width trace-copper surface distances; the corner topology guard is separate; baseline gaps, attachment extensions and corner obligations remain separate ledger classes. No centerline field or derived centerline pass belongs to the current T02 policy-v15 path. Any future policy change must bind a new metric explicitly.

Keep feature selection distinct from effective copper. The embedded-circle pass may change a latent contained round selection while adding zero composed copper. An agent response must report both facts rather than describing every latent selection as visible copper growth.

Keep status dimensions independent: T02 owner acceptance, geometry/audit result, electrical intent, EDIT equivalence, native export, manufacturing status and future trace obligations. For v69, the owner acceptance is recorded separately from the generated-time PENDING_USER fields; native export is NOT_RUN; electrical, manufacturing and EDIT equivalence remain NOT_ESTABLISHED; the trace ledger remains open.

## Deferred qualification outline

When an implementation is separately authorized, test at least: wrong ORG or accepted-T01 scene; mismatched result/policy/code bindings; ambiguous or duplicate source identity; wrong or missing geometry metric; side-versus-corner classification; attachment-port scope leakage; physical-contact evidence versus electrical intent; missing local output bundle; stale or incomplete audit; latent covered-circle selection versus effective copper; exact owner-review scope; and preservation of all 255 open trace-clearance records and the separate 120 overlap witnesses.

Only after run and verification adapters are authorized should their direct-runner parity, isolated execution, failure behavior, artifact publication and current-state requirements be implemented and tested. Passing parity would establish adapter compatibility, not independent mathematical correctness.

## Status

ABI_IMPLEMENTATION_DEFERRED. The current work is documentation only. No T02 ABI capability should be advertised as available based on the local runner, saved audit or review page.
