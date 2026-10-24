# Dynamic shape decisions: five operation types, ten explicit stages

**Purpose:** Refine the existing `ORG_FIVE_STAGE_TREATMENT_HANDOFF.md` with a neighborhood-aware shape-decision phase for each operation type. This is an additive design and execution instruction, not a claim that the expert's original order has been recovered. It becomes an active project instruction when supplied by the owner to Codex. No repository changes or experiments were performed in preparing this document.

## 1. The owner's clarification

Retain the five operation types. Each must construct geometry, not merely classify features. Add phases 1.5, 2.5, 3.5, 4.5, and 5.5 to make dynamic decisions about the corresponding proposed geometry in its current neighborhood.

The essential distinction is:

> The main phase proposes a concrete transformation. Its decision phase adapts, checks, and commits or rejects that transformation against the currently accepted experimental geometry and protected reservations.

The objective is a directionally useful demo for the dominant, supported cases. Exact reproduction of every EDIT contour is not required. Broadening or filling more area alone is not success: references, required local connections, protected geometry, and declared separating gaps remain constraints.

No repeated-family recognition prerequisite is reintroduced. Existing families can remain optional descriptive metadata.

## 2. Ten stages, five paired operations

| Stage | Responsibility | Required output |
|---|---|---|
| **1 — Circular-feature transformation** | Select supported circular copper features from ORG and construct nominal enlarged or reshaped candidates under the frozen policy. Keep or abstain where appropriate. | Candidate geometry, target provenance, growth bounds, and reason. |
| **1.5 — Dynamic circular-shape decision** | Determine how much of that growth fits the current neighborhood. Choose bounded asymmetric growth, limit optional growth, or retain a designated round outline where feasible and declared. | Accepted experimental shape or explicit rejection/abstention, with actual local constraints. |
| **2 — Other-shape transformation** | Construct candidates for supported noncircular features, including directional widening/shortening where the policy permits. | Candidate geometry and degrees of freedom, not only a feature classification. |
| **2.5 — Dynamic noncircular-shape decision** | Fit the proposal around already accepted geometry, protected original features, and future trace reservations. | Accepted contour and local exceptions; no generic requirement to preserve its original primitive shape. |
| **3 — Trace attachment/path transformation** | Propose revised attachment locations, approaches, bends, and short local paths around the accepted land geometry, preserving fixed ports. | Candidate path plus its intended finite-width footprint. |
| **3.5 — Dynamic path/footprint decision** | Check space for that intended footprint, not merely the centerline. Resolve admissible path conflicts or retain/reject the proposal. | Accepted path and reserved routing corridor, with width assumptions. |
| **4 — Trace width/contour transformation** | Propose eligible width profiles, widening, or explicitly permitted local narrowing/cutback. | Candidate effective copper and nominal profile. |
| **4.5 — Dynamic width/spacing decision** | Fit the profile to the corridor and current neighbors while respecting experimental minimum dimensions and connections. | Accepted effective copper or a named conflict; bounded path reconciliation if necessary. |
| **5 — Junction/neck transformation** | Propose bounded land-to-trace and relevant width-transition blends, tapers, or fillets. | Actual proposed transition copper. |
| **5.5 — Dynamic junction decision** | Fit the transition within remaining admitted space, recheck local neck width, separation, and contact, and select or reject the proposal. | Final experimental junction and complete local checks. |

A decision phase is not just a score attached after the edit. It changes the proposal when necessary or refuses it. A proposal is not published as an accepted experimental candidate merely because it was generated.

These are ten visible stages, not ten unrelated algorithms or ten human-approval gates. Reuse a common neighborhood resolver with operation-specific degrees of freedom and predicates.

## 3. One evolving scene and a shared neighborhood resolver

Maintain two distinct sources of information:

- **Pinned ORG:** original geometry, identities, observed topology, source references, and protected obligations.
- **Current experimental scene:** accepted changes generated from ORG, their provenance, and explicit reservations for later operations.

