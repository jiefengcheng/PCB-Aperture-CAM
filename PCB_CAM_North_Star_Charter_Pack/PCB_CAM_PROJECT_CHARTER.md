# PCB/CAM Intelligent Modification — Project Goal & Engineering Charter

**Document ID:** PCB-CAM-CHARTER-001  
**Version:** 1.0 — 2026-10-14  
**Status:** Proposed for adoption by the user; strategic authority after explicit adoption  
**Scope:** Long-lived project direction; not an authorization to implement a new milestone  
**Implementation owner:** Codex (sole coordinator); Cursor (independent reviewer only when a verified direct channel exists); manufacturing specialists (process semantics and acceptance)

## 1. Mission / North Star

Develop an **engineer-supervised PCB/CAM modification system** that converts customer artwork and applicable manufacturing requirements into **precise, bounded, independently validated, reviewable production-artwork changes**, while preserving the original data, relevant electrical connections, protected geometry, and a reproducible decision trail.

The end-to-end contract is:

**Receive and preserve → understand source and requirements → identify operation context → propose a typed bounded change → execute on an isolated revision → export → independently validate → engineer accept/reject/escalate → record and reuse evidence.**

**Success is not** an LLM drawing copper, a lower DRC error count, a successful KiCad export, or a screenshot. Success is an **approved manufacturing modification**, supported by explicit objectives and preservation conditions, on the **delivered output**.

## 2. Why this project exists / partner problem

The customer describes variable source layout conventions, differing customer rules, factory process constraints, repetitive manual CAM changes, fragmented tools and error risk. Requested initial operation families include **trace movement/reshaping (自动移线), pad/footprint arrangement (调封装), via adjustments (过孔调整), pad–trace teardrops (PAD 加泪滴)**, plus protective-layer openings, ink and marking layers. Later scope includes panelization and checking. These are **requirements to investigate**, not already-defined operators with approved tolerances.

The partner's technical proposal reports copper geometry parsing, connected-component grouping, structured storage and selective export; this is a potential foundation, not proof of reliable automated repair. Its presentation mixes Gerber input claims and native KiCad object handling: do not treat them as interchangeable. Evaluate actual partner code and examples before integration decisions.

## 3. Product boundaries and non-goals

**Product:** an engineer-supervised CAM workbench/service, not a universal PCB designer. **First business goal:** reproducibly solve one partner-approved, recurring manufacturing edit and show that it reduces engineer effort without unsafe regressions.

**Supported input modes, with different guarantees:**
- **Native design:** KiCad board/project, schematic and rules where supplied; native objects and nets may be available.
- **Manufacturing data:** Gerber layers, drills, supplied netlist/attributes, coverlay/mask and process specifications; missing net/assembly intent remains unknown.

**Non-goals for early milestones:** universal Gerber-to-design recovery; unsupervised factory signoff; broad autonomous routing; model-generated coordinates without deterministic constraints; complete impedance/assembly verification via DRC alone; arbitrary multilayer transformations; replacing the partner's code before inspecting it; building a graph database or GNN before a measured need.

## 4. Core conceptual model: operation-centered modification case

A connected copper component is **not** necessarily an edit unit. Every `ModificationCase` must identify:

1. **Source revisions and provenance:** original immutable artifacts, coordinate system, layer roles, unit and transformation records.
2. **Direct targets:** exact objects/regions authorized to change.
3. **Dependent objects:** connected or functionally associated items that may require synchronized modification.
4. **Protected objects/connections:** things that must not change or break.
5. **Read-only context:** nearby or cross-layer obstacles relevant to checking but **not** implicitly writable.
6. **Requirement and rule provenance:** source passage, unit, scope, version, status (`supplied`, `inferred`, `engineer-approved`, `unresolved`).
7. **Operation contract:** operator type, parameters, preconditions, allowed region, allowed object IDs, read dependencies, write set, invariants and approval requirement.
8. **Result:** candidate revision, geometric diff, export artifacts, validation report, review decision, residual unknowns.

Maintain three distinct relationship families: **physical copper connectivity**, **associated modification dependencies**, and **spatial/cross-layer influence**. Net intent must remain separate from observed geometric connectivity. An inferred relation does not grant permission to modify an object.

A historical before/after difference is an **observation**, not automatically the true edit sequence, reason, correctness label or training ground truth. Preserve `observed`, `hypothesized`, and `engineer-confirmed` interpretations separately.

## 5. Architecture and ownership

