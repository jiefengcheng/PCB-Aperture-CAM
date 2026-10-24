# T02 only — Other-shape treatment on the accepted T01 scene

**Prepared:** 2026-10-24
**Operation stages:** 2 + 2.5: noncircular feature proposals and current-neighborhood shape decisions.
**Mode:** One bounded implementation task. Autonomy inside the task; local commit and mandatory STOP before T03.
**Authority:** This mandate becomes active when the owner supplies it to Codex in the isolated PCB/CAM checkout. It does not change a repository by itself.

## 1. Goal and evidence boundary

> Starting from the latest owner-accepted T01 geometry, identify eligible original noncircular copper features in the same crowded crop, construct bounded proposals, adapt them to the current neighborhood, and demonstrate their incremental contribution without damaging T01's accepted shapes or reservations.

The owner reports local commit `838b2d5`: T01 was split into size selection, square recess construction, and owner review edits; the former import path is retained as a compatibility facade. Syntax compilation passed, but no regression tests or behavioral-parity run were performed. The accepted geometry bundle and unrelated dirty files were reportedly untouched.

These are user-reported facts, not independently inspected code. Read the actual `docs/crop_dynamic_tasks/T01_CODE_STRUCTURE.md`, the saved `out/crop_dynamic_tasks/t01_owner_review_20261024_v2/code_consolidation_audit/response.md`, current source, tests, and acceptance receipts before relying on the refactor. The architecture map and latest accepted-bundle identity were not supplied to the author of this mandate. Do not invent module names, accepted run hashes, square-recess semantics, or an owner-edit recipe.

T02's input is the **latest accepted T01 scene**, not automatically the original 39-circle run at `ee619a01...`, the first T01-R1 candidate, the G22 A/B/C neighborhood, or whatever run was generated most recently. Choose the accepted baseline by its recorded owner decision and artifact bindings. Preserve historical results and qualifications.

This task includes runtime/parity preflight as an internal first step. Passing that step authorizes continuation within T02 without another human approval. A concrete inability to establish the required baseline is a blocker, not a reason to manufacture parity.

## 2. Scope override and hard boundaries

At entry, record this T02-only authorization additively in the local task board/decision log. Point repository-local instructions to it where necessary. Preserve previous handoffs as historical documents.

- The prior T01-only prohibition is superseded **only for the work described here**.
- The inherited T02 task card's wording to continue automatically to T03 is superseded. **Commit locally and STOP after T02 for every outcome**, including no applicable features.
- No automatic T03–T07, trace routing, general trace width changes, junction/neck treatment, integrated export-and-fit campaign, or production approval.
- No new family-recognition prerequisite, general parser, database/index migration, gfs/pcb_Z changes, global agent settings, unrelated lane access, broad cleanup, remote push, or external browser/search-field audit paste.
- Keep the full crop as the principal view. Do not substitute A/B/C, a distant rectangular array, or another board to force a visible T02 result.
- Native export is not a T02 completion claim. Use existing local geometry and validation capabilities within their qualified scope; final native/exported reconstruction acceptance remains a later task.
- Unknown manufacturing, bend, support and reference-purpose semantics remain unknown. Experimental geometry behavior is not manufacturing permission.

## 3. Internal checkpoint A — Establish a trustworthy T01 base

### 3.1 Lock the relevant state

Record current HEAD, the full hash resolved for `838b2d5`, relevant dirty/untracked files, the accepted T01 bundle identity, its generating revision or retained receipt, ORG source revision, existing crop/frame, policy, geometry kernel/numerical settings, and acceptance limitations. Do not reset or stash unrelated changes.

The reported older viewport was `(1.2858444444444446, -15.687077777777787, 4.508066666666666, -12.975966666666665)` mm. This is a historical navigation aid: use and verify the latest accepted crop/frame rather than blindly imposing old bounds or the old 0.075 mm halo.

Resolve the actual recorded distinction between:

1. automatic size-selection output;
2. square-recess construction;
3. owner-review edits or an owner-approved final overlay;
4. the accepted final scene.

An owner-edited result must not be described as automatically inferred from ORG. Its provenance can be preserved honestly while it is used as T02's frozen input.

### 3.2 Test the refactor, not just its syntax

Run existing applicable T01 tests and identify the public import/entry points actually used by the pipeline. Add only focused compatibility checks that are missing:

- importing through the old facade and new modules;
- public argument/return contracts, defaults, and relevant error behavior;
- no accidental expensive execution, publication, or source mutation during import;
- unchanged outputs for the same source/order/policy, including size selection, recess geometry and recorded owner edits;
- reproducible deterministic execution under the pinned environment.

