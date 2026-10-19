# Decision log

Entries distinguish user authorization, recorded evidence and proposals. They do not independently grant permission. Codex is sole coordinator; no manufacturing approval is recorded.

| ID / date | Decision owner and authorization | Decision / evidence | Status and stop |
|---|---|---|---|
| D-001 / 2026-10-14 | User-authorized isolated V1; Codex technical decision | Freeze V1 `36eab151a0bf00ea57eef09f1dc425c4b5603e50`; recorded coupon technical PASS with synthetic rules, limited Gerber subset, 13 corruption controls and eight-test receipt | Historical technical result; no manufacturing signoff; Cursor NOT_RUN |
| D-002 / 2026-10-14 | User public-reference roadmap amendment; Codex qualification decision | Freeze V1.5 `cb0377cbdcdac25ee9b89c01aca6901b3ae48d0d`; source custody and no-edit CLI compatibility established, realistic validation NOT_ESTABLISHED | Historical qualification closure; no V2/V3 |
| D-003 / 2026-10-14 | User explicitly requested private GitHub repository under `jiefengcheng` | Existing project history published to `jiefengcheng/PCB-Aperture-CAM`; generated evidence and external checkouts stayed Git-ignored/local | Past upload authorization fulfilled; this documentation task does not initiate another push |
| D-004 / 2026-10-14 | Repository owner in current Codex conversation: adopt supplied charter as proposed strategic reference, reconcile/verify, commit documentation and stop | Integrate `PCB-CAM-CHARTER-001` supplied v1.0 (2026-10-14), with aligned copy v1.0-alignment.1; preserve both supplied Markdown documents; add operational pointer, evidence audit and requirements traceability | Documentation integration authorized; reconciliations proposed for approval, no new implementation authority |
| D-005 / 2026-10-14 | Codex read-only audit within D-004 | Frozen source/schema/asset checks, retained native/public/export hashes, schema, negative receipts, test-count/log review support the bounded historical claims; fresh four bootstrap tests pass | Audit consistency PASS; no fresh geometry/parser/full-suite rerun and no independent review |
| D-006 / 2026-10-14 | Codex reconciliation proposal, awaiting user decision | C-01 authority separation; C-02 frozen overall status enum; C-03 unverified GUI claim; C-04 qualification/round-trip limits; C-05 strategic gate namespace; C-06 unverified partner requirements | See [CHARTER_INTEGRATION.md](CHARTER_INTEGRATION.md); original charter preserved, no frozen result changed |
| D-007 / 2026-10-14 | Codex next-gate recommendation, awaiting explicit user approval | FC-1: independent oracle and support decision for one already acquired non-nested aperture-block example; alternative MC-1 passive operation-case record | PROPOSED / NOT_RUN. No parser implementation, executor, V2/V3, new downloads or partner contact authorized |
| D-008 / 2026-10-14 | Codex tool-inventory observation | No authenticated direct Cursor agent/review tool found. Governance packet prepared under `out/charter_adoption/` | Review NOT_RUN / CHANNEL_UNAVAILABLE; no human relay or implied approval |

Evidence audit: [CHARTER_EVIDENCE_AUDIT.md](CHARTER_EVIDENCE_AUDIT.md). Requirements map: [TRACEABILITY.md](TRACEABILITY.md). Approval target: [NEXT_GATE_PROPOSAL.md](NEXT_GATE_PROPOSAL.md).

User approval of a future gate must be recorded as a new entry with its exact scope, allowed mutations, acceptance obligations and stop condition. Do not rewrite an old entry to imply earlier authorization. The charter describes eventual product success, not an active implementation mandate.


## Subsequent authorization and FC-1 closure

- **D-009 / 2026-10-14 — user approval:** “Sure. go ahead” approves the preceding reconciliations and recommended FC-1 only. Charter version 1.0-alignment.1 is adopted as the strategic reference; operational isolation and frozen acceptance remain intact. Allowed mutations: new mathematical oracle/reference modules, tests/expected ledger, new `out/fc1/` evidence and documentation. No Gerber parser implementation, dependency change, MC-1, V2/V3, additional download or partner outreach. Stop after the oracle/support decision. Earlier proposal entries remain historical.
- **D-010 / 2026-10-14 — Codex FC-1 decision:** one-file oracle qualified with analytic/polygon checks and explicit raster limits; seven geometry faults, two separately labeled synthetic scene probes and five fail-closed scope controls recorded. Parser and realistic validation remain NOT_ESTABLISHED. Fresh existing-parser failure preserved; Cursor review NOT_RUN / CHANNEL_UNAVAILABLE. See `FC1_DECISION.md` and `FC1_ORACLE_DERIVATION.md`.
- **D-011 / 2026-10-14 — proposal only:** possible FC-2A non-nested block-composition route must first demonstrate maintained-parser viability and a bounded independent acceptance contract. No alternate parser evaluated/installed and no route implementation approved. Do not infer authorization from the FC-1 PASS.