```
Customer native design or manufacturing job + process requirements
          |
Immutable intake, hashes, source references, units, layers, revisions
          |
Canonical geometric + semantic representation (preserve original files)
          |----------------------------|
Geometry/topology services     Requirement/rule compiler and provenance
          |----------------------------|
Operation-context extraction + diagnosis
          |
Planner: engineer/rules first; retrieval/LLM later; GNN only if measured
          |
Typed constrained operation / deterministic geometry executor
          |
Isolated candidate + native/production export
          |
Independent output validation + engineer review
          |
Accept / reject / not established / rollback + case ledger
```

- **Codex:** sole coordinator for this isolated checkout; implementation, test evidence, integration, decision reports and frozen review packets.
- **Cursor:** independent *read-only* reviewer when a verified direct tool/channel exists. `CHANNEL_UNAVAILABLE` means `NOT_RUN`, never implied approval; no human message relay required.
- **CAM/manufacturing engineers:** own real process interpretation, target semantics, exceptions, allowable changes and production acceptance.
- **KiCad:** replaceable native editor/viewer/export/DRC adapter; not the canonical business policy or universal industrial CAM engine.
- **Geometry/parser tools:** explicit versioned dependencies with documented support limits. No silent dropping of Gerber constructs or invented nets.

## 6. Validation contract (all milestones)

Validation must evaluate the **exported, reopened/composed production geometry**, not just internal JSON or KiCad in-memory state. Distinguish:

- **Objective achieved:** requested registration, exposure, opening, shape or other specified change.
- **Preservation:** frozen aperture/reference, unrelated geometry, approved object scope, electrical topology, clearance, width/neck and relevant layers.
- **Source/format validity:** layer semantics, origin, units, polarity, regions, arcs, aperture macros/blocks, drills, attributes and tool coverage.
- **Manufacturing/engineering approval:** specific factory DFM, assembly and process requirements; cannot be inferred from synthetic tests.

Every individual check and overall decision uses `PASS`, `FAIL`, `NOT_ESTABLISHED`, or `NOT_RUN`, with machine-readable reasons and evidence. An unsupported required construct is **not** a pass. A lower violation count is not a substitute for objective and preservation checks. Use negative fixtures that fail for the intended reason. Preserve source hashes, commands, versions, tolerances and candidate lineage. Avoid shared-oracle circularity where the same candidate model supplies both the output and its purported independent truth.

## 7. Current evidence ledger (as reported by Codex, not independently re-audited here)

| Gate | Reported evidence | Status / limit |
|---|---|---|
| V0 synthetic coupon | KiCad opens, independent aperture fixture, generated before/candidate | Experimental scaffolding only |
| V1 exported-Gerber validation | Commit `36eab151a0bf00ea57eef09f1dc425c4b5603e50`; KiCad 10.99.0; exposure 1.19→1.40 mm²; fixed mask/outline, connectivity, 1.55 mm clearance, scope reported pass; 8 tests incl. 13 corruption controls; 70 hashes | **PASS for synthetic coupon only**; native DRC footprint-library warning; no manufacturing signoff |
| V1.5 public assets | Commit `cb0377c`; GlowStitch and HALPI2 pinned/acquired; native boards load/export and reproduce plotting primitives without edits; Ucamco 9/11 expand without warnings, two aperture-block cases fail; 11 tests pass | **Qualification pass; realistic validation NOT_ESTABLISHED**; parser coverage gap; source intent unqualified |
| Independent Cursor review | Frozen packet; direct channel unavailable | **NOT_RUN / CHANNEL_UNAVAILABLE** |
| Partner manufacturing case | No engineer-approved real input/target/rules in this checkout | **NOT_ESTABLISHED** |

**Evidence authority:** the above is a faithful summary of user-supplied Codex reports. Before relying on a claim, Codex must inspect local commits, tests and evidence files. `docs/ROADMAP.md` and `docs/V1_5_DECISION.md` are reported local files but were not supplied here for direct inspection. Never claim they were reviewed here.

## 8. Milestone plan and gates (future milestones proposed, not automatically authorized)

