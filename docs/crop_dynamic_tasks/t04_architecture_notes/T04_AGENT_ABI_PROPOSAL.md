# T04 ChatGPT-agent ABI suite

**PROPOSED / NOT_IMPLEMENTED.** Standalone T04 width-optimization contract; not registered tools or callable ABI functions. Read with [common envelope and composition rules](../AGENT_STAGE_COMPOSITION.md) and [actual module map](README.md). Existing `cam_run` and `cam_verify` remain unavailable. No automatic execution is implied by a plan.

Version proposal: `t04-proposed-0.1`. Proposed profile: `complete-source-uniform-width-proposed`, bound to an explicitly qualified source-offset family and surface-check contract. This name is not a live registry ID.

| Proposed selector | Required payload beyond common refs | Result | Permitted future effects |
|---|---|---|---|
| `t04_describe` | requested_contract_version | Source families, supported predecessors, scale/search limits, actual adapter availability | None |
| `t04_inspect` | source_ids/finding_ids, page_size, cursor | Complete routes, widths, cohort/singleton membership, exact fixed/covered/bulk dispositions, blockers and remote constraints | None |
| `t04_plan` | inspection_ref, selection_ref, predecessor_qualification_ref, bounds_ref, strategy=`collective_uniform_width` | Ordered source-disjoint groups; common-factor objective, protected operands, finite solver bounds and required checks | None; no geometry |
| `t04_run` | output_scope_ref; common scene/policy/plan/authorization/idempotency refs required | Immutable search attempt, scale vector, per-source nominal parts, envelopes, collective deltas, cumulative scene, KEEP/reject reasons | New local candidate/evidence only |
| `t04_verify` | candidate_ref, verifier_ref, proof_scope_ref | Fresh reconstruction from source/route/scale bindings; simultaneous nominal/envelope checks; fixed-land identity and proof limits | New verification evidence, no search |
| `t04_compare` | left_ref, right_ref, viewport_ref, evidence_selection_ref | Width/factor differences by source/cohort, actual copper delta and same-frame full/detail views | Bounded derived review only |
| `t04_review` | candidate_ref, verification_ref, decision_filters | Actual saved receipts and separate owner/independent decisions | None; no promotion |

## Module-specific plan and policy

The policy binds original widths, complete route semantics, constructor family, scale1..1.5, scalar tolerance/iteration/evaluation/time budgets, clearance target/floor/attachment-port interpretation, checking-envelope error/tessellation and every skip rule. Exact current constants are evidence for the present profile, not universal defaults for new samples.

The plan records every source occurrence in exactly one role: admitted complete trace contribution, fully covered skip, fixed bulk contributor, other protected copper, or unresolved/unsupported. Unresolved coverage is not silently counted as successful processing. Parallel membership needs geometric/source evidence; shared physical-component or net labels cannot establish eligibility or a clearance exemption.

Each route belongs to exactly one group, including singleton groups. Each group's factor applies uniformly across every full member route, including partially overlapping segments which are admitted at the same prior scale. Fully covered strokes/shapes are skipped. Covered and overlapping are distinct; never grow hidden background caps independently. Display each collective unioned expansion once, preserving per-source evidence separately.

T04 may optimize widths, never narrow, displace a route, enlarge a land or insert a spindle. A candidate that requires another stage's writable domain is rejected or reported as an unresolved dependency. Existing unchanged gaps are inherited relationships, not newly introduced defects to repair automatically.

## Verification and qualifications

Require exact route/source/scale bindings; original source cores and all protected contributions retained; uniform nominal width by route; shared factors by cohort; every source represented exactly once; final simultaneous finite-copper checks on both nominal parts and conservative envelopes; original attachment scope; and same-frame cumulative/delta outputs. A centerline fit cannot establish conductor clearance.

Stored rejected upper factors must be freshly checked against the current complete scene. Maximality claims state their coordinate-wise model scope and numerical tolerance. Fixed-scale replay proves reconstruction only, not a fresh optimum. Deterministic ordering is not proof of global optimality.

Candidate negatives before exposure: missing remote chain, branched/mixed-width unsupported route, duplicate source/group, false covered/bulk classification, hidden-stroke protrusion, changed fixed land, one independently widened cohort member, source/scene drift, narrowed route, unsafe nominal/envelope gap, stale accepted hint, budget exhaustion and interrupted-resume idempotency. Require direct-runner/adapter parity and fresh source replay on real samples, separately from synthetic tests.

Proposed errors include `ROUTE_NOT_COMPLETE`, `TRACE_GROUP_PARTITION_INVALID`, `PROTECTED_SOURCE_SELECTED`, `WIDTH_FAMILY_UNSUPPORTED`, `SCALE_OUT_OF_BOUNDS`, `FINITE_SURFACE_CLEARANCE_FAILED`, `SOURCE_BINDING_MISMATCH`, `PREDECESSOR_NOT_QUALIFIED`, `BUDGET_EXHAUSTED`, `IDEMPOTENCY_CONFLICT` and `ADAPTER_NOT_IMPLEMENTED`.

Current pure functions are implemented. The filesystem adapter remains qualified only for the prepared no-route-change trace-first branch. General T03-modified routes, arbitrary predecessor stages, new board families and runtime agent dispatch remain qualification gaps. This specification implements no ABI functions.