- **D-012 / 2026-10-14 — user V1.5 completion authorization:** supplied completion handoff is adopted as the bounded implementation authority. Earlier parser/FC-1/proposal-only stops are superseded for this task only. Codex alone may implement the missing real-Gerber path and qualification through the finite matrix; no intermediate approval pauses. Preserve historical contracts/receipts, defer pcb_Z, and stop before V2/V3 or external actions. Cursor unavailable review is NOT_RUN and does not block local work.

- **D-013 / 2026-10-14 — completion technical decision:** raw reader/compositor agrees with FC-1; both full nine-layer public selections pass composed geometry/replay, all native pad anchors, nominal exposure, source physical continuity and six declared fault controls per board. HALPI2 scoped source-justified named-net checks pass. 31 full-suite tests pass; 289 prior receipts unchanged. Overall required V1.5 electrical validation remains NOT_ESTABLISHED: GlowStitch has only unnamed net 0 and no supplied schematic/net map. See `V1_5_COMPLETION_DECISION.md`; no obligation was removed and no factory rule inferred. Stop at this evidenced profile and exact reference-data blocker, not at an intermediate implementation gate.


## D-014 — Source-aware technical profile v1, 2026-10-15

User explicitly authorized a separate profile when the pinned GlowStitch source lacks authoritative intent. Direct source recheck confirms only unnamed net 0. Adopt contracts/source_aware_v1.json separately; actual result PASS with 37 regressions passing. Original completion matrix and aggregate NOT_ESTABLISHED remain unchanged. Legacy source IDs repeat: revision-bound composite identities are required. See SOURCE_AWARE_V1_DECISION.md for evidence, deferral and exact limits. Stop without V2/V3 or pcb_Z.


## D-015 — HALPI2 bounded electrical case, 2026-10-15

User authorized focused reuse/consolidation of HALPI2 evidence and only missing project-local controls. Adopt no new acceptance profile. The existing physical open control did not test a named net pair; added a native-bound J22.1 isolation control, preserving the pad and breaking precisely its 15 required GND pairs. Named case PASS: 120 source-justified GND pairs per layer, all 64 named pads mapped and separation-checked; existing bridge rejected. Explicit native-source reference class, no schematic parity claim. Original aggregate/GlowStitch NOT_ESTABLISHED and source-aware PASS unchanged. See HALPI2_ELECTRICAL_CASE.md. Stop without expanding scope.


## D-016 — Standing authorization and bounded V2 result, 2026-10-15

User explicitly granted standing authorization after clarification: implement the proposed end-to-end synthetic MovePadWithConnections slice, including read-only inspection/minimal helper integration of the specified adjacent pcb_Z package. This supersedes prior stops/isolation only for those actions; no per-step approval within scope. Close V1.5 engineering investigation while preserving original NOT_ESTABLISHED and separate positive results. V2 technical PASS: P1 computed at 20.05 mm, T1–T3 synchronized, protected objects preserved, native exports and unchanged validators pass, fault attempts cannot replace accepted output, 48 tests PASS. See V2_DECISION.md. No V3, public-board editing, full legacy/database merger, remote publication or other lanes authorized.


## D-017 — Additive visual delivery, 2026-10-15

User supplied/adopted the visual handoff and requested a working evidence-linked local workbench, not a proposal. Implemented one read-only scene adapter and HTML/SVG surface over hash-bound actual V2/public Gerber results: synchronized comparisons, layer delta, roles/source-group distinction, localized findings/terminals, separate control/candidate statuses, explicit unknown intent and recorded transaction replay. 56 regressions/report tests and 30 final UI combinations pass; 1,078 prior evidence files unchanged. Each future meaningful checkpoint includes an applicable visual case bundle through this same surface. No acceptance/profile/parser changes or new native execution; no broader authority is inferred. See VISUAL_WORKBENCH.md, including precise Safari versus final in-app browser coverage.


