# ORG-driven five-stage copper treatment
## Route-change decision and integrated Codex research mandate

**Prepared:** 2026-10-24  
**Status:** Proposed execution mandate; becomes active when supplied by the owner to the isolated PCB/CAM project. No local repository changes or implementation are performed by this document.  
**Scientific objective:** Predict which ORG features require treatment, construct their changed geometry through explicit operators, and test whether the resulting exported copper explains EDIT materially better than the existing weak-fit experiment.  
**Not a claim:** Recovery of the expert's unique action sequence, generalization to unseen manufacturing jobs, electrical design correctness, or manufacturing approval.

## 1. Why the route changes

The owner's latest Slice D audit reports presentation/binding acceptance and only weak geometric improvement. These are different achievements. Source-to-display correctness must not be counted as successful expert-treatment reconstruction.

Freeze the existing A–D experiment and its publication as historical evidence. The owner reports payload digest:

`619778095ff802374cff2838c84253b61352e4e404332bd08360f9b1d7b155d7`

Verify its local binding before reuse. Do not reopen the publication solely for additional assurance. Preserve unsupported-arc, correspondence, intent, DRC and manufacturing qualifications exactly.

The new organizing unit is an **ORG feature and its actionable neighborhood**, not a repeated family. Family membership is neither an eligibility requirement nor a presumption that members receive one treatment. Existing family records remain available as historical context; no migration or deletion is needed.

The author of this mandate has the owner's latest summary, not the current A–C code, fitted parameters, or residual arrays. Begin by inspecting the actual implemented operators and measurements. Do not claim that a hypothesized cause of weak fit has already been demonstrated.

## 2. Outcome and bounded scope

Deliver a working five-stage experiment:

1. Predict treatment of circular copper features from ORG.
2. Predict treatment of other eligible copper shapes from ORG.
3. Adapt affected adjacent/connected trace paths and attachment geometry.
4. Adjust eligible trace widths or local trace contours.
5. Reshape eligible pad-to-trace junctions/necks.

**Discovery scope:** Inventory the declared ORG top-copper layer, plus ORG reference-layer geometry admitted by the existing project. Account for all native circular records and other supported shape classes, including explicit unsupported/unclassified entries. This is not a claim that every geometric circle encoded by arbitrary polygons has been recognized. State the recognition coverage.

**Execution scope:** New disposable candidates within a finite set of declared influence regions. Select these reproducibly from ORG features, spatial interaction and representation coverage—not just the three G22 members, not family membership, and not the regions where EDIT happens to fit best. Freeze the selected regions, their halos and boundary ports before fitting. Keep the existing three members as optional regression examples.

Do not attempt unconditional whole-board editing. Every inventoried feature receives a disposition; not every feature must be modified. Every supported trace is considered for a disposition; not every trace should be widened.

Use one or more source-derived connected interaction neighborhoods where effects overlap. These are operational dependencies, not a new repeated-family recognition scheme.

This mandate supersedes the previous three-member/family-only and measurement-only restrictions for this experimental scope. It preserves isolation, original inputs, unknown process intent, immutable evidence, unchanged numerical qualification budgets, and the prohibition on production release. No routine human review is required between implementation slices.

## 3. Separate the predictor, constructor and evaluator

### 3.1 Source-only prediction and execution

The executable prediction and construction path may read:

- pinned ORG geometry and source records;
- available ORG layer associations, used geometrically unless their role is qualified;
- ORG adjacency, contact, spatial neighborhoods and already qualified descriptors;
- a frozen low-dimensional policy/model/parameter artifact and its provenance;
- the explicit experimental constraints and edit permissions.

It must not read EDIT geometry, EDIT-derived per-object labels, target delta masks, target-generated clipping contours, candidate rankings derived from EDIT, or hidden coordinate-to-EDIT lookup tables.

Prediction means selecting and parameterizing an operation, not merely detecting circles. It may initially be deterministic rules; a trained model is not a prerequisite.

### 3.2 EDIT in development and evaluation

EDIT may be used by a separate calibration/evaluation process to:

- establish qualified observed-change labels;
- assess geometric representation and operator adequacy;
- fit compact shared coefficients or rules on explicitly declared development cases;
- evaluate selection and exported candidate geometry;
- locate and explain residual errors.

