# Codex handoff — Complete the bounded V1.5 technical validation path

**Document ID:** PCB-CAM-V15-COMPLETION-001  
**Date:** 2026-10-14  
**Status:** Proposed task authorization; active when the user sends/adopts this handoff in the isolated PCB project.  
**Owner:** Codex, sole coordinator.  
**Purpose:** Continue from the qualified FC-1 oracle through necessary implementation, integration, negative tests, and a truthful V1.5 technical decision. This is not another proposal-only task.

## 1. Outcome and authority

Implement the missing path from the actual public Gerber bytes to independently checked composed geometry, then exercise the supported validation checks on the already selected public PCB assets. Retain the synthetic V1 as a regression baseline.

This task authorizes the project-local parser/adapter/compositor changes, oracle extensions strictly required by those changes, tests, reproducible runs, minimal reference/intent manifests, and documentation needed for that outcome. It includes FC-2A to the extent its actual repository definition falls within this V1.5 validation scope. Read that definition; do not invent it from the label.

**FC-1, FC-2A, and other necessary implementation subtasks are internal checkpoints, not automatic requests for another human approval.** Record their evidence and continue while in scope. Do not conclude this task merely because a plan, oracle, parser unit test, review packet, or commit is complete.

Reconcile this authorization in repository-local AGENTS.md and the decision log. Explicitly supersede earlier *proposal-only*, *stop before parser implementation*, and *stop after FC-1* restrictions for this task only. Do not overwrite the charter, frozen contracts, or historical decisions. Preserve source immutability, operating-system permissions, other-lane isolation, and the stop before V2/V3. If a restriction is outside these explicitly superseded ones, respect it and identify a genuine conflict rather than bypassing it.

Codex remains the only coordinator. Cursor is a reviewer through a verified direct channel only. No human relay, global configuration edits, remote publication, or new service integration is authorized.

## 2. Read the actual local record, then continue

Read the active AGENTS.md, adopted charter, ROADMAP.md, V1_5_DECISION.md, FC1_DECISION.md, FC1_ORACLE_DERIVATION.md, the actual FC-2A specification if present, current acceptance documents, source/asset manifests, and relevant implementation/tests. These are reported local document names; locate their actual paths inside this checkout.

Verify and preserve these reported reference commits without resetting the current checkout:

- V1: `36eab151a0bf00ea57eef09f1dc425c4b5603e50` — synthetic coupon validation.
- V1.5 qualification: `cb0377c` — public asset inventory/replay and feature gaps.
- FC-1: `ca12323` — qualified oracle for one selected Ucamco example.

The supplied FC-1 summary reports eight oracle tests, four bootstrap tests, and 274 prior evidence files unchanged. Verify the actual manifests and tests; counts alone are not an integrity check. Keep new evidence in a new run directory, never overwrite prior run artifacts.

The author of this handoff has the reported summaries and original charter/handoff, not the contents of the local FC-1/FC-2A documents or the current implementation. Resolve those details locally before acting. In particular, **do not assume the selected FC-1 example is one of the two failing aperture-block examples**.

The authoritative synthetic candidate remains P1 X=20.05 mm, before X=20.35 mm, fixed aperture X=20.00 mm. Exclude the user's discarded manual X=20.00 mm candidate from all acceptance inputs and expected results.

## 3. Freeze one finite completion matrix before implementation

Update the existing acceptance/decision record rather than inventing another project version. Preserve the fact that V1.5 *asset qualification* was completed even though realistic numerical validation was not established. This task extends the evidence; it does not rewrite that history.

Record these fields for every target:

`source commit/hash | file/layer | feature actually encountered | check | independent reference | required or optional | current blocker | completion evidence`

The matrix must distinguish:

1. Frozen synthetic regression obligations.
2. FC-1 oracle and parser-to-oracle agreement obligations.
3. Public-board composed-geometry/replay obligations.
4. Operation-specific or electrical checks and their reference/intent prerequisites.
5. Ucamco compatibility controls outside the selected boards' required feature set.
6. External review and manufacturing acceptance, reported separately.

Recover all previously required V1.5 obligations from the repository. Do not silently reduce them to obtain PASS. Use the already pinned GlowStitch selection as the first complete public-board target, then complete any other required targets, including the HALPI2 selection where the existing contract requires it. A first-board result is a partial result if the frozen required set is larger.

The intended technical endpoint is evidence for the complete declared files/layers, not merely a convenient crop. A local operation check can have a bounded region, but include its relevant connection/obstacle context and do not claim whole-board or multilayer checking from a cropped result.