Compare refactored outputs with the pre-refactor implementation or retained pre-refactor receipts. Obtain prior code through read-only Git inspection or a disposable snapshot inside the PCB workspace, not by switching/resetting the active checkout. Existing exact fixtures are preferable to recomputing every historical run.

Compare canonical geometry, feature identities, decisions, relevant ordering, protected contours/voids and meaningful policy values. Ignore only explicitly declared nonsemantic fields such as timestamps or output-directory names. Equal total area, a close-looking PNG, or equal test counts is not sufficient. Preserve existing numerical budgets; do not introduce a more permissive tolerance to pass the refactor.

If final acceptance included manual edits that are not represented as an executable recipe, distinguish the algorithmic pre-refactor/refactor comparison from the immutable final-scene check. Do not force the unedited generator to reproduce undocumented manual choices or reconstruct them from screenshot pixels. Load the exact qualified accepted final materialization when the established import path supports it, and identify any unreplayed manual step explicitly. No claim of complete regeneration is permitted without that evidence.

A missing regeneration path does not automatically invalidate a verifiable retained artifact. However, the scene admitted to T02 must have qualified bindings and a faithful load path; a PNG alone is not an executable base.

A narrow compatibility bug may be corrected within this task, with before/after tests and its own evidence. Do not silently change the accepted shape or retune T01 to close parity. If equivalence or accepted input cannot be established within the existing supported path, report the exact blocker and STOP before T02 geometry changes.

**Checkpoint output:** compact `t01_baseline_parity` receipt, including exactly what was replayed, what was loaded from frozen artifacts, and what remains unverified.

## 4. Internal checkpoint B — Define genuine T02 targets

### 4.1 Eligibility comes from original feature provenance

Use the existing inventory/catalogue to identify supported original rectangles, obrounds, polygonal lands, and previously qualified composite noncircular features that affect the fixed crop and its admitted local context.

Distinguish these from:

- polygons or nonround contours generated by T01 circular treatment;
- T01 square recesses, notches, and protected empty regions;
- a circle-plus-trace component that merely looks noncircular as a union;
- broad boundary copper, rails, pours, planes, and long trace corridors;
- drawing annotations or noncopper layers;
- unsupported geometry or ambiguous local-feature ownership.

**A T01 circle does not become a T02 target because its final contour is polygonal. A square recess is empty-space intent, not a rectangle to fill. A component is not automatically one editable land.**

Do not infer feature type solely from its serialization primitive or current outline. Use original source roles and the already qualified feature decomposition. Retain source occurrences, derived-subregion definitions, and overlapping supports separately.

### 4.2 Freeze a bounded disposition table

Every relevant candidate considered needs an ID, source/revision binding, original representation, current effective geometry, disposition and reason:

`TREAT`, `KEEP_PROTECTED`, `ALREADY_TREATED_T01`, `UNRESOLVED_FEATURE`, `UNSUPPORTED_GEOMETRY`, or `INFEASIBLE` as appropriate to the existing status conventions.

Freeze the eligible target set and its shared policy before the main run. Do not choose targets because EDIT changed them or narrow the denominator after seeing poor results. A screenshot is a location cue, not a source identifier or numerical template.

Keep the visual viewport fixed. Reuse qualified full geometry for boundary targets. Expand computational context only as necessary for the declared maximum operation reach and separation constraints within the admitted job. Any write envelope beyond the existing crop must be a specific, source-bound local envelope of an admitted T02 feature, be shown in an audit view, and preserve all accepted T01 geometry. Do not crop away the rest of a feature to make it easier to edit or assume unsupported exterior geometry is empty.

### 4.3 No-applicable-feature branch

If the verified crop has no supported, genuinely noncircular targets, or none whose writable ownership can be established, record that evidence explicitly. Distinguish absence from ambiguity and from an unsupported representation.

In a true `NO_APPLICABLE_FEATURE` branch, exercise a compact deterministic control fixture for directional/neighborhood behavior, publish the unchanged full crop and disposition table, commit the bounded implementation/evidence, and **STOP**. This does not demonstrate noncircular transformation on the real crop and does not authorize T03. Do not enlarge a plane, fill a recess, relabel a T01 polygon, or select a different region just to produce visible change.

## 5. Internal checkpoint C — Construct and resolve noncircular proposals

### 5.1 Start from the complete accepted scene

The evolving scene contains accepted T01 geometry, unchanged ORG copper, source references, protected round-priority boundaries, owner-approved positive and negative geometry, and declared ports/corridors. Update the index/scene after each accepted T02 proposal using existing mechanisms.