A frozen rule calibrated using EDIT is target-informed development, not discovery of a factory rule. A diagnostic run with EDIT-informed parameters is not an ORG-only prediction result. Label both separately.

Test the dependency boundary: with the model/policy artifact frozen, run prediction/construction in an input environment that does not expose EDIT. Changing or withholding EDIT must not change the plan or candidate. Evaluation may, of course, change when its target changes.

Absolute coordinates remain necessary for geometry. They must not act as a memorized per-site target parameter table. A source-defined region constraint is allowed only when its role and provenance are explicit.

## 4. Reuse the catalogue; add a treatment queue, not a replacement database

A task-local treatment record should link existing source identities and geometry:

```text
feature_key, source_revision, source_occurrences, layer
representation_status, feature_kind, local_geometry_refs
reference_candidates_and_role_status
attached_trace_refs, fixed_ports, physical_context_refs
neighbor_query_and_influence_region
prediction: KEEP | EXPAND | RESHAPE | ABSTAIN
reason_codes, model_or_policy_digest, evidence_class
proposed_parameters, allowed_changes, protected_geometry
operator_results, validation_refs, residual_refs
```

These are proposed fields, not assertions that current schemas already contain them. Reuse equivalent existing fields. Avoid copying large geometry or inventing new permanent identities unnecessarily.

Distinguish source record, composed geometric feature, physical component and operation target. A feature may have several source occurrences. A circle might be a land-like copper feature, part of another construction, or in a reference layer; shape alone does not prove pad, via, or manufacturing role.

Preserve occurrence-to-composed-geometry provenance. Replacing one source contribution must not accidentally subtract copper still contributed by a protected overlapping object. Compose retained and replacement contributions with the qualified semantics; do not blindly subtract source-object areas from the final union.

Do not confuse unknown net assignments with one shared net. Physical contact in ORG is an observation, not electrical authorization.

## 5. The five stages and their concrete contracts

### Stage 1 — Circular-feature treatment

Enumerate all supported ORG circular copper features in the discovery scope. Keep circular reference-layer features distinct. Record centre, radius, orientation where meaningful, local attached traces, measured gaps, reference relationships, overlap/supporting primitives, and coverage limits.

Predict KEEP, EXPAND, RESHAPE or ABSTAIN using ORG descriptors and the frozen policy. Do not classify every circle as a pad or automatically enlarge all circles. Include predicted unchanged features in evaluation.

For selected features, propose target dimensions or a bounded shape envelope and its parameter provenance. Retain centre/reference position unless explicit experimental permissions allow displacement. Asymmetric clipping or shape adjustment is different from relocating the reference.

**Audit:** circular-record inventory denominator; selection reasons; label coverage; source-only dependency test; generated local geometry and reference preservation.

### Stage 2 — Noncircular shape treatment

Apply the same framework to supported rectangles, obrounds, polygons and composite local copper, according to actual existing parser capabilities. Classify unsupported constructs rather than inventing their geometry.

Use anisotropic dimensions or bounded contours when appropriate. The earlier source investigation reports a rectangular family becoming wider and shorter; therefore this stage cannot be restricted to positive isotropic growth.

Treat these shapes independently of repeated-family membership. A physically connected copper component may contain multiple target features and protected paths.

**Audit:** shape-class coverage; unique/shared source attribution; dimension changes; false selections on unchanged features; source-only plan reproducibility.

### Stage 3 — Trace attachment and local path adjustment

Interpret the owner's “adjoint position” as the geometry of adjacent or connected trace approaches, attachment points and short local paths.

Retain qualified connectivity and fixed boundary ports. Propose bounded endpoint, entry-angle, local bend or centreline changes within the admitted influence region. A trace starting inside the land need not always be recentered; identify the actual path/spacing objective.

Use planned final copper/width envelopes to reserve space. Merely moving a centreline and widening it later without reconsidering clearance is insufficient. Neighboring protected conductors remain obstacles; same-component geometry is not automatically writable.

When several proposed changes compete for space, solve the coupled neighborhood or perform a bounded deterministic reconciliation cycle. Record failed alternatives. Do not assume arbitrary source iteration order reproduces expert priority. This is a local adjustment implementation, not an authorization for a general autorouter.

