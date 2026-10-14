# Next-gate proposal — approval required

Status: **PROPOSED / NOT_RUN**. Codex is sole coordinator. This document authorizes no work. Preserve V1 commit `36eab151a0bf00ea57eef09f1dc425c4b5603e50`, V1.5 commit `cb0377cbdcdac25ee9b89c01aca6901b3ae48d0d`, existing acceptance/schema and all original evidence. No V2/V3, partner outreach, additional acquisition or parser implementation occurs in this charter alignment.

## Decision and options

| Option | Small falsifiable deliverable | Dependencies and planning cost | Risk / limit |
|---|---|---|---|
| **A — FC-1: one aperture-block oracle and support decision (recommended)** | Independently specified expected geometry for the already acquired non-nested Ucamco block example; negative oracle cases; explicit contract for a possible later compatibility adapter | Existing pinned Gerbers/PNG, mathematical geometry review, project-local tools; estimate 1–2 engineer days, not measured | Example bundles blocks, clear/dark composition, arcs and transforms; cannot present an aperture-block-only patch as complete support. Parser implementation deferred to separate approval. |
| B — MC-1: passive operation-case model | Minimal versioned case record and engineer-readable replay for the coupon; explicit targets/dependents/protected/context/rule provenance; rejects implicit write permission | Existing coupon policy and independent intent; estimate 0.5–1.5 days | No realistic geometry gain; partner semantics remain unresolved. No executor or planner. |
| C — FC-2: targeted realistic-geometry composition | Qualify one named public layer, including rounded-rectangle macros, polarity, regions/arcs and non-coupon object identities | Approved independent oracle, parser/dependency decision, exact layer scope; estimate 3–6+ days, high uncertainty | Larger scope; aperture-block support alone will not fix public-board coverage. Full public electrical/process validity still unknown. |

Recommend **A only** as the smallest next gate. Do not bundle B or C into its approval. Minimal MC-1 concepts are already traced in [TRACEABILITY.md](TRACEABILITY.md); formal modeling should precede any V2 executor, but its implementation is not part of FC-1. Strategic mapping: FC-1 is an oracle/support-decision slice of charter CH-G1; MC-1 maps to CH-G2. Neither starts CH-G3/V2.

## FC-1 exact scope

Input: acquired `external/sources/Ucamco/gerber-layer-format-test-files_en.zip`, exact archive/member hashes in `contracts/public_sources.json`; select `2026_03_24_Gerber_Layer_Format_Test_Files/Block_with_different_orientations.gbr` and its bundled PNG. Originals stay immutable; any new material goes into a new `out/` gate directory and explicitly authorized test/source areas. No additional download is required.

Question: **Can a small independent oracle distinguish the correct composed image of this one non-nested block example from plausible transform/polarity mistakes, and define a viable bounded compatibility contract before parser work?**

Read source semantics explicitly: `%FSLAX26Y26*%` absolute millimeters; `%ABD12*%` / `%AB*%`; circular flashes and strokes; local dark/clear operations; `G75` / `G03` arcs; four block placements using `LMX`, `LMY`, `LMXY`, `LR30.0`, `LR45.0`, `LS0.8` and reset operations. These constructs are present in the selected file; this is broader than recognizing block delimiters. Nested blocks, generic macros, drills, public PCB intent and all automated edits remain outside FC-1.

Deliverables, if approved:

1. Hand-derived, inspectable block geometry, four transforms, units and polarity-composition order, with expected bounds/areas and named geometric landmarks. Oracle derivation must not consume the same parser-produced primitives as its truth. Bundled PNG is a secondary visual reference, not precision ground truth.
2. Explicit positive/negative oracle fixtures, numerical-error budget and a versioned expected-result ledger separate from V1 acceptance. Choose and justify any comparison tolerance from coordinate resolution and geometric approximation; do not transplant a factory rule or silently reuse the coupon margin.
3. Compare available parser coverage to that oracle contract without changing the frozen parser. Preserve current unsupported statuses. Propose a maintained-parser dependency or narrowly specified standards adapter for a separately approved FC-2 if feasible; do not substitute a general regex parser.
4. A bounded decision: oracle qualified with recorded checks, oracle NOT_ESTABLISHED, or route rejected. State exact next implementation scope and stop. This gate is allowed to conclude that implementation is not yet justified.

## Falsification and acceptance

| Check | Required result / evidence |
|---|---|
| Custody | Archive/member hashes match the frozen manifest before and after; no edits to source or old receipts |
| Positive oracle | One block and all four placements have independently derived locations/orientations/scale and local clear geometry; PNG cross-check documented with raster limits |
| Mirror/rotation faults | Deliberately wrong axis or rotation order is rejected at named asymmetric landmarks |
| Scale/reset faults | Wrong 0.8 scale and leaked transform after reset are rejected by expected bounds/placement |
| Polarity fault | Treating the local clear flash as additive, or clearing unrelated global content, is rejected for the intended geometric reason |
| Arc fault | Wrong sweep/center/units is rejected for the intended bounds/area/landmark reason |
| Unsupported semantics | Undefined aperture, recursive/cyclic/nested block beyond scope, missing units and unknown operation remain explicit NOT_ESTABLISHED; none silently passes |
| Report and stop | Oracle evidence/status, cost and dependency decision; no parser coverage or public validation PASS unless independently established in a future approved gate |

FC-1 success means an independently reviewable oracle and a falsifiable support decision, **not** newly supported Gerber parsing, full Ucamco conformance or realistic repair validation. The negative fixtures are proposed, not created or run. Current oracle qualification, extended composition, MC-1 schema and all executors are NOT_ESTABLISHED / NOT_RUN.

## Prerequisites and stop conditions

The relevant retained coverage matrix is [CHARTER_EVIDENCE_AUDIT.md](CHARTER_EVIDENCE_AUDIT.md). Gerbonara 1.6.3 currently warns on aperture blocks and fails the selected example; retaining that failure is mandatory. Nested-block fixture stays outside the proposed positive scope. Any dependency change, implementation of parser support, broader public-layer scope or manufacturing-policy change requires another explicit approval.

Realistic electrical or manufacturing acceptance additionally needs engineer-approved intent and process rules for a selected case. A partner original/final pair, operation explanation and exact rule passages would help CH-G4, but access/contact is a separate unresolved dependency; do not solicit or acquire it without authorization. No such evidence is claimed here.

Request independent read-only Cursor review only through a verified authenticated direct channel. Current state is NOT_RUN / CHANNEL_UNAVAILABLE. Do not ask a human to relay reviews or imply Cursor approval. Codex may finish an authorized local gate with that review limitation stated, but cannot assert independent review.

**Requested user decision:** approve the reconciled proposed strategic reference and **FC-1 only**, choose MC-1 instead, or revise the scope. After this documentation commit, stop without executing any option.


## FC-1 authorization and decision — 2026-10-14

The user approved the reconciliations and FC-1 only (DECISIONS D-009); earlier proposal/approval-stop text is retained as history. [FC1_DECISION.md](FC1_DECISION.md) records oracle qualification PASS for one exact Ucamco source, with [FC1_ORACLE_DERIVATION.md](FC1_ORACLE_DERIVATION.md) defining the independent expectations and numerical limits. Extended parser support and realistic PCB validation remain NOT_ESTABLISHED; Cursor review NOT_RUN / CHANNEL_UNAVAILABLE. MC-1 and FC-2A are not authorized, and no V2/V3 begins. Stop at this gate.