Make reservations explicit. Positive-copper preservation alone cannot protect a recess: retain a supported keep-clear/negative-geometry representation or an equivalent scene-bound constraint for accepted recesses and owner keep-out edits. Do not derive new semantic reservations from an image. If a relevant reservation has no qualified representation, preserve the accepted neighborhood by bounded no-write protection and disclose the limitation rather than guessing its intended outline.

A later T02 target sees both T01's final contour and all accepted prior T02 contours. The source-only construction contract is: ORG + frozen accepted T01 input/its declared owner-edit provenance + shared T02 policy. EDIT is not consulted by the constructor.

### 5.2 Use the existing propose/decide mechanism

Reuse the current architecture and its compatibility facade. Add a small responsibility-specific T02 module or entry point only as needed; do not re-entangle size selection, recess construction and owner edits or add T02 behavior to the facade itself.

Implement supported directional expansion, bounded length/width changes, or contour adaptation using a qualified local orientation. The original protected contribution, geometry, ports, maximum reach and admitted local space constrain the result. A rotated rectangle must not be widened along the wrong global axis.

Prefer additive growth and trimming of optional new growth as the initial policy. If original noncircular copper is to be shortened or locally removed, first bind the exact editable contribution and retained core/ports in the frozen experimental contract, with existing removal/connectivity checks; otherwise KEEP or abstain. No original trace, T01 contour, protected source overlap, or owner-approved boundary may be removed by this exception.

Growth need not be proportional to original dimensions. Use the bounded available space and declare the actual limiting reasons. Do not fill remote voids or bridge across a trace-only corridor. Exact geometric support is needed for each accepted addition.

Work in a deterministic schedule using ORG descriptors and the frozen current scene; no per-site EDIT dimensions. Existing tie-breaking and scene/version handling should be reused.

### 5.3 Preserve contributed copper and intended separation

When replacing one editable noncircular contribution, do not compute a blind subtraction that removes copper also supplied by protected objects. Preserve the union of retained contributions and their provenance.

T01 is fixed for this stage: do not rerun its growth, reorder priorities, resize its circles, refill recesses, change its accepted contours, or automatically reconcile it to accommodate T02. A conflicting T02 proposal must adapt, KEEP, or abstain. Its conflict may inform a later task, but does not authorize undoing owner acceptance now.

Original trace centerlines and width profiles stay fixed. Existing qualified local attachment overlap may be reused where explicitly admitted, but it is not permission to route, widen, fillet, or construct a new neck. Broad same-component membership does not waive all local separations or authorize new shortcuts.

Reject a failed proposal before it enters the accepted scene. Allow at most one bounded local reconsideration per target under the same hard checks; retain the failed version and limiting reason.

## 6. Verification contract

Read exact thresholds, buffers, precision and curve settings from the latest accepted policy/receipts. Historical T01 reports used a 0.020 mm hard experimental gap, a 0.025 mm construction buffer, and a 0.00001 mm numerical tolerance. Do not assume these are unchanged or turn the construction buffer into a final-clearance claim. A conflict in active numerical policy must be resolved from authoritative records, not by selecting the value that passes.

### Required checks

1. **Baseline admission:** facade/import behavior and deterministic geometry parity, plus exact binding of the final accepted scene and owner edits.
2. **Eligibility:** no generated T01 polygon becomes a new ORG target; no protected rail, plane, trace or recess is treated as a land solely because of appearance.
3. **Directional geometry:** rotation/local-to-world transform controls; open-side growth versus constrained-side response with original shape and policy fixed.
4. **Current-neighbor use:** an actual later T02 proposal reads the accepted T01/current scene. Where a real interaction exists, use a diagnostic replay changing just the relevant earlier addition to its original geometry while holding the policy, target and all other constraints fixed. Label this as a causal test under the shared implementation, not independent kernel validation.
5. **Positive and negative preservation:** accepted T01 contours, round-priority boundaries outside ports, recess/keep-clear masks, original references, fixed traces, protected overlaps and ports remain valid after assembly.
6. **Local validity:** no detached islands, invalid shapes, prohibited new contacts, forbidden gap failures, unqualified original-core removal or changes outside the write scope. Recheck assembled geometry, not only each candidate separately.
7. **Identity and failure behavior:** wrong source/revision, stale scene/index, missing support, invalid feature ownership and conflicting protected contributions fail closed; failed trials do not overwrite accepted scenes.
8. **Determinism and no target leakage:** same accepted input/policy/order gives the same canonical plan and geometry; disabling EDIT access does not alter construction. Explain any frozen T01 owner edits rather than claiming they were newly predicted.
9. **Evidence/rendering:** scene labels and source references distinguish ORG, accepted T01, and incremental T02; changed counts equal the bound disposition records. Reuse existing publication verification without a new presentation assurance project.
10. **Regressions:** run the current applicable T01 tests, new T02 tests, and touched-module/facade/scene/publication regressions. Record exact commands, counts, failures and unrun suites. Do not copy historical suite counts into a new PASS.