Before treating a feature, retrieve the current effective geometry of the relevant neighbors. Do not repeatedly resolve every proposal against the unchanged ORG scene.

A minimal execution pattern is:

```text
for each operation pair in the declared schedule:
    choose the next eligible feature from the local priority policy
    propose geometry from ORG, current scene, and frozen policy
    adapt proposal to current neighbors and protected reservations
    validate the resulting local patch
    commit to the disposable working scene, or keep/abstain/reject
    record the scene revision, reason, conflicts, and geometric changes
```

For interacting features, proposal and decision must be interleaved at feature or bounded joint-patch granularity. Do not generate a whole stage against one old snapshot and later commit mutually incompatible edits.

Preserve source-contribution semantics: replacing one primitive must not delete copper still contributed by a protected overlapping primitive. Do not confuse scene unions with editable object identity.

## 4. Dynamic growth should occupy eligible local space—not every void

For each land-like target, declare an ORG-derived, bounded influence region and a nominal growth cap. Available space is the part remaining after accounting for:

- protected original geometry and fixed reference geometry;
- currently accepted neighboring copper and required separating gaps;
- reserved trace corridors, boundary ports, and minimum retained seed/junction geometry;
- uncertain or unsupported geometry whose possible influence cannot be excluded.

Unknown geometry is not empty space.

The growth objective may encourage use of otherwise available space around the selected terminal-like feature. It must not reward filling distant trace-only corridors, bridging separate components, or covering the entire board's voids. Keep growth attached to the intended feature; reject detached islands or uncheckable narrow appendages.

Define the influence distance, growth cap, and gap as explicit experimental parameters. Observed EDIT dimensions may inform calibration, but are not automatically factory limits. No EDIT-derived target contour may be used as an influence mask or clipping boundary.

## 5. Priority is part of the proposed demo policy

The image motivates an order-sensitive growth hypothesis; it does not establish the human expert's actual order. Similarly, "one round feature remains while its neighbors reshape" is a useful candidate heuristic, not a universal property of every connected component.

For the first demo:

1. Honor explicit fixed references, minimum retained bodies, and fixed connections first.
2. Give a preferred round outline priority only when the experimental policy selects it from ORG evidence and the outline fits the admitted constraints.
3. Process the remaining local competitors with one declared deterministic policy, such as the most constrained feature first, using a stable identity only to break ties.
4. Respect earlier accepted shapes when adapting later ones. Do not move earlier protected geometry silently.

A physical component may be large and may contain several relevant sites. Do not impose exactly one round anchor on a whole component, and do not interpret component membership as permission to merge every branch or shortcut.

Include one simple alternative ordering as a bounded diagnostic. Compare results rather than asserting that the selected order reproduces expert practice. Do not introduce a combinatorial schedule optimizer in this demo.

## 6. Prevent early stages from consuming space required later

Before committing land growth, reserve the required trace ports and a plausible finite-width corridor derived from the frozen trace policy. Include protected noncircular features even when the circular stage runs first.

The ten-stage list describes responsibilities. It must not imply that circles can consume arbitrary space simply because they are processed before rectangles or traces.

Earlier accepted growth can be provisional rather than immutable. Permit a small, declared reconciliation budget—for example one local reconsideration pass—when later width or junction checks reveal a conflict. Any reconsideration must explicitly reopen the relevant disposable patch, preserve the original evidence, and produce a new recorded decision. No silent modification of fixed objects or unlimited shrinking cascades.

When the budget is exhausted, retain the safe previous patch or abstain. Final publication requires the full declared invariant checks; intermediate proposals can remain rejected or provisional.

## 7. Keep the source-only boundary

Prediction and candidate construction may read pinned ORG, the scene built from ORG, and the frozen policy. Reading earlier generated geometry does not violate ORG-only construction.