Do not require general Gerber conformance or factory signoff to complete a narrower, explicitly declared technical profile. Conversely, unsupported semantics inside a required input block that input's technical PASS. Optional unsupported examples stay in the report and rejection tests; they do not become supported.

## 4. Establish the actual dependency and implement it

Identify whether each current failure occurs in syntax reading, command/state interpretation, primitive expansion, image composition, geometric comparison, source-intent association, or the acceptance policy. Keep these stages distinct.

Use the already qualified FC-1 reference to test the production parsing/composition path from raw Gerber bytes. Do not feed its expected polygons into the implementation under test or special-case a sample filename, checksum, or expected result.

Prefer a small, tested extension or adapter around the existing pinned reader over a whole parser rewrite. A project-local dependency change is permitted when needed, but document and pin the version and preserve the old regression path. Do not upgrade KiCad or all dependencies just to restart the project.

Support the semantics actually needed by the frozen target inputs, using the applicable pinned specification. Preserve operation order, transformations, polarity, geometry, units, and layer roles through the supported path. For numerical approximations, establish a defensible error budget before accepting results. Do not loosen tolerances to hide a mismatch.

Make the path produce inspectable intermediate diagnostics so a failure can be localized, but judge the final composed geometry rather than merely the count of expanded primitives.

If aperture-block support is required by a selected target or an existing mandatory acceptance control, implement and test it. If neither selected PCB uses it and the examples are optional compatibility probes, record that dependency result and keep them explicitly unsupported without making them a prerequisite for all public-board progress. FC-1's finished oracle should be reused, not discarded; do not expand its scope indefinitely before attempting the implementation it was intended to test.

Create small variations of the qualified example sufficient to rule out hard-coding and exercise the changed semantics. Additional oracle work is justified by a named required behavior, not by a desire to certify every possible Gerber construct.

## 5. Apply the result to the public boards

Use existing pinned checkouts and derived copies. No new repository acquisition or pcb_Z integration is needed for this task. Reproduce exports with the available pinned KiCad build and capture exact commands, versions, stdout/stderr, input/output hashes, and process outcomes.

For each required board, compose the declared copper, aperture/mask, and outline files. Check layer interpretation and coordinate mapping before measuring anything. Do not independently best-fit copper and mask or silently repair invalid input geometry.

Perform a no-edit baseline/replay comparison of final geometry. Primitive replay is useful evidence but is not sufficient by itself. Combine the qualified semantics tests with independent source anchors/reference measurements and, where needed, an independent implementation comparison. Describe what each reference establishes. Two outputs from the same implementation do not prove that implementation correct; two wrappers around the same geometry engine are not independent engines.

Use shape/location differences, boundaries, holes/components, and selected meaningful measurements as appropriate. Area or bounding-box equality alone is insufficient. Keep raster/render checks, vector checks, and numerical clearance/contact checks distinguishable; visual agreement alone is not a precision acceptance test.

## 6. Qualify intent without inventing manufacturing rules

Separate three kinds of reference:

- **Format reference:** the pinned Gerber specification and qualified analytic fixture(s).
- **Source-design reference:** immutable native source objects, supplied nets, schematic/netlist where available, layer roles, and declared export mapping.
- **Process reference:** actual customer/factory requirements; not supplied by a successful public repository checkout.

The source native design can provide nominal pad locations and net assignments for a technical test. Check that extraction/mapping explicitly; do not reject available design intent merely because a factory manual is absent. It is not factory-approved process intent.

Do not derive expected electrical connections from the candidate's own reconstructed connected components. Match independently supplied terminals/nets to physical exported copper. Declare the actual layer span; require drill/plating evidence for a cross-layer claim.

The first public-board run is read-only. Appropriate technical questions include: does no-edit export preserve the selected geometry, mask/opening geometry, exposed-copper shape and terminal relationships? Do deliberately corrupted copies violate those preservation expectations?

Do not impose the synthetic coupon's smaller-opening/covered-rim rule on every public pad. Measure or preserve the nominal source relation where that is the declared technical contract. Any newly supplied experimental tolerance or assumption must be labeled as such and recorded before candidate evaluation. Do not invent registration allowance, copper clearance, or assembly requirements and describe them as factory rules.

Separate measured clearance from clearance acceptance. Without a justified threshold, report the measurement and mark process compliance unestablished. Existing source violations must remain visible; a preservation test can show no regression without claiming the original design was compliant.

Where a required scoped connection check lacks complete source intent, attempt to qualify it from existing native assets within scope. If it genuinely cannot be qualified, identify the exact missing datum and retain NOT_ESTABLISHED for that obligation. Never replace an unknown net with a guess to obtain PASS.