| Gate | Deliverable | Acceptance / stop condition |
|---|---|---|
| V0 | Synthetic before/candidate and native editor/export | Reproducible input; original preserved |
| V1 | Independent checker for selected synthetic Gerber constructs | Positive and corruption cases, exported evidence, no false PASS |
| V1.5 | Public asset qualification | Pinned sources, read-only round trip, unsupported features enumerated; **not** manufacturing acceptance |
| **G1: format coverage decision** | Prioritized aperture-block and realistic-geometry coverage plan | Explicit supported/unsupported matrix and negative tests; decide whether to implement before V2 |
| **G2: operation case model** | Minimal typed `ModificationCase`, target/dependent/protected/context relations, rule provenance | Engineer-readable case replay and no implicit write permission |
| **G3: V2 one bounded executor** | Isolated `MovePadWithConnections` or partner-approved equivalent | Candidate exported; validator confirms objective, preservation and rollback; bad candidates rejected |
| **G4: partner integration** | One real original/final pair, partner rules, code inventory and approved case | Engineer confirms operation semantics; measured usefulness; unknowns remain explicit |
| **G5: assisted planning** | Rule/retrieval baseline vs LLM-assisted proposal, same executor and validator | Measured reduction in total engineer time or improved accepted coverage without increased unsafe errors |
| **G6: broader CAM operations** | Via, grouped pads, teardrops, mask/coverlay, cross-layer effects, panelization when authorized | Separate process-specific acceptance gates |

**Ordering:** G1 and the minimal G2 model should inform V2; do not postpone all object-relationship modeling until after automated edits. A real partner case should be sought in parallel with engineering work when permitted. Each gate requires **explicit user authorization**; this charter alone authorizes none.

## 9. Immediate decision after `cb0377c`

**Do not interpret V1.5 as realistic repair validation.** Before V2, Codex should deliver a short **gate proposal**, not new implementation:

1. Verify `cb0377c` and the actual evidence; identify precise unsupported primitives/semantics in GlowStitch, HALPI2 and the two Ucamco aperture-block examples.
2. Build a **coverage matrix**: source file/feature → parser behavior → composed geometry confidence → supported checks → `NOT_ESTABLISHED` reason.
3. Recommend the smallest next implementation: likely expand independent Gerber composition/coverage and/or establish a minimal `ModificationCase` schema, with costs and falsification cases.
4. Request an engineer-approved original/final pair and exact manufacturing rule when partner access is available; keep this as a dependency, not a guessed fact.
5. Report Cursor review as `NOT_RUN` unless a real direct channel is verified.
6. Stop for user approval before changing V1 acceptance semantics or beginning V2/V3.

## 10. Governance, isolation and source-of-truth hierarchy

1. **This charter:** mission, product boundary, engineering principles and strategic gates.
2. **`AGENTS.md`:** repository-local operational rules, isolation and delegation, must link to this charter.
3. **Milestone acceptance documents:** concrete test obligations, permitted changes and stop conditions for the active authorized gate.
4. **Immutable fixtures and evidence:** factual source of results; a narrative cannot override failing evidence.
5. **Decision log:** dated, owner-approved scope changes and gate authorizations.

If documents conflict, stop and report the conflict rather than silently reinterpret. This charter is **proposed until adopted**; do not overwrite existing `AGENTS.md` or frozen V1/V1.5 evidence automatically. Only Codex should perform changes in the isolated repository after review.

Never inspect or mutate other research repositories/worktrees, global agent configuration, or adjacent lanes. External downloads require provenance, licensing review and authorization. Never upload private customer data to public services without permission.

## 11. Reporting template (every Codex checkpoint)

```
Gate / commit / owner:
North Star capability advanced:
Question this experiment answers:
Inputs, pinned versions, hashes:
Executed tests and actual results:
Positive objective checks:
Preservation and negative controls:
Unsupported / NOT_ESTABLISHED / NOT_RUN:
Cursor review status and evidence:
Engineering/manufacturing approval status:
New findings and risk changes:
Decision requested from user:
Explicit stop point:
```

## 12. Business-level measures (when partner cases exist)

Track accepted repair rate on held-out jobs, scope violations, connectivity/clearance regressions, false acceptance, appropriate escalation, total engineer handling time (including review/rework), and traceability of every decision. Separate **synthetic technical correctness**, **format compatibility**, **engineering acceptance**, and **measured business improvement**. Never infer one from another.

## 13. Definition of eventual product success

On a representative, engineer-approved customer CAM job, the system can explain the required modification and source rule, identify direct/dependent/protected objects, propose a bounded operation, execute on an isolated copy, export complete manufacturing files, independently verify supported geometry/connectivity/process constraints, surface unknowns for human review, record acceptance or rejection, and demonstrate a measured improvement against the existing manual workflow. Broader autonomy is an optional later optimization, not the definition of success.