## D-018 — Client Gerber operation and consolidated delivery, 2026-10-15

The user accepted the one-region client plan, authorized full implementation/review/video, and then requested consolidation. Close the bounded bottom-copper R140.1 demonstration with actual candidate export/reparse, nine local PASS checks, expected open/bridge/admission rejections, accepted-artifact preservation and evidence-linked replay. The +0.35 mm challenge is artificial; accepted bytes equal the already-aligned source. Consolidate source, runbook, decision and hash register in a local commit. Retain client data/generated artifacts outside Git. Preserve the asset-inventory/full-suite and custom-receipt-verifier limitations explicitly. Cursor review NOT_RUN: CHANNEL_UNAVAILABLE; no manufacturing/whole-board claim, remote publication or new stage. See CLIENT_OPERATION_DECISION.md.


## D-019 — Consolidate discovered delivery issues, 2026-10-15

The user clarified “no new step but to consolidate discovered/left issues.” Authorize project-local maintenance of existing delivery: explicit receipt compatibility and fail-closed validation, common future bundle receipts, accurate dirty-state provenance, exclusion of recordings/obsolete review notes, and source/candidate/control hash admission before replay generation. Add corruption regressions and retain exact fresh receipts. Preserve immutable assets including the extra `.DS_Store`, all old bundles/video/frozen decisions and existing engineering limits. Track unresolved items in CLIENT_ISSUES.md. No new operation, parser support, implementation stage or publication.


## D-020 — Explicit metadata removal, 2026-10-15

The user explicitly instructed removal of the extra `.DS_Store`, superseding preservation solely for `assets/.DS_Store`. Removed only that file; all 70 frozen assets pass strict inventory and 114 full-suite tests pass. Preserve historical failure receipts and other isolation/immutability rules. No new stage or remote action.


## D-021 — Minimum common catalogue definition and bounded payload adjustment, 2026-10-18

The user opened the previously deferred common-catalogue definition step and requested review of discovery, grouping, structured storage and selective export, scoped to existing Storage & indexes capabilities and a future R140.1/trace/R140.2/mask retrieval. Define source/revision identities, minimum fields, cross-source correspondence and retained qualification without requiring a full catalogue taxonomy. The follow-up explicitly supports raising the existing payload ceiling to 128 MiB; this bounded change is implemented and the real 72,514,570-byte native source admits/readbacks. No chunked backend is introduced. Definition and reuse evidence are in docs/catalogue/MINIMUM_SLICE.md and contracts/common_catalogue_slice_v0_1.json. The client materialization, new correspondence layer and fresh-process retrieval/export acceptance remain implementation work, not results of this definition review. Preserve frozen decisions, original sources and project isolation.

## D-022 — Complete the bounded catalogue with Cursor audit, 2026-10-18

The active user goal requests completion of Step 2 with Cursor audition. This authorizes the minimum R140 slice defined in D-021: bounded native/Gerber records, immutable per-artifact and dataset revisions, retained qualifications, four-role fresh-process retrieval, diagnostic selection export and Storage & indexes presentation. Reuse the existing catalogue, locators, selection and spatial infrastructure. Original assets, sealed client inputs, earlier receipts and all V1/V1.5/V2 acceptance boundaries remain unchanged. No general PCB parser expansion, whole-board reconstruction, repair operation, independent net-intent or manufacturing claim follows. Authenticated Cursor CLI is the read-only reviewer; Codex retains authorship/integration. Implementation/reproduction is in docs/catalogue/DELIVERY.md; actual review findings, corrections and final completion checks belong in docs/catalogue/COMPLETION_AUDIT.md.

## D-023 — Preliminary infrastructure themes, 2026-10-18

The user requested remaining steps and a preliminary visualization of discovery, grouping, structured storage and selective export in Storage & indexes. The existing R140 store/retrieval is reused. The new presentation derives disk/index facts from that store and adds a read-only diagnostic subset download with dependency retention; it does not expand extraction, repair or manufacturing scope. All four themes and the actual browser attachment are verified, with 161 Python tests, five JS suites and an independent Cursor QUALIFIED_IN_DECLARED_SCOPE verdict. See docs/catalogue/STORAGE_THEMES_COMPLETION.md for the exact publication, evidence and remaining limits.