**Audit:** port preservation; local path legality; obstacle conflict counts; observed connection/separation invariants; effect on fit independent of width changes.

### Stage 4 — Trace-width and local-contour adjustment

Consider all supported traces in the selected regions, including nearby traces whose change is not captured by a chosen circular seed's strict correspondence.

Allow KEEP, widening, width-profile changes, or permitted local neck-down/cutback. Preserve minimum dimensions and protected clearances under an explicitly declared experimental policy. Never silently import toy-coupon or measured EDIT values as factory requirements.

Assess distance using effective copper geometry, not centreline distance alone. Reconcile with Stage 3 if the proposed width cannot fit. Do not assume every intermediate stage is an acceptable publishable candidate.

**Audit:** declared cross-section stations; changed widths/contours; constraint conflicts and exceptions; incremental and final target fit; non-target preservation.

### Stage 5 — Junction/neck shaping

Apply bounded transitions only at eligible land–trace and relevant width-transition junctions after the main geometry is laid out. Parameterize junction length, taper/fillet extent or equivalent geometric controls using the smallest suitable existing operators.

Recheck nearby spacing and observed connectivity after blending. A visually smooth neck can still create a short or an excessively narrow bridge. Reject unqualified candidates rather than relying on appearance.

**Audit:** junction support and eligibility; local width/neck checks; no prohibited merges or splits; fixed-reference and scope checks; final exported result.

### Sequencing qualification

The five stages are a useful computational decomposition, not a claim about the human expert's historical sequence. Plan major shape and width envelopes together, then execute/reconcile in a finite declared schedule. Retain actual snapshots of meaningful prefixes and the final candidate. Do not require every prefix to improve fit monotonically or pass final dimensional checks; the final accepted candidate must satisfy the full declared invariant set.

## 6. Prevent another selection-only or presentation-only success

Evaluate two questions independently:

1. **Selection:** Did the ORG-only predictor choose the correct features and treatment classes on evaluable targets?
2. **Construction:** Even when the chosen treatment and a few dimensions are supplied diagnostically, can the operators generate the observed kind of local copper change?

Use a bounded EDIT-informed operator-capacity diagnostic early, as an internal part of the same task. It may provide target-informed low-dimensional operation parameters for supported cases; it must not transplant target contours. If the five-stage operators still achieve only weak improvement under this privileged diagnostic, improving a selector alone cannot resolve the demonstrated construction limitation. Identify and address the specific representation, editable-scope, path, contour or operator gap within this task's scope.

Conversely, if the diagnostic construction works but ORG-only selection fails, focus on selection features and calibration. Do not spend the next cycle polishing the viewer.

Do not label this diagnostic a rigorous mathematical upper bound; it is conditional on the operator set, parameterization and tested search budget.

The lack of local process intent may leave multiple plausible actions for identical ORG geometry. Record ABSTAIN or model uncertainty when justified. Do not promise unique exact reconstruction from geometry alone.

## 7. Target and data adequacy

Inspect the existing A–C receipt, actual recipe code and per-region residuals. Determine which quantities were supported and how the prior modest improvement was measured. Do not infer current numerical fit from the source-to-display audit.

Preserve the earlier exact reference-based transform when qualified; do not independently align copper to improve scores. Reference-layer geometric correspondence is not a physical exposure-role qualification.

Compare **composed effective copper in fixed regions**, not sums of primitive areas or only a correspondence-filtered object list. Include incoming primitives whose endpoints lie outside but whose effective geometry enters the region. Preserve larger context or fixed ports needed for claimed local topology.

The earlier report says 84 native EDIT arcs remain unsupported. Determine whether each affects the particular evaluation region or safety neighborhood. Use an already admitted original Gerber or qualified native export interpretation of the same layer as an alternative only with explicit revision/layer/coordinate bindings and supporting tests. Do not silently repair native arcs, discard them, assign zero area, promote the general parser, or run previously prohibited real-board counterfactuals.

An incomplete target cannot provide a reliable unchanged label. An unknown obstacle cannot be treated as free space. State separately which regions are usable for prediction labels, fit measurements, and constrained candidate validation. Continue unaffected eligible work; do not claim whole-layer reconstruction from a partial score.

## 8. Calibration and evaluation discipline

