# Independent T05 ChatGPT-agent ABI suite

**PROPOSED / NOT_IMPLEMENTED.** This suite owns junction treatment only. It is independent of [T02's rectangle suite](../t02_architecture_notes/T02_AGENT_ABI_PROPOSAL.md), not an alias, extension or renamed phase of it. Read with [common envelope and composition rules](../AGENT_STAGE_COMPOSITION.md), [T05 code map](T05_CODE_STRUCTURE.md) and [implemented spindle contract](T05_CONSTRUCTION_CONTRACT.md). No functions, schemas, registry entries or endpoints are installed. Existing `cam_run`/`cam_verify` availability is unchanged.

Version proposal: `t05-proposed-0.1`. Proposed profile: `land-sized-additive-spindle-proposed`, bound to internal family `land-sized-additive-spindle/1`. Earlier short-taper geometry is a separate family and cannot silently substitute its limits or claims.

| Proposed selector | Required payload beyond common refs | Result | Permitted future effects |
|---|---|---|---|
| `t05_describe` | requested_contract_version | Junction families, predecessor support, limits, proof coverage and adapter availability | None |
| `t05_inspect` | source_ids/finding_ids, page_size, cursor | Original/current trace-land contacts, exact owner/foreign operands, covered skips, source roles and ambiguity witnesses | None |
| `t05_plan` | inspection_ref, selection_ref, predecessor_qualification_ref, bounds_ref, strategy=`bounded_additive_spindle` | Contact-qualified owner/window definitions, ordered route junctions, protected sources, radius schedule and finite attempt budget | None; no closing or patch construction |
| `t05_run` | output_scope_ref; common scene/policy/plan/authorization/idempotency required | Immutable attempts, owner/window/addition WKB refs, selected radius, rejects/KEEP, complete cumulative scene | New local candidate/evidence only |
| `t05_verify` | candidate_ref, verifier_ref, proof_scope_ref | Source/contact reconstruction, exact additions, owner/window/foreign checks and simultaneous final-patch checks | New verification evidence, no repair |
| `t05_compare` | left_ref, right_ref, viewport_ref, evidence_selection_ref | Per-junction added copper, measured limits, exact same-frame full/detail and cumulative views | Bounded derived review only |
| `t05_review` | candidate_ref, verification_ref, decision_filters | Recorded owner/independent decisions and missing evidence, separately from geometry verdicts | None; cannot approve/freeze |

## Source admission and writable domain

Bind actual original positive-area trace/land contacts and their current contact, complete trace source IDs, current nominal width/route lineage, exact native filled-land semantics, aliases, coverage witnesses and current neighbor discovery. Coincident aliases must agree. A shared component/net label is never contact proof or permission for new copper contact. Unsupported contact intent remains unresolved, not a manufactured owner union.

T05 accepts admitted filled circles, rectangles and already constructed inclusive rectangles as land operands. That does not give T05 authority to grow or combine rectangles. T02 need not have run if a separately qualified profile admits original lands; an absent T02 stage must be explicit, as in C01. A post-T02 profile must bind the actual T02 result, not an assumed intermediate. All predecessor parts and nominal route/width metadata are protected.

The writable set contains only optional junction **addition** within source-bound windows. No deletion, source-route replacement, nominal-width rescaling or land resizing is permitted. The implementation may trim optional proposed addition against foreign barriers; it may not recess or trim predecessor copper. Fully covered land operands and fixed bulk contributors are skipped with witnesses. Unsupported branches/mixed components remain explicit dispositions.

## Family parameters and objective

For current family/1 the policy binds radius scales `[1,0.75,0.5,0.25]`, window2 base land radii, buffer quad-segs64, foreign barrier0.02011mm, construction gap0.02010mm, documented floor0.02000mm, area allowance1e-12mm² and positive-growth threshold1e-8mm². Base radius is the smallest half-minimum-bounding-dimension of the admitted current lands. Changing parameters requires a separately versioned and qualified family, not free agent overrides.

Select the first passing positive patch in declared order, not a purported global maximum. The T04 1.5 nominal-width ceiling is not the T05 local spindle-flare bound. A no-visible-addition or rejected attempt is KEEP with reasons, distinct from positive growth and unresolved admission. The plan includes finite route/land/foreign-object/attempt/time/output budgets; the four-radius schedule alone does not bound arbitrarily large input scenes.

## Verification and future exposure gates

Rebuild source contacts and current owner/window; reconstruct patch bytes directly from family/version/selected radius; verify valid connected candidate, owner preservation, exact delta, containment, and addition-to-foreign finite-surface gaps. Full exact owner coverage is the sole supported primitive-internal exception; partial coverage and component/net names are not exemptions. Check each patch against all other final additions, including later ones, before cumulative assembly.

Retain every source, owner/window/patch hash, all tried radii, rejection operands and reasons, full and located detail images, actual additions and zero removals, final checks and stored decisions. Do not infer neck-width, electrical intent, impedance, mechanical or manufacturing qualification from connected polygon geometry or tessellation alone.

Negative controls before agent exposure: false original contact, disconnected owner, conflicting alias, uncovered partial primitive incorrectly exempted, window leak, altered predecessor land/width/route, hidden missing obstacle, patch-patch conflict, stale plan, unbounded selection, unsafe paths, policy/family drift and idempotency conflict. Qualify deterministic direct-runner/adapter parity and independently challenge proof scope before claiming an exposed production execution adapter.

Proposed errors: `CONTACT_INTENT_UNRESOLVED`, `SOURCE_CONTACT_NOT_ESTABLISHED`, `OWNER_DISCONNECTED`, `LAND_ALIAS_CONFLICT`, `JUNCTION_FAMILY_UNSUPPORTED`, `WINDOW_SCOPE_EXCEEDED`, `FOREIGN_CLEARANCE_FAILED`, `PATCH_BATCH_CONFLICT`, `PREDECESSOR_CHANGED`, `BUDGET_EXHAUSTED`, `IDEMPOTENCY_CONFLICT`, `ADAPTER_NOT_IMPLEMENTED`.

The pure functions `prepare_spindle_context`, `fit_spindle_blend`, `verify_spindle_batch`, `assemble_spindle_scene` already form T05's internal module API. They are not these agent operations. Source admission and I/O still live in crop adapters; a generic admitted-scene adapter is required before arbitrary new-sample/stage-order execution. No T02 implementation or accepted result changes are authorized by this suite design.