Controlled fixtures are useful for mechanisms, but only real-crop evidence demonstrates applicability to this crop. Do not demand three causal examples if only one eligible target interacts. Report the actual number and its limitations.

A static-neighbor comparator is optional, not a prerequisite when targeted current-neighbor tests already suffice. If supplied, hold target set, accepted T01 baseline, reservations, buffer, curve settings, caps and algorithm fixed; only the evolving T02-neighbor updates differ. Report union area, summed additions and assembled violations; an infeasible larger area is not superior.

## 7. Finite task budget and anti-drift rules

Use one main shared policy and deterministic order. At most one clearly labelled diagnostic alternative is allowed for a specific unresolved geometric hypothesis; do not start broad parameter fitting. Unit and fault tests are not extra fitting trials.

No EDIT fitting is required for T02. A clearly qualified descriptive comparison may be retained, but the future 20% residual-reduction objective and final expert-like reconstruction are not T02 acceptance conditions. Do not loosen gap/coverage checks to improve appearance.

Routine source inspection, local fixes, test execution, run generation and report building continue autonomously inside this task. Do not stop after an inventory, parity table, proposal or unit-only implementation when real eligible targets remain to be run.

Conversely, do not repeat T01 owner review or reopen closed audits unless the targeted parity tests reveal a concrete regression relevant to this task. No full CAD/geometry/graph rewrite is justified by an unsupported individual feature.

## 8. Perceivable deliverable

Reuse the current workbench and report builder. Show the same full crop as:

1. ORG, for historical context;
2. latest owner-accepted T01 scene, the actual baseline;
3. T01 plus accepted T02 changes;
4. an incremental T02 delta, proposals and limiting obstacles.

Include both single-color effective copper and a separately labeled change overlay. An irregular T01 shape must not look like a newly edited T02 target simply because of display coloring.

For each treated feature, show original provenance, eligibility reason, accepted/proposed dimensions and orientation, limiting object/reservation, earlier scene version, local gap measurement and result. For KEEP/ABSTAIN show the concrete reason. Provide a recess/priority preservation overlay where relevant.

Keep the display bounded; evidence should be compact and linked, not a new duplication of all historical reports. The actual scene/state used for each screenshot must be retained. Do not represent a planned transformation as executed.

## 9. Deliverables and final stop report

Use the repository's existing output conventions; names below indicate content, not invented APIs:

- T01 baseline/parity receipt and source/accepted-scene bindings;
- T02 feature disposition table and frozen local contract;
- per-target proposals, decisions, failures and accepted scene/delta;
- focused test and relevant regression results with reproduction commands;
- same-frame full-crop review page/images;
- final decision with separate status axes.

Suggested final fields:

```text
task: T02_ONLY
input_base: exact accepted T01 artifact identity
refactor_parity: PASS / FAIL / NOT_ESTABLISHED
execution: COMPLETE / BLOCKED
local_checks: PASS_WITH_SCOPE_LIMITS / FAIL / NOT_ESTABLISHED
real_crop_operation: DEMONSTRATED / NO_APPLICABLE_FEATURE / NOT_DEMONSTRATED
eligible / treated / kept / rejected / unsupported counts
accepted_T01_geometry_and_reservations_preserved: actual result
native_export_this_task: NOT_RUN
global_electrical / manufacturing / EDIT_equivalence: NOT_ESTABLISHED
local_commit / dirty_files_preserved / evidence_paths / reproduction_command
next_action: STOP_FOR_OWNER_REVIEW; T03_NOT_AUTHORIZED
```

`PASS WITH SCOPE LIMITS` requires runtime baseline qualification, valid local behavior, real-crop T02 demonstration on the eligible supported targets, and preserved T01 acceptance. Tests alone are insufficient.

`COMPLETE — NO_APPLICABLE_FEATURE` is a legitimate inventory-backed task result, but not a demonstration of T02 on the real crop. Unknown ownership must remain unknown, not be relabeled as absence.

`PARTIAL` means implementation exists but a material intended feature or required demonstration remains unresolved. `BLOCKED` names the exact missing prerequisite and affected work. No outcome authorizes automatic progression.

Commit only owned code, tests and documentation locally. Keep generated evidence under the established local evidence policy with explicit hashes and paths; do not force-add the historical ignored corpus. Leave unrelated files and prior failures intact. No push.

**STOP after T02, report the result, and await owner review before T03.**