Build a change-observation ledger for evaluable feature neighborhoods using the existing qualified ORG/EDIT paths. Retain ambiguity where one-to-many or overlapping records prevent exact attribution. Compose both geometries even when individual source-object matching is ambiguous, provided region coverage is qualified.

Separate development regions from non-retuned test regions by ORG spatial interaction components, not random adjacent objects sharing traces or halos. Declare any unavoidable shared context. Select the split and freeze parameters before scoring the latter. The board and several targets were already examined; describe this as same-job non-retuned transfer, not blind validation or cross-job generalization.

Report KEEP/changed/unknown coverage and class-specific selection outcomes. Where labels are qualified, include precision/recall and counts of false treatment on unchanged geometry. Do not manufacture labels to fill a confusion matrix.

If one job cannot support a meaningful independent split, report an in-sample reconstruction study honestly. No new external dataset is required for this goal, and no supervised model training is mandatory.

## 9. Evaluation that measures the actual objective

For a fixed qualified domain R, let O be original copper, T be EDIT target copper and C be candidate copper, all in the same frame and clipped to R after correct composition.

```text
observed_added   = T \ O
observed_removed = O \ T
candidate_added = C \ O
candidate_removed = O \ C

captured_addition = candidate_added ∩ observed_added
false_addition = candidate_added \ observed_added
captured_removal = candidate_removed ∩ observed_removed
false_removal = candidate_removed \ observed_removed
residual = C symmetric_difference T
baseline_residual = O symmetric_difference T
```

These are geometric evaluation definitions, not manufacturing tolerances. Normalize only when denominators are nonzero and meaningful; explicitly report no-change cases and absolute units. Use union domains to avoid double counting overlapping windows.

Report:

- missed and incorrectly added/removed copper;
- residual reduction against unchanged ORG and the prior best candidate, only on comparable domains;
- boundary discrepancy and width/neck profiles where qualified;
- selection error and ABSTAIN/unsupported coverage;
- reference preservation, prohibited connection changes, scope violations and experimental width/gap checks;
- actual native-to-export agreement and supported DRC results/limits;
- error by shape and operation class, not only a global area score dominated by unchanged copper.

Run stage ablations: unchanged ORG; circle-only; circles plus other shapes; then path adjustment, widths/contours and junction shaping. A no-op stage must be visible, not dressed as a completed capability. Nonmonotonic prefixes are allowed, but explain material interactions and judge the final composite result.

At task entry, record a quantitative material-improvement objective against the existing baseline, a finite search budget, and explicit invariant obligations before new fitting. Choose an objective justified by the current baseline and covered target regions; do not retrospectively loosen it to turn weak fitting into PASS. Distinguish experiment executed, technical invariants passed, and reconstruction objective attained. A completed run with weak fit must say **RECONSTRUCTION_OBJECTIVE_NOT_MET**.

## 10. Running verification without human-review gates

Use four work slices internally:

- **I — Source-only feature inventory, target coverage and split, task contract.**
- **II — Five-stage candidate construction and bounded operator-capacity diagnostic.**
- **III — Source-only selection/parameterization, local conflict reconciliation and non-retuned evaluation.**
- **IV — Real exports, final checks, stage-ablation workbench and final decision.**

Slices are checkpoints, not permission requests. Emit concise machine-readable receipts and useful progress statements containing the executed capability, newly measured fit, failed invariants, missing coverage and next action. Continue automatically within scope.

Retain focused negative tests for wrong revision, wrong roles, candidate/target substitution, source mutation, missing primitives, reference motion, disconnection, accidental bridge, protected-object change, unsupported influence, stale stage display, and target leakage into generation. Reuse prior qualified tests rather than rebuilding their infrastructure.

If a scientific step fails, preserve it, diagnose a specific cause, and perform bounded in-scope corrections. Stop only at integrated completion, an evidenced blocker outside the admitted scope, or execution/resource limits. Do not loop indefinitely on fitting, re-seal the same presentation, or stop after a proposal/registry/target card alone.

## 11. Export, invariants and safety of the experiment

Use the current pinned functioning KiCad/runtime and existing admitted export/read paths. No reinstall or version upgrade is implied. Produce candidate artwork in disposable workspaces with an explicit patch/source map. Keep ORG, EDIT, prior successful outputs and historical failure evidence unchanged.