## 7. Test false acceptance and regressions

Keep every frozen V1, bootstrap, and FC-1 test. Add tests through the actual reader/compositor for each new supported behavior.

For a selected public-board validation slice, create disposable derived faults with explicit expected failing checks: moved mask, broken required same-layer connection, new copper bridge, protected geometry changed, polarity/order error relevant to the implemented semantics, and unsupported or malformed input. These are validator challenge fixtures, not V2 repair implementation and not alleged faults in upstream designs.

Include equivalent encodings or controlled geometric variations for the new semantics so the implementation cannot pass only one golden file. Derive them without using the implementation under test to invent its own expected answer. Exclude transformation cases that have no valid semantics-preserving expectation.

A negative test must fail for its intended reason, not simply because every input is rejected. Pair it with a positive control. Keep 'test harness PASS for expected UNSUPPORTED' separate from 'sample geometry correctly interpreted'. Do not report 11/11 interpreted when some tests merely confirmed refusal.

## 8. Reporting and decision

Add or reuse one documented command that runs the new checks and emits a machine-readable report and a short readable decision. The command must bind its outputs to the exact source revisions, required-check manifest, policies, references, tolerances and tool versions. It must not reuse stale successful output after a failed subprocess.

Use existing result vocabulary and error conventions. A technical profile is PASS only when all of its required obligations actually pass and all required inputs are accounted for. A required FAIL or NOT_ESTABLISHED prevents that profile's PASS. Report optional compatibility gaps separately. Do not change the required set after seeing results except through an explicit, versioned, authorized scope revision.

Return a compact table with at least:

- Frozen V1 regression.
- FC-1 oracle regression.
- Production reader/compositor agreement with the selected oracle.
- Public-board composed geometry and no-edit preservation per required board/layer.
- Scoped exposure/connection/clearance/scope checks, with source and meaning of each requirement.
- Deliberate-fault detection and unsupported-feature handling.
- Original source and historical evidence integrity.
- Cursor review status.
- Factory/manufacturing acceptance status.

Report the exact new capability, not just total test counts. Suggested plain-language outcome: 'The tool now reads these specified real board layers, reconstructs their geometry under the declared support profile, and detects these defined errors; these other checks remain unsupported.'

## 9. Coordination and stopping

Do not pause at normal internal milestones that this task authorizes. Commit useful checkpoints and continue to the end-to-end acceptance run. Source/code/permission conflicts outside this authorization remain legitimate blockers.

Do not wait indefinitely for Cursor. If no verified direct channel exists, retain NOT_RUN / CHANNEL_UNAVAILABLE, prepare a frozen review packet, and continue local technical implementation/testing. This authorization removes Cursor availability as a prerequisite for this technical task, not as a prerequisite for claiming independent Cursor review.

Stop substantive work only when the declared technical endpoint is evidenced; when a reproducible blocker cannot be resolved within the authorized scope; when the next needed action changes acceptance semantics, external permissions, or product scope; or when execution/resource limits require pausing. In the latter cases, keep the task incomplete and provide the exact reproduction and next action. Do not fabricate background continuation or a PASS.

**Still excluded:** V2 automated board repair, V3 AI planning, V4 manufacturing deployment, pcb_Z merger/qualification, whole-schema migration, broad new data collection, global tooling changes, changes to other research lanes, and remote writes/uploads.

## 10. Why this matters

This task advances the charter's independent exported-result validation capability: a CAM system cannot safely modify a shape it cannot reliably interpret and check. It does not replace operation-context work or manufacturer approval. Completing the declared realistic technical slice should make the next operation-model/execution decision evidence-based, instead of keeping the project in a sequence of preparatory reports.

## References and evidence boundaries

The repository's adopted contracts and observed results are the authority for project claims. The latest FC-1 state above is user-reported and must be verified locally. No local Codex repository was accessed or modified in preparing this handoff.

Public documentation consulted on 2026-10-14, for supporting terminology and workflow guidance rather than as substitutes for local evidence:

- Ucamco, Gerber Format and official downloads: https://www.ucamco.com/en/gerber and https://www.ucamco.com/en/gerber/downloads
- Ucamco, Gerber Layer Format Specification (the downloads page lists revision 2026.05). Sections on graphical objects/polarity, file processing, and block apertures distinguish command parsing, ordered object generation and final image composition. Retain the project's applicable pinned specification instead of silently migrating it.
- OpenAI, Custom instructions with AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- OpenAI, Prompting: https://developers.openai.com/codex/prompting
- OpenAI, Using Goals in Codex: https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex

No new Codex feature, global setting, or automatic background runtime is required by this handoff.
