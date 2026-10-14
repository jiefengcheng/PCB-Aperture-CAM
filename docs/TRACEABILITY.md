# Requirements traceability — proposed operation cases

Status: conceptual traceability only, not an implemented schema, operator or approved manufacturing policy. Source: supplied charter §§2, 4, 6, 8 and 13, plus existing [CONTEXT.md](CONTEXT.md). Partner needs are **supplied summaries**, not independently inspected requirements or engineer-approved rules.

## Requirement-to-case map

| ID / supplied need | Proposed operation case and relationship model | Required independent acceptance / dependencies | Proposed strategic gate | Current evidence and status |
|---|---|---|---|---|
| R-01 Trace movement/reshaping | `ReshapeTrace`: direct track segments; explicitly permitted dependent junctions; protected terminals; neighboring copper is read-only context | Approved path/width/clearance, neck/contact and preserved connections; exported geometry diff within exact write set | CH-G2 case definition → CH-G3 bounded executor | V1 checks a supplied P1/T1–T3 adjustment; no movement executor or partner trace operation. Production operation NOT_ESTABLISHED. |
| R-02 Pad-group/footprint adjustment | `MovePadGroupWithConnections`: exact pad group and allowed transforms; dependents explicitly enumerated; non-target pads protected | Engineer-approved grouping, spacing/rotation, movement envelope, linked tracks, exposed openings and clearance | CH-G2 → CH-G3; broader grouping CH-G6 | V1 verifies one pre-generated pad move, not group editing or generic footprint semantics. Operator NOT_RUN; real correctness NOT_ESTABLISHED. |
| R-03 Via adjustment | `MoveVia`: explicit via and authorized attached conductors; plated connection/layer span separate from proximity context | Independent net intent, drill and copper layer alignment, annular ring, plating/span and process rules; qualified multilayer geometry | CH-G6, after CH-G1 and CH-G2 prerequisites | V1 is single-front-copper with no qualified holes/vias. Public drill export is inventory only. Via semantics and process acceptance NOT_ESTABLISHED. |
| R-04 Pad–trace teardrops | `AddTeardrop`: target junction; bounded added copper; protected pad/opening; nearby shapes read-only | Approved taper/contact/width/clearance parameters and net continuity; distinguish additive delta from unrelated changes | CH-G2 case contract, CH-G6 execution | No operator, teardrop oracle or approved dimensions. NOT_ESTABLISHED. |
| R-05 Mask/coverlay openings | `AdjustOpening` or `MoveCopperRelativeToFrozenOpening`: declare which layer may change and which is fixed | Process-specific layer role/polarity, registration uncertainty, exposure/overlap and approved coverlay material/process constraints | CH-G1 geometry support → CH-G2 → CH-G3/CH-G6 | V1 fixed synthetic F.Mask opening, 0.15 mm invented rim; public mask composition unsupported. F.Mask is not automatically flex coverlay. Production rules NOT_ESTABLISHED. |
| R-06 Layer outputs, ink/marking | `PreserveOrEditLayerArtwork`: explicit output/layer set, role, origin/units, approved graphic targets; other layers protected | Complete layer/drill manifest, composed polarity and primitive semantics, diff and independent oracle; approved marking constraints if edited | CH-G1 first; CH-G6 edits when authorized | V1 three layers; V1.5 nine requested native layers with repeated primitive fingerprints and empty layers inventoried. Complete manufacturing job and layer edits NOT_ESTABLISHED. |
| R-07 Later panelization/checking | `PanelizeApprovedBoard`: explicit copies/transforms, panel context and permitted rails/holes | Engineer-approved panel/process rules, transformed connectivity/layer consistency and independent exported checks | CH-G6, separately authorized | GlowStitch input is panelized; loading it proves no panelization operator. NOT_ESTABLISHED. |
| R-08 Engineer decision and provenance | Every case binds immutable originals, rule passages, scope, candidate lineage, validation and accept/reject/escalate decision | Named approving engineer and real case objective; audit trail; no automatic acceptance for unknowns | CH-G2/CH-G4; measurable usefulness CH-G5 | V1/V1.5 commit/hash receipts exist; no partner approval or measured business improvement. NOT_ESTABLISHED. |

## Minimal operation-case concepts to specify later

A proposed `ModificationCase` needs immutable source revisions and file hashes; coordinate/layer/unit transforms; direct targets; **separately authorized** dependent writes; protected objects/connections; read-only context; rule passages and provenance states (`supplied`, `inferred`, `engineer-approved`, `unresolved`); operation type/parameters/preconditions; exact write set and region; output lineage/diff; supported checks and unknowns; engineer decision. This is a field inventory, not schema code or implementation authorization.

Keep physical copper connectivity, modification dependencies and spatial/cross-layer influence as different relations. A net name is not geometric connectivity. A touching component is not an implicit edit group. An inferred association grants no write permission. For example, P1 may be a direct target; T1–T3 are writable only by explicit case scope; P2–P4/T4–T5 are protected; nearby N2 copper is read-only context. This describes the frozen coupon contract without implementing an executor.

Historical before/after artwork is `observed` data. Edit sequences and reasons are `hypothesized` unless an engineer confirms them. It is not repair ground truth merely because two revisions exist.

## Evidence anchors and outstanding needs

- Frozen coupon policy and intent: `assets/starter/reference/policy.json`, `intended_connections.json`; actual export receipts and `out/v1_validation.json`. Synthetic constraints only.
- Public custody: `contracts/public_sources.json`; [V1_5_DECISION.md](V1_5_DECISION.md); `out/v1_5/`. Repeated parser primitives do not establish semantic independence or process rules.
- Verification limits: [CHARTER_EVIDENCE_AUDIT.md](CHARTER_EVIDENCE_AUDIT.md). No new geometry validation in this governance pass.
- Future partner dependency: one permitted immutable original/final pair, exact rule and target passages, layer/drill/net intent, protected objects, engineer-confirmed goal and acceptance. Partner access/contact is not authorized by this document.
- Future technical dependency: coverage and independent geometric oracle for relevant constructs before any bounded executor. See [NEXT_GATE_PROPOSAL.md](NEXT_GATE_PROPOSAL.md).


## FC-1 authorization and decision — 2026-10-14

The user approved the reconciliations and FC-1 only (DECISIONS D-009); earlier proposal/approval-stop text is retained as history. [FC1_DECISION.md](FC1_DECISION.md) records oracle qualification PASS for one exact Ucamco source, with [FC1_ORACLE_DERIVATION.md](FC1_ORACLE_DERIVATION.md) defining the independent expectations and numerical limits. Extended parser support and realistic PCB validation remain NOT_ESTABLISHED; Cursor review NOT_RUN / CHANNEL_UNAVAILABLE. MC-1 and FC-2A are not authorized, and no V2/V3 begins. Stop at this gate.