Predictive selection is not unlimited write permission. The experimental contract defines the maximum writable objects/regions, protected objects, fixed ports and reference geometry. The selector chooses a subset of those eligible for a supported operation.

Use observed same-layer connectivity conservatively where that is all the source supplies; do not label it verified net intent. Preserve known unknowns on support/bending/electrical requirements. No claim of factory-approved gap/width or mechanical reliability follows from a geometric fit.

Actual final Gerbers must be independently read within qualified coverage and checked, not replaced by SVG-only evidence. Native DRC, where feasible, is supplementary and retains all warnings and limitations; no-net converted artwork cannot demonstrate schematic parity by passing a local DRC.

Candidate publication follows the existing bounded transaction/custody protocol. Do not upgrade directory-rename publication into an untested power-loss durability claim. No remote publication is authorized by this document.

## 12. Minimal visual delivery; no new workbench project

Reuse the accepted workbench and binding checks. Add an operation-first view:

```text
ORG → predicted treatment map → circular changes → other shapes
    → trace-path changes → width/contour changes → junction changes
    → final exported candidate versus EDIT
```

Show KEEP, selected and ABSTAIN objects. Enable both effective copper and source-occurrence inspection. Give each stage its actual object/region changes, incremental differences, final invariant state and residual against EDIT. Do not animate unretained intermediate shapes.

The main table should answer:

| Stage | Evaluated | Selected | Changed | Fit contribution | False changes | Invariant failures |
|---|---|---|---|---|---|---|
| 1 circles | actual | actual | actual | measured | measured | actual |
| 2 other shapes | actual | actual | actual | measured | measured | actual |
| 3 trace paths | actual | actual | actual | measured | measured | actual |
| 4 widths/contours | actual | actual | actual | measured | measured | actual |
| 5 junctions | actual | actual | actual | measured | measured | actual |

Keep final outcome distinct from intermediate event state. Retain existing source-to-display safeguards, but stop at their established level unless new behavior creates a regression. Do not generate thousands of new static pages as a substitute for a meaningful experiment.

## 13. Completion deliverables and report

Produce one reproducible entrypoint and a compact bundle containing:

1. The frozen experiment contract and complete feature-disposition ledger for the declared discovery scope.
2. The source-only predictor policy/model and executable five-stage operators.
3. Operator-capacity diagnostic and source-only end-to-end results, explicitly separated.
4. Exported candidate, verification receipts, stage ablations, residual metrics and failure examples.
5. An updated workbench view and concise decision explaining what improved and what remains unexplained.

In the final report state separately:

- source inventory/representation coverage;
- ORG-only prediction demonstrated or not;
- operation set adequate for the tested target or not;
- material reconstruction objective achieved or not;
- technical invariants and actual export result;
- same-job transfer status and selection errors;
- unresolved target coverage, manufacturing and electrical qualifications;
- independent review status.

Codex remains sole coordinator. Cursor review uses a verified direct channel only; CHANNEL_UNAVAILABLE remains NOT_RUN and does not block local implementation. Do not modify shared gfs/pcb_Z code or unrelated lanes. No additional B-tree, R-tree, database migration, AI planning platform, human form filling, or broad feature expansion is required.

## 14. Basis and provenance of this mandate

- **Owner's latest message:** accepts changing route away from repeated families and supplies the five-stage skeleton. It includes a duplicated summary audit reporting weak fitting and Slice D binding acceptance; it does not supply the current full experiment payload for independent verification here.
- **ORG_EDIT_3020301113B_Findings/REPORT.md:** prior read-only measurements, including selective copper growth, failure of uniform growth, source-layer ambiguity and a rectangle family widening while shortening. These are prior observations, not factory specifications or fresh verification of the latest slices.
- **G22_Family_Reconstruction_Handoff/G22_FAMILY_RECONSTRUCTION_HANDOFF.md:** previous experimental mandate. Its preservation, export and non-copying principles are reused; its three-member/family organizing restriction is superseded by this new route when adopted.
- **OWNER_REVIEW_DECISION_20261024.md:** bounded visual SUPPORTED decision remains unchanged. It is not the authority for manufacturing edits; the new mandate is the separate experimental authorization when delivered by the owner.

This document is a new implementation proposal, not a claim that the five-stage route has already succeeded.