EDIT belongs to the separate calibration/evaluation path. It may inform compact policy parameters on declared development cases, but must not supply per-feature answers, exact cut boundaries, residual masks, or hidden coordinate-to-target lookups during construction.

With the policy frozen, withholding EDIT must not change the plan or generated candidate. Preserve the existing distinction between a target-informed operator-capacity diagnostic and an ORG-driven run.

## 8. Retain a small decision record, using existing storage

Reuse the treatment queue/catalogue and execution receipts. Add equivalent fields only where missing:

```text
feature_key, operation_pair, source_revision, input_scene_revision
nominal_shape_ref, accepted_shape_ref, influence_region_ref
priority_reason, reference/shape protection, reserved_ports/corridors
limiting_neighbor_ids, measured_gaps, local_constraints
outcome, adaptation_reason, output_scene_revision, check_refs
```

Example explanation:

> "The nominal circular expansion would violate the experimental gap to an earlier accepted shape. The proposal retains its protected core and attached connection, accepts growth in other available directions, and limits the conflicting side."

No new database, generic family graph, native-index migration, or dashboard platform is necessary.

## 9. Focused running verification

Reuse existing regressions and add controls tied to this change:

- **Crowded pair:** two proposals are individually acceptable against ORG but incompatible together; the later decision must observe the earlier accepted shape.
- **Round-preference exception:** a selected round outline is retained where feasible; an impossible round preference is reported rather than forced.
- **Future corridor:** early growth does not consume a required fixed-port/trace-width reservation.
- **Protected original neighbor:** clipping optional enlargement does not move or erase protected copper.
- **Junction crowding:** a blend cannot silently create a new prohibited connection or subminimum neck.
- **Trace-only void:** terminal-driven growth does not fill unassigned trace-only regions.
- **Order sensitivity:** repeated runs with the same schedule are deterministic; a different declared order is a separate experiment.
- **Incomplete geometry:** unsupported influence prevents an unqualified acceptance rather than disappearing as free space.
- **Source-only construction:** the frozen-policy candidate does not depend on access to EDIT.

Keep target fit and invariant validity separate. Actual exported candidate geometry, not only an in-memory preview, remains the final comparison input.

## 10. A directional demo with honest coverage

The objective is to capture substantial recurring behavior on declared supported cases: localized growth, heterogeneous outlines, retained connections, separating channels, adjusted trace paths/widths, and shaped necks.

Select execution regions from ORG evidence and representation coverage, not from whichever EDIT windows produce the best score. Freeze the evaluated area and show detected, eligible, changed, kept, abstained, and unsupported counts so the demo cannot look better merely by dropping hard cases.

Compare against the prior best candidate and unchanged ORG on the same qualified domains. Retain added/removed copper recovery, incorrect changes, and residual measures. Do not require exact contour equality, but do not call increased copper occupancy successful reconstruction without the corresponding constraints and target comparison.

Keep the existing quantitative improvement objective unless explicitly revised before new fitting; any revision is a new recorded experiment, not retroactive acceptance of a failed one.

## 11. Visual delivery and authority

Extend the existing stage replay. Each operation pair should expose the proposed shape, accepted shape, limiting neighbors, relevant gap/corridor, reason for priority, and actual scene revision. A ten-label timeline must reflect captured states; missing intermediate captures stay explicitly missing.

This addendum refines the already proposed five-stage experimental route. Once adopted, Codex should implement and run its internal slices without routine human-review gates, within the existing finite research scope and resource budget. Preserve immutable inputs, historical evidence, family records, unknown manufacturing/electrical context, and unrelated work. Do not reopen closed Slice D assurance merely to add another publication campaign.

No production approval, whole-board autonomous routing, general machine-learning project, unrelated infrastructure changes, or new remote-publication authority is granted.

**Working mental model:** propose a change; decide its permissible shape in the current scene; retain the result; let the next change respond to it. The five operation types remain stable while their local geometry adapts.
